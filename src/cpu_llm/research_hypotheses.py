"""Extract candidate predictions and turn them into proposed research tests."""
import re
import unicodedata

from cpu_llm.answerability import _sentences
from cpu_llm.channels import _content_words
from cpu_llm.nammade.encode import span_hash

_PREDICTION = re.compile(r"\b(?:predicts?|should|would|might|could|hypothes[ei]s)\b", re.I)
_NON_TOPIC = {"test", "research", "hypothesis", "hypotheses", "predict", "prediction"}
_SIDM_TOPIC = re.compile(r"\b(?:self[- ]interacting dark matter|sidm)\b", re.I)
_DWARF_CORES = re.compile(
    r"\bcores in dwarf galaxies with sizes of \((?P<low>\d+(?:\.\d+)?)[-–−]"
    r"(?P<high>\d+(?:\.\d+)?)\)\s*kpc\b", re.I,
)
_MERGER_BOUND = re.compile(
    r"\bupper bound of (?P<limit>\d+(?:\.\d+)?) square centimeters per gram "
    r"at (?P<confidence>\d+) percent confidence\b", re.I,
)


def sidm_boundary_option(query, rows):
    """Join a dwarf-core simulation result and an independent merger bound."""
    if not _SIDM_TOPIC.search(query):
        return None
    dwarf = merger = None
    for row in rows:
        text = unicodedata.normalize("NFKC", row["chunk_text"])
        if dwarf is None and re.search(r"\bsidm\b|withsidm", text, re.I):
            if match := _DWARF_CORES.search(text):
                dwarf = row, match
        if merger is None and all(phrase in text.casefold() for phrase in (
            "bullet cluster", "self-interactions", "mass peak", "galaxy centroid",
        )):
            if match := _MERGER_BOUND.search(text):
                merger = row, match
    if not dwarf or not merger or dwarf[0]["document_id"] == merger[0]["document_id"]:
        return None
    dwarf_row, sizes = dwarf
    merger_row, bound = merger
    low, high = sizes["low"], sizes["high"]
    limit, confidence = bound["limit"], bound["confidence"]
    premises = [
        dict(document_id=row["document_id"], span=row["chunk_text"], span_hash=span_hash(row["chunk_text"]))
        for row in (dwarf_row, merger_row)
    ]
    return dict(
        document_id=dwarf_row["document_id"],
        qualification="hypothesis",
        origin="cross_source_synthesis",
        prediction=(
            f"A single velocity-dependent self-interacting dark matter model can reproduce "
            f"dwarf-galaxy core radii in the reported simulation range ({low}–{high} kpc) "
            f"while remaining below the reported Bullet Cluster bound."
        ),
        test=(
            f"Fit the model to independent dwarf-galaxy kinematics, controlling for baryonic feedback. "
            f"Use the same parameters to predict the cluster-merger mass–galaxy offset. "
            f"Under the cited merger analysis assumptions, reject the candidate if no parameter "
            f"set that fits the dwarf data also stays below {limit} cm²/g at cluster velocities "
            f"(the reported {confidence}% confidence bound). Compare with a collisionless baseline."
        ),
        premises=premises,
        span_hash=premises[0]["span_hash"],
    )


def hypothesis_options(query, rows, *, limit=3):
    """Return source-attributed predictions with a proposed check for each."""
    if candidate := sidm_boundary_option(query, rows):
        return [candidate][:limit]
    topic = set(_content_words(query)) - _NON_TOPIC
    if not topic:
        return []
    ranked = []
    seen = set()
    for row in rows:
        chunk = row["chunk_text"]
        for sentence in _sentences(chunk):
            overlap = topic.intersection(_content_words(sentence))
            if (not overlap or not 20 <= len(sentence) <= 700 or sentence in seen
                    or sentence not in chunk or not _PREDICTION.search(sentence)):
                continue
            seen.add(sentence)
            ranked.append((len(overlap), dict(
                document_id=row["document_id"],
                prediction=sentence,
                span_hash=span_hash(sentence),
                qualification="hypothesis",
                test=("Define a measurable outcome for this prediction and compare it with an "
                      "independent observation and a baseline under the same conditions."),
            )))
    ranked.sort(key=lambda entry: -entry[0])
    return [option for _, option in ranked[:limit]]


def _phrases():
    from cpu_llm.abductive_bridge import bound_phrase, regime_phrase, shared_interval_phrase

    return bound_phrase, regime_phrase, shared_interval_phrase


def _bound_step(constraint):
    bound_phrase, regime_phrase, _shared = _phrases()
    step = {
        "kind": "bound",
        "source_id": constraint.source_id,
        "bound": bound_phrase(constraint),
        "sentence": constraint.sentence,
    }
    regime = regime_phrase(constraint)
    if regime:
        step["regime"] = regime
    return step


