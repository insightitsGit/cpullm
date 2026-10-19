# Retrieval measurement, 18 October 2026

This is a labelled run of four sentences ingested into the `retrieval_lab` namespace. It is not a customer corpus. It is not a pass bar. The 102/104 figure remains a wording score with the passages handed in.

| Field | Value |
| --- | --- |
| Commit | `4483522` |
| Machine | `DESKTOP-H3RO1EI` |
| Command | `python -m pytest tests/test_tenant_isolation.py::test_labelled_retrieval_is_recorded_without_a_threshold --tb=short` |
| Cases | 4 |
| Hit-rate@5 | 1.0 |
| Spoken attribution | 1.0 |

Hit-rate@5 is the fraction of questions for which the one relevant document id was among the five retrieved ids. Spoken attribution is the fraction whose spoken sentence contained the stored sentence of that relevant id. Each question's other three sentences were the distractors. The questions use a made-up name that appears in only one sentence, so this run does not measure a hard neighbor.

The same pytest file also ingested `ALPHATOKENZXQ` as tenant `tenant_alpha` and `BETATOKENQWZ` as tenant `tenant_beta`. Each token was present in its own result and absent from the other tenant's result, including the reply, the preface, the draft, and the rest of the JSON.
