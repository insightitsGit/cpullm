"""Bounded request separation, independent retrieval, and ordered continuations.

Quoted text is data. Only explicit question/command boundaries create tasks.
Background can name a shared entity, but is never silently ingested as evidence.
"""
from __future__ import annotations

from collections import OrderedDict
import re
import threading
import time
import uuid

MAX_TASKS = 8
MAX_PROMPT_CHARS = 32000
MAX_TASK_CHARS = 1000
_START = r'(?:what|where|when|why|how|who|which|can|does|do|is|are|summari[sz]e|explain|describe|list|enumerate|compare|calculate|tell me about)\b'
_BOUNDARY = re.compile(rf'(?:[?;]\s*|[.!]\s+|\n+\s*(?:\d+[.)]\s*)?|,\s*(?:(?:and|also|then)\s+)?|\s+(?:and then|and|also|then)\s+)(?=(?:please\s+)?{_START})', re.I)
_LEADING = re.compile(rf'^(?:please\s+)?{_START}', re.I)
_REF = re.compile(r'\b(?:it|its|they|them|their|this|that|these|those)\b', re.I)
_FORMAT = re.compile(r'(?:[?.;]\s*|\n+)(?P<text>(?:please\s+)?(?:answer|respond|present (?:it|the answers)|use)\s+(?:briefly|concisely|in detail|in depth|in\s+(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s+(?:bullets?(?: points?)?|sentences?|words?))\s*[.!]?)\s*$', re.I)


def _mask(text):
    pattern = r'''```[\s\S]*?```|"[^"\n]*"|“[^”\n]*”|(?<!\w)'[^'\n]*'(?!\w)|‘[^’\n]*’|(?m:^\s*>[^\n]*)'''
    return re.sub(pattern, lambda m: re.sub(r'[^\n]', ' ', m[0]), text)


def _entity(query):
    from cpu_llm.prompt_intent import route_prompt, _name
    from cpu_llm.answerability import parse_query
    request = route_prompt(query).get('requested') or {}
    if request.get('relation') == 'causes':
        return None  # An event/effect is not an established entity antecedent.
    value = request.get('entity')
    if not value:
        parsed = parse_query(query) or {}
        value = parsed.get('subject') or parsed.get('entity')
    if not value:
        match = re.match(r'^(?:please\s+)?(?:summari[sz]e|describe|explain|list|enumerate|tell me about)\s+(?:the\s+)?(.+?)\s*[.!?]*$', query, re.I)
        value = match[1] if match else None
    if value and not _REF.search(value) and not re.search(r'\b(?:and|or)\b|[?;\n]', value, re.I):
        return _name(value)
    return None


