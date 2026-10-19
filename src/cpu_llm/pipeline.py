"""One turn of the CPU text path.

ChorusGraph orders the steps. There is no language-model client in this module.

Training stores a caller-supplied chunk in three places: VectorPrism writes the
1024-d tensor to pgvector, PrismResonance keeps the dense-channel amplitude for
each lexical tag, and PrismCortex records the chunk as a graph node with those
tags beside any proposition. Training and sleep write the second- and third-hand
word relations into the tail of the relational channel. The dense core stays
the vector VectorPrism encoded. A later sleep cycle may also link related nodes.

A prompt then runs:

1. PrismGuard checks the prompt.
2. VectorPrism returns the nearest chunks and their tensors. When the question
   names one or more articles whose lead paragraphs are stored, those articles
   replace the neighbors from other articles, and each lead is included if the
   scan missed it. The prompt was encoded once, before this graph runs, and that same
   1024-d tensor is the query for the scan and for every later channel rank.
3. PrismResonance ranks those chunks by dense-channel interference. The header
   is a packed timestamp, not a coordinate, so it is not part of the amplitude.
   VectorPrism already chose this shortlist, so the coherence shield does not
   drop a hit whose cosine is merely moderate.
4. Six channel nodes read that same shortlist. Dense cosine is the trained
   rank. A stored proposition, a word unique to one passage, Poincaré distance
   inside the unit ball, a shared name, and a sentence that states a cause are
   the other readings. A head that is off in the checkpoint is not ranked by
   its slice. The detail node writes those six readings into one template and,
   when the prompt asks why, how, for a comparison, or about a cause, suggests
   the discovery loop. It does not turn the loop on, and it does not add a
   sentence that was not written in a retrieved passage.
5. PrismRAG labels each retrieved chunk with the article slug already in its
   document id, and labels the prompt only when that slug's token is in the prompt.
6. PrismThinker reads the ranked chunks as evidence and names what is missing.
   Its five head processes and the in-process probe pool are started with the
   appliance, beside the encoder, and reused for every prompt. A payment
   proposal is evaluated with PrismAgenticPay's corporate policy.
7. The design's deliberation adapter runs when evidence propositions are
   present, and when the retrieval is empty. A named article is realized from
   that article. An open question drops a neighbor that shares none of its
   content words. An identity question leads with the affirmative copula that
   names the asked subject, then any later sentence from the same scope. The
   surface realizer turns that result into a sentence, and the auditor checks
   the sentence.
8. PrismShine checks the retrieval trace and, when a sentence exists, the
   sentence against those paragraphs. The judge stays off. An abstention
   sentence is kept. Any other blocked sentence is replaced.
9. Creative writing runs only when the prompt classifier names a reason, or
   when the caller turns it on. The gather node loads every paragraph of the
   articles in the shortlist and ranks the words that share a paragraph with
   the prompt. Those ranked paragraphs are passed to the realizer. Each
   generated sentence is checked by the auditor and the numeric span grammar.
   A plain question skips this step.
10. Model01 writes the sentence from the prompt and the stored records. It
    runs after math, finance, and the event frame, and before the reply. A
    blocked prompt skips it. A withheld sentence stays withheld.
11. A reply node adds a preface, follow-ups, and next steps taken from the
    passages and the open questions. It leaves the checked sentence as the
    body. When Model01 verified a sentence and no specialist owns the turn,
    that sentence is what is spoken. When creative writing ran, that passage
    is appended after the checked sentence. Discovery still runs only when
    the caller asks for it.

A proposition is stored only when the source supplies one. VectorPrism's
offline heuristic extractor can add a causal graph and numeric attributes
from the retrieved texts. A measurement written in a chunk, such as a body
length in centimetres, is copied onto that chunk alone, and "up to" stays
a maximum in the claim's provenance. A policy rule and an objective are
not inferred from those texts. PrismManifest's span grammar then allows only numeric
tokens that were cut from those chunks. The signed tool gate is separate
and needs an Ed25519 keyring.
"""

from __future__ import annotations

import math
import os
import re
import threading
import uuid
from pathlib import Path
from typing import Any

import numpy as np
from vectorprism.tensor_contract import PSMTensorContract
from chorusgraph.core import END, START, Graph
from chorusgraph.core.node import dict_node_adapter
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta
from prismguard.runtime.factory import create_checker_rules_only
from prismresonance import FrequencyFamily, PrismResonance
from prismthinker.adapters.chorusgraph import to_chorusgraph
from prismthinker.adapters.vectorprism import RetrievedDocument, from_vectorprism
from prismthinker.config import EngineConfig
from prismthinker.core.schemas import EpistemicRegime, ReasoningContext

from cpu_llm.access import AccessError, CallerContext, StorageError, TenantNotFoundError, keep_allowed
from cpu_llm.agents.discovery import run_discovery
from cpu_llm.agents.imagine import compose_imagination
from cpu_llm.agents.reply import compose_reply
from cpu_llm.classifier import (
    creative_writing_trigger,
    deep_search_trigger,
    explain_trigger,
    finance_trigger,
    list_trigger,
    math_trigger,
    source_trigger,
    summary_trigger,
)
from cpu_llm.formats import draft_trigger, install_output_formats, parse_order
from cpu_llm.format_sense import FormatSense, semantic_reason
from cpu_llm.comparison import comparison_sides, possibilities_by_side, rows_for_side
from cpu_llm.channels import _content_words, complexity_reasons, judge_readings, read_channel
from cpu_llm.audit.entailment import EpistemicEntailmentAuditor
from cpu_llm.catalog import article_slug, label_retrieval, title_slugs
from cpu_llm.cognition.adapter import PrismCognitionSubspaceAdapter
from cpu_llm.grounding import shine_gate, verify_grounding
from cpu_llm.ir.schema import EIRProposition
from cpu_llm.manifest_spans import answer_numbers_allowed, build_span_grammar, canonical_values
from cpu_llm.measurements import extract_stated_measurements, stated_million_amount
from cpu_llm.realizer.surface import SemanticSurfaceRealizer
from cpu_llm.retrieval import VectorPrismIndex
from cpu_llm.thinker_pool import WarmPrismThinker
from cpu_llm.word_taxonomy import bind_word_taxonomy, load_word_index, recall_document_ids

TENSOR_DIM = 1024


def resonance_amplitude(tensor: np.ndarray) -> np.ndarray:
    """Unit dense core in the 1024-d layout. The header is not an embedding.

    VectorPrism stores a unix timestamp in header slots 3 and 4 by reinterpreting
    the integer bits as float32. That bit pattern is about 1e26, and a float32
    dot product of two such headers overflows to infinity. The dense core is the
    trained channel and is already a unit vector. The other five channels are
    still initialization; the disentangled slice alone has a norm near 12, so
    mixing it in would rank that noise and drop the real matches under the
    coherence shield.
    """
    vector = np.asarray(tensor, dtype=np.float64).reshape(-1)
    if vector.shape != (TENSOR_DIM,):
        raise ValueError(f"expected a {TENSOR_DIM}-d tensor, got {vector.shape}")
    dense = PSMTensorContract.DENSE_CORE
    part = vector[dense.start : dense.end]
    norm = float(np.linalg.norm(part))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError("dense channel is not a finite non-zero vector")
    amplitude = np.zeros(TENSOR_DIM, dtype=np.float32)
    amplitude[dense.start : dense.end] = (part / norm).astype(np.float32)
    return amplitude


def default_checkpoint() -> Path:
    from cpu_llm.retrieval import default_checkpoint as checkpoint

    return checkpoint()


