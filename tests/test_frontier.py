import hashlib
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cpu_llm.frontier import (
    HARD_CAP, Candidate, DeductiveContext, Edge, FrontierLimits, abductive_check, batches, build_graph,
    compose, deductive_check, edge_support, frontier_seed, generate, lexical_relations, path_support,
    pre_thinker_check, rank_key, run_frontier, scope_edges, source_support, topic_focus,
    validate_frontier_option,
)
from cpu_llm.cycle_exploration import Budget, StopSearch
from cpu_llm.invention import NOTE
from cpu_llm.pipeline import Appliance
from cpu_llm.serve import _dispatch

_NAMES = ['wafer', 'lithography', 'packaging', 'substrate', 'cooling', 'transformer', 'turbine', 'permit',
          'labor', 'tariff']
_OUTPUTS = ['training', 'inference', 'serving', 'research', 'deployment', 'evaluation', 'robotics', 'search']


@pytest.fixture(autouse=True)
def regex_parser(monkeypatch, request):
    """Unit tests pin the regex reader; the dependency-parser tests opt out."""
    if 'dependency_parser' not in request.node.name:
        monkeypatch.setenv('FRONTIER_PARSER', 'regex')


def rows_of(*texts, prefix='doc'):
    return [dict(document_id=f'{prefix}{i}-p0001', chunk_text=text) for i, text in enumerate(texts, 1)]


def wide_corpus():
    """Ten upstream limits on one hub and eight downstream uses: many cross-chunk readings."""
    texts = [f'{name.title()} supply limits accelerator capacity.' for name in _NAMES]
    texts += [f'Accelerator capacity drives {name} throughput.' for name in _OUTPUTS]
    return rows_of(*texts)


def small_corpus():
    return rows_of('Memory bandwidth limits inference throughput.',
                   'Inference throughput drives serving revenue.',
                   'HBM supply constrains memory bandwidth.')


def edge(subject, kind, obj, doc='a-p1', quote=None, hedged=False):
    quote = quote or f'{subject} {kind} {obj}.'
    proof = dict(document_id=doc, quote=quote, start=0, end=len(quote),
                 chunk_sha256=hashlib.sha256(quote.encode()).hexdigest())
    from cpu_llm.frontier import term_key
    return Edge(subject, subject, term_key(subject), kind, obj, term_key(obj), True, [proof], hedged, False, 'test')


def appliance(rows):
    app = object.__new__(Appliance)
    app.tenant_id = 'test'
    app.small_talk = False
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow'))
    # The index exposes only the read used by the snapshot. Any write would fail.
    app.index = SimpleNamespace(strict_source_rows=Mock(return_value=(rows, 123)))
    return app


# ------------------------------------------------------------------ triggers and options

@pytest.mark.parametrize('message, topic', [
    ('Frontier: AI bottlenecks.', 'AI bottlenecks'), ('frontier: AI energy bottlenecks', 'AI energy bottlenecks'),
    ('Please Frontier: chips!', 'chips'), ('Frontier:', ''),
])
def test_prompt_trigger_extracts_the_topic(message, topic):
    assert frontier_seed(message) == topic


@pytest.mark.parametrize('message', ['What is the frontier of AI?', 'Research AI bottlenecks.',
                                     'Explain frontier models.'])
def test_other_prompts_do_not_trigger(message):
    assert frontier_seed(message) is None
    assert frontier_seed(message, forced=True) == message.rstrip('.?')


def test_option_validation_and_limit_ceilings():
    assert validate_frontier_option(None) is None and validate_frontier_option(False) is None
    assert validate_frontier_option(True)['limits'] == FrontierLimits()
    option = validate_frontier_option(dict(topic='chips', limits=dict(max_candidates=10)))
    assert option['topic'] == 'chips' and option['limits'].max_candidates == 10
    for bad in ['yes', dict(seed='x'), dict(limits=dict(unknown=1)), dict(limits=dict(max_results=51)),
                dict(limits=dict(max_rounds=100_001)), dict(limits=dict(max_seconds=0)),
                dict(limits=dict(max_path_edges=1)), dict(limits=dict(min_results=20, max_results=10))]:
        with pytest.raises(ValueError):
            validate_frontier_option(bad)


# ------------------------------------------------------------------ relation extraction

