import copy
import math
import pytest
from cpu_llm.stylistic import apply_style, StyleOptions, Tone, Relationship
from cpu_llm.stylistic.contracts import snapshot
from cpu_llm.stylistic.lexicon import Lexicon, Entry
from cpu_llm.stylistic.profiles import TONES
from cpu_llm.stylistic.verifier import verify_compound

def fact(relation,text,source):
    proof=[dict(document_id=source,span=text)]
    return dict(reply=dict(text=text,body=text),answer_status='answered',judgment=dict(
        outcome='answered',verification='structural',evidence=copy.deepcopy(proof),answer_decision=dict(
        outcome='answered',text=text,proof=proof,request=dict(entity='aster',relation=relation,
        direction='subject',polarity='affirmative',quantifier_scope='individual'))))

def batch():
    rows=[('has_color','The Aster is blue.'),('lives_in','The Aster is found in coastal waters.'),
          ('attribute:shape','The shape of the Aster is round.'),
          ('attribute:material','The material of the Aster is steel.'),
          ('attribute:weight','The weight of the Aster is 12.5 pounds.')]
    return dict(answer_status='answered',reply=dict(text='Canonical batch'),
        task_results=[dict(id=str(i),result=fact(r,t,f'doc-p{i:04d}')) for i,(r,t) in enumerate(rows)])

def test_long_related_response_preserves_all_five_claims_and_sources():
    original=batch();before=copy.deepcopy(original)
    result=apply_style(original,StyleOptions(tone='friendly',max_sentences=3))
    side=result['stylistic']
    assert side['status']=='generated'
    assert side['sentence_count']==3
    assert side['verification']['claim_count']==5
    assert len(side['proof'])==5 and len(side['claims'])==5
    assert side['text']==('The Aster is blue, and you can find the Aster in coastal waters. '
        'The Aster has a round shape, and the Aster is made of steel. The Aster weighs 12.5 pounds.')
    assert original==before and result['reply']==before['reply']

@pytest.mark.parametrize('change,reason',[
    (lambda r:r['task_results'].append(dict(id='pending',result=None)),'incomplete_or_unsupported_children'),
    (lambda r:r['task_results'][0]['result']['judgment']['answer_decision']['request'].update(entity='different'),'incomplete_or_unsupported_children'),
    (lambda r:r['task_results'].append(dict(id='conflict',result=fact('has_color','The Aster is red.','other'))),'conflicting_values'),
])
def test_no_partial_or_conflicting_summary(change,reason):
    result=batch();change(result)
    output=apply_style(result,'formal')['stylistic']
    assert output['status']=='children' and output['reason']==reason
    assert 'text' not in output

def test_budget_does_not_truncate_claims():
    result=apply_style(batch(),StyleOptions(max_sentences=1,clauses_per_sentence=2))
    assert result['stylistic']['reason']=='budget_cannot_preserve_all_claims'
    result=batch();result['response_plan']={'sentence_budget':1}
    assert apply_style(result,'formal')['stylistic']['status']=='skipped'

def test_different_subjects_are_not_joined():
    result=batch();row=result['task_results'][0]['result']
    row['judgment']['answer_decision']['request']['entity']='orion'
    row['judgment']['answer_decision']['text']='The Orion is blue.'
    row['judgment']['answer_decision']['proof'][0]['span']='The Orion is blue.'
    row['judgment']['evidence'][0]['span']='The Orion is blue.'
    assert apply_style(result,'formal')['stylistic']['reason']=='multiple_subjects'

@pytest.mark.parametrize('tone',TONES)
def test_every_tone_is_bounded_and_fallback_is_honest(tone):
    output=apply_style(batch(),StyleOptions(tone=tone,relationship=Relationship.ROMANTIC))['stylistic']
    assert output['verification']['verified']
    if tone not in {'friendly','formal','serious','analytical'}:
        assert output['tone_alignment']=='neutral_fallback'
    assert 'beautiful' not in output['text'] and 'passionately' not in output['text']

