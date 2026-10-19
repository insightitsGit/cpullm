"""A document order follows the output catalog and stays inside retrieved sentences."""

import json

from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta

from cpu_llm.agents.reply import compose_reply
from cpu_llm.formats import (
    MISSING,
    OUTPUT_FORMATS,
    bind_formats,
    catalog_text,
    draft_trigger,
    output_format_ids,
    output_formats_from,
    parse_order,
    remember_output_formats,
    render_draft,
)

_SHIPMENT = "The late shipment left the dock on Monday."
_UNRELATED = "Business class is allowed for flights over six hours."
_RECIPIENT = "The letter is addressed to Dana Chen."
_ROWS = [
    {"chunk_id": "c0", "chunk_text": f"{_RECIPIENT} {_SHIPMENT}"},
    {"chunk_id": "c1", "chunk_text": _UNRELATED},
]


def test_the_catalog_lists_every_output_format():
    assert output_format_ids() == (
        "email",
        "letter",
        "memo",
        "document",
        "report",
        "agenda",
        "minutes",
        "notice",
        "checklist",
        "faq",
        "outline",
        "status",
        "proposal",
        "briefing",
        "essay",
        "article",
        "blog",
        "press",
        "abstract",
        "paper",
        "case",
        "newsletter",
        "speech",
        "biography",
        "review",
        "tutorial",
        "procedure",
        "decision",
        "incident",
        "invitation",
        "post",
    )
    aliases = [alias.casefold() for item in OUTPUT_FORMATS for alias in item.aliases]
    assert len(aliases) == len(set(aliases))
    listed = catalog_text()
    for format_id in output_format_ids():
        assert f"- {format_id}:" in listed