class Appliance:
    def __init__(
        self,
        checkpoint: Path | None = None,
        *,
        dsn: str | None = None,
        child_safety: bool | None = None,
        namespace: str | None = None,
        on_escalate: Any = None,
    ) -> None:
        from cpu_llm.child_safety import ChildSafetyGate, enabled_by_default

        # A namespace gets its own Postgres schema and its own local memory folder.
        self.namespace = _namespace_slug(namespace) if namespace else None
        self.tenant_id = self.namespace or "cpu-llm"
        if self.namespace:
            try:
                dsn = _namespace_dsn(dsn or os.environ.get("VECTORPRISM_PG_DSN") or _local_dsn(), self.namespace)
            except AccessError:
                raise
            except Exception as exc:
                raise StorageError("the database schema could not be opened") from exc
        self.child_safety = ChildSafetyGate(
            enabled=enabled_by_default() if child_safety is None else child_safety,
            on_escalate=on_escalate,
        )
        self._conversations: dict[str, Any] = {}
        self.index = VectorPrismIndex(
            checkpoint or default_checkpoint(),
            backend="pgvector",
            dsn=dsn,
        )
        if self.namespace:
            from cpu_llm.retrieval import ensure_namespace_vectors

            ensure_namespace_vectors(self.index, self.namespace)
        self.guard = create_checker_rules_only()
        self.thinker = WarmPrismThinker()
        self._bound = threading.local()
        self._seats = None
        self._thinker_factory = WarmPrismThinker
        self.cognition = PrismCognitionSubspaceAdapter()
        self.realizer = SemanticSurfaceRealizer()
        self.auditor = EpistemicEntailmentAuditor()
        self.shine = shine_gate()
        # Deep search keeps a reached paragraph only when its dense-core cosine to the prompt is at least this.
        # None keeps every reached paragraph.
        self.deep_min_similarity: float | None = 0.62
        self.payment_policy = _payment_evaluator()
        cache = Path(".chorusgraph") / "cpu-llm" / (self.namespace or "")
        cache.mkdir(parents=True, exist_ok=True)
        self.resonance = PrismResonance.create(
            embedding_dim=TENSOR_DIM,
            onnx_path=cache / "resonance_1024.onnx",
            state_path=cache / "resonance_state.db",
            coherence_threshold=-1.0,
            auto_sleep=False,
        )
        self.memory = SqliteGraphStore(cache / "graph_store.db", tenant_id=self.tenant_id)
        install_output_formats(self.memory)
        self.format_sense = FormatSense(self.memory, self._encode_sense)
        self.word_tags_path = cache / "word_tags.json"
        self.word_tags = load_word_index(self.word_tags_path)
        self.relations_path = cache / "word_relations.json"
        self._turn: dict[str, Any] | None = None
        self._creative_seen: dict[str, str] = {}
        self._previous_ids: list[str] = []
        self._deep_tensors: dict[str, Any] = {}
        self.graph = _compile(self)

    def _encode_sense(self, texts: list[str]):
        """Frozen retrieval encoder. The semantic trigger uses this space, not a second model."""
        return self.index.pipeline.encoder.encode(list(texts))

    def index_chunks(
        self,
        chunks: list[tuple[str, str]],
        propositions: dict[str, EIRProposition] | None = None,
    ) -> int:
        """Store source chunks. The caller has already split the source.

        A proposition stored under a document id is the symbolic form of that
        chunk. Retrieval can then deliberate it. A chunk with no proposition
        stays text evidence.
        """
        bound = propositions or {}
        stored: list[tuple[str, np.ndarray]] = []
        edges = _passage_edges(self, chunks)
        indexer = _taxonomy_indexer(self)
        for document_id, chunk_text in chunks:
            self.index.upsert(document_id, chunk_text)
            tensor = np.asarray(self.index.encode_chunk(chunk_text), dtype=np.float32).reshape(-1)
            signed, hands = _signed_row(self.index.db, document_id, chunk_text, tensor, edges)
            stored.append((document_id, signed))
            tags = indexer.build_chunk_tags(document_id, chunk_text, signed)
            _remember_chunk(
                self.memory,
                document_id,
                chunk_text,
                signed,
                bound.get(document_id),
                tags,
                hands,
            )
        if chunks:
            _bind_stored_words(
                self,
                chunks,
                [tensor for _document_id, tensor in stored],
            )
        return len(chunks)

    def catalog_chunks(
        self,
        chunks: list[tuple[str, str]],
        propositions: dict[str, EIRProposition] | None = None,
        *,
        replace_prefix: str | None = None,
    ) -> int:
        """Store every chunk, and store a proposition when one was supplied.

        The vector rows are written in a batch. Each chunk is then encoded
        again so the graph node keeps the same tensor the row stores.
        """
        self.index.save_chunks(chunks, replace_prefix=replace_prefix)
        bound = propositions or {}
        texts = [text for _document_id, text in chunks]
        vectors: list[Any] = []
        for start in range(0, len(texts), 32):
            vectors.extend(self.index.pipeline.encode_texts(texts[start : start + 32]))
        known = {node.id: node for node in self.memory.all_nodes()}
        pending: dict[str, str] = {}
        ops: list[DeltaOp] = []
        indexer = _taxonomy_indexer(self)
        edges = _passage_edges(self, chunks)
        signed_rows: list[np.ndarray] = []
        for (document_id, chunk_text), vector in zip(chunks, vectors):
            tensor = np.asarray(vector, dtype=np.float32).reshape(-1)
            signed, hands = _signed_row(self.index.db, document_id, chunk_text, tensor, edges)
            signed_rows.append(signed)
            tags = indexer.build_chunk_tags(document_id, chunk_text, signed)
            op = _assimilation(
                self.memory,
                document_id,
                chunk_text,
                signed,
                bound.get(document_id),
                known,
                pending,
                tags,
                hands,
            )
            if op is not None and op.node is not None:
                ops.append(op)
                known[op.node.id] = op.node
                pending[chunk_text.strip().lower()] = op.node.id
        if ops:
            self.memory.apply(StateDelta(ops=ops))
        if chunks:
            _bind_stored_words(self, chunks, signed_rows)
        return len(chunks)

    def ingest(self, source: str | Path | Any) -> dict[str, Any]:
        """Store a file, a folder, or a ``SourceDocument`` the caller already split.

        Each paragraph joins the same index as the paragraphs already stored.
        Reading the same source again replaces that source's paragraphs.
        A sheet connection is stored as a word edge beside the paragraph.
        """
        from cpu_llm.clauses import propositions_for
        from cpu_llm.documents import chunks_for, open_source, replace_prefix
        from cpu_llm.relations import add_edges

        documents = open_source(source)
        stored = 0
        ids: list[str] = []
        connections = 0
        for document in documents:
            chunks = chunks_for(document)
            stored += self.catalog_chunks(
                chunks,
                propositions_for(chunks),
                replace_prefix=replace_prefix(document),
            )
            ids.extend(document_id for document_id, _text in chunks)
            pairs = [(left, right) for left, right, _label in document.connections]
            if pairs:
                connections += add_edges(self.relations_path, pairs)
        return {
            "documents": len(documents),
            "chunks": stored,
            "ids": ids,
            "connections": connections,
        }

    def correct(
        self,
        document_id: str,
        prior_sentence: str,
        new_sentence: str,
        *,
        actor_id: str,
        timestamp: int,
        caller: Any | None = None,
    ) -> dict[str, Any]:
        """Store a round-tripped replacement beside the old sentence.

        The old node stays. The vector row's validity interval closes at
        ``timestamp``. A caller whose source list excludes this document is
        refused before the graph is written.
        """
        from cpu_llm.access import SourceForbidden, source_allowed
        from cpu_llm.corrections import apply_correction
        from cpu_llm.source_delete import source_prefix

        context = _caller_for(self, caller)
        if context is not None and not source_allowed(source_prefix(document_id), context.allowed_sources):
            raise SourceForbidden("that source is outside this caller's scope")
        return apply_correction(
            self.memory,
            self.index,
            document_id=document_id,
            prior_sentence=prior_sentence,
            new_sentence=new_sentence,
            actor_id=actor_id,
            timestamp=timestamp,
        )

    def delete_source(self, source: str) -> dict[str, Any]:
        """Remove one source from the vector index, the graph, and the word index.

        ``source`` is a file name, a document id, or the ingest id prefix.
        The resonance ledger and the shared word-relation file are not rebuilt.
        """
        from cpu_llm.source_delete import delete_stored_source

        return delete_stored_source(
            self.index,
            self.memory,
            self.word_tags,
            self.word_tags_path,
            source,
        )

    def upsert(self, document_id: str, chunk_text: str) -> int:
        return self.index_chunks([(document_id, chunk_text)])

    @property
    def _turn(self) -> dict[str, Any] | None:
        return getattr(self._bound, "turn", None)

    @_turn.setter
    def _turn(self, value: dict[str, Any] | None) -> None:
        self._bound.turn = value

    def active_thinker(self) -> WarmPrismThinker:
        """The thinker for this thread's seat. The default ask uses the appliance thinker."""
        bound = getattr(self._bound, "thinker", None)
        return self.thinker if bound is None else bound

    def ask(
        self,
        message: str,
        propositions: list[EIRProposition] | None = None,
        *,
        discover: bool = False,
        imagine: bool = False,
        deep: bool = False,
        math: bool = False,
        finance: bool = False,
        payment: Any | None = None,
        authority: Any | None = None,
        objective: Any | None = None,
        hypothesis: Any | None = None,
        causal_graph: Any | None = None,
        realization: str = "deterministic",
        account: bool = False,
        grade: Any = None,
        child_safety: bool | None = None,
        session_id: str | None = None,
        caller: Any | None = None,
        as_of: int | None = None,
    ) -> dict[str, Any]:
        if realization not in {"deterministic", "evidence_neural", "model01"}:
            raise ValueError("realization must be deterministic, evidence_neural, or model01")
        if (payment is None) != (authority is None):
            raise ValueError("a payment turn needs both a proposal and an authority snapshot")
        del child_safety, grade, session_id
        self._deep_tensors = {}
        context = _caller_for(self, caller)
        refused = empty_scope_result(self.tenant_id, message, context)
        if refused is not None:
            return refused
        from cpu_llm.typos import correct_message

        original_message = message
        message, typos = correct_message(message, self.word_tags, tenant_id=self.tenant_id)
        z_query = np.asarray(self.index.encode_query(message), dtype=np.float32).reshape(TENSOR_DIM)
        creative_reasons = creative_writing_trigger(message, forced=imagine)
        deep_reasons = deep_search_trigger(message, forced=deep)
        sides = comparison_sides(message)
        summary_reasons = summary_trigger(message)
        explain_reasons = explain_trigger(message)
        list_reasons = list_trigger(message)
        source_reasons = source_trigger(message)
        from cpu_llm.memory.frames import frame_trigger

        math_reasons = math_trigger(message, forced=math)
        finance_reasons = finance_trigger(message, forced=finance)
        frame_reasons = frame_trigger(message)
        draft_order = parse_order(message)
        if draft_order is None and not creative_reasons:
            draft_order = self.format_sense.classify(message)
        if draft_order is None:
            draft_reasons = []
        else:
            draft_reasons = draft_trigger(message) or [semantic_reason(draft_order)]
        self._turn = {
            "propositions": list(propositions or []),
            "payment": payment,
            "authority": authority,
            "objective": objective,
            "hypothesis": hypothesis,
            "causal_graph": causal_graph,
            "z_query": z_query,
            "allowed_sources": None if context is None else context.allowed_sources,
            "as_of": as_of,
        }
        result = self.graph.invoke(
            {
                "message": message,
                "tenant_id": self.tenant_id,
                "caller_id": None if context is None else context.caller_id,
                "request_id": None if context is None else context.request_id,
                "allowed_sources": None if context is None else sorted(context.allowed_sources),
                "discover": discover,
                "creative": bool(creative_reasons),
                "creative_reasons": creative_reasons,
                "deep": bool(deep_reasons),
                "deep_reasons": deep_reasons,
                "compare": bool(sides),
                "comparison_sides": sides,
                "summarize": bool(summary_reasons),
                "summary_reasons": summary_reasons,
                "explain": bool(explain_reasons),
                "explain_reasons": explain_reasons,
                "list": bool(list_reasons),
                "list_reasons": list_reasons,
                "sources": bool(source_reasons),
                "source_reasons": source_reasons,
                "math": bool(math_reasons),
                "math_reasons": math_reasons,
                "finance": bool(finance_reasons),
                "finance_reasons": finance_reasons,
                "frame": bool(frame_reasons),
                "frame_reasons": frame_reasons,
                "draft": bool(draft_reasons),
                "draft_reasons": draft_reasons,
                "draft_order": None
                if draft_order is None
                else {"format": draft_order.format_id, "topic": draft_order.topic},
            }
        )
        self._previous_ids = [
            str(item["chunk_id"]) for item in result.get("related") or [] if item.get("chunk_id")
        ]
        if realization == "evidence_neural" or account:
            from cpu_llm.realizer.ranker import apply_realization

            extra = apply_realization(
                result,
                realization=realization,
                account=account,
                memory=self.memory,
                causal_edges=list(getattr(causal_graph, "edges", None) or []),
            )
            result = {**result, **extra}
        result["child_safety"] = {"action": "off", "reasons": ["child safety is not applied"]}
        result["typos"] = typos
        result["tenant_id"] = self.tenant_id
        if context is not None:
            result["caller_id"] = context.caller_id
            result["request_id"] = context.request_id
        if typos:
            result["original_message"] = original_message
        return result

    def ask_concurrent(self, message: str, *, request_id: str | None = None, caller: Any | None = None, thinker_factory: Any = None, **kwargs: Any) -> dict[str, Any]:
        """Run ``ask`` on one seat lock and that seat's thinker.

        The ordinary ``ask`` stays on the calling thread and the appliance
        thinker. This path opens another local seat only when ``_place`` says
        the machine has the CPUs for another six processes. Otherwise the
        result is ``other_server`` and no second machine is started. A new
        seat builds its own thinker, so it does not take the first seat's
        evaluator-pool lock.
        """
        from cpu_llm.scale import EngineManager

        if self._seats is None:
            self._seats = EngineManager()
            self._seats.thinkers["engine-0"] = self.thinker
            self._seats.on_seat_failed = self._release_seat_thinker
        manager: EngineManager = self._seats
        factory = thinker_factory or self._thinker_factory
        context = caller if caller is None else _caller_for(self, caller)
        scope = [] if context is None else sorted(context.allowed_sources)
        rid = request_id or (None if context is None else context.request_id) or uuid.uuid4().hex

        def work() -> dict[str, Any]:
            seat_id = manager.current_seat()
            self._bound.thinker = manager.thinker_for(seat_id, factory)
            try:
                return self.ask(message, caller=caller, **kwargs)
            finally:
                self._bound.thinker = None

        outcome = manager.dispatch_turn(
            work,
            request_id=rid,
            tenant_id=self.tenant_id,
            caller_scope=scope,
            chunk_ids=[],
        )
        if outcome.get("error"):
            return outcome
        result = dict(outcome["result"])
        ids = _turn_chunk_ids(result)
        manager.publish_turn(
            request_id=rid,
            tenant_id=self.tenant_id,
            caller_scope=scope,
            chunk_ids=ids,
        )
        result["seat"] = outcome["seat"]
        result["request_id"] = rid
        return result

    def _release_seat_thinker(self, seat_id: str) -> None:
        manager = self._seats
        if manager is None or seat_id == "engine-0":
            return
        thinker = manager.thinkers.pop(seat_id, None)
        closer = getattr(thinker, "close", None)
        if closer is not None and thinker is not self.thinker:
            closer()

    def sleep(self, max_pairs: int = 500) -> int:
        """Judge stored word claims, then refresh relation tails on chunk tensors."""
        from cpu_llm.cortex_sleep import CortexSleepConsolidator
        from cpu_llm.relations import load_edges

        return CortexSleepConsolidator(
            self.memory,
            self.cognition,
            vector_db=self.index.db,
            relation_edges=load_edges(self.relations_path),
        ).run_sleep_cycle(max_pairs=max_pairs)

    def close(self) -> None:
        manager = self._seats
        if manager is not None:
            for thinker in list(manager.thinkers.values()):
                if thinker is not self.thinker:
                    closer = getattr(thinker, "close", None)
                    if closer is not None:
                        closer()
            manager.thinkers.clear()
            manager.close()
            self._seats = None
        self.thinker.close()

    def __enter__(self) -> Appliance:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def _taxonomy_indexer(appliance: Appliance):
    from cpu_llm.taxonomy import IngestTaxonomyIndexer

    return IngestTaxonomyIndexer(appliance.resonance)


