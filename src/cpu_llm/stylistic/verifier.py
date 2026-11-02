"""Independent inverse grammar: do not call the candidate generator to verify it."""
import re
from .contracts import Frame
from .profiles import options
from .lexicon import lexicon

def verify(frame: Frame, candidate: dict, profile: str) -> tuple[str,...]:
    spec=options(profile)
    errors=[]
    if candidate.get('input_fingerprint')!=frame.fingerprint:errors.append('stale_input')
    text=candidate.get('text','')
    # Grammar terminals are closed and every variable must recover the snapshot.
    construction=candidate.get('construction_id')
    entry=next((e for e in lexicon().entries if e.id==construction),None)
    patterns={
        'formal-color-v1':r'The color of (.+) is ([a-z]+)\.',
        'plain-color-v2':r'(.+) is ([a-z]+)\.',
        'friendly-location-v1':r'You can find (.+) in (.+)\.',
        'plain-location-v2':r'(.+) is found in (.+)\.',
        'shape-predicate-v2':r'(.+) has '+('an' if frame.value=='oval' else 'a')+r' (.+) shape\.',
        'shape-attribute-v2':r'The shape of (.+) is (.+)\.',
        'material-predicate-v2':r'(.+) is made of (.+)\.',
        'material-attribute-v2':r'The material of (.+) is (.+)\.',
        'weight-predicate-v2':r'(.+) weighs (.+)\.',
        'weight-attribute-v2':r'The weight of (.+) is (.+)\.',
    }
    if not entry or construction not in patterns:return ('unsupported_construction',)
    if entry.relation!=frame.relation:errors.append('construction_mismatch')
    if entry.risks&spec.prohibited_risks:errors.append('relationship_exclusion')
    match=re.fullmatch(patterns[construction],text)
    interior=construction in {'formal-color-v1','friendly-location-v1','shape-attribute-v2','material-attribute-v2','weight-attribute-v2'}
    subject=frame.subject
    if interior and subject.startswith('The '):subject='the '+subject[4:]
    if not interior and subject.startswith('the '):subject='The '+subject[4:]
    if not match or match.group(1)!=subject or match.group(2)!=frame.value:
        errors.append('meaning_or_coverage_changed')
    if tuple(tuple(p) for p in candidate.get('proof',()))!=frame.proof:errors.append('proof_changed')
    return tuple(errors)

def verify_compound(frames,candidate,spec,sentence_budget):
    """Every input claim must survive, in order, with its own unchanged proof."""
    clauses=candidate.get('clauses',())
    if len(clauses)!=len(frames) or not clauses:return ('claim_coverage_changed',)
    errors=[]
    for frame,clause in zip(frames,clauses):errors.extend(verify(frame,clause,spec))
    if len(frames)>spec.clauses_per_sentence*sentence_budget:errors.append('budget_exceeded')
    sentences=[]
    # Independently assemble only the approved conjunction grammar. No causal,
    # contrastive or comparative connective is available to the generator.
    for start in range(0,len(clauses),spec.clauses_per_sentence):
        group=clauses[start:start+spec.clauses_per_sentence]
        pieces=[]
        for i,clause in enumerate(group):
            part=clause.get('text','')[:-1]
            if i and part.startswith('The '):part='the '+part[4:]
            if i and part.startswith('You '):part='you '+part[4:]
            pieces.append(part)
        sentences.append(', and '.join(pieces)+'.')
    if candidate.get('text')!=' '.join(sentences):errors.append('compound_surface_changed')
    proof=tuple(sorted(set(p for f in frames for p in f.proof)))
    if tuple(tuple(p) for p in candidate.get('proof',()))!=proof:errors.append('proof_changed')
    return tuple(dict.fromkeys(errors))
