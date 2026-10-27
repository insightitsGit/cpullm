"""Independent membership and rule join. This module does not import cpu_llm."""

from __future__ import annotations


def _kind_match(universal_subject: str, kind: str) -> bool:
    left = " ".join(universal_subject.casefold().split())
    right = " ".join(kind.casefold().split())
    if left.startswith("every "):
        left = left[6:]
    if left.startswith("all "):
        left = left[4:]
    if left.endswith("s") and not left.endswith("ss") and right + "s" == left:
        return True
    return left == right


def entailed(facts: list[dict], subject: str, relation: str) -> list[str]:
    """Return objects licensed for one individual.

    A direct fact licenses itself. An every/all fact licenses an individual only
    when that individual is a member of the quantified kind. Some, average, and
    unquantified class statements license nothing about an individual.
    """
    name = subject.casefold()
    licensed = [
        fact["object"]
        for fact in facts
        if fact["subject"].casefold() == name
        and fact["relation"] == relation
        and fact["quantifier"] == "direct"
    ]
    kinds = [
        fact["object"]
        for fact in facts
        if fact["subject"].casefold() == name
        and fact["relation"] == "is_a"
        and fact["quantifier"] == "direct"
    ]
    for kind in kinds:
        for fact in facts:
            if fact["relation"] != relation or fact["quantifier"] != "every":
                continue
            if _kind_match(fact["subject"], kind):
                licensed.append(fact["object"])
    return licensed
