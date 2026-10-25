"""Optional CPU coreference adapters and bounded, scope-local reference state."""
from collections import OrderedDict
import re
import threading
import time

_REF = re.compile(r'\b(?:it|its|they|them|their|he|him|his|she|her|this|that|these|those)\b', re.I)
_PLURAL = {'they', 'them', 'their', 'these', 'those'}


class CorefereeBackend:
    name = 'coreferee'

    def __init__(self, model='en_core_web_sm'):
        import spacy
        import coreferee  # noqa: F401 -- registers the spaCy component
        spacy.require_cpu()
        self.nlp = spacy.load(model)
        self.nlp.add_pipe('coreferee')
        self.lock = threading.RLock()

    def analyze(self, context, prompt):
        with self.lock:
            prefix = context + ('' if context.endswith(('.', '?', '!')) else '.') + '\n'
            doc = self.nlp(prefix + prompt)
            chunks = list(doc.noun_chunks)
            bindings, candidates = [], []
            for token in doc:
                if token.idx < len(prefix) or not _REF.fullmatch(token.text):
                    continue
                if token.pos_ not in {'PRON', 'DET'}:
                    continue
                mention = next((chunk for chunk in chunks if token in chunk), None)
                possessive = token.lower_ in {'its','their','his'} or token.dep_ == 'poss'
                demonstrative = token.pos_ == 'DET' and not possessive and mention is not None
                root = mention.root if demonstrative else token
                nominal_span = None
                if token.lower_ in {'this','that','these','those'}:
                    # Small parsers can tag "lobster" as a verb after
                    # "does that". Match only a noun already observed in
                    # context, retaining ambiguity between same-named species.
                    for prior_chunk in chunks:
                        if prior_chunk.end_char > len(context) or prior_chunk.root.pos_ not in {'NOUN','PROPN'}:
                            continue
                        noun = prior_chunk.root.text
                        match = re.match(rf'{re.escape(token.text)}\s+{re.escape(noun)}\b', doc.text[token.idx:], re.I)
                        if match:
                            nominal_span = (token.idx, token.idx+match.end())
                            demonstrative, root = True, prior_chunk.root
                            break
                refs = doc._.coref_chains.resolve(root) or []
                prior = [chunk for chunk in chunks if chunk.end_char <= len(context)
                         and chunk.root.dep_ in {'nsubj', 'nsubjpass', 'dobj', 'obj', 'pobj', 'conj'}
                         and chunk.root.pos_ != 'PRON'
                         and (token.lower_ not in {'he','him','his','she','her'} or chunk.root.ent_type_ == 'PERSON')
                         and (token.lower_ not in {'it','its'} or chunk.root.ent_type_ != 'PERSON')
                         and not _REF.search(chunk.text)
                         and ('Plur' in chunk.root.morph.get('Number')) == (token.lower_ in _PLURAL)
                         and (not demonstrative or chunk.root.lemma_ == root.lemma_)]
                names = list(dict.fromkeys(chunk.text for chunk in prior))
                candidates.extend(names)
                if demonstrative and len(names) == 1 and not any(chunk.root in refs for chunk in prior):
                    # A unique prior noun phrase with the same lemma is an
                    # explicit nominal-reference rule, not a neural score.
                    refs = [prior[0].root]
                if token.lower_ in {'this','that','these','those'} and not demonstrative:
                    continue  # event/discourse deixis is not an entity guess
                # Multiple plausible entities require user confirmation even
                # when the model happens to prefer one of them.
                if len(names) != 1 or len(refs) != 1:
                    continue
                antecedent = next((chunk for chunk in prior if chunk.root == refs[0]), None)
                if antecedent is None:
                    continue
                start = nominal_span[0] if nominal_span else mention.start_char if demonstrative else token.idx
                end = nominal_span[1] if nominal_span else mention.end_char if demonstrative else token.idx + len(token.text)
                replacement = antecedent.text
                if possessive:
                    replacement += "'" if replacement.endswith('s') else "'s"
                bindings.append(dict(start=start-len(prefix), end=end-len(prefix), antecedent=antecedent.text,
                                     replacement=replacement, source_start=antecedent.start_char,
                                     source_end=antecedent.end_char, backend=self.name))
            return bindings, list(dict.fromkeys(candidates))

    def mention_spans(self, prompt):
        with self.lock:
            doc = self.nlp(prompt)
            spans = []
            for token in doc:
                if not _REF.fullmatch(token.text) or token.pos_ not in {'PRON', 'DET'}:
                    continue
                mention = next((chunk for chunk in doc.noun_chunks if token in chunk), None)
                if token.lower_ in {'this','that','these','those'} and mention is not None:
                    spans.append((mention.start_char, mention.end_char))
                else:
                    spans.append((token.idx, token.idx+len(token.text)))
            return spans


