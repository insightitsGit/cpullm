from types import SimpleNamespace
from unittest.mock import Mock
import pytest

from cpu_llm.cycle_exploration import CycleLimits, Budget, edge_record, explore, explore_snapshot
from cpu_llm.knowledge_graph import Fact
from cpu_llm.research_plan import build_research_plan, select_research_rows
from cpu_llm.document_workflow import plan_document, execute_document


def edge(a, b, relation='causes', doc='d'):
    return edge_record(Fact(a, relation, b, doc, f'{a} {relation.replace("_", " ")} {b}.'))


def search(edges, seed='Alpha', **limits):
    graph = {}
    for e in edges:
        graph.setdefault(e['source'], []).append(e)
    return explore(seed, lambda n: iter(graph.get(n, [])), budget=Budget(CycleLimits(**limits)))


@pytest.mark.parametrize('value', [True, False, 0, -1, 1.5, '1000', 100001])
def test_round_validation(value):
    with pytest.raises(ValueError):
        CycleLimits(max_rounds=value)


def test_round_defaults_and_absolute_ceiling():
    assert CycleLimits().max_rounds == 1000
    assert CycleLimits(max_rounds=100000).max_rounds == 100000


def test_long_cycle_and_all_channel_receipts():
    nodes = ['Alpha'] + [f'Node{i}' for i in range(15)] + ['Alpha']
    result = search([edge(a,b) for a,b in zip(nodes,nodes[1:])])
    assert result['complete'] and len(result['cycles']) == 1
    assert result['cycles'][0]['length'] == 16
    assert set(result['cycles'][0]['edges'][0]['channels']['channels']) == {
        'dense','relational','disentangled','hyperbolic','identity','causal'}
    assert result['inferred_facts'] == []


def test_multiple_cycles_and_subcycles_are_bounded():
    result = search([edge('Alpha','Beta'), edge('Beta','Alpha'), edge('Beta','Gamma'),
                     edge('Gamma','Beta'), edge('Gamma','Alpha')])
    assert sorted(c['length'] for c in result['cycles']) == [2,3]
    assert result['complete']


def test_shared_node_alternative_paths_are_not_lost():
    result=search([edge('Alpha','Beta'),edge('Alpha','Gamma'),edge('Beta','Delta'),
                   edge('Gamma','Delta'),edge('Delta','Alpha')])
    assert len(result['cycles']) == 2


def test_alias_only_and_self_loops_do_not_qualify():
    assert not search([edge('Alpha','Alpha')])['cycles']
    assert not search([edge('Alpha','Beta','alias_of'),edge('Beta','Alpha','alias_of')])['cycles']


def test_budget_outcomes_and_acyclic_search():
    edges=[edge('Alpha','Beta'),edge('Beta','Alpha')]
    assert search(edges,max_rounds=1)['stop_reason']=='max_rounds'
    assert search(edges,max_edges=1)['stop_reason']=='edges_limit'
    assert search(edges,max_cycles=1)['stop_reason']=='result_limit'
    assert search([edge('Alpha','Beta')])['cycles']==[]


def test_deadline_cancellation_and_shared_ledger():
    clock=Mock(side_effect=[0,10])
    r=explore('Alpha',lambda n:(),budget=Budget(clock=clock))
    assert r['stop_reason']=='deadline'
    assert explore('Alpha',lambda n:(),cancelled=lambda:True)['stop_reason']=='cancelled'
    budget=Budget(CycleLimits(max_states=1))
    explore('Alpha',lambda n:(),budget=budget)
    assert explore('Beta',lambda n:(),budget=budget)['stop_reason']=='states_limit'


def test_snapshot_permissions_atomic_proofs_and_no_reverse_bounce():
    rows=[dict(document_id='one',chunk_text='Alpha causes Beta.'),
          dict(document_id='two',chunk_text='Beta causes Alpha.')]
    assert not explore_snapshot('Alpha',rows,allowed={'one'})['cycles']
    r=explore_snapshot('Alpha',rows)
    assert len(r['cycles'])==1
    for e in r['cycles'][0]['edges']:
        source=next(row['chunk_text'] for row in rows if row['document_id']==e['document_id'])
        p=e['proof']
        assert source[p['start']:p['end']]==p['quote']
    assert not explore_snapshot('Alpha',[rows[0]])['cycles']


def test_research_plan_does_not_assume_causes_and_preserves_spans():
    message='Write a detailed report about Helios.'
    p=build_research_plan(message,plan_document(message))
    assert all(message[r['start']:r['end']]==r['value'] for r in p['requirements'])
    assert 'cause' not in [q['facet'] for q in p['questions']]
    assert 'assuming their premises' in p['expanded_prompt']
    assert build_research_plan(message,plan_document(message))['plan_hash']==p['plan_hash']


def test_negated_why_and_quoted_directives_do_not_expand_causes():
    for suffix in [' Do not explain why.', ' "why"']:
        p=build_research_plan('Write a report about Helios.'+suffix,plan_document('Write a report about Helios.'))
        assert 'cause' not in [q['facet'] for q in p['questions']]


def test_separate_topics_retrieve_independent_atomic_evidence():
    m='Write an article about Helios and PostgreSQL.'
    p=build_research_plan(m,plan_document(m))
    rows=[dict(document_id='a',chunk_text='Helios is a backup service.'),
          dict(document_id='b',chunk_text='PostgreSQL is a database.'),
          dict(document_id='c',chunk_text='Other is a tool.')]
    assert [r['document_id'] for r in select_research_rows(p,rows)]==['a','b']
    assert not p['coverage']['question_answers_verified']