def _remember_chunk(
    store: SqliteGraphStore,
    document_id: str,
    chunk_text: str,
    tensor: np.ndarray,
    proposition: EIRProposition | None,
    tags: list[Any] | None = None,
    relation_hands: dict[int, list[str]] | None = None,
) -> None:
    known = {node.id: node for node in store.all_nodes()}
    op = _assimilation(
        store,
        document_id,
        chunk_text,
        tensor,
        proposition,
        known,
        {},
        tags,
        relation_hands,
    )
    if op is not None:
        store.apply(StateDelta(ops=[op]))


def _assimilation(
    store: SqliteGraphStore,
    document_id: str,
    chunk_text: str,
    tensor: np.ndarray,
    proposition: EIRProposition | None,
    known: dict[str, Node],
    pending: dict[str, str],
    tags: list[Any] | None = None,
    relation_hands: dict[int, list[str]] | None = None,
) -> DeltaOp | None:
    payload = proposition.model_dump(mode="json") if proposition is not None else None
    tag_payload = [tag.model_dump() for tag in tags] if tags else []
    existing_id = pending.get(chunk_text.strip().lower()) or store.find_node_by_label(chunk_text)
    current = known.get(existing_id) if existing_id is not None else None
    attributes: dict[str, Any] = dict(current.attributes) if current is not None else {}
    from cpu_llm.memory.frames import frame_from_chunk

    frame = frame_from_chunk(document_id, chunk_text)
    if payload is not None:
        attributes["proposition"] = payload
    if frame is not None:
        attributes["event_frame"] = frame
    else:
        attributes.pop("event_frame", None)
    if tag_payload:
        attributes["taxonomy_tags"] = tag_payload
    if relation_hands and any(relation_hands.values()):
        attributes["relation_hands"] = {str(hand): words for hand, words in relation_hands.items()}
    if "related_terms" not in attributes:
        attributes["related_terms"] = []
    if existing_id is not None:
        same_proposition = current is not None and current.attributes.get("proposition") == attributes.get("proposition")
        same_tags = current is not None and current.attributes.get("taxonomy_tags") == attributes.get("taxonomy_tags")
        same_hands = current is not None and current.attributes.get("relation_hands") == attributes.get("relation_hands")
        same_frame = current is not None and current.attributes.get("event_frame") == attributes.get("event_frame")
        if payload is None and not tag_payload and not relation_hands and frame is None:
            return None
        if same_proposition and same_tags and same_hands and same_frame:
            return None
        node_id = existing_id
    else:
        node_id = document_id
    return DeltaOp(
        operation=Operation.ASSIMILATE,
        node=Node(
            id=node_id,
            label=chunk_text,
            kind="chunk",
            embedding=[float(value) for value in tensor],
            attributes=attributes,
        ),
        reason="vectorprism chunk",
    )


def _stored_proposition(store: SqliteGraphStore, chunk_text: str, tensor: np.ndarray) -> EIRProposition | None:
    node_id = store.find_node_by_label(chunk_text)
    if node_id is not None:
        node = next((item for item in store.all_nodes() if item.id == node_id), None)
        if node is None or node.label != chunk_text:
            return None
        raw = node.attributes.get("proposition")
        if isinstance(raw, dict):
            return EIRProposition.model_validate(raw)
        return None
    subgraph = store.retrieve([float(value) for value in tensor], k=4)
    for node in subgraph.nodes:
        if node.label != chunk_text:
            continue
        raw = node.attributes.get("proposition")
        if isinstance(raw, dict):
            return EIRProposition.model_validate(raw)
    return None


def graph_identity(tenant_id: str) -> tuple[str, str]:
    """The Chorus graph tenant and id for one appliance."""
    return tenant_id, f"appliance_{tenant_id}"


def empty_scope_result(tenant_id: str, message: str, context: CallerContext | None) -> dict[str, Any] | None:
    """The empty-retrieval reply when this caller may read no source.

    Returned before typo correction and before ``encode_query``. ``None`` means
    the turn may continue.
    """
    if context is None or context.allowed_sources:
        return None
    reply = compose_reply(
        {"message": message, "guard_decision": "allow", "related": [], "tenant_id": tenant_id}
    )
    return {
        "answer": None,
        "reply": reply,
        "related": [],
        "tenant_id": tenant_id,
        "caller_id": context.caller_id,
        "request_id": context.request_id,
        "access_error": "allowed_sources_empty",
        "typos": [],
    }


def _caller_for(appliance: Appliance, caller: Any | None) -> CallerContext | None:
    if caller is None:
        return None
    if not isinstance(caller, CallerContext):
        raise TypeError("caller must be a CallerContext")
    if caller.tenant_id != appliance.tenant_id:
        raise TenantNotFoundError("the caller is not a member of this appliance")
    return caller


def _compile(appliance: Appliance):
    tenant_id, graph_id = graph_identity(appliance.tenant_id)
    graph = Graph(tenant_id=tenant_id, graph_id=graph_id)
    graph.add_node("guard", dict_node_adapter(_guard(appliance), hop="guard"))
    graph.add_node("retrieve", dict_node_adapter(_retrieve(appliance), hop="retrieve"))
    graph.add_node("resonate", dict_node_adapter(_resonate(appliance), hop="resonate"))
    for channel_name in ("dense", "relational", "disentangled", "hyperbolic", "identity", "causal"):
        graph.add_node(channel_name, dict_node_adapter(_channel(appliance, channel_name), hop=channel_name))
    graph.add_node("catalog", dict_node_adapter(_catalog(appliance), hop="catalog"))
    graph.add_node("detail", dict_node_adapter(_detail, hop="detail"))
    graph.add_node("spans", dict_node_adapter(_spans(appliance), hop="spans"))
    graph.add_node("think", dict_node_adapter(_think(appliance), hop="think"))
    graph.add_node("cognize", dict_node_adapter(_cognize(appliance), hop="cognize"))
    graph.add_node("grammar", dict_node_adapter(_grammar(appliance), hop="grammar"))
    graph.add_node("shine", dict_node_adapter(_shine(appliance), hop="shine"))
    graph.add_node("reply", dict_node_adapter(_reply, hop="reply"))
    graph.add_node("imagine", dict_node_adapter(_imagine(appliance), hop="imagine"))
    graph.add_node("gather", dict_node_adapter(_gather(appliance), hop="gather"))
    graph.add_node("deep", dict_node_adapter(_deep(appliance), hop="deep"))
    graph.add_node("compare", dict_node_adapter(_compare(appliance), hop="compare"))
    graph.add_node("brief", dict_node_adapter(_brief(appliance), hop="brief"))
    graph.add_node("math", dict_node_adapter(_math(appliance), hop="math"))
    graph.add_node("finance", dict_node_adapter(_finance(appliance), hop="finance"))
    graph.add_node("frame", dict_node_adapter(_frame(appliance), hop="frame"))
    graph.add_node("model01", dict_node_adapter(_model01, hop="model01"))
    graph.add_node("discover", dict_node_adapter(_discover(appliance), hop="discover"))
    graph.add_edge(START, "guard")
    graph.add_conditional_edges("guard", _after_guard, {"retrieve": "retrieve", "reply": "reply"})
    graph.add_edge("retrieve", "resonate")
    graph.add_edge("resonate", "dense")
    graph.add_edge("dense", "relational")
    graph.add_edge("relational", "disentangled")
    graph.add_edge("disentangled", "hyperbolic")
    graph.add_edge("hyperbolic", "identity")
    graph.add_edge("identity", "causal")
    graph.add_edge("causal", "catalog")
    graph.add_edge("catalog", "detail")
    graph.add_edge("detail", "spans")
    graph.add_edge("spans", "think")
    graph.add_edge("think", "cognize")
    graph.add_edge("cognize", "grammar")
    graph.add_edge("grammar", "shine")
    graph.add_conditional_edges(
        "shine",
        _after_shine,
        {
            "deep": "deep",
            "gather": "gather",
            "compare": "compare",
            "brief": "brief",
            "math": "math",
            "finance": "finance",
            "frame": "frame",
            "model01": "model01",
            "reply": "reply",
        },
    )
    graph.add_conditional_edges(
        "deep",
        _after_deep,
        {
            "gather": "gather",
            "compare": "compare",
            "brief": "brief",
            "math": "math",
            "finance": "finance",
            "frame": "frame",
            "model01": "model01",
            "reply": "reply",
        },
    )
    graph.add_edge("gather", "imagine")
    graph.add_conditional_edges(
        "imagine",
        _after_imagine,
        {
            "compare": "compare",
            "brief": "brief",
            "math": "math",
            "finance": "finance",
            "frame": "frame",
            "model01": "model01",
            "reply": "reply",
        },
    )
    graph.add_conditional_edges(
        "compare",
        _after_compare,
        {"brief": "brief", "math": "math", "finance": "finance", "frame": "frame", "model01": "model01", "reply": "reply"},
    )
    graph.add_conditional_edges(
        "brief",
        _after_brief,
        {"math": "math", "finance": "finance", "frame": "frame", "model01": "model01", "reply": "reply"},
    )
    graph.add_conditional_edges(
        "math", _after_math, {"finance": "finance", "frame": "frame", "model01": "model01", "reply": "reply"}
    )
    graph.add_conditional_edges(
        "finance", _after_finance, {"frame": "frame", "model01": "model01", "reply": "reply"}
    )
    graph.add_edge("frame", "model01")
    graph.add_edge("model01", "reply")
    graph.add_conditional_edges("reply", _after_reply, {"discover": "discover", "end": END})
    graph.add_edge("discover", END)
    return graph.compile()


