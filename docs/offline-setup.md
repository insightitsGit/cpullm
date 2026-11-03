# Encoder caching and offline setup

cpu-llm includes its trained VectorPrism projection and demo records. The
pretrained retrieval encoder `sentence-transformers/all-mpnet-base-v2` is a
separate download. Both strict evidence and ordinary document use still
construct the appliance's retrieval stack; strict mode does not eliminate this
setup dependency. Encoder preparation is a download/cache operation, not training.

Set cache variables **before** starting Python or the server. Use `HF_HOME` and
`HF_HUB_CACHE`; `TORCH_HOME` is not the Hugging Face model-cache location. Do not
rely on deprecated library-specific cache variables to find these assets.
If `SENTENCE_TRANSFORMERS_HOME` is already set in your deployment, align it with
`HF_HUB_CACHE` or unset it; an unrelated encoder cache override can otherwise
take precedence. The checkout helper passes its cache directory explicitly.

## Connected preparation

PowerShell, using a directory that you can transfer to the deployment machine:

```powershell
$env:HF_HOME = Join-Path $PWD "model-cache"
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"
python -c "import pyarrow; from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2', device='cpu')"
```

POSIX shell:

```sh
export HF_HOME="$PWD/model-cache"
export HF_HUB_CACHE="$HF_HOME/hub"
python -c "import pyarrow; from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2', device='cpu')"
```

In a repository checkout, the helper also emits an optional snapshot receipt:

```powershell
python tools/prepare_encoder_cache.py --cache-root model-cache --receipt build/encoder-cache.json
```

First preparation requires network access and enough disk for encoder assets;
there is no fixed download/startup SLA. The installed wheel already has the
required encoder dependencies. No hosted inference API key is needed for this
public encoder. A genuine air-gapped machine also needs a prepared Python
package wheelhouse and a PostgreSQL/pgvector image or installation; a model
cache alone does not make pip or Docker downloads available offline.

## Transfer and verify

Copy the prepared cache **including blobs, snapshots and refs**, preserving or
dereferencing symlinks consistently. Configure the same cache root on the target.
Do not copy unrelated credential files/tokens with a shared model cache.

```powershell
$env:HF_HOME = "C:\models\cpu-llm-cache"
$env:HF_HUB_CACHE = Join-Path $env:HF_HOME "hub"
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
python -c "import pyarrow; from sentence_transformers import SentenceTransformer; m=SentenceTransformer('sentence-transformers/all-mpnet-base-v2', device='cpu', local_files_only=True); print(m.encode(['cache check']).shape)"
```

The expected shape is `(1, 768)`. A checkout can verify with TCP connections
forbidden inside the encoder-check process:

```powershell
python tools/prepare_encoder_cache.py --cache-root C:\models\cpu-llm-cache --offline-check --receipt build/offline-encoder.json
```

Then configure `VECTORPRISM_PG_DSN` and run:

```powershell
cpu-llm-demo healthcare --out healthcare-offline-new-run
cpu-llm-demo conversation --out conversation-offline-new-run
```

Each output directory must be new. Environment flags make Hugging Face/Transformers
use cached assets and fail when required assets are absent; they are not a
universal operating-system egress firewall for every optional dependency. The
runtime still needs access to its configured database, including on another host.
Set offline flags before the service/worker processes start. Record the cached
snapshot ID and dependency versions; the 1.11.0 runtime requests the model ID's
cached `main` revision rather than exposing an encoder revision override.

## Optional models are a separate concern

Strict evidence and the new bounded document-tone constructions do not require
FLAN-T5. The ordinary fact-bridge may load compatible **application-provided**
extraction/writing checkpoints when installed. `FACTBRIDGE_MODELS` points to that
checkpoint tree; merely downloading the encoder or a generic FLAN-T5 base model
does not create the trained fact-bridge extractor/writer. See the consumer guide
and existing fact-bridge model layout. spaCy/coreference backends also require
their own optional packages/model assets. Do not claim an arbitrary optional
backend is air-gap-ready because the retrieval encoder check passed.

References: [Hugging Face cache layout](https://huggingface.co/docs/huggingface_hub/en/guides/manage-cache),
[environment variables and offline mode](https://huggingface.co/docs/huggingface_hub/en/package_reference/environment_variables).
