import copy
import itertools
import json
from pathlib import Path

import pytest

from cpu_llm.flag_contract import (FLAG_BINDINGS, enforce_node_request, enforce_response_flags,
    mapping_records, next_optional, validate_graph_consumers)
from cpu_llm.response_policy import classify_response_request
from cpu_llm.classifier import (summary_trigger, list_trigger, source_trigger,
    explain_trigger, deep_search_trigger, math_trigger)


def test_mapping_is_complete_unique_and_matches_versioned_table():
    assert len({b.path for b in FLAG_BINDINGS}) == len(FLAG_BINDINGS)
    path = Path(__file__).resolve().parents[1] / 'docs/prompt-flag-map.json'
    assert json.loads(path.read_text()) == json.loads(json.dumps(mapping_records()))


def test_optional_combinations_have_one_stable_order_without_repeating_agents():
    names = ['deep', 'creative', 'compare', 'list', 'math', 'finance', 'frame', 'sources']
    for values in itertools.product([False, True], repeat=len(names)):
        state = dict(zip(names, values), guard_decision='allow')
        expected = [node for node, enabled in [
            ('deep', state['deep']), ('gather', state['creative']), ('compare', state['compare']),
            ('brief', state['list'] or state['sources']), ('math', state['math']),
            ('finance', state['finance']), ('frame', state['frame'])] if enabled]
        actual, after = [], 'shine'
        for _ in range(8):
            node = next_optional(state, after)
            if node == 'model01':
                break
            actual.append(node)
            after = 'imagine' if node == 'gather' else node
        assert actual == expected


@pytest.mark.parametrize('hold', [{'delivery_blocked': 'audit'}, {'shine_enforced': True}, {'shine_ok': False}])
def test_delivery_holds_are_rechecked_after_every_optional_agent(hold):
    state = dict(deep=True, creative=True, compare=True, summarize=True, frame=True,
                 math=True, finance=True, guard_decision='allow', **hold)
    for after in ['shine', 'deep', 'imagine', 'compare', 'brief']:
        assert next_optional(state, after) == 'math'
    assert next_optional(state, 'math') == 'finance'
    assert next_optional(state, 'finance') == 'model01'
    with pytest.raises(ValueError):
        enforce_node_request('compare', state)
    enforce_node_request('math', state)
    assert next_optional(dict(state, guard_decision='block'), 'shine') == 'reply'


def test_unrequested_nodes_and_missing_consumers_are_rejected():
    with pytest.raises(ValueError):
        enforce_node_request('deep', dict(guard_decision='allow'))
    with pytest.raises(ValueError, match='brief'):
        validate_graph_consumers({n for b in FLAG_BINDINGS for n in b.consumers} - {'brief'})


@pytest.mark.parametrize('change', [
    lambda p: p['flags'].update(html=True),
    lambda p: p['flags'].update(table=True),
    lambda p: p['flags'].update(mystery=True),
    lambda p: p['flags'].update(expand_retrieval=False),
    lambda p: p.update(retrieval_budget=5),
])
def test_inconsistent_flags_cannot_reach_consumers(change):
    plan = copy.deepcopy(classify_response_request('Explain the Aster in detail.'))
    change(plan)
    with pytest.raises(ValueError):
        enforce_response_flags(plan)


def test_data_words_and_negated_controls_do_not_select_agents():
    for trigger, prompt in [(summary_trigger, 'What is a summary?'),
                            (list_trigger, 'What is the list archive?'),
                            (source_trigger, 'What are sources?'),
                            (explain_trigger, 'What is the explain command?'),
                            (deep_search_trigger, 'What is deep search?'),
                            (math_trigger, 'What is the title "2 + 3"?')]:
        assert trigger(prompt) == []
    assert deep_search_trigger('Do not run a deep search.') == []
    assert source_trigger('Do not cite sources.') == []
    assert summary_trigger('Summarize the Aster.')
    assert source_trigger('Cite the sources.')


def test_explicit_false_draft_flag_is_honored():
    from cpu_llm.agents.reply import _draft
    assert _draft(dict(message='Draft a letter about the Aster.', draft=False)) is None