def _guard(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        result = appliance.guard.check(state.get("message") or "")
        update: dict[str, Any] = {
            "guard_decision": result.decision,
            "guard_category": result.matched_category,
        }
        if result.decision != "allow":
            update["answer"] = "The prompt was blocked by PrismGuard."
        return update

    return node


def _after_guard(state: dict[str, Any]) -> str:
    if state.get("guard_decision") == "allow":
        return "retrieve"
    return "reply"


def _reply(state: dict[str, Any]) -> dict[str, Any]:
    reply = compose_reply(state)
    update: dict[str, Any] = {"reply": reply}
    status = reply.get("answer_status")
    if not status:
        return update
    update["answer_status"] = status
    update["answer_evidence"] = list(reply.get("answer_evidence") or [])
    update["verification_scope"] = reply.get("verification_scope")
    update["retrieved_candidates"] = list(reply.get("retrieved_candidates") or [])
    if status in {"insufficient_evidence", "conflicting", "evidence_quote"}:
        update["answer"] = None
    elif status == "answered" and reply.get("supported_text"):
        update["answer"] = reply["supported_text"]
    return update


def _after_shine(state: dict[str, Any]) -> str:
    """First optional agent. Later agents still run when the prompt names them."""
    if state.get("delivery_blocked"):
        # Agents that read the retrieved sentence are skipped. Math and finance
        # read the question, so a rejected sentence does not cancel them.
        return _else_math(state, "reply")
    if state.get("deep") is True:
        return "deep"
    if state.get("creative") is True:
        return "gather"
    if state.get("compare") is True:
        return "compare"
    if _wants_brief(state):
        return "brief"
    return _else_math(state, "reply")


def _after_deep(state: dict[str, Any]) -> str:
    if state.get("creative") is True:
        return "gather"
    if state.get("compare") is True:
        return "compare"
    if _wants_brief(state):
        return "brief"
    return _else_math(state, "reply")


def _after_imagine(state: dict[str, Any]) -> str:
    if state.get("compare") is True:
        return "compare"
    if _wants_brief(state):
        return "brief"
    return _else_math(state, "reply")


def _after_compare(state: dict[str, Any]) -> str:
    if _wants_brief(state):
        return "brief"
    return _else_math(state, "reply")


def _after_brief(state: dict[str, Any]) -> str:
    return _else_math(state, "reply")


def _after_math(state: dict[str, Any]) -> str:
    return _else_finance(state, "reply")


def _after_finance(state: dict[str, Any]) -> str:
    return _else_frame(state, "reply")


def _delivery_rejected(state: dict[str, Any]) -> bool:
    """A Shine, audit, or grammar rejection is the final delivery decision."""
    if state.get("delivery_blocked"):
        return True
    if state.get("shine_enforced"):
        return True
    return state.get("shine_ok") is False


def _else_math(state: dict[str, Any], destination: str) -> str:
    """Run the math agent before the reply when the prompt asked for a calculation.

    The calculation does not read the retrieved sentence, so a Shine or audit rejection of that
    sentence does not cancel it. A guard block never reaches this point.
    """
    if destination == "reply" and state.get("math") is True and state.get("guard_decision", "allow") == "allow":
        return "math"
    return _else_finance(state, destination)


def _else_finance(state: dict[str, Any], destination: str) -> str:
    """Run the finance checks before the reply when the prompt asked for one.

    The check reads the fields in the question. A Shine or audit rejection of
    the retrieved sentence does not cancel it. A guard block never reaches it.
    """
    if destination == "reply" and state.get("finance") is True and state.get("guard_decision", "allow") == "allow":
        return "finance"
    return _else_frame(state, destination)


def _else_frame(state: dict[str, Any], destination: str) -> str:
    """Answer from a stored event frame, then let Model01 write the sentence."""
    if destination == "reply" and state.get("guard_decision") not in (None, "allow"):
        return "reply"
    if destination == "reply" and state.get("frame") is True and not _delivery_rejected(state):
        return "frame"
    if destination == "reply":
        return "model01"
    return destination


def _model01(state: dict[str, Any]) -> dict[str, Any]:
    """The sentence generator. It runs after the specialists and before the reply.

    A retrieved paragraph that shares no word with the prompt is not a source
    for this sentence. Math and finance still read the question.
    """
    from cpu_llm.model01.generator import generate

    rejected = _delivery_rejected(state)
    message = str(state.get("message") or "")
    related = _passages_for_sentence(message, list(state.get("related") or []))
    chunks = [
        (str(item.get("chunk_id") or ""), str(item.get("chunk_text") or ""))
        for item in related
        if item.get("chunk_id") and item.get("chunk_text")
    ]
    attributes = {
        str(item.get("chunk_id")): item["attributes"]
        for item in state.get("related") or []
        if item.get("chunk_id") and isinstance(item.get("attributes"), dict)
    }
    outcome = generate(
        message,
        chunks,
        attributes=attributes or None,
        math_result=state.get("math_result") if isinstance(state.get("math_result"), dict) else None,
        delivery_rejected=rejected,
    )
    entity = _prompt_entity(message)
    if entity:
        outcome["scoped_entity"] = entity
        outcome["scoped_passages"] = [
            {"chunk_id": str(item.get("chunk_id") or ""), "chunk_text": str(item.get("chunk_text") or "")}
            for item in related
            if item.get("chunk_text")
        ]
    return {"model01": outcome}


_MODEL01_SKIP = frozenset(
    """
    what which who how why when where this that these those with from into
    about there here best worst better worse highest lowest
    tell me please describe explain show give the a an of to and or in on for
    by as is are was were be
    """.split()
)
_ABOUT_ENTITY = re.compile(
    r"^(?:please\s+)?(?:tell\s+me\s+about|describe|explain)\s+(?P<entity>.+?)\s*[.?!]*$",
    re.IGNORECASE,
)


def _passages_for_sentence(question: str, related: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Passages that name the asked entity. The others stay on the turn for the other agents.

    A multi-word name has to appear as that name. ``harbor`` alone does not
    select a sentence about a harbor. A short name such as ``Ada`` is kept.
    """
    entity = _prompt_entity(question)
    if entity:
        return [item for item in related if _entity_in_text(entity, str(item.get("chunk_text") or ""))]
    words = _prompt_terms(question)
    if not words:
        return []
    return [
        item
        for item in related
        if words & _text_tokens(str(item.get("chunk_text") or ""))
    ]


def _prompt_entity(question: str) -> str:
    """The subject a supported question names, including a short proper name.

    Instruction words and a leading determiner are removed. Words inside the
    name, such as ``of`` and ``and``, stay part of the name.
    """
    text = " ".join((question or "").strip().split())
    about = _ABOUT_ENTITY.match(text)
    if about:
        return _named_entity(about.group("entity"))
    from cpu_llm.answerability import parse_query

    plan = parse_query(text)
    if plan is None:
        return ""
    return _named_entity(str(plan.get("subject") or plan.get("entity") or ""))


_LEADING_DETERMINER = re.compile(r"^(?:the|a|an)\s+", re.IGNORECASE)


def _named_entity(text: str) -> str:
    phrase = " ".join((text or "").strip().strip(" ?.!\"'").split())
    return _LEADING_DETERMINER.sub("", phrase).strip()


def _content_phrase(text: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[A-Za-z][A-Za-z'-]*", text or "")
        if token.casefold() not in _MODEL01_SKIP and len(token) >= 2
    ]
    return " ".join(tokens)


def _prompt_terms(question: str) -> set[str]:
    return {token.casefold() for token in _content_phrase(question).split()}


def _text_tokens(text: str) -> set[str]:
    return {token.casefold() for token in re.findall(r"[A-Za-z][A-Za-z'-]*", text)}


def _entity_in_text(entity: str, text: str) -> bool:
    if not entity:
        return False
    return re.search(rf"(?<![A-Za-z]){re.escape(entity)}(?![A-Za-z])", text, re.IGNORECASE) is not None


def _wants_brief(state: dict[str, Any]) -> bool:
    return any(state.get(flag) is True for flag in ("summarize", "explain", "list", "sources"))


def _after_reply(state: dict[str, Any]) -> str:
    if state.get("guard_decision") != "allow":
        return "end"
    if state.get("discover") is True:
        return "discover"
    return "end"


def _channel(appliance: Appliance, name: str):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        passages = _passages(appliance, state)
        flags = appliance.index.pipeline.enabled_channels
        anchor_set, anchor = _identity_anchor(appliance)
        propositions = {}
        if name == "relational":
            propositions = {
                passage["document_id"]: _stored_proposition(
                    appliance.memory,
                    passage["chunk_text"],
                    np.asarray(passage["tensor"], dtype=np.float32),
                )
                for passage in passages
            }
        query = (appliance._turn or {}).get("z_query")
        reading = read_channel(
            name,
            state.get("message") or "",
            passages,
            query_tensor=None if query is None else np.asarray(query, dtype=np.float64),
            propositions=propositions,
            enabled=bool(flags.get(name)),
            anchor_set=anchor_set,
            anchor=anchor,
        )
        readings = list(state.get("channel_readings") or [])
        readings.append(reading)
        return {"channel_readings": readings}

    return node


def _detail(state: dict[str, Any]) -> dict[str, Any]:
    report = judge_readings(
        state.get("message") or "",
        list(state.get("channel_readings") or []),
        [item.get("category") or "" for item in state.get("related") or []],
    )
    return {
        "channel_report": report,
        "discovery_suggested": report["discovery_suggested"],
        "discovery_reasons": report["discovery_reasons"],
    }


def _passages(appliance: Appliance, state: dict[str, Any]) -> list[dict[str, Any]]:
    hits = {hit["document_id"]: hit for hit in (appliance._turn or {}).get("hits") or []}
    passages: list[dict[str, Any]] = []
    for item in state.get("related") or []:
        hit = hits.get(item["chunk_id"])
        if hit is None:
            continue
        passages.append(
            {
                "document_id": item["chunk_id"],
                "chunk_text": item["chunk_text"],
                "tensor": np.asarray(hit["tensor_1024d"], dtype=np.float64).reshape(-1),
            }
        )
    return passages


def _identity_anchor(appliance: Appliance) -> tuple[bool, np.ndarray]:
    raw = appliance.index.pipeline.adapter.identity_anchor_v0.detach().cpu().numpy()
    anchor = np.asarray(raw, dtype=np.float64).reshape(-1)
    return float(np.linalg.norm(anchor)) > 0.0, anchor


def _catalog(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        labeled = label_retrieval(
            state.get("message") or "",
            list(state.get("related") or []),
            tenant_id=str(state.get("tenant_id") or appliance.tenant_id),
        )
        return {
            "related": labeled["related"],
            "query_category": labeled["query_category"],
            "rag_hits": labeled["rag_hits"],
            "rag_retrieval_mode": labeled["rag_retrieval_mode"],
        }

    return node


def _shine(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        checked = verify_grounding(
            appliance.shine,
            question=state.get("message") or "",
            answer=state.get("answer"),
            related=list(state.get("related") or []),
            query_category=state.get("query_category"),
            abstention=bool(state.get("abstention_triggered")),
        )
        update = {
            "shine_decision": checked["shine_decision"],
            "shine_resolution_gate": checked["shine_resolution_gate"],
            "shine_signatures": checked["shine_signatures"],
            "shine_ok": checked["shine_ok"],
            "shine_enforced": checked["shine_enforced"],
            "shine_unmatched_measurements": checked["shine_unmatched_measurements"],
        }
        if checked["answer"] is not None:
            update["answer"] = checked["answer"]
        return update

    return node


def _payment_evaluator():
    from prismagenticpay.core.evaluator import PrismThinkerPaymentEvaluator
    from prismagenticpay.policies.corporate import default_corporate_policies

    return PrismThinkerPaymentEvaluator(default_corporate_policies())


def evaluate_payment(evaluator, proposal, authority):
    """Run the corporate policy with a fresh authority snapshot.

    PrismAgenticPay withholds a fact that has no source timestamp. The
    snapshot just taken is the source, with the library's own freshness record.
    """
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    facts = evaluator._structured_facts(proposal, authority)
    metadata = evaluator._fresh_metadata(facts, now)
    return evaluator.evaluate_proposal(proposal, authority, fact_metadata=metadata, now=now)


def _deep(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.deep_search import collect_possibilities
        from cpu_llm.relations import load_edges

        edges = load_edges(appliance.relations_path)
        sides = list(state.get("comparison_sides") or [])
        if sides:
            gathered = possibilities_by_side(sides, appliance.word_tags, edges, appliance.index)
        else:
            gathered = collect_possibilities(state.get("message") or "", appliance.word_tags, edges)
        texts: dict[str, str] = {}
        tensors: dict[str, Any] = {}
        allowed = state.get("allowed_sources")
        gathered["possibilities"] = keep_allowed(list(gathered["possibilities"]), allowed)
        ids = [item["document_id"] for item in gathered["possibilities"]]
        if ids and hasattr(appliance.index.db, "get_by_ids"):
            for row in appliance.index.db.get_by_ids(ids):
                document_id = str(row["document_id"])
                texts[document_id] = str(row.get("chunk_text") or "")
                if row.get("tensor_1024d") is not None:
                    tensors[document_id] = row["tensor_1024d"]
        appliance._deep_tensors = tensors
        query = (getattr(appliance, "_turn", None) or {}).get("z_query")
        floor = getattr(appliance, "deep_min_similarity", None)
        possibilities = []
        for item in gathered["possibilities"]:
            copy = dict(item)
            document_id = str(item["document_id"])
            copy["chunk_text"] = texts.get(document_id, "")
            copy["similarity"] = _dense_similarity(query, tensors.get(document_id))
            possibilities.append(copy)
        reached = len(possibilities)
        # The relation walk keeps every paragraph it reaches. Rank them on the trained dense core and keep
        # the ones that read like the question, so a shared generic word does not bring in another topic.
        if floor is not None and query is not None:
            possibilities = [item for item in possibilities if (item["similarity"] or 0.0) >= floor]
        possibilities.sort(key=lambda item: -(item["similarity"] or 0.0))
        return {
            "deep_reasons": list(state.get("deep_reasons") or []),
            "possibilities": possibilities,
            "possibility_count": len(possibilities),
            "possibilities_reached": reached,
            "deep_seeds": gathered["seeds"],
            "deep_hands": gathered["hands"],
        }

    return node


def _namespace_slug(namespace: str) -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", namespace.lower()).strip("_")[:48]
    if not slug:
        raise ValueError("namespace must contain letters or digits")
    return slug


def _local_dsn() -> str:
    from cpu_llm.retrieval import LOCAL_PG_DSN

    return LOCAL_PG_DSN


def _namespace_dsn(dsn: str, namespace: str) -> str:
    """Same database, a schema of its own. The vector type stays in public."""
    import psycopg

    schema = f"ns_{namespace}"
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
    sep = "&" if "?" in dsn else "?"
    return f"{dsn}{sep}options=-csearch_path%3D{schema}%2Cpublic"


def _dense_similarity(query: Any, tensor: Any) -> float | None:
    """Cosine on the trained dense core [16:384]. None when either vector is missing."""
    if query is None or tensor is None:
        return None
    left = np.asarray(query, dtype=np.float64).reshape(-1)[16:384]
    right = np.asarray(tensor, dtype=np.float64).reshape(-1)[16:384]
    denom = float(np.linalg.norm(left) * np.linalg.norm(right))
    return float(left @ right / denom) if denom else None


def _frame(appliance: Appliance):
    """Join stored event roles. The joined sentence is not a new proposition."""

    del appliance

    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.memory.frames import SCHEMA, frame_from_chunk, resolve_frames

        frames = []
        seen: set[str] = set()
        rows = list(state.get("passages") or [])
        rows.extend(state.get("related") or [])
        for row in rows:
            document_id = str(row.get("document_id") or row.get("chunk_id") or "")
            text = str(row.get("chunk_text") or "")
            if not document_id or document_id in seen:
                continue
            if not text and not isinstance(row.get("event_frame"), dict):
                continue
            seen.add(document_id)
            stored = row.get("event_frame")
            if isinstance(stored, dict) and stored.get("schema") == SCHEMA:
                frame = stored
            else:
                frame = frame_from_chunk(document_id, text) if text else None
            if frame is not None:
                frames.append(frame)
        result = resolve_frames(state.get("message") or "", frames)
        return {
            "frame_reasons": list(state.get("frame_reasons") or []),
            "frame_result": result,
            "frame_verified": result.get("verified") is True,
        }

    return node


def _finance(appliance: Appliance):
    """Validate the finance fields in the prompt. The verdict is not a proposition."""

    del appliance

    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.finance import run_finance

        reasons = list(state.get("finance_reasons") or [])
        return {
            "finance_reasons": reasons,
            "finance_result": run_finance(state.get("message") or "", reasons=reasons),
        }

    return node


def _math(appliance: Appliance):
    """Evaluate the prompt's arithmetic. The number is not stored as a proposition."""

    del appliance

    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.math import solve_math

        return {
            "math_reasons": list(state.get("math_reasons") or []),
            "math_result": solve_math(state.get("message") or ""),
        }

    return node


def _compare(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.gather import gather_article

        covered = []
        query = (appliance._turn or {}).get("z_query")
        for side in list(state.get("comparison_sides") or []):
            rows = _rows_for_agent(appliance, state, side)
            if not rows:
                covered.append({"label": side, "text": "", "articles": [], "links": []})
                continue
            pool = gather_article(side, rows, query)
            realized = _realize_pool(appliance, side, rows, pool)
            covered.append(
                {
                    "label": side,
                    "text": realized["text"],
                    "articles": list(pool.get("articles") or []),
                    "links": realized["links"],
                }
            )
        return {"comparison": {"sides": covered}}

    return node


def _brief(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.summarize import LIST_KEEP, SUMMARY_KEEP, cause_first, rank_by_cognition, topic_words
        from cpu_llm.clauses import proposition_from_chunk
        from cpu_llm.manifest_spans import answer_numbers_allowed, build_span_grammar

        rows = _brief_rows(appliance, state)
        query = (appliance._turn or {}).get("z_query")
        if query is None:
            query = np.zeros(TENSOR_DIM, dtype=np.float32)
        propositions = []
        tensors = []
        texts: dict[str, str] = {}
        origins: dict[str, str] = {}
        for row in rows:
            tensor = row.get("tensor_1024d")
            if tensor is None:
                continue
            document_id = str(row["document_id"])
            text = str(row.get("chunk_text") or "")
            proposition = None
            if text:
                proposition = _stored_proposition(
                    appliance.memory,
                    text,
                    np.asarray(tensor, dtype=np.float32).reshape(-1),
                )
            if proposition is None:
                proposition = proposition_from_chunk(document_id, text)
            if proposition is None:
                continue
            propositions.append(proposition)
            tensors.append(np.asarray(tensor, dtype=np.float32).reshape(-1))
            texts[proposition.proposition_id] = text
            origins[proposition.proposition_id] = document_id
        ranked: list[Any] = []
        if propositions:
            result = appliance.cognition.deliberate(
                np.asarray(query, dtype=np.float32).reshape(-1),
                propositions,
                tensors,
                state.get("tenant_id") or "cpu-llm",
            )
            tensors_by_id = {
                proposition.proposition_id: tensor for proposition, tensor in zip(propositions, tensors)
            }
            ranked = rank_by_cognition(result, tensors_by_id)
        index, mask = build_span_grammar(
            [{"chunk_id": str(row["document_id"]), "chunk_text": str(row.get("chunk_text") or "")} for row in rows]
        )

        def speak(selected: list[Any], limit: int) -> tuple[str, list[str]]:
            sentences: list[str] = []
            sources: list[str] = []
            for proposition in selected:
                if len(sentences) >= limit:
                    break
                sentence, delivered = appliance.realizer.synthesize([proposition], [])
                if not sentence or not appliance.auditor.audit_delivered_output(delivered, [proposition]):
                    continue
                if not answer_numbers_allowed(sentence, index, mask):
                    continue
                sentences.append(sentence)
                document_id = origins.get(proposition.proposition_id)
                if document_id and document_id not in sources:
                    sources.append(document_id)
            return " ".join(sentences), sources

        summary, summary_sources = ("", [])
        explanation, explanation_sources = ("", [])
        listed, list_sources = ("", [])
        if state.get("summarize") is True:
            summary, summary_sources = speak(ranked, SUMMARY_KEEP)
        if state.get("explain") is True:
            explanation, explanation_sources = speak(cause_first(ranked, texts), SUMMARY_KEEP)
        if state.get("list") is True:
            spoken, list_sources = speak(ranked, LIST_KEEP)
            listed = "\n".join(_sentence_lines(spoken))
        source_ids: list[str] = []
        for document_id in summary_sources + explanation_sources + list_sources:
            if document_id not in source_ids:
                source_ids.append(document_id)
        if state.get("sources") is True and not source_ids:
            from cpu_llm.answerability import supporting_ids

            bound = supporting_ids(state.get("message") or "", list(state.get("related") or []))
            if bound is not None:
                source_ids = bound
            else:
                for item in state.get("related") or []:
                    document_id = str(item.get("chunk_id") or "")
                    if document_id and document_id not in source_ids:
                        source_ids.append(document_id)
        return {
            "brief": {
                "summary": summary,
                "explanation": explanation,
                "list": listed,
                "sources": source_ids,
                "weights": [float(item.epistemic_weight) for item in ranked[:SUMMARY_KEEP]],
            }
        }

    return node


def _sentence_lines(text: str) -> list[str]:
    parts = [part.strip() for part in text.split(". ") if part.strip()]
    lines = []
    for part in parts:
        lines.append(part if part.endswith(".") else f"{part}.")
    return lines


def _brief_rows(appliance: Appliance, state: dict[str, Any]) -> list[dict[str, Any]]:
    from cpu_llm.agents.summarize import topic_words

    rows = _possibility_rows(state, tensors=appliance._deep_tensors)
    if rows:
        return rows
    collected: list[dict[str, Any]] = []
    seen: set[str] = set()
    for side in list(state.get("comparison_sides") or []):
        for row in _rows_for_agent(appliance, state, side):
            document_id = str(row["document_id"])
            if document_id in seen:
                continue
            seen.add(document_id)
            collected.append(row)
    if collected:
        return collected
    if topic_words(state.get("message") or ""):
        cleaned = " ".join(topic_words(state.get("message") or ""))
        return rows_for_side(appliance.index, appliance.word_tags, cleaned)
    if appliance._previous_ids and hasattr(appliance.index.db, "get_by_ids"):
        return list(appliance.index.db.get_by_ids(appliance._previous_ids))
    return []


def _gather(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.gather import gather_article

        rows = _possibility_rows(state, tensors=appliance._deep_tensors)
        if not rows:
            related = list(state.get("related") or [])
            rows = appliance.index.chunks_for_articles([item["chunk_id"] for item in related])
            if not rows:
                rows = _shortlist_rows(appliance, related)
        turn = appliance._turn or {}
        turn["gathered_rows"] = rows
        appliance._turn = turn
        return {
            "creative_pool": gather_article(
                state.get("message") or "",
                rows,
                turn.get("z_query"),
            )
        }

    return node


def _realize_pool(
    appliance: Appliance,
    message: str,
    rows: list[dict[str, Any]],
    pool: dict[str, Any],
    *,
    vary: bool = False,
    avoid: set[str] | None = None,
) -> dict[str, Any]:
    from cpu_llm.agents.gather import realize_ranked_paragraphs
    from cpu_llm.clauses import proposition_from_chunk
    from cpu_llm.manifest_spans import answer_numbers_allowed, build_span_grammar

    index, mask = build_span_grammar(
        [{"chunk_id": str(row["document_id"]), "chunk_text": str(row.get("chunk_text") or "")} for row in rows]
    )

    def proposition_for(document_id: str, text: str, tensor: Any) -> Any:
        stored = None
        if tensor is not None:
            stored = _stored_proposition(
                appliance.memory,
                text,
                np.asarray(tensor, dtype=np.float32).reshape(-1),
            )
        if stored is not None:
            return stored
        return proposition_from_chunk(document_id, text)

    return realize_ranked_paragraphs(
        message,
        rows,
        pool,
        proposition_for,
        appliance.realizer,
        appliance.auditor,
        numbers_allowed=lambda sentence: answer_numbers_allowed(sentence, index, mask),
        vary=vary,
        avoid=avoid,
    )


def _imagine(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        from cpu_llm.agents.gather import gather_article

        sides = list(state.get("comparison_sides") or [])
        if sides:
            return _imagine_sides(appliance, state, sides)
        related = list(state.get("related") or [])
        if not related and not (appliance._turn or {}).get("gathered_rows"):
            return {
                "imagination": compose_imagination(state.get("message") or "", [], {}),
            }
        rows = _possibility_rows(state, tensors=appliance._deep_tensors) or (appliance._turn or {}).get("gathered_rows")
        if not rows:
            rows = appliance.index.chunks_for_articles([item["chunk_id"] for item in related])
        if not rows:
            rows = _shortlist_rows(appliance, related)
        turn = appliance._turn or {}
        query = turn.get("z_query")
        scores = _resonate_article(appliance, rows, query)
        pool = state.get("creative_pool") or gather_article(state.get("message") or "", rows, query)
        seen = appliance._creative_seen
        key = (state.get("message") or "").strip().casefold()
        avoid = {seen[key]} if key in seen else set()
        answer = str(state.get("answer") or "")
        if answer:
            avoid.add(answer)
        realized = _realize_pool(
            appliance,
            state.get("message") or "",
            rows,
            pool,
            vary=True,
            avoid=avoid,
        )
        if realized["text"]:
            seen[key] = realized["text"]
        chunks = [
            {
                "document_id": row["document_id"],
                "chunk_text": row["chunk_text"],
                "tensor": np.asarray(row["tensor_1024d"], dtype=np.float32).reshape(-1),
            }
            for row in rows
            if row.get("tensor_1024d") is not None
        ]
        walked = compose_imagination(state.get("message") or "", chunks, scores)
        imagined = {
            "triggered": True,
            "articles": pool.get("articles") or walked["articles"],
            "loaded": pool.get("paragraph_count", walked["loaded"]),
            "links": realized["links"],
            "keywords": [word for link in realized["links"] for word in link["keywords"]],
            "text": realized["text"],
            "note": (
                "A fresh arrangement of the checked sentences was drawn for this run. "
                "Each sentence was checked against its proposition and the numbers in the group."
            ),
            "pool": pool,
            "walk": {"loaded": walked["loaded"], "links": walked["links"]},
        }
        return {"imagination": imagined}

    return node


def _possibility_rows(
    state: dict[str, Any],
    side: str | None = None,
    tensors: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Rows the deep-search agent already kept, optionally for one topic."""
    items = list(state.get("possibilities") or [])
    if side is not None:
        items = [item for item in items if item.get("side") == side]
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    held = tensors or {}
    for item in items:
        document_id = str(item.get("document_id") or "")
        text = str(item.get("chunk_text") or "")
        if not document_id or not text or document_id in seen:
            continue
        seen.add(document_id)
        row = {"document_id": document_id, "chunk_text": text}
        tensor = held.get(document_id, item.get("tensor_1024d"))
        if tensor is not None:
            row["tensor_1024d"] = tensor
        rows.append(row)
    return rows


def _rows_for_agent(appliance: Appliance, state: dict[str, Any], side: str) -> list[dict[str, Any]]:
    """Prefer the chunks deep search already returned for this topic."""
    rows = _possibility_rows(state, side, appliance._deep_tensors)
    if rows:
        return rows
    return rows_for_side(appliance.index, appliance.word_tags, side)


def _imagine_sides(appliance: Appliance, state: dict[str, Any], sides: list[str]) -> dict[str, Any]:
    from cpu_llm.agents.gather import gather_article

    parts: list[str] = []
    links: list[dict[str, Any]] = []
    articles: list[str] = []
    loaded = 0
    query = (appliance._turn or {}).get("z_query")
    seen = appliance._creative_seen
    answer = str(state.get("answer") or "")
    for side in sides:
        rows = _rows_for_agent(appliance, state, side)
        loaded += len(rows)
        if not rows:
            parts.append(f"{side}:\nNo stored sentence for this side.")
            continue
        pool = gather_article(side, rows, query)
        for slug in pool.get("articles") or []:
            if slug not in articles:
                articles.append(slug)
        key = f"{(state.get('message') or '').strip().casefold()}::{side.casefold()}"
        avoid = {seen[key]} if key in seen else set()
        if answer:
            avoid.add(answer)
        realized = _realize_pool(appliance, side, rows, pool, vary=True, avoid=avoid)
        if realized["text"]:
            seen[key] = realized["text"]
            parts.append(f"{side}:\n{realized['text']}")
            links.extend(realized["links"])
        else:
            parts.append(f"{side}:\nNo stored sentence for this side.")
    return {
        "imagination": {
            "triggered": True,
            "articles": articles,
            "loaded": loaded,
            "links": links,
            "keywords": [word for link in links for word in link["keywords"]],
            "text": "\n\n".join(parts),
            "note": (
                "Each topic was drawn on its own. "
                "A later run draws another arrangement for every topic that has more than one sentence."
            ),
            "sides": list(sides),
        }
    }


def _shortlist_rows(appliance: Appliance, related: list[dict[str, Any]]) -> list[dict[str, Any]]:
    hits = {hit["document_id"]: hit for hit in (appliance._turn or {}).get("hits") or []}
    rows: list[dict[str, Any]] = []
    for item in related:
        hit = hits.get(item["chunk_id"])
        if hit is None or hit.get("tensor_1024d") is None:
            continue
        rows.append(
            {
                "document_id": item["chunk_id"],
                "chunk_text": item["chunk_text"],
                "tensor_1024d": hit["tensor_1024d"],
            }
        )
    return rows


def _resonate_article(appliance: Appliance, rows: list[dict[str, Any]], query: Any) -> dict[str, float]:
    if query is None or not rows:
        return {}
    kept: list[tuple[str, np.ndarray]] = []
    for row in rows:
        try:
            amplitude = resonance_amplitude(row["tensor_1024d"])
        except ValueError:
            continue
        kept.append((row["document_id"], amplitude))
    if not kept:
        return {}
    try:
        query_amplitude = resonance_amplitude(query)
    except ValueError:
        return {}
    for chunk_id, amplitude in kept:
        appliance.resonance.ingest(chunk_id, amplitude, frequency=FrequencyFamily.NEUTRAL)
    ranked = appliance.resonance.query(
        query_amplitude,
        FrequencyFamily.NEUTRAL,
        [chunk_id for chunk_id, _amplitude in kept],
        np.stack([amplitude for _chunk_id, amplitude in kept]),
        flat=True,
    )
    scores: dict[str, float] = {}
    for hit in ranked:
        score = float(hit.score)
        if math.isfinite(score):
            scores[hit.chunk_id] = score
    return scores


def _discover(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        return {"discovery": run_discovery(state)}

    return node


def _bind_stored_words(appliance: Appliance, chunks: list[tuple[str, str]], tensors: list[np.ndarray]) -> None:
    """Record the word index and checkpoint resonance. Relation tails are already stored."""
    bound = bind_word_taxonomy(
        appliance.resonance,
        chunks,
        tensors,
        tags_path=appliance.word_tags_path,
        tenant_id=appliance.tenant_id,
    )
    appliance.word_tags = bound["index"]


def _passage_edges(appliance: Appliance, chunks: list[tuple[str, str]]):
    from cpu_llm.relations import merge_passage_edges

    return merge_passage_edges(appliance.relations_path, chunks, appliance.word_tags)


def _signed_row(db, document_id: str, text: str, tensor: np.ndarray, edges):
    from cpu_llm.relations import apply_relation_signature, hands_for_text
    from cpu_llm.word_taxonomy import write_stamped_tensor

    hands = hands_for_text(edges, text)
    if not any(hands.values()):
        return tensor, hands
    signed = apply_relation_signature(tensor, hands)
    write_stamped_tensor(db, document_id, text, signed)
    return signed, hands


def _with_tagged_paragraphs(
    appliance: Appliance,
    message: str,
    hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Add a tagged paragraph when the shortlist missed the query word.

    An empty shortlist stays empty. A word already written in a retrieved
    paragraph is not used to pull in another article.
    """
    if not hits:
        return hits
    present = {word for hit in hits for word in _content_words(str(hit.get("chunk_text") or ""))}
    allowed = {article_slug(str(hit["document_id"])) for hit in hits}
    wanted = recall_document_ids(
        appliance.resonance,
        appliance.word_tags,
        message,
        skip_words=present,
        allowed_slugs=allowed,
    )
    have = {str(hit["document_id"]) for hit in hits}
    missing = [document_id for document_id in wanted if document_id not in have]
    if not missing or not hasattr(appliance.index.db, "get_by_ids"):
        return hits
    added = list(hits)
    for row in appliance.index.db.get_by_ids(missing):
        added.append(
            {
                "document_id": row["document_id"],
                "chunk_text": row["chunk_text"],
                "tensor_1024d": np.asarray(row["tensor_1024d"], dtype=np.float32).reshape(-1),
                "final_score": 0.0,
            }
        )
    return added


def _retrieve(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        message = state.get("message") or ""
        turn = appliance._turn or {}
        z_query = turn.get("z_query")
        if z_query is None:
            z_query = np.asarray(appliance.index.encode_query(message), dtype=np.float32).reshape(TENSOR_DIM)
            turn["z_query"] = z_query
        allowed = (appliance._turn or {}).get("allowed_sources")
        as_of = (appliance._turn or {}).get("as_of")
        if allowed is None:
            hits = appliance.index.search(message, top_k=5, query_tensor=z_query, as_of=as_of)
        else:
            hits = appliance.index.search_allowed(
                message, set(allowed), top_k=5, query_tensor=z_query, as_of=as_of
            )
        named = _hits_for_named_article(appliance.index, message, hits)
        if named:
            hits = named
        hits = _with_tagged_paragraphs(appliance, message, hits)
        hits = keep_allowed(hits, allowed)
        from cpu_llm.corrections import conflict_among

        conflict = conflict_among(appliance.memory, hits)
        turn["hits"] = hits
        appliance._turn = turn
        return {
            "correction_conflict": conflict,
            "passages": [
                {
                    "document_id": hit["document_id"],
                    "chunk_text": hit["chunk_text"],
                    "final_score": float(hit["final_score"]),
                }
                for hit in hits
            ]
        }

    return node


def _hits_for_named_article(index, message: str, hits: list[dict[str, Any]]) -> list[dict[str, Any]] | None:
    """Keep every article the question names, once that article's lead is stored.

    Neighbors from unnamed articles are left out. Each lead is added when the
    scan missed it. Leads come first, then the other stored hits from those
    articles, in the order the scan returned them.
    """
    matched: list[dict[str, Any]] = []
    seen: set[str] = set()
    found = False
    for slug in title_slugs(message):
        lead = index.lead_for_slug(slug)
        if lead is None:
            continue
        found = True
        kept = [hit for hit in hits if article_slug(str(hit["document_id"])) == slug]
        if str(lead["document_id"]) not in {str(hit["document_id"]) for hit in kept}:
            kept.insert(0, lead)
        for hit in kept:
            document_id = str(hit["document_id"])
            if document_id in seen:
                continue
            seen.add(document_id)
            matched.append(hit)
    if not found:
        return None
    return matched


def _resonate(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        turn = appliance._turn or {}
        hits = turn.get("hits") or []
        if not hits:
            return {"related": []}
        ids = [hit["document_id"] for hit in hits]
        amplitudes = np.stack(
            [
                resonance_amplitude(hit["tensor_1024d"])
                for hit in hits
            ]
        )
        query_amplitude = resonance_amplitude(turn["z_query"])
        for chunk_id, amplitude in zip(ids, amplitudes):
            appliance.resonance.ingest(chunk_id, amplitude, frequency=FrequencyFamily.NEUTRAL)
        ranked = appliance.resonance.query(
            query_amplitude,
            FrequencyFamily.NEUTRAL,
            ids,
            amplitudes,
            flat=True,
        )
        by_id = {hit["document_id"]: hit for hit in hits}
        related = []
        for hit in ranked:
            source = by_id.get(hit.chunk_id)
            if source is None:
                continue
            score = float(hit.score)
            if not math.isfinite(score):
                raise RuntimeError(f"resonance score for {hit.chunk_id} is not finite")
            related.append(
                {
                    "chunk_id": hit.chunk_id,
                    "score": score,
                    "chunk_text": source["chunk_text"],
                }
            )
        turn["related_ids"] = [item["chunk_id"] for item in related]
        appliance._turn = turn
        return {"related": related}

    return node


def _structure_metadata(related: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Numeric attributes from VectorPrism's offline extractor.

    A causal graph is not inferred from the paragraph. The caller passes one
    to ``Appliance.ask``.
    """
    if len(related) < 1:
        return {}
    documents = {item["chunk_id"]: item["chunk_text"] for item in related}
    extracted = _extract_structure(documents)
    metadata: dict[str, dict[str, Any]] = {}
    for item in related:
        metadata[item["chunk_id"]] = {}
    rows = extracted.relational_attrs if extracted is not None else []
    for row in rows:
        claims = {
            key: float(value)
            for key, value in row.get("attributes", {}).items()
            if isinstance(value, (int, float)) and not isinstance(value, bool) and key != "amount_min"
        }
        if not claims:
            continue
        meta = metadata.setdefault(str(row["doc_id"]), {})
        meta["numeric_claims"] = claims
        meta["facts"] = claims
    _attach_money_amounts(metadata, related)
    _attach_literal_measurements(metadata, related)
    return metadata


def _extract_structure(documents: dict[str, str]):
    """Heuristic structure for the batch.

    VectorPrism's amount pattern treats a lone ``.`` as a number and raises
    ValueError. One such paragraph must not drop the other paragraphs.
    """
    from vectorprism.structure_extract import extract_structure

    try:
        return extract_structure(documents, backend="heuristic")
    except ValueError:
        if len(documents) == 1:
            return None
    kept = {}
    for doc_id, text in documents.items():
        try:
            extract_structure({doc_id: text}, backend="heuristic")
        except ValueError:
            continue
        kept[doc_id] = text
    if not kept:
        return None
    return extract_structure(kept, backend="heuristic")


def _attach_money_amounts(
    metadata: dict[str, dict[str, Any]],
    related: list[dict[str, Any]],
) -> None:
    """Set amount_min from a money span. A metre or a counted noun does not qualify."""
    for item in related:
        amount = stated_million_amount(item["chunk_text"])
        if amount is None:
            continue
        meta = metadata.setdefault(item["chunk_id"], {})
        claims = dict(meta.get("numeric_claims") or {})
        facts = dict(meta.get("facts") or {})
        claims["amount_min"] = amount
        facts["amount_min"] = amount
        meta["numeric_claims"] = claims
        meta["facts"] = facts


def _attach_literal_measurements(
    metadata: dict[str, dict[str, Any]],
    related: list[dict[str, Any]],
) -> None:
    """Copy stated measurements onto the chunk that contains them."""
    for item in related:
        claims, provenance = extract_stated_measurements(item["chunk_text"])
        if not claims:
            continue
        meta = metadata.setdefault(item["chunk_id"], {})
        numeric = dict(meta.get("numeric_claims") or {})
        facts = dict(meta.get("facts") or {})
        kept: dict[str, Any] = {}
        for key, value in claims.items():
            if key in numeric:
                continue
            numeric[key] = value
            facts.setdefault(key, value)
            kept[key] = provenance[key]
        if not kept:
            continue
        meta["numeric_claims"] = numeric
        meta["facts"] = facts
        qualifiers = dict(meta.get("numeric_qualifiers") or {})
        qualifiers.update(kept)
        meta["numeric_qualifiers"] = qualifiers


def _spans(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        related = [
            {"chunk_id": item["chunk_id"], "chunk_text": item["chunk_text"]}
            for item in state.get("related") or []
        ]
        index, mask = build_span_grammar(related)
        turn = appliance._turn or {}
        turn["span_index"] = index
        turn["span_mask"] = mask
        appliance._turn = turn
        return {
            "grammar_span_ids": list(mask.allowed_ids),
            "grammar_values": canonical_values(index),
        }

    return node


def _withhold(state: dict[str, Any], reason: str) -> dict[str, Any]:
    """Drop the sentence from delivery and keep it for the caller."""
    return {
        "grammar_ok": False,
        "answer": None,
        "rejected_answer": state.get("rejected_answer") or state.get("answer"),
        "delivery_blocked": state.get("delivery_blocked") or reason,
    }


def _with_caller_context(context: ReasoningContext, turn: dict[str, Any]) -> ReasoningContext:
    """Attach an objective, hypothesis, or causal graph the caller supplied."""
    update = {
        key: turn[key]
        for key in ("objective", "hypothesis", "causal_graph")
        if turn.get(key) is not None
    }
    if not update:
        return context
    return context.model_copy(update=update)


def _grammar(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        answer = state.get("answer")
        if not answer:
            return {"grammar_ok": True}
        turn = appliance._turn or {}
        index = turn.get("span_index")
        mask = turn.get("span_mask")
        if index is None or mask is None:
            return _withhold(state, "grammar")
        if answer_numbers_allowed(answer, index, mask):
            return {"grammar_ok": True}
        return _withhold(state, "grammar")

    return node


def _descriptive_turn(message: str, context: ReasoningContext) -> bool:
    """A stated measurement on a what-is question is a formal check.

    A why, how, or cause question keeps the Thinker's own directive. Incidental
    numbers in a neighbor do not turn that question into a descriptive answer.
    """
    if not _observation_without_target(context):
        return False
    reasons = set(complexity_reasons(message, []))
    explanatory = {"the prompt asks why or how", "the prompt asks about a cause"}
    return reasons.isdisjoint(explanatory)


def _observation_without_target(context: ReasoningContext) -> bool:
    """A stated number is not an optimization unless the caller supplied a test.

    Height, length, and weight on a descriptive question stay observations.
    An objective target, a numeric hypothesis payload, or a caller causal
    graph is what engages the empirical and causal heads.
    """
    observed = any(item.numeric_claims for item in context.evidence)
    if not observed:
        observed = any(
            isinstance(fact.value, (int, float)) and not isinstance(fact.value, bool)
            for fact in context.structured_facts.values()
        )
    if not observed:
        return False
    if context.causal_graph is not None and context.causal_graph.edges:
        return False
    if context.objective is not None and any(term.target is not None for term in context.objective.terms):
        return False
    payload = {}
    if context.hypothesis is not None and context.hypothesis.action is not None:
        payload = context.hypothesis.action.payload
    return not any(isinstance(value, (int, float)) and not isinstance(value, bool) for value in payload.values())


def _descriptive_config(base: EngineConfig) -> EngineConfig:
    """Formal check only. The lattice's extra-head fill would re-open empirical."""
    optional = dict(base.selector.regime_optional)
    optional["closed_formal"] = []
    selector = base.selector.model_copy(update={"regime_optional": optional})
    return base.model_copy(update={"min_heads": 1, "selector": selector})


def _directive_after_descriptive(graph: Any, directive: str, descriptive: bool) -> str:
    """One approving formal head is the descriptive result.

    PrismThinker's lattice calls a single determined head insufficient and
    emits gather. That gather has no question once empirical and causal are
    not selected. The sentence is the answer to the descriptive question.
    """
    if not descriptive or directive != "gather":
        return directive
    if "empirical" in graph.selected_evaluators or "causal" in graph.selected_evaluators:
        return directive
    formal = graph.evaluators.get("formal")
    if formal is None or formal.unresolved_questions:
        return directive
    if formal.verdict.value != "approve":
        return directive
    return "answer"


def _turn_chunk_ids(result: dict[str, Any]) -> list[str]:
    """Every passage, related row, and deep-search id on the turn. Not capped at five."""
    ids: list[str] = []
    seen: set[str] = set()
    for key in ("passages", "related", "possibilities"):
        for item in result.get(key) or []:
            if not isinstance(item, dict):
                continue
            document_id = str(item.get("document_id") or item.get("chunk_id") or "")
            if document_id and document_id not in seen:
                seen.add(document_id)
                ids.append(document_id)
    return ids


def _think(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        related = list(state.get("related") or [])
        metadata = _structure_metadata(related)
        documents = [
            RetrievedDocument(
                id=item["chunk_id"],
                text=item["chunk_text"],
                source="vectorprism",
                score=float(item["score"]),
                metadata=metadata.get(item["chunk_id"], {}),
            )
            for item in related
        ]
        context = from_vectorprism(state.get("message") or "", documents)
        context = _with_caller_context(context, appliance._turn or {})
        descriptive = _descriptive_turn(state.get("message") or "", context)
        if descriptive:
            context = context.model_copy(update={"force_regime": EpistemicRegime.CLOSED_FORMAL})
            thinker = appliance.active_thinker()
            graph = thinker.evaluate(context, config=_descriptive_config(thinker.config))
        else:
            graph = appliance.active_thinker().evaluate(context)
        envelope = to_chorusgraph(graph)
        update: dict[str, Any] = {
            "thinker_directive": _directive_after_descriptive(graph, envelope.directive.value, descriptive),
            "thinker_regime": graph.regime.value,
            "thinker_regime_reasons": [str(code) for code in graph.classifier.reason_codes],
            "thinker_turn_kind": "descriptive" if descriptive else "classified",
            "thinker_regime_forced": bool(descriptive),
            "thinker_evaluators": list(graph.selected_evaluators),
            "gather_questions": list(envelope.gather_questions),
            "numeric_claims": {
                chunk_id: meta["numeric_claims"]
                for chunk_id, meta in metadata.items()
                if meta.get("numeric_claims")
            },
            "numeric_qualifiers": {
                chunk_id: meta["numeric_qualifiers"]
                for chunk_id, meta in metadata.items()
                if meta.get("numeric_qualifiers")
            },
        }
        turn = appliance._turn or {}
        proposal = turn.get("payment")
        authority = turn.get("authority")
        if proposal is not None and authority is not None:
            from prismagenticpay.policies.corporate import CORPORATE_POLICY_VERSION

            outcome = evaluate_payment(appliance.payment_policy, proposal, authority)
            update["payment_directive"] = outcome.directive
            update["payment_allowed_tools"] = list(outcome.allowed_tools)
            update["payment_gather_fact_keys"] = list(outcome.gather_fact_keys)
            update["policy_version"] = CORPORATE_POLICY_VERSION
        return update

    return node


def _lexical_evidence(store: SqliteGraphStore, message: str):
    from cpu_llm.consolidation.sleep import lexical_evidence

    return lexical_evidence(store, message)


def _cognize(appliance: Appliance):
    def node(state: dict[str, Any]) -> dict[str, Any]:
        turn = appliance._turn or {}
        propositions: list[EIRProposition] = list(turn.get("propositions") or [])
        related_ids = list(turn.get("related_ids") or [])
        hits = {hit["document_id"]: hit for hit in turn.get("hits") or []}
        if not propositions and related_ids:
            from cpu_llm.assembly import realization_order

            ordered_hits: list[dict[str, Any]] = []
            stored_by_id: dict[str, EIRProposition] = {}
            for chunk_id in related_ids:
                hit = hits.get(chunk_id)
                if hit is None:
                    continue
                ordered_hits.append(hit)
                stored = _stored_proposition(
                    appliance.memory,
                    hit["chunk_text"],
                    np.asarray(hit["tensor_1024d"], dtype=np.float32).reshape(-1),
                )
                if stored is not None:
                    stored_by_id[chunk_id] = stored
            paired_ids = realization_order(state.get("message") or "", ordered_hits, stored_by_id)
            paired = [stored_by_id[chunk_id] for chunk_id in paired_ids]
            if not paired:
                lexical = _lexical_evidence(appliance.memory, state.get("message") or "")
                if not lexical:
                    return {"cognition_status": "needs_evidence_propositions"}
                propositions = [item[0] for item in lexical]
                tensors = [item[1] for item in lexical]
            else:
                propositions = paired
                related_ids = paired_ids
                turn["related_ids"] = paired_ids
                appliance._turn = turn
                tensors = None
        else:
            tensors = None
        if tensors is None:
            if propositions and len(related_ids) != len(propositions):
                return {
                    "cognition_status": "proposition_tensor_mismatch",
                    "proposition_count": len(propositions),
                    "tensor_count": len(related_ids),
                }
            hits = {hit["document_id"]: hit for hit in turn.get("hits") or []}
            tensors = [
                np.asarray(hits[chunk_id]["tensor_1024d"], dtype=np.float32).reshape(-1) for chunk_id in related_ids
            ]
        query = turn.get("z_query")
        if query is None:
            query = np.zeros(TENSOR_DIM, dtype=np.float32)
        result = appliance.cognition.deliberate(
            query,
            propositions,
            tensors,
            state.get("tenant_id") or "cpu-llm",
        )
        sentence, delivered = appliance.realizer.synthesize(result.grounded_propositions, result.graph_edges)
        audited = appliance.auditor.audit_delivered_output(delivered, result.grounded_propositions)
        update = {
            "cognition_status": "deliberated",
            "answer": sentence,
            "audit_passed": audited,
            "abstention_triggered": result.abstention_triggered,
            "ruin_distance": result.ruin_distance,
            "audit_trace_id": result.audit_trace_id,
        }
        if not audited:
            update["rejected_answer"] = sentence
            update["answer"] = None
            update["delivery_blocked"] = "audit"
        return update

    return node
