import copy
import hashlib
from types import SimpleNamespace
import pytest
from cpu_llm.document_workflow import plan_document, plan_long_overview, compose_document, execute_document
from cpu_llm.response_policy import classify_response_request
from cpu_llm.access import CallerContext

FACTS = ['Helios is a backup service.', 'Helios uses PostgreSQL for metadata.',
         'Helios stores backup files in object storage.', 'Helios retains backups for 30 days.',
         'Helios requires operator approval before deletion.',
         'Helios does not support automatic regional failover.',
         'Helios verifies backup checksums.', 'The Aster is blue.']

def rows():
    return [dict(document_id=f'manual-p{i:04}',chunk_text=t) for i,t in enumerate(FACTS,1)]

@pytest.mark.parametrize('genre',['report','article','design document'])
def test_document_genres_share_depth_coverage_and_provenance(genre):
    plan=plan_document(f'Write a detailed {genre} about Helios.')
    result=compose_document(plan,rows())
    assert len(result['answer_evidence'])==7
    for proof in result['answer_evidence']:
        assert proof['quote'] in FACTS
        assert proof['chunk_sha256']==hashlib.sha256(proof['quote'].encode()).hexdigest()
    assert 'The Aster' not in result['reply']['text']
    assert 'does not support' in result['reply']['text']
    assert '30 days' in result['reply']['text']
    response=classify_response_request(f'Write a detailed {genre} about Helios.')
    assert response['mode']=='document' and response['flags']['expand_retrieval']
    assert not result['audit_passed'] and result['answer'] is None

def test_design_missing_sections_are_explicit_and_not_invented():
    result=compose_document(plan_document('Write a detailed design document about Helios.'),rows())
    coverage=result['document']['coverage']
    assert coverage['missing_sections']==['Interfaces']
    assert result['answer_status']=='partial'
    assert 'Not stated' in result['reply']['text']

def test_long_explanation_uses_technical_quotes_not_lossy_proposition_subset():
    plan=plan_long_overview('Explain Helios in twelve sentences as bullet points.')
    assert plan['unit_budget']==12
    result=compose_document(plan,rows())
    assert len(result['answer_evidence'])==7
    assert any('PostgreSQL' in p['quote'] for p in result['answer_evidence'])

def test_long_overview_caps_requests_and_keeps_continuation_genre_and_outline():
    plan=plan_long_overview('Explain Helios in 1000 sentences as bullet points.')
    assert plan['unit_budget']==20
    plan['unit_budget']=2
    r=compose_document(plan,rows(),snapshot={'as_of':123})
    follow=plan_document(r['document']['coverage']['continuation_prompt'])
    assert follow['genre']==plan['genre'] and follow['sections']==plan['sections']
    assert follow['unit_budget']==2 and follow['format']=='bullets'

@pytest.mark.parametrize('layout',['a Markdown report','an HTML report','a Markdown table','an HTML table','bullet points','a numbered list'])
def test_renderers_preserve_one_evidence_set_and_escape_source_markup(layout):
    data=rows()+[dict(document_id='manual-p0099',chunk_text='Helios accepts <script>alert(1)</script> as an example.')]
    plan=plan_document('Write a detailed report about Helios as '+layout+'.')
    r=compose_document(plan,data)
    assert len(r['answer_evidence'])==8
    assert '<script>' not in r['reply']['text']
    assert any('<script>' in p['quote'] for p in r['answer_evidence'])

def test_continuation_retains_size_time_and_has_no_overlap():
    first=compose_document(plan_document('Write a report about Helios in 3 items.'),rows(),snapshot={'as_of':1234})
    follow=first['document']['coverage']['continuation_prompt']
    plan=plan_document(follow)
    assert plan['unit_budget']==3 and plan['page']==2 and plan['snapshot_as_of']==1234
    second=compose_document(plan,rows())
    assert not {p['document_id'] for p in first['answer_evidence']} & {p['document_id'] for p in second['answer_evidence']}

def test_recognized_conflict_preserves_both_sources_and_marks_partial():
    data=[dict(document_id='a-p1',chunk_text='The color of Helios is blue.'),dict(document_id='b-p1',chunk_text='The color of Helios is red.')]
    r=compose_document(plan_document('Write a report about Helios.'),data)
    assert r['document']['coverage']['conflicts']
    assert len(r['answer_evidence'])==2 and r['answer_status']=='partial'