@pytest.mark.parametrize('sentence, expected', [
    ('Memory bandwidth limits inference throughput.', ('Memory bandwidth', 'constrains', 'inference throughput')),
    ('Data center power demand is constrained by grid interconnection queues.',
     ('grid interconnection queues', 'constrains', 'Data center power demand')),
    ('Training large models requires vast amounts of electricity.',
     ('electricity', 'constrains', 'Training large models')),
    ('Compute demand grows with model size.', ('model size', 'increases', 'Compute demand')),
    ('The cost per token falls as hardware efficiency rises.',
     ('hardware efficiency', 'decreases', 'cost per token')),
])
def test_lexical_relations_read_cause_to_effect(sentence, expected):
    [(subject, kind, obj, negative, _)] = list(lexical_relations(sentence))
    assert (subject, kind, obj) == expected and not negative


def test_negation_is_recorded_and_conditionals_are_skipped():
    [(_, _, _, negative, _)] = list(lexical_relations('Export controls do not reduce domestic compute supply.'))
    assert negative
    assert list(lexical_relations('If energy prices rise, energy limits training.')) == []


# ------------------------------------------------------------------ abductive check

def test_abductive_check_composes_signs_and_rejects_incoherent_chains():
    up, down = edge('chip supply', 'increases', 'compute'), edge('compute', 'decreases', 'training time', 'b-p1')
    reading, reason = abductive_check(Candidate('chain', (up, down)))
    assert reason is None and reading['relation'] == 'decreases' and reading['via'] == ['compute']
    taxonomy = Candidate('chain', (edge('gpu', 'is_a', 'accelerator'), edge('accelerator', 'is_a', 'chip', 'b-p1')))
    assert abductive_check(taxonomy) == (None, 'no_explanatory_relation')
    backwards = Candidate('chain', (edge('energy', 'constrains', 'gpu'), edge('gpu', 'is_a', 'chip', 'b-p1')))
    assert abductive_check(backwards) == (None, 'incoherent_composition')
    assert compose('constrains', 'constrains') == ('constrains', 1.0)
    assert compose('decreases', 'decreases') == ('increases', 1.0)
    assert compose('is_a', 'is_a') is None


def test_abductive_check_reads_convergent_and_divergent_pairs():
    a, b = edge('energy', 'constrains', 'training'), edge('data', 'constrains', 'training', 'b-p1')
    reading, _ = abductive_check(Candidate('convergent', (a, b)))
    assert reading['relation'] == 'co_constrain'
    up, down = edge('efficiency', 'increases', 'throughput'), edge('heat', 'decreases', 'throughput', 'b-p1')
    assert abductive_check(Candidate('convergent', (up, down)))[0]['relation'] == 'offset'
    left, right = edge('demand', 'increases', 'chip prices'), edge('demand', 'increases', 'power use', 'b-p1')
    assert abductive_check(Candidate('divergent', (left, right)))[0]['relation'] == 'common_driver'
    structural = Candidate('convergent', (edge('gpu', 'is_a', 'chip'), b))
    assert abductive_check(structural) == (None, 'no_explanatory_relation')


# ------------------------------------------------------------------ deductive check

def _deduce(rows, candidate):
    graph = build_graph(rows, Budget(FrontierLimits()))
    reading, reason = abductive_check(candidate)
    assert reason is None
    return deductive_check(candidate, reading, DeductiveContext(rows, graph, ['throughput']))


def _graph_edges(rows):
    graph = build_graph(rows, Budget(FrontierLimits()))
    return graph, {(e.subject_key, e.object_key): e for e in graph.edges.values()}


def test_deductive_check_rejects_a_negated_conclusion():
    rows = small_corpus() + rows_of('Memory bandwidth does not limit serving revenue.', prefix='neg')
    _, edges = _graph_edges(rows)
    chain = Candidate('chain', (edges['memory bandwidth', 'inference throughput'],
                                edges['inference throughput', 'serving revenue']))
    assert _deduce(rows, chain) == (None, 'conclusion_contradicted')


def test_deductive_check_rejects_a_premise_with_an_opposite_source_claim():
    rows = small_corpus() + rows_of('Inference throughput reduces serving revenue.', prefix='opp')
    _, edges = _graph_edges(rows)
    key = ('inference throughput', 'serving revenue')
    drive = next(e for e in build_graph(rows, Budget(FrontierLimits())).edges.values()
                 if (e.subject_key, e.object_key) == key and e.kind == 'increases')
    chain = Candidate('chain', (edges['memory bandwidth', 'inference throughput'], drive))
    assert _deduce(rows, chain) == (None, 'premise_contradicted')


