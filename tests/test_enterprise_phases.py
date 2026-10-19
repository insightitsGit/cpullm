"""Corrections, retrieval measurement, entity spans, and per-seat turns."""

import threading

from prismcortex.adapters.reference import InMemoryGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta

from cpu_llm.agents.reply import compose_reply
from cpu_llm.corrections import apply_correction, conflict_among
from cpu_llm.memory.entities import bind_entities
from cpu_llm.memory.frames import frame_from_chunk, resolve_frames, stated_role
from cpu_llm.retrieval_eval import measure
from cpu_llm.scale import EngineManager, FABRIC_WIDTH

PRIOR = "The harbor kestrel is a small coastal falcon."
REVISED = "The harbor kestrel is a small coastal bird."
APPLE = "John ate a yellow apple in his house."


class _Index:
    def __init__(self) -> None:
        self.retired: list[tuple[str, int]] = []
        self.saved: list[tuple[str, str]] = []

    def retire_document(self, document_id: str, timestamp: int) -> None:
        self.retired.append((document_id, int(timestamp)))

    def save_chunks(self, pairs: list[tuple[str, str]]) -> int:
        self.saved.extend(pairs)
        return len(pairs)


def _store(document_id: str, sentence: str) -> InMemoryGraphStore:
    memory = InMemoryGraphStore()
    memory.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id=document_id, kind="chunk", label=sentence, embedding=None),
                )
            ]
        )
    )
    return memory


def test_a_correction_keeps_the_old_node_and_closes_the_vector_row():
    memory = _store("notes-p0001", PRIOR)
    index = _Index()
    result = apply_correction(
        memory,
        index,
        document_id="notes-p0001",
        prior_sentence=PRIOR,
        new_sentence=REVISED,
        actor_id="editor-1",
        timestamp=1_700_000_000,
    )
    assert result["prior_kept"] is True
    assert memory._nodes["notes-p0001"].label == PRIOR
    new = memory._nodes[result["new_id"]]
    assert new.label == REVISED
    assert new.attributes["base_id"] == "notes-p0001"
    edge = memory._edges[f"{result['new_id']}-supersedes"]
    assert edge.relation == "SUPERSEDES"
    assert edge.dst == "notes-p0001"
    assert edge.valid_to is None
    assert index.retired == [("notes-p0001", 1_700_000_000)]
    assert index.saved[0][0] == result["new_id"]


def test_a_sentence_that_does_not_round_trip_is_refused():
    memory = _store("notes-p0001", PRIOR)
    try:
        apply_correction(
            memory,
            _Index(),
            document_id="notes-p0001",
            prior_sentence=PRIOR,
            new_sentence="Purple wallpaper samples",
            actor_id="editor-1",
            timestamp=1_700_000_001,
        )
    except ValueError as exc:
        assert "round-trip" in str(exc)
    else:
        raise AssertionError("expected the new sentence to be refused")
    assert list(memory._nodes) == ["notes-p0001"]


def test_a_second_correction_closes_the_previous_edge():
    memory = _store("notes-p0001", PRIOR)
    index = _Index()
    first = apply_correction(
        memory,
        index,
        document_id="notes-p0001",
        prior_sentence=PRIOR,
        new_sentence=REVISED,
        actor_id="editor-1",
        timestamp=1_700_000_000,
    )
    second = apply_correction(
        memory,
        index,
        document_id="notes-p0001",
        prior_sentence=REVISED,
        new_sentence="The harbor kestrel is a small coastal hawk.",
        actor_id="editor-1",
        timestamp=1_700_000_100,
    )
    closed = memory._edges[f"{first['new_id']}-supersedes"]
    assert closed.valid_to is not None
    assert memory._edges[f"{second['new_id']}-supersedes"].dst == first["new_id"]
    assert memory._nodes["notes-p0001"].label == PRIOR
    assert conflict_among(memory, [{"document_id": "notes-p0001"}]) is None


def test_two_live_wordings_stay_contested():
    memory = _store("notes-p0001", PRIOR)
    memory.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(
                        id="notes-p0001-other",
                        kind="chunk",
                        label=REVISED,
                        embedding=None,
                        attributes={"base_id": "notes-p0001"},
                    ),
                )
            ]
        )
    )
    found = conflict_among(memory, [{"document_id": "notes-p0001"}])
    assert found is not None
    assert found["verdict"] == "CONTESTED"
    assert PRIOR in found["text"]
    assert REVISED in found["text"]
    assert "conflict" in found["text"]
    reply = compose_reply(
        {
            "message": "What is the harbor kestrel?",
            "guard_decision": "allow",
            "answer": PRIOR,
            "correction_conflict": found,
            "related": [{"chunk_id": "notes-p0001", "chunk_text": PRIOR, "score": 1.0}],
        }
    )
    assert reply["text"] == found["text"]


