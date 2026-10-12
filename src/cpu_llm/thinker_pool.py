"""PrismThinker heads that stay up for the life of the appliance.

The five standard heads are pure and finish in a few milliseconds. Starting a
Python process for each of them on every prompt costs a few hundred
milliseconds and then throws the process away. This module starts those
processes once, with the encoder, and sends each later prompt across a queue.

A head that exceeds its timeout is terminated and replaced, so a stuck
evaluator still cannot occupy the next prompt. Counterfactual probes stay
in-process on one thread pool created at the same time.
"""

from __future__ import annotations

import atexit
import multiprocessing
import threading
import time
import weakref
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout, wait
from dataclasses import dataclass
from multiprocessing.process import BaseProcess
from multiprocessing.queues import Queue
from queue import Empty
from typing import Any

from prismthinker.config import EngineConfig
from prismthinker.core.engine import PrismThinker, _sanitize_isolated_crash, _undetermined
from prismthinker.core.failures import crash_message
from prismthinker.core.isolation import HEAD_STARTUP_TIMEOUT_S, terminate_process
from prismthinker.core.schemas import EvaluatorError, EvaluatorResult, Hypothesis, ReasoningContext
from prismthinker.reason_codes import REASON_CRASH, REASON_TIMEOUT

_HEADS = ("formal", "policy", "empirical", "causal", "utility")
_MP = multiprocessing.get_context("spawn")


def persistent_head_worker(
    name: str,
    config_data: dict[str, Any],
    inbox: Queue,
    outbox: Queue,
) -> None:
    """Load one head, then evaluate each job until the parent sends None."""
    from prismthinker.config import EngineConfig
    from prismthinker.core.schemas import Hypothesis, ReasoningContext
    from prismthinker.core.selector import build_registry

    try:
        evaluator = build_registry(EngineConfig.model_validate(config_data))[name]
    except Exception as exc:  # noqa: BLE001 — report startup failure to the parent
        outbox.put(("crash", crash_message(exc, evaluator=name)))
        return
    outbox.put(("ready", None))
    while True:
        job = inbox.get()
        if job is None:
            return
        context_data, hypothesis_data = job
        try:
            context = ReasoningContext.model_validate(context_data)
            hypothesis = Hypothesis.model_validate(hypothesis_data)
            result = evaluator.evaluate(context, hypothesis)
            outbox.put(("ok", result.model_dump(mode="json")))
        except Exception as exc:  # noqa: BLE001 — keep the worker for the next prompt
            outbox.put(("crash", crash_message(exc, evaluator=name)))


def _queue_get(queue: Queue, timeout_s: float) -> tuple[str, Any] | None:
    try:
        return queue.get(timeout=max(0.0, timeout_s))
    except Empty:
        return None


def _warm_thread(_index: int) -> None:
    return None


@dataclass
class _Worker:
    process: BaseProcess
    inbox: Queue
    outbox: Queue


