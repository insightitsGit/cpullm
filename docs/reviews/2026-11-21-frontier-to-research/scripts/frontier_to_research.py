"""Frontier ideas as seeds for the research route (invention, source hypotheses, Nammade, abductive bridge).

usage: frontier_to_research.py outdir namespace 'Frontier: <topic>.' [top_k]

For each of the top-k Frontier hypotheses, the anchors become one research seed,
"Investigate A, B and C.", which runs through the existing research route on the
same knowledge base. Nothing is written to the index; both stages only read.
"""
import json
import pathlib
import sys
import time

from cpu_llm.pipeline import Appliance


def seed_for(hypothesis):
    anchors = list(dict.fromkeys(a.strip().rstrip('.') for a in hypothesis['anchors'] if a.strip()))
    if hypothesis['pattern'] == 'chain' and hypothesis.get('via'):
        via = hypothesis['via'][0].split(' (read as ')[0]
        anchors = [anchors[0], via, anchors[-1]]
    joined = ', '.join(anchors[:-1]) + ' and ' + anchors[-1] if len(anchors) > 1 else anchors[0]
    return f'Investigate {joined}.'


def research_summary(reply):
    workspace_options = reply.get('research_options') or []
    invention = reply.get('invention') or {}
    nammade = reply.get('nammade') or {}
    return dict(
        answer_status=reply.get('answer_status'),
        stages=(reply.get('routing') or {}).get('post_stages'),
        research_methods=reply.get('research_methods'),
        research_question=(invention.get('research_brief') or {}) or None,
        proposals=invention.get('proposals', []),
        source_context=[dict(document_id=p.get('document_id'), quote=p.get('quote'))
                        for p in invention.get('research_context', []) if isinstance(p, dict)],
        hypothesis_options=workspace_options,
        nammade_comparisons=len(nammade.get('evaluations', [])),
        abductive_bridge=reply.get('abductive_bridge'),
        research_inference=(reply.get('research_inference') or {}).get('outcome'),
        reply=reply['reply']['text'],
    )


def main():
    out, namespace, prompt = pathlib.Path(sys.argv[1]), sys.argv[2], sys.argv[3]
    top_k = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    out.mkdir(parents=True, exist_ok=True)
    with Appliance(namespace=namespace) as app:
        started = time.perf_counter()
        frontier = app.ask(prompt)
        frontier_seconds = time.perf_counter() - started
        receipt = frontier['frontier']
        chained = []
        for rank, hypothesis in enumerate(receipt['hypotheses'][:top_k], 1):
            seed = seed_for(hypothesis)
            started = time.perf_counter()
            reply = app.ask(seed)
            chained.append(dict(rank=rank, frontier_hypothesis=hypothesis, seed=seed,
                                research_seconds=round(time.perf_counter() - started, 2),
                                research=research_summary(reply)))
            print(prompt, rank, seed, reply.get('answer_status'), flush=True)
    name = prompt.removeprefix('Frontier: ').rstrip('.').replace(' ', '-').lower()
    (out / f'{name}.json').write_text(json.dumps(dict(
        prompt=prompt, namespace=namespace, frontier_seconds=round(frontier_seconds, 2),
        frontier_status=receipt['status'], frontier_returned=len(receipt['hypotheses']),
        chained=chained), indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