def test_deductive_check_rejects_an_unverified_premise_and_scores_relevance():
    rows = small_corpus()
    _, edges = _graph_edges(rows)
    first, second = edges['memory bandwidth', 'inference throughput'], edges['inference throughput', 'serving revenue']
    reading, reason = _deduce(rows, Candidate('chain', (first, second)))
    assert reason is None and 0 < reading['deductive_relevance'] <= 1
    tampered = Edge(**{**first.__dict__, 'proofs': [dict(first.proofs[0], quote='Memory bandwidth is unlimited.')]})
    assert _deduce(rows, Candidate('chain', (tampered, second))) == (None, 'premise_not_verified')


def test_deductive_check_uses_the_registered_rule_engine():
    rows = rows_of('Accelerator capacity limits training runs.', 'Packaging limits accelerator capacity.',
                   'Training runs require packaging.')
    _, edges = _graph_edges(rows)
    chain = Candidate('chain', (edges['packaging', 'accelerator capacity'],
                                edges['accelerator capacity', 'training run']))
    graph = build_graph(rows, Budget(FrontierLimits()))
    context = DeductiveContext(rows, graph, [])
    reading, _ = abductive_check(chain)
    reading, reason = deductive_check(chain, reading, context)
    assert reason is None and reading['rule_verdict'] == 'ENTAILED_BY_RULES'
    context.rule_verdict = lambda *_: 'CONTRADICTED_BY_RULES'
    reading, _ = abductive_check(chain)
    assert deductive_check(chain, reading, context) == (None, 'rule_contradiction')


# ------------------------------------------------------------------ pre-thinker validation

def _pre(candidate, rows):
    graph = build_graph(rows, Budget(FrontierLimits()))
    reading, _ = abductive_check(candidate)
    return pre_thinker_check(candidate, reading, graph)


def test_pre_thinker_rejects_malformed_and_circular_candidates():
    rows = small_corpus()
    malformed = Candidate('chain', (edge('it', 'constrains', 'memory bandwidth'),
                                    edge('memory bandwidth', 'constrains', 'growth of', 'b-p1')))
    assert _pre(malformed, rows) == (None, 'malformed')
    circular = Candidate('chain', (edge('memory bandwidth', 'constrains', 'throughput'),
                                   edge('throughput', 'increases', 'memory bandwidth', 'b-p1')))
    assert _pre(circular, rows) == (None, 'circular')
    nested = Candidate('chain', (edge('memory', 'constrains', 'throughput'),
                                 edge('throughput', 'increases', 'memory bandwidth', 'b-p1')))
    assert _pre(nested, rows) == (None, 'circular')


def test_pre_thinker_rejects_single_source_and_restated_candidates():
    rows = small_corpus()
    single = Candidate('chain', (edge('hbm supply', 'constrains', 'memory bandwidth', 'a-p1'),
                                 edge('memory bandwidth', 'constrains', 'inference throughput', 'a-p1')))
    assert _pre(single, rows) == (None, 'single_source')
    restated_rows = rows + rows_of('Memory bandwidth ultimately limits serving revenue.', prefix='r')
    chain = Candidate('chain', (edge('memory bandwidth', 'constrains', 'inference throughput', 'a-p1'),
                                edge('inference throughput', 'increases', 'serving revenue', 'b-p1')))
    assert _pre(chain, restated_rows) == (None, 'restates_source')
    reading, reason = _pre(chain, rows)
    assert reason is None and reading['co_mentions'] == 0


# ------------------------------------------------------------------ scoring and ranking

def test_scores_follow_the_documented_formulas():
    assertive, hedged = edge('a', 'increases', 'b'), edge('b', 'increases', 'c', hedged=True)
    assert edge_support(assertive) == 0.8 and edge_support(hedged) == 0.55
    corroborated = edge('a', 'increases', 'b')
    corroborated.proofs += [dict(corroborated.proofs[0], document_id=d) for d in ('b-p1', 'c-p1', 'd-p1')]
    assert edge_support(corroborated) == pytest.approx(1.0)
    assert path_support((assertive, hedged)) == 0.55
    assert source_support([(assertive,), (hedged,)]) == pytest.approx(1 - 0.2 * 0.45)


