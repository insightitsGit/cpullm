"""Iterative, bounded multi-cycle discovery over explicit directed source edges.

Cycles are source-backed lexical paths, not new facts or identity/causal proofs.
No database, learned generator or persistent migration is required by the core.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, asdict
import hashlib
import json
import time


@dataclass(frozen=True)
class CycleLimits:
    max_rounds: int = 1000
    max_nodes: int = 10000
    max_edges: int = 50000
    max_states: int = 100000
    max_frontier: int = 10000
    max_cycles: int = 32
    max_bytes: int = 64 * 1024 * 1024
    max_seconds: float = 5.0

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == 'max_seconds':
                import math
                if type(value) not in (int, float) or not math.isfinite(value) or value <= 0 or value > 60:
                    raise ValueError('max_seconds must be finite and in (0, 60]')
            elif type(value) is not int or value < 1:
                raise ValueError(key + ' must be a positive integer')
        ceilings = dict(max_rounds=100000, max_nodes=100000, max_edges=200000,
                        max_states=200000, max_frontier=100000, max_cycles=100,
                        max_bytes=128 * 1024 * 1024)
        for key, ceiling in ceilings.items():
            if getattr(self, key) > ceiling:
                raise ValueError(key + ' exceeds operator ceiling')


def key(label):
    # No substring matching or alias merging; exact whole labels only.
    return ' '.join(label.casefold().split())


class Budget:
    """One ledger can be shared across seeds. Limits never reset per child."""
    def __init__(self, limits=None, *, clock=time.monotonic):
        self.limits = limits or CycleLimits()
        self.clock = clock
        self.started = clock()
        self.counters = dict(edges=0, states=0, nodes=0, bytes=0, cycles=0)

    def check(self):
        if self.clock() - self.started >= self.limits.max_seconds:
            raise StopSearch('deadline')

    def charge(self, kind, count=1):
        self.check()
        cap = getattr(self.limits, 'max_' + kind)
        if self.counters[kind] + count > cap:
            raise StopSearch(kind + '_limit')
        self.counters[kind] += count


class StopSearch(Exception):
    pass


def edge_record(fact):
    from cpu_llm.connection_channels import evaluate_connection
    identity = [fact.subject, fact.relation, fact.object, fact.document_id, fact.sentence]
    edge_id = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()
    return dict(id=edge_id, subject=fact.subject, relation=fact.relation, object=fact.object,
                source=key(fact.subject), target=key(fact.object), document_id=fact.document_id,
                sentence=fact.sentence, channels=evaluate_connection(fact),
                claim_key=(key(fact.subject), fact.relation, key(fact.object)))


def explore(seed, adjacency, *, budget=None, cancelled=None):
    """adjacency(node) yields bounded, source-authorized edge records in stable order.

    The caller owns a fixed snapshot. Exact labels identify lexical nodes only;
    callers must not advertise these results as disambiguated semantic identity.
    """
    budget = budget or Budget()
    limits = budget.limits
    root = key(seed)
    if not root or len(root) > 240:
        raise ValueError('seed must be a nonempty whole entity label of at most 240 characters')
    paths = [(root, None, None, 0)]
    queue = deque([0])
    known = {root}
    cycles, signatures = [], set()
    round_reached = 0
    truncated = False
    reason = 'frontier_exhausted'
    def chain(index):
        while index is not None:
            yield index
            index = paths[index][1]
    try:
        budget.charge('nodes'); budget.charge('states'); budget.charge('bytes', 256 + len(root.encode()))
        while queue:
            budget.check()
            if cancelled and cancelled():
                raise StopSearch('cancelled')
            index = queue.popleft()
            node, parent, incoming, depth = paths[index]
            if depth >= limits.max_rounds:
                truncated = True
                continue
            round_reached = max(round_reached, depth + 1)
            claims = set()
            for edge in adjacency(node):
                budget.charge('edges')
                if cancelled and cancelled():
                    raise StopSearch('cancelled')
                if edge['source'] != node:
                    continue
                # Distinct source proofs of the same claim do not create new paths.
                claim = tuple(edge['claim_key'])
                if claim in claims:
                    continue
                claims.add(claim)
                if not edge['channels']['epistemic']['source_supported']:
                    continue
                if not any(c['symbolic_supported'] for c in edge['channels']['channels'].values()):
                    continue
                target = edge['target']
                if target == root:
                    if depth < 1:
                        continue
                    links = list(reversed(list(chain(index))))
                    edges = [paths[p][2] for p in links if paths[p][2] is not None] + [edge]
                    if all(e['relation'] == 'alias_of' for e in edges):
                        continue
                    signature = tuple(tuple(e['claim_key']) for e in edges)
                    if signature in signatures:
                        continue
                    budget.charge('cycles')
                    # Full source paths remain bounded by state, memory and result limits.
                    size = sum(len(json.dumps(e, ensure_ascii=False).encode()) for e in edges)
                    budget.charge('bytes', size)
                    cycles.append(dict(edges=edges, length=len(edges),
                        qualification='lexical_candidate',
                        relation_pattern='taxonomy_cycle' if all(e['relation'] == 'is_a' for e in edges)
                            else 'causal_cycle' if all(e['relation'] == 'causes' for e in edges) else 'mixed',
                        verification='source_backed_lexical_path; no new inferred fact',
                        identity_resolution='exact_labels_only; homonyms_not_disambiguated'))
                    signatures.add(signature)
                    if budget.counters['cycles'] >= limits.max_cycles:
                        raise StopSearch('result_limit')
                    continue
                if target in known and any(paths[p][0] == target for p in chain(index)):
                    continue
                if len(queue) >= limits.max_frontier:
                    raise StopSearch('frontier_limit')
                if target not in known:
                    budget.charge('nodes'); known.add(target)
                budget.charge('states')
                budget.charge('bytes', 256 + len(target.encode()) + len(json.dumps(edge).encode()))
                paths.append((target, index, edge, depth + 1))
                queue.append(len(paths) - 1)
        if truncated:
            reason = 'max_rounds'
    except StopSearch as exc:
        reason = str(exc)
    return dict(schema='cycle-exploration-v1', seed=seed, cycles=cycles,
                complete=reason == 'frontier_exhausted', stop_reason=reason,
                rounds=round_reached, counters=dict(budget.counters), limits=asdict(limits),
                source_truth_verified=False, inferred_facts=[], continuation=None,
                identity_resolution='exact_labels_only; unresolved senses are not validated')


def explore_snapshot(seed, rows, *, limits=None, allowed=None, tenant_id='', snapshot=None):
    """Build an ephemeral graph only from the caller's bounded source snapshot."""
    from cpu_llm.knowledge_graph import extract_facts
    from cpu_llm.access import source_allowed
    budget = Budget(limits)
    graph = {}
    reason = None
    try:
        for row in rows:
            budget.check()
            if not source_allowed(row['document_id'], allowed):
                continue
            for fact in extract_facts(row['document_id'], row['chunk_text']):
                budget.charge('edges')
                edge = edge_record(fact)
                start = row['chunk_text'].find(fact.sentence)
                if start < 0:
                    continue
                edge['proof'] = dict(document_id=row['document_id'], quote=fact.sentence,
                    start=start, end=start + len(fact.sentence),
                    chunk_sha256=hashlib.sha256(row['chunk_text'].encode()).hexdigest())
                budget.charge('bytes', 256 + len(json.dumps(edge).encode()))
                claims = graph.setdefault(edge['source'], {})
                claim = tuple(edge['claim_key'])
                if claim in claims:
                    existing = claims[claim]
                    existing.setdefault('additional_proofs', []).append(edge['proof'])
                else:
                    claims[claim] = edge
    except StopSearch as exc:
        reason = str(exc)
    if reason:
        result = dict(schema='cycle-exploration-v1', seed=seed, cycles=[], complete=False,
                      stop_reason=reason, rounds=0, counters=dict(budget.counters),
                      limits=asdict(budget.limits), inferred_facts=[], continuation=None)
    else:
        for node, claims in list(graph.items()):
            edges = list(claims.values())
            edges.sort(key=lambda e: (e['target'], e['relation'], e['id']))
            graph[node] = edges
        result = explore(seed, lambda node: iter(graph.get(node, ())), budget=budget)
    result.update(tenant_id=tenant_id, snapshot=snapshot, source_truth_verified=False,
                  graph_scope='authorized_snapshot; explicit directed lexical claims')
    return result


