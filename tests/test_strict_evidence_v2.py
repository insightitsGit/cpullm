"""Fictional evidence handling only, not clinical decision validation."""
import pytest
from test_strict_evidence import appliance


@pytest.mark.parametrize('text', ["DemoMed's strength is 0.75 mg.",
    'DemoMed has a strength of 0.75 mg.', 'The strength for DemoMed is 0.75 mg.'])
def test_recognized_paraphrases_keep_original_proofs(text):
    result = appliance(text).ask('What is the strength of DemoMed?', strict_evidence=True)
    assert result['answer_status'] == 'evidence_quote'
    assert result['answer_evidence'][0]['quote'] == text


@pytest.mark.parametrize('alternative,status', [('0.00075 g', 'evidence_quote'),
    ('750 mcg', 'evidence_quote'), ('0.75 mL', 'conflicting'), ('0.25 mg', 'conflicting'),
    ('not 0.75 mg', 'conflicting'), ('unknown', 'insufficient_evidence'),
    ('0.75 mg if condition Q applies', 'insufficient_evidence')])
def test_cross_form_conflicts_and_exact_units(alternative, status):
    result = appliance('The strength of DemoMed is 0.75 mg.', f"DemoMed's strength is {alternative}.").ask(
        'What is the strength of DemoMed?', strict_evidence=True)
    assert result['answer_status'] == status
    assert len(result['answer_evidence']) == 2


def test_batch_fields_single_snapshot_and_reference_binding():
    app = appliance('The strength of DemoMed is 0.75 mg.', 'The storage of DemoMed is cold.')
    result = app.ask('What is the strength of DemoMed? What is the storage of it?', strict_evidence=True)
    assert result['answer_status'] == 'evidence_quote'
    assert len(result['task_results']) == 2
    assert result['task_results'][1]['request']['reference_binding']['replacement'] == 'DemoMed'
    app.index.strict_source_rows.assert_called_once()
    result = app.ask('What are the strength and storage of DemoMed?', strict_evidence=True)
    assert len(result['answer_evidence']) == 2


def test_batch_missing_and_ambiguous_references_are_preserved():
    app = appliance('The strength of DemoMed is 1 mg.')
    result = app.ask('What is the strength of DemoMed? What is the storage of OtherMed? What is the strength of it?', strict_evidence=True)
    assert result['answer_status'] == 'partial'
    assert [t['status'] for t in result['task_results']] == ['evidence_quote', 'insufficient_evidence', 'unsupported']
    assert app.ask(' '.join(['What is the strength of DemoMed?'] * 9), strict_evidence=True)['answer_status'] == 'unsupported'


def test_explicit_universal_join_keeps_both_premises_and_conflicts():
    app = appliance('Lobster is a crustacean.', 'Every crustacean has a lifespan of 30 years.')
    result = app.ask('What is the lifespan of Lobster?', strict_evidence=True)
    assert result['answer_status'] == 'evidence_quote'
    assert len(result['answer_evidence']) == 2
    app = appliance('Lobster is a crustacean.', 'Every crustacean has a lifespan of 30 years.',
                    'The lifespan of Lobster is 20 years.')
    assert app.ask('What is the lifespan of Lobster?', strict_evidence=True)['answer_status'] == 'conflicting'
    app = appliance('Lobster is a crustacean.', 'The average lifespan of crustacean is 30 years.')
    assert app.ask('What is the lifespan of Lobster?', strict_evidence=True)['answer_status'] == 'insufficient_evidence'


def test_overview_retains_all_attributes_and_conflict_tasks():
    app = appliance('The strength of DemoMed is 1 mg.', 'The storage of DemoMed is cold.',
                    "DemoMed's strength is 2 mg.")
    result = app.ask('List documented attributes of DemoMed.', strict_evidence=True)
    assert result['answer_status'] == 'partial'
    assert len(result['answer_evidence']) == 3
    assert len(result['task_results']) == 2


@pytest.mark.parametrize('query,value', [('Calculate 0.1 + 0.2.', '0.3'),
    ('Calculate 9000001 * 0.5.', '4500000.5'), ('Calculate 4 - 7.', '-3')])
def test_exact_arithmetic_without_source_scan(query, value):
    app = appliance()
    result = app.ask(query, strict_evidence=True)
    assert result['answer_status'] == 'derived_calculation'
    assert result['calculation']['value'] == value
    assert result['answer'] is None
    app.index.strict_source_rows.assert_not_called()


def test_source_arithmetic_never_chooses_a_conflicting_value():
    app = appliance('The strength of DemoMed is 0.75 mg.')
    result = app.ask('Calculate the strength of DemoMed times 3.', strict_evidence=True)
    assert result['calculation']['display'] == '2.25 mg'
    assert len(result['answer_evidence']) == 1
    app = appliance('The strength of DemoMed is 0.75 mg.', "DemoMed's strength is 0.25 mg.")
    result = app.ask('Calculate the strength of DemoMed times 3.', strict_evidence=True)
    assert result['answer_status'] == 'conflicting'
    assert 'calculation' not in result


@pytest.mark.parametrize('query', ['Which antibiotic should Case Birch receive?',
    'Can I take DemoMed?', 'Calculate the strength of DemoMed times 3 if pregnant.',
    'What is the strength of DemoMed or OtherMed?'])
def test_medical_advice_and_context_conditions_abstain(query):
    assert appliance('The strength of DemoMed is 1 mg.').ask(query, strict_evidence=True)['answer_status'] == 'unsupported'