def separate_request(message):
    """Return a plan with source offsets; never silently discard an extra task."""
    from cpu_llm.response_policy import classify_response_request
    raw = message or ''
    base = dict(schema='request-plan-v1', original_message=raw, tasks=[], background='',
                presentation=None, max_tasks=MAX_TASKS, status='single')
    if len(raw) > MAX_PROMPT_CHARS:
        return dict(base, status='limit_exceeded', reason=f'Please send at most {MAX_PROMPT_CHARS} characters per request.')
    masked = _mask(raw)
    begin, end = 0, len(raw)
    # Explicit background is isolated from executable instructions. The boundary
    # marker must be a real line, not a quoted/fenced example.
    background = ''
    marker = re.search(r'(?im)^\s*(?:questions|requests|tasks)\s*:\s*', masked)
    if marker and re.match(r'\s*(?:background|context)\s*:', masked, re.I):
        background = raw[:marker.start()].strip()
        begin = marker.end()
    style = _FORMAT.search(masked[begin:])
    presentation = None
    if style:
        end = begin + style.start()
        presentation = classify_response_request(raw[begin + style.start('text'):begin + style.end('text')])
    begin += len(re.match(r'\s*(?:\d+[.)]\s*)?', raw[begin:end])[0])
    work = masked[begin:end]
    ranges = []
    cursor = 0
    for match in _BOUNDARY.finditer(work):
        ranges.append((cursor, match.start()))
        cursor = match.end()
    ranges.append((cursor, len(work)))
    pieces = []
    for left, right in ranges:
        fragment = raw[begin + left:begin + right]
        # Strip numbering, but keep exact original span for provenance.
        leading = re.match(r'\s*(?:\d+[.)]\s*)?', fragment)[0]
        left += len(leading)
        fragment = raw[begin + left:begin + right].strip(' \t\r\n,;')
        if fragment:
            pieces.append((fragment, begin + left, begin + right))
    if len(pieces) <= 1 and not background and presentation is None:
        return base
    if not pieces:
        return dict(base, status='needs_clarification', reason='Please add a question after Questions:.')
    if len(pieces) > MAX_TASKS:
        return dict(base, status='limit_exceeded', reason=f'Please ask at most {MAX_TASKS} questions or commands at a time.')
    if any(not _LEADING.match(_mask(piece)) for piece, _, _ in pieces):
        return dict(base, status='needs_clarification', reason='Please put each question or command on its own line. Label background as Context: and the requests as Questions:.')
    entities = []
    if background:
        from cpu_llm.knowledge_graph import extract_facts
        from cpu_llm.prompt_intent import _name
        entities = list(dict.fromkeys(_name(f.subject) for f in extract_facts('user-context', background.split(':', 1)[-1])))
    tasks = []
    for index, (fragment, left, right) in enumerate(pieces):
        query = fragment.rstrip('?.!').strip()
        bindings = []
        ambiguous = False
        refs = list(_REF.finditer(_mask(query)))
        if refs:
            # Bind singular it/its only when the prompt explicitly supplies one
            # possible antecedent. Multiple names or plural/deictic forms ask.
            if len(entities) == 1 and all(m[0].casefold() in {'it', 'its'} for m in refs):
                for match in reversed(refs):
                    replacement = entities[0] + ("'s" if match[0].casefold() == 'its' else '')
                    query = query[:match.start()] + replacement + query[match.end():]
                    bindings.append(dict(start=match.start(), end=match.end(), antecedent=entities[0], replacement=replacement))
            else:
                ambiguous = True
        entity = _entity(query) if not ambiguous else None
        if entity and not bindings and entity not in entities:
            entities.append(entity)
        task_id = f'q{index + 1}'
        tasks.append(dict(id=task_id, text=fragment, query=query, source_start=left, source_end=right,
                          bindings=list(reversed(bindings)), depends_on=[tasks[-1]['id']] if bindings and tasks else [],
                          reference_unresolved=ambiguous, candidates=list(entities),
                          overlong=len(query) > MAX_TASK_CHARS))
    if any(task['overlong'] for task in tasks):
        return dict(base, status='limit_exceeded', reason=f'Please keep each individual question under {MAX_TASK_CHARS} characters; put longer source material in Context:.')
    return dict(base, status='multi', tasks=tasks, background=background, presentation=presentation,
                background_role='reference context, not verified evidence')


class RequestSessions:
    def __init__(self, ttl=1800, limit=256, clock=time.monotonic):
        self.ttl, self.limit, self.clock = ttl, limit, clock
        self.states = OrderedDict()
        self.lock = threading.RLock()

    def pop(self, key):
        with self.lock:
            for expired in [k for k, value in self.states.items() if self.clock() - value['touched'] >= self.ttl]:
                del self.states[expired]
            return self.states.pop(key, None) if key is not None else None

    def save(self, key, state):
        if key is None:
            return
        with self.lock:
            self.states[key] = dict(state, touched=self.clock())
            self.states.move_to_end(key)
            while len(self.states) > self.limit:
                self.states.popitem(last=False)