class FastCorefBackend(CorefereeBackend):
    name = 'fastcoref'

    def __init__(self, model='en_core_web_sm', model_path='biu-nlp/f-coref'):
        import spacy
        from fastcoref import spacy_component  # noqa: F401
        spacy.require_cpu()
        self.nlp = spacy.load(model)
        self.nlp.add_pipe('fastcoref', config={'device': 'cpu', 'model_path': model_path})
        self.lock = threading.RLock()

    def analyze(self, context, prompt):
        # Convert Fastcoref character clusters to the same span contract.
        with self.lock:
            prefix = context + ('' if context.endswith(('.', '?', '!')) else '.') + '\n'
            doc = self.nlp(prefix + prompt)
            bindings, candidates = [], []
            prior = [chunk for chunk in doc.noun_chunks if chunk.end_char <= len(context)
                     and chunk.root.dep_ in {'nsubj', 'nsubjpass', 'dobj', 'obj', 'pobj', 'conj'}
                     and chunk.root.pos_ != 'PRON' and not _REF.search(chunk.text)]
            for cluster in doc._.coref_clusters:
                antecedents = [(a,b) for a,b in cluster if b <= len(context) and not _REF.search(doc.text[a:b])]
                for a,b in cluster:
                    if a < len(prefix) or not _REF.search(doc.text[a:b]):
                        continue
                    word = doc.text[a:b].lower()
                    compatible = [chunk.text for chunk in prior if ('Plur' in chunk.root.morph.get('Number')) == (word in _PLURAL)
                                  and (word not in {'he','him','his','she','her'} or chunk.root.ent_type_ == 'PERSON')
                                  and (word not in {'it','its'} or chunk.root.ent_type_ != 'PERSON')]
                    candidates.extend(compatible)
                    if len(set(compatible)) != 1 or not antecedents:
                        continue
                    left,right = antecedents[0]
                    name = doc.text[left:right]
                    if name not in compatible:
                        continue
                    replacement = name + ("'s" if word in {'its','their','his'} else '')
                    bindings.append(dict(start=a-len(prefix), end=b-len(prefix), antecedent=name,
                        replacement=replacement, source_start=left, source_end=right, backend=self.name))
            return bindings, list(dict.fromkeys(candidates))


