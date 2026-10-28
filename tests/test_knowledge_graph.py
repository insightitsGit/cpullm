from types import SimpleNamespace

from cpu_llm.knowledge_graph import KnowledgeGraph, extract_facts
from cpu_llm.pipeline import _with_graph_paragraphs


def test_typed_edges_keep_direction_and_exact_source_sentences():
    text = 'The coastal moth is a species of insect from Norway. The coastal moth is blue. The coastal moth has wings.'
    facts = extract_facts('moth', text)
    assert {(f.relation, f.object) for f in facts} == {
        ('is_a', 'insect'), ('lives_in', 'Norway'), ('has_color', 'blue'), ('has', 'wings')}
    assert all(f.subject == 'The coastal moth' and f.sentence in text for f in facts)
    assert extract_facts('bad', 'The moth is not blue. If the moth is an insect. It has wings.') == []
    copper = extract_facts('kestrel', 'The Kestrel is copper.')
    assert [(fact.relation, fact.object) for fact in copper] == [('has_color', 'copper')]
    assert extract_facts('ready', 'The Kestrel is ready.') == []
    assert extract_facts('place', 'The Reed is found in Rim.')[0].relation == 'lives_in'
    named = extract_facts('mauve', 'The color of the Kestrel is mauve.')
    assert [(fact.relation, fact.object.casefold()) for fact in named] == [('has_color', 'mauve')]
    kind = extract_facts('instrument', 'The Kestrel is a copper instrument.')
    assert [(fact.relation, fact.object) for fact in kind] == [('is_a', 'copper instrument')]


def test_alias_connects_named_entity_to_facts_in_another_paragraph(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace([
        ('a', 'Caligo marina, known as the coastal moth, is a species of insect.'),
        ('b', 'Caligo marina lives in Norway.'),
        ('noise', 'The red fox lives in Canada.'),
    ])
    facts = graph.neighborhood('Where does the coastal moth live?')
    assert {f.document_id for f in facts} == {'a', 'b'}
    assert any(f.relation == 'alias_of' for f in facts)
    assert any(f.relation == 'lives_in' for f in facts)
    assert len(graph.neighborhood('coastal moth', limit=1)) == 1
    assert graph.neighborhood('coastal moth', hops=0) == []


def test_forbidden_edge_cannot_bridge_into_authorized_source(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    graph.replace([('secret', 'Caligo marina, known as the coastal moth, is a species of insect.'),
                   ('public', 'Caligo marina lives in Norway.')])
    assert graph.neighborhood('coastal moth', allowed={'public'}) == []
    assert graph.neighborhood('Caligo marina', allowed=set()) == []


def test_replace_delete_and_reopen_do_not_leave_stale_facts(tmp_path):
    path = tmp_path / 'facts.db'
    graph = KnowledgeGraph(path)
    graph.replace([('guide-p1', 'The moth is blue.'), ('guide-p2', 'The moth has wings.')])
    graph.replace([('guide-p1', 'The moth is red.')], prefix='guide-')
    facts = KnowledgeGraph(path).neighborhood('moth')
    assert len(facts) == 1 and facts[0].object == 'red'
    graph.replace([('guide-p1', 'No affirmative fact here.')])
    assert graph.neighborhood('moth') == []
    graph.replace([('guide-p1', 'The moth is red.')])
    graph.delete_prefix('guide-')
    assert graph.neighborhood('moth') == []


def test_normal_retrieval_can_add_graph_evidence_without_dense_hits(tmp_path):
    graph = KnowledgeGraph(tmp_path / 'facts.db')
    text = 'The coastal moth lives in Norway.'
    graph.replace([('guide', text)])
    requested = []
    def fetch(ids):
        requested.extend(ids)
        return [{'document_id': 'guide', 'chunk_text': text}]
    appliance = SimpleNamespace(knowledge_graph=graph, index=SimpleNamespace(db=SimpleNamespace(get_by_ids=fetch)))
    rows = _with_graph_paragraphs(appliance, 'coastal moth', [], allowed={'guide'})
    assert requested == ['guide']
    assert rows[0]['graph_evidence'][0]['relation'] == 'lives_in'
    assert _with_graph_paragraphs(appliance, 'coastal moth', [], allowed=set()) == []
    assert _with_graph_paragraphs(appliance, 'coastal moth', [], as_of=123) == []
    # Stale evidence is not returned if the source row no longer contains it.
    appliance.index.db.get_by_ids = lambda ids: [{'document_id': 'guide', 'chunk_text': 'Unrelated replacement.'}]
    assert _with_graph_paragraphs(appliance, 'coastal moth', []) == []
