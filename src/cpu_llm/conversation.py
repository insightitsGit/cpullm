"""Reviewed whole-turn social responses, separate from document knowledge."""
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import unicodedata


def normalize(text):
    if not isinstance(text,str) or len(text)>512:
        return ''
    text=unicodedata.normalize('NFKC',text).replace('’',"'")
    return ' '.join(text.casefold().strip().rstrip('!?.,').split())


@lru_cache(maxsize=1)
def _pack():
    raw=(Path(__file__).parent/'data/conversation-pack.json').read_bytes()
    data=json.loads(raw)
    if data.get('schema')!='builtin-conversation-pack-v1':
        raise ValueError('Invalid built-in conversation pack')
    aliases={}
    for intent,spec in data['intents'].items():
        for phrase in spec['phrases']:
            key=normalize(phrase)
            if not key or key in aliases:raise ValueError('Duplicate conversation phrase')
            aliases[key]=intent
    return data,aliases,hashlib.sha256(raw).hexdigest()


def recognize(message):
    return _pack()[1].get(normalize(message))


def split_greeting(message):
    """Remove only a leading social prefix; preserve the entire remaining request."""
    if len(message)>32000:return None
    match=re.match(r'\A\s*(?:hello|hi|hey|good morning|good afternoon|good evening|thank you|thanks)\b(?:[!,:.]+\s*|\s+)(\S[\s\S]*)\Z',message,re.I)
    if not match:return None
    return dict(text=message[:match.start(1)],start=0,end=match.start(1),engine_query=match[1])


def reply(appliance,message,query,*,caller=None,strict=False,style=None):
    intent=recognize(query)
    if intent is None:return None
    from cpu_llm.pipeline import _caller_for
    context=_caller_for(appliance,caller)
    if appliance.guard.check(message).decision!='allow':return None
    data,_,digest=_pack()
    requested='neutral'
    if style is not None:
        from cpu_llm.stylistic.profiles import options,TONES
        spec=options(style)
        if spec.tone_bit & spec.prohibited_risks:
            requested='restricted'
        else:
            requested=TONES[max(range(10),key=lambda i:spec.distribution[i])]
    selected=requested if requested in {'friendly','formal'} else 'neutral'
    spec=data['intents'][intent]
    text=spec.get('strict_response') if strict and intent=='capabilities' else spec['responses'][selected]
    result=dict(message=message,original_message=message,tenant_id=appliance.tenant_id,
        request_id=None if context is None else context.request_id,
        response_kind='conversation',answer_status='conversation',answer=None,
        answer_evidence=[],audit_passed=False,guard_decision='allow',reply=dict(text=text),
        conversation=dict(schema='conversation-result-v1',intent=intent,source_type='builtin_policy',
            pack_schema=data['schema'],pack_sha256=digest,learned_generation=False,
            requested_tone=requested,selected_tone=selected,
            tone_alignment='supported' if selected==requested else 'neutral_fallback',
            clinical_validation=False,document_evidence=False,stateless=True))
    if strict:
        result['evidence_policy']=dict(version='strict-evidence-v3',enabled=True,
            response_scope='builtin_conversation',learned_generation=False,
            source_truth_verified=False,clinical_validation=False,scan_complete=False,
            disabled_nodes=['fact_bridge','realizer','stylistic','reference_resolution','specialists'],
            stateless=True,allowed_sources=None if context is None else sorted(context.allowed_sources))
    return result
