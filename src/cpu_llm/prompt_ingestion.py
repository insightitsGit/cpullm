"""Auditable prompt interpretation; user text is never source evidence.

The optional CPU parser supplies span annotations, not facts or authority to
rewrite a request. Only declared, reversible request constructions are compiled.
"""
from __future__ import annotations

import re
import threading
import importlib.util

SCHEMA = 'prompt-interpretation-v1'
MAX_ANNOTATIONS = 64
_GUARD = re.compile(r"\b(?:not|never|without|except|unless|if|whether|only|every|all|some|average|must|may|might)\b|n't", re.I)
_WH = r'(?:what|who|where|when|why|how|which)\b'
_SHELL = re.compile(
    rf"^(?:please\s+)?(?:(?:can|could|would|will) you\s+(?:please\s+)?(?:tell me|explain|show me|find out)|"
    rf"(?:tell me|let me know)|do you know|i (?:want|need|would like) to know|i['’]d like to know|i was wondering)\s+(?={_WH})", re.I)
_FACET = re.compile(
    r"^(?:please\s+)?(?:tell me|show(?: me)?|give me|provide(?: me)?|i (?:want|need)(?: to know)?|"
    r"i would like to know|i['’]d like to know)\s+(?:the\s+)?(?P<fields>.+?)\s+(?:of|for)\s+(?P<entity>.+?)[.?!]*$", re.I)
_FIELDS = {
    'color': 'What color is {entity}?', 'colour': 'What color is {entity}?',
    'shape': 'What shape is {entity}?', 'material': 'What material is {entity}?',
    'habitat': 'Where does {entity} live?', 'lifespan': 'How long does {entity} live?',
    'weight': 'How much does {entity} weigh?', 'definition': 'What is {entity}?',
}
_ANNOTATION_REQUEST = re.compile(
    r'^(?:please\s+)?(?:(?:can|could|would) you\s+)?(?:give(?: me)?|provide(?: me)?|find|show(?: me)?)\s+'
    r'(?:some\s+)?(?:information|details|data)\s+(?:about|on|regarding)\s+', re.I)


def _parser_query(text, candidate):
    """Validate a parser proposal against the entire explicit source request."""
    if _GUARD.search(text) or re.search(r'["“”]|```', text):
        return None
    prefix = _ANNOTATION_REQUEST.match(text)
    try:
        a, b, c, d = (candidate[key] for key in ('attribute_start', 'attribute_end', 'entity_start', 'entity_end'))
        if not all(type(value) is int for value in (a, b, c, d)) or not 0 <= a < b < c < d <= len(text):
            return None
        field = re.sub(r'^the\s+', '', text[a:b], flags=re.I).casefold()
        if (not prefix or prefix.end() != a or field not in _FIELDS
                or not re.fullmatch(r'\s+of\s+', text[b:c], re.I)
                or not re.fullmatch(r'[.!?\s]*', text[d:])):
            return None
        return _FIELDS[field].format(entity=text[c:d])
    except (KeyError, TypeError, ValueError):
        return None