def test_ranking_is_support_then_relevance_then_novelty():
    def item(support, relevance, novelty, name):
        return dict(id=name, scores=dict(source_support=support, deductive_relevance=relevance, novelty=novelty))
    items = [item(0.8, 0.9, 0.9, 'a'), item(0.9, 0.1, 0.1, 'b'), item(0.8, 0.9, 0.95, 'c'), item(0.8, 0.95, 0.1, 'd')]
    assert [i['id'] for i in sorted(items, key=rank_key)] == ['b', 'd', 'c', 'a']


def test_every_survivor_has_three_bounded_scores_citations_and_a_falsification_test():
    receipt = run_frontier('accelerator capacity', wide_corpus())
    assert receipt['hypotheses']
    for item in receipt['hypotheses']:
        assert set(item['scores']) == {'source_support', 'deductive_relevance', 'novelty'}
        assert all(0 <= value <= 1 for value in item['scores'].values())
        assert item['claim_status'] == 'UNVERIFIED_HYPOTHESIS' and item['promotion'] == 'blocked'
        assert len(item['source_ids']) >= 2 and all(c['quote'] for c in item['citations'])
        assert item['falsification_test'].startswith(('Compare', 'Relieve', 'Measure', 'Vary', 'Track'))
    assert receipt['hypotheses'] == sorted(receipt['hypotheses'], key=rank_key)


# ------------------------------------------------------------------ cap, shortage and budgets

def test_output_is_capped_at_fifty():
    receipt = run_frontier('accelerator capacity', wide_corpus())
    assert receipt['survivors'] > HARD_CAP
    assert len(receipt['hypotheses']) == HARD_CAP and receipt['status'] == 'hypotheses'
    assert receipt['shortage'] is None and not receipt['incomplete']
    smaller = run_frontier('accelerator capacity', wide_corpus(), limits=FrontierLimits(max_results=12))
    assert len(smaller['hypotheses']) == 12


def test_a_shortage_is_reported_without_padding():
    receipt = run_frontier('inference', small_corpus())
    assert 0 < len(receipt['hypotheses']) < 10 and receipt['status'] == 'shortage'
    assert receipt['shortage']['returned'] == len(receipt['hypotheses'])
    from cpu_llm.frontier import format_reply
    assert 'not padded' in format_reply(receipt)


def test_candidate_round_and_edge_budgets_stop_the_run_and_flag_it():
    by_candidates = run_frontier('accelerator capacity', wide_corpus(),
                                 limits=FrontierLimits(max_candidates=40, batch_size=16))
    assert by_candidates['incomplete'] and by_candidates['stop_reason'] == 'candidates_limit'
    assert by_candidates['candidates_generated'] <= 40
    by_rounds = run_frontier('accelerator capacity', wide_corpus(), limits=FrontierLimits(max_rounds=2, batch_size=8))
    assert by_rounds['stop_reason'] == 'rounds_limit' and by_rounds['candidates_generated'] == 16
    by_edges = run_frontier('accelerator capacity', wide_corpus(), limits=FrontierLimits(max_edges=5))
    assert by_edges['incomplete'] and by_edges['stop_reason'] == 'edges_limit'
    by_memory = run_frontier('accelerator capacity', wide_corpus(), limits=FrontierLimits(max_bytes=4000))
    assert by_memory['incomplete'] and by_memory['stop_reason'] == 'bytes_limit'
    from cpu_llm.frontier import format_reply
    assert 'Search incomplete' in format_reply(by_candidates)


def test_the_deadline_stops_the_run():
    ticks = iter(range(10_000))
    receipt = run_frontier('accelerator capacity', wide_corpus(),
                           limits=FrontierLimits(max_seconds=30), clock=lambda: next(ticks))
    assert receipt['incomplete'] and receipt['stop_reason'] == 'deadline'


def test_generation_is_streamed_in_batches():
    rows = wide_corpus()
    budget = Budget(FrontierLimits())
    budget.counters = dict(rounds=0, candidates=0, edges=0, bytes=0)
    graph = build_graph(rows, budget)
    _, _, focus = topic_focus('accelerator capacity', graph)
    stream = generate(scope_edges(graph, focus), FrontierLimits())
    assert inspect.isgenerator(stream)
    sizes = [len(batch) for batch in batches(stream, 7, budget)]
    assert max(sizes) == 7 and budget.counters['rounds'] == len(sizes)
    assert budget.counters['candidates'] == sum(sizes)


