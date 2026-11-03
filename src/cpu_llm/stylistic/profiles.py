"""Request-local tone controls. A requested tone never licenses new facts."""
from dataclasses import dataclass
from enum import IntFlag
import math
import re

TONES=('friendly','poetic','formal','emotional','serious','playful','melancholic','empathetic','analytical','intimate')

class Tone(IntFlag):
    FRIENDLY=1; POETIC=2; FORMAL=4; EMOTIONAL=8; SERIOUS=16
    PLAYFUL=32; MELANCHOLIC=64; EMPATHETIC=128; ANALYTICAL=256; INTIMATE=512

class Relationship(IntFlag):
    UNKNOWN=0; FAMILIAL=1; ROMANTIC=2; COLLEAGUE=4; FORMAL=8; CASUAL=16

@dataclass(frozen=True)
class StyleOptions:
    tone: str='formal'
    relationship: Relationship=Relationship.UNKNOWN
    magnitude: float=0.4
    valence: float=0.0
    arousal: float=0.3
    max_sentences: int=3
    clauses_per_sentence: int=2
    tone_weights: tuple[float,...] | None=None

    def __post_init__(self):
        if self.tone not in TONES:raise ValueError('Unknown style tone')
        if self.tone_weights is not None:
            if (not isinstance(self.tone_weights,tuple) or len(self.tone_weights)!=10
                or any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) or v<0 or v>1 for v in self.tone_weights)
                or not math.isclose(sum(self.tone_weights),1.0,abs_tol=1e-6)):
                raise ValueError('Tone weights must be an immutable normalized ten-channel distribution')
        if not isinstance(self.relationship,Relationship) or int(self.relationship)&~31:
            raise ValueError('Invalid relationship flags')
        for value,low,high in ((self.magnitude,0,1),(self.valence,-1,1),(self.arousal,0,1)):
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not low<=value<=high:
                raise ValueError('Invalid finite intensity range')
        for value,high in ((self.max_sentences,20),(self.clauses_per_sentence,4)):
            if type(value) is not int or not 1<=value<=high:raise ValueError('Invalid style budget')

    @property
    def distribution(self):
        return self.tone_weights or tuple(float(t==self.tone) for t in TONES)

    @property
    def tone_bit(self):
        return Tone(sum(1<<i for i,value in enumerate(self.distribution) if value>0))

    @property
    def prohibited_risks(self):
        # Restrictions accumulate: a romantic bit cannot override familial/formal.
        risks=Tone(0)
        if not self.relationship&Relationship.ROMANTIC:risks|=Tone.INTIMATE
        if self.relationship&Relationship.FAMILIAL:risks|=Tone.INTIMATE
        if self.relationship&Relationship.FORMAL:risks|=Tone.INTIMATE|Tone.PLAYFUL|Tone.EMOTIONAL
        if self.relationship&Relationship.COLLEAGUE:risks|=Tone.INTIMATE|Tone.EMOTIONAL
        return risks

def options(value):
    if isinstance(value,StyleOptions):return value
    if isinstance(value,str):return StyleOptions(tone=value)
    raise ValueError('style must be None, a supported tone, or StyleOptions')


def extract_style_request(message):
    """Explicit presentation directives only; quoted titles and negations are data."""
    tones='|'.join(TONES)
    from cpu_llm.output_rendering import extract_layout
    layout=extract_layout(message)
    if layout['format']:
        inner=extract_style_request(layout['content_query'])
        if inner['tone'] is not None:
            return dict(inner,query=inner['query']+' '+layout['directive'].lstrip())
    masked=re.sub(r'```[\s\S]*?```|"[^"\n]*"|“[^”\n]*”|`[^`\n]*`',lambda m:' '*len(m[0]),message)
    prefix=re.match(rf'^\s*[Ii]n (?:a |an )?(?P<tone>{tones}) tone\s*[:,]\s*',masked,re.I)
    suffix=re.search(rf'(?:\s+in (?:a |an )?|[.;]\s*(?:please\s+)?(?:use|write in) (?:a |an )?)(?P<tone>{tones}) tone\s*[.!?]*$',masked,re.I)
    match=suffix or prefix
    if not match:return dict(query=message,tone=None)
    if re.search(r"\b(?:not|don't|do not)\s*$",masked[:match.start()],re.I):
        return dict(query=message,tone=None)
    query=(message[:match.start()]+message[match.end():]).strip()
    return dict(query=query,tone=match['tone'].lower(),directive=message[match.start():match.end()])
