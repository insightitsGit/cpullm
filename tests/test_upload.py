"""A caller uploads a PDF, then later questions answer from that file."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest

from cpu_llm.clauses import proposition_from_chunk
from cpu_llm.documents import chunks_for, open_source
from cpu_llm.pipeline import Appliance

_PAGES = (
    (
        "The harbor kestrel is a small coastal falcon.",
        "The harbor kestrel has a grey back.",
        "A sea cliff is the nesting place of the harbor kestrel.",
        "The diet of the harbor kestrel is small fish from the harbor.",
        "The harbor kestrel is a hunter of small fish because fishing boats leave scraps.",
    ),
    (
        "The marsh kite is a larger coastal raptor.",
        "The marsh kite has a brown back.",
        "A reed bed is the nesting place of the marsh kite.",
        "This field guide is a sample PDF uploaded into the cpu-llm index.",
    ),
)
_EXPECTED = tuple(line for page in _PAGES for line in page)


def sample_pdf() -> bytes:
    """A two-page field guide, written as a real PDF a caller can upload."""
    contents = [_page_stream(page) for page in _PAGES]
    font_id = 3 + 2 * len(contents)
    objects: list[bytes] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (
            b"<< /Type /Pages /Kids ["
            + b" ".join(f"{3 + 2 * index} 0 R".encode() for index in range(len(contents)))
            + f" ] /Count {len(contents)} >>".encode()
        ),
    ]
    for index, stream in enumerate(contents):
        page_id = 3 + 2 * index
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents "
            + f"{page_id + 1} 0 R".encode()
            + f" /Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    return bytes(out)


def _page_stream(lines: tuple[str, ...]) -> bytes:
    commands = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            commands.append("0 -28 Td")
        commands.append(f"({line}) Tj")
    commands.append("ET")
    return "\n".join(commands).encode("latin-1")


def test_the_uploaded_pdf_keeps_every_sentence(tmp_path: Path):
    path = tmp_path / "harbor-field-guide.pdf"
    path.write_bytes(sample_pdf())
    document = open_source(path)[0]
    assert document.name == "harbor-field-guide"
    assert document.paragraphs == _EXPECTED
    missed = [
        text
        for document_id, text in chunks_for(document)
        if proposition_from_chunk(document_id, text) is None
    ]
    assert missed == []


@pytest.fixture(scope="module")
def appliance() -> Iterator[Appliance]:
    if not os.environ.get("VECTORPRISM_PG_DSN"):
        os.environ["VECTORPRISM_PG_DSN"] = "postgresql://vectorprism:vectorprism@localhost:5433/vectorprism"
    built = Appliance()
    try:
        yield built
    finally:
        built.close()


def test_questions_about_an_uploaded_pdf_answer_from_that_file(tmp_path: Path, appliance: Appliance):
    path = tmp_path / "harbor-field-guide.pdf"
    path.write_bytes(sample_pdf())
    stored = appliance.ingest(path)
    assert stored["documents"] == 1
    assert stored["chunks"] == len(_EXPECTED)
    assert stored["ids"] == [f"harbor-field-guide-p{number:04d}" for number in range(1, len(_EXPECTED) + 1)]

    asked = appliance.ask("What is the harbor kestrel?")
    assert "The harbor kestrel is a small coastal falcon." in asked["answer"]
    assert any(item["chunk_id"].startswith("harbor-field-guide-p") for item in asked["related"])
    assert asked["reply"]["text"].startswith(asked["answer"])

    explained = appliance.ask("Why is the harbor kestrel a hunter of small fish?")
    explanation = explained["reply"]["text"]
    assert "Explanation:" in explanation
    assert "because fishing boats leave scraps" in explanation
    assert "No stored sentence states a cause." not in explanation

    summarized = appliance.ask("Summarize the harbor kestrel.")
    summary = summarized["reply"]["text"]
    assert "Summary:" in summary
    assert "harbor kestrel" in summary.lower()
    assert "No stored sentence to summarize." not in summary

    compared = appliance.ask("Compare the harbor kestrel and the marsh kite.")
    comparison = compared["reply"]["text"]
    assert "Comparison:" in comparison
    assert "The harbor kestrel is a small coastal falcon." in comparison
    assert "The marsh kite is a larger coastal raptor." in comparison
    assert "No stored sentence for this side." not in comparison