def _overlap_summary(left, right):
    bound_phrase, _regime, shared_interval_phrase = _phrases()
    interval = shared_interval_phrase(left, right)
    if left.kind == right.kind == "upper":
        summary = (
            f"No new mechanism was added. Both passages are upper bounds, {bound_phrase(left)} and "
            f"{bound_phrase(right)}. They overlap on {interval}, so the tighter ceiling still fits "
            "inside the looser one."
        )
        finding = f"Overlap {interval}. The tighter ceiling fits inside the looser one."
    elif left.kind == right.kind == "lower":
        summary = (
            f"No new mechanism was added. Both passages are lower bounds, {bound_phrase(left)} and "
            f"{bound_phrase(right)}. They overlap on {interval}."
        )
        finding = f"Overlap {interval}."
    else:
        summary = (
            f"No new mechanism was added. {bound_phrase(left).capitalize()} and {bound_phrase(right)} "
            f"overlap on {interval}, so one constant can satisfy both stored bounds."
        )
        finding = f"Overlap {interval}. One constant in that range satisfies both bounds."
    return summary, finding


def _bridge_summary(low, high, scaling):
    bound_phrase, regime_phrase, _shared = _phrases()
    left = regime_phrase(low)
    right = regime_phrase(high)
    difference = ""
    if left and right and left != right:
        difference = f" The passages differ by regime: {left} versus {right}."
    summary = (
        f"No constant can be both {bound_phrase(low)} and {bound_phrase(high)}.{difference} "
        f"That empty intersection is why this option is an UNVERIFIED_HYPOTHESIS: {scaling}. "
        "It is not a stored fact."
    )
    finding = "No shared value. The bounds cannot both be true of one constant."
    return summary, finding


def hypothesis_for_bridge(bridge, low, high):
    """Falsification test for one abductive candidate. The claim stays unverified."""
    candidate = bridge.candidate
    variable = candidate.mediating_variable.replace("_", " ")
    observable = candidate.shared_observable.replace("_", " ")
    scaling = {
        "inverse_monotonic": f"{observable} decreases as {variable} increases",
        "direct_monotonic": f"{observable} increases as {variable} increases",
        "threshold_piecewise": f"{observable} changes across a threshold in {variable}",
        "regime_conditional": f"{observable} is conditional on {variable}",
    }[candidate.proposed_relation]
    summary, finding = _bridge_summary(low, high, scaling)
    test = (
        f"Fit one {variable}-dependent scaling to both regimes. "
        f"Keep a parameter set only when it satisfies both constraints: "
        f"\"{candidate.regime_a_constraint}\" and \"{candidate.regime_b_constraint}\". "
        "Reject the candidate when no shared parameter set satisfies both. "
        "Claim status: UNVERIFIED_HYPOTHESIS."
    )
    if bridge.contradiction_source_ids:
        cited = ", ".join(bridge.contradiction_source_ids)
        test += f" Remaining comparisons that disagree stay recorded and do not promote the claim: {cited}."
    premises = [
        dict(document_id=source_id, span=sentence, span_hash=span_hash(sentence))
        for source_id, sentence in (
            (candidate.anchor_chunk_ids[0], candidate.regime_a_constraint),
            (candidate.anchor_chunk_ids[1], candidate.regime_b_constraint),
        )
    ]
    return dict(
        document_id=candidate.anchor_chunk_ids[0],
        qualification="hypothesis",
        origin="abductive_bridge",
        claim_status="UNVERIFIED_HYPOTHESIS",
        prediction=f"Unverified hypothesis: {scaling}.",
        test=test,
        premises=premises,
        span_hash=premises[0]["span_hash"],
        provenance={
            "decision": "unverified_hypothesis",
            "summary": summary,
            "steps": [
                _bound_step(low),
                _bound_step(high),
                {"kind": "comparison", "result": "empty", "finding": finding},
            ],
        },
    )


def compatible_bounds_option(left, right):
    """One option for two stored bounds that a single constant can satisfy."""
    _bound, _regime, shared_interval_phrase = _phrases()
    observable = left.observable.replace("_", " ")
    premises = [
        dict(document_id=item.source_id, span=item.sentence, span_hash=span_hash(item.sentence))
        for item in (left, right)
    ]
    summary, finding = _overlap_summary(left, right)
    return dict(
        document_id=left.source_id,
        qualification="bound_check",
        origin="compatible_bounds",
        claim_status="CONSISTENCY_CHECK",
        prediction=f"A single constant value of {observable} can satisfy both stored bounds.",
        test=(
            "Shared-constant check. Keep a constant only when it lies in both intervals: "
            f"\"{left.sentence}\" and \"{right.sentence}\". "
            "This option does not introduce a mediating variable."
        ),
        premises=premises,
        span_hash=premises[0]["span_hash"],
        provenance={
            "decision": "no_new_mechanism",
            "summary": summary,
            "interval": shared_interval_phrase(left, right),
            "steps": [
                _bound_step(left),
                _bound_step(right),
                {"kind": "comparison", "result": "overlap", "finding": finding},
            ],
        },
    )