def test_each_format_follows_its_fields_and_keeps_only_the_topic():
    expected = {
        "email": ["Email", "To:", "From:", "Date:", "Subject: the late shipment", _SHIPMENT],
        "letter": ["Letter", "Date:", "To: Dana Chen", "Subject: the late shipment"],
        "memo": ["Memo", "To: Dana Chen", "Subject: the late shipment"],
        "document": ["Document", "Title: the late shipment", f"1. {_SHIPMENT}"],
        "report": ["Report", "Findings:", f"- {_SHIPMENT}", "Sources:", "- c0"],
        "agenda": ["Agenda", "Title: the late shipment", f"1. {_SHIPMENT}"],
        "minutes": ["Minutes", "Attendees:", "Recorded:", f"- {_SHIPMENT}"],
        "notice": ["Notice", _SHIPMENT],
        "checklist": ["Checklist", f"- [ ] {_SHIPMENT}"],
        "faq": ["FAQ", "Q: the late shipment", f"A: {_SHIPMENT}"],
        "outline": ["Outline", f"1. {_SHIPMENT}"],
        "status": ["Status update", "Subject: the late shipment", f"- {_SHIPMENT}"],
        "proposal": ["Proposal", "To: Dana Chen", f"- {_SHIPMENT}"],
        "briefing": ["Briefing", "Subject: the late shipment", f"- {_SHIPMENT}"],
        "essay": ["Essay", "Title: the late shipment", _SHIPMENT, "Sources:", "- c0"],
        "article": ["Article", "Title: the late shipment", "By:", _SHIPMENT, "Sources:", "- c0"],
        "blog": ["Blog post", "Title: the late shipment", _SHIPMENT],
        "press": ["Press release", "Title: the late shipment", "Date:", _SHIPMENT],
        "abstract": ["Abstract", "Title: the late shipment", _SHIPMENT],
        "paper": ["Paper", "Findings:", f"- {_SHIPMENT}", "Sources:", "- c0"],
        "case": ["Case study", "Findings:", f"- {_SHIPMENT}", "Sources:", "- c0"],
        "newsletter": ["Newsletter", "Title: the late shipment", _SHIPMENT],
        "speech": ["Speech", "Title: the late shipment", _SHIPMENT],
        "biography": ["Biography", "Title: the late shipment", _SHIPMENT],
        "review": ["Review", "Title: the late shipment", _SHIPMENT],
        "tutorial": ["Tutorial", "Title: the late shipment", f"1. {_SHIPMENT}"],
        "procedure": ["Procedure", "Title: the late shipment", f"1. {_SHIPMENT}"],
        "decision": ["Decision record", f"- {_SHIPMENT}", "Sources:", "- c0"],
        "incident": ["Incident report", "Title: the late shipment", "Findings:", f"- {_SHIPMENT}"],
        "invitation": ["Invitation", "To: Dana Chen", "Subject: the late shipment", _SHIPMENT],
        "post": ["Post", "Title: the late shipment", f"- {_SHIPMENT}"],
    }
    prompts = {
        "email": "Write an email about the late shipment.",
        "letter": "Draft a letter about the late shipment.",
        "memo": "Prepare a memo about the late shipment.",
        "document": "Create a document about the late shipment.",
        "report": "Write a report on the late shipment.",
        "agenda": "Write a meeting agenda for the late shipment.",
        "minutes": "Write meeting minutes for the late shipment.",
        "notice": "Write a notice about the late shipment.",
        "checklist": "Make a checklist of the late shipment.",
        "faq": "Write an faq about the late shipment.",
        "outline": "Write an outline of the late shipment.",
        "status": "Write a status update about the late shipment.",
        "proposal": "Write a proposal for the late shipment.",
        "briefing": "Write a briefing about the late shipment.",
        "essay": "Create a essay about the late shipment.",
        "article": "Create an article about the late shipment.",
        "blog": "Write a blog post about the late shipment.",
        "press": "Write a press release about the late shipment.",
        "abstract": "Write an abstract about the late shipment.",
        "paper": "Write a white paper on the late shipment.",
        "case": "Write a case study of the late shipment.",
        "newsletter": "Write a newsletter about the late shipment.",
        "speech": "Write a speech about the late shipment.",
        "biography": "Write a biography of the late shipment.",
        "review": "Write a review of the late shipment.",
        "tutorial": "Write a how to about the late shipment.",
        "procedure": "Write a procedure for the late shipment.",
        "decision": "Write a decision record for the late shipment.",
        "incident": "Write an incident report about the late shipment.",
        "invitation": "Write an invitation for the late shipment.",
        "post": "Write a post about the late shipment.",
    }
    assert set(prompts) == set(output_format_ids())
    for format_id, prompt in prompts.items():
        draft = render_draft(prompt, _ROWS)
        assert draft is not None
        assert draft["format"] == format_id
        assert draft["topic"] == "the late shipment"
        assert draft["sources"] == ["c0"]
        for line in expected[format_id]:
            assert line in draft["text"]
        assert _UNRELATED not in draft["text"]
        assert _RECIPIENT not in draft["text"]


def test_a_named_recipient_is_filled_and_a_second_one_is_not_chosen():
    one = render_draft("Write an email about the late shipment.", _ROWS)
    assert one is not None
    assert "To: Dana Chen" in one["text"]
    assert "From: Not stated in the retrieved passages." in one["text"]
    assert "sender, date" in one["text"]
    assert one["missing"] == ["from", "date"]

    contested = render_draft(
        "Write an email about the late shipment.",
        [
            {"chunk_id": "c0", "chunk_text": f"{_RECIPIENT} {_SHIPMENT}"},
            {"chunk_id": "c1", "chunk_text": "The notice is addressed to the finance team."},
        ],
    )
    assert contested is not None
    assert "To: The retrieved passages name more than one recipient." in contested["text"]
    assert "To: Dana Chen" not in contested["text"]
    assert "To: the finance team" not in contested["text"]


