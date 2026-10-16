"""The N0 realizer speaks only the clauses the plan licensed."""

import inspect
from dataclasses import replace

from cpu_llm.ir.schema import EdgeType, TypedGraphEdge
from cpu_llm.memory.frames import resolve_frames, frame_from_chunk
from cpu_llm.pipeline import Appliance
from cpu_llm.realizer.constructions import bundle_from_chunks
from cpu_llm.realizer.derivation_check import check_derivation
from cpu_llm.realizer.evidence_schema import replay
from cpu_llm.realizer.ranker import UntrainedCheckpoint, apply_realization, load_checkpoint, realize, select
from cpu_llm.realizer.surface import SemanticSurfaceRealizer

APPLE = "John ate a yellow apple in his house."
SELLER = "The apple seller ate a yellow apple in his house."
FALLBACK = "I don't have enough grounded evidence to answer that confidently."


def test_the_default_ask_does_not_opt_into_the_realizer():
    signature = inspect.signature(Appliance.ask)
    assert signature.parameters["realization"].default == "deterministic"
    assert signature.parameters["account"].default is False
    try:
        load_checkpoint("missing.pt")
    except UntrainedCheckpoint as exc:
        assert "no trained" in str(exc)


def test_frame_sentences_match_the_stage1_speaker():
    cases = [
        ("What color was the apple John ate?", APPLE, "The apple John ate was yellow."),
        ("Where did John eat the apple?", APPLE, "John ate the apple in his house."),
        ("Who ate the apple?", APPLE, "John ate the apple."),
        ("What color was the apples?", "The apples were yellow.", "The apples were yellow."),
    ]
    for question, source, expected in cases:
        frame = frame_from_chunk("apple-1", source)
        assert resolve_frames(question, [frame])["text"] == expected
        result = realize(bundle_from_chunks([("apple-1", source)]), question)
        assert result["text"] == expected
        assert result["verified"] is True
        assert result["model_checkpoint_id"] is None
        assert result["mode"] == "deterministic_fallback"


def test_the_seven_frame_regressions_still_abstain():
    picture = "John ate a picture of the apple in his house."
    attached = "John ate the apple with Mary in his house."
    conditional = "John ate a yellow apple if Mary cooked dinner."
    for source, question in (
        (picture, "Who ate the apple?"),
        (attached, "Who ate the apple?"),
        (conditional, "Who ate the dinner?"),
    ):
        result = realize(bundle_from_chunks([("bad", source)]), question)
        assert result["status"] == "missing"
        assert result["text"] == "No stored sentence names who did that."
        assert "John ate the apple." not in result["text"]
        assert "John ate the dinner." not in result["text"]
    seller = bundle_from_chunks([("seller", SELLER)])
    patient = next(span for record in seller.records if record.kind == "frame" for span in record.spans if span.role == "patient")
    assert (patient.start, patient.end, patient.text) == (30, 35, "apple")
    refused = realize(seller, "What color was the apple?")
    assert refused["status"] == "unsupported"
    assert "yellow" not in refused["text"]
    undated = bundle_from_chunks([("apple-1", APPLE)])
    prefixed = realize(undated, "In 2020, what color was the apple John ate?")
    assert prefixed["text"] == "No stored sentence states that color in 2020."
    present = realize(bundle_from_chunks([("present", "The apple is yellow.")]), "What color was the apple?")
    assert present["text"] == "No stored sentence states that color in the past."
    assert "yellow" not in present["text"]
    odd = realize(undated, "On Tuesday, what color was the apple John ate?")
    assert odd["status"] == "unsupported"
    assert "yellow" not in odd["text"]
    plain = realize(bundle_from_chunks([("plain", "John ate an apple in his house.")]), "What color was the apple John ate?")
    assert plain["text"] == "No stored sentence states that color in the past."
    yellow = frame_from_chunk("yellow", APPLE)
    red = frame_from_chunk("red", "John ate a red apple in his house.")
    conflict = realize(bundle_from_chunks([("yellow", APPLE), ("red", "John ate a red apple in his house.")]), "What color was the apple John ate?")
    assert conflict["status"] == "conflicting"
    assert conflict["text"] == "Two stored sentences state different colors."
    assert yellow is not None and red is not None