def normalize_question(text: str) -> dict:
    """Compile request syntax only, preserving all unrecognized wording."""
    raw = text or ''
    result = dict(input_text=raw, query=raw, transformations=[], status='unchanged')
    # Quoted/code data, conditions, negation and quantified wording cannot be
    # dropped by an outer-shell rewrite. Existing producers may still handle it.
    if _GUARD.search(raw) or re.search(r'```|["“”]|(?m:^\s*>)', raw):
        return dict(result, status='guarded')
    query = raw.strip()
    shell = _SHELL.match(query)
    if shell:
        query = query[shell.end():]
        result['transformations'].append(dict(rule='explicit_inquiry_shell', removed=shell[0]))
    core = query.rstrip('?.!').strip()
    inverse = re.fullmatch(r'(what (?:colou?r|shape|material)|who|what)\s+(.+?)\s+(is|are|was|were)', core, re.I)
    if inverse and not re.match(r'^(?:is|are|was|were)\b', inverse[2], re.I):
        query = f'{inverse[1]} {inverse[3]} {inverse[2]}?'
        result['transformations'].append(dict(rule='indirect_copula_order'))
    else:
        residence = re.fullmatch(r'(where|how long)\s+(.+?)\s+(lives|resides|live|reside)', core, re.I)
        if residence and not re.search(r'\b(?:does|do|did|can|is|are|was|were|and|or)\b', residence[2], re.I):
            auxiliary = 'does' if residence[3].casefold().endswith('s') else 'do'
            verb = residence[3].casefold().removesuffix('s')
            query = f'{residence[1]} {auxiliary} {residence[2]} {verb}?'
            result['transformations'].append(dict(rule='indirect_residence_order'))
    if result['transformations']:
        result.update(query=query, status='normalized')
    fields = expand_explicit_fields(result['query'])
    if fields and fields['status'] == 'expanded' and len(fields['queries']) == 1:
        result.update(query=fields['queries'][0], status='normalized')
        result['transformations'].append(dict(rule='explicit_field', fields=fields['fields']))
    return result


def expand_explicit_fields(text: str) -> dict | None:
    """Expand an explicit field list, never infer unasked-for fields."""
    if _GUARD.search(text) or re.search(r'["“”]|```', text):
        return None
    match = _FACET.fullmatch(text.strip())
    if not match:
        return None
    fields = [re.sub(r'^the\s+', '', part.strip(), flags=re.I).casefold()
              for part in re.split(r'\s*,\s*(?:and\s+)?|\s+and\s+', match['fields']) if part.strip()]
    # A general summary is not a field list. A partly recognized list must not
    # silently omit the unknown field.
    if not any(field in _FIELDS for field in fields):
        return None
    unknown = [field for field in fields if field not in _FIELDS]
    if unknown:
        return dict(status='needs_clarification', reason='Please restate the requested fields: ' + ', '.join(unknown), queries=[])
    entity = match['entity'].strip()
    if re.search(r'\b(?:and|or)\b|[?;\n]', entity, re.I):
        return dict(status='needs_clarification', reason='Please specify one subject for each field list.', queries=[])
    return dict(status='expanded', fields=fields, entity=entity,
                queries=[_FIELDS[field].format(entity=entity) for field in fields])


class SpacyPromptBackend:
    """Lazy local CPU pipeline. No implicit downloads and no invented facts."""
    def __init__(self, model='en_core_web_sm', *, nlp=None):
        self.model = model
        self.nlp = nlp
        self.lock = threading.RLock()

    def annotate(self, text):
        with self.lock:
            if self.nlp is None:
                try:
                    import spacy
                    spacy.require_cpu()
                    self.nlp = spacy.load(self.model)
                except (ImportError, OSError) as error:
                    raise RuntimeError('Prompt NLP requires cpu-llm[prompt_nlp] and a local spaCy model. '
                                       'Run python -m spacy download en_core_web_sm during setup.') from error
            if not self.nlp.has_pipe('parser'):
                raise RuntimeError('Prompt NLP requires a spaCy dependency parser, not a blank tokenizer.')
            doc = self.nlp(text)
            spans = []
            chunks = list(doc.noun_chunks)
            candidates = []
            for chunk in chunks:
                spans.append(dict(kind='noun_phrase', text=chunk.text, start=chunk.start_char,
                                  end=chunk.end_char, role=chunk.root.dep_, head=chunk.root.head.text))
                if chunk.root.lemma_.casefold() in _FIELDS:
                    for prep in chunk.root.children:
                        if prep.lower_ != 'of' or prep.dep_ != 'prep':
                            continue
                        for entity in chunks:
                            if entity.root.head == prep:
                                candidates.append(dict(attribute_start=chunk.start_char, attribute_end=chunk.end_char,
                                                       entity_start=entity.start_char, entity_end=entity.end_char))
            for entity in doc.ents:
                spans.append(dict(kind='entity', label=entity.label_, text=entity.text,
                                  start=entity.start_char, end=entity.end_char))
            for token in doc:
                if token.dep_ == 'neg' or token.tag_ == 'MD':
                    spans.append(dict(kind='negation' if token.dep_ == 'neg' else 'modality',
                                      text=token.text, start=token.idx, end=token.idx + len(token.text)))
            return dict(backend='spacy', model=self.model, spans=spans[:MAX_ANNOTATIONS],
                        candidates=candidates[:MAX_ANNOTATIONS],
                        omitted_spans=max(0, len(spans)-MAX_ANNOTATIONS), role='unverified linguistic annotations')


