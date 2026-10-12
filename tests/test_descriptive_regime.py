"""A stated measurement does not open the empirical or causal heads."""

from prismthinker.adapters.chorusgraph import to_chorusgraph
from prismthinker.config import EngineConfig
from prismthinker.core.engine import PrismThinker
from prismthinker.core.schemas import (
    CausalEdge,
    CausalGraph,
    EpistemicRegime,
    EvidenceItem,
    ObjectiveSpec,
    ObjectiveTerm,
    ReasoningContext,
)

from cpu_llm.pipeline import (
    _descriptive_config,
    _directive_after_descriptive,
    _observation_without_target,
)


def _height() -> ReasoningContext:
    return ReasoningContext(
        query="What is Mount Elbert?",
        evidence=[
            EvidenceItem(
                id="p0008",
                content="Originally measured as 14,433 feet (4,399 m) in height.",
                source="vectorprism",
                numeric_claims={"height_ft": 14433.0, "height_m": 4399.0},
            )
        ],
    )


def test_a_height_without_a_target_uses_only_the_formal_head():
    context = _height()
    assert _observation_without_target(context) is True
    thinker = PrismThinker(_descriptive_config(EngineConfig(isolate_heads=False)))
    graph = thinker.evaluate(context.model_copy(update={"force_regime": EpistemicRegime.CLOSED_FORMAL}))
    envelope = to_chorusgraph(graph)
    assert graph.selected_evaluators == ["formal"]
    assert envelope.gather_questions == []
    assert _directive_after_descriptive(graph, envelope.directive.value, True) == "answer"


def test_a_caller_target_or_causal_graph_keeps_the_observation_evaluable():
    targeted = _height().model_copy(
        update={
            "objective": ObjectiveSpec(
                id="height-limit",
                terms=[ObjectiveTerm(fact_key="height_ft", weight=1.0, direction="hit", target=14440.0)],
            )
        }
    )
    assert _observation_without_target(targeted) is False
    linked = _height().model_copy(
        update={
            "causal_graph": CausalGraph(
                nodes=["treaty", "name"],
                edges=[CausalEdge(source="treaty", target="name", edge_id="treaty->name", signed=1)],
            )
        }
    )
    assert _observation_without_target(linked) is False
