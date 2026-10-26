"""Thirty-three sentences for the resonance-tag mechanism check.

Four ambiguous words, two senses each, one source. Senses are mixed only by
sharing the ambiguous word, except the crane senses, which also share "lifted".
The sentences are synthetic. They are not a claim about real documents.
"""

from __future__ import annotations


def _id(number: int) -> str:
    return f"notes-p{number:04d}"


_ROWS = [
    # bank / finance. "vault" joins the first four. The fifth shares only "bank".
    ("bank-finance", "The bank vault stored payroll cash after the robbery police response."),
    ("bank-finance", "The bank vault teller counted the deposit slips."),
    ("bank-finance", "The bank vault guard watched the lobby doors."),
    ("bank-finance", "The bank vault loan funded the corner shop."),
    ("bank-finance", "The bank audit checked the ledger totals."),
    # bank / river. "shore" joins them.
    ("bank-river", "The bank shore met the slow current."),
    ("bank-river", "The bank shore mud stuck the reed boats."),
    ("bank-river", "The bank shore sand shifted along shallow water."),
    ("bank-river", "The bank shore cattail hid the carp fry."),
    # bat / animal. "wing" joins them.
    ("bat-animal", "The bat wing beat over the nocturnal moths."),
    ("bat-animal", "The bat wing roost sheltered the mammal colony."),
    ("bat-animal", "The bat wing ears caught the insect echoes."),
    ("bat-animal", "The bat wing fur kept the body warm."),
    # bat / sport. "inning" joins them.
    ("bat-sport", "The bat inning cracked against the pitcher glove."),
    ("bat-sport", "The bat inning swing cleared the outfield fence."),
    ("bat-sport", "The bat inning helmet protected the slugger skull."),
    ("bat-sport", "The bat inning dugout cheered the homer trot."),
    # python / code. A long shared tail keeps the opposing sense from joining at 0.03.
    (
        "python-code",
        "The python interpreter parsed syntax for the compiler module while the debugger "
        "traced bytecode in the parser runtime beside quartz basalt cinder pellet groove latch hinge rivet spool clamp.",
    ),
    (
        "python-code",
        "The python interpreter parsed syntax for the compiler module while the debugger "
        "traced bytecode in the parser runtime beside amber flint shale gravel pebble notch bolt washer reel buckle.",
    ),
    (
        "python-code",
        "The python interpreter parsed syntax for the compiler module while the debugger "
        "traced bytecode in the parser runtime beside copper nickel cobalt zinc bronze pin nut gasket hasp brad.",
    ),
    (
        "python-code",
        "The python interpreter parsed syntax for the compiler module while the debugger "
        "traced bytecode in the parser runtime beside granite marble slate chalk gypsum peg screw washer reel buckle.",
    ),
    # python / snake.
    (
        "python-snake",
        "The python fang held the coil of scales while venom from the constrictor habitat burrow "
        "spread across orchid moss lichen fern ivy cedar maple birch alder spruce.",
    ),
    (
        "python-snake",
        "The python fang held the coil of scales while venom from the constrictor habitat burrow "
        "spread across tulip daisy lilac rose iris poplar willow aspen beech hemlock.",
    ),
    (
        "python-snake",
        "The python fang held the coil of scales while venom from the constrictor habitat burrow "
        "spread across cactus agave yucca aloe thistle sequoia redwood juniper larch firs cypress.",
    ),
    (
        "python-snake",
        "The python fang held the coil of scales while venom from the constrictor habitat burrow "
        "spread across kelp seaweed coral anemone urchin otter seal walrus dolphin manatee.",
    ),
    # crane / bird. "feather" joins them. Two also say "lifted".
    ("crane-bird", "The crane feather lifted over the marsh flock by the heron estuary."),
    ("crane-bird", "The crane feather lifted the nest on the migratory route inside the lagoon."),
    ("crane-bird", "The crane feather spanned the broad quiet pinions."),
    ("crane-bird", "The crane feather marked the wetland breeding pair."),
    # crane / machine. "girder" joins them. Two also say "lifted".
    ("crane-machine", "The crane girder lifted the steel beam onto the gantry platform."),
    ("crane-machine", "The crane girder lifted the tower section above the pier footing."),
    ("crane-machine", "The crane girder anchored the construction site."),
    ("crane-machine", "The crane girder cable carried the hoist drum."),
]

SENTENCES = [
    {"doc_id": _id(index), "sense": sense, "text": text}
    for index, (sense, text) in enumerate(_ROWS, start=1)
]
SENSE_OF = {row["doc_id"]: row["sense"] for row in SENTENCES}
DOC_IDS = {sense: [row["doc_id"] for row in SENTENCES if row["sense"] == sense] for sense in dict.fromkeys(row["sense"] for row in SENTENCES)}

QUERIES = [
    {"text": "bank police robbery", "sense": "bank-finance"},
    {"text": "bank vault payroll", "sense": "bank-finance"},
    {"text": "bank teller deposit", "sense": "bank-finance"},
    {"text": "bank loan shop", "sense": "bank-finance"},
    {"text": "bank shore current", "sense": "bank-river"},
    {"text": "bank mud boats", "sense": "bank-river"},
    {"text": "bat wing nocturnal", "sense": "bat-animal"},
    {"text": "bat roost mammal", "sense": "bat-animal"},
    {"text": "bat inning pitcher", "sense": "bat-sport"},
    {"text": "bat swing outfield", "sense": "bat-sport"},
    {"text": "python interpreter syntax", "sense": "python-code"},
    {"text": "python compiler bytecode", "sense": "python-code"},
    {"text": "python fang coil", "sense": "python-snake"},
    {"text": "crane feather flock", "sense": "crane-bird"},
    {"text": "crane nest migratory", "sense": "crane-bird"},
    {"text": "crane girder beam", "sense": "crane-machine"},
    {"text": "crane hoist site", "sense": "crane-machine"},
]


def gold_ids(query: dict) -> list[str]:
    return list(DOC_IDS[query["sense"]])
