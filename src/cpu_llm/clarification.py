"""Bounded, caller-scoped clarification for underspecified ranking requests."""
from collections import OrderedDict
import re
import threading
import time

_RANK = re.compile(r'\b(?:best|worst|better|worse)\b', re.I)
_CRITERION = re.compile(r'\b(?:for|by|based on|in terms of|according to)\s+(.+)', re.I)
_VAGUE = {'yes', 'no', 'anything', 'everything', 'whatever', 'best', 'i dont know', "i don't know", 'not sure'}


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
            # A full new question abandons the pending request rather than
            # being silently consumed as a preference for the previous topic.
            if state and ('?' in text or re.match(r'^(?:who|what|where|when|why|how|can|which)\b', text, re.I)):
                state = None
            if state and state.get('stage') == 'evidence':
                state['count'] += 1
                if state['count'] >= self.max_questions:
                    return dict(status='insufficient_information', text='I cannot settle this comparison without supporting evidence. Please start a new question when you have it.')
                self._save(key, state)
                return dict(status='needs_clarification', slot='evidence', text='Please provide the relevant source or data, starting with “Source:”, or ask a new question.')
            if state:
                criteria = text
                question = state['question']
                count = state['count'] + 1
            elif _RANK.search(text):
                match = _CRITERION.search(text)
                criteria = match[1].rstrip('?.!') if match else ''
                question, count = text, 1
            else:
                return dict(status='ready', query=message)
            vague = not criteria or criteria.casefold().strip(' .?!') in _VAGUE or len(criteria) > 500
            if vague:
                if count >= self.max_questions:
                    return dict(status='insufficient_information', text='I still need a specific criterion to compare them. Please restate the question with what matters to you.')
                self._save(key, dict(stage='criteria', question=question, count=count))
                return dict(status='needs_clarification', slot='criteria', question=question,
                            text='What does “best” mean for you, and what will you use it for? For example, taste, price, or size—or another criterion you choose.')
            query = f"{question.rstrip('?.!')} — criterion supplied by the user: {criteria}"
            return dict(status='ready', query=query, question=question, criteria=criteria)

    def need_evidence(self, plan, *, key=None):
        count = plan.get('evidence_attempts', 0) + 1
        if count >= self.max_questions:
            return dict(status='insufficient_information', slot='evidence', criteria=plan['criteria'],
                        text='The supplied information still does not settle this comparison. Please start a new question when more evidence is available.')
        with self.lock:
            self._save(key, dict(stage='evidence', query=plan['query'], question=plan['question'], criteria=plan['criteria'], count=count))
        return dict(status='needs_clarification', slot='evidence', criteria=plan['criteria'],
                    text=f'I do not have evidence that establishes which is best for {plan["criteria"]}. Can you provide relevant comparison data or a source?')


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
    return dict(message=message, original_message=message, tenant_id=tenant, answer=None,
                status=outcome['status'], needs_clarification=outcome['status'] == 'needs_clarification',
                clarification=outcome, reply=dict(text=outcome['text'], answer_status=outcome['status']),
                passages=[], related=[])