class PromptInterpreter:
    def __init__(self, backend=None):
        self.automatic = backend in (None, 'auto')
        self.fallback_reason = None
        if self.automatic:
            # Discover local packages without importing a model or accessing the
            # network. Missing optional assets remain visible in diagnostics.
            try:
                available = all(importlib.util.find_spec(name) is not None for name in ('spacy', 'en_core_web_sm'))
            except (ImportError, ValueError):
                available = False
            backend = 'spacy' if available else 'rules'
            if not available:
                self.fallback_reason = 'spaCy or en_core_web_sm is not installed locally'
        if isinstance(backend, str):
            if backend not in {'rules', 'spacy'}:
                raise ValueError('prompt_backend must be auto, rules, spacy, or an annotation adapter')
            backend = SpacyPromptBackend() if backend == 'spacy' else None
        self.backend = backend

    def interpret(self, text: str) -> dict:
        from cpu_llm.semantic import request_contract
        from cpu_llm.prompt_intent import route_prompt
        from cpu_llm.output_rendering import extract_layout
        layout = extract_layout(text)
        original_input = text
        text = layout['content_query']
        result = normalize_question(text)
        annotations = self.backend.annotate(text) if self.backend is not None else dict(
            backend='rules', spans=[], role='unverified linguistic annotations')
        if result['status'] == 'unchanged':
            candidates = list(dict.fromkeys(query for item in annotations.get('candidates', [])
                                            if (query := _parser_query(text, item))))
            if len(candidates) == 1:
                result.update(query=candidates[0], status='normalized')
                result['transformations'].append(dict(rule='validated_dependency_attribute'))
        query = result['query']
        # A parser-backed information request may name several attributes. All
        # requested fields must survive planning, including unknown ones.
        prefix = _ANNOTATION_REQUEST.match(text)
        fields = expand_explicit_fields(query)
        named_field = any(span.get('kind') == 'noun_phrase' and
                          re.sub(r'^the\s+', '', span.get('text', ''), flags=re.I).casefold() in _FIELDS
                          for span in annotations.get('spans', []))
        if prefix and (annotations.get('candidates') or named_field):
            fields = expand_explicit_fields('Tell me ' + text[prefix.end():])
        if fields and fields['status'] == 'needs_clarification':
            result.update(status='needs_clarification', reason=fields['reason'])
        result['queries'] = fields['queries'] if fields and fields['status'] == 'expanded' else [query]
        contract = request_contract(query)
        intent = route_prompt(query)
        constraints = [dict(text=m[0], start=m.start(), end=m.end()) for m in
                       re.finditer(r"\b(?:not|never|without|except|unless|if|only|every|all|some|average|must|may|might)\b|\d+(?:\.\d+)?(?:\s+\w+)?", text, re.I)]
        result.update(schema=SCHEMA, request=contract.as_dict() if contract else None,
                      original_input=original_input, output_format=layout['format'], output_media=layout['output_media'],
                      channels=intent.get('channels', {}),
                      search_plan=dict(primary_query=query,
                          equivalent_queries=list(intent.get('dictionary', {}).get('variants') or [])[:1],
                          max_equivalent_queries=1, max_attribute_repairs=3),
                      constraints=constraints[:MAX_ANNOTATIONS],
                      omitted_constraints=max(0, len(constraints)-MAX_ANNOTATIONS),
                      annotations=annotations,
                      backend_policy='auto' if self.automatic else 'explicit',
                      fallback_reason=self.fallback_reason,
                      evidence_role='user request, not verified evidence')
        return result
