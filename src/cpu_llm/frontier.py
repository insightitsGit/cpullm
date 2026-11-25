"""Frontier: exhaustive, budgeted hypothesis search over one authorized snapshot.

``Frontier: <topic>.``, ``ask(..., frontier=True)`` or ``"frontier": true`` on
``/v1/ask`` run this route. The node reads one authorized snapshot, builds a
relation graph from the words and chunks related to the topic, and enumerates
every combination of relations that the graph allows (two- and optionally
three-edge chains, shared-target pairs and shared-source pairs). Candidates are
streamed in batches; the full candidate set is never materialized.

Each candidate passes three filters in order:

1. abductive check: its relations compose into a coherent explanatory relation
   between its anchors;
2. deductive check: its premises are exact source spans, no source negates a
   premise or the conclusion, the registered rule engine does not contradict
   it, and it receives a relevance score;
3. pre-thinker validation: it is not malformed, circular, single-source or a
   restatement of one source sentence.

Every survivor is an ``UNVERIFIED_HYPOTHESIS`` with ``promotion: blocked``. The
node never writes to the index. Strict evidence mode disables it.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
import hashlib
from itertools import combinations, islice
import json
import math
import re
import time

from cpu_llm.cycle_exploration import Budget, StopSearch
from cpu_llm.invention import NOTE

SCHEMA = 'frontier-v1'
CLAIM_STATUS = 'UNVERIFIED_HYPOTHESIS'
HARD_CAP = 50
STAGES = ['frontier_snapshot', 'frontier_generate', 'frontier_abductive', 'frontier_deductive',
          'frontier_pre_thinker', 'frontier_rank']
_MAX_PATHS = 5          # supporting paths kept per hypothesis
_MIN_ANCHORED = 10      # below this, background topic words also anchor
_MAX_TERM_WORDS = 6
_COMMAND = re.compile(r'^(?:please\s+)?frontier\s*:\s*(.*?)[\s.!?]*$', re.I | re.S)


# --------------------------------------------------------------------------- limits

@dataclass(frozen=True)
class FrontierLimits:
    """Budgets for one run. A round is one streamed batch of candidates."""
    max_rounds: int = 1000
    max_candidates: int = 200_000
    max_edges: int = 50_000
    max_bytes: int = 64 * 1024 * 1024
    max_seconds: float = 60.0
    batch_size: int = 256
    max_path_edges: int = 2
    max_results: int = HARD_CAP
    min_results: int = 10

    def __post_init__(self):
        for key, value in asdict(self).items():
            if key == 'max_seconds':
                if type(value) not in (int, float) or not math.isfinite(value) or not 0 < value <= 120:
                    raise ValueError('max_seconds must be finite and in (0, 120]')
            elif type(value) is not int or value < 1:
                raise ValueError(key + ' must be a positive integer')
        ceilings = dict(max_rounds=100_000, max_candidates=2_000_000, max_edges=200_000,
                        max_bytes=128 * 1024 * 1024, batch_size=10_000, max_path_edges=3,
                        max_results=HARD_CAP, min_results=HARD_CAP)
        for key, ceiling in ceilings.items():
            if getattr(self, key) > ceiling:
                raise ValueError(key + ' exceeds operator ceiling')
        if self.max_path_edges < 2:
            raise ValueError('max_path_edges must be 2 or 3')
        if self.min_results > self.max_results:
            raise ValueError('min_results cannot exceed max_results')


DEEPEN_TOP = 5     # leading entries checked by Deepen in an appliance run (0 turns the check off)


def validate_frontier_option(option):
    """Return None (not requested) or a dict with optional topic and limits."""
    if option is None or option is False:
        return None
    if option is True:
        return dict(topic=None, limits=FrontierLimits(), deepen_top=DEEPEN_TOP)
    if not isinstance(option, dict) or set(option) - {'topic', 'limits', 'deepen_top'}:
        raise ValueError('frontier must be a boolean or an object with optional topic, limits and deepen_top')
    deepen_top = option.get('deepen_top', DEEPEN_TOP)
    if type(deepen_top) is not int or not 0 <= deepen_top <= 10:
        raise ValueError('frontier.deepen_top must be an integer from 0 to 10')
    topic = option.get('topic')
    if topic is not None and (not isinstance(topic, str) or not topic.strip() or len(topic) > 240):
        raise ValueError('frontier.topic must be a short subject (1..240 characters)')
    limits = option.get('limits', {})
    if not isinstance(limits, dict) or set(limits) - set(FrontierLimits.__dataclass_fields__):
        raise ValueError('unknown frontier limit')
    return dict(topic=topic, limits=FrontierLimits(**limits), deepen_top=deepen_top)


def frontier_seed(message, *, forced=False):
    """Return the topic, ``''`` for a missing topic, or None for another route."""
    text = (message or '').strip()
    match = _COMMAND.fullmatch(text)
    if match:
        return match[1].strip()
    return text.rstrip('.!?').strip() if forced else None


# --------------------------------------------------------------------------- words

_DET = frozenset('''a an the this that these those its their our his her such some any each every all both
    either neither several various many much more most further other another own same current new key main
    major primary significant'''.split())
_PRONOUN = frozenset('it they this that these those which who we he she there one others something'.split())
_NOT_ADVERB = frozenset('supply assembly family anomaly monopoly apply reply rely ally italy july'.split())
_AUX = frozenset('do does did not can cannot will would may might could should must also'.split())
_ADVERB = re.compile(r'^(?:\w{3,}ly|also|now|often|already|still|further|even|thus|therefore|hence|then|currently|'
                     r'increasingly|ultimately|fundamentally|largely|mainly|primarily|generally|typically)$', re.I)
_TRAILING_BAD = frozenset('of for to in on at by with from and or but as than into over under'.split())
_STOPWORDS = None


def _stop():
    global _STOPWORDS
    if _STOPWORDS is None:
        from cpu_llm.channels import _STOP
        _STOPWORDS = _STOP | _DET | _TRAILING_BAD
    return _STOPWORDS


def _tokens(text):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’-]*", text)


def _strip_markup(text):
    """Drop Markdown heading and emphasis marks that an ingested title can carry."""
    return re.sub(r'^[#>*\s]+|[*_`]+', '', text).strip()


def _stem(token):
    word = token.casefold().replace('’', "'").removesuffix("'s")
    if len(word) > 4 and word.endswith('ies'):
        return word[:-3] + 'y'
    if len(word) > 3 and word.endswith('s') and not word.endswith(('ss', 'us', 'is', 'ics')):
        return word[:-1]
    return word


def _content(tokens):
    stop = _stop()
    return [_stem(t) for t in tokens
            if (_stem(t) not in stop and len(t) >= 3 and not t.isdigit()) or (t.isupper() and len(t) >= 2)]


def term_key(text):
    """Stable key for a term: stemmed tokens without determiners."""
    return ' '.join(_stem(t) for t in _tokens(text) if t.casefold() not in _DET)


_QUANTITY = re.compile(r'^(?:(?:vast|large|huge|massive|growing|increasing|significant|enormous)\s+)?'
                       r'(?:amounts?|quantities|quantity|levels?|volumes?|numbers?)\s+of\s+', re.I)


def _clean_term(tokens, *, keep='tail'):
    tokens = [t for t in tokens if t]
    def adverb(token):
        return bool(_ADVERB.match(token)) and token.casefold() not in _NOT_ADVERB

    while tokens and (tokens[0].casefold() in _DET or adverb(tokens[0])):
        tokens = tokens[1:]
    quantity = _QUANTITY.match(' '.join(tokens))
    if quantity:
        tokens = _tokens(' '.join(tokens)[quantity.end():])
    while tokens and (adverb(tokens[-1]) or tokens[-1].casefold() in _AUX):
        tokens = tokens[:-1]
    if len(tokens) > _MAX_TERM_WORDS:
        tokens = tokens[-_MAX_TERM_WORDS:] if keep == 'tail' else tokens[:_MAX_TERM_WORDS]
    return ' '.join(tokens)


# --------------------------------------------------------------------------- relation lexicon

_INCREASE = (r'increases?|increased|raises?|raised|drives?|drove|boosts?|boosted|accelerates?|accelerated|'
             r'amplifies|amplified|fuels?|fueled|fuelled|expands?|expanded|improves?|improved|enables?|enabled|'
             r'spurs?|spurred|consumes?|consumed|grows|intensifies|intensified|speeds? up|sped up|maximizes?|'
             r'doubles|doubled|triples|tripled|multiplies')
_DECREASE = (r'reduces?|reduced|lowers?|lowered|decreases?|decreased|cuts?|slows?|slowed|hinders?|hindered|'
             r'hampers?|hampered|impedes?|impeded|erodes?|eroded|offsets?|delays?|delayed|'
             r'mitigates?|mitigated|alleviates?|alleviated|saves?|saved|lessens?|shrinks?|minimizes?|minimized|'
             r'eliminates?|eliminated')
_CONSTRAIN = (r'limits?|constrains?|restricts?|caps?|bounds|bottlenecks?|throttles?|gates?|'
              r'determines?|governs?')
_REQUIRE = r'requires?|required|depends? on|depended on|relies? on|relied on|needs?|demands?'
_SCALES = r'scales? with|grows? with|rises? with|increases? with'
# Argument relations, for philosophical and theoretical prose.
_SUPPORT = (r'entails?|entailed|implies|implied|presupposes?|presupposed|supports?|supported|motivates?|motivated|'
            r'explains?|explained|vindicates?|vindicated|grounds')
_UNDERMINE = (r'undermines?|undermined|challenges?|challenged|refutes?|refuted|contradicts?|contradicted|'
              r'conflicts? with|(?:is|are) incompatible with|rules? out|ruled out|threatens?|threatened|'
              r'cannot explain|fails? to explain|failed to explain')
_CAUSE_VERB = (r'leads? to|led to|results? in|resulted in|contributes? to|contributed to|accounts? for|'
               r'gives? rise to|gave rise to|produces?|produced|emits?|emitted|(?:is|are) (?:an?|the) (?:\w+ )?'
               r'drivers? of')
_PASSIVE = (r'(?:is|are|was|were|remains?|remained|becomes?|became|has been|have been|will be|can be|may be)\s+'
            r'(?:\w+ly\s+)?(?P<pverb>limited|constrained|bottlenecked|bounded|driven|gated|capped|throttled|'
            r'slowed|hindered|hampered|reduced|increased|determined|dominated|governed|restricted|accelerated|'
            r'enabled|fueled|fuelled)\s+by')
_BOTTLENECK_NOUN = (r'(?:is|are|was|were|remains?|becomes?|has become|have become)\s+(?:an?|the|one of the)\s+'
                    r'(?:\w+\s+){0,2}?(?:bottlenecks?|constraints?|limiting factors?|binding constraints?)\s+'
                    r'(?:for|to|on|in|of)')
_CUE = re.compile(
    rf'\b(?:(?P<passive>{_PASSIVE})|(?P<noun>{_BOTTLENECK_NOUN})|(?P<scales>{_SCALES})|(?P<require>{_REQUIRE})|'
    rf'(?P<support>{_SUPPORT})|(?P<undermine>{_UNDERMINE})|(?P<cause>{_CAUSE_VERB})|(?P<increase>{_INCREASE})|(?P<decrease>{_DECREASE})|(?P<constrain>{_CONSTRAIN}))\b',
    re.I)
_PASSIVE_KIND = dict(limited='constrains', constrained='constrains', bottlenecked='constrains',
                     bounded='constrains', gated='constrains', capped='constrains', throttled='constrains',
                     determined='constrains', dominated='constrains', governed='constrains',
                     restricted='constrains', driven='increases', increased='increases',
                     accelerated='increases', enabled='increases', fueled='increases', fuelled='increases',
                     slowed='decreases', hindered='decreases', hampered='decreases', reduced='decreases')
_NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|without|cannot)\b|n't", re.I)
_HEDGE = re.compile(r'\b(?:may|might|could|would|should|likely|possibly|potentially|perhaps|suggests?|'
                    r'appears?|seems?|can)\b', re.I)
_CONDITIONAL = re.compile(r'\b(?:if|unless|whether)\b', re.I)
_SUBJECT_CUT = re.compile(r'[,;:()\[\]"“”]|\b(?:that|which|who|while|whereas|because|although|though|as|since|'
                          r'when|where|and|but|so|thus|hence|then|however)\b', re.I)
_OBJECT_CUT = re.compile(r'[,;:()\[\]"“”]|\b(?:and|but|which|that|who|while|whereas|because|as|by|through|via|'
                         r'due|when|where|if|unless|from|at|on|in|with|within|across|over|under|among|than|to|'
                         r'into|during|until|so|thus|whose|since|after|before|beyond|without|rather)\b', re.I)
_LOGICAL = frozenset({'supports', 'undermines'})
_CAUSAL = frozenset({'increases', 'decreases', 'constrains', 'causes'}) | _LOGICAL
_STRUCTURAL = frozenset({'is_a', 'alias_of', 'has'})
_VERB = dict(increases='increase', decreases='reduce', constrains='constrain', causes='contribute to',
             supports='support', undermines='undermine',
             affects='affect')


_NOUN_BEFORE = frozenset('a an the this that these those its their our of for to in on with by and or'.split())
_NOUN_AFTER = frozenset('is are was were has have had will can may of for to and or in on with that which by'.split())
_BAD_START = frozenset('of for to in on at by with from and or but as than into over under across about via '
                       'have has had been be is are was were do does did can will provide'.split())
_PARTICIPLE = frozenset('been led come garnered obtained become shown made seen grown achieved demonstrated '
                        'enabled attracted received gained'.split())
_WH_START = frozenset('what whose which who whom how why where when although though while whereas because '
                      'since unless'.split())
_CLAUSE = frozenset('have has had been is are was were be'.split())


def usable_term(term):
    """A term must be a noun phrase: no leading preposition or verb, no pronoun-only phrase."""
    tokens = [t.casefold() for t in _tokens(term)]
    if not tokens or tokens[0] in _BAD_START or tokens[0] in _PRONOUN or tokens[0] in _WH_START:
        return False
    if tokens[0] in {'no', 'none', 'neither', 'any', 'every', 'each'}:
        return False                                  # a quantifier phrase, not a named quantity
    if term.lstrip().startswith(('#', '>', '*')):
        return False
    if re.search(r'[^\x00-\x7f\u2019]', term) and len(tokens) == 1:
        return False                                  # a bare symbol such as a Greek variable
    return not _CLAUSE.intersection(tokens[1:])


def _noun_use(sentence, match):
    """True when an active cue word is used as a noun ("power demand is ...", "the limits of")."""
    if match['passive'] or match['noun']:
        return False
    before = _tokens(sentence[:match.start()])
    after = _tokens(sentence[match.end():])
    if not before:
        return True                              # a sentence-initial cue has no subject
    if before[-1].casefold() in _NOUN_BEFORE:
        return True
    following = sentence[match.end():].lstrip()
    return bool(after) and (after[0].casefold() in _NOUN_AFTER or bool(_CUE.match(following)))


def _cue_kind(match):
    if match['passive']:
        return _PASSIVE_KIND[match['pverb'].casefold()], True
    if match['noun']:
        return 'constrains', False
    if match['scales']:
        return 'increases', True
    if match['cause']:
        return 'causes', False
    if match['support']:
        return 'supports', False
    if match['undermine']:
        return 'undermines', False
    if match['require']:
        return 'constrains', True      # "A requires B": the supply of B bounds A.
    for kind in ('increase', 'decrease', 'constrain'):
        if match[kind]:
            return kind + 's', False
    raise AssertionError('unreachable')


def lexical_relations(sentence):
    """Yield (subject, kind, object, negative, hedged) for the first relation cue.

    The subject is the last noun phrase before the cue and the object is the
    first noun phrase after it. ``reverse`` cues (passive voice, *requires*,
    *scales with*) swap the two so that every edge reads cause -> effect.
    """
    if _CONDITIONAL.search(sentence) or len(sentence) > 1000:
        return
    negative_sentence = bool(_NEGATION.search(sentence))
    hedged = bool(_HEDGE.search(sentence))
    covary = _COVARY.search(sentence)
    if covary:
        effect = _clean_term(_tokens(_SUBJECT_CUT.split(covary['a'])[-1]), keep='tail')
        cause = _clean_term(_tokens(covary['b']), keep='tail')
        if effect and cause and usable_term(effect) and usable_term(cause):
            same = (covary['da'].casefold() in _UP) == (covary['db'].casefold() in _UP)
            yield cause, 'increases' if same else 'decreases', effect, negative_sentence, hedged
            return
    for match in _CUE.finditer(sentence):
        if _noun_use(sentence, match):
            continue
        kind, reverse = _cue_kind(match)
        before = _SUBJECT_CUT.split(sentence[:match.start()])[-1]
        after = _OBJECT_CUT.split(sentence[match.end():])[0]
        subject = _clean_term(_tokens(before), keep='tail')
        obj = _clean_term(_tokens(after), keep='head')
        if not subject or not obj or not usable_term(subject) or not usable_term(obj):
            continue
        negative = bool(_NEGATION.search(sentence[max(0, match.start() - 40):match.start()])
                        or _NEGATION.search(sentence[match.end():match.end() + 10]))
        if reverse:
            subject, obj = obj, subject
        yield subject, kind, obj, negative, hedged
        return


_UP = frozenset('increases increase rises rise grows grow climbs climb'.split())
_COVARY = re.compile(r'(?P<a>[\w\s\'’-]{3,80}?)\s+(?P<da>increases|rises|grows|climbs|decreases|falls|declines|drops)\s+'
                     r'as\s+(?P<b>[\w\s\'’-]{3,80}?)\s+(?P<db>increases|rises|grows|climbs|decreases|falls|declines|drops)\b',
                     re.I)


# --------------------------------------------------------------------------- dependency parser

# Lemma -> (kind, reverse, preposition). ``reverse`` swaps subject and object so that every edge reads
# cause -> effect; a preposition names the particle verb's object ("depends on X").
_VERB_LEMMAS = {
    **{v: ('constrains', False, None) for v in
       'limit constrain restrict cap bottleneck throttle gate determine govern'.split()},
    **{v: ('increases', False, None) for v in
       ('increase raise drive boost accelerate amplify fuel expand improve enable spur consume intensify '
        'maximize double triple multiply').split()},
    **{v: ('decreases', False, None) for v in
       ('reduce lower decrease cut slow hinder hamper impede erode offset delay mitigate alleviate save lessen '
        'shrink minimize eliminate').split()},
    **{v: ('causes', False, None) for v in 'cause produce emit'.split()},
    **{v: ('supports', False, None) for v in
       'entail imply presuppose support motivate explain vindicate ground'.split()},
    **{v: ('undermines', False, None) for v in 'undermine challenge refute contradict threaten'.split()},
    **{v: ('constrains', True, None) for v in 'require need'.split()},
    'depend': ('constrains', True, 'on'), 'rely': ('constrains', True, 'on'),
    'lead': ('causes', False, 'to'), 'result': ('causes', False, 'in'), 'contribute': ('causes', False, 'to'),
    'account': ('causes', False, 'for'), 'conflict': ('undermines', False, 'with'),
    'scale': ('increases', True, 'with'), 'grow': ('increases', True, 'with'),
}
_PASSIVE_LEMMAS = {v: kind for v, (kind, reverse, prep) in _VERB_LEMMAS.items() if prep is None and not reverse}
_PASSIVE_LEMMAS.update(dominate='constrains')
_PARSE_CUE = re.compile(
    r'\b(?:' + '|'.join(sorted({v[:5] if len(v) > 5 else v for v in _VERB_LEMMAS}, key=len, reverse=True)) + r')'
    r'|\bincompatible with\b|\brules? out\b|\bruled out\b'
    r'|\b(?:is|are) (?:an? |the )?(?:form|kind|type|species|version|consequence|product) of\b'
    r'|\bconsists? in\b|\b(?:is|are) identical (?:to|with)\b|\b(?:is|are) nothing (?:but|over and above)\b',
    re.I)
_NP_DEPS = frozenset({'compound', 'amod', 'nmod', 'poss', 'det', 'nummod', 'quantmod', 'npadvmod'})
_PARSER = None
_PARSER_NAME = 'regex'


def parser():
    """The spaCy pipeline used for dependency relations, or None for the regex fallback.

    ``FRONTIER_PARSER`` names a model, or ``regex`` forces the fallback. The default prefers
    ``en_core_web_lg`` and then ``en_core_web_sm`` (the optional ``prompt_nlp`` dependency).
    """
    global _PARSER, _PARSER_NAME
    import os
    wanted = os.environ.get('FRONTIER_PARSER', 'auto')
    if wanted == 'regex':
        return None
    if _PARSER is not None and wanted in ('auto', _PARSER_NAME):
        return _PARSER
    import warnings
    try:
        import spacy
    except ImportError:
        return None
    for name in ([wanted] if wanted != 'auto' else ['en_core_web_lg', 'en_core_web_sm']):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                _PARSER = spacy.load(name, disable=['ner'])
            _PARSER_NAME = name
            return _PARSER
        except (OSError, ImportError):
            continue
    return None


def parser_name():
    return _PARSER_NAME if parser() is not None else 'regex'


def _phrase(token):
    """A noun phrase around ``token``: its modifiers and at most one ``of``/``for`` complement.

    A phrase headed by a person's name (an author such as "Eliya Nachmani") names no variable and is dropped.
    """
    if token.ent_type_ == 'PERSON':
        return ''
    left = []

    def gather(node):
        for child in node.lefts:
            if child.dep_ in _NP_DEPS:
                left.append(child)
                gather(child)
    gather(token)
    phrase = [t.text for t in sorted([*left, token], key=lambda t: t.i)]
    for child in token.rights:
        if child.dep_ == 'prep' and child.lower_ in {'of', 'for'}:
            objects = [c for c in child.children if c.dep_ == 'pobj']
            if objects:
                phrase += [child.text, *_phrase(objects[0]).split()]
            break
    return _clean_term([w for w in phrase if w not in {'#', '*', '>'}], keep='head')


def _conjoined(token):
    return [token, *[t for t in token.conjuncts if t.pos_ in {'NOUN', 'PROPN'}]]


def _prep_objects(node, prepositions):
    return [g for c in node.children if c.dep_ == 'prep' and c.lower_ in prepositions
            for g in c.children if g.dep_ == 'pobj']


def parsed_relations(doc):
    """Yield (subject, kind, object, negative, hedged) from one parsed sentence."""
    text = doc.text
    if text.rstrip().endswith('?') or len(text) > 1000:
        return
    hedged = bool(_HEDGE.search(text))
    for token in doc:
        if token.pos_ not in {'VERB', 'AUX'}:
            continue
        children = list(token.children)
        if any(c.dep_ == 'mark' and c.lower_ in {'if', 'unless', 'whether'} for c in children):
            continue
        negative = any(c.dep_ == 'neg' for c in children) or any(
            g.dep_ in {'det', 'preconj', 'neg'} and g.lower_ in {'neither', 'no', 'nor', 'none'}
            for c in children if c.dep_ in {'nsubj', 'nsubjpass', 'dobj'} for g in c.children)
        lemma = token.lemma_.casefold()
        passive_subject = next((c for c in children if c.dep_ in {'nsubjpass', 'nsubj:pass'}), None)
        if passive_subject is not None:
            if lemma in _PASSIVE_LEMMAS:
                for cause in _prep_objects(next((c for c in children if c.dep_ == 'agent'), token), {'by'}) or [
                        g for c in children if c.dep_ == 'agent' for g in c.children if g.dep_ == 'pobj']:
                    for effect in _conjoined(passive_subject):
                        for source in _conjoined(cause):
                            a, b = _phrase(source), _phrase(effect)
                            if a and b and usable_term(a) and usable_term(b):
                                yield a, _PASSIVE_LEMMAS[lemma], b, negative, hedged
            continue
        subject = next((c for c in children if c.dep_ == 'nsubj'), None)
        if subject is None and token.dep_ == 'conj' and token.head.pos_ in {'VERB', 'AUX'}:
            subject = next((c for c in token.head.children if c.dep_ == 'nsubj'), None)
        clause = next((c for c in children if c.dep_ == 'csubj'), None) if subject is None else None
        if subject is None and clause is None:
            continue
        objects, kind, reverse = [], None, False
        if lemma in _VERB_LEMMAS:
            kind, reverse, preposition = _VERB_LEMMAS[lemma]
            objects = ([c for c in children if c.dep_ in {'dobj', 'obj'}] if preposition is None
                       else _prep_objects(token, {preposition}))
            if lemma == 'rule' and not any(c.dep_ == 'prt' and c.lower_ == 'out' for c in children):
                kind = None
        elif lemma == 'rule' and any(c.dep_ == 'prt' and c.lower_ == 'out' for c in children):
            kind, objects = 'undermines', [c for c in children if c.dep_ in {'dobj', 'obj'}]
        elif lemma == 'consist':
            kind, objects = 'alias_of', _prep_objects(token, {'in'})
        elif lemma == 'be':
            attribute = next((c for c in children if c.dep_ in {'attr', 'acomp'}), None)
            if attribute is not None:
                word = attribute.lower_
                if word in {'form', 'kind', 'type', 'species', 'version', 'consequence', 'product'}:
                    kind, objects = 'is_a', _prep_objects(attribute, {'of'})
                elif word == 'nothing':
                    kind, objects = 'alias_of', _prep_objects(attribute, {'but'})
                elif word == 'incompatible':
                    kind, objects = 'undermines', _prep_objects(attribute, {'with'})
                elif word == 'identical':
                    kind, objects = 'alias_of', _prep_objects(attribute, {'to', 'with'})
        if kind is None or not objects:
            continue
        subjects = ([_clean_term([t.text for t in clause.subtree][:_MAX_TERM_WORDS], keep='head')]
                    if clause is not None else [_phrase(t) for t in _conjoined(subject)])
        for a_phrase in subjects:
            for right in (o for obj in objects for o in _conjoined(obj)):
                a, b = a_phrase, _phrase(right)
                if reverse:
                    a, b = b, a
                if a and b and usable_term(a) and usable_term(b):
                    yield a, kind, b, negative, hedged


def sentence_relations(sentences):
    """Relations per sentence: the dependency parser where available, otherwise the regex reader."""
    nlp = parser()
    if nlp is None:
        return [list(lexical_relations(s)) for s in sentences]
    results = [[] for _ in sentences]
    wanted = [i for i, s in enumerate(sentences) if _PARSE_CUE.search(s) and not _CONDITIONAL.search(s)]
    for index, doc in zip(wanted, nlp.pipe([sentences[i] for i in wanted], batch_size=128)):
        results[index] = list(dict.fromkeys(parsed_relations(doc)))
    return results


# --------------------------------------------------------------------------- relation graph

def source_of(document_id):
    """The source document of a paragraph id (``notes-p0003`` -> ``notes``)."""
    from cpu_llm.source_ids import is_paragraph_id, prefix_of
    return prefix_of(document_id) if is_paragraph_id(document_id) else document_id


@dataclass
class Edge:
    id: str
    subject: str
    subject_key: str
    kind: str
    object: str
    object_key: str
    anchored: bool
    proofs: list
    hedged: bool
    quantitative: bool
    origin: str

    def documents(self):
        """Distinct source documents (paragraphs of one file count once)."""
        return list(dict.fromkeys(source_of(p['document_id']) for p in self.proofs))


def _proof(row, sentence, chunk_hash):
    start = row['chunk_text'].find(sentence)
    if start < 0:
        return None
    return dict(document_id=row['document_id'], quote=sentence, start=start, end=start + len(sentence),
                chunk_sha256=chunk_hash)


class RelationGraph:
    """Edges from the authorized snapshot, plus a sentence index for the filters."""

    def __init__(self):
        self.edges = {}
        self.negatives = {}                    # (subject_key, relation, object_key) -> exact proofs
        self.signs = {}                        # (subject_key, object_key) -> {kind}
        self.sentences = []                    # (document_id, set of stems, has_cue)
        self.postings = {}                     # stem -> set(sentence index)
        self.chunk_postings = {}               # stem -> set(document_id)
        self.document_frequency = Counter()
        self.chunk_count = 0
        self.complete = True
        self.stop_reason = None

    def add(self, subject, kind, obj, row, sentence, chunk_hash, *, hedged, origin, budget):
        from cpu_llm.abductive_bridge import _first_bound
        skey, okey = term_key(subject), term_key(obj)
        if not skey or not okey:
            return
        proof = _proof(row, sentence, chunk_hash)
        if proof is None:
            return
        identity = (skey, kind, okey)
        edge = self.edges.get(identity)
        if edge is None:
            budget.charge('edges')
            budget.charge('bytes', 256 + len(sentence) + len(subject) + len(obj))
            edge_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:16]
            edge = self.edges[identity] = Edge(edge_id, subject, skey, kind, obj, okey, False, [], True,
                                               False, origin)
        elif any(p['document_id'] == proof['document_id'] and p['quote'] == sentence for p in edge.proofs):
            return
        else:
            budget.charge('bytes', 128 + len(sentence))
        edge.proofs.append(proof)
        edge.hedged = edge.hedged and hedged     # one assertive statement is enough
        edge.quantitative = edge.quantitative or _first_bound(sentence) is not None
        self.signs.setdefault((skey, okey), set()).add(kind)

    def add_negative(self, subject, kind, obj, row, sentence, chunk_hash, budget):
        proof = _proof(row, sentence, chunk_hash)
        if proof is None:
            return
        identity = (term_key(subject), kind, term_key(obj))
        if not identity[0] or not identity[2]:
            return
        proofs = self.negatives.get(identity)
        if proofs is not None and proof in proofs:
            return
        if proofs is None:
            budget.charge('edges')
            proofs = self.negatives[identity] = []
        budget.charge('bytes', 256 + len(sentence))
        proofs.append(proof)

    def term_sentences(self, key):
        stems = [s for s in key.split() if s not in _stop()] or key.split()
        sets = [self.postings.get(s, set()) for s in stems]
        return set.intersection(*sets) if sets else set()

    def term_chunks(self, key):
        stems = [s for s in key.split() if s not in _stop()] or key.split()
        sets = [self.chunk_postings.get(s, set()) for s in stems]
        return set.intersection(*sets) if sets else set()


_RELATION_CACHE = {}
_RELATION_CACHE_LIMIT = 50_000


def _cached_relations(chunk_hash, sentences):
    """Relations for one chunk, cached by its SHA-256 and the active parser (text-derived, never stale)."""
    key = (chunk_hash, parser_name())
    found = _RELATION_CACHE.get(key)
    if found is None:
        found = sentence_relations(sentences)
        if len(_RELATION_CACHE) >= _RELATION_CACHE_LIMIT:
            _RELATION_CACHE.clear()
        _RELATION_CACHE[key] = found
    return found


def build_graph(rows, budget):
    from cpu_llm.answerability import _sentences
    from cpu_llm.knowledge_graph import extract_facts

    graph = RelationGraph()
    graph.chunk_count = len(rows)
    graph.origin = 'dependency_parse' if parser() is not None else 'frontier_lexicon'
    try:
        for row in rows:
            budget.check()
            chunk = row['chunk_text']
            chunk_hash = hashlib.sha256(chunk.encode()).hexdigest()
            seen = set()
            sentences = _sentences(chunk)
            for sentence, relations in zip(sentences, _cached_relations(chunk_hash, sentences)):
                stems = set(_content(_tokens(sentence)))
                index = len(graph.sentences)
                graph.sentences.append((row['document_id'], stems, bool(relations)))
                for stem in stems:
                    graph.postings.setdefault(stem, set()).add(index)
                    graph.chunk_postings.setdefault(stem, set()).add(row['document_id'])
                seen |= stems
                for subject, kind, obj, negative, hedged in relations:
                    if negative:
                        graph.add_negative(subject, kind, obj, row, sentence, chunk_hash, budget)
                        continue
                    graph.add(subject, kind, obj, row, sentence, chunk_hash, hedged=hedged,
                              origin=graph.origin, budget=budget)
            graph.document_frequency.update(seen)
            # Reuse the shared typed-fact extractor for causal and taxonomy edges. Its patterns are regular
            # expressions; with the dependency parser active, the parser reads these forms itself.
            for fact in (extract_facts(row['document_id'], chunk) if graph.origin == 'frontier_lexicon' else ()):
                if fact.relation not in {'causes', 'is_a', 'alias_of', 'has'} or len(fact.sentence) > 1000:
                    continue
                subject = _clean_term(_tokens(fact.subject))
                obj = _clean_term(_tokens(_OBJECT_CUT.split(fact.object)[0]), keep='head')
                if usable_term(subject) and usable_term(obj) and _tokens(obj)[0].casefold() not in _PARTICIPLE:
                    graph.add(subject, fact.relation, obj, row, fact.sentence, chunk_hash,
                              hedged=bool(_HEDGE.search(fact.sentence)), origin='knowledge_graph', budget=budget)
    except StopSearch as exc:
        graph.complete, graph.stop_reason = False, str(exc)
    return graph


def topic_focus(topic, graph):
    """Topic stems that discriminate within this snapshot.

    A stem that appears in more than half of the chunks is background for this
    corpus (for example ``AI`` in an AI-only namespace) and does not scope.
    """
    stems = list(dict.fromkeys(_content(_tokens(topic))))
    present = [s for s in stems if graph.document_frequency.get(s)]
    background = {s for s in present if graph.chunk_count and graph.document_frequency[s] > graph.chunk_count / 2}
    focus = [s for s in present if s not in background]
    return stems, present, focus or present


def scope_edges(graph, focus):
    """Edges anchored on the topic, plus the edges one relation away from them."""
    edges = sorted(graph.edges.values(), key=lambda e: (e.subject_key, e.kind, e.object_key))
    if not focus:
        for edge in edges:
            edge.anchored = True
        return edges
    focus = set(focus)
    for edge in edges:
        words = set(edge.subject_key.split()) | set(edge.object_key.split())
        quoted = any(focus & set(_content(_tokens(p['quote']))) for p in edge.proofs)
        edge.anchored = bool(focus & words) or quoted
    terms = {key for edge in edges if edge.anchored for key in (edge.subject_key, edge.object_key)}
    return [edge for edge in edges if edge.anchored or edge.subject_key in terms or edge.object_key in terms]


# --------------------------------------------------------------------------- generation

@dataclass
class Candidate:
    pattern: str            # chain | convergent | divergent
    edges: tuple


_GENERIC_HEAD = frozenset('model ai system method approach result work paper task application technique way '
                          'problem number amount use process framework study analysis one time year factor '
                          'performance case value'.split())


def term_head(key):
    """The head noun of a term key: the last content word before a prepositional phrase."""
    words = key.split()
    for index, word in enumerate(words):
        if word in ('of', 'for', 'in', 'on') and index:
            words = words[:index]
            break
    content = [w for w in words if w not in _stop()]
    return content[-1] if content else (words[-1] if words else '')


def related(left, right):
    """1.0 for the same term, 0.8 for terms that share a head noun, otherwise None.

    A generic head (``model``, ``system``) also needs one more shared content word.
    """
    if left == right:
        return 1.0
    head = term_head(left)
    if not head or head != term_head(right):
        return None
    if head in _GENERIC_HEAD and not (set(left.split()) & set(right.split())) - {head} - _stop():
        return None
    return 0.8


def generate(edges, limits):
    """Yield every relation combination that contains a topic-anchored edge.

    Edges meet at a shared head noun. No preference ordering or pruning is
    applied; the order is the stable lexical order of heads, so runs over the
    same snapshot are repeatable.
    """
    out, into = {}, {}
    for edge in edges:
        out.setdefault(term_head(edge.subject_key), []).append(edge)
        into.setdefault(term_head(edge.object_key), []).append(edge)
    for head in sorted(set(out) & set(into)):
        for first in into[head]:
            for second in out[head]:
                if second is first:
                    continue
                if first.anchored or second.anchored:
                    yield Candidate('chain', (first, second))
                if limits.max_path_edges >= 3:
                    for third in out.get(term_head(second.object_key), ()):
                        if third is not first and third is not second and (
                                first.anchored or second.anchored or third.anchored):
                            yield Candidate('chain', (first, second, third))
    for head in sorted(into):
        for first, second in combinations(into[head], 2):
            if first.anchored or second.anchored:
                yield Candidate('convergent', (first, second))
    for head in sorted(out):
        for first, second in combinations(out[head], 2):
            if first.anchored or second.anchored:
                yield Candidate('divergent', (first, second))


def batches(stream, size, budget):
    """Stream candidates in rounds; each round is charged to the budget."""
    while True:
        budget.check()
        batch = list(islice(stream, size))
        if not batch:
            return
        budget.charge('rounds')
        budget.charge('candidates', len(batch))
        yield batch


# --------------------------------------------------------------------------- filters

def _sign(kind):
    return {'increases': 1, 'causes': 1, 'decreases': -1, 'supports': 1, 'undermines': -1}.get(kind)


def compose(left, right):
    """Compose two relation kinds into (kind, certainty), or None if incoherent."""
    if left in {'is_a', 'alias_of'} and right in _CAUSAL | {'affects'}:
        return right, 1.0 if left == 'alias_of' else 0.9
    if left == 'has' and right in _CAUSAL | {'affects'}:
        return 'affects', 0.6
    if right == 'alias_of' and left in _CAUSAL | {'affects'}:
        return left, 1.0
    if left not in _CAUSAL | {'affects'} or right not in _CAUSAL | {'affects'}:
        return None
    if 'affects' in (left, right):
        return 'affects', 0.6
    if left in _LOGICAL and right in _LOGICAL:
        # Support passes support along; support then undermining undermines; two underminings do not cancel.
        if left == right == 'undermines':
            return 'affects', 0.5
        return ('supports' if _sign(left) * _sign(right) > 0 else 'undermines'), 1.0
    if left in _LOGICAL or right in _LOGICAL:
        return 'affects', 0.6
    ls, rs = _sign(left), _sign(right)
    if ls is not None and rs is not None:
        certainty = 0.95 if 'causes' in (left, right) else 1.0
        return ('increases' if ls * rs > 0 else 'decreases'), certainty
    if left == right == 'constrains':
        return 'constrains', 1.0
    if left == 'constrains' and rs == 1:
        return 'constrains', 0.85
    return 'affects', 0.7


BRIDGE_SIMILARITY = 0.6     # cosine a head-noun bridge needs when an encoder is available


@dataclass(frozen=True)
class _Term:
    key: str
    surface: str


def _bridge(left, right, similar):
    """Certainty of joining two terms: 1.0 if equal; else the encoder cosine (0.8 without an encoder)."""
    base = related(left.key, right.key)
    if base is None or base == 1.0 or similar is None:
        return base
    score = similar(left.surface, right.surface)
    return None if score is None or score < BRIDGE_SIMILARITY else round(min(score, 0.95), 3)


def abductive_check(candidate, similar=None):
    """The candidate must form a coherent explanatory relation between its anchors.

    With ``similar(a, b)`` (encoder cosine), a bridge between two different terms that share a head noun
    must also be close in meaning.
    """
    edges = candidate.edges
    if not any(edge.kind in _CAUSAL for edge in edges):
        return None, 'no_explanatory_relation'
    if candidate.pattern == 'chain':
        kind, certainty, via = edges[0].kind, 1.0, []
        for previous, edge in zip(edges, edges[1:]):
            bridge = _bridge(_Term(previous.object_key, previous.object), _Term(edge.subject_key, edge.subject),
                             similar)
            if bridge is None:
                return None, 'unrelated_bridge'
            certainty *= bridge
            via.append(previous.object if bridge == 1.0 else f'{previous.object} (read as {edge.subject})')
            step = compose(kind, edge.kind)
            if step is None:
                return None, 'incoherent_composition'
            kind, part = step
            certainty *= part
        certainty *= 0.9 ** (len(edges) - 2)
        if kind not in _CAUSAL | {'affects'}:
            return None, 'incoherent_composition'
        return dict(relation=kind, certainty=certainty,
                    anchors=(edges[0].subject, edges[-1].object),
                    keys=(edges[0].subject_key, edges[-1].object_key),
                    via=via, same_quantity=any('(read as' in item for item in via),
                    hub=edges[0].object_key), None
    first, second = edges
    if first.kind not in _CAUSAL or second.kind not in _CAUSAL:
        return None, 'no_explanatory_relation'
    shared = (_bridge(_Term(first.object_key, first.object), _Term(second.object_key, second.object), similar)
              if candidate.pattern == 'convergent' else
              _bridge(_Term(first.subject_key, first.subject), _Term(second.subject_key, second.subject), similar))
    if shared is None:
        return None, 'unrelated_bridge'
    if candidate.pattern == 'convergent':
        signs = {_sign(first.kind), _sign(second.kind)}
        if {first.kind, second.kind} <= _LOGICAL:
            relation = {frozenset({'supports'}): 'jointly_support', frozenset({'undermines'}): 'jointly_undermine'}.get(
                frozenset({first.kind, second.kind}), 'contested')
            return dict(relation=relation, certainty=0.85 * shared, anchors=(first.subject, second.subject, first.object),
                        keys=(first.subject_key, second.subject_key, first.object_key), via=[],
                        same_quantity=shared < 1.0), None
        if {first.kind, second.kind} <= {'constrains', 'decreases'}:
            relation, certainty = 'co_constrain', 0.9
        elif signs == {1, -1}:
            relation, certainty = 'offset', 0.85
        elif signs == {1}:
            relation, certainty = 'jointly_drive', 0.85
        else:
            relation, certainty = 'jointly_affect', 0.7
        return dict(relation=relation, certainty=certainty * shared, anchors=(first.subject, second.subject, first.object),
                    keys=(first.subject_key, second.subject_key, first.object_key), via=[],
                    same_quantity=shared < 1.0), None
    relation = 'common_ground' if {first.kind, second.kind} <= _LOGICAL else 'common_driver'
    return dict(relation=relation, certainty=0.8 * shared, anchors=(first.object, second.object, first.subject),
                keys=(first.object_key, second.object_key, first.subject_key), via=[],
                same_quantity=shared < 1.0), None


class DeductiveContext:
    """Snapshot-local state for the deductive check (premise spans and rule engine)."""

    def __init__(self, rows, graph, focus):
        self.chunks = {row['document_id']: row['chunk_text'] for row in rows}
        self.hashes = {doc: hashlib.sha256(text.encode()).hexdigest() for doc, text in self.chunks.items()}
        self.graph = graph
        self.focus = set(focus)
        self._rules = None
        self._rows = rows
        self._verdicts = {}

    def rules(self):
        if self._rules is None:
            from cpu_llm.inference import PreparedInference
            try:
                self._rules = PreparedInference(self._rows)
            except ValueError:
                self._rules = False
        return self._rules

    def rule_verdict(self, subject, relation, obj):
        """Run the registered rule engine on a compatible conclusion; None if not applicable."""
        key = (subject, relation, obj)
        if key not in self._verdicts:
            verdict = None
            prepared = self.rules()
            if prepared and prepared.facts:
                from cpu_llm.inference import InferenceRequest
                try:
                    verdict = prepared.deduce(InferenceRequest(subject, relation, obj))['verdict']
                except ValueError:
                    verdict = None
            self._verdicts[key] = verdict
        return self._verdicts[key]

    def verified(self, proof):
        chunk = self.chunks.get(proof['document_id'])
        return (chunk is not None and self.hashes[proof['document_id']] == proof['chunk_sha256']
                and chunk[proof['start']:proof['end']] == proof['quote'])


def _opposes(kinds, kind):
    sign = _sign(kind)
    return sign is not None and any(_sign(other) == -sign for other in kinds)


def deductive_check(candidate, reading, context):
    """Premises are verified spans, nothing negates them, and the conclusion is not contradicted."""
    graph = context.graph
    for edge in candidate.edges:
        if not all(context.verified(proof) for proof in edge.proofs):
            return None, 'premise_not_verified'
        if (edge.subject_key, edge.kind, edge.object_key) in graph.negatives:
            return None, 'premise_contradicted'
        if _opposes(graph.signs.get((edge.subject_key, edge.object_key), ()), edge.kind):
            return None, 'premise_contradicted'
    keys = reading['keys']
    if candidate.pattern == 'chain':
        pair = (keys[0], keys[1])
        if (pair[0], reading['relation'], pair[1]) in graph.negatives or _opposes(graph.signs.get(pair, ()), reading['relation']):
            return None, 'conclusion_contradicted'
        if reading['relation'] == 'constrains':
            verdict = context.rule_verdict(reading['anchors'][1], 'requires', reading['anchors'][0])
            if verdict in {'CONFLICT', 'CONTRADICTED_BY_RULES'}:
                return None, 'rule_contradiction'
            reading['rule_verdict'] = verdict
    else:
        a, b, hub = keys
        pairs = [(a, hub), (b, hub)] if candidate.pattern == 'convergent' else [(hub, a), (hub, b)]
        if any((e.subject_key, e.kind, e.object_key) in graph.negatives for e in candidate.edges):
            return None, 'conclusion_contradicted'
    # Relevance: how certain the composition is, and how closely it fits the topic.
    terms = set(' '.join(keys).split()) | {w for edge in candidate.edges for w in edge.subject_key.split()}
    quotes = set()
    for edge in candidate.edges:
        quotes |= set(_content(_tokens(edge.proofs[0]['quote'])))
    focus = context.focus
    term_fit = len(focus & terms) / len(focus) if focus else 1.0
    quote_fit = len(focus & quotes) / len(focus) if focus else 1.0
    base = 0.5 * reading['certainty'] + 0.3 * quote_fit + 0.2 * term_fit
    # Specificity: terms found in many chunks ("brain", "compute", "training") explain little. Scale the
    # relevance by the mean specificity of the anchors, 1 - log(1 + chunks with the term) / log(1 + all chunks).
    reading['specificity'] = round(_specificity(graph, keys), 3)
    reading['deductive_relevance'] = round(base * (0.6 + 0.4 * reading['specificity']), 3)
    return reading, None


def _specificity(graph, keys):
    total = max(graph.chunk_count, 1)
    values = [1.0 - math.log1p(len(graph.term_chunks(key))) / math.log1p(total) for key in keys if key]
    return max(0.0, min(1.0, sum(values) / len(values))) if values else 1.0


_VAGUE = frozenset("""associated somewhat such way case thing part lot year month day week time factor value result
    number amount level kind type aspect set use order fact example instance respect term half rest end top method
    approach technique work paper study edition ingredient enhancement condition impact similar increase behavior
    behaviour match combination discrepancy occurrence observation finding phenomenon situation""".split())
_BARE_ADJECTIVE = frozenset('''regulatory associated facilitated similar various different important significant
    relevant available possible effective efficient large small high low new recent current technical economic
    environmental computational sufficient necessary critical key global local general specific overall'''.split())
_ED_NOUN = frozenset('speed need seed feed bed shed embed'.split())
_CONJUNCTION_START = frozenset('because since although though while whereas unless whether'.split())
_QUANTIFIER_START = frozenset('none no all some each one any most few several'.split())
_COMPARATIVE = frozenset('larger smaller higher lower faster slower better worse greater fewer more less bigger '
                         'longer shorter cheaper newer older'.split())
_NUMBER_WORD = frozenset('one two three four five six seven eight nine ten hundred thousand million billion'.split())


_HEADER = re.compile(r'^\s*(?:(?:[A-Z]|[IVXL]{1,5}|\d{1,2}(?:\.\d{1,2}){0,3})\.\s+[A-Z]|\d{1,2}(?:\.\d{1,2}){1,3}\s+[A-Z]|'
                     r'(?:Fig|Figs|Figure|Table|Tab|Sec|Section|Appendix|Eq|Eqs|Equation|Ref|Refs)\b\.?)')
_INITIAL_NAME = re.compile(r'\b[A-Z]\.\s?(?:[A-Z]\.\s?)?[A-Z][a-z]{2,}\b')
_JOINED = ('the', 'of', 'to', 'our', 'and')
_META_HEAD = frozenset('''issue issues result results definition definitions implication implications advance advances
    former latter remainder literature research'''.split())
_META_START = frozenset('recent previous our this these'.split())
_COMPARATOR = re.compile(r'^\s*(?:less|more|fewer|greater)\s+than\s+[\d.]|^\s*(?:at\s+(?:least|most)|up\s+to)\s+[\d.]',
                         re.I)
_PARTITIVE = re.compile(r'^\s*(?:the\s+)?(?:majority|minority|fraction|portion|proportion|bulk|most|part)\s+of\b',
                        re.I)


def artefact_reason(term):
    """Why ``term`` is a document artefact rather than a variable, or None.

    Catches section headers ("D. Implications for Future Processors"), figure and table labels, initial-plus-surname
    author names ("S. Bravyi"), words merged by text extraction ("Tothebestofour"), meta nouns ("issues",
    "definition", "Recent experiments"), bare comparator quantities ("less than 10 mEh") and partitive phrases
    ("majority of error").
    """
    if not isinstance(term, str) or not term.strip():
        return None
    if re.fullmatch(r'\s*(?:[A-Z]\.\s?){1,2}[A-Z][a-z]+(?:[- ][A-Z][a-z]+)?\s*', term):
        return 'author_name'          # "S. Bravyi": initials and a surname, nothing else
    if _HEADER.search(term):
        return 'header'               # "D. Implications for Future Processors", "3.2 Noise model", "Fig. 3"
    if _INITIAL_NAME.search(term):
        return 'author_name'
    for token in re.findall(r'[A-Za-z]+', term):
        lowered = token.casefold()
        # Text extraction can drop spaces ("Tothebestofour"); a real long word rarely embeds "of" plus another
        # function word ("photothermal" embeds "to" and "the" but not "of").
        if len(lowered) >= 12 and ('of' in lowered or 'our' in lowered) and sum(w in lowered for w in _JOINED) >= 2:
            return 'merged_words'
    if _COMPARATOR.search(term):
        return 'comparator_quantity'
    if _PARTITIVE.search(term):
        return 'partitive'
    words = [t.casefold() for t in _tokens(term)]
    if words and (words[0] in _META_START and len(words) <= 3 or words[-1] in _META_HEAD
                  or ' '.join(words[:3]) == 'line of work'):
        return 'meta_noun'
    return None


def _malformed(term):
    """A broken, vague or truncated phrase cannot anchor a hypothesis."""
    tokens = _tokens(term)
    if not tokens or len(tokens) > _MAX_TERM_WORDS or len(term) > 80:
        return True
    lowered = [t.casefold() for t in tokens]
    if lowered[-1] in _TRAILING_BAD | _DET or lowered[0] in _TRAILING_BAD or lowered[-1] == 'such':
        return True
    if all(t in _PRONOUN for t in lowered) or lowered[0] in _PRONOUN:
        return True
    if lowered[0] in _QUANTIFIER_START and len(lowered) > 1 and lowered[1] in {'of', 'these', 'those', 'the'}:
        return True
    if lowered[0].isdigit() or lowered[0] in _NUMBER_WORD and len(lowered) <= 3:
        return True                                   # a count or a time span, not a quantity
    if any(len(t) == 1 and t not in {'a', 'k', 'x'} for t in lowered[1:]):
        return True                                   # text extraction broke a word ("speci c")
    if any(re.match(r'^\d+[a-z]', t) for t in lowered):
        return True                                   # a footnote marker glued to a word
    if len(lowered) == 1 and (lowered[0] in _COMPARATIVE | _BARE_ADJECTIVE
                              or lowered[0].endswith('ed') and lowered[0] not in _ED_NOUN):
        return True                                   # a bare adjective or participle names no quantity
    if lowered[0] in _CONJUNCTION_START:
        return True
    content = _content(tokens)
    if not content or all(word in _VAGUE for word in content):
        return True
    return term_head(term_key(term)) in _VAGUE


def _contains(left, right):
    a, b = left.split(), right.split()
    if not a or not b:
        return False
    short, long = (a, b) if len(a) <= len(b) else (b, a)
    return any(long[i:i + len(short)] == short for i in range(len(long) - len(short) + 1))


def pre_thinker_check(candidate, reading, graph):
    """Reject malformed, circular, single-source or restated candidates."""
    terms = [term for edge in candidate.edges for term in (edge.subject, edge.object)]
    if any(artefact_reason(term) for term in terms):
        return None, 'artefact'
    if any(_malformed(term) for term in terms):
        return None, 'malformed'
    keys = reading['keys']
    if candidate.pattern == 'chain':
        path = [candidate.edges[0].subject_key] + [edge.object_key for edge in candidate.edges]
        if len(set(path)) != len(path) or any(_contains(x, y) for x, y in combinations(path, 2)):
            return None, 'circular'
    elif keys[0] == keys[1] or _contains(keys[0], keys[1]) or any(_contains(k, keys[2]) for k in keys[:2]):
        return None, 'circular'
    documents = {source_of(p['document_id']) for edge in candidate.edges for p in edge.proofs}
    if len(documents) < 2:
        return None, 'single_source'
    # A sentence that names both ends of the reading and carries a relation cue
    # may already state it. Abstain, as the invention node does for such pairs.
    ends = (keys[0], keys[1]) if candidate.pattern == 'chain' else (keys[0], keys[1])
    together = graph.term_sentences(ends[0]) & graph.term_sentences(ends[1])
    if candidate.pattern != 'chain':
        together &= graph.term_sentences(keys[2])
    if any(graph.sentences[index][2] for index in together):
        return None, 'restates_source'
    reading['co_mentions'] = len(together)
    reading['co_chunk'] = bool(graph.term_chunks(ends[0]) & graph.term_chunks(ends[1]))
    return reading, None


# --------------------------------------------------------------------------- scoring

def edge_support(edge):
    """Assertive 0.8 / hedged 0.55, +0.1 per extra document (max +0.2), +0.05 if quantitative."""
    score = 0.55 if edge.hedged else 0.8
    score += 0.1 * min(2, len(edge.documents()) - 1)
    score += 0.05 if edge.quantitative else 0.0
    return min(1.0, score)


def path_support(edges):
    return min(edge_support(edge) for edge in edges)   # weakest premise bounds the path


def source_support(paths):
    """Noisy-or over independent supporting paths (at most five)."""
    missing = 1.0
    for edges in paths[:_MAX_PATHS]:
        missing *= 1.0 - path_support(edges)
    return round(1.0 - missing, 3)


def novelty(text, edges, reading):
    """0.5 x (1 - largest overlap with one premise) + 0.3 x document spread + 0.2 x separation."""
    words = set(_content(_tokens(text)))
    overlap = max((len(words & set(_content(_tokens(p['quote'])))) / len(words)
                   for edge in edges for p in edge.proofs), default=1.0) if words else 1.0
    documents = len({source_of(p['document_id']) for edge in edges for p in edge.proofs})
    spread = min(1.0, (documents - 1) / 2)
    separation = 0.5 if reading.get('co_mentions') else 1.0 if not reading.get('co_chunk') else 0.75
    return round(0.5 * (1.0 - overlap) + 0.3 * spread + 0.2 * separation, 3)


def rank_key(item):
    scores = item['scores']
    return (-round(scores['source_support'], 2), -round(scores['deductive_relevance'], 2),
            -round(scores['novelty'], 2), item['id'])


# --------------------------------------------------------------------------- text

def hypothesis_text(candidate, reading):
    edges = candidate.edges
    if candidate.pattern == 'chain':
        verb = _VERB[reading['relation']]
        via = ' and then '.join(reading['via'])
        return f'{edges[0].subject} may {verb} {edges[-1].object} through {via}.'
    a, b, hub = reading['anchors']
    if reading['relation'] == 'co_constrain':
        return (f'{a} and {b} may jointly constrain {hub}, so relieving one may shift the bottleneck to the other.')
    if reading['relation'] == 'offset':
        up, down = (a, b) if _sign(edges[0].kind) == 1 else (b, a)
        return f'Gains in {hub} from {up} may be offset by {down}.'
    if reading['relation'] == 'jointly_drive':
        return f'{a} and {b} may jointly drive {hub}, and their effects may compound.'
    if reading['relation'] == 'jointly_affect':
        return f'{a} and {b} may interact in their effect on {hub}.'
    if reading['relation'] == 'jointly_support':
        return f'{a} and {b} may jointly support {hub}, each covering what the other leaves open.'
    if reading['relation'] == 'jointly_undermine':
        return f'{a} and {b} may jointly undermine {hub}, so answering one objection may leave the other standing.'
    if reading['relation'] == 'contested':
        up, down = (a, b) if _sign(edges[0].kind) == 1 else (b, a)
        return f'The support that {up} gives {hub} may be cancelled by {down}.'
    if reading['relation'] == 'common_ground':
        return f'{a} and {b} may stand or fall together because both rest on {hub}.'
    return f'{a} and {b} may move together because both depend on {hub}.'


def falsification(candidate, reading):
    edges = candidate.edges
    if candidate.pattern == 'chain' and reading['relation'] in _LOGICAL:
        start, end = edges[0].subject, edges[-1].object
        via = ', '.join(reading['via'])
        claim = 'holds' if reading['relation'] == 'supports' else 'fails'
        return (f'Construct a coherent case where {start} is accepted. The hypothesis fails if {end} still '
                f'{"fails" if claim == "holds" else "holds"} in that case, or if the argument does not need {via}.')
    if candidate.pattern == 'chain':
        start, end = edges[0].subject, edges[-1].object
        via = ', '.join(reading['via'])
        direction = dict(increases='rise', decreases='fall', constrains='stay bounded',
                         causes='rise', affects='change').get(reading['relation'], 'change')
        return (f'Compare settings where {start} differs while other inputs are matched. The hypothesis fails if '
                f'{end} does not {direction} with {start}, or if fixing {via} removes no part of the effect.')
    a, b, hub = reading['anchors']
    if reading['relation'] == 'co_constrain':
        return (f'Relieve {a} alone while measuring {hub}. The hypothesis fails if {hub} keeps improving without '
                f'{b} becoming the binding limit, or if relieving {b} alone has no effect.')
    if reading['relation'] == 'offset':
        return (f'Measure {hub} where both {a} and {b} vary independently. The hypothesis fails if the effect of '
                'one does not shrink when the other is present.')
    if reading['relation'] in {'jointly_support', 'jointly_undermine', 'contested'}:
        return (f'Assess {hub} against {a} alone, {b} alone, and both together. The hypothesis fails if the '
                'combined case adds nothing to the stronger single case.')
    if reading['relation'] == 'common_ground':
        return (f'Find a position that keeps {a} and rejects {b}, or the reverse, without giving up {hub}. The '
                'hypothesis fails if such a position is coherent.')
    if reading['relation'] in {'jointly_drive', 'jointly_affect'}:
        return (f'Vary {a} and {b} separately and together. The hypothesis fails if the joint change in {hub} '
                'equals the sum of the separate changes.')
    return (f'Track {a} and {b} across periods where {hub} changes and where it does not. The hypothesis fails '
            f'if they co-vary just as strongly when {hub} is held fixed.')


def _citations(edges):
    cited = []
    for edge in edges:
        for proof in edge.proofs[:3]:
            cited.append(dict(proof, relation=edge.kind, subject=edge.subject, object=edge.object,
                              hedged=edge.hedged, origin=edge.origin))
    return cited


def _identity(candidate, reading):
    keys = reading['keys']
    if candidate.pattern == 'chain':
        return ('chain', keys[0], reading['relation'], keys[1])
    return (candidate.pattern, reading['relation'], tuple(sorted(keys[:2])), keys[2])


# --------------------------------------------------------------------------- run

HUB_CAP = 3      # at most this many returned hypotheses may share one bridge or hub term


def _similarity(encode, edges, budget=None):
    """Encode every term that could join another term by head noun; return a cosine lookup."""
    if budget: budget.check()
    if encode is None:
        return None, 0
    import numpy as np
    by_head = {}
    for edge in edges:
        if budget: budget.check()
        for key, surface in ((edge.subject_key, edge.subject), (edge.object_key, edge.object)):
            by_head.setdefault(term_head(key), {}).setdefault(key, surface)
    surfaces = sorted({surface for group in by_head.values() if len(group) > 1 for surface in group.values()})
    if not surfaces:
        return (lambda a, b: None), 0
    try:
        if budget: budget.check()
        vectors = np.asarray(encode(surfaces), dtype=float).reshape(len(surfaces), -1)
        if budget: budget.check()
    except (ValueError, RuntimeError, OSError):
        return None, 0
    norms = np.linalg.norm(vectors, axis=1)
    norms[norms == 0] = 1.0
    unit = {surface: vectors[i] / norms[i] for i, surface in enumerate(surfaces)}

    def similar(a, b):
        if a not in unit or b not in unit:
            return None
        return float(unit[a] @ unit[b])
    return similar, len(surfaces)


def run_frontier(topic, rows, *, limits=None, clock=time.monotonic, encode=None, deepen_top=0):
    """Pure core: no database, no writes. Returns the ``frontier`` receipt.

    ``encode(texts)`` (optional) returns one vector per text and is used to check head-noun bridges.
    """
    limits = limits or FrontierLimits()
    budget = Budget(limits, clock=clock)
    budget.counters = dict(rounds=0, candidates=0, edges=0, bytes=0)
    graph = build_graph(rows, budget)
    stems, present, focus = topic_focus(topic, graph)
    passed = dict(abductive=0, deductive=0, pre_thinker=0)
    rejected = Counter()
    survivors = {}
    stop_reason = graph.stop_reason
    receipt = dict(schema=SCHEMA, triggered=True, topic=topic, claim_status=CLAIM_STATUS, promotion='blocked',
                   index_write=False, potentially_nondeterministic=True, limits=asdict(limits),
                   topic_terms=stems, focus_terms=focus, chunk_count=len(rows),
                   candidate_search_complete=graph.complete, deepened=0,
                   leading_check=dict(requested=0, checked=0, complete=True, stop_reason=None))
    if stems and not present:
        receipt.update(status='insufficient_evidence', hypotheses=[], candidates_generated=0,
                       candidates_passed=passed, candidates_rejected={}, relation_edges=len(graph.edges),
                       scoped_edges=0, budget_used=_used(budget), incomplete=not graph.complete,
                       stop_reason=stop_reason, shortage=None)
        return receipt
    edges = scope_edges(graph, focus)
    if sum(edge.anchored for edge in edges) < _MIN_ANCHORED and set(present) - set(focus):
        # The discriminative words anchor too little; use every topic word present.
        focus = present
        edges = scope_edges(graph, focus)
        receipt['focus_terms'] = focus
        receipt['focus_fallback'] = True
    context = DeductiveContext(rows, graph, focus)
    try:
        similar, encoded = _similarity(encode, edges, budget)
    except StopSearch as exc:
        similar, encoded = None, 0
        graph.complete, stop_reason = False, str(exc)
    receipt.update(parser=parser_name(), bridge_check='encoder' if similar is not None else 'head_noun',
                   encoded_terms=encoded)
    generated = 0
    if graph.complete:
        try:
            for batch in batches(generate(edges, limits), limits.batch_size, budget):
                generated += len(batch)
                for candidate in batch:
                    budget.check()
                    reading, reason = abductive_check(candidate, similar)
                    if reading is None:
                        rejected['abductive:' + reason] += 1
                        continue
                    passed['abductive'] += 1
                    reading, reason = deductive_check(candidate, reading, context)
                    if reading is None:
                        rejected['deductive:' + reason] += 1
                        continue
                    passed['deductive'] += 1
                    reading, reason = pre_thinker_check(candidate, reading, graph)
                    if reading is None:
                        rejected['pre_thinker:' + reason] += 1
                        continue
                    passed['pre_thinker'] += 1
                    identity = _identity(candidate, reading)
                    entry = survivors.get(identity)
                    if entry is None:
                        budget.charge('bytes', 512 + sum(len(p['quote']) for e in candidate.edges
                                                          for p in e.proofs[:3]))
                        survivors[identity] = entry = dict(candidate=candidate, reading=reading, paths=[])
                    if len(entry['paths']) < _MAX_PATHS:
                        entry['paths'].append(candidate.edges)
        except StopSearch as exc:
            stop_reason = str(exc)
    hypotheses = []
    for identity, entry in survivors.items():
        candidate, reading = entry['candidate'], entry['reading']
        # Report the strongest path; every path contributes to source support.
        paths = sorted(entry['paths'], key=path_support, reverse=True)
        best = Candidate(candidate.pattern, paths[0])
        text = hypothesis_text(best, reading)
        scores = dict(source_support=source_support(paths), deductive_relevance=reading['deductive_relevance'],
                      novelty=novelty(text, best.edges, reading))
        citations = _citations(best.edges)
        hypotheses.append(dict(
            id=hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:12], text=text,
            pattern=candidate.pattern, relation=reading['relation'], anchors=list(reading['anchors']),
            via=reading['via'], claim_status=CLAIM_STATUS, promotion='blocked',
            source_ids=list(dict.fromkeys(c['document_id'] for c in citations)), citations=citations,
            scores=scores, falsification_test=falsification(best, reading),
            assumptions=('Assumes each cited relation holds in the same setting and that effects carry across '
                         'the shared term.' + (' It also assumes that terms with the same head noun name the same '
                                               'quantity.' if reading.get('same_quantity') else '')),
            supporting_paths=len(entry['paths']), rule_verdict=reading.get('rule_verdict'),
            hub=reading.get('hub') or reading['keys'][-1]))
    hypotheses.sort(key=rank_key)
    # Diversity: up to HUB_CAP entries per bridge or hub term first, then the rest in rank order, so one
    # well-connected term cannot fill the list while alternatives exist. Nothing is dropped for lack of them.
    limit = min(limits.max_results, HARD_CAP)
    per_term, first, deferred = Counter(), [], []
    for item in hypotheses:
        # Spread by the hub and by every anchor, so one well-connected side term cannot fill the list.
        terms = {item['hub'], *(term_key(a) for a in item['anchors'])}
        if all(per_term[t] < HUB_CAP for t in terms):
            first.append(item)
            per_term.update(terms)
        else:
            deferred.append(item)
    returned = (first + deferred)[:limit]
    receipt['hub_deferred'] = len(deferred)    # entries moved behind more varied ones (none dropped)
    receipt['candidate_search_complete'] = stop_reason is None
    leading = _check_leading(returned[:deepen_top], rows, graph, encode, budget)
    receipt['leading_check'] = leading
    receipt['deepened'] = leading['checked']
    if not leading['complete'] and stop_reason is None:
        stop_reason = 'leading_check:' + leading['stop_reason']
    incomplete = stop_reason is not None
    shortage = None
    if len(returned) < limits.min_results:
        shortage = dict(returned=len(returned), target_min=limits.min_results,
                        reason='Fewer candidates survived the filters than the target; the list is not padded.')
    status = 'hypotheses' if not shortage else 'shortage' if returned else 'insufficient_evidence'
    receipt.update(status=status, hypotheses=returned, survivors=len(hypotheses), candidates_generated=generated,
                   candidates_passed=passed, candidates_rejected=dict(sorted(rejected.items())),
                   relation_edges=len(graph.edges), scoped_edges=len(edges), budget_used=_used(budget),
                   incomplete=incomplete, stop_reason=stop_reason, shortage=shortage)
    return receipt


def _check_leading(items, rows, graph, encode, budget):
    """Check leading entries using the parent's ledger and complete snapshot graph."""
    result = dict(requested=len(items), checked=0, complete=True, stop_reason=None)
    if not items:
        return result
    from cpu_llm.deepen import _Sentences, run_deepen
    try:
        budget.check()
        similar, _ = _similarity(encode, list(graph.edges.values()), budget)
        sentences = _Sentences(rows, budget)
        for item in items:
            budget.check()
            receipt = run_deepen(item, rows, graph=graph, similar=similar, sentences=sentences, budget=budget)
            item['check'] = dict(verdict=receipt['verdict'], incomplete=receipt['incomplete'],
                direction_check=receipt['direction_check'],
                composition=receipt['composition'], plan_readiness=receipt['test_plan']['readiness'],
                links=[dict(source=l['source'], target=l['target'], status=l['status'],
                            counter=l['counter'][:2]) for l in receipt['links']])
            if receipt['incomplete']:
                result.update(complete=False, stop_reason=receipt['stop_reason'])
                break
            result['checked'] += 1
    except StopSearch as exc:
        result.update(complete=False, stop_reason=str(exc))
    return result