class ReferenceSessions:
    def __init__(self, backend=None, *, ttl=1800, limit=256, clock=time.monotonic):
        self.backend, self.ttl, self.limit, self.clock = backend, ttl, limit, clock
        self.states = OrderedDict()
        self.lock = threading.RLock()

    def prepare(self, prompt, *, key=None, continuation=None):
        with self.lock:
            for expired in [k for k,v in self.states.items() if self.clock()-v['time'] >= self.ttl]:
                del self.states[expired]
            state = self.states.pop(key, {}) if key is not None else {}
            if prompt.lower().strip() in {'cancel', 'start over'}:
                return dict(status='cancelled', text='Cleared the reference context. What would you like to ask next?', query=prompt, bindings=[])
            pending = state.get('pending')
            bindings, candidates = [], []
            original = prompt
            def mentions(text):
                try:
                    if self.backend is not None and hasattr(self.backend, 'mention_spans'):
                        return self.backend.mention_spans(text)
                except Exception:
                    pass
                return [(m.start(),m.end()) for m in _REF.finditer(text)]
            if pending and not '?' in prompt and not re.match(r'^(?:who|what|where|why|how|can|which)\b', prompt, re.I):
                normalize = lambda name: re.sub(r'^(?:the|a|an)\s+', '', name.strip().lower())
                choices = [name for name in pending['candidates'] if normalize(name) == normalize(prompt)]
                if not choices and not pending['candidates'] and re.fullmatch(r'[A-Za-z][A-Za-z -]{2,100}', prompt) and prompt.lower() not in {'yes','no','not sure'}:
                    choices = [prompt]
                if len(choices) == 1:
                    original = pending['prompt']
                    spans = mentions(original)
                    # Extend a short demonstrative over an explicitly named
                    # noun, even if the parser mis-tagged that noun as a verb.
                    extended = []
                    for a,b in spans:
                        if original[a:b].lower() in {'this','that','these','those'}:
                            noun = choices[0].split()[-1]
                            suffix = re.match(rf'\s+{re.escape(noun)}\b', original[b:], re.I)
                            if suffix:
                                b += suffix.end()
                        extended.append((a,b))
                    spans = extended
                    bindings = [dict(start=a, end=b, antecedent=choices[0], replacement=choices[0] + ("'s" if original[a:b].lower() in {'its','their','his'} else ''), backend='user-confirmed') for a,b in spans]
                else:
                    state['attempts'] = state.get('attempts', 0) + 1
                    if state['attempts'] >= 3:
                        return dict(status='insufficient_information', text='Please restate the question with the full entity name.', bindings=[])
                    self._save(key, state)
                    return dict(status='needs_clarification', slot='reference', text='Please give the full entity name or restate your question.', candidates=pending['candidates'], bindings=[])
            spans = mentions(prompt)
            if not bindings and spans:
                context = state.get('context', '')
                try:
                    if self.backend is not None and context:
                        bindings, candidates = self.backend.analyze(context, prompt)
                        bindings = [b for b in bindings if 0 <= b['start'] < b['end'] <= len(prompt)
                                    and b['antecedent'] in context and b.get('replacement')]
                except Exception as exc:
                    # A backend failure cannot turn an unresolved reference
                    # into an answer; report unavailability, not a guessed binding.
                    state['backend_error'] = type(exc).__name__
                # All detected references must be covered; partial rewrites
                # can attach one person's attribute to another entity.
                if not all(any(b['start'] <= a and b['end'] >= end for b in bindings) for a,end in spans):
                    bindings = []
                    state['pending'] = dict(prompt=prompt, candidates=candidates, continuation=continuation)
                    state['attempts'] = state.get('attempts', 0) + 1
                    if state['attempts'] >= 3:
                        return dict(status='insufficient_information', text='Please restate the question with the full entity name.', bindings=[])
                    self._save(key, state)
                    return dict(status='needs_clarification', slot='reference', text='Which entity do you mean? Please give its full name.', candidates=candidates, bindings=[])
            if bindings:
                query = original
                for binding in sorted(bindings, key=lambda b:b['start'], reverse=True):
                    query = query[:binding['start']] + binding['replacement'] + query[binding['end']:]
            else:
                query = prompt
            # Only user/resolved prompt context is retained, never retrieved
            # private documents or generated answers. Keep the latest topic.
            self._save(key, dict(context=query[:4000], attempts=0))
            return dict(status='resolved' if bindings else 'unchanged', query=query, bindings=bindings, original=original,
                        continuation=pending.get('continuation') if pending and bindings else None)

    def _save(self, key, state):
        if key is None:
            return
        self.states[key] = dict(state, time=self.clock())
        self.states.move_to_end(key)
        while len(self.states) > self.limit:
            self.states.popitem(last=False)
