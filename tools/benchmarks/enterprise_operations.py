"""Exercise HTTP ingestion contention, interruption, and a coordinated restore."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen
import uuid

import psycopg
from psycopg import sql

from cpu_llm.documents import SourceDocument, replace_prefix
from cpu_llm.entry import Entry, secret_sha256
from cpu_llm.pipeline import Appliance
from cpu_llm.serve import LocalService

NAMESPACE = "enterprise_lab"
SOURCE = "pilot-control"
QUESTION = "What is the color of Aster?"
SENTENCE = "The color of Aster is blue."


def interrupt_worker(marker):
    with Appliance(namespace=NAMESPACE, prompt_backend="rules") as app:
        encoder = app.index.pipeline.encode_texts

        def stop_after_first_batch(texts, *args, **kwargs):
            if texts == ["Replacement row 33."]:
                marker.touch()
                threading.Event().wait()
            return encoder(texts, *args, **kwargs)

        app.index.pipeline.encode_texts = stop_after_first_batch
        app.catalog_chunks([(f"{SOURCE}-p{i:04d}", f"Replacement row {i}.") for i in range(1, 34)],
                           replace_prefix=f"{SOURCE}-p")


def measure_http(pdf, credentials, audit, secret, pdf_prefix):
    entered = threading.Event()
    cache = {}

    def appliance_for(tenant):
        if tenant not in cache:
            cache[tenant] = Appliance(namespace=tenant, prompt_backend="rules")
        return cache[tenant]

    class ObservedEntry(Entry):
        def ingest(self, presented, source):
            if source == str(pdf):
                entered.set()
            return super().ingest(presented, source)

    service = LocalService(ObservedEntry(credentials, appliance_for, ingest_root=pdf.parent, audit_path=audit),
                           port=0)

    def serve():
        try:
            service.serve_forever()
        finally:
            for app in cache.values():
                app.close()

    thread = threading.Thread(target=serve)
    thread.start()

    def post(path, payload):
        started = time.perf_counter()
        req = Request(f"http://127.0.0.1:{service.port}{path}", data=json.dumps(payload).encode(),
                      headers={"Content-Type": "application/json", "Authorization": f"Bearer {secret}"})
        with urlopen(req, timeout=360) as response:
            value = json.load(response)
        return value, time.perf_counter() - started

    try:
        post("/v1/ingest", {"name": SOURCE, "paragraphs": [SENTENCE]})
        ask = {"message": QUESTION, "strict_evidence": True}
        before, baseline = post("/v1/ask", ask)
        assert before["answer_status"] == "evidence_quote"
        with ThreadPoolExecutor(max_workers=4) as pool:
            ingestion = pool.submit(post, "/v1/ingest", {"source": str(pdf)})
            if not entered.wait(30):
                raise RuntimeError("HTTP ingest did not begin.")
            concurrent = [pool.submit(post, "/v1/ask", ask) for _ in range(3)]
            imported, duration = ingestion.result()
            queries = [future.result() for future in concurrent]
        assert imported["chunks"] > 32
        assert all(result["answer_status"] == "evidence_quote" for result, _ in queries)
        inventory, _ = post("/v1/chunks", {"source": pdf_prefix})
        assert inventory["chunk_count"] == imported["chunks"]
        return dict(baseline_seconds=baseline, ingest_seconds=duration, chunks=imported["chunks"],
                    concurrent_query_seconds=[elapsed for _, elapsed in queries])
    finally:
        service.close()
        thread.join()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--pg-bin", type=Path)
    parser.add_argument("--interrupt-marker", type=Path)
    args = parser.parse_args()
    if args.interrupt_marker:
        interrupt_worker(args.interrupt_marker)
        return
    if not all((args.pdf, args.out, args.pg_bin)):
        parser.error("--pdf, --out, and --pg-bin are required")
    dsn = os.environ["VECTORPRISM_PG_DSN"]
    url = urlsplit(dsn)
    if url.hostname not in {"localhost", "127.0.0.1"} or url.path != "/enterprise_ops":
        parser.error("Use a disposable loopback database named enterprise_ops.")
    pdf, out = args.pdf.resolve(), args.out.resolve()
    out.mkdir(parents=True)
    work = out / "primary"
    work.mkdir()
    os.chdir(work)
    pdf_prefix = replace_prefix(SourceDocument(pdf.stem, ()))
    credentials, audit = work / "credentials.json", work / "audit.sqlite"
    secret = uuid.uuid4().hex
    credentials.write_text(json.dumps({"credentials": [
        dict(id="operator", tenant_id=NAMESPACE, role="admin", secret_sha256=secret_sha256(secret),
             allowed_sources=[pdf_prefix, f"{SOURCE}-p"])
    ]}), encoding="utf8")
    summary = {"http": measure_http(pdf, credentials, audit, secret, pdf_prefix)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")

    marker = work / "interruption-ready"
    child = subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "--interrupt-marker", str(marker)],
        start_new_session=os.name != "nt",
    )
    try:
        deadline = time.monotonic() + 90
        while not marker.exists() and child.poll() is None and time.monotonic() < deadline:
            time.sleep(.1)
        if not marker.exists():
            raise RuntimeError("Interrupted import did not reach the second encoder batch.")
    finally:
        if child.poll() is None:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], check=True,
                               stdout=subprocess.DEVNULL)
            else:
                os.killpg(child.pid, signal.SIGKILL)
        child.wait(timeout=15)
    with Appliance(namespace=NAMESPACE, prompt_backend="rules") as app:
        active = app.chunk_inventory(SOURCE)
        answer = app.ask(QUESTION, strict_evidence=True)
        assert active["chunk_ids"] == [f"{SOURCE}-p0001"]
        assert answer["answer_status"] == "evidence_quote" and SENTENCE in answer["reply"]["text"]
        app.ingest(SourceDocument(SOURCE, (SENTENCE,)))
    summary["interruption"] = dict(second_batch_reached=True, previous_chunk_preserved=True, retry_completed=True)

    backup = out / "backup"
    backup.mkdir()
    dump = backup / "postgres.dump"
    subprocess.run([str(args.pg_bin / "pg_dump"), "--dbname", dsn, "--format", "custom", "--file", str(dump)],
                   check=True)
    shutil.copytree(work / ".chorusgraph", backup / ".chorusgraph")
    shutil.copy2(audit, backup / "audit.sqlite")
    restored = out / "restored"
    shutil.copytree(backup / ".chorusgraph", restored / ".chorusgraph")
    shutil.copy2(backup / "audit.sqlite", restored / "audit.sqlite")
    target = f"enterprise_restore_{uuid.uuid4().hex[:8]}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)))
    restored_dsn = urlunsplit(url._replace(path=f"/{target}"))
    subprocess.run([str(args.pg_bin / "pg_restore"), "--exit-on-error", "--dbname", restored_dsn, str(dump)],
                   check=True)
    os.chdir(restored)
    with Appliance(dsn=restored_dsn, namespace=NAMESPACE, prompt_backend="rules") as app:
        reply = app.ask(QUESTION, strict_evidence=True)
        assert reply["answer_status"] == "evidence_quote" and SENTENCE in reply["reply"]["text"]
        assert app.chunk_inventory(pdf_prefix)["chunk_count"] == summary["http"]["chunks"]
    assert (restored / "audit.sqlite").read_bytes() == audit.read_bytes()
    summary["restore"] = dict(chunk_count_preserved=True, strict_answer_preserved=True, audit_copy_verified=True)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