def test_hit_rate_counts_a_relevant_id_in_the_five_and_records_the_run():
    record = measure(
        [
            {"relevant_ids": ["a"], "retrieved_ids": ["b", "a", "c"], "spoken_document_id": "a"},
            {"relevant_ids": ["d"], "retrieved_ids": ["e", "f"], "spoken_document_id": "e"},
        ],
        commit="4540532",
        machine="test",
        command="python -m pytest tests/test_enterprise_phases.py",
    )
    assert record["hit_rate_at_5"] == 0.5
    assert record["spoken_attribution"] == 0.5
    assert record["commit"] == "4540532"
    assert "threshold" not in record


def test_a_negated_question_speaks_the_stored_span():
    frame = frame_from_chunk("apple-2", "John did not eat a yellow apple in his house.")
    spoken = resolve_frames("What did John not eat?", [frame])
    assert spoken["verified"] is True
    assert spoken["text"] == "John did not eat a yellow apple in his house."
    positive = resolve_frames("Who ate the apple?", [frame])
    assert positive["text"] == "The retrieved passages do not settle that."
    assert "John ate the apple." not in positive["text"]


def test_a_role_comes_only_from_the_frames_that_were_passed_in():
    frame = frame_from_chunk("apple-1", APPLE)
    assert stated_role([frame], "color", "apple") == "yellow"
    assert stated_role([], "color", "apple") == "No stored sentence states that color in the past."
    assert resolve_frames("What color was the apple John ate in 2018?", [frame])["text"] == (
        "No stored sentence states that color in 2018."
    )


def test_an_alias_is_only_a_string_the_paragraph_states():
    bound = bind_entities("Mary, also called Molly, waved.")
    groups = {tuple(item["mentions"]) for item in bound["bound"]}
    assert ("Mary", "Molly") in groups or ("Molly", "Mary") in groups
    ambiguous = bind_entities("John saw Mary. It left.")
    assert "It" in ambiguous["unbound"] or "it" in {item.casefold() for item in ambiguous["unbound"]}
    alone = bind_entities("John left. It waited.")
    mentions = [mention for item in alone["bound"] for mention in item["mentions"]]
    assert "John" in mentions
    assert any(mention.casefold() == "it" for mention in mentions)
    assert bind_entities("The lobster sat. The lobster left.")["bound"] == []


def test_a_busy_machine_reports_other_server_without_running_the_turn():
    manager = EngineManager(cpu_count=6)
    started = threading.Event()
    release = threading.Event()
    calls = {"second": 0}

    def hold() -> str:
        started.set()
        assert release.wait(2)
        return "held"

    def second() -> str:
        calls["second"] += 1
        return "ran"

    worker = threading.Thread(
        target=lambda: manager.dispatch_turn(
            hold,
            request_id="req-1",
            tenant_id="cpu-llm",
            caller_scope=["notes-p"],
            chunk_ids=[f"notes-p000{i}" for i in range(7)],
        )
    )
    worker.start()
    assert started.wait(2)
    refused = manager.dispatch_turn(
        second,
        request_id="req-2",
        tenant_id="cpu-llm",
        chunk_ids=["notes-p0001"],
    )
    release.set()
    worker.join(2)
    assert refused["error"] == "other_server"
    assert refused["request_id"] == "req-2"
    assert calls["second"] == 0
    frame = manager.turn_frames[0]
    assert frame.metadata["request_id"] == "req-1"
    assert len(frame.vector_64) == FABRIC_WIDTH
    assert set(frame.vector_64) == {0.0}
    assert len(frame.metadata["chunk_ids"]) == 7
    assert "tensor" not in frame.metadata


def test_a_dead_seat_returns_its_request_error():
    manager = EngineManager(cpu_count=6)
    manager.seats[0].failed = True
    calls = {"n": 0}

    def work() -> str:
        calls["n"] += 1
        return "ran"

    result = manager.dispatch_turn(work, request_id="req-dead", tenant_id="cpu-llm", chunk_ids=["a", "b"])
    assert result["error"] == "seat_failed"
    assert result["request_id"] == "req-dead"
    assert calls["n"] == 0


def test_a_raised_turn_is_a_seat_failure_for_that_request():
    manager = EngineManager(cpu_count=24)

    def boom() -> None:
        raise RuntimeError("seat stopped")

    result = manager.dispatch_turn(boom, request_id="req-boom", tenant_id="tenant-a", chunk_ids=["c"])
    assert result == {"error": "seat_failed", "request_id": "req-boom", "message": "RuntimeError"}
    assert any(not seat.failed and seat.place == "this_server" for seat in manager.seats)
