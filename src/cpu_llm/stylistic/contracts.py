"""Deeply immutable snapshots of a deliberately small accepted-claim subset."""
from dataclasses import dataclass
import hashlib
import json
import re

from .profiles import TONES, options
PROFILES = TONES
_NAME = r"[A-Za-z][A-Za-z '\-]{0,79}"
_COLOR = r'(?:red|blue|green|white|black|purple|yellow|orange|gray|grey|teal|amber)'
_DISALLOWED = re.compile(r'\b(?:not|never|if|unless|and|or|before|after|may|must|all|some|every|only)\b',re.I)

@dataclass(frozen=True)
class Frame:
    subject: str
    relation: str
    value: str
    canonical: str
    proof: tuple[tuple[str,str], ...]

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps((self.subject,self.relation,self.value,self.canonical,self.proof)).encode()).hexdigest()

def validate_profile(profile):
    if profile is not None:options(profile)

def snapshot(result):
    """Only direct, single-proof decisions accepted by the existing judge qualify.

    This is an internal adapter, not an authorization API for external results.
    """
    judgment=result.get('judgment') or {}
    decision=judgment.get('answer_decision') or {}
    if (result.get('__partial__') or result.get('__node_error__') or result.get('needs_clarification')
        or result.get('delivery_blocked') or result.get('shine_enforced') or result.get('shine_ok') is False
        or result.get('guard_decision') not in (None,'allow')
        or result.get('answer_status') not in (None,'answered','evidence_quote')
        or judgment.get('outcome') not in ('answered','evidence_quote')
        or judgment.get('verification')!='structural' or decision.get('outcome')!='answered'):
        return None
    request=decision.get('request') or {}
    if request.get('direction')!='subject' or request.get('polarity')!='affirmative':return None
    if request.get('quantifier_scope')!='individual' or request.get('object_constraint'):return None
    canonical=decision.get('text') or ''
    if not isinstance(canonical,str) or len(canonical)>240 or _DISALLOWED.search(canonical):return None
    proof=tuple(sorted(set((p.get('document_id',''),p.get('span','')) for p in decision.get('proof',[]))))
    accepted={(p.get('document_id',''),p.get('span','')) for p in judgment.get('evidence',[])}
    if len(proof)!=1 or not proof[0][0] or proof[0][1]!=canonical or set(proof)!=accepted:return None
    relation=request.get('relation')
    weight=r'[0-9]{1,6}(?:\.[0-9]{1,4})? (?:pounds?|kilograms?|grams?|kg|g)'
    pattern={'has_color':rf'(?P<subject>{_NAME}) is (?P<value>{_COLOR})\.',
             'lives_in':rf'(?P<subject>{_NAME}) is found in (?P<value>{_NAME})\.',
             'attribute:shape':rf'The shape of (?P<subject>{_NAME}) is (?P<value>round|square|oval|flat)\.',
             'attribute:material':rf'The material of (?P<subject>{_NAME}) is (?P<value>brass|wood|steel|glass|copper|iron|oak)\.',
             'attribute:weight':rf'The weight of (?P<subject>{_NAME}) is (?P<value>{weight})\.'}.get(relation)
    if not pattern:return None
    match=re.fullmatch(pattern,canonical)
    if not match:return None
    subject,value=match['subject'],match['value']
    key=lambda s:re.sub(r'^the\s+','',s.strip(),flags=re.I).casefold()
    if key(subject)!=key(request.get('entity') or ''):return None
    # A single grammatical subject; no copular/nested clause admitted as a name.
    if re.search(r'\b(?:is|are|was|were|has|have|because|who|which|that)\b',subject+' '+value,re.I):return None
    return Frame(subject,relation,value,canonical,proof)
