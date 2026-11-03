# Default conversation demo

The package includes original reviewed replies for eight basic conversational
intents. This example runs 12 actual public-API turns, including ordinary social
messages, explicit tone variants, a greeting plus a factual lookup, a medication
question that must remain unsupported, per-request disable, and quoted text
that must not be treated as a greeting.

After the usual database/checkpoint/cached-encoder setup from the main README:

```powershell
python examples/conversation/run_demo.py --out build/conversation-demo-new-run
```

Set `VECTORPRISM_PG_DSN` to a demo database first. For cached offline operation,
set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`. Use a new output directory.
The script creates an isolated strict-mode namespace and restricts the demo
caller to its single fictional source. It saves actual responses and explicit
status checks; it does not train a model or download dialogue datasets.

`conversation` results are built-in policy replies, not document evidence.
Strict factual replies remain quotations, bounded arithmetic or nonanswers.
The fictional label is not real medication guidance. To disable social replies
globally, construct `Appliance(small_talk=False)` or serve with `--no-small-talk`.
See [the specification](../../docs/conversation-spec.md) for exact scope and
dataset-candidate preparation instructions.
