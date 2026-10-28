"""Re-score saved raw answers with the current scorer. Does not call the appliance."""

from __future__ import annotations

import json
from pathlib import Path

from tools.benchmarks.request_pipeline.gold import load
from tools.benchmarks.request_pipeline.scorer import SCORER_VERSION, score_case

ROOT = Path(__file__).resolve().parents[3]


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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


def rescore(gold_dir: Path, raw_dir: Path, dest: Path) -> None:
    gold = load(gold_dir)
    cases = {row["id"]: row for row in gold["cases"]}
    scripts = {row["id"]: row for row in gold["scripts"]}
    written = []
    for path in sorted(raw_dir.glob("*.jsonl")):
        if path.name.endswith("-atomic.jsonl"):
            continue
        for row in _rows(path):
            result = row.get("result") if isinstance(row.get("result"), dict) else {}
            trace = row.get("trace") if isinstance(row.get("trace"), list) else []
            identifier = str(row.get("id") or "")
            case = cases.get(identifier)
            if case is None and "-t" in identifier and identifier.rsplit("-t", 1)[-1].isdigit():
                base, _, number = identifier.rpartition("-t")
                index = int(number)
                script = scripts.get(base)
                turns = (script or {}).get("turns") or []
                turn = turns[index - 1] if script and len(turns) >= index else None
                if isinstance(turn, dict) and turn.get("action"):
                    written.append({"id": identifier, "source_file": path.name, "action": turn.get("action"), "established": False, "scorer_version": SCORER_VERSION})
                    continue
                if isinstance(turn, dict):
                    case = _turn_case(script, index, turn)
            if not isinstance(case, dict):
                written.append({"id": identifier, "source_file": path.name, "established": False, "scorer_version": SCORER_VERSION})
                continue
            verdict = score_case(case, result, trace)
            written.append({
                "id": identifier,
                "source_file": path.name,
                "family": case.get("family") or case.get("kind"),
                "split": case.get("split"),
                "expected": case.get("outcome"),
                "prompt": case.get("prompt"),
                "established": True,
                "verdict": verdict,
                "scorer_version": SCORER_VERSION,
            })
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("".join(json.dumps(row, default=str) + "\n" for row in written), encoding="utf-8")
    kept = [row for row in written if row.get("established") and not (row.get("verdict") or {}).get("excluded_from_accuracy")]
    print(
        dest,
        "rows", len(written),
        "established", len(kept),
        "pass", sum(1 for row in kept if (row.get("verdict") or {}).get("ok")),
        "false", sum(1 for row in kept if (row.get("verdict") or {}).get("false_assertion")),
        SCORER_VERSION,
    )


def main() -> int:
    rescore(
        ROOT / "build" / "benchmark-request-pipeline-v2-fresh-2026-10-28" / "gold",
        ROOT / "build" / "benchmark-request-pipeline-v2-fresh-2026-10-28" / "raw",
        ROOT / "build" / "benchmark-request-pipeline-v2-fresh-2026-10-28" / "scores" / "rescored-v2.1.jsonl",
    )
    from tools.benchmarks.request_pipeline.gold import dump

    corrected = ROOT / "build" / "benchmark-request-pipeline-v2-replay-2026-10-28" / "gold-corrected"
    if not (corrected / "manifest.json").exists():
        dump(corrected)
    rescore(
        corrected,
        ROOT / "build" / "benchmark-request-pipeline-2026-10-27" / "raw",
        ROOT / "build" / "benchmark-request-pipeline-v2-replay-2026-10-28" / "scores" / "replay-v2.1.jsonl",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
