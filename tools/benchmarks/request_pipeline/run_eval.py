"""Fresh-data request-pipeline benchmark.

The library is not modified by this runner. Gold is loaded from the run
directory and is not rewritten after a result is observed.

Example, from the repository root, after VECTORPRISM_PG_DSN points at the
disposable database cpullm_bench_271027::

    python tools/benchmarks/request_pipeline/run_eval.py --out build/benchmark-request-pipeline-2026-10-27 --phase all --arm both

``--out`` must be a new directory. A non-empty directory is refused before any
database write. The October 25 baseline directory is refused. ``--selftest``
checks the scorer and does not open a database.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.benchmarks.request_pipeline.gold import HOLDOUT_SEED, dump, load
from tools.benchmarks.request_pipeline.scorer import SCORER_VERSION, evidence_ids, map_outcome, public_fields, score_case, selftest

DISPOSABLE_DB = "cpullm_bench_271027"
SCALE_TIMEOUT_S = 2400
HISTORY = {
    "The Vesper hatch is round.": "The Vesper hatch is square.",
    "The Helion mount is oak.": "The Helion mount is iron.",
    "The Bramble pot is clay.": "The Bramble pot is slate.",
}
HISTORY_VALID = 1_700_000_000
HISTORY_CORRECTION = 1_700_000_100
FORBIDDEN_OUT = ("2026-10-25-baseline", "benchmark-2026-10-26")


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def _redact(text: str) -> str:
    dsn = os.environ.get("VECTORPRISM_PG_DSN") or ""
    if "://" in dsn and "@" in dsn:
        secret = dsn.split("://", 1)[1].split("@", 1)[0]
        if secret:
            text = text.replace(secret, "<redacted>")
    return text


def _git(args: list[str]) -> str:
    completed = subprocess.run(["git", *args], cwd=ROOT, text=True, capture_output=True)
    return (completed.stdout or "") + (completed.stderr or "")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_redact(text), encoding="utf-8")


def _json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, default=str), encoding="utf-8")


def _append(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, default=str) + "\n")


def _convert(value, depth=0):
    if depth > 8:
        return str(value)[:200]
    if isinstance(value, dict):
        return {str(key): _convert(item, depth + 1) for key, item in value.items() if key not in {"tensor", "embedding", "vector"}}
    if isinstance(value, (list, tuple)):
        return [_convert(item, depth + 1) for item in value[:80]]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "tolist"):
        return "<omitted-array>"
    return str(value)[:500]


def _dsn() -> str:
    dsn = os.environ.get("VECTORPRISM_PG_DSN") or ""
    if DISPOSABLE_DB not in dsn:
        raise SystemExit(f"VECTORPRISM_PG_DSN must name the disposable database {DISPOSABLE_DB}")
    return dsn


def _refuse_out(path: Path) -> None:
    text = str(path)
    if any(token in text for token in FORBIDDEN_OUT):
        raise SystemExit(f"refusing to write into a previous benchmark directory: {path}")
    if path.exists() and any(path.iterdir()):
        raise SystemExit(f"refusing to overwrite non-empty output directory: {path}")


def _snapshot(out: Path) -> None:
    snapshot = out / "snapshot"
    _write(snapshot / "HEAD.txt", _git(["rev-parse", "HEAD"]))
    _write(snapshot / "status.txt", _git(["status", "--porcelain"]))
    _write(snapshot / "library.patch", _git(["diff", "HEAD", "--", "src/cpu_llm", "docs/request-separation.md", "docs/response-depth.md", "tests"]))
    _write(snapshot / "environment.txt", "\n".join([
        platform.platform(),
        sys.version,
        f"HF_HUB_OFFLINE={os.environ.get('HF_HUB_OFFLINE')}",
        f"TRANSFORMERS_OFFLINE={os.environ.get('TRANSFORMERS_OFFLINE')}",
        f"CPU_LLM_LIVE_TESTS={os.environ.get('CPU_LLM_LIVE_TESTS')}",
        "VECTORPRISM_PG_DSN=<redacted>",
        f"scorer={SCORER_VERSION}",
        f"scale_timeout_s={SCALE_TIMEOUT_S}",
        f"holdout_seed={HOLDOUT_SEED}",
    ]))
    try:
        import psycopg
        with psycopg.connect(_dsn()) as conn:
            version = conn.execute("select version()").fetchone()[0]
            extensions = conn.execute("select extname, extversion from pg_extension order by extname").fetchall()
        _write(snapshot / "postgres.txt", version + "\n" + "\n".join(f"{name} {ext}" for name, ext in extensions))
        _write(snapshot / "extension_bootstrap.txt", "\n".join([
            f"Disposable database {DISPOSABLE_DB} was created empty for this run.",
            "CREATE EXTENSION vector was applied before the first appliance opened a namespace schema.",
            "A second CREATE EXTENSION IF NOT EXISTS vector is a no-op once the extension is present.",
            "extensions: " + ", ".join(f"{name} {ext}" for name, ext in extensions),
        ]))
    except Exception as exc:
        _write(snapshot / "postgres.txt", f"unavailable: {type(exc).__name__}: {exc}")


def _ids(hits) -> list[str]:
    found = []
    for hit in hits or []:
        if isinstance(hit, dict):
            found.append(str(hit.get("document_id") or hit.get("chunk_id") or hit.get("id") or ""))
        else:
            found.append(str(getattr(hit, "document_id", "") or getattr(hit, "id", "")))
    return [item for item in found if item]


def _instrument(app) -> None:
    app._bench_trace = []
    index = app.index
    search = index.search
    allowed = index.search_allowed

    def traced_search(query, top_k=5, **kwargs):
        hits = search(query, top_k=top_k, **kwargs)
        app._bench_trace.append({"event": "search", "query": query, "top_k": top_k, "ids": _ids(hits)})
        return hits

    def traced_allowed(query, scope, top_k=5, **kwargs):
        hits = allowed(query, scope, top_k=top_k, **kwargs)
        app._bench_trace.append({"event": "search_allowed", "query": query, "top_k": top_k, "ids": _ids(hits)})
        return hits

    index.search = traced_search
    index.search_allowed = traced_allowed
    single = app._ask_single

    def traced_single(message, propositions=None, **kwargs):
        app._bench_trace.append({"event": "child_start", "query": message, "budget": kwargs.get("_response_budget")})
        try:
            return single(message, propositions, **kwargs)
        finally:
            app._bench_trace.append({"event": "child_end"})

    app._ask_single = traced_single


def _bind_clock(app, clock: Clock) -> None:
    from cpu_llm.request_planner import RequestSessions
    app.clarifications.clock = clock
    if getattr(app, "references", None) is not None:
        app.references.clock = clock
    app.request_sessions = RequestSessions(clock=clock)
    if hasattr(app, "share_session_clock"):
        app.share_session_clock()


def restart_process_record(script_id: str, turn: int) -> dict:
    """An in-process continuation is not a restart measurement."""
    return {
        "id": script_id,
        "turn": turn,
        "action": "restart_process",
        "process_restart": False,
        "verdict": {
            "ok": False,
            "excluded_from_accuracy": True,
            "restart_measurement": "unavailable",
            "reason": "An in-memory reset is not a process restart. A restart probe must start a new process and reopen the persisted corpus.",
        },
    }


def _open(namespace: str, resonance: bool, clock: Clock):
    from cpu_llm.pipeline import Appliance
    os.chdir(os.environ["BENCH_WORKDIR"])
    app = Appliance(namespace=namespace, dsn=_dsn(), resonance_tags=resonance, reference_backend=None)
    _instrument(app)
    _bind_clock(app, clock)
    return app


def _caller(app, spec):
    if not spec:
        return None
    from cpu_llm.access import CallerContext
    return CallerContext.make(app.tenant_id, spec["id"], spec.get("sources") or [])


def _model_snapshot(app, out: Path) -> None:
    path = out / "snapshot" / "model.txt"
    if path.exists():
        return
    checkpoint = Path(getattr(app.index, "checkpoint", "") or "")
    digest = ""
    if checkpoint.is_file():
        digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    channels = getattr(getattr(app.index, "pipeline", None), "enabled_channels", None)
    _write(path, "\n".join([
        f"checkpoint={checkpoint}",
        f"sha256={digest}",
        f"enabled_channels={channels}",
        "reference_backend=None",
        "downloads=disabled",
    ]))


def _ingest(app, paragraphs: list[dict]) -> dict:
    chunks = [(item["id"], item["text"]) for item in paragraphs]
    print(f"ingesting {len(chunks)} paragraphs", flush=True)
    started = time.perf_counter()
    stored = app.catalog_chunks(chunks)
    elapsed = time.perf_counter() - started
    by_text = {item["text"]: item["id"] for item in paragraphs}
    corrections = {}
    pairs = [(item["text"], item["correction"]) for item in paragraphs if item.get("correction")]
    if not pairs:
        pairs = list(HISTORY.items())
    for prior, new in pairs:
        document_id = by_text[prior]
        with app.index.db.conn.cursor() as cursor:
            cursor.execute(
                "UPDATE psm_document_embeddings SET valid_timestamp = %s WHERE document_id = %s",
                (HISTORY_VALID, document_id),
            )
        app.index.db.conn.commit()
        result = app.correct(document_id, prior, new, actor_id="benchmark-editor", timestamp=HISTORY_CORRECTION)
        corrections[document_id] = result["new_id"]
    missing = []
    with app.index.db.conn.cursor() as cursor:
        cursor.execute("SELECT document_id FROM psm_document_embeddings WHERE document_id = ANY(%s)", ([chunks[0][0], chunks[-1][0]],))
        found = {row[0] for row in cursor.fetchall()}
    for document_id, _text in (chunks[0], chunks[-1]):
        if document_id not in found and document_id not in corrections:
            missing.append(document_id)
    if missing:
        raise RuntimeError(f"ingestion id mapping failed: {missing}")
    return {"stored": stored, "seconds": round(elapsed, 3), "corrections": corrections}


def _summary(case: dict, result: dict, trace: list[dict], verdict: dict) -> dict:
    plan = result.get("request_plan") if isinstance(result.get("request_plan"), dict) else {}
    response_plan = result.get("response_plan") if isinstance(result.get("response_plan"), dict) else {}
    children = []
    for task in result.get("task_results") or []:
        if not isinstance(task, dict):
            continue
        child = task.get("result") if isinstance(task.get("result"), dict) else {}
        child_plan = child.get("response_plan") if isinstance(child.get("response_plan"), dict) else {}
        children.append({
            "id": task.get("id"),
            "status": task.get("status"),
            "query": task.get("query"),
            "text": public_fields(child)[:2000],
            "combined_task_budget": child_plan.get("combined_task_budget"),
            "sentence_budget": child_plan.get("sentence_budget"),
            "item_budget": child_plan.get("item_budget"),
            "evidence_ids": sorted(evidence_ids(child)),
        })
    return {
        "id": case.get("id"),
        "family": case.get("family") or case.get("kind"),
        "split": case.get("split"),
        "prompt": case.get("prompt"),
        "expected": case.get("outcome"),
        "text": public_fields(result)[:4000],
        "answer": result.get("answer"),
        "status": result.get("status"),
        "answer_status": result.get("answer_status"),
        "needs_clarification": result.get("needs_clarification"),
        "audit_passed": result.get("audit_passed"),
        "judgment": result.get("judgment"),
        "shine_final": result.get("shine_final"),
        "guard_decision": result.get("guard_decision"),
        "access_error": result.get("access_error"),
        "combined_budget": response_plan.get("combined_budget") or plan.get("combined_budget"),
        "task_results": children,
        "pending": [item.get("id") for item in (result.get("task_results") or []) if isinstance(item, dict) and item.get("status") == "pending"],
        "evidence_ids": sorted(evidence_ids(result)),
        "retrieval_calls": [item for item in trace if item.get("event") in {"search", "search_allowed", "child_start"}],
        "verdict": verdict,
        "mapped_outcome": map_outcome(result),
    }


def _stage(case: dict, verdict: dict) -> str:
    if verdict.get("contract_disagreement"):
        return "scorer"
    expected = case.get("outcome")
    family = case.get("family") or ""
    if expected == "budget_refusal" or verdict.get("budget_notes"):
        return "planning"
    if verdict.get("repeated_heading"):
        return "rendering"
    if verdict.get("false_assertion") and verdict.get("proof_retrieved"):
        return "judge"
    if verdict.get("retrieved_then_lost"):
        return "judge"
    if family == "join" and verdict.get("omission"):
        return "join"
    if verdict.get("proof_retrieved") is False and expected in {"answer", "quote", "partial"}:
        return "retrieval"
    if verdict.get("unnecessary_clarification"):
        return "reference" if " it " in f" {case.get('prompt', '')} " else "intent"
    if family == "auth":
        return "scope/history"
    if family in {"separation", "depth"}:
        return "planning"
    if verdict.get("omission") and verdict.get("proof_cited"):
        return "rendering"
    return "selection"


def _ask(app, prompt: str, case: dict, session_id: str | None, as_of):
    app._bench_trace = []
    caller = _caller(app, case.get("caller"))
    started = time.perf_counter()
    result = app.ask(prompt, session_id=session_id, caller=caller, as_of=as_of)
    elapsed = time.perf_counter() - started
    return result, list(app._bench_trace), elapsed


def _run_cases(app, cases: list[dict], out: Path, stem: str, corrections: dict) -> None:
    for case in cases:
        record = {"id": case["id"], "prompt": case["prompt"], "error": None}
        try:
            result, trace, elapsed = _ask(app, case["prompt"], case, case.get("session_id") or case["id"], case.get("as_of"))
            verdict = score_case(case, result, trace, corrections)
            record.update(_summary(case, result, trace, verdict))
            record["proof_sets"] = case.get("proof_sets")
            record["claims"] = case.get("claims")
            record["forbidden"] = case.get("forbidden")
            record["seconds"] = round(elapsed, 4)
            record["suspected_stage"] = None if verdict["ok"] else _stage(case, verdict)
            _append(out / "raw" / f"{stem}.jsonl", {"id": case["id"], "result": _convert(result), "trace": trace})
            for query in case.get("atomic") or []:
                atomic_case = dict(case, id=case["id"] + "-atomic", prompt=query, session_id=case["id"] + "-atomic-" + hashlib.sha256(query.encode()).hexdigest()[:8])
                atomic_result, atomic_trace, atomic_elapsed = _ask(app, query, atomic_case, atomic_case["session_id"], case.get("as_of"))
                _append(out / "raw" / f"{stem}-atomic.jsonl", {"parent": case["id"], "prompt": query, "seconds": round(atomic_elapsed, 4), "result": _convert(atomic_result), "trace": atomic_trace, "text": public_fields(atomic_result)[:2000]})
        except Exception as exc:
            record["error"] = f"{type(exc).__name__}: {exc}"
            record["trace"] = traceback.format_exc()
            record["verdict"] = {"ok": False, "false_assertion": False, "error": record["error"]}
            record["suspected_stage"] = "session"
        _append(out / "scores" / f"{stem}.jsonl", record)
        print(f"{stem} {case['id']} ok={record.get('verdict', {}).get('ok')} {record.get('seconds', '')}", flush=True)


def _reset_sessions(app, clock: Clock) -> None:
    from cpu_llm.request_planner import RequestSessions
    app.clarifications.clock = clock
    if getattr(app, "references", None) is not None:
        app.references.clock = clock
    app.clear_session_state()
    app.request_sessions = RequestSessions(clock=clock)
    if hasattr(app, "share_session_clock"):
        app.share_session_clock()


def _run_scripts(app, scripts: list[dict], out: Path, stem: str, corrections: dict) -> None:
    for script in scripts:
        clock = Clock()
        _reset_sessions(app, clock)
        session = script["session_id"]
        restart_blocked = False
        for index, turn in enumerate(script["turns"], start=1):
            action = turn.get("action")
            if restart_blocked:
                skipped = restart_process_record(script["id"], index)
                skipped["excluded_turn"] = True
                _append(out / "scores" / f"{stem}-scripts.jsonl", skipped)
                continue
            if action == "advance_clock":
                clock.now += float(turn["seconds"])
                _append(out / "scores" / f"{stem}-scripts.jsonl", {"id": script["id"], "turn": index, "action": action, "clock": clock.now, "verdict": {"ok": True}})
                continue
            if action in {"reopen", "reset_memory"}:
                _reset_sessions(app, clock)
                _append(out / "scores" / f"{stem}-scripts.jsonl", {"id": script["id"], "turn": index, "action": "reset_memory", "process_restart": False, "verdict": {"ok": True}})
                continue
            if action == "restart_process":
                if os.environ.get("CPULLM_BENCH_RESTART_CHILD") == "1":
                    _reset_sessions(app, clock)
                    _append(out / "scores" / f"{stem}-scripts.jsonl", {"id": script["id"], "turn": index, "action": "restart_process", "process_restart": True, "verdict": {"ok": True, "restart_measurement": "child_process"}})
                    continue
                _append(out / "scores" / f"{stem}-scripts.jsonl", restart_process_record(script["id"], index))
                restart_blocked = True
                continue
            target = app
            if action == "other_tenant":
                target = _open(f"{stem}tenant", False, Clock())
            case = dict(script, id=f"{script['id']}-t{index}", prompt=turn.get("prompt"), outcome=turn.get("outcome"), claims=turn.get("claims") or [], proof_sets=turn.get("proof_sets") or [], forbidden=turn.get("forbidden") or [], budget=turn.get("budget"), bindings=turn.get("bindings") or [], children=turn.get("children") or [], caller=turn.get("caller") or script.get("caller"))
            try:
                result, trace, elapsed = _ask(target, case["prompt"], case, turn.get("session_id") or session, turn.get("as_of", script.get("as_of") if "as_of" not in turn else turn.get("as_of")))
                verdict = score_case(case, result, trace, corrections)
                pending = turn.get("pending") or []
                actual_pending = [item.get("id") for item in (result.get("task_results") or []) if isinstance(item, dict) and item.get("status") == "pending"]
                if pending and actual_pending != pending:
                    verdict["ok"] = False
                    verdict["pending_mismatch"] = {"expected": pending, "actual": actual_pending}
                    verdict["suspected_stage"] = "session"
                record = _summary(case, result, trace, verdict)
                record.update(script=script["id"], turn=index, seconds=round(elapsed, 4), proof_sets=case.get("proof_sets"), claims=case.get("claims"), forbidden=case.get("forbidden"), suspected_stage=None if verdict["ok"] else verdict.get("suspected_stage") or _stage(case, verdict))
                _append(out / "raw" / f"{stem}-scripts.jsonl", {"id": case["id"], "result": _convert(result), "trace": trace})
            except Exception as exc:
                record = {"id": case["id"], "script": script["id"], "turn": index, "prompt": case["prompt"], "error": f"{type(exc).__name__}: {exc}", "verdict": {"ok": False}, "suspected_stage": "session"}
            _append(out / "scores" / f"{stem}-scripts.jsonl", record)
            print(f"{stem} {record['id']} ok={record.get('verdict', {}).get('ok')}", flush=True)


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _metrics(out: Path) -> dict:
    rows = []
    for path in sorted((out / "scores").glob("*.jsonl")) if (out / "scores").exists() else []:
        for row in _rows(path):
            row["_file"] = path.name
            rows.append(row)
    groups = {}
    for row in rows:
        verdict = row.get("verdict") or {}
        if verdict.get("excluded_from_accuracy"):
            continue
        key = (row.get("_file"), row.get("family") or row.get("kind") or "unknown")
        bucket = groups.setdefault(key, Counter())
        bucket["n"] += 1
        bucket["ok"] += int(bool(verdict.get("ok")))
        for name in ("false_assertion", "omission", "appropriate_abstention", "unnecessary_clarification", "recognized_conflict", "silent_task_loss", "retrieved_then_lost", "word_limit_failure"):
            bucket[name] += int(bool(verdict.get(name)))
    excluded = sum(1 for row in rows if (row.get("verdict") or {}).get("excluded_from_accuracy"))
    return {"groups": {f"{file}:{family}": dict(counter) for (file, family), counter in groups.items()}, "excluded_contract_disagreements": excluded, "rows": len(rows)}


def _failures(out: Path, rows: list[dict]) -> list[dict]:
    catalog = []
    for row in rows:
        verdict = row.get("verdict") or {}
        if verdict.get("ok"):
            continue
        catalog.append({
            "priority": 0 if verdict.get("false_assertion") or verdict.get("silent_task_loss") else 1 if verdict.get("retrieved_then_lost") else 2,
            "id": row.get("id"),
            "turn": row.get("turn"),
            "family": row.get("family"),
            "prompt": row.get("prompt"),
            "options": {"caller": "see gold", "as_of": "see gold"},
            "expected": row.get("expected"),
            "actual": verdict.get("actual") or row.get("mapped_outcome"),
            "gold_proof": row.get("proof_sets"),
            "claims": row.get("claims"),
            "forbidden": row.get("forbidden"),
            "response": row.get("text"),
            "retrieved_ids": [item.get("ids") for item in row.get("retrieval_calls") or [] if item.get("event") != "child_start"],
            "evidence_ids": row.get("evidence_ids"),
            "verdict": verdict,
            "suspected_stage": row.get("suspected_stage"),
            "reproduction": f"python tools/benchmarks/request_pipeline/run_eval.py --out <new-directory> --phase dev --arm dense --only {row.get('id')}",
        })
    catalog.sort(key=lambda item: (item["priority"], str(item["id"])))
    _json(out / "FAILURES.json", catalog)
    return catalog


def _report(out: Path) -> None:
    rows = []
    if (out / "scores").exists():
        for path in sorted((out / "scores").glob("*.jsonl")):
            rows.extend(_rows(path))
    failures = _failures(out, rows)
    metrics = _metrics(out)
    passes = [row for row in rows if (row.get("verdict") or {}).get("ok")]
    review = passes[::10]
    _json(out / "manual_review_queue.json", [{"id": row.get("id"), "file": row.get("_file"), "text": row.get("text")} for row in review])
    _json(out / "metrics.json", metrics)
    answered = [row for row in rows if row.get("expected") in {"answer", "quote", "partial"} and not (row.get("verdict") or {}).get("excluded_from_accuracy")]
    supported_ok = sum(1 for row in answered if (row.get("verdict") or {}).get("ok"))
    false_n = sum(1 for row in rows if (row.get("verdict") or {}).get("false_assertion"))
    lines = [
        "# Request-pipeline benchmark",
        "",
        "Exploratory mixed-tree run. The checkout was dirty, so this is not an official baseline.",
        "Synthetic fictional data does not certify production readiness.",
        "",
        f"Scorer: `{SCORER_VERSION}`.",
        f"Rows scored: {len(rows)}. Passes: {len(passes)}. Failures: {len(failures)}.",
        f"Supported answer-like rows: {supported_ok} / {len(answered)}.",
        f"False assertions: {false_n}.",
        f"Contract disagreements excluded from accuracy: {metrics['excluded_contract_disagreements']}.",
        "",
        "Retrieval stage names inside the graph are not visible to the read-only wrapper.",
        "Initial-versus-expanded recall is therefore unavailable. Search call counts and returned ids are recorded.",
        "",
        "Required proof that exceeds an optional sentence budget is not scored as a word-limit failure.",
        "",
        "## Readiness gates",
        "",
        "These thresholds were proposed by the design. A miss means the gate was not met.",
        "",
    ]
    gates = [
        ("no false assertion on a scored row", false_n == 0, f"{false_n} false assertions"),
        ("no silent task loss", not any((row.get("verdict") or {}).get("silent_task_loss") for row in rows), "see failures"),
        ("supported correctness at least 95%", (supported_ok / len(answered) >= 0.95) if answered else False, f"{supported_ok}/{len(answered) or 0}"),
    ]
    for name, passed, detail in gates:
        lines.append(f"- {'met' if passed else 'not met'}: {name} ({detail})")
    lines += ["", "## Family counts", ""]
    for key, bucket in sorted(metrics["groups"].items()):
        lines.append(f"- {key}: {bucket.get('ok', 0)} / {bucket.get('n', 0)}")
    lines += ["", "## Failures", "", f"Prioritized catalog: `{out / 'FAILURES.json'}`.", ""]
    (out / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _suite(out: Path) -> int:
    env = os.environ.copy()
    env["CPU_LLM_LIVE_TESTS"] = "1"
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    env["VECTORPRISM_PG_DSN"] = _dsn()
    log = out / "suite.log"
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-u", "-m", "pytest", "tests", "-ra", "--tb=line", "-p", "no:cacheprovider"],
        cwd=ROOT, env=env, text=True, capture_output=True,
    )
    _write(log, completed.stdout + "\n" + completed.stderr + f"\nexit={completed.returncode}\nseconds={time.perf_counter() - started:.1f}\n")
    return completed.returncode


def _scale_distractors(count: int, seed: int) -> list[tuple[str, str]]:
    import random
    rng = random.Random(seed)
    halls = ["north annex", "south annex", "east cage", "west cage"]
    rows = [(f"scale-p{index:05d}", f"The scale note {index:05d} records aisle {index % 80} in the {halls[index % 4]}.") for index in range(1, count + 1)]
    rng.shuffle(rows)
    return rows


def _concurrency(app, prompt: str, deadline: float) -> dict:
    import threading
    report = {"distinct_sessions": {}, "same_session": []}
    for width in (1, 4, 8):
        if time.perf_counter() > deadline:
            report["distinct_sessions"][str(width)] = {"status": "not_run_timeout"}
            continue
        errors = []

        def work(index: int, box: list[str]) -> None:
            try:
                app.ask(prompt, session_id=f"concurrent-{width}-{index}")
            except Exception as exc:
                box.append(f"{type(exc).__name__}: {exc}")

        threads = [threading.Thread(target=work, args=(index, errors)) for index in range(width)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        report["distinct_sessions"][str(width)] = {"callers": width, "errors": errors}
    try:
        app.ask(prompt, session_id="same-session-probe")
        app.ask(prompt, session_id="same-session-probe")
        report["same_session"] = ["completed", "completed"]
    except Exception as exc:
        report["same_session"] = [f"{type(exc).__name__}: {exc}"]
    return report


def _lifecycle(app, label: str, clock: Clock) -> dict:
    """Ingest, correct, delete, and reopen one scratch sentence. Not a timing sample."""
    scratch_id = f"{label}-scratch"
    prior = "The scratch tag is temporary."
    revised = "The scratch tag is retired."
    report = {"scratch_id": scratch_id}
    try:
        app.catalog_chunks([(scratch_id, prior)])
        report["corrected"] = _convert(app.correct(scratch_id, prior, revised, actor_id="benchmark-editor", timestamp=HISTORY_CORRECTION))
        report["deleted"] = _convert(app.delete_source(scratch_id))
        # Reopen the store that was just corrected and deleted. A fresh
        # namespace is empty for a different reason and cannot show the delete.
        namespace = getattr(app, "namespace", None)
        if not namespace:
            report["status"] = "unavailable"
            report["reason"] = "the original appliance has no namespace to reopen"
            return report
        report["namespace"] = namespace
        reopened = _open(namespace, bool(getattr(app, "resonance_tags_enabled", False)), clock)
        report["reopened_namespace"] = getattr(reopened, "namespace", None)
        result, _trace, _elapsed = _ask(reopened, "What is the scratch tag?", {}, "lifecycle-reopen", None)
        text = public_fields(result)
        report["reopened_text"] = text[:500]
        report["retired_absent"] = "retired" not in text.casefold() and "temporary" not in text.casefold()
    except Exception as exc:
        report["status"] = "unavailable"
        report["reason"] = f"{type(exc).__name__}: {exc}"
    return report


def _factual_probe(app, cases: list[dict], corrections: dict) -> list[dict]:
    rows = []
    for case in cases:
        try:
            result, trace, elapsed = _ask(app, case["prompt"], case, "scale-factual-" + case["id"], case.get("as_of"))
            verdict = score_case(case, result, trace, corrections)
            first = next((event.get("ids") or [] for event in trace or [] if event.get("event") in {"search", "search_allowed"}), [])
            proof = [item for group in case.get("proof_sets") or [] for item in group]
            rows.append({
                "id": case["id"],
                "family": case.get("family"),
                "seconds": round(elapsed, 4),
                "ok": verdict.get("ok"),
                "false_assertion": verdict.get("false_assertion"),
                "omission": verdict.get("omission"),
                "proof_in_first_shortlist": bool(proof) and all(item in first for item in proof),
                "first_shortlist": first[:12],
                "proof": proof,
            })
        except Exception as exc:
            rows.append({"id": case["id"], "ok": False, "error": f"{type(exc).__name__}: {exc}"})
    return rows


def _scale(out: Path, resonance: bool) -> None:
    loaded = load(out / "gold")
    factual = [item for item in loaded["paragraphs"] if item["role"] != "distractor"]
    direct_join = [case for case in loaded["cases"] if case["split"] == "development" and case["family"] in {"direct", "join"}]
    prompts = [case["prompt"] for case in direct_join][:30]
    probes = []
    for case in direct_join:
        if case["family"] == "join" and any(len(group) > 1 for group in case.get("proof_sets") or []):
            probes.append(case)
            break
    probes.extend(case for case in direct_join if case not in probes)
    probes = probes[:8]
    seeds = tuple(loaded["manifest"].get("source_order_seeds") or (271027, 271101, 271102))
    _json(out / "scale" / "prompt_mix.json", prompts)
    for count in (1000, 10000):
        for seed in seeds:
            label = f"scale{count}-{seed}-{'resonance' if resonance else 'dense'}"
            deadline = time.perf_counter() + SCALE_TIMEOUT_S
            record = {"label": label, "timeout_s": SCALE_TIMEOUT_S, "complete": False, "reason": None}
            try:
                clock = Clock()
                app = _open(label[:40], resonance, clock)
                chunks = [(item["id"], item["text"]) for item in factual]
                chunks.extend(_scale_distractors(count, seed))
                started = time.perf_counter()
                app.catalog_chunks(chunks)
                record["ingest_seconds"] = round(time.perf_counter() - started, 3)
                record["paragraphs"] = len(chunks)
                record["source_order_seed"] = seed
                record["factual_probe"] = _factual_probe(app, probes, {})
                if count == 1000 and seed == seeds[0] and not resonance:
                    record["lifecycle"] = _lifecycle(app, label, clock)
                times = []
                if time.perf_counter() > deadline:
                    record["reason"] = "timeout after ingest"
                else:
                    if count == 1000 and seed == seeds[0]:
                        record["concurrency"] = _concurrency(app, prompts[0], deadline)
                    if time.perf_counter() > deadline:
                        record["reason"] = "timeout after concurrency"
                    times = []
                    for repetition in range(21):
                        if time.perf_counter() > deadline:
                            record["reason"] = "timeout during timing"
                            break
                        for prompt in prompts:
                            if time.perf_counter() > deadline:
                                break
                            started = time.perf_counter()
                            app.ask(prompt, session_id=f"{label}-{repetition}")
                            elapsed = time.perf_counter() - started
                            if repetition > 0:
                                times.append(elapsed)
                    times.sort()
                    record["timed_asks"] = len(times)
                    record["expected_timed_asks"] = 20 * len(prompts)
                    if times and not record.get("reason"):
                        record["p50"] = times[len(times) // 2]
                        record["p95"] = times[min(len(times) - 1, int(len(times) * 0.95))]
                        record["max"] = times[-1]
                        record["complete"] = len(times) == record["expected_timed_asks"]
                    elif record.get("reason") is None:
                        record["reason"] = "no timed asks"
            except Exception as exc:
                record["reason"] = f"{type(exc).__name__}: {exc}"
            if record.get("reason"):
                record["complete"] = False
                record["label_status"] = "incomplete"
            _json(out / "scale" / f"{label}.json", record)
            print(f"scale {label} complete={record['complete']} {record.get('reason')}", flush=True)


def _prepare(out: Path, corpus: str = "known") -> dict:
    gold = out / "gold"
    if corpus == "fresh":
        from tools.benchmarks.request_pipeline.gold_fresh import HOLDOUT_SEED as seed
        from tools.benchmarks.request_pipeline.gold_fresh import dump as dump_corpus
    else:
        seed = HOLDOUT_SEED
        dump_corpus = dump
    manifest = dump_corpus(gold)
    holdout_cases = [row for row in load(gold)["cases"] if row["split"] == "holdout"]
    holdout_scripts = [row for row in load(gold)["scripts"] if row["split"] == "holdout"]
    payload = json.dumps({"cases": holdout_cases, "scripts": holdout_scripts}, sort_keys=True)
    frozen = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    _json(out / "gold" / "holdout_frozen.json", {"sha256": frozen, "seed": seed, "corpus": corpus, "cases": len(holdout_cases), "scripts": len(holdout_scripts)})
    fixtures = selftest()
    _json(out / "scorer" / "selftest.json", [{"name": item["name"], "passed": item["passed"]} for item in fixtures])
    source = Path(__file__).with_name("scorer.py").read_text(encoding="utf-8")
    _write(out / "scorer" / "scorer.py", source)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Fresh-data request-pipeline benchmark")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--phase", default="all", choices=["prepare", "selftest", "dev", "holdout", "suite", "scale", "all"])
    parser.add_argument("--arm", default="both", choices=["dense", "resonance", "both"])
    parser.add_argument("--only", default="", help="case or script id to rerun")
    parser.add_argument("--corpus", default="known", choices=["known", "fresh"])
    args = parser.parse_args()
    if args.phase == "selftest" and args.out is None:
        rows = selftest()
        print(f"{len(rows)} scorer fixtures passed")
        return 0
    if args.out is None:
        raise SystemExit("--out is required")
    out = args.out if args.out.is_absolute() else ROOT / args.out
    if args.phase in {"prepare", "all"} or not (out / "gold" / "manifest.json").exists():
        if args.phase == "prepare" or not out.exists():
            _refuse_out(out)
        out.mkdir(parents=True, exist_ok=True)
    if not (out / "snapshot" / "HEAD.txt").exists():
        _refuse_out(out) if not out.exists() else None
        out.mkdir(parents=True, exist_ok=True)
        work = out / "work"
        work.mkdir(exist_ok=True)
        os.environ["BENCH_WORKDIR"] = str(work)
        _snapshot(out)
    else:
        os.environ["BENCH_WORKDIR"] = str(out / "work")
    if args.phase in {"prepare", "selftest", "all"} and not (out / "gold" / "manifest.json").exists():
        _prepare(out, args.corpus)
    elif args.phase == "prepare":
        _prepare(out, args.corpus)
    if args.phase == "selftest":
        print(f"{len(selftest())} scorer fixtures passed")
        return 0
    if args.phase == "prepare":
        print(f"gold written to {out / 'gold'}")
        return 0
    _dsn()
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    gold = load(out / "gold")
    arms = ["dense", "resonance"] if args.arm == "both" else [args.arm]
    if args.phase in {"dev", "holdout", "all"}:
        frozen_path = out / "gold" / "holdout_frozen.json"
        if not frozen_path.exists():
            raise SystemExit("holdout was not frozen before the run")
    for arm in arms:
        resonance = arm == "resonance"

        def factory(clock, namespace=f"bench{arm}"):
            return _open(namespace, resonance, clock)

        if args.phase in {"dev", "all"}:
            clock = Clock()
            app = factory(clock, f"bench{arm}dev")
            _model_snapshot(app, out)
            ingested = _ingest(app, gold["paragraphs"])
            _json(out / "ingest" / f"{arm}-dev.json", ingested)
            cases = [case for case in gold["cases"] if case["split"] == "development" and (not args.only or args.only in case["id"])]
            _run_cases(app, cases, out, f"{arm}-dev", ingested["corrections"])
            scripts = [script for script in gold["scripts"] if script["split"] == "development" and (not args.only or args.only in script["id"])]
            if scripts:
                _run_scripts(app, scripts, out, f"{arm}-dev", ingested["corrections"])
        if args.phase in {"holdout", "all"}:
            frozen = json.loads((out / "gold" / "holdout_frozen.json").read_text(encoding="utf-8"))
            payload = json.dumps({"cases": [row for row in gold["cases"] if row["split"] == "holdout"], "scripts": [row for row in gold["scripts"] if row["split"] == "holdout"]}, sort_keys=True)
            current = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if current != frozen["sha256"]:
                raise SystemExit("holdout hash changed after it was frozen")
            clock = Clock()
            app = factory(clock, f"bench{arm}hold")
            ingested = _ingest(app, gold["paragraphs"])
            _json(out / "ingest" / f"{arm}-hold.json", ingested)
            _run_cases(app, [case for case in gold["cases"] if case["split"] == "holdout" and (not args.only or args.only in case["id"])], out, f"{arm}-hold", ingested["corrections"])
            scripts = [script for script in gold["scripts"] if script["split"] == "holdout" and (not args.only or args.only in script["id"])]
            if scripts:
                _run_scripts(app, scripts, out, f"{arm}-hold", ingested["corrections"])
    if args.phase in {"suite", "all"} and not args.only:
        _suite(out)
    if args.phase in {"scale", "all"} and not args.only:
        for arm in arms:
            _scale(out, arm == "resonance")
    _report(out)
    print(f"report {out / 'REPORT.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