def test_budget_never_truncates_atomic_qualifier_or_claims_exact_word_limit():
    plan=plan_document('Write an article about Helios in 2 words.')
    r=compose_document(plan,rows())
    assert r['document']['coverage']['requested_budget_exceeded']
    assert not r['document']['coverage']['word_limit_enforced']
    assert r['answer_evidence'][0]['quote'] in FACTS

def test_explicit_outline_is_respected_without_manufacturing_decisions():
    plan=plan_document('Write a detailed design document about Helios, including Architecture, Interfaces and Costs.')
    assert plan['sections']==['Overview','Architecture','Interfaces','Costs']
    result=compose_document(plan,rows())
    assert 'Interfaces' in result['document']['coverage']['missing_sections']
    assert 'Costs' in result['document']['coverage']['missing_sections']

@pytest.mark.parametrize('prompt',[
    'Use deep search to write a detailed report about Helios.',
    'Write a detailed report about the topic of Helios with citations. Use deep search.',
])
def test_explicit_search_and_citation_controls_do_not_pollute_topic(prompt):
    plan=plan_document(prompt)
    assert plan['topic']=='Helios' and plan['deep_requested']

def test_atomic_output_cap_fails_instead_of_truncating_a_record():
    plan=plan_document('Write a report about Helios.')
    with pytest.raises(ValueError,match='output'):
        compose_document(plan,[dict(document_id='a-p1',chunk_text='Helios '+('x'*200001))])

def test_public_api_document_strict_and_tone_boundaries(monkeypatch):
    from cpu_llm.pipeline import Appliance
    import cpu_llm.stylistic as style
    app=SimpleNamespace(tenant_id='t',small_talk=False,strict_evidence=True,
        guard=SimpleNamespace(check=lambda m:SimpleNamespace(decision='allow')),
        index=SimpleNamespace(strict_source_rows=lambda *a,**k:(rows(),123)))
    monkeypatch.setattr(style,'apply_style',lambda *a:pytest.fail('strict document styled'))
    r=Appliance.ask(app,'Write a detailed report about Helios.',style='friendly')
    assert r['evidence_policy']['enabled'] and len(r['answer_evidence'])==7
    assert 'stylistic' not in r
    app.strict_evidence=False
    with pytest.raises(ValueError,match='realization'):
        Appliance.ask(app,'Write a report about Helios.',realization='invalid')

def test_scoped_snapshot_uses_caller_and_historical_time():
    captured=[]
    def scan(allowed,as_of):
        captured.append((allowed,as_of));return rows(),999
    app=SimpleNamespace(tenant_id='t',guard=SimpleNamespace(check=lambda m:SimpleNamespace(decision='allow')),
                        index=SimpleNamespace(strict_source_rows=scan))
    r=execute_document(app,'Write a report about Helios.',plan_document('Write a report about Helios.'),
        caller=CallerContext.make('t','u',['manual-p']),as_of=321,strict=True)
    assert captured==[(frozenset({'manual-p'}),321)]
    assert r['evidence_policy']['enabled'] and not r['evidence_policy']['learned_generation']

def test_guard_scan_failure_empty_and_scope_violation_fail_closed():
    app=SimpleNamespace(tenant_id='t',guard=SimpleNamespace(check=lambda m:SimpleNamespace(decision='block')),
        index=SimpleNamespace(strict_source_rows=lambda *a,**k:pytest.fail('blocked scan')))
    plan=plan_document('Write a report about Helios.')
    assert execute_document(app,'bad',plan)['answer_status']=='blocked'
    app.guard.check=lambda m:SimpleNamespace(decision='allow')
    app.index.strict_source_rows=lambda *a,**k:([],123)
    assert execute_document(app,'ok',plan)['answer_status']=='insufficient_evidence'
    def overflow(*a,**k):raise ValueError('limit')
    app.index.strict_source_rows=overflow
    assert execute_document(app,'ok',plan)['answer_evidence']==[]
    app.index.strict_source_rows=lambda *a,**k:(rows(),123)
    with pytest.raises(RuntimeError,match='scope violation'):
        execute_document(app,'ok',plan,caller=CallerContext.make('t','u',['other-p']))

@pytest.mark.parametrize('message',['What is a report?', 'Do not write a report about Helios.', 'What color is the Aster as a report?', 'Tell me the color and habitat of the Aster as a report.'])
def test_factual_negated_and_subject_words_are_not_document_commands(message):
    assert plan_document(message) is None