def _used(budget):
    return dict(budget.counters, seconds=round(budget.clock() - budget.started, 3))


def format_reply(receipt):
    lines = [f'Frontier hypotheses for {receipt["topic"]}. Each one is an unverified hypothesis built from '
             'relations across the authorized sources; none is stated by a single source.']
    passed = receipt['candidates_passed']
    lines.append(f'Candidates generated: {receipt["candidates_generated"]}. Passed abductive check: '
                 f'{passed["abductive"]}; deductive check: {passed["deductive"]}; pre-thinker validation: '
                 f'{passed["pre_thinker"]}.')
    for number, item in enumerate(receipt['hypotheses'], 1):
        scores = item['scores']
        lines.append(f'\n{number}. {item["text"]}')
        lines.extend(f'[{c["document_id"]}] {c["quote"]}' for c in item['citations'])
        lines.append('Falsification test: ' + item['falsification_test'])
        if item.get('check'):
            check = item['check']
            statuses = ', '.join(f'{l["source"]} -> {l["target"]}: {l["status"].replace("_", " ")}'
                                 for l in check['links'])
            flag = 'Warning, contested: ' if check['verdict'] == 'contested' else 'Deepen check: '
            lines.append(f'{flag}{check["verdict"].replace("_", " ")} ({statuses}).')
            if 'composition' in check:
                lines.append('Composition: ' + check['composition']['status'].replace('_', ' ') +
                             '; plan readiness: ' + check['plan_readiness'].replace('_', ' ') + '.')
            lines.extend(f'  - [{c["document_id"]}] {c["quote"]}' for l in check['links'] for c in l['counter'])
        lines.append(f'Scores: source support {scores["source_support"]:.2f}, deductive relevance '
                     f'{scores["deductive_relevance"]:.2f}, novelty {scores["novelty"]:.2f}.')
    if receipt.get('shortage'):
        shortage = receipt['shortage']
        lines.append(f'\nOnly {shortage["returned"]} hypotheses survived the filters (target at least '
                     f'{shortage["target_min"]}). The list is not padded.')
    if receipt['incomplete']:
        if receipt.get('candidate_search_complete'):
            lines.append(f'\nLeading checks incomplete: {receipt["stop_reason"]}. Candidate enumeration completed; '
                         'entries without a completed check remain unchecked.')
        else:
            lines.append(f'\nSearch incomplete: {receipt["stop_reason"]}. Results cover only the candidates '
                         'examined before the budget stopped the run.')
    return '\n'.join(lines)


