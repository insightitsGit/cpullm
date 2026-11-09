from types import SimpleNamespace
import pytest
from cpu_llm.document_workflow import plan_document, compose_document, execute_document, _section


def rich_rows(count=80):
    return [dict(document_id=f'large-p{i:04}', chunk_text=
        f'Helios retains backup generation {i} in encrypted storage for scheduled restoration under the documented retention policy.')
        for i in range(1,count+1)]


def app(rows):
    return SimpleNamespace(tenant_id='t', guard=SimpleNamespace(check=lambda _:SimpleNamespace(decision='allow')),
                           index=SimpleNamespace(strict_source_rows=lambda *a,**k:(rows,123)))


def test_word_target_uses_enough_evidence_instead_of_twenty_chunks():
    r=compose_document(plan_document('Write a detailed article about Helios in 1000 words.'),rich_rows())
    c=r['document']['coverage']
    assert c['included_chunks']>20
    assert 1000<=c['body_word_count']<1020
    assert c['length_target_met']


def test_sixty_explicit_items_are_not_silently_capped_at_twenty():
    r=compose_document(plan_document('Write a report about Helios in 60 items.'),rich_rows())
    assert len(r['answer_evidence'])==60


def test_word_pagination_has_no_overlap_or_skipped_records():
    p=plan_document('Write an article about Helios in 200 words.')
    first=compose_document(p,rich_rows(),snapshot={'as_of':123})
    follow=plan_document(first['document']['coverage']['continuation_prompt'])
    assert follow['requested_limits']['words']==200 and follow['snapshot_as_of']==123
    second=compose_document(follow,rich_rows(),snapshot={'as_of':123})
    ids=[p['document_id'] for p in first['answer_evidence']+second['answer_evidence']]
    assert len(ids)==len(set(ids))
    assert set(ids)=={r['document_id'] for r in rich_rows(len(ids))}


def test_evidence_exhaustion_is_reported_without_padding():
    r=compose_document(plan_document('Write an article about Helios in 1000 words.'),rich_rows(3))
    c=r['document']['coverage']
    assert not c['length_target_met'] and c['length_stop_reason']=='evidence_exhausted'
    assert len(r['answer_evidence'])==3


def test_email_details_and_native_draft_not_report_or_unnecessary_pages():
    rows=[dict(document_id=f'a-p{i:04}',chunk_text=s) for i,s in enumerate([
        'Helios is a backup service.','Helios stores encrypted backups.',
        'Helios uses PostgreSQL for metadata.','Helios does not support regional failover.'])]
    m='Draft a concise email to Alex about Helios.'
    r=execute_document(app(rows),m,plan_document(m))
    text=r['reply']['text']
    assert 'Subject: Helios' in text and 'Hello Alex,' in text
    assert '\n## ' not in text and 'More evidence available' not in text
    assert 'Research evidence not found' not in text
    assert r['answer_status']=='evidence_quote'
    assert len(r['answer_evidence'])==4 and not r['document']['coverage']['has_more']
    assert _section(rows[1]['chunk_text'],'email')=='Details'


def test_budget_omission_is_not_mislabeled_missing_data():
    p=plan_document('Write an article about Helios in 1 item.')
    rows=[dict(document_id='a',chunk_text='Helios is a backup service.'),
          dict(document_id='b',chunk_text='Helios stores encrypted backups.')]
    r=compose_document(p,rows)
    c=r['document']['coverage']
    assert 'Details' in c['omitted_sections'] and 'Details' not in c['missing_sections']
    assert 'omitted' in r['reply']['text'].lower()


def test_ordinary_document_composes_long_verified_prose_without_tone_request():
    m='Write a detailed article about Helios in 1000 words.'
    r=execute_document(app(rich_rows()),m,plan_document(m))
    assert r['document_composition']['verification']['verified']
    assert r['document_composition']['verification']['claim_count']>20
    assert ' and retains backup generation ' in r['reply']['text']
    assert 'stylistic' not in r
    assert len(r['answer_evidence'])>20
    assert 'canonical_text' in r['rendered_response']


def test_explicit_style_budget_is_still_enforced_and_strict_never_rewrites():
    from cpu_llm.stylistic import apply_style,StyleOptions
    base=compose_document(plan_document('Write a detailed article about Helios.'),rich_rows())
    styled=apply_style(base,StyleOptions(tone='friendly',max_sentences=1))
    assert styled['stylistic']['status']=='rejected'
    m='Write an article about Helios in 1000 words.'
    r=execute_document(app(rich_rows()),m,plan_document(m),strict=True)
    assert 'document_composition' not in r and 'stylistic' not in r
    assert 'prose' not in r['document']['sections'][0]