def execute_cycle_request(app, message, options, *, caller=None, as_of=None, strict=False):
    """Explicit Python/HTTP opt-in; strict answers never acquire cycle inference."""
    from cpu_llm.pipeline import _caller_for
    import psycopg
    seed,limits=validate_cycle_options(options)
    context = _caller_for(app, caller)
    def refusal(status, text):
        return dict(answer_status=status, status=status, answer=None, audit_passed=False,
                    answer_evidence=[], reply=dict(text=text), tenant_id=app.tenant_id)
    if app.guard.check(message + '\n' + seed).decision != 'allow':
        return refusal('blocked', 'Request blocked.')
    if strict:
        return refusal('unsupported', 'Cycle exploration is disabled in strict evidence mode.')
    allowed = None if context is None else context.allowed_sources
    if allowed is not None and not allowed:
        return refusal('blocked', 'No authorized sources are available.')
    try:
        rows, when = app.index.strict_source_rows(allowed, as_of=as_of)
        if len(rows) > 10000 or sum(len(r['chunk_text']) for r in rows) > 8_000_000:
            return refusal('insufficient_evidence', 'Cycle source snapshot exceeds its limit.')
    except (ValueError, RuntimeError, psycopg.Error):
        return refusal('insufficient_evidence', 'Cycle source snapshot is unavailable.')
    result = explore_snapshot(seed, rows, limits=limits, allowed=allowed,
                             tenant_id=app.tenant_id, snapshot=dict(as_of=when))
    from .cycle_composition import compose_cycles
    composition=compose_cycles(result,rows)
    evidence=composition['evidence']
    lines=['Source-backed lexical cycles; no new inferred facts or resolved word senses.']
    lines.extend(s['text']+'\nSources: '+', '.join(s['source_ids']) for s in composition['sentences'])
    if not evidence:
        lines.append('Discovered cycles could not be included within validation or presentation limits.' if result['cycles'] else
                     'No qualifying cycle found within the authorized snapshot and search limits.')
    if not result['complete']:
        lines.append('Search incomplete: '+result['stop_reason']+'.')
    if composition['omitted_cycles']:
        lines.append(str(composition['omitted_cycles'])+' cycles omitted by validation or presentation limits.')
    result['presentation_truncated']=composition['presentation_truncated']
    return dict(answer_status='evidence_quote' if evidence else 'insufficient_evidence',
                status='completed' if result['complete'] and not composition['presentation_truncated'] else 'partial',
                answer=None,audit_passed=False,answer_evidence=evidence,cycle_exploration=result,
                cycle_composition=composition,reply=dict(text='\n'.join(lines)),tenant_id=app.tenant_id,
                routing=dict(post_stages=['cycle_snapshot','cycle_explore','cycle_compose','cycle_verify']))


def validate_cycle_options(options):
    if not isinstance(options, dict) or set(options) - {'seed', 'limits'}:
        raise ValueError('cycle_search requires seed and optional limits')
    seed = options.get('seed')
    if not isinstance(seed, str) or not seed.strip() or len(seed) > 240:
        raise ValueError('cycle_search.seed must be a named entity label (1..240 characters)')
    limit_options = options.get('limits', {})
    if not isinstance(limit_options, dict) or set(limit_options) - set(CycleLimits.__dataclass_fields__):
        raise ValueError('unknown cycle search limit')
    limits = CycleLimits(**limit_options)
    return seed,limits