def app(rows):
    return SimpleNamespace(tenant_id='t', guard=SimpleNamespace(check=lambda _:SimpleNamespace(decision='allow')),
                           index=SimpleNamespace(strict_source_rows=Mock(return_value=(rows,123))))


def test_document_integration_and_strict_isolation():
    rows=[dict(document_id='a',chunk_text='Helios is a backup service.'),
          dict(document_id='b',chunk_text='PostgreSQL is a database.'),
          dict(document_id='c',chunk_text='Unrelated is a tool.')]
    m='Write an article about Helios and PostgreSQL.'
    r=execute_document(app(rows),m,plan_document(m))
    assert {p['document_id'] for p in r['answer_evidence']}=={'a','b'}
    assert r['research_plan']['budget']['snapshot_reads']==1
    assert r['document']['coverage']['snapshot']['scanned_chunks']==3
    r=execute_document(app(rows),m,plan_document(m),strict=True)
    assert 'research_plan' not in r and r['answer_evidence']==[]


def test_document_missing_context_stops_before_retrieval():
    a=app([]); m='Draft an email about it.'
    r=execute_document(a,m,plan_document(m))
    assert r['needs_clarification']
    a.index.strict_source_rows.assert_not_called()


def test_cycle_api_strict_floor_and_scope():
    from cpu_llm.cycle_exploration import execute_cycle_request
    from cpu_llm.access import CallerContext
    a=app([dict(document_id='one',chunk_text='Alpha causes Beta.'),
           dict(document_id='two',chunk_text='Beta causes Alpha.')])
    r=execute_cycle_request(a,'Explore Alpha',dict(seed='Alpha'),strict=True)
    assert r['answer_status']=='unsupported'
    a.index.strict_source_rows.assert_not_called()
    r=execute_cycle_request(a,'Explore Alpha',dict(seed='Alpha'),caller=CallerContext.make('t','user',{'one'}))
    assert not r['cycle_exploration']['cycles']
    r=execute_cycle_request(a,'Explore Alpha',dict(seed='Alpha'))
    assert len(r['answer_evidence'])==2 and not r['audit_passed']


def test_follow_related_evidence_does_not_assert_inheritance():
    rows=[dict(document_id='a',chunk_text='Lobster is a crustacean.'),
          dict(document_id='b',chunk_text='The lifespan of crustacean is 20 years.')]
    m='Write an article about Lobster.'
    r=execute_document(app(rows),m,plan_document(m))
    assert {p['document_id'] for p in r['answer_evidence']}=={'a','b'}
    assert all(p['quote']==row['chunk_text'] for p,row in zip(r['answer_evidence'], rows))
    assert r['research_plan']['research_leads']['hop_limit']==1


def test_appliance_ask_routes_explicit_cycles_and_strict_floor():
    from cpu_llm.pipeline import Appliance
    a=object.__new__(Appliance)
    helper=app([dict(document_id='a',chunk_text='Alpha causes Beta.'),
                dict(document_id='b',chunk_text='Beta causes Alpha.')])
    a.__dict__.update(helper.__dict__)
    r=a.ask('Explore Alpha',cycle_search={'seed':'Alpha'},as_of=42)
    assert len(r['cycle_exploration']['cycles'])==1
    a.index.strict_source_rows.assert_called_once_with(None,as_of=42)
    a.strict_evidence=True
    assert a.ask('Explore Alpha',cycle_search={'seed':'Alpha'})['answer_status']=='unsupported'


def test_email_recipient_is_presentation_not_send_authority():
    m='Draft a concise email to Alex about Helios.'
    p=plan_document(m)
    assert p['recipient']=='Alex' and p['topic']=='Helios' and p['detail']=='brief'
    r=execute_document(app([dict(document_id='a',chunk_text='Helios is a backup service.')]),m,p)
    assert r['research_plan']['recipient']=='Alex'
    assert not r['research_plan']['sending_authorized']
    a=app([])
    assert execute_document(a,m,p,strict=True)['answer_status']=='unsupported'
    a.index.strict_source_rows.assert_not_called()


def test_duplicate_claim_retains_independent_proofs_not_duplicate_cycles():
    rows=[dict(document_id='a',chunk_text='Alpha causes Beta.'),
          dict(document_id='b',chunk_text='Alpha causes Beta.'),
          dict(document_id='c',chunk_text='Beta causes Alpha.')]
    from cpu_llm.cycle_exploration import execute_cycle_request
    r=execute_cycle_request(app(rows),'Explore Alpha',{'seed':'Alpha'})
    assert len(r['cycle_exploration']['cycles'])==1
    assert {p['document_id'] for p in r['answer_evidence']}=={'a','b','c'}


@pytest.mark.parametrize('limit,expected', [({'max_nodes':1},'nodes_limit'),
    ({'max_frontier':1},'frontier_limit'), ({'max_bytes':1},'bytes_limit')])
def test_other_resource_caps_are_enforced(limit,expected):
    r=search([edge('Alpha','Beta'),edge('Alpha','Gamma')],**limit)
    assert not r['complete'] and r['stop_reason']==expected