def test_long_multi_subject_composition_retains_each_subject():
    rows=rich_rows(30)+[dict(document_id=f'postgres-p{i:04}',chunk_text=f'PostgreSQL records transaction batch {i}.') for i in range(30)]
    m='Write a detailed article about Helios and PostgreSQL.'
    r=execute_document(app(rows),m,plan_document(m))
    assert r['document_composition']['verification']['verified']
    assert 'PostgreSQL records' in r['reply']['text'] and 'Helios retains' in r['reply']['text']


def test_shortfall_and_operator_caps_are_not_reported_as_completed_targets():
    r=compose_document(plan_document('Write an article about Helios in 60 items.'),rich_rows(3))
    assert not r['document']['coverage']['length_target_met']
    assert not r['judgment']['complete']
    r=compose_document(plan_document('Write an article about Helios in 99999 words.'),rich_rows(3))
    assert r['document']['coverage']['requested_budget_clamped']
    assert not r['document']['coverage']['length_target_met']
    assert 'No padding was added' in r['reply']['text']


def test_email_continuation_preserves_recipient_and_word_budget():
    p=plan_document('Draft an email to Alex about Helios in 100 words.')
    first=compose_document(p,rich_rows(),snapshot={'as_of':123})
    follow=plan_document(first['document']['coverage']['continuation_prompt'])
    assert follow['recipient']=='Alex' and follow['requested_limits']['words']==100
    assert follow['snapshot_as_of']==123
    second=compose_document(follow,rich_rows(),snapshot={'as_of':123})
    assert not {p['document_id'] for p in first['answer_evidence']} & {p['document_id'] for p in second['answer_evidence']}


def test_explicit_items_are_not_merged_into_fewer_presented_units():
    m='Write a report about Helios in 60 items.'
    r=execute_document(app(rich_rows()),m,plan_document(m))
    assert sum(len(s.get('prose',[]))+len(s.get('literal_quotes',[])) for s in r['document']['sections'])==60


def test_nonhuman_identity_cannot_license_it_for_a_different_subject():
    from cpu_llm.stylistic import apply_style
    rows=[dict(document_id='a',chunk_text='Helios is a backup service.')]+[
        dict(document_id=f'j{i}',chunk_text=f'John stores item {i}.') for i in range(5)]
    # Pure composer retains its original lexical contract; supply the approved
    # research topic sets as the executor would.
    p=plan_document('Write an article about Helios and John.')
    p['research_topic_sets']=[['helios'],['john']]
    r=apply_style(compose_document(p,rows),'friendly')
    assert r['stylistic']['verification']['verified']
    assert 'It stores' not in r['reply']['text'] and 'John stores' in r['reply']['text']


def test_research_gaps_prevent_a_false_completed_document():
    m='Write an article about Helios, including Mechanism.'
    r=execute_document(app([dict(document_id='a',chunk_text='Helios is a backup service.')]),m,plan_document(m))
    assert not r['judgment']['complete']
    assert 'mechanism' in r['document']['coverage']['research_missing_facets']
    assert 'No explanation was invented' in r['reply']['text']


def test_requested_facets_select_and_reserve_matching_evidence():
    from cpu_llm.document_workflow import execute_document
    message = 'Write a report about Helios in 2 items, including Mechanism and Validation.'
    data = [
        dict(document_id='a', chunk_text='Helios is a process.'),
        dict(document_id='b', chunk_text='Helios stores records by encrypting each archive.'),
        dict(document_id='c', chunk_text='Helios verifies archive checksums.'),
    ]
    app = SimpleNamespace(tenant_id='t', guard=SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow')),
                          index=SimpleNamespace(strict_source_rows=lambda *a, **k: (data, 123)))
    result = execute_document(app, message, plan_document(message))
    questions = {q['facet']: q for q in result['research_plan']['questions']}
    assert questions['mechanism']['evidence_ids'] == ['b']
    assert questions['validation']['required'] and questions['validation']['evidence_ids'] == ['c']
    assert {proof['document_id'] for proof in result['answer_evidence']} == {'b', 'c'}


def test_bare_process_label_leaves_required_mechanism_missing():
    from cpu_llm.document_workflow import execute_document
    message = 'Write a report about Helios, including Mechanism.'
    data = [dict(document_id='a', chunk_text='Helios is a process.')]
    app = SimpleNamespace(tenant_id='t', guard=SimpleNamespace(check=lambda _: SimpleNamespace(decision='allow')),
                          index=SimpleNamespace(strict_source_rows=lambda *a, **k: (data, 123)))
    result = execute_document(app, message, plan_document(message))
    assert 'mechanism' in result['document']['coverage']['research_required_missing_facets']
    assert 'Mechanism' in result['document']['coverage']['missing_sections']
