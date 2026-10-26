"""Bounded, caller-scoped clarification for underspecified ranking requests.

A resonance-tag sense question uses the same session. It asks which meaning
was intended and does not choose one.
"""
from collections import OrderedDict
import re
import threading
import time

_RANK = re.compile(r'\b(?:best|worst|better|worse)\b', re.I)
_CRITERION = re.compile(r'\b(?:for|by|based on|in terms of|according to)\s+(.+)', re.I)
_LEADING = re.compile(r'^(?:who|what|where|when|why|how|can|which)\b', re.I)
_CRITERION_LEAD = re.compile(r'^(?:how|by|for|based on)\s+', re.I)
_VAGUE = {'yes', 'no', 'anything', 'everything', 'whatever', 'best', 'i dont know', "i don't know", 'not sure'}
_TOPIC_STOP = {
    'the', 'a', 'an', 'is', 'are', 'of', 'for', 'to', 'which', 'what', 'who', 'how',
    'where', 'when', 'why', 'can', 'best', 'worst', 'better', 'worse',
}


class ClarificationLoop:
    def __init__(self, *, ttl=1800, max_sessions=256, max_questions=3, clock=time.monotonic):
        self.ttl, self.max_sessions, self.max_questions, self.clock = ttl, max_sessions, max_questions, clock
        self.pending = OrderedDict()
        self.lock = threading.RLock()

    def _save(self, key, state):
        if key is None:
            return
        self.pending[key] = dict(state, touched=self.clock())
        self.pending.move_to_end(key)
        while len(self.pending) > self.max_sessions:
            self.pending.popitem(last=False)

    def prepare(self, message, *, key=None):
        with self.lock:
            now = self.clock()
            for expired in [k for k,v in self.pending.items() if now - v['touched'] >= self.ttl]:
                del self.pending[expired]
            state = self.pending.pop(key, None) if key is not None else None
            text = message.strip()
            if text.casefold() in {'cancel', 'start over'} and state:
                return dict(status='cancelled', text='Cancelled that question. What would you like to ask next?')
            source = None
            if state and state.get('stage') == 'evidence' and text.lower().startswith('source:'):
                source = text.split(':', 1)[1].strip()
                return dict(status='ready', query=state['query'], question=state['question'],
                            criteria=state['criteria'], user_source=source, evidence_attempts=state['count'])
            # A new question abandons the pending request. A short criterion
            # such as "how it tastes" stays with the pending ranking.
            abandoned = bool(state and _abandons_pending(text, state))
            if abandoned:
                state = None
            if state and state.get('stage') == 'sense':
                return self._resume_sense(state, text, key, abandoned)
            if state and state.get('stage') == 'evidence':
                state['count'] += 1
                if state['count'] >= self.max_questions:
                    return dict(status='insufficient_information', text='I cannot settle this comparison without supporting evidence. Please start a new question when you have it.')
                self._save(key, state)
                return dict(status='needs_clarification', slot='evidence', text='Please provide the relevant source or data, starting with “Source:”, or ask a new question.')
            if state:
                question = state['question']
                criteria = _criterion_text(text, question)
                count = state['count'] + 1
            elif _RANK.search(text):
                match = _CRITERION.search(text)
                criteria = match[1].rstrip('?.!') if match else ''
                question, count = text, 1
            else:
                ready = dict(status='ready', query=message)
                if abandoned:
                    ready['clarification_abandoned'] = True
                return ready
            vague = not criteria or criteria.casefold().strip(' .?!') in _VAGUE or len(criteria) > 500
            if vague:
                if count >= self.max_questions:
                    return _with_abandonment(dict(status='insufficient_information', text='I still need a specific criterion to compare them. Please restate the question with what matters to you.'), abandoned)
                self._save(key, dict(stage='criteria', question=question, count=count))
                return _with_abandonment(dict(status='needs_clarification', slot='criteria', question=question,
                            text='What does “best” mean for you, and what will you use it for? For example, taste, price, or size—or another criterion you choose.'), abandoned)
            query = f"{question.rstrip('?.!')} — criterion supplied by the user: {criteria}"
            ready = dict(status='ready', query=query, question=question, criteria=criteria)
            if abandoned:
                ready['clarification_abandoned'] = True
            return ready

    def need_evidence(self, plan, *, key=None):
        count = plan.get('evidence_attempts', 0) + 1
        if count >= self.max_questions:
            return dict(status='insufficient_information', slot='evidence', criteria=plan['criteria'],
                        text='The supplied information still does not settle this comparison. Please start a new question when more evidence is available.')
        with self.lock:
            self._save(key, dict(stage='evidence', query=plan['query'], question=plan['question'], criteria=plan['criteria'], count=count))
        return dict(status='needs_clarification', slot='evidence', criteria=plan['criteria'],
                    text=f'I do not have evidence that establishes which is best for {plan["criteria"]}. Can you provide relevant comparison data or a source?')

    def need_sense(self, message, senses, *, key=None):
        """Ask which meaning the user intends. The words shown are the choices."""
        shown = [dict(words=list(sense.get('words') or []), size=int(sense.get('size') or 0)) for sense in senses]
        with self.lock:
            self._save(key, dict(stage='sense', question=message, senses=shown, count=1))
        return dict(status='needs_clarification', slot='sense', question=message, senses=shown, text=_sense_text(shown))

    def _resume_sense(self, state, text, key, abandoned):
        choice = _sense_choice(text, state.get('senses') or [])
        if choice is None:
            count = state['count'] + 1
            if count >= self.max_questions:
                return _with_abandonment(dict(status='insufficient_information', slot='sense',
                            text='I still need to know which meaning you mean. Please start a new question.'), abandoned)
            self._save(key, dict(state, count=count))
            return _with_abandonment(dict(status='needs_clarification', slot='sense', question=state['question'],
                        senses=state['senses'], text=_sense_text(state['senses'])), abandoned)
        words = [word for word in choice.get('words') or []]
        query = state['question'] if not words else f"{state['question'].rstrip()} {' '.join(words)}"
        return dict(status='ready', query=query, question=state['question'], sense=choice)


