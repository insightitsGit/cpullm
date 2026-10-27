# Channel-evidence judge: result handoff

Source revision is `af39da6f10fa8ef41e1d10bc31323829af8652f6` plus uncommitted
work. No dependency was added. PrismShine remains `prismshine==0.2.2` with
`judge=None` and Tier 3 disabled. No cloud judge is called.

## What owns the decision

`finalize_turn` in `src/cpu_llm/evidence_judge.py` is the last step of `ask()`.
`judgment` (`channel-evidence-judgment-v1`) is also attached to an early sense
clarification. `route_prompt` and `select_channel_answer` are the only routers.
A sense question is asked when stored classes of one name are not linked by a
source `is_a` edge, or when the question has a single content word and at least
two senses. Cluster size is not a meaning. A requested attribute is not a meaning.

Replacing the licensed body withholds the answer (`final_text_not_in_evidence`).
An appended sentence is removed (`appended_text_removed`) and the licensed body
stays. `shine_final` is the record for the text that left `ask()`. When the
earlier grounding node already accepted the licensed claim and that claim is
still present, `reused_graph_verdict` is true. Attribution lines are not scored
as a new answer. A Shine hold is not lifted. An empty-retrieval abstention keeps
its sentence and is not checked again. Specialist contracts are not rewritten
for lack of an ordinary factual relation.

A because-sentence answers only the effect it states.

## Suite

Command, from a machine with the disposable database on port 5433 and cached
encoder files:

```text
$env:CPU_LLM_LIVE_TESTS='1'
$env:VECTORPRISM_PG_DSN='postgresql://vectorprism:vectorprism@127.0.0.1:5433/cpullm_public'
$env:HF_HUB_OFFLINE='1'
$env:TRANSFORMERS_OFFLINE='1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD='1'
python -u -m pytest tests -ra --tb=line -p no:cacheprovider
```

Result on 2026-10-27: **487 passed, 2 skipped, 3 xfailed, 6 warnings in 57.42s**.
Log: `build/suite-2026-10-27-judge.log`.

Skips: `test_answering.py` and `test_fact_bridge.py`, no trained extractor
checkpoint. Strict xfails, unchanged: the three crane sense tests in
`test_resonance_groups.py`. Warnings are NumPy overflow inside `linalg` during
pipeline tests. They are not assertion failures.

The holdout is `tests/test_evidence_judge.py`: one ferry's properties do not
ask, a bat with two unlinked classes asks, a bare spring asks, a possession
join keeps or drops each premise, a cause binds only to the asked effect, a
replaced final sentence is withheld, an appended sentence is removed, a scored
licensed sentence passes Shine, and a summary is not rewritten.

## Benchmark

Not replayed. `run_eval.py` refuses a dirty tree outside `docs/benchmarks/`.
The historical baseline and `build/benchmark-2026-10-26` were not modified.
The why-diesel case still expects the unsupported sentence. Quoting the stored
river-current sentence is `contract_disagreement`, not `wrong`. The corpus was
not edited. A replay has to use a fresh `--out` directory after the tree is
committed. Resonance stays opt-in until that replay is measured.

## Still out of scope

Source-specific synonym extraction, including "municipal" and "town-operated",
is not implemented. Passing this check does not establish general intent
understanding or that a source sentence is true in the world.