def test_a_proposition_is_the_realizer_clause_and_the_account_keeps_hands_apart():
    source = "Mary baked a cake."
    bundle = bundle_from_chunks(
        [("mary", source)],
        attributes={"mary": {"relation_hands": {"1": ["lobster"]}, "taxonomy_tags": [{"category": "crustacean"}]}},
    )
    spoken = realize(bundle, "What did Mary bake?")
    expected, _delivered = SemanticSurfaceRealizer().synthesize(
        [next(record.proposition for record in bundle.records if record.proposition is not None)],
        [],
    )
    assert spoken["text"] == expected
    assert "lobster" not in spoken["text"]
    assert "crustacean" not in spoken["text"]
    account = realize(bundle, "What did Mary bake?", account=True)
    clauses = account["text"].split(". ")
    assert clauses[0].rstrip(".") == expected.rstrip(".")
    assert "lobster" not in clauses[0]
    assert "These words share a stored word-edge: lobster." in account["text"]
    assert "Stored tag: crustacean." in account["text"]
    assert "is a crustacean" not in account["text"]
    quote = realize(bundle_from_chunks([("picture", "A picture of the apple.")]), "Describe it.", account=True)
    assert quote["text"] == "A picture of the apple."


def test_math_stays_off_the_proposition_store_and_a_cause_is_a_stored_edge():
    math = realize(
        bundle_from_chunks([], math_result={"ok": True, "expression": "2+2", "value": "4", "text": "2+2 = 4."}),
        "2+2",
    )
    assert math["text"] == "2+2 = 4."
    assert all(not item.startswith("prop-") for item in math["evidence_ids"])
    first = "Mary baked a cake."
    second = "John ate a yellow apple in his house."
    edge = TypedGraphEdge(source_id="prop-mary", target_id="prop-john", edge_type=EdgeType.CAUSAL_RELATION)
    caused = realize(
        bundle_from_chunks([("mary", first), ("john", second)], causal_edges=[edge]),
        "What happened?",
        account=True,
    )
    assert "Consequently, John ate a yellow apple in his house." in caused["text"]
    plain = realize(bundle_from_chunks([("mary", first), ("john", second)]), "What happened?", account=True)
    assert "Consequently" not in plain["text"]


def test_uniform_scores_stay_inside_the_licensed_set_and_a_foreign_span_fails():
    bundle = bundle_from_chunks(
        [("apple-1", APPLE)],
        attributes={"apple-1": {"relation_hands": {"1": ["lobster"]}}},
    )
    result = realize(bundle, "What color was the apple John ate?")
    derivation = _only_derivation(bundle)
    other = replace(derivation, construction_id="zzz_other", derivation_id="zzz_other:frame")
    assert select([derivation, other], "uniform") is derivation
    assert select([other, derivation], "uniform").construction_id in {derivation.construction_id, other.construction_id}
    hand = next(record for record in bundle.records if record.kind == "word_edge").spans[0]
    stolen = []
    for action in derivation.actions:
        if action.kind == "COPY" and action.role == "color":
            stolen.append(replace(action, span_id=hand.span_id, surface=hand.text, role="color"))
        else:
            stolen.append(action)
    mutated = replace(derivation, actions=tuple(stolen))
    assert check_derivation(bundle, _plan(bundle), mutated)
    assert "lobster" not in result["text"]
    assert replay(derivation.actions) == result["text"]


def test_a_shine_rejection_is_not_replaced_and_a_plain_question_is_not_the_account():
    state = {
        "message": "What color was the apple John ate?",
        "frame": True,
        "shine_ok": False,
        "shine_enforced": True,
        "related": [{"chunk_id": "apple-1", "chunk_text": APPLE}],
        "reply": {"text": FALLBACK},
    }
    update = apply_realization(state, realization="evidence_neural", account=False)
    assert "reply" not in update
    assert update["realization_result"]["status"] == "blocked"
    assert update["realization_result"]["text"] == FALLBACK
    assert update["realization_result"]["verified"] is False
    plain = {
        "message": "What did Mary bake?",
        "related": [
            {
                "chunk_id": "mary",
                "chunk_text": "Mary baked a cake.",
                "attributes": {"relation_hands": {"1": ["lobster"]}},
            }
        ],
        "reply": {"text": "Mary baked a cake."},
    }
    held = apply_realization(plain, realization="evidence_neural", account=False)
    assert "reply" not in held
    assert "lobster" not in held["realization_result"]["text"]
    opened = apply_realization(plain, realization="deterministic", account=True)
    assert opened["reply"]["text"].startswith("Mary baked a cake.")
    assert "lobster" in opened["reply"]["text"]


def _only_derivation(bundle):
    from cpu_llm.realizer.constructions import derivations_for, plan_for

    plan = plan_for(bundle, "What color was the apple John ate?")
    groups = derivations_for(bundle, plan)
    assert len(groups) == 1 and len(groups[0]) == 1
    return groups[0][0]


def _plan(bundle):
    from cpu_llm.realizer.constructions import plan_for

    return plan_for(bundle, "What color was the apple John ate?")
