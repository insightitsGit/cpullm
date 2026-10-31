"""Independent inverse grammar: do not call the candidate generator to verify it."""
import re
from .contracts import Frame

def verify(frame: Frame, candidate: dict, profile: str) -> tuple[str,...]:
    errors=[]
    if candidate.get('input_fingerprint')!=frame.fingerprint:errors.append('stale_input')
    text=candidate.get('text','')
    # Grammar terminals are closed and every variable must recover the snapshot.
    if profile=='formal' and frame.relation=='has_color':
        match=re.fullmatch(r'The color of (.+) is ([a-z]+)\.',text)
        construction='formal-color-v1'
    elif profile=='friendly' and frame.relation=='lives_in':
        match=re.fullmatch(r'You can find (.+) in (.+)\.',text)
        construction='friendly-location-v1'
    else:return ('unsupported_construction',)
    if candidate.get('construction_id')!=construction:errors.append('construction_mismatch')
    subject='the '+frame.subject[4:] if frame.subject.startswith('The ') else frame.subject
    if not match or match.group(1)!=subject or match.group(2)!=frame.value:
        errors.append('meaning_or_coverage_changed')
    if tuple(tuple(p) for p in candidate.get('proof',()))!=frame.proof:errors.append('proof_changed')
    return tuple(errors)