class WarmEvaluatorPool:
    """One living process per standard head, started before the first prompt."""

    def __init__(self, config: EngineConfig) -> None:
        self._config_data = config.model_dump(mode="json")
        self._lock = threading.Lock()
        self._workers: dict[str, _Worker] = {}
        self._closed = False
        failures: dict[str, str] = {}
        try:
            with self._lock:
                for name in _HEADS:
                    self._spawn(name)
                failures = self._await_ready(list(_HEADS), HEAD_STARTUP_TIMEOUT_S)
                if failures:
                    self._shutdown_locked()
        except Exception:
            with self._lock:
                if not self._closed:
                    self._shutdown_locked()
            raise
        if failures:
            detail = "; ".join(f"{name}: {message}" for name, message in failures.items())
            raise RuntimeError(f"evaluator pool failed to start: {detail}")

    def worker_pids(self) -> tuple[int, ...]:
        with self._lock:
            pids: list[int] = []
            for name in _HEADS:
                worker = self._workers.get(name)
                if worker is None or worker.process.pid is None:
                    continue
                pids.append(int(worker.process.pid))
            return tuple(pids)

    def run(
        self,
        names: list[str],
        context: ReasoningContext,
        hypothesis: Hypothesis,
        *,
        head_timeout_s: float,
        budget_s: float,
    ) -> tuple[dict[str, EvaluatorResult], list[EvaluatorError], bool]:
        context_data = context.model_dump(mode="json")
        hypothesis_data = hypothesis.model_dump(mode="json")
        results: dict[str, EvaluatorResult] = {}
        errors: list[EvaluatorError] = []
        with self._lock:
            if self._closed:
                raise RuntimeError("evaluator pool is closed")
            pending: list[str] = []
            for name in names:
                failure = self._ready(name)
                if failure is not None:
                    errors.append(
                        EvaluatorError(
                            evaluator=name,
                            error_type="crash",
                            message=_sanitize_isolated_crash(failure),
                        )
                    )
                    results[name] = _undetermined(name, REASON_CRASH)
                    continue
                worker = self._workers[name]
                worker.inbox.put((context_data, hypothesis_data))
                pending.append(name)
            started = time.perf_counter()
            replace: list[str] = []
            for name in pending:
                worker = self._workers[name]
                remaining = max(0.0, min(head_timeout_s, budget_s - (time.perf_counter() - started)))
                item = _queue_get(worker.outbox, remaining)
                if item is None or not worker.process.is_alive():
                    replace.append(name)
                    if item is None and worker.process.is_alive():
                        errors.append(
                            EvaluatorError(
                                evaluator=name,
                                error_type="timeout",
                                message="head timed out and worker was terminated",
                            )
                        )
                        results[name] = _undetermined(name, REASON_TIMEOUT)
                    else:
                        message = "worker exited during evaluation"
                        if item is not None:
                            message = str(item[1])
                        errors.append(
                            EvaluatorError(
                                evaluator=name,
                                error_type="crash",
                                message=_sanitize_isolated_crash(message),
                            )
                        )
                        results[name] = _undetermined(name, REASON_CRASH)
                    continue
                status, payload = item
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                if status == "ok" and isinstance(payload, dict):
                    result = EvaluatorResult.model_validate(payload)
                    results[name] = result.model_copy(update={"latency_ms": elapsed_ms})
                    continue
                errors.append(
                    EvaluatorError(
                        evaluator=name,
                        error_type="crash",
                        message=_sanitize_isolated_crash(payload),
                    )
                )
                results[name] = _undetermined(name, REASON_CRASH)
            over_budget = (time.perf_counter() - started) * 1000.0 >= budget_s * 1000.0
            for name in replace:
                self._drop(name)
                self._launch(name)
        return results, errors, over_budget

    def close(self) -> None:
        with self._lock:
            self._shutdown_locked()

    def _ready(self, name: str) -> str | None:
        worker = self._workers.get(name)
        if worker is not None and worker.process.is_alive():
            return None
        self._drop(name)
        return self._launch(name)

    def _spawn(self, name: str) -> None:
        self._drop(name)
        inbox: Queue = _MP.Queue()
        outbox: Queue = _MP.Queue()
        process = _MP.Process(
            target=persistent_head_worker,
            args=(name, self._config_data, inbox, outbox),
            daemon=True,
            name=f"prismthinker-{name}",
        )
        process.start()
        self._workers[name] = _Worker(process, inbox, outbox)

    def _await_ready(self, names: list[str], timeout_s: float) -> dict[str, str]:
        pending = set(names)
        failures: dict[str, str] = {}
        deadline = time.perf_counter() + timeout_s
        while pending and time.perf_counter() < deadline:
            for name in list(pending):
                worker = self._workers.get(name)
                if worker is None:
                    pending.remove(name)
                    failures[name] = "worker was not started"
                    continue
                item = _queue_get(worker.outbox, 0.02)
                if item is None:
                    if not worker.process.is_alive():
                        pending.remove(name)
                        failures[name] = f"worker exited during startup ({worker.process.exitcode})"
                        self._drop(name)
                    continue
                pending.remove(name)
                if item[0] != "ready" or not worker.process.is_alive():
                    failures[name] = str(item[1]) if item[0] != "ready" else "worker exited during startup"
                    self._drop(name)
            if pending:
                time.sleep(0.01)
        for name in list(pending):
            failures[name] = "worker failed to start before startup timeout"
            self._drop(name)
            pending.remove(name)
        return failures

    def _launch(self, name: str) -> str | None:
        self._spawn(name)
        return self._await_ready([name], HEAD_STARTUP_TIMEOUT_S).get(name)

    def _drop(self, name: str) -> None:
        worker = self._workers.pop(name, None)
        if worker is None:
            return
        terminate_process(worker.process)

    def _shutdown_locked(self) -> None:
        if self._closed:
            return
        self._closed = True
        for worker in self._workers.values():
            if not worker.process.is_alive():
                continue
            try:
                worker.inbox.put(None)
            except (OSError, ValueError):
                continue
        for worker in self._workers.values():
            worker.process.join(timeout=0.5)
            terminate_process(worker.process)
        self._workers.clear()


