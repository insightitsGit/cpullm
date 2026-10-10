"""PrismRAG labels a chunk with the article slug already in its document id."""

from cpu_llm.catalog import article_slug, label_retrieval


def test_article_slug_drops_the_source_prefix_and_paragraph_number():
    assert article_slug("wikitext2-homarus-gammarus-p0001") == "homarus-gammarus"
    assert article_slug("doc_hyper") == "doc_hyper"


def test_query_category_follows_an_article_token():
    related = [
        {
            "chunk_id": "wikitext2-homarus-gammarus-p0001",
            "chunk_text": "Homarus gammarus, known as the European lobster.",
            "score": 0.86,
        }
    ]
    labeled = label_retrieval("Where does homarus live?", related)
    assert labeled["query_category"] == "homarus-gammarus"
    assert labeled["related"][0]["category"] == "homarus-gammarus"
    assert labeled["rag_retrieval_mode"] != "empty"

    unlabeled = label_retrieval("What is the European lobster?", related)
    assert unlabeled["query_category"] is None
    assert unlabeled["related"][0]["category"] == "homarus-gammarus"
