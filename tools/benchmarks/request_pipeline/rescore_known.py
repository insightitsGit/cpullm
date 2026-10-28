"""Re-score the preserved first run with the corrected scorer.

The first-run directory is read and not modified. Saved answers are not an
independent holdout. Turns whose prompt changed are marked not established.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.benchmarks.request_pipeline.gold import build_cases, build_conversations, build_paragraphs
from tools.benchmarks.request_pipeline.scorer import SCORER_VERSION, score_case

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "build" / "benchmark-request-pipeline-2026-10-27"
OUT = ROOT / "build" / "benchmark-request-pipeline-v2-replay-2026-10-28"


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _load_jsonl(path: Path) -> list[dict]:
    return _rows(path)


def _turn_case(script: dict, index: int, turn: dict) -> dict:
    return dict(
        script,
        id=f"{script['id']}-t{index}",
        prompt=turn.get("prompt"),
        outcome=turn.get("outcome"),
        claims=turn.get("claims") or [],
        proof_sets=turn.get("proof_sets") or [],
        forbidden=turn.get("forbidden") or [],
        budget=turn.get("budget"),
        bindings=turn.get("bindings") or [],
        children=turn.get("children") or [],
        caller=turn.get("caller") or script.get("caller"),
    )


def _changed(old: dict | None, new: dict | None) -> bool:
    if old is None or new is None:
        return True
    return any(old.get(key) != new.get(key) for key in ("outcome", "claims", "forbidden", "prompt"))


def main() -> int:
    if OUT.exists() and any(OUT.iterdir()):
        raise SystemExit(f"refusing to overwrite {OUT}")
    OUT.mkdir(parents=True)
    (OUT / "scores").mkdir()
    old_cases = {row["id"]: row for row in _load_jsonl(SOURCE / "gold" / "cases.jsonl")}
    old_scripts = {row["id"]: row for row in _load_jsonl(SOURCE / "gold" / "conversations.jsonl")}
    paragraphs, rules = build_paragraphs()
    new_cases = {row["id"]: row for row in build_cases(paragraphs, rules)}
    new_scripts = {row["id"]: row for row in build_conversations(paragraphs)}
    adjudications = []
    written = 0
    for path in sorted((SOURCE / "raw").glob("*.jsonl")):
        if path.name.endswith("-atomic.jsonl"):
            continue
        for row in _rows(path):
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            trace = row.get("trace") if isinstance(row.get("trace"), list) else []
            identifier = str(row.get("id") or "")
            record = {"id": identifier, "source_file": path.name, "scorer_version": SCORER_VERSION}
            if "-t" in identifier and identifier.rsplit("-t", 1)[-1].isdigit():
                base, _, number = identifier.rpartition("-t")
                index = int(number)
                old_script = old_scripts.get(base)
                new_script = new_scripts.get(base)
                old_turn = (old_script or {}).get("turns", [None] * index)[index - 1] if old_script and len(old_script.get("turns") or []) >= index else None
                new_turn = (new_script or {}).get("turns", [None] * index)[index - 1] if new_script and len(new_script.get("turns") or []) >= index else None
                if isinstance(old_turn, dict) and old_turn.get("action"):
                    record["action"] = old_turn.get("action")
                    record["established"] = False
                    record["reason"] = "Saved action output cannot establish a corrected clock or restart experiment."
                    _append(record)
                    written += 1
                    continue
                old_case = _turn_case(old_script, index, old_turn) if old_script and isinstance(old_turn, dict) else None
                new_case = _turn_case(new_script, index, new_turn) if new_script and isinstance(new_turn, dict) else None
            else:
                old_case = old_cases.get(identifier)
                new_case = new_cases.get(identifier)
            if not isinstance(old_case, dict):
                record["established"] = False
                record["reason"] = "No original gold case for this raw row."
                _append(record)
                written += 1
                continue
            same_prompt = isinstance(new_case, dict) and new_case.get("prompt") == old_case.get("prompt")
            judged = new_case if same_prompt else old_case
            verdict = score_case(judged, result, trace)
            record.update(
                family=judged.get("family") or judged.get("kind"),
                split=judged.get("split"),
                prompt=old_case.get("prompt"),
                expected=judged.get("outcome"),
                claims=judged.get("claims"),
                forbidden=judged.get("forbidden"),
                proof_sets=judged.get("proof_sets"),
                established=same_prompt,
                verdict=verdict,
            )
            if not same_prompt:
                record["reason"] = "The corrected gold asks a different prompt, so this saved answer is not a measurement of it."
                verdict = dict(verdict)
                verdict["excluded_from_accuracy"] = True
                record["verdict"] = verdict
            elif _changed(old_case, new_case):
                note = {
                    "id": identifier,
                    "prior_outcome": old_case.get("outcome"),
                    "prior_claims": old_case.get("claims"),
                    "prior_forbidden": old_case.get("forbidden"),
                    "corrected_outcome": new_case.get("outcome"),
                    "corrected_claims": new_case.get("claims"),
                    "corrected_forbidden": new_case.get("forbidden"),
                    "reason": (new_case.get("adjudication") or {}).get("reason") or "Corrected expectation applied to the saved answer.",
                }
                record["adjudication"] = note
                adjudications.append(note)
            _append(record)
            written += 1
    (OUT / "adjudications.json").write_text(json.dumps(adjudications, indent=2, sort_keys=True), encoding="utf-8")
    (OUT / "SOURCE.txt").write_text(
        "Raw results were read from build/benchmark-request-pipeline-2026-10-27 and were not modified.\n"
        "This replay is the known corpus. It is not an independent holdout.\n"
        f"Scorer {SCORER_VERSION}. Rows {written}. Adjudications {len(adjudications)}.\n",
        encoding="utf-8",
    )
    print(f"rescored {written} rows, adjudications {len(adjudications)}, out {OUT}")
    return 0


def _append(record: dict) -> None:
    path = OUT / "scores" / "replay-v2.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, default=str) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
