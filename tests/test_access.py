"""Phase 1 gate: tenant, source scope, credential, and typo vocabulary stay apart."""

import json
from types import SimpleNamespace

import numpy as np
import pytest
from chorusgraph.persistence.sqlite_graph_store import SqliteGraphStore
from prismcortex.models import DeltaOp, Node, Operation, StateDelta

from cpu_llm.access import AuthenticationError, CallerContext, SourceForbidden, source_allowed
from cpu_llm.entry import Entry, secret_sha256
from cpu_llm.format_sense import FormatSense
from cpu_llm.pipeline import empty_scope_result, graph_identity
from cpu_llm.retrieval import VectorPrismIndex
from cpu_llm.typos import correct_message

TOKEN_A = "ALPHATOKENZXQ"
TOKEN_B = "BETATOKENQWZ"


class _Cursor:
    def __init__(self, db):
        self.db = db
        self.rows = []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, params=None):
        self.db.sqls.append(sql)
        if "SELECT" not in sql.upper():
            return
        where = sql.lower().split("order by")[0]
        filtered = "document_id" in where and "limit" not in where
        self.rows = self.db.allowed_rows if filtered else self.db.forbidden_rows

    def fetchall(self):
        return self.rows


class _Conn:
    def __init__(self, db):
        self.db = db

    def cursor(self):
        return _Cursor(self.db)


class _Db:
    def __init__(self):
        self.conn = _Conn(self)
        self.sqls: list[str] = []
        self.allowed_rows = [_row(f"allowed-p000{i}") for i in range(1, 6)]
        self.forbidden_rows = [_row(f"forbidden-p000{i}") for i in range(1, 6)]


def _row(document_id: str):
    return (document_id, f"text {document_id}", np.zeros(1024, dtype=np.float32))


def _index() -> VectorPrismIndex:
    index = object.__new__(VectorPrismIndex)
    index.db = _Db()
    index.engine = SimpleNamespace(model_version=1)
    index.pipeline = SimpleNamespace(enabled_channels={})
    return index


def test_a_forbidden_rank_one_does_not_take_a_slot_from_the_five():
    index = _index()
    hits = index.search_allowed(
        "where is the allowed note?",
        frozenset({"allowed-p"}),
        top_k=5,
        query_tensor=np.zeros(1024, dtype=np.float32),
    )
    ids = [hit["document_id"] for hit in hits]
    assert ids == [f"allowed-p000{i}" for i in range(1, 6)]
    assert all(not item.startswith("forbidden") for item in ids)
    select = next(sql for sql in index.db.sqls if "SELECT" in sql.upper())
    where = select.lower().split("order by")[0]
    assert "document_id" in where
    assert "limit" not in where


def test_an_empty_scope_is_the_existing_empty_retrieval_sentence():
    context = CallerContext.make("tenant_alpha", "alice", [])
    refused = empty_scope_result("tenant_alpha", "Can I bring my dog?", context)
    assert refused is not None
    assert refused["typos"] == []
    assert refused["reply"]["text"] == "No passage was retrieved."
    assert TOKEN_A not in refused["reply"]["text"]
    assert empty_scope_result("cpu-llm", "What is a lobster?", None) is None