def _criterion_text(text, question=''):
    stripped = _CRITERION_LEAD.sub('', text.strip(), count=1).strip()
    criteria = stripped or text.strip()
    # This binding comes from the explicit subject in the pending question,
    # not an inferred entity from retrieved documents.
    target = re.fullmatch(r'which\s+(.+?)\s+is\s+(?:best|worst|better|worse)[?.!]*', question.strip(), re.I)
    if target and not re.search(r'\b(?:and|or)\b', target[1], re.I):
        criteria = re.sub(r'\bits\b', lambda _: target[1] + "'s", criteria, flags=re.I)
        criteria = re.sub(r'\bit\b', lambda _: target[1], criteria, flags=re.I)
    return criteria


def _abandons_pending(text, state):
    """True when this reply is a new question rather than an answer to the pending one."""
    if '?' in text:
        return True
    if state.get('stage') == 'evidence':
        return bool(_LEADING.match(text))
    if not _LEADING.match(text):
        return False
    words = re.findall(r"[A-Za-z']+", text)
    if re.match(r'^(?:how|what)\s+(?:it|its|they|their)\b', text, re.I):
        return False
    topic = {word.lower() for word in re.findall(r"[A-Za-z']+", state.get('question') or '')} - _TOPIC_STOP
    reply = {word.lower() for word in words} - _TOPIC_STOP
    return not bool(topic & reply)


def _sense_text(senses):
    lines = ['Which meaning do you mean? Reply with the number or the words that match.']
    for index, sense in enumerate(senses, start=1):
        shown = ', '.join(sense.get('words') or []) or 'another meaning'
        lines.append(f'{index}. {shown}')
    return '\n'.join(lines)


def _sense_choice(text, senses):
    from cpu_llm.resonance_groups import content_words

    stripped = text.strip().rstrip('.')
    number = re.fullmatch(r'\d+', stripped)
    if number:
        index = int(stripped) - 1
        if 0 <= index < len(senses):
            return senses[index]
        return None
    words = set(content_words(text))
    if not words:
        return None
    scored = [(len(words & set(sense.get('words') or [])), sense) for sense in senses]
    scored.sort(key=lambda item: -item[0])
    if scored[0][0] == 0:
        return None
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        return None
    return scored[0][1]


def _with_abandonment(result, abandoned):
    if abandoned:
        result['clarification_abandoned'] = True
    return result


def scoped_session(tenant, caller, sources, session_id, as_of):
    return None if session_id is None else (tenant, caller, None if sources is None else tuple(sorted(sources)), str(session_id), as_of)


def supported_ranking(plan, rows):
    """Quote only a ranking explicitly tied to the user's criterion and topic."""
    from cpu_llm.answerability import _sentences
    from cpu_llm.ranking import _topic_words
    stop = {'for', 'the', 'and', 'with', 'that', 'this', 'criterion', 'terms', 'based'}
    token = r'[A-Za-z]+|\d+(?:\.\d+)?'
    criteria = {word.lower() for word in re.findall(token, plan['criteria']) if word.lower() not in stop}
    topic = _topic_words(_CRITERION.split(plan['question'])[0])
    evidence = []
    for row in rows:
        for sentence in _sentences(row.get('chunk_text') or ''):
            words = {word.lower().rstrip('s') for word in re.findall(token, sentence)}
            if (_RANK.search(sentence) and criteria and {word.rstrip('s') for word in criteria} <= words
                    and any(word.rstrip('s') in words for word in topic)
                    and not re.search(r"\b(?:not|never|if|might|may|but|whereas)\b|n't|;", sentence, re.I)):
                evidence.append(dict(document_id=row['document_id'], span=sentence))
    return evidence


def clarification_result(outcome, message, tenant):
    result = dict(message=message, original_message=message, tenant_id=tenant, answer=None,
                  status=outcome['status'], needs_clarification=outcome['status'] == 'needs_clarification',
                  clarification=outcome, reply=dict(text=outcome['text'], answer_status=outcome['status']),
                  passages=[], related=[])
    if outcome.get('clarification_abandoned'):
        result['clarification_abandoned'] = True
    return result
