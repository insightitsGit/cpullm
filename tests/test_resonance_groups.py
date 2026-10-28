"""Prototype checks for resonance tags. The store is not wired into Appliance."""

from __future__ import annotations

import importlib.util
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from cpu_llm.resonance_groups import ResonanceTags, cluster_units


def _eval():
    path = Path(__file__).with_name("resonance_eval.py")
    spec = importlib.util.spec_from_file_location("resonance_eval", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


EVAL = _eval()
CORPUS = EVAL.CORPUS


def _store(tmp_path: Path) -> ResonanceTags:
    return EVAL.build_store(tmp_path / "resonance_tags.db")


def _sense_blob(result: dict) -> list[str]:
    return [" ".join(sense["words"]) for sense in result["senses"]]


def _group_senses(groups) -> list[set[str]]:
    return [{CORPUS.SENSE_OF[unit["doc_id"]] for unit in group} for group in groups]


def _impure(groups) -> int:
    return sum(1 for senses in _group_senses(groups) if len(senses) > 1)


def _finance_groups(groups) -> int:
    return sum(1 for senses in _group_senses(groups) if "bank-finance" in senses)


def _words(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute("SELECT DISTINCT word FROM unit_word")}
    finally:
        connection.close()


def _docs(path: Path) -> set[str]:
    connection = sqlite3.connect(path)
    try:
        return {row[0] for row in connection.execute("SELECT DISTINCT doc_id FROM unit")}
    finally:
        connection.close()


def test_bare_ambiguous_words_list_senses_and_no_units(tmp_path):
    store = _store(tmp_path)
    bank = store.recall_spread("bank")
    assert bank["status"] == "ambiguous"
    assert bank["units"] == []
    bank_words = _sense_blob(bank)
    assert any("vault" in words for words in bank_words)
    assert any("shore" in words for words in bank_words)

    bat = store.recall_spread("bat")
    assert bat["status"] == "ambiguous"
    assert bat["units"] == []
    bat_words = _sense_blob(bat)
    assert any("wing" in words for words in bat_words)
    assert any("inning" in words for words in bat_words)

    python = store.recall_spread("python")
    assert python["status"] == "ambiguous"
    assert python["units"] == []
    python_words = _sense_blob(python)
    assert any("compiler" in words for words in python_words)
    assert any("fang" in words for words in python_words)


def test_bank_police_robbery_leaves_the_river_silent(tmp_path):
    store = _store(tmp_path)
    result = store.recall_spread("bank police robbery")
    assert result["status"] == "ok"
    docs = {unit["doc_id"] for unit in result["units"]}
    assert docs.isdisjoint(CORPUS.DOC_IDS["bank-river"])
    assert docs <= set(CORPUS.DOC_IDS["bank-finance"])
    assert "notes-p0001" in docs


def test_uncorroborated_pair_expands_through_the_shared_sense_word(tmp_path):
    store = _store(tmp_path)
    result = store.recall_spread("police robbery")
    assert result["status"] == "ok"
    expanded = [unit for unit in result["units"] if unit["expanded"]]
    assert expanded
    assert all(unit["shared"] == [] for unit in expanded)
    assert all("vault" in unit["text"] for unit in expanded)
    assert all("police" not in unit["text"] and "robbery" not in unit["text"] for unit in expanded)


def test_units_stay_explainable_candidates(tmp_path):
    store = _store(tmp_path)
    result = store.recall_spread("bank vault payroll")
    assert set(result) == {"status", "units", "senses"}
    assert result["senses"] == []
    assert result["units"]
    for unit in result["units"]:
        assert {"unit_id", "doc_id", "text", "shared", "expanded", "score"} <= set(unit)
        assert isinstance(unit["shared"], list)
        assert isinstance(unit["expanded"], bool)
        assert isinstance(unit["score"], float)


def test_cluster_sweep_shows_why_hard_groups_were_dropped(tmp_path):
    store = _store(tmp_path)
    units = store._load(None)
    strict = cluster_units(units, 0.22)
    loose = cluster_units(units, 0.03)
    assert _impure(strict) == 0
    assert _finance_groups(strict) == 5
    assert _finance_groups(loose) == 1
    assert _impure(loose) == 3


def test_scope_ignores_tags_outside_the_allowed_prefix(tmp_path):
    path = tmp_path / "resonance_tags.db"
    store = ResonanceTags(path)
    own = []
    other = []
    for row in CORPUS.SENTENCES:
        number = row["doc_id"].rsplit("-p", 1)[1]
        own.append((f"a-p{number}", row["text"]))
        other.append((f"b-p{number}", row["text"]))
    store.add_chunks(own + other)
    messages = ("bank", "bank police robbery", "python interpreter syntax", "crane feather flock")
    scoped = [store.recall_spread(message, allowed={"a-p"}) for message in messages]
    for result in scoped:
        assert all(unit["doc_id"].startswith("a-p") for unit in result["units"])
    store.delete_prefix("b-p")
    alone = [store.recall_spread(message, allowed={"a-p"}) for message in messages]
    assert scoped == alone
    assert _docs(path) == {doc_id for doc_id, _text in own}


def test_reingest_and_delete_remove_only_that_source(tmp_path):
    path = tmp_path / "resonance_tags.db"
    store = ResonanceTags(path)
    store.add_chunks(
        [
            ("notes-p0001", "The bank vault stored payroll cash after the robbery police response."),
            ("notes-p0002", "The bank vault teller counted the deposit slips."),
            ("kept-p0001", "The bat wing beat over the nocturnal moths."),
        ]
    )
    store.consolidate()
    replaced = store.add_chunks(
        [("notes-p0001", "The bank shore met the slow current.")],
        replace_prefix="notes-p",
    )
    assert replaced == 1
    assert _docs(path) == {"notes-p0001", "kept-p0001"}
    words = _words(path)
    assert "payroll" not in words
    assert "teller" not in words
    assert "shore" in words
    assert "wing" in words

    store.add_chunks(
        [
            ("hr-p0001", "The bank vault stored payroll cash."),
            ("hr-p0002-v1700000000", "The bank vault guard watched the lobby doors."),
            ("hr-policy-p0001", "The bank shore cattail hid the carp fry."),
        ]
    )
    receipt = store.delete_prefix("hr-p")
    assert receipt == {"units": 2, "words": receipt["words"]}
    assert receipt["words"] > 0
    assert "hr-p0001" not in _docs(path)
    assert "hr-p0002-v1700000000" not in _docs(path)
    assert "hr-policy-p0001" in _docs(path)
    assert "guard" not in _words(path)
    assert "cattail" in _words(path)

    store.consolidate()
    notes = store.delete_prefix("notes-p")
    assert notes["units"] == 1
    assert _docs(path) == {"kept-p0001", "hr-policy-p0001"}
    assert "current" not in _words(path)
    assert "shore" in _words(path)
    assert "wing" in _words(path)
    from cpu_llm.source_ids import matches_prefix

    connection = sqlite3.connect(path)
    try:
        members = [row[0] for row in connection.execute("SELECT unit_id FROM grp_member")]
    finally:
        connection.close()
    assert all(not matches_prefix(unit_id.split("#", 1)[0], "notes-p") for unit_id in members)
    assert all(not matches_prefix(unit_id.split("#", 1)[0], "hr-p") for unit_id in members)
    assert any(unit_id.startswith("hr-policy-p0001") for unit_id in members)


def test_candidates_keep_the_sense_and_leave_a_hub_only_sense_out(tmp_path):
    store = _store(tmp_path)
    crane = store.recall_candidates("crane feather flock")
    assert crane["status"] == "ok"
    texts = " ".join(unit["text"].casefold() for unit in crane["units"])
    assert "feather" in texts
    assert "girder" not in texts
    assert "gantry" not in texts
    robbery = store.recall_candidates("police robbery")
    assert any(unit["expanded"] for unit in robbery["units"])
    assert {CORPUS.SENSE_OF[unit["doc_id"]] for unit in robbery["units"]} == {"bank-finance"}


def test_replaced_sentence_moves_to_the_new_id(tmp_path):
    store = ResonanceTags(tmp_path / "resonance_tags.db")
    store.add_chunks(
        [
            ("notes-p0001", "The bank vault stored payroll cash. The ledger stayed in the vault."),
            ("kept-p0001", "The bat wing beat over the nocturnal moths."),
        ]
    )
    receipt = store.replace_sentence(
        "notes-p0001",
        "The bank vault stored payroll cash.",
        "notes-p0001-v10",
        "The bank shore met the slow current.",
    )
    assert receipt["removed"] == 1
    assert receipt["stored"] == 1
    docs = _docs(tmp_path / "resonance_tags.db")
    assert "notes-p0001-v10" in docs
    assert "kept-p0001" in docs
    words = _words(tmp_path / "resonance_tags.db")
    assert "payroll" not in words
    assert "ledger" in words
    assert "shore" in words


def test_delete_receipt_counts_only_the_source_tags(tmp_path):
    from cpu_llm.source_delete import delete_stored_source

    path = tmp_path / "resonance_tags.db"
    tags = ResonanceTags(path)
    tags.add_chunks(
        [
            ("hr-p0001", "The bank vault stored payroll cash."),
            ("hr-p0002-v1700000000", "The bank vault guard watched the lobby doors."),
            ("hr-policy-p0001", "The bank shore cattail hid the carp fry."),
        ]
    )

    class Index:
        def delete_prefix(self, prefix):
            return 1

    class Memory:
        def all_nodes(self):
            return []

        def all_edges(self):
            return []

    receipt = delete_stored_source(Index(), Memory(), {}, None, "hr-p", resonance_tags=tags)
    assert receipt["resonance"] == "unchanged"
    assert receipt["resonance_tags"]["units"] == 2
    assert receipt["resonance_tags"]["words"] > 0
    assert _docs(path) == {"hr-policy-p0001"}
    assert "guard" not in _words(path)
    assert "cattail" in _words(path)
    untouched = delete_stored_source(Index(), Memory(), {}, None, "other")
    assert untouched["resonance_tags"] == {"units": 0, "words": 0}


def test_retrieval_adds_the_matching_sense_without_changing_dense_order(tmp_path):
    import numpy as np
    from types import SimpleNamespace

    from cpu_llm.pipeline import _sense_clarification, _store_resonance_tags, _with_resonance_paragraphs

    store = _store(tmp_path)
    texts = {row["doc_id"]: row["text"] for row in CORPUS.SENTENCES}

    class Database:
        def get_by_ids(self, ids):
            return [
                {"document_id": doc_id, "chunk_text": texts[doc_id], "tensor_1024d": np.zeros(4, dtype=np.float32)}
                for doc_id in ids
            ]

    dense = {"document_id": "already-p0001", "chunk_text": "dense hit", "final_score": 0.9}
    enabled = SimpleNamespace(resonance_tags_enabled=True, resonance_tags=store, index=SimpleNamespace(db=Database()))
    added = _with_resonance_paragraphs(enabled, "crane feather flock", [dense], allowed=None)
    assert added[0] == dense
    assert all(hit["final_score"] == 0.0 for hit in added[1:])
    assert any("feather" in hit["chunk_text"] for hit in added[1:])
    assert all("girder" not in hit["chunk_text"] for hit in added[1:])
    assert all(hit["resonance_tag"]["shared"] for hit in added[1:])
    disabled = SimpleNamespace(resonance_tags_enabled=False, resonance_tags=store, index=SimpleNamespace(db=Database()))
    assert _with_resonance_paragraphs(disabled, "crane feather flock", [dense], allowed=None) == [dense]
    before = store.counts()
    assert _store_resonance_tags(disabled, [("zzz-p0001", "The bank vault stored payroll cash.")]) == 0
    assert store.counts() == before
    from cpu_llm.clarification import ClarificationLoop

    loop = ClarificationLoop()
    enabled.clarifications = loop
    enabled._turn = {"allowed_sources": None}
    assert _sense_clarification(enabled, "bank", None)['slot'] == 'sense'
    assert not loop.pending
    question = _sense_clarification(enabled, "bank", ("tenant", "caller", (), "chat", None))
    assert question["status"] == "needs_clarification"
    assert question["slot"] == "sense"
    assert "vault" in question["text"]
    assert "shore" in question["text"]


def test_spreading_meets_the_measured_gate(tmp_path):
    precision, recall = EVAL.spreading_scores(tmp_path / "resonance_tags.db")
    assert precision >= 0.88
    assert recall >= 0.89
    completed = subprocess.run(
        [sys.executable, str(Path(__file__).with_name("resonance_eval.py"))],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_resonance_tags_default_off_and_true_still_wires_the_store(tmp_path):
    import inspect
    from types import SimpleNamespace

    from cpu_llm.pipeline import Appliance, _correct_resonance_tags, _resonance_store, _store_resonance_tags
    from cpu_llm.resonance_groups import ResonanceTags
    from cpu_llm.source_delete import delete_stored_source

    assert inspect.signature(Appliance.__init__).parameters["resonance_tags"].default is False
    assert "_store_resonance_tags" in inspect.getsource(Appliance.catalog_chunks)
    assert "_store_resonance_tags" in inspect.getsource(Appliance.index_chunks)
    assert "_correct_resonance_tags" in inspect.getsource(Appliance.correct)
    assert "_resonance_store" in inspect.getsource(Appliance.delete_source)

    class Index:
        def delete_prefix(self, prefix):
            return 1

    class Memory:
        def all_nodes(self):
            return []

        def all_edges(self):
            return []

    path = tmp_path / "resonance_tags.db"
    store = ResonanceTags(path)
    enabled = SimpleNamespace(resonance_tags_enabled=True, resonance_tags=store)
    assert _store_resonance_tags(enabled, [("notes-p0001", "The bank vault stored payroll cash.")]) == 1
    _correct_resonance_tags(
        enabled,
        "notes-p0001",
        "The bank vault stored payroll cash.",
        "notes-p0001-v2",
        "The bank shore met the slow current.",
    )
    assert _docs(path) == {"notes-p0001-v2"}
    receipt = delete_stored_source(Index(), Memory(), {}, None, "notes-p", resonance_tags=_resonance_store(enabled))
    assert receipt["resonance_tags"]["units"] == 1
    assert _docs(path) == set()

    disabled = SimpleNamespace(resonance_tags_enabled=False, resonance_tags=store)
    assert _resonance_store(disabled) is None
    assert _store_resonance_tags(disabled, [("notes-p0001", "The bank vault stored payroll cash.")]) == 0
    _correct_resonance_tags(disabled, "notes-p0001", "old", "notes-p0001-v3", "The bank vault stored payroll cash.")
    assert _docs(path) == set()


def test_two_scopes_stay_apart_across_twenty_runs(tmp_path):
    """Two callers on one store never see each other's documents."""
    import json
    import threading

    from cpu_llm.resonance_groups import ResonanceTags

    store = ResonanceTags(tmp_path / "scopes.db")
    store.add_chunks(
        [
            ("a-p0001", "The bank vault stores alphatoken cash."),
            ("a-p0002", "The bank vault holds alphatoken payroll."),
            ("b-p0001", "The bank shore grows bravotoken reeds."),
            ("b-p0002", "The bank shore has bravotoken sand."),
        ]
    )

    def once() -> None:
        barrier = threading.Barrier(2)
        leaks: list[str] = []

        def worker(prefix: str, foreign: str) -> None:
            barrier.wait()
            for _ in range(500):
                result = store.recall_spread("bank", allowed={prefix})
                if foreign in json.dumps(result):
                    leaks.append(foreign)
                for unit in result["units"]:
                    if not str(unit["doc_id"]).startswith(prefix):
                        leaks.append(str(unit["doc_id"]))
                for sense in result["senses"]:
                    words = sense["words"] if isinstance(sense, dict) else sense
                    if foreign in words:
                        leaks.append(foreign)

        threads = [
            threading.Thread(target=worker, args=("a-p", "bravotoken")),
            threading.Thread(target=worker, args=("b-p", "alphatoken")),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert leaks == []

    for _ in range(20):
        once()


def test_bare_crane_stays_one_sense_while_lifted_links_them(tmp_path):
    """Current behavior. The strict xfail below is the behavior we still want."""
    store = _store(tmp_path)
    result = store.recall_spread("crane")
    assert result["status"] == "ok"
    assert {CORPUS.SENSE_OF[unit["doc_id"]] for unit in result["units"]} == {
        "crane-bird",
        "crane-machine",
    }


@pytest.mark.xfail(strict=True, reason="lifted joins the crane senses; open decisions 1 and 6")
def test_spread_does_not_merge_senses_through_an_accidental_shared_word(tmp_path):
    store = _store(tmp_path)
    result = store.recall_spread("crane feather flock")
    texts = " ".join(unit["text"].casefold() for unit in result["units"])
    assert "girder" not in texts
    assert "gantry" not in texts


@pytest.mark.xfail(strict=True, reason="bare crane is one component while lifted is not a hub")
def test_bare_crane_is_ambiguous(tmp_path):
    store = _store(tmp_path)
    result = store.recall_spread("crane")
    assert result["status"] == "ambiguous"
    assert result["units"] == []
    assert len(result["senses"]) >= 2


@pytest.mark.xfail(strict=True, reason="no threshold is both pure and a single finance group")
def test_cluster_groups_stay_pure_and_unfragmented(tmp_path):
    store = _store(tmp_path)
    units = store._load(None)
    found = any(
        _finance_groups(cluster_units(units, threshold / 100)) == 1
        and _impure(cluster_units(units, threshold / 100)) == 0
        for threshold in range(1, 51)
    )
    assert found


def test_sense_components_join_through_a_shared_word():
    from cpu_llm.resonance_groups import _sense_components

    units = [
        {"unit_id": "a", "words": {"cedar", "white"}},
        {"unit_id": "b", "words": {"cedar", "diesel"}},
        {"unit_id": "c", "words": {"white", "hull"}},
        {"unit_id": "e", "words": {"hull", "diesel"}},
        {"unit_id": "d", "words": {"spring", "clock"}},
    ]
    groups = {frozenset(group) for group in _sense_components(units, {"cedar"})}
    assert frozenset({"a", "b", "c", "e"}) in groups
    assert frozenset({"d"}) in groups
    separate = {frozenset(group) for group in _sense_components(units[:2], {"cedar"})}
    assert separate == {frozenset({"a"}), frozenset({"b"})}


def test_a_named_attribute_is_not_replaced_by_a_sense_question(tmp_path):
    from types import SimpleNamespace

    from cpu_llm.clarification import ClarificationLoop
    from cpu_llm.pipeline import _sense_clarification

    store = ResonanceTags(tmp_path / "tags.db")
    store.add_chunks([
        ("cedar-p0001", "The Cedar is white."),
        ("cedar-p0002", "The Cedar has a diesel engine."),
        ("cedar-p0003", "The Cedar is found in Millhaven."),
        ("cedar-p0004", "The Cedar departs at dawn."),
        ("cedar-p0005", "The Cedar carries cars."),
        ("cedar-p0006", "The Cedar uses fuel."),
        ("cedar-p0007", "The Cedar crosses daily."),
        ("spring-p0001", "The clock spring turns the hands."),
        ("spring-p0002", "The spare clock spring sits in the drawer."),
        ("spring-p0003", "The mountain spring feeds the pond."),
        ("spring-p0004", "The forest spring joins the creek."),
    ])
    appliance = SimpleNamespace(
        resonance_tags_enabled=True,
        resonance_tags=store,
        clarifications=ClarificationLoop(),
        _turn={"allowed_sources": None},
    )
    assert _sense_clarification(appliance, "What color is the Cedar?", None) is None
    assert _sense_clarification(appliance, "What kind of boat is the Cedar?", None) is None
    assert _sense_clarification(appliance, "Where does the Cedar live?", None) is None
    assert _sense_clarification(appliance, "How long does the Cedar live?", None) is None
    assert _sense_clarification(appliance, "What does the Cedar have?", None) is None
    spring = _sense_clarification(appliance, "What is a spring?", None)
    assert spring["slot"] == "sense"
    blob = " ".join(" ".join(sense["words"]) for sense in spring["senses"])
    assert "clock" in blob
    assert "pond" in blob or "creek" in blob or "mountain" in blob or "forest" in blob
    assert _sense_clarification(appliance, "Who captains the Cedar?", None) is None
    assert _sense_clarification(appliance, "Compare the Cedar and the Rowan.", None) is None


def test_a_valid_choice_does_not_reopen_the_sense_question(tmp_path):
    from types import SimpleNamespace

    from cpu_llm.clarification import ClarificationLoop
    from cpu_llm.pipeline import _open_sense_question, _sense_clarification

    store = ResonanceTags(tmp_path / "bats.db")
    store.add_chunks([
        ("bat-m1", "The bat is a mammal."),
        ("bat-m2", "The flying bat hunts insects."),
        ("bat-m3", "The nocturnal bat uses echolocation."),
        ("bat-m4", "The winged bat roosts in caves."),
        ("bat-c1", "The bat is a wooden club."),
        ("bat-c2", "The carved bat hits baseballs."),
        ("bat-c3", "The oak bat cracks pitches."),
        ("bat-c4", "The weighted bat swings hard."),
    ])
    appliance = SimpleNamespace(
        resonance_tags_enabled=True,
        resonance_tags=store,
        clarifications=ClarificationLoop(),
        _turn={"allowed_sources": None},
    )
    first = _sense_clarification(appliance, "What kind of thing is the bat?", "chat")
    assert first["slot"] == "sense"
    ready = appliance.clarifications.prepare("1", key="chat")
    assert ready["status"] == "ready"
    chosen = " ".join(ready["sense"]["words"])
    restored = ready["question"]
    assert restored == "What kind of thing is the bat?"
    assert _open_sense_question(chosen, as_of=None, allowed=True) is False
    assert _open_sense_question("", as_of=None, allowed=True) is True
    # The restored question is still ambiguous. The gate would ask it again.
    again = _sense_clarification(appliance, restored, "chat")
    assert again["slot"] == "sense"
    assert again["text"] == first["text"]


def test_two_kinds_of_bat_stay_ambiguous(tmp_path):
    from types import SimpleNamespace

    from cpu_llm.clarification import ClarificationLoop
    from cpu_llm.pipeline import _sense_clarification

    store = ResonanceTags(tmp_path / "bats.db")
    store.add_chunks([
        ("bat-m1", "The bat is a mammal."),
        ("bat-m2", "The flying bat hunts insects."),
        ("bat-m3", "The nocturnal bat uses echolocation."),
        ("bat-m4", "The winged bat roosts in caves."),
        ("bat-c1", "The bat is a wooden club."),
        ("bat-c2", "The carved bat hits baseballs."),
        ("bat-c3", "The oak bat cracks pitches."),
        ("bat-c4", "The weighted bat swings hard."),
    ])
    appliance = SimpleNamespace(
        resonance_tags_enabled=True,
        resonance_tags=store,
        clarifications=ClarificationLoop(),
        _turn={"allowed_sources": None},
    )
    asked = _sense_clarification(appliance, "What kind of thing is the bat?", None)
    assert asked["slot"] == "sense"
    blob = " ".join(" ".join(sense["words"]) for sense in asked["senses"])
    assert "mammal" in blob
    assert "wooden" in blob or "club" in blob
    assert "another meaning" not in asked["text"]


def test_sense_choices_are_capped(tmp_path):
    store = ResonanceTags(tmp_path / "many.db")
    words = [
        "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel",
        "india", "juliet", "kilo", "lima", "mike", "november", "oscar", "papa",
        "quebec", "romeo", "sierra", "tango",
    ]
    store.add_chunks([(f"topic-{word}", f"The topic {word}.") for word in words])
    result = store.recall_spread("topic")
    assert result["status"] == "ambiguous"
    assert len(result["senses"]) == 8
    assert result["omitted"] == 12
    assert all(sense["words"] for sense in result["senses"])