def test_three_edge_chains_are_optional():
    two = run_frontier('inference', small_corpus())
    three = run_frontier('inference', small_corpus(), limits=FrontierLimits(max_path_edges=3))
    assert three['candidates_generated'] > two['candidates_generated']


# ------------------------------------------------------------------ appliance and HTTP

def test_ask_runs_frontier_from_the_prompt_and_appends_the_note():
    app = appliance(wide_corpus())
    result = app.ask('Frontier: accelerator capacity.')
    receipt = result['frontier']
    assert result['answer_status'] == 'hypotheses' and len(receipt['hypotheses']) == HARD_CAP
    assert set(receipt) >= {'status', 'hypotheses', 'candidates_generated', 'candidates_passed',
                            'budget_used', 'incomplete'}
    assert set(receipt['candidates_passed']) == {'abductive', 'deductive', 'pre_thinker'}
    assert receipt['index_write'] is False and receipt['promotion'] == 'blocked'
    assert result['reply']['text'].endswith(NOTE) and result['reply']['text'].count(NOTE) == 1
    assert result['routing']['post_stages'][0] == 'frontier_snapshot'
    app.index.strict_source_rows.assert_called_once()


def test_python_flag_and_option_topic():
    app = appliance(small_corpus())
    assert app.ask('inference', frontier=True)['frontier']['topic'] == 'inference'
    result = app.ask('anything', frontier=dict(topic='memory bandwidth', limits=dict(max_path_edges=3)))
    assert result['frontier']['topic'] == 'memory bandwidth'
    assert result['frontier']['limits']['max_path_edges'] == 3


def test_strict_evidence_disables_frontier_without_a_snapshot():
    app = appliance(wide_corpus())
    result = app.ask('Frontier: accelerator capacity.', strict_evidence=True)
    assert result['answer_status'] == 'unsupported' and 'frontier' not in result
    app.index.strict_source_rows.assert_not_called()
    assert app.ask('[strict-evidence]\nFrontier: accelerator capacity.')['answer_status'] == 'unsupported'


def test_frontier_refuses_other_specialists_and_missing_topics():
    app = appliance(small_corpus())
    with pytest.raises(ValueError, match='separately'):
        app.ask('Frontier: inference.', invent=True)
    with pytest.raises(ValueError, match='separately'):
        app.ask('Frontier: inference.', cycle_search=dict(seed='x'))
    assert app.ask('Frontier:')['answer_status'] == 'needs_clarification'


def test_blocked_guard_and_unknown_topic():
    app = appliance(small_corpus())
    app.guard = SimpleNamespace(check=lambda _: SimpleNamespace(decision='block'))
    assert app.ask('Frontier: inference.')['answer_status'] == 'blocked'
    app = appliance(small_corpus())
    result = app.ask('Frontier: photosynthesis.')
    assert result['answer_status'] == 'insufficient_evidence' and result['frontier']['hypotheses'] == []


def test_http_forwards_and_validates_the_frontier_field():
    entry = SimpleNamespace(ask=lambda secret, message, **kwargs: kwargs)
    assert _dispatch(entry, '/v1/ask', 'test-only', dict(message='AI', frontier=True))[1] == dict(frontier=True)
    with pytest.raises(ValueError):
        _dispatch(entry, '/v1/ask', 'test-only', dict(message='AI', frontier='yes'))


def test_background_topic_words_anchor_only_when_the_focus_is_too_narrow():
    rows = wide_corpus()
    narrow = run_frontier('accelerator capacity wafer', rows)
    assert narrow['focus_terms'] == ['accelerator', 'capacity', 'wafer'] and narrow.get('focus_fallback')
    graph = build_graph(rows, Budget(FrontierLimits()))
    _, present, focus = topic_focus('accelerator wafer', graph)
    assert present == ['accelerator', 'wafer'] and focus == ['wafer']   # accelerator is in every chunk


