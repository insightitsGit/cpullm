"""``cpu-llm-ask``: ask a namespace from the command line.

    cpu-llm-ask --namespace quantum "Frontier: barren plateaus." --screen
    cpu-llm-ask --namespace quantum --deepen --novelty "Leakage may increase logical error rates."
    cpu-llm-ask --namespace docs --strict --json "What is the retention period of the archive?"

Prints the reply text, or the whole result with ``--json``. Exit status: 0 for a usable reply, 2 when storage was
unavailable or the request was blocked, 3 when a budget stopped the work.
"""
from __future__ import annotations

import argparse
import json
import sys


def build_options(args):
    options = {}
    if args.strict:
        options['strict_evidence'] = True
    if args.session_id:
        options['session_id'] = args.session_id
    if args.screen or args.frontier or args.max_seconds:
        frontier = {}
        if args.screen:
            frontier['screen'] = True if args.shortlist is None else {'shortlist': args.shortlist}
        if args.max_seconds:
            frontier['limits'] = {'max_seconds': args.max_seconds}
        options['frontier'] = frontier or True
    if args.deepen:
        options['deepen'] = {'hypothesis': args.message, 'novelty': args.novelty} if args.novelty else True
    return options


def exit_code(result):
    status = result.get('answer_status')
    receipt = result.get('frontier') or result.get('deepen') or {}
    if status in ('unavailable', 'blocked'):
        return 2
    if status == 'partial' or receipt.get('incomplete'):
        return 3
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog='cpu-llm-ask', description='Ask a cpu-llm namespace.')
    parser.add_argument('message')
    parser.add_argument('--namespace', required=True)
    parser.add_argument('--state-dir', help='local state folder (default: CPU_LLM_STATE_DIR or ./.chorusgraph)')
    parser.add_argument('--json', action='store_true', help='print the whole result as JSON')
    parser.add_argument('--strict', action='store_true', help='strict evidence mode')
    parser.add_argument('--session-id')
    parser.add_argument('--frontier', action='store_true', help='run Frontier on the message')
    parser.add_argument('--screen', action='store_true', help='Frontier with screening (implies --frontier)')
    parser.add_argument('--shortlist', type=int, help='entries checked when screening (5-30)')
    parser.add_argument('--max-seconds', type=float, help='Frontier time budget (at most 120)')
    parser.add_argument('--deepen', action='store_true', help='run Deepen on the message as a hypothesis')
    parser.add_argument('--novelty', action='store_true', help='with --deepen, add the novelty review')
    args = parser.parse_args(argv)
    if args.novelty and not args.deepen:
        parser.error('--novelty needs --deepen')
    if args.deepen and (args.screen or args.frontier):
        parser.error('send one specialist request per call: --deepen or --frontier, not both')

    from cpu_llm.pipeline import Appliance
    with Appliance(namespace=args.namespace, state_dir=args.state_dir) as app:
        result = app.ask(args.message, **build_options(args))
    if args.json:
        print(json.dumps(result, indent=1, ensure_ascii=False, default=str))
    else:
        print(result.get('reply', {}).get('text', ''))
        if result.get('error'):
            print(f"\n[{result['answer_status']}] {result['error']['kind']}", file=sys.stderr)
    return exit_code(result)


if __name__ == '__main__':
    sys.exit(main())