def test_a_missing_topic_or_format_asks_and_lists_the_catalog():
    email = render_draft("Write an email.", [{"chunk_id": "c0", "chunk_text": _SHIPMENT}])
    assert email is not None
    assert email["format"] == "email"
    assert email["topic"] == ""
    assert "does not name a topic" in email["text"]
    assert _SHIPMENT not in email["text"]
    for format_id in output_format_ids():
        assert f"- {format_id}:" in email["text"]

    bare = render_draft("Write about the late shipment.", _ROWS)
    assert bare is not None
    assert bare["format"] is None
    assert bare["topic"] == "the late shipment"
    assert "does not name an output format" in bare["text"]
    assert _SHIPMENT not in bare["text"]

    empty = render_draft("Write something.", [])
    assert empty is not None
    assert empty["format"] is None
    assert empty["topic"] == ""
    assert "Name one format and a topic." in empty["text"]


def test_an_ordinary_question_or_a_poem_is_not_a_document_order():
    assert parse_order("What is the European lobster?") is None
    assert parse_order("Write a poem about the claws.") is None
    assert parse_order("Write a story about the lobster.") is None
    assert parse_order("Can I fly business class to Tokyo?") is None
    assert parse_order("Write an incident report about the late shipment.").format_id == "incident"
    assert parse_order("Write a research paper about the late shipment.").format_id == "paper"
    assert draft_trigger("Write an email about the late shipment.") == ["the prompt asks for an email"]
    assert "the prompt does not name a topic" in draft_trigger("Write an email.")
    assert draft_trigger("Write a poem about the claws.") == []


def test_the_reply_speaks_the_format_instead_of_an_unrelated_passage():
    reply = compose_reply(
        {
            "message": "Write an email about the late shipment.",
            "guard_decision": "allow",
            "related": _ROWS,
        }
    )
    assert reply["text"].startswith("Email\nTo: Dana Chen")
    assert _SHIPMENT in reply["text"]
    assert _UNRELATED not in reply["text"]
    assert "From c1" not in reply["text"]
    assert reply["situation"] is None
    assert reply["draft"]["format"] == "email"

    plain = compose_reply(
        {
            "message": "What is the European lobster?",
            "guard_decision": "allow",
            "related": [{"chunk_id": "c0", "chunk_text": "Homarus gammarus is the European lobster."}],
        }
    )
    assert plain["draft"] is None
    assert plain["text"].startswith("From c0:")

    blocked = compose_reply(
        {
            "message": "Write an email about the late shipment.",
            "guard_decision": "block",
            "answer": "The prompt was blocked by PrismGuard.",
            "related": _ROWS,
        }
    )
    assert blocked["draft"] is None
    assert blocked["text"] == "The prompt was blocked by PrismGuard."
    assert MISSING not in blocked["text"]


def test_formats_are_stored_in_prismcortex_without_embeddings(tmp_path):
    path = tmp_path / "graph.db"
    store = SqliteGraphStore(path, tenant_id="cpu-llm")
    chunk = Node(
        id="chunk1",
        label=_SHIPMENT,
        kind="chunk",
        embedding=[1.0, 0.0],
        attributes={},
    )
    store.apply(StateDelta(ops=[DeltaOp(operation=Operation.ASSIMILATE, node=chunk, reason="chunk")]))
    try:
        assert remember_output_formats(store) == len(OUTPUT_FORMATS)
        assert remember_output_formats(store) == 0
        formats = [node for node in store.all_nodes() if node.kind == "output_format"]
        assert len(formats) == len(OUTPUT_FORMATS)
        for node in formats:
            assert node.embedding is None
            assert len(json.dumps(node.attributes)) < 320
        loaded = output_formats_from(store)
        assert [item.id for item in loaded] == list(output_format_ids())
        found = store.retrieve([1.0, 0.0], k=5)
        assert [node.id for node in found.nodes] == ["chunk1"]
    finally:
        store.close()

    reopened = SqliteGraphStore(path, tenant_id="cpu-llm")
    try:
        bind_formats(output_formats_from(reopened))
        essay = render_draft("Create an essay about the late shipment.", _ROWS)
        article = render_draft("Create an article about the late shipment.", _ROWS)
        assert essay is not None and essay["format"] == "essay"
        assert article is not None and article["format"] == "article"
        assert _SHIPMENT in essay["text"]
        assert _UNRELATED not in article["text"]
    finally:
        bind_formats(None)
        reopened.close()
