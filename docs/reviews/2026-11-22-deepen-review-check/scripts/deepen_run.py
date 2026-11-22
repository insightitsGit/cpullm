"""Deepen selected Frontier hypotheses from the v2 re-runs.

usage: deepen_run.py outdir namespace raw-frontier-json 'text fragment' ['text fragment' ...]
"""
import json
import pathlib
import sys
import time

from cpu_llm.pipeline import Appliance


def main():
    out, namespace, raw = pathlib.Path(sys.argv[1]), sys.argv[2], pathlib.Path(sys.argv[3])
    fragments = sys.argv[4:]
    out.mkdir(parents=True, exist_ok=True)
    hypotheses = json.loads(raw.read_text())['frontier']['hypotheses']
    with Appliance(namespace=namespace) as app:
        for fragment in fragments:
            hypothesis = next(h for h in hypotheses if fragment.casefold() in h['text'].casefold())
            started = time.perf_counter()
            reply = app.ask('Deepen this hypothesis.', deepen=dict(hypothesis=hypothesis, novelty=True))
            seconds = round(time.perf_counter() - started, 2)
            slug = ''.join(ch if ch.isalnum() else '-' for ch in fragment.casefold()).strip('-')[:60]
            (out / f'{namespace}-{slug}.json').write_text(json.dumps(dict(
                namespace=namespace, frontier_hypothesis=hypothesis, seconds=seconds,
                answer_status=reply['answer_status'], deepen=reply.get('deepen'), reply=reply['reply']['text']),
                indent=1, ensure_ascii=False))
            receipt = reply.get('deepen') or {}
            print(namespace, '|', hypothesis['text'], '|', reply['answer_status'], receipt.get('verdict'),
                  [link['status'] for link in receipt.get('links', [])], seconds, flush=True)


if __name__ == '__main__':
    main()
