"""Read-only review reproductions against cpullm at 4d4ded6.

Run from the installed checkout. Prints observed behavior; this is not a
correctness test suite. The Writer probe stubs generation, not verification.
No actual neural model output or live PostgreSQL pipeline is asserted here.
"""
import json
from dataclasses import replace

from fact_bridge import answer
from fact_bridge.writer import Writer, verify
from cpu_llm.agents.reply import compose_reply
from cpu_llm.formats import render_draft
from cpu_llm.realizer.constructions import bundle_from_chunks, derivations_for, plan_for
from cpu_llm.realizer.derivation_check import check_derivation
from cpu_llm.realizer.evidence_schema import Action, replay
from cpu_llm.scale import EngineManager, scale_order


def emit(case, **observed):
    print(json.dumps({"case": case, **observed}, ensure_ascii=False))


policy = "Business class is allowed for flights over 6 hours."
long = "The flight to Paris takes 7 hours."
short = "The flight to Paris takes 2 hours."
question = "Can I fly business class on the flight to Paris?"
yes = answer(question, [policy, long])

writer = object.__new__(Writer)
writer.generate = lambda plans: ["Yes. John owns the house and business class is forbidden."]
written = writer.write(yes)
emit("writer_missing_delivery_verification", text=written.text, path=written.path,
     rejected=written.rejected)
candidate = yes.text.replace("over 6", "under 6")
emit("writer_verifier_comparator_mutation", text=candidate, verification=verify(candidate, yes.plan))

sources = [
    "Employees traveling internationally for more than 8 hours are eligible to book premium economy.",
    "Our flight to London takes roughly 10 hours.",
]
q = "Can I book premium economy on our flight to London?"
result = answer(q, sources)
reply = compose_reply({
    "message": q, "guard_decision": "allow", "answer": sources[0],
    "audit_passed": True, "shine_ok": True,
    "related": [{"chunk_id": str(i), "chunk_text": s} for i, s in enumerate(sources)],
})
emit("unretrieved_memory", supplied=sources, cited=result.because, reply=reply["text"])

result = answer(question, [policy, short])
emit("converse_of_sufficient_condition", verdict=result.verdict, text=result.text)

orders = []
for facts in ([long, short], [short, long]):
    result = answer(question, [policy, *facts])
    orders.append({"facts": facts, "verdict": result.verdict, "text": result.text})
emit("conflicting_measurement_order", orders=orders)

result = answer("Is business class forbidden on the flight to Paris?", [policy, long])
emit("query_modality", verdict=result.verdict, text=result.text)

bundle = bundle_from_chunks([("a", "John ate a yellow apple in his house.")])
plan = plan_for(bundle, "What color was the apple John ate?")
derivation = derivations_for(bundle, plan)[0][0]
actions = list(derivation.actions)
actions.insert(-1, Action("EMIT_GRAMMAR", derivation.construction_id,
                          surface=" John owns the house."))
forged = replace(derivation, actions=tuple(actions))
emit("n0_checker_mutated_trace", text=replay(forged.actions),
     rejection_reasons=check_derivation(bundle, plan, forged))

draft = render_draft("Write an email about the late shipment.", [
    {"chunk_id": "late", "chunk_text": "The shipment is late."},
    {"chunk_id": "picnic", "chunk_text": "The picnic recipient is Mary."},
])
emit("unrelated_header_role", draft=draft)

order = scale_order(stored_bytes=2000, available_bytes=1000, cpu_count=24,
                    engines=1, busy=False, waiting=0)
emit("memory_pressure_local_placement", action=order.action, place=order.place,
     engines=order.engines, stored_bytes=order.stored_bytes, available_bytes=order.available_bytes)

manager = EngineManager(cpu_count=24, available_bytes=1000000)
try:
    manager.publish_chunk("same-id", "hello")
    first = manager.stored_bytes()
    manager.publish_chunk("same-id", "hello")
    emit("republish_double_count", first_bytes=first, second_bytes=manager.stored_bytes(),
         chunks=manager.seats[0].chunks, catalog_entries=len(manager.catalog))
finally:
    manager.close()