def _release(pool: WarmEvaluatorPool | None, threads: ThreadPoolExecutor, state: dict[str, bool]) -> None:
    if state.get("done"):
        return
    state["done"] = True
    if pool is not None:
        pool.close()
    threads.shutdown(wait=False, cancel_futures=True)


class WarmPrismThinker(PrismThinker):
    """PrismThinker whose head processes and thread pool are created in __init__."""

    def __init__(self, config: EngineConfig | None = None) -> None:
        super().__init__(config)
        self._threads = ThreadPoolExecutor(max_workers=8, thread_name_prefix="prismthinker")
        list(self._threads.map(_warm_thread, range(len(_HEADS))))
        self.pool: WarmEvaluatorPool | None = None
        self._released = {"done": False}
        try:
            if self.config.isolate_heads:
                self.pool = WarmEvaluatorPool(self.config)
        except Exception:
            self._threads.shutdown(wait=False, cancel_futures=True)
            raise
        self._finalizer = weakref.finalize(self, _release, self.pool, self._threads, self._released)
        atexit.register(self.close)

    def close(self) -> None:
        self._finalizer()

    def worker_pids(self) -> tuple[int, ...]:
        if self.pool is None:
            return ()
        return self.pool.worker_pids()

    def __enter__(self) -> WarmPrismThinker:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _run_isolated_pool(
        self,
        names: list[str],
        context: ReasoningContext,
        hypothesis: Hypothesis,
    ) -> tuple[dict[str, EvaluatorResult], list[EvaluatorError], bool]:
        if self.pool is None:
            raise RuntimeError("isolated heads require the startup evaluator pool")
        return self.pool.run(
            names,
            context,
            hypothesis,
            head_timeout_s=self.config.head_timeout_ms / 1000.0,
            budget_s=self.config.pool_budget_ms / 1000.0,
        )

    def _run_thread_pool(
        self,
        names: list[str],
        context: ReasoningContext,
        hypothesis: Hypothesis,
    ) -> tuple[dict[str, EvaluatorResult], list[EvaluatorError], bool]:
        results: dict[str, EvaluatorResult] = {}
        errors: list[EvaluatorError] = []
        head_timeout = self.config.head_timeout_ms / 1000.0
        budget = self.config.pool_budget_ms / 1000.0
        started = time.perf_counter()
        futures = {
            name: self._threads.submit(
                self._registry[name].evaluate,
                context.model_copy(deep=True),
                hypothesis.model_copy(deep=True),
            )
            for name in names
        }
        wait(list(futures.values()), timeout=budget)
        for name, fut in futures.items():
            t0 = time.perf_counter()
            remaining = max(0.0, min(head_timeout, budget - (t0 - started)))
            try:
                if not fut.done() and remaining <= 0:
                    raise FuturesTimeout()
                result = fut.result(timeout=remaining)
                result = result.model_copy(update={"latency_ms": (time.perf_counter() - t0) * 1000.0})
                results[name] = result
            except FuturesTimeout:
                errors.append(EvaluatorError(evaluator=name, error_type="timeout", message="head timed out"))
                results[name] = _undetermined(name, REASON_TIMEOUT)
            except Exception as exc:  # noqa: BLE001 — isolate head crashes
                errors.append(
                    EvaluatorError(
                        evaluator=name,
                        error_type="crash",
                        message=crash_message(exc, evaluator=name),
                    )
                )
                results[name] = _undetermined(name, REASON_CRASH)
        over_budget = (time.perf_counter() - started) * 1000.0 >= self.config.pool_budget_ms
        return results, errors, over_budget