def test_a_bad_credential_never_reaches_the_appliance(tmp_path):
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "id": "alice",
                        "secret_sha256": secret_sha256("alpha-secret"),
                        "tenant_id": "tenant_alpha",
                        "caller_id": "alice",
                        "allowed_sources": ["alpha-p"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    calls: list[str] = []

    def factory(tenant: str):
        calls.append(tenant)
        raise AssertionError("a rejected credential must not open an appliance")

    entry = Entry(secrets, factory)
    with pytest.raises(AuthenticationError) as caught:
        entry.ask("wrong-secret", "What is the European lobster?")
    assert caught.value.as_dict()["error"] == "authentication_failed"
    assert "Traceback" not in str(caught.value)
    assert calls == []


def test_typo_correction_does_not_read_another_tenants_words():
    alpha = {"lobster": {}}
    beta = {"kestrel": {}}
    rewritten, changes = correct_message("What is the lobstor?", alpha, tenant_id="tenant_alpha")
    assert rewritten == "What is the lobster?"
    assert changes[0]["to"] == "lobster"
    other, other_changes = correct_message("What is the lobstor?", beta, tenant_id="tenant_beta")
    assert other == "What is the lobstor?"
    assert other_changes == []
    again, _ = correct_message("What is the lobstor?", alpha, tenant_id="tenant_alpha")
    assert again == "What is the lobster?"


def test_graph_and_format_cache_stay_inside_the_tenant(tmp_path):
    alpha = SqliteGraphStore(tmp_path / "alpha.db", tenant_id="tenant_alpha")
    beta = SqliteGraphStore(tmp_path / "beta.db", tenant_id="tenant_beta")
    alpha.apply(
        StateDelta(
            ops=[
                DeltaOp(
                    operation=Operation.ASSIMILATE,
                    node=Node(id="alpha-p0001", label=f"The private fact is {TOKEN_A}.", kind="chunk"),
                    reason="test",
                )
            ]
        )
    )

    def encode(texts):
        return np.ones((len(texts), 4), dtype=np.float32)

    FormatSense(alpha, encode).classify("Write an email about the late shipment.")
    FormatSense(beta, encode)
    assert TOKEN_A not in " ".join(node.label for node in beta.all_nodes())
    beta_rows = beta._conn.execute("SELECT COUNT(*) FROM format_sense_cache").fetchone()
    assert beta_rows[0] == 0
    with pytest.raises(AuthenticationError):
        Entry(tmp_path / "missing.json", lambda tenant: None).authenticate("nope")
    assert TOKEN_A in " ".join(node.label for node in alpha.all_nodes())
    alpha.close()
    beta.close()


def test_a_then_b_then_a_keeps_each_vocabulary(tmp_path):
    secrets = tmp_path / "secrets.json"
    secrets.write_text(
        json.dumps(
            {
                "credentials": [
                    {
                        "id": "alice",
                        "secret_sha256": secret_sha256("alpha-secret"),
                        "tenant_id": "tenant_alpha",
                        "caller_id": "alice",
                        "allowed_sources": ["alpha-p"],
                    },
                    {
                        "id": "bob",
                        "secret_sha256": secret_sha256("beta-secret"),
                        "tenant_id": "tenant_beta",
                        "caller_id": "bob",
                        "allowed_sources": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    seen: dict[str, list[str]] = {"tenant_alpha": [], "tenant_beta": []}

    class Appliance:
        def __init__(self, tenant):
            self.tenant_id = tenant
            self.words = {"lobster": {}} if tenant == "tenant_alpha" else {"kestrel": {}}

        def ask(self, message, caller=None, **kwargs):
            seen[self.tenant_id].append(message)
            if caller is not None and not caller.allowed_sources:
                refused = empty_scope_result(self.tenant_id, message, caller)
                assert refused is not None
                return refused
            text, _ = correct_message(message, self.words, tenant_id=self.tenant_id)
            return {"reply": {"text": text, "preface": "", "draft": None}, "answer": text, "tenant_id": self.tenant_id}

    appliances = {}

    def factory(tenant):
        appliances.setdefault(tenant, Appliance(tenant))
        return appliances[tenant]

    entry = Entry(secrets, factory)
    with pytest.raises(AuthenticationError):
        entry.ask("not-a-secret", f"leak {TOKEN_A}")
    first = entry.ask("alpha-secret", "What is the lobstor?")
    second = entry.ask("beta-secret", "What is the lobstor?")
    third = entry.ask("alpha-secret", "What is the lobstor?")
    assert first["reply"]["text"] == "What is the lobster?"
    assert second["reply"]["text"] == "No passage was retrieved."
    assert TOKEN_A not in second["reply"]["text"]
    assert third["reply"]["text"] == "What is the lobster?"
    assert seen["tenant_beta"] == ["What is the lobstor?"]
    with pytest.raises(SourceForbidden):
        entry.delete_source("beta-secret", "alpha-notes")


def test_graph_identity_uses_the_tenant_slug():
    assert graph_identity("cpu-llm") == ("cpu-llm", "appliance_cpu-llm")
    assert graph_identity("tenant_alpha") == ("tenant_alpha", "appliance_tenant_alpha")
    assert source_allowed("alpha-p0001", frozenset({"alpha-p"}))
    assert not source_allowed("beta-p0001", frozenset({"alpha-p"}))
    assert source_allowed("beta-p0001", None)