def _aggregate(plan, results, tenant):
    """Render only already judged child output. Every planned item is accounted for."""
    by_id = {item['id']: item for item in results}
    entries, lines, evidence, supporting = [], [], [], []
    for task in plan['tasks']:
        entry = by_id.get(task['id'])
        if entry is None:
            entries.append(dict(id=task['id'], query=task['query'], status='pending'))
            prefix = '- ' if (plan.get('presentation') or {}).get('format') == 'bullets' else f"{len(lines) + 1}. "
            lines.append(f"{prefix}{task['text']}\nNot executed yet; an earlier question needs attention.")
            continue
        entries.append(entry)
        text = str((entry['result'].get('reply') or {}).get('text') or '')
        prefix = '- ' if (plan.get('presentation') or {}).get('format') == 'bullets' else f"{len(lines) + 1}. "
        lines.append(f"{prefix}{task['text']}\n{text}")
        evidence.extend(entry['result'].get('answer_evidence') or [])
        supporting.extend(entry['result'].get('supporting_evidence') or [])
    waiting = any(item['status'] == 'needs_clarification' for item in entries)
    incomplete = any(item['status'] not in {'answered', 'evidence_quote'} for item in entries)
    status = 'needs_clarification' if waiting else 'partial' if incomplete else 'answered'
    text = '\n\n'.join(lines)
    presentation = dict(plan.get('presentation') or {})
    requested_items = (presentation.get('requested_limits') or {}).get('items')
    if requested_items is not None and requested_items < len(entries):
        presentation['budget_overridden_for_coverage'] = True
    return dict(message=plan['original_message'], original_message=plan['original_message'], tenant_id=tenant,
                request_plan=plan, task_results=entries, answer=None, answer_status=status, status=status,
                needs_clarification=waiting, audit_passed=False,
                answer_evidence=evidence, supporting_evidence=supporting,
                reply=dict(text=text, body=text, answer_status=status, answer_evidence=evidence),
                judgment=dict(schema='request-judgment-v1', outcome=status,
                              verification='per_task', task_ids=[item['id'] for item in entries],
                              complete=not incomplete),
                response_plan=presentation or None)


def run_request_plan(app, plan, propositions, options, *, pending=None):
    """Execute one task at a time and suspend on the first clarification."""
    state = pending or dict(plan=plan, results=[], cursor=0, propositions=propositions,
                            options=dict(options), batch_id=uuid.uuid4().hex)
    results = state['results']
    tasks = state['plan']['tasks']
    for index in range(state['cursor'], len(tasks)):
        task = tasks[index]
        child_options = dict(state['options'])
        child_options['caller'] = options.get('caller')
        parent_session = options.get('session_id')
        child_options['session_id'] = f"request:{state['batch_id']}:{task['id']}" if parent_session is not None else None
        query = state.pop('followup') if 'followup' in state else task['query']
        if query == task['query'] and state['plan'].get('presentation'):
            from cpu_llm.response_policy import classify_response_request
            if not classify_response_request(query)['explicit']:
                depth = state['plan']['presentation']['detail']
                query = 'Briefly ' + query if depth == 'brief' else query + ' in detail' if depth == 'detailed' else query
        result = app._ask_single(query, state['propositions'], **child_options)
        status = (result.get('answer_status') or (result.get('reply') or {}).get('answer_status')
                  or result.get('status') or (result.get('judgment') or {}).get('outcome') or 'insufficient_evidence')
        if result.get('needs_clarification'):
            status = 'needs_clarification'
        entry = dict(id=task['id'], query=task['query'], status=status, result=result)
        if index < len(results):
            results[index] = entry
        else:
            results.append(entry)
        state['cursor'] = index
        if status == 'needs_clarification':
            state['child_session_id'] = child_options['session_id']
            return _aggregate(state['plan'], results, app.tenant_id), state
        _clear_child(app, child_options)
        state['cursor'] = index + 1
        if status == 'blocked':
            break
    return _aggregate(state['plan'], results, app.tenant_id), None


def _clear_child(app, options):
    """Finished internal tasks must not evict pending user conversations."""
    from cpu_llm.clarification import scoped_session
    from contextlib import nullcontext
    caller = options.get('caller')
    key = scoped_session(app.tenant_id, None if caller is None else caller.caller_id,
                         None if caller is None else caller.allowed_sources,
                         options.get('session_id'), options.get('as_of'))
    if key is None:
        return
    for name, field in [('clarifications', 'pending'), ('references', 'states')]:
        store = getattr(app, name, None)
        if store is not None:
            with getattr(store, 'lock', nullcontext()):
                getattr(store, field).pop(key, None)