def prompt_premise_hypothesis(query, comparisons):
    """Compile the user's named model against the first two stored bounds."""
    from cpu_llm.abductive_bridge import extract_constraints, names_mediating_model

    if not names_mediating_model(query):
        return None
    chosen = []
    for constraint in extract_constraints(query, comparisons):
        if chosen and (constraint.observable != chosen[0].observable or constraint.source_id in {item.source_id for item in chosen}):
            continue
        chosen.append(constraint)
        if len(chosen) == 2:
            break
    if len(chosen) < 2:
        return None
    first, second = chosen
    premises = [
        dict(document_id=item.source_id, span=item.sentence, span_hash=span_hash(item.sentence))
        for item in (first, second)
    ]
    from cpu_llm.abductive_bridge import intervals_disjoint

    bound_phrase, _regime, shared_interval_phrase = _phrases()
    if intervals_disjoint(first, second):
        summary = (
            f"This option checks only the premise named in the question. "
            f"{bound_phrase(first).capitalize()} and {bound_phrase(second)} cannot share one constant."
        )
        finding = "No shared value between the two bounds used for this premise check."
        comparison = "empty"
    else:
        interval = shared_interval_phrase(first, second)
        summary = (
            f"This option checks only the premise named in the question. "
            f"{bound_phrase(first).capitalize()} and {bound_phrase(second)} overlap on {interval}."
        )
        finding = f"Overlap {interval}."
        comparison = "overlap"
    return dict(
        document_id=first.source_id,
        qualification="hypothesis",
        origin="prompt_premise",
        claim_status="UNVERIFIED_HYPOTHESIS",
        prediction=query.strip(),
        test=(
            "Parameter-space check for the stated premise. Fit one parameter set to both constraints: "
            f"\"{first.sentence}\" and \"{second.sentence}\". "
            "Reject the premise if no shared parameter set satisfies both. "
            "This option checks only the premise named in the question."
        ),
        premises=premises,
        span_hash=premises[0]["span_hash"],
        provenance={
            "decision": "stated_premise",
            "summary": summary,
            "steps": [
                _bound_step(first),
                _bound_step(second),
                {"kind": "comparison", "result": comparison, "finding": finding},
            ],
        },
    )


def option_label(option):
    """Short name for one research reading in the reply."""
    return {
        "abductive_bridge": "Abductive bridge",
        "prompt_premise": "Stated premise",
        "compatible_bounds": "Shared constant",
        "cross_source_synthesis": "Cited premises",
    }.get(option.get("origin"), "Source prediction")


def resolve_hypotheses(query, comparisons, options):
    """Keep every distinct reading: source options, the stated premise, bridges, and shared constants."""
    from cpu_llm.abductive_bridge import AbductiveBridgeNode

    bridge, bridges, compatible = AbductiveBridgeNode().collect(query, comparisons)
    readings = list(options)
    compiled = prompt_premise_hypothesis(query, comparisons)
    if compiled is not None:
        readings.append(compiled)
    readings.extend(hypothesis_for_bridge(item, low, high) for item, low, high in bridges)
    readings.extend(compatible_bounds_option(left, right) for left, right in compatible)
    return bridge, readings


def hypothesis_intro(options, bridge):
    """One opening that separates an overlap from an unverified hypothesis."""
    has_bridge = any(item.get("origin") == "abductive_bridge" for item in options)
    has_overlap = any(item.get("origin") == "compatible_bounds" for item in options)
    lines = []
    if options:
        lines.append("Each item below is a separate option.")
    if has_bridge and has_overlap:
        lines.append(
            "A shared-constant option means the bounds overlap, so no new mechanism was added. "
            "An unverified-hypothesis option means no single constant can satisfy both bounds. "
            "That hypothesis is not a stored fact."
        )
    elif has_bridge:
        lines.append(
            "No single constant can satisfy the bounds in the hypothesis option. "
            "That hypothesis is unverified and is not a stored fact."
        )
    elif has_overlap:
        lines.append("A shared-constant option means the bounds overlap, so no new mechanism was added.")
    elif bridge.status == "INSUFFICIENT_EVIDENCE" and bridge.abstention_reason:
        lines.append(bridge.abstention_reason)
    return lines


def option_block(index, option):
    """Reply lines for one option, with the cited bounds before the decision."""
    lines = [f'H{index}. ({option_label(option)}) {option["prediction"]}']
    provenance = option.get("provenance") or {}
    for step in provenance.get("steps") or []:
        if step.get("kind") == "bound":
            regime = f" — {step['regime']}" if step.get("regime") else ""
            lines.append(f'  [{step["source_id"]}] {step["bound"]}{regime}')
            lines.append(f'  "{step["sentence"]}"')
        elif step.get("kind") == "comparison":
            lines.append(f'  {step["finding"]}')
    if provenance.get("summary"):
        lines.append(provenance["summary"])
    lines.append(option["test"])
    if option.get("premises") and not provenance:
        lines.append("Premises included " + ", ".join(f'[{item["document_id"]}]' for item in option["premises"]))
    return lines
