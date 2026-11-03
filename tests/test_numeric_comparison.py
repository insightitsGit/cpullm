import pytest
from cpu_llm.numeric_comparison import compare_prompt
from cpu_llm.agents.math import solve_math
from cpu_llm.classifier import math_trigger
from test_strict_evidence import appliance

INLINE = 'A fictional label states a maximum daily amount of 3000 mg. Does a supplied total of 3375 mg exceed that label limit?'


@pytest.mark.parametrize('query,value', [(INLINE, 'true'), ('Does 0.625 mg exceed 0.625 mg?', 'false'),
    ('Does 0.624999 mg exceed 0.625 mg?', 'false'), ('Does 0.625001 mg exceed 0.625 mg?', 'true')])
def test_exact_direction_and_boundary(query, value):
    assert compare_prompt(query)['value'] == value
    assert solve_math(query)['value'] == value
    assert math_trigger(query)
    app = appliance()
    result = app.ask(query, strict_evidence=True)
    assert result['calculation']['value'] == value
    assert result['answer_status'] == 'derived_calculation'
    assert result['calculation']['clinical_validation'] is False
    app.index.strict_source_rows.assert_not_called()


@pytest.mark.parametrize('query', ['Does 1 g exceed 2 mg?', 'Does 1 Mg exceed 2 mg?',
    'Does 1 mg exceed 2 mg if pregnant?', 'Can I take 3000 mg?', 'The strength is 1 mg.'])
def test_no_guessing_units_conditions_or_treatment(query):
    assert compare_prompt(query) is None