@pytest.mark.parametrize('sentence, expected', [
    ('Integrated information theory entails panpsychism.', ('Integrated information theory', 'supports', 'panpsychism')),
    ('The knowledge argument undermines physicalism.', ('knowledge argument', 'undermines', 'physicalism')),
    ('Illusionism is incompatible with phenomenal realism.', ('Illusionism', 'undermines', 'phenomenal realism')),
    ('Global workspace theory cannot explain phenomenal character.',
     ('Global workspace theory', 'undermines', 'phenomenal character')),
])
def test_argument_relations_for_philosophical_prose(sentence, expected):
    [(subject, kind, obj, negative, _)] = list(lexical_relations(sentence))
    assert (subject, kind, obj) == expected and not negative


def test_argument_relations_compose_by_sign():
    assert compose('supports', 'supports') == ('supports', 1.0)
    assert compose('supports', 'undermines') == ('undermines', 1.0)
    assert compose('undermines', 'undermines') == ('affects', 0.5)
    assert compose('supports', 'increases') == ('affects', 0.6)
    rows = rows_of('Integrated information theory entails panpsychism.',
                   'Panpsychism supports the intrinsic nature view.', 'The combination problem undermines panpsychism.')
    receipt = run_frontier('panpsychism', rows)
    texts = [h['text'] for h in receipt['hypotheses']]
    assert any('Integrated information theory may support intrinsic nature view through panpsychism' in t for t in texts)
    assert 'combination problem may undermine intrinsic nature view through panpsychism.' in texts
    assert any('may be cancelled by combination problem' in t for t in texts)


def test_double_descent_is_a_term_not_a_cue():
    assert list(lexical_relations('Model-wise double descent occurs near the interpolation threshold.')) == []
    [(_, kind, obj, _, _)] = list(lexical_relations('Compute demand doubles every year.'))
    assert kind == 'increases'



def test_hub_terms_are_spread_but_never_cause_a_shortage():
    receipt = run_frontier('accelerator capacity', wide_corpus())
    assert len(receipt['hypotheses']) == HARD_CAP      # one hub only: the cap re-orders, it does not drop
    two_hubs = wide_corpus() + rows_of(*[f'Grid {name} limits cooling capacity.' for name in _NAMES[:4]],
                                       'Cooling capacity drives rack density.', prefix='grid')
    hubs = [h['hub'] for h in run_frontier('capacity', two_hubs)['hypotheses'][:6]]
    assert len(set(hubs)) >= 2


def test_encoder_rejects_head_noun_bridges_that_mean_different_things():
    rows = rows_of('Chip supply limits training capacity.', 'Grid capacity drives data center growth.')
    plain = run_frontier('capacity', rows)
    assert plain['bridge_check'] == 'head_noun' and plain['candidates_passed']['abductive'] >= 1
    import numpy as np
    def encode(texts):
        return np.array([[1.0, 0.0] if 'training' in t else [0.0, 1.0] for t in texts])
    checked = run_frontier('capacity', rows, encode=encode)
    assert checked['bridge_check'] == 'encoder' and checked['encoded_terms'] >= 2
    assert checked['candidates_rejected'].get('abductive:unrelated_bridge', 0) >= 1
    assert checked['candidates_passed']['abductive'] < plain['candidates_passed']['abductive']


def _spacy_model():
    from cpu_llm.frontier import parser
    import os
    os.environ.pop('FRONTIER_PARSER', None)
    return parser()


def test_dependency_parser_reads_clean_noun_phrases():
    nlp = _spacy_model()
    if nlp is None:
        pytest.skip('no spaCy English model installed')
    from cpu_llm.frontier import parsed_relations
    cases = {
        'Memory bandwidth, rather than compute, increasingly limits the throughput of large language models.':
            ('Memory bandwidth', 'constrains', 'throughput of large language models'),
        'Training large models requires vast amounts of electricity.':
            ('electricity', 'constrains', 'Training large models'),
        'Data center growth is constrained by grid interconnection queues.':
            ('grid interconnection queues', 'constrains', 'Data center growth'),
        'Integrated information theory entails a form of panpsychism.':
            ('Integrated information theory', 'supports', 'form of panpsychism'),
    }
    for sentence, (subject, kind, obj) in cases.items():
        found = {(a, k, b) for a, k, b, _, _ in parsed_relations(nlp(sentence))}
        assert any(k == kind and subject in a and obj.split()[-1] in b for a, k, b in found), (sentence, found)
    assert list(parsed_relations(nlp('Does memory bandwidth limit inference?'))) == []
    [(_, _, _, negative, _)] = list(parsed_relations(nlp('Export controls do not reduce domestic supply.')))
    assert negative
