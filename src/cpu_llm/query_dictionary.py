"""Bounded sense-labeled query expansion; never rewrite source evidence."""
import json
import re
from functools import lru_cache
from pathlib import Path

_GUARD = re.compile(r"\b(?:not|no|never|without|except|unless|cannot|if)\b|n't", re.I)


@lru_cache(maxsize=1)
def load_dictionary():
    return json.loads((Path(__file__).parent / 'data' / 'query-lexicon.json').read_text(encoding='utf-8'))


def interpret_prompt(message):
    lexicon = load_dictionary()
    text = ' '.join(message.strip().split())
    terms = [dict(term) for term in lexicon['terms']
             if re.search(rf"\b{re.escape(term['word'])}\b", text, re.I)]
    result = dict(version=lexicon['version'], original=message, canonical=message,
                  variants=[], terms=terms, applied=None, status='unchanged')
    if _GUARD.search(text):
        return dict(result, status='guarded')
    if any(term['relation'] == 'ambiguous' for term in terms):
        return dict(result, status='ambiguous_sense')
    for expression in lexicon['expressions']:
        match = re.fullmatch(expression['pattern'], text.rstrip('?.!'), re.I)
        if match:
            entity = match['entity'].strip()
            # Do not guess an antecedent or collapse a compound request.
            if re.search(r'\b(?:it|that|those|them|and|or)\b', entity, re.I):
                return dict(result, status='unresolved_entity')
            canonical = expression['canonical'].format(entity=entity)
            if canonical.casefold().rstrip('?') != text.casefold().rstrip('?'):
                return dict(result, canonical=canonical, variants=[canonical],
                            applied={key: expression[key] for key in ('id', 'relation', 'sense')}, status='expanded')
    return result
