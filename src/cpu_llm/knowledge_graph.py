"""Source-backed, directed facts, separate from lossy word-cooccurrence vectors.

Extraction deliberately accepts a small set of explicit affirmative clauses.
Graph paths discover evidence; they never establish a new inferred fact.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from pathlib import Path
import re
import sqlite3
import json

from cpu_llm.access import source_allowed
from cpu_llm.answerability import _sentences
from cpu_llm.connection_channels import evaluate_connection


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s'-]", " ", text.casefold())
    return re.sub(r"^(?:a species of|the|an|a)\s+", "", " ".join(text.split())).strip()


@dataclass(frozen=True)
class Fact:
    subject: str
    relation: str
    object: str
    document_id: str
    sentence: str
    channel_data: str = field(default='', compare=False, repr=False)

    @property
    def channel_assessment(self):
        return json.loads(self.channel_data) if self.channel_data else evaluate_connection(self)

    @property
    def channels(self):
        return frozenset(name for name, result in self.channel_assessment['channels'].items()
                         if result['active'] is True)


_UNSAFE = re.compile(r"\b(?:not|no|never|if|unless|may|might|could|would|should|allegedly)\b|n't", re.I)
_SUBJECT = r"(?P<subject>[\w][\w '’-]*?)"
_COLORS = r"(?:black|blue|brown|gr[ae]y|green|orange|pink|purple|red|white|yellow)"


def extract_facts(document_id: str, text: str) -> list[Fact]:
    facts = []
    for sentence in _sentences(text):
        if _UNSAFE.search(sentence):
            continue
        body = sentence.rstrip('.!?')
        because = re.fullmatch(r'(?P<effect>.+?)\s+because\s+(?P<cause>.+)', body, re.I)
        if because:
            facts.append(Fact(because['cause'], 'causes', because['effect'], document_id, sentence))
            continue
        # Explicit alias apposition, e.g. the scientific and common names.
        alias = re.fullmatch(r"(?P<subject>[\w '’-]+), known as (?:the )?(?P<alias>[^,]+), (?P<tail>.+)", body)
        if alias:
            for name in re.split(r"\s+or\s+", alias['alias']):
                facts.append(Fact(alias['subject'], 'alias_of', name, document_id, sentence))
            body = alias['subject'] + ' ' + alias['tail']
        patterns = [
            ('causes', rf"{_SUBJECT}\s+causes?\s+(?P<object>.+)"),
            ('differs_from', rf"{_SUBJECT}\s+differs?\s+from\s+(?P<object>.+)"),
            ('lives_in', rf"{_SUBJECT}\s+(?:lives?|resides?|is found)\s+(?:in|across)\s+(?P<object>.+)"),
            ('has_color', rf"{_SUBJECT}\s+(?:is|are)\s+(?P<object>{_COLORS})"),
            ('has', rf"{_SUBJECT}\s+(?:has|have)\s+(?P<object>.+)"),
            ('is_a', rf"{_SUBJECT}\s+(?:is|are)\s+(?:a species of|an|a)\s+(?P<object>.+)"),
        ]
        for relation, pattern in patterns:
            match = re.fullmatch(pattern, body, re.I)
            if not match or normalize(match['subject']) in {'it', 'they', 'he', 'she', 'this', 'that'}:
                continue
            subject, obj = match['subject'], match['object']
            if re.search(r"\b(?:that|which|who|and|or)\b", subject, re.I):
                continue
            # Species definitions can explicitly state their geographic range.
            range_match = re.fullmatch(r"(?P<kind>.+?)\s+from\s+(?P<range>.+)", obj)
            if relation == 'is_a' and range_match and ' is a species of ' in body.casefold():
                facts.append(Fact(subject, 'lives_in', range_match['range'], document_id, sentence))
                obj = range_match['kind']
            facts.append(Fact(subject, relation, obj, document_id, sentence))
            break
    return list(dict.fromkeys(facts))


class KnowledgeGraph:
    def __init__(self, path: Path, *, enabled_channels=None, thresholds=None,
                 encode_texts=None, causal_matrix=None, model_version=None):
        self.path = path
        self.enabled_channels = enabled_channels or {}
        self.thresholds = thresholds or {}
        self.encode_texts = encode_texts
        self.causal_matrix = causal_matrix
        self.model_version = model_version

    @contextmanager
    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                conn.execute('CREATE TABLE IF NOT EXISTS facts (subject TEXT, relation TEXT, object TEXT, document_id TEXT, sentence TEXT, PRIMARY KEY(subject, relation, object, document_id, sentence))')
                columns = {row['name'] for row in conn.execute('PRAGMA table_info(facts)')}
                if 'channel_data' not in columns:
                    conn.execute("ALTER TABLE facts ADD COLUMN channel_data TEXT NOT NULL DEFAULT ''")
                yield conn
        finally:
            conn.close()

    def replace(self, chunks: list[tuple[str, str]], prefix: str | None = None):
        extracted = {document_id: extract_facts(document_id, text) for document_id, text in chunks}
        endpoints = list(dict.fromkeys(value for facts in extracted.values() for fact in facts
                                       for value in (fact.subject, fact.object)))
        tensors = {}
        if self.encode_texts is not None:
            for start in range(0, len(endpoints), 32):
                batch = endpoints[start:start + 32]
                vectors = self.encode_texts(batch)
                if len(vectors) != len(batch):
                    raise ValueError('endpoint encoder returned the wrong number of vectors')
                tensors.update(zip(batch, vectors))
        with self._connect() as conn:
            if prefix is not None:
                conn.execute('DELETE FROM facts WHERE substr(document_id, 1, ?) = ?', (len(prefix), prefix))
            for document_id, text in chunks:
                conn.execute('DELETE FROM facts WHERE document_id = ?', (document_id,))
                for fact in extracted[document_id]:
                    assessment = evaluate_connection(fact, enabled_channels=self.enabled_channels,
                        left_tensor=tensors.get(fact.subject), right_tensor=tensors.get(fact.object),
                        thresholds=self.thresholds, causal_matrix=self.causal_matrix)
                    assessment['model_version'] = self.model_version
                    conn.execute('INSERT OR IGNORE INTO facts (subject, relation, object, document_id, sentence, channel_data) VALUES (?, ?, ?, ?, ?, ?)',
                                 (fact.subject, fact.relation, fact.object, fact.document_id, fact.sentence,
                                  json.dumps(assessment, allow_nan=False)))

    def delete_prefix(self, prefix: str):
        if self.path.exists():
            with self._connect() as conn:
                conn.execute('DELETE FROM facts WHERE substr(document_id, 1, ?) = ?', (len(prefix), prefix))

    def neighborhood(self, question: str, *, allowed=None, hops: int = 2, limit: int = 24,
                     channels: set[str] | None = None, intent=None) -> list[Fact]:
        if not self.path.exists() or limit <= 0 or hops <= 0:
            return []
        with self._connect() as conn:
            rows = [Fact(**dict(row)) for row in conn.execute('SELECT * FROM facts ORDER BY document_id, subject, relation, object')
                    if source_allowed(row['document_id'], allowed)]
        if channels is not None:
            rows = [row for row in rows if row.channels.intersection(channels)]
        if intent is not None:
            request = intent.get('requested') or {}
            weights = intent.get('channels') or {}
            rows.sort(key=lambda row: (
                row.relation == request.get('relation'),
                sum(weights.get(name, {}).get('weight', 0.) for name in row.channels)), reverse=True)
            question = request.get('entity') or question
        question = ' ' + normalize(question) + ' '
        endpoints = {normalize(value) for row in rows for value in (row.subject, row.object)}
        frontier = {value for value in endpoints if value and f' {value} ' in question}
        if not frontier:
            # A lone content word may recall phrases containing it. Keep
            # endpoint phrases intact: "European lobster" is one entity,
            # not an assertion about everything named "European".
            from cpu_llm.channels import _content_words
            seeds = set(_content_words(question))
            frontier = {value for value in endpoints if seeds.intersection(value.split())}
        # Prefer the full named entity over a generic substring of its name.
        frontier = {value for value in frontier if not any(value != other and f' {value} ' in f' {other} ' for other in frontier)}
        found = []
        seen = set()
        for _ in range(min(hops, 3)):
            nxt = set()
            for row in rows:
                if row in seen or not frontier.intersection((normalize(row.subject), normalize(row.object))):
                    continue
                seen.add(row)
                found.append(row)
                nxt.update((normalize(row.subject), normalize(row.object)))
                if len(found) >= limit:
                    return found
            frontier = nxt
        return found

    def word_channels(self, word: str, *, allowed=None):
        """Membership comes from incident edges with evidence, not one word label."""
        facts = self.neighborhood(word, allowed=allowed, hops=1)
        return {name: [dict(subject=f.subject, relation=f.relation, object=f.object,
                           document_id=f.document_id, sentence=f.sentence)
                       for f in facts if name in f.channels]
                for name in ('dense', 'relational', 'disentangled', 'hyperbolic', 'identity', 'causal')}
