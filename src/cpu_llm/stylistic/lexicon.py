"""Small curated construction lexicon, stored as immutable arrays.

Semantic licenses are exact relation IDs, not learned word embeddings. Ranking
operates only within the licensed set; a score cannot trade meaning for tone.
Tone affinities and inherent register risks are separate: suitability for a tone
does not make an otherwise neutral phrase inherently romantic or emotional.
"""
from dataclasses import dataclass
from functools import lru_cache
import numpy as np
from .profiles import TONES, Tone

@dataclass(frozen=True)
class Entry:
    id: str
    relation: str
    tone: Tone
    intensity: tuple[float,float,float]=(0.4,0.0,0.3)
    risks: Tone=Tone(0)
    generic: float=0.1
    pos: int=8  # finite predicate/construction category, not a full POS parser

ENTRIES=(
    Entry('formal-color-v1','has_color',Tone.FORMAL|Tone.ANALYTICAL|Tone.SERIOUS,intensity=(.45,0,.2),generic=0.0),
    Entry('plain-color-v2','has_color',Tone.FRIENDLY,intensity=(.3,0,.3)),
    Entry('friendly-location-v1','lives_in',Tone.FRIENDLY,intensity=(.35,0,.4)),
    Entry('plain-location-v2','lives_in',Tone.FORMAL|Tone.ANALYTICAL|Tone.SERIOUS),
    Entry('shape-predicate-v2','attribute:shape',Tone.FRIENDLY),
    Entry('shape-attribute-v2','attribute:shape',Tone.FORMAL|Tone.ANALYTICAL|Tone.SERIOUS),
    Entry('material-predicate-v2','attribute:material',Tone.FRIENDLY),
    Entry('material-attribute-v2','attribute:material',Tone.FORMAL|Tone.ANALYTICAL|Tone.SERIOUS),
    Entry('weight-predicate-v2','attribute:weight',Tone.FRIENDLY),
    Entry('weight-attribute-v2','attribute:weight',Tone.FORMAL|Tone.ANALYTICAL|Tone.SERIOUS),
)

class Lexicon:
    def __init__(self,entries=ENTRIES):
        self.entries=tuple(entries)
        if len({e.id for e in entries})!=len(entries):raise ValueError('Duplicate lexicon ID')
        if any(type(e.pos) is not int or not 0<e.pos<65536 or int(e.tone)&~1023 or int(e.risks)&~1023 for e in entries):
            raise ValueError('Invalid feature bitmask')
        self.pos=np.array([e.pos for e in entries],dtype=np.uint16)
        self.tone=np.array([int(e.tone) for e in entries],dtype=np.uint16)
        self.risks=np.array([int(e.risks) for e in entries],dtype=np.uint16)
        self.intensity=np.array([e.intensity for e in entries],dtype=np.float32).reshape((-1,3))
        self.penalty=np.array([e.generic for e in entries],dtype=np.float32)
        self.affinity=np.array([[float(bool(e.tone&Tone(1<<i))) for i in range(10)] for e in entries],dtype=np.float32).reshape((-1,10))
        if len(entries):
            totals=self.affinity.sum(axis=1,keepdims=True)
            self.affinity=np.divide(self.affinity,totals,out=np.zeros_like(self.affinity),where=totals!=0)
        if (not np.isfinite(self.intensity).all() or not np.isfinite(self.penalty).all()
            or np.any(self.intensity[:,0]<0) or np.any(self.intensity[:,0]>1)
            or np.any(abs(self.intensity[:,1])>1) or np.any(self.intensity[:,2]<0)
            or np.any(self.intensity[:,2]>1) or np.any(self.penalty<0) or np.any(self.penalty>1)
            or any(type(e.pos) is not int or not 0<e.pos<65536 or int(e.tone)&~1023 or int(e.risks)&~1023 for e in entries)):
            raise ValueError('Invalid construction features')
        for a in (self.pos,self.tone,self.risks,self.intensity,self.penalty,self.affinity):a.setflags(write=False)

    def rank(self,relation,spec,required_pos=8):
        mask=(self.pos&required_pos)!=0
        mask&=(self.risks&int(spec.prohibited_risks))==0
        # Exact semantic eligibility precedes every continuous feature score.
        indices=[i for i,e in enumerate(self.entries) if mask[i] and e.relation==relation]
        target=np.array([spec.magnitude,spec.valence,spec.arousal],dtype=np.float32)
        ranked=[]
        for i in indices:
            d=abs(self.intensity[i]-target)
            intensity=1-float(.5*d[0]+.3*d[1]/2+.2*d[2])
            affinity=float(np.dot(self.affinity[i],spec.distribution))
            score=.4+.25*intensity+.25*affinity-.15*float(self.penalty[i])
            ranked.append((round(score,6),self.entries[i].id,i,affinity))
        ranked.sort(key=lambda item:(-item[0],item[1]))
        return ranked

    def explain(self,index,spec):
        difference=abs(self.intensity[index]-np.array([spec.magnitude,spec.valence,spec.arousal]))
        return dict(semantic_license=1.0,
            intensity_similarity=1-float(.5*difference[0]+.3*difference[1]/2+.2*difference[2]),
            tone_affinity=float(np.dot(self.affinity[index],spec.distribution)),
            generic_penalty=float(self.penalty[index]),weights=(.4,.25,.25,.15))

@lru_cache(maxsize=1)
def lexicon():return Lexicon()