def execute_frontier(app, message, topic, *, options=None, caller=None, as_of=None, strict=False):
    import psycopg
    from cpu_llm.invention import _snapshot
    from cpu_llm.pipeline import _caller_for

    options = options or dict(topic=None, limits=FrontierLimits())
    context = _caller_for(app, caller)
    allowed = None if context is None else context.allowed_sources

    def result(status, text, receipt=None):
        response = dict(message=message, tenant_id=app.tenant_id, status=status, answer_status=status, answer=None,
                        audit_passed=False, answer_evidence=[], reply=dict(text=text, body=text),
                        needs_clarification=status == 'needs_clarification',
                        judgment=dict(outcome=status, complete=status == 'hypotheses'
                                      and not (receipt or {}).get('incomplete', False)),
                        routing=dict(schema='flag-routing-contract-v1', executed_nodes=[],
                                     post_stages=list(STAGES) if receipt and receipt.get('hypotheses') is not None
                                     else ['frontier_snapshot']))
        if receipt is not None:
            response['frontier'] = receipt
        return response

    if app.guard.check(message + '\n' + (topic or '')).decision != 'allow' or allowed is not None and not allowed:
        return result('blocked', 'Request blocked.')
    if strict:
        return result('unsupported', 'Strict evidence mode disables Frontier.')
    base = dict(schema=SCHEMA, triggered=True, topic=topic, claim_status=CLAIM_STATUS, promotion='blocked',
                index_write=False, hypotheses=[], candidates_generated=0,
                candidates_passed=dict(abductive=0, deductive=0, pre_thinker=0), budget_used={}, incomplete=False)
    if not topic or len(topic) > 240:
        return result('needs_clarification', 'Name a short topic, such as “Frontier: AI energy bottlenecks.”',
                      dict(base, status='needs_clarification'))
    try:
        rows, when = _snapshot(app, allowed, as_of)
    except (ValueError, RuntimeError, psycopg.Error):
        return result('partial', 'The Frontier source snapshot was unavailable or exceeded its limit.',
                      dict(base, status='partial', incomplete=True, stop_reason='snapshot_unavailable'))
    pipeline = getattr(app.index, 'pipeline', None)
    receipt = run_frontier(topic, rows, limits=options['limits'], deepen_top=options.get('deepen_top', DEEPEN_TOP),
                           encode=getattr(pipeline, 'encode_texts', None))
    receipt['snapshot'] = dict(as_of=when, chunk_count=len(rows))
    if receipt['status'] == 'insufficient_evidence' and not receipt['hypotheses']:
        text = format_reply(receipt) + '\nNo candidate survived the filters.'
    else:
        text = format_reply(receipt)
    response = result(receipt['status'], text, receipt)
    response['answer_evidence'] = [c for item in receipt['hypotheses'] for c in item['citations']][:200]
    return response


def finish_frontier_response(result):
    """Render the selected layout, then append the standard invention note once."""
    import html
    from cpu_llm.output_rendering import render_response

    result = render_response(result)
    if not result.get('frontier', {}).get('triggered') or result.get('answer_status') == 'blocked':
        return result
    rendered = result.get('rendered_response', {})
    suffix = '<p>' + html.escape(NOTE) + '</p>' if rendered.get('media_type') == 'text/html' else '\n\n' + NOTE
    text = result['reply']['text'] + suffix
    result['reply'].update(text=text, body=text)
    if rendered:
        rendered['text'] = text
    return result