def dispatch_request(app, message, propositions, options):
    """Public ask boundary: single requests retain their existing pipeline."""
    from cpu_llm.pipeline import _caller_for, empty_scope_result
    from cpu_llm.clarification import scoped_session, clarification_result
    from prismguard.runtime.factory import create_checker_rules_only

    planned = separate_request(message)
    sessions = getattr(app, 'request_sessions', None)
    if planned['status'] == 'single' and sessions is None:
        return app._ask_single(message, propositions, **options)
    context = _caller_for(app, options.get('caller'))
    refused = empty_scope_result(app.tenant_id, message, context)
    if refused is not None:
        return refused
    checker = getattr(app, 'guard', None) or create_checker_rules_only()
    if checker.check(message).decision != 'allow':
        return app._ask_single(message, propositions, **options)
    key = scoped_session(app.tenant_id, None if context is None else context.caller_id,
                         None if context is None else context.allowed_sources,
                         options.get('session_id'), options.get('as_of'))
    with app._session_turn(key):
        # Different parent sessions have different turn locks. Initialize the
        # shared registry under the appliance guard so neither can lose the
        # other's first pending plan.
        with getattr(app, '_session_guard', None) or threading.Lock():
            sessions = getattr(app, 'request_sessions', None)
            if sessions is None:
                sessions = app.request_sessions = RequestSessions()
        state = sessions.pop(key)
        if state and message.strip().casefold() in {'cancel', 'start over'}:
            child_options = dict(state['options'], caller=options.get('caller'), session_id=state.get('child_session_id'))
            app._ask_single('cancel', state['propositions'], **child_options)
            _clear_child(app, child_options)
            response = clarification_result(dict(status='cancelled', text='Cancelled the remaining questions.'), message, app.tenant_id)
            response['request_plan'] = state['plan']
            return response
        fresh_question = bool(_LEADING.match(message.strip()) and not re.match(r'^(?:how|what)\s+(?:it|its|they|their)\b', message.strip(), re.I))
        if state and planned['status'] == 'single' and not fresh_question:
            state['followup'] = message
            result, remaining = run_request_plan(app, state['plan'], state['propositions'], options, pending=state)
        else:
            if state:
                _clear_child(app, dict(state['options'], caller=options.get('caller'), session_id=state.get('child_session_id')))
            if planned['status'] == 'single':
                return app._ask_single(message, propositions, **options)
            if planned['status'] != 'multi':
                result = clarification_result(dict(status='needs_clarification', slot='request_structure',
                    text=planned['reason']), message, app.tenant_id)
                result['request_plan'] = planned
                return result
            model = getattr(getattr(getattr(getattr(app, 'index', None), 'pipeline', None), 'encoder', None), '_model', None)
            if model is not None and getattr(model, 'tokenizer', None) is not None:
                for task in planned['tasks']:
                    tokens = model.tokenizer.encode(task['query'], add_special_tokens=True, truncation=False, verbose=False)
                    if len(tokens) > model.max_seq_length:
                        result = clarification_result(dict(status='needs_clarification', slot='request_structure',
                            text=f"Please shorten question {task['id']} or move its background to Context:; it exceeds the encoder's {model.max_seq_length}-token window."), message, app.tenant_id)
                        result['request_plan'] = dict(planned, status='limit_exceeded')
                        return result
            if options.get('payment') is not None or options.get('authority') is not None:
                raise ValueError('Submit a payment proposal as a separate single request.')
            loop = getattr(app, 'clarifications', None)
            if key is not None and loop is not None:
                with loop.lock:
                    loop.pending.pop(key, None)
            result, remaining = run_request_plan(app, planned, propositions, options)
        if remaining:
            sessions.save(key, remaining)
            current = remaining['results'][remaining['cursor']]
            result['clarification'] = dict(current['result'].get('clarification') or {}, task_id=current['id'])
            if key is None:
                result['clarification']['continuation'] = 'Restate the unresolved question with its entity or criterion; no session state is stored.'
        elif key is not None and result.get('task_results') and getattr(app, 'references', None) is not None:
            # Retain user/resolved prompt context, never an answer or private
            # retrieved text, for an ordinary follow-up after the batch.
            last = result['task_results'][-1]
            child = last.get('result') or {}
            query = (child.get('reference_resolution') or {}).get('query') or last['query']
            app.references.prepare(query, key=key)
        if context is not None:
            result.update(caller_id=context.caller_id, request_id=context.request_id)
        return result
