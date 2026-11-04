# Third-party data notices

cpu-llm's project code is licensed under Apache-2.0; see `LICENSE`.
That code license does not replace the terms of third-party data bundled in
the distributions.

## WikiText-2 raw text

The package includes the **validation and test** splits of WikiText-2 raw text
under `cpu_llm/data/wikitext-2-raw-v1/`. The source dataset is Salesforce WikiText,
derived from English Wikipedia articles and the contributions of their authors.
Its dataset card identifies **CC BY-SA 3.0 and GFDL** licenses:

- Dataset and license labels: https://huggingface.co/datasets/Salesforce/wikitext
- Validation source: https://huggingface.co/datasets/Salesforce/wikitext/resolve/main/wikitext-2-raw-v1/validation-00000-of-00001.parquet
- Test source: https://huggingface.co/datasets/Salesforce/wikitext/resolve/main/wikitext-2-raw-v1/test-00000-of-00001.parquet
- Attribution/license/provenance records included with the data:
  `src/cpu_llm/data/wikitext-2-raw-v1/PROVENANCE.txt` and `test-PROVENANCE.txt`.
- CC BY-SA 3.0: https://creativecommons.org/licenses/by-sa/3.0/
- GFDL: https://www.gnu.org/licenses/fdl.html

The shipped Parquet splits are the referenced dataset records. Ingestion
restores WikiText token punctuation/hyphen/contraction markers and stores
paragraphs separately; retrieved excerpts retain their source attribution.
Redistribution of this text or modified excerpts requires respecting the
applicable data-license terms. The software's Apache label alone is not a
license statement for all text inside a wheel or source archive.

The bundled AI/finance primers and fictional healthcare/conversation fixtures
are separate from WikiText. The pretrained retrieval encoder is downloaded
separately and has its own upstream model/license information; third-party
Python dependencies likewise retain their licenses.

The published 1.11.1 artifacts already include the two dataset provenance files.
This consolidated notice adds visibility in the repository and future builds;
it does not rewrite already published distribution bytes or claim a legal audit.