@pytest.mark.parametrize('relationship',[
    Relationship.FAMILIAL,Relationship.FAMILIAL|Relationship.ROMANTIC,
    Relationship.FORMAL|Relationship.ROMANTIC,Relationship.COLLEAGUE|Relationship.ROMANTIC,
])
def test_relationship_exclusions_override_permissions(relationship):
    side=apply_style(batch(),StyleOptions(tone='intimate',relationship=relationship))['stylistic']
    assert side['status']=='skipped' and side['reason']=='relationship_tone_conflict'

def test_candidate_filtering_happens_before_scoring():
    lex=Lexicon((Entry('risky','has_color',Tone.INTIMATE,risks=Tone.INTIMATE),
                 Entry('safe','has_color',Tone.FRIENDLY),Entry('wrong','lives_in',Tone.FRIENDLY)))
    ranked=lex.rank('has_color',StyleOptions(relationship=Relationship.FAMILIAL),required_pos=8|16)
    assert [row[1] for row in ranked]==['safe']
    assert not lex.intensity.flags.writeable

def test_soft_tone_mixture_and_mask_are_consistent():
    weights=(.5,0,.5,0,0,0,0,0,0,0)
    spec=StyleOptions(tone_weights=weights)
    assert spec.tone_bit==Tone.FRIENDLY|Tone.FORMAL
    assert Lexicon().rank('has_color',spec)==Lexicon().rank('has_color',spec)
    with pytest.raises(ValueError):StyleOptions(tone_weights=(0.,)*10)
    with pytest.raises(ValueError):StyleOptions(tone_weights=[.1]*10)

def test_shape_inflection_preserves_grammar():
    output=apply_style(fact('attribute:shape','The shape of the Aster is oval.','shape'),'friendly')
    assert output['stylistic']['text']=='The Aster has an oval shape.'

def test_weight_normalization_preserves_guarded_requests():
    from cpu_llm.prompt_ingestion import normalize_question,expand_explicit_fields
    assert normalize_question('How much does the Aster weigh?')['query']=='What is the weight of the Aster?'
    assert expand_explicit_fields('Tell me the weight of the Aster.')['queries']==['What is the weight of the Aster?']
    for text in ('How much does the Aster weigh if wet?','How much does the Aster weigh during winter?'):
        assert normalize_question(text)['query']==text

def test_machine_readable_spec_matches_runtime_registry():
    from dataclasses import fields
    from pathlib import Path
    import json
    from cpu_llm.stylistic.lexicon import ENTRIES
    spec=json.loads((Path(__file__).parents[1]/'docs/stylistic-generation-spec.json').read_text())
    assert spec['profiles']==list(TONES)
    assert spec['controls']==[f.name for f in fields(StyleOptions)]
    assert spec['relationship_flags']=={name:int(value) for name,value in Relationship.__members__.items()}
    assert {c['id'] for c in spec['constructions']}|set(spec['additional_constructions'])=={e.id for e in ENTRIES}
    assert set(spec['relations'])=={e.relation for e in ENTRIES}
    assert spec['construction_count']==len(ENTRIES)

@pytest.mark.parametrize('kwargs',[
    {'magnitude':math.nan},{'valence':2},{'arousal':math.inf},{'max_sentences':0},
    {'clauses_per_sentence':5},{'magnitude':True},{'relationship':128},
])
def test_invalid_controls_rejected(kwargs):
    with pytest.raises(ValueError):StyleOptions(**kwargs)

def test_compound_verifier_rejects_omission_addition_role_and_proof_changes():
    import cpu_llm.stylistic.node as module
    original=batch();frames=tuple(snapshot(t['result']) for t in original['task_results'])
    spec=StyleOptions(tone='friendly');candidate=module._generate(dict(frames=frames,spec=spec))['candidate']
    assert not verify_compound(frames,candidate,spec,3)
    for mutate in (
        lambda c:c['clauses'].pop(),
        lambda c:c.update(text=c['text']+' It is beautiful.'),
        lambda c:c['clauses'][0].update(text='The Orion is blue.'),
        lambda c:c.update(proof=()),
        lambda c:c.update(text=c['text'].replace(', and ','; therefore ',1)),
    ):
        changed=copy.deepcopy(candidate);mutate(changed)
        assert verify_compound(frames,changed,spec,3)
