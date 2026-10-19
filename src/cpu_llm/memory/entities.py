"""Entity ids from a stored paragraph.

Two mentions share an id when the surface string is the same, or when the
paragraph itself says one is also called the other. A ``{category}:{term}``
tag is not an alias. A pronoun with more than one possible noun stays
unbound. Near vectors and hyperbolic or relational heads are not a binding.
"""

from __future__ import annotations

import re

_NAME = re.compile(r"\b[A-Z][a-z]+(?: [A-Z][a-z]+)*\b")
_ALSO_CALLED = re.compile(
    r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*), also called ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b"
)
_KNOWN_AS = re.compile(
    r"\b([A-Z][a-z]+(?: [A-Z][a-z]+)*) is also known as ([A-Z][a-z]+(?: [A-Z][a-z]+)*)\b"
)
_PRONOUN = re.compile(r"\b(it|they|he|she|them|him|her)\b", re.IGNORECASE)
_SKIP = frozenset("the a an in if it they he she them him her what where who".split())


def bind_entities(text: str) -> dict[str, list]:
    """Groups of mentions, and pronouns that stay unbound.

    ``bound`` is a list of ``{"id", "mentions"}``. ``unbound`` is the pronoun
    surfaces that had more than one candidate, or no candidate.
    """
    paragraph = text or ""
    names = [match.group(0) for match in _NAME.finditer(paragraph) if match.group(0).casefold() not in _SKIP]
    groups: dict[str, set[str]] = {}
    owner: dict[str, str] = {}

    def join(left: str, right: str) -> None:
        left_key = left.casefold()
        right_key = right.casefold()
        left_id = owner.get(left_key) or left_key
        right_id = owner.get(right_key) or right_key
        target = left_id
        groups.setdefault(target, set()).add(left)
        groups.setdefault(target, set()).add(right)
        if right_id != target and right_id in groups:
            groups[target].update(groups.pop(right_id))
        owner[left_key] = target
        owner[right_key] = target

    for name in names:
        key = name.casefold()
        if key not in owner:
            owner[key] = key
            groups.setdefault(key, set()).add(name)
        else:
            groups[owner[key]].add(name)
    for pattern in (_ALSO_CALLED, _KNOWN_AS):
        for match in pattern.finditer(paragraph):
            join(match.group(1), match.group(2))

    distinct = {name.casefold() for name in names}
    unbound: list[str] = []
    bound_pronouns: list[str] = []
    for match in _PRONOUN.finditer(paragraph):
        surface = match.group(0)
        if len(distinct) == 1:
            only = next(iter(names))
            groups[owner[only.casefold()]].add(surface)
            bound_pronouns.append(surface)
        else:
            unbound.append(surface)

    bound = [
        {"id": key, "mentions": sorted(values, key=str.casefold)}
        for key, values in sorted(groups.items())
        if values
    ]
    return {"bound": bound, "unbound": unbound, "pronouns_bound": bound_pronouns}
