import copy
from types import SimpleNamespace
import pytest


def test_joined_sentence_reports_shortfall_in_rendered_reply():
    from cpu_llm.document_workflow import compose_document, plan_document
    plan = plan_document('Write an article about Helios Core in 8 words.')
    rows = [dict(document_id='a', chunk_text='Helios Core stores backups.'),
            dict(document_id='b', chunk_text='Helios Core uses PostgreSQL.')]
    result = apply_style(compose_document(plan, rows), 'formal')
    coverage = result['document']['coverage']
    assert coverage['body_word_count'] == 7
    assert coverage['word_shortfall'] == 1
    assert 'Requested length not reached: 7 source-backed body words' in result['reply']['text']
from cpu_llm.document_workflow import plan_document,compose_document
from cpu_llm.stylistic import apply_style,StyleOptions,Relationship
from cpu_llm.stylistic.profiles import extract_style_request
from cpu_llm.stylistic.document import claim_from,verify_sentence

def source_result(extra=()):
    texts=['Helios is a backup service.','Helios stores encrypted backups.',
        'Helios uses PostgreSQL for metadata.','Helios retains backups for 30 days.',
        'Helios runs backups every night.','Helios does not support automatic regional failover.',*extra]
    return compose_document(plan_document('Write a detailed article about Helios.'),
        [dict(document_id=f'manual-p{i:04}',chunk_text=t) for i,t in enumerate(texts)])

@pytest.mark.parametrize('prompt',[
    'Write a detailed article about Helios in a friendly tone.',
    'Write a detailed article about Helios. Use a friendly tone.',
    'In a friendly tone, write a detailed article about Helios.',
    'Write a detailed article about Helios in a friendly tone as an HTML report.',
])
def test_prompt_tone_is_control_not_a_kb_keyword(prompt):
    control=extract_style_request(prompt)
    assert control['tone']=='friendly'
    assert 'friendly' not in control['query']
    assert plan_document(control['query'])['topic']=='Helios'

@pytest.mark.parametrize('prompt',['What does "in a friendly tone" mean?',
    'Write about the friendly tone.', 'Write an article about Helios not in a friendly tone.'])
def test_quoted_data_and_negation_do_not_trigger_tone(prompt):
    assert extract_style_request(prompt)['tone'] is None

def test_document_generates_new_prose_not_present_in_source_and_keeps_proof():
    original=source_result();before=copy.deepcopy(original)
    result=apply_style(original,'friendly')
    assert original==before
    assert result['stylistic']['status']=='generated'
    assert result['stylistic']['executed_nodes']==['stylistic','style_verify']
    assert result['stylistic']['verification']['claim_count']==6
    assert 'Helios stores encrypted backups and uses PostgreSQL for metadata.' in result['reply']['text']
    assert "Helios doesn't support automatic regional failover." in result['reply']['text']
    assert 'It retains backups for 30 days and runs backups every night.' in result['reply']['text']
    assert result['answer_evidence']==before['answer_evidence']
    assert result['rendered_response']['canonical_text']==before['reply']['text']
    assert not result['audit_passed']

def test_unrecognized_conditional_statement_is_literal_not_dropped_or_simplified():
    result=apply_style(source_result(['Helios restores files only if an operator approves.']),'friendly')
    assert result['stylistic']['verification']['retained_literal_quotes']==1
    assert '> Helios restores files only if an operator approves.' in result['reply']['text']

@pytest.mark.parametrize('changed',[
    'Helios retains backups for 300 days.',
    'Helios does support automatic regional failover.',
    'Helios runs backups every night because it is reliable.',
])
def test_inverse_verifier_rejects_changed_number_negation_and_added_cause(changed):
    r=source_result();quote=next(q for q in r['answer_evidence'] if 'retains' in q['quote'])
    claim=claim_from(quote,'Helios')
    assert verify_sentence(changed,[claim],friendly=True)

def test_human_subject_never_gets_it_without_explicit_nonhuman_antecedent():
    r=source_result()
    for section in r['document']['sections']:
        section['quotes']=[q for q in section['quotes'] if 'backup service' not in q['quote']]
    r['answer_evidence']=[q for q in r['answer_evidence'] if 'backup service' not in q['quote']]
    result=apply_style(r,'friendly')
    assert 'It retains' not in result['reply']['text']

def test_no_claim_is_dropped_to_force_style_budget():
    r=source_result();s=apply_style(r,StyleOptions(tone='friendly',max_sentences=1))
    assert s['stylistic']['status']=='rejected'
    assert s['reply']['text']==r['reply']['text']

def test_lowercase_topic_keeps_original_source_entity_spelling():
    r=source_result();r['document']['plan']['topic']='helios'
    styled=apply_style(r,'friendly')
    assert styled['stylistic']['status']=='generated'
    assert 'Helios stores encrypted backups' in styled['reply']['text']

def test_proof_mutations_are_rejected():
    r=source_result();r['document']['sections'][0]['quotes'][0]['quote']='Helios is dangerous.'
    assert apply_style(r,'friendly')['stylistic']['status']=='rejected'

def test_relationship_restrictions_and_unsupported_expressive_tones_remain_visible():
    r=source_result()
    restricted=apply_style(r,StyleOptions(tone='intimate',relationship=Relationship.FAMILIAL))
    assert restricted['stylistic']['reason']=='relationship_tone_conflict'
    assert apply_style(r,'poetic')['stylistic']['tone_alignment']=='neutral_fallback'

def test_public_prompt_trigger_api_override_and_strict_precedence():
    from cpu_llm.pipeline import Appliance
    data=[dict(document_id=q['document_id'],chunk_text=q['quote']) for q in source_result()['answer_evidence']]
    app=SimpleNamespace(tenant_id='t',small_talk=False,strict_evidence=False,
        guard=SimpleNamespace(check=lambda m:SimpleNamespace(decision='allow')),
        index=SimpleNamespace(strict_source_rows=lambda *a,**k:(data,123)))
    prompt='Write a detailed article about Helios in a friendly tone.'
    r=Appliance.ask(app,prompt)
    assert r['stylistic']['status']=='generated' and r['tone_request']['effective_tone']=='friendly'
    formal=Appliance.ask(app,prompt,style='formal')
    assert formal['tone_request']['effective_tone']=='formal'
    strict=Appliance.ask(app,prompt,strict_evidence=True)
    assert 'stylistic' not in strict and strict['tone_request']['disabled_by_strict']
    assert strict['answer_evidence']==r['answer_evidence']
