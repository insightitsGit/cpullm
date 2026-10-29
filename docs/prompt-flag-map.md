# Prompt flags → agentic consumers

Generated from `cpu_llm.flag_contract.FLAG_BINDINGS`. The JSON companion is tested for exact registry agreement.

| Flag | Origin / example | Consumer | Stage | Enforcement / behavior |
|---|---|---|---|---|
| `state.deep` | prompt or explicit API override; Deep search | `deep` | graph | Wider authorized search; not enabled by response length. |
| `state.creative` | prompt or explicit API override; Imagine a story | `gather`, `imagine` | graph | Gather before imagination; no factual proof exemption. |
| `state.compare` | recognized prompt / internal interpretation; Compare X and Y | `compare` | graph | Compare explicitly named sides. |
| `state.summarize` | recognized prompt / internal interpretation; Summarize X | `brief` | graph | Produce source-backed summary units. |
| `state.explain` | recognized prompt / internal interpretation; Why did X stop? | `brief` | graph | Prioritize supported causal explanation. |
| `state.list` | recognized prompt / internal interpretation; List X facts | `brief` | graph | Produce verified list units. |
| `state.sources` | recognized prompt / internal interpretation; Cite the sources | `brief`, `reply` | graph | Select and display source references. |
| `state.math` | prompt or explicit API override; Calculate 2 + 3 | `math` | graph | Independent arithmetic from prompt fields. |
| `state.finance` | prompt or explicit API override; Check this refund | `finance` | graph | Check supplied finance fields. |
| `state.frame` | recognized prompt / internal interpretation; What did John eat? | `frame` | graph | Resolve a source-backed event frame. |
| `state.draft` | recognized prompt / internal interpretation; Draft a letter about X | `reply` | graph | Document catalog is rendered inside reply; no separate draft node. |
| `state.discover` | API-only; API discover=True | `discover` | graph | API-only follow-up suggestions after reply; never inferred from layout. |
| `response_plan.flags.long_response` | explicit prompt presentation or derived default; Long response about X | `retrieve`, `brief` | budget | Derived depth/size indicator; consumers use validated numeric budgets. |
| `response_plan.flags.expand_retrieval` | explicit prompt presentation or derived default; Explain X in 20 sentences | `retrieve` | budget | Must agree with long_response; use retrieval_budget, not the deep-search agent. |
| `response_plan.flags.extended_overview` | explicit prompt presentation or derived default; Elaborate on X | `brief` | budget | Long response plus overview mode; direct factual slots are unchanged. |
| `response_plan.flags.table` | explicit prompt presentation or derived default; as a table | `render_response` | post_graph | Tabulate plus built-in Jinja layout after judgment. |
| `response_plan.flags.bullets` | explicit prompt presentation or derived default; as bullet points | `brief`, `render_response` | presentation | Overview uses list producer; a direct fact remains a fact. |
| `response_plan.flags.numbered` | explicit prompt presentation or derived default; as a numbered list | `brief`, `render_response` | presentation | Use verified item boundaries and numbered layout. |
| `response_plan.flags.report` | explicit prompt presentation or derived default; as a report | `render_response` | post_graph | Built-in task-response report; distinct from legacy draft report. |
| `response_plan.flags.html` | explicit prompt presentation or derived default; as an HTML report | `render_response` | post_graph | Escaped HTML output; does not choose a factual agent. |
| `response_plan.flags.markdown` | explicit prompt presentation or derived default; as a Markdown table | `render_response` | post_graph | Markdown representation; default does not force a template. |
| `response_plan.flags.template_requested` | explicit prompt presentation or derived default; Please use a table | `render_response` | post_graph | Explicit layout indicator; validated against format/media. |
| `prompt_intent.channels.dense.active` | recognized request form / channel evidence; Any content query | `retrieve`, `dense` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
| `prompt_intent.channels.relational.active` | recognized request form / channel evidence; What does X have? | `retrieve`, `relational` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
| `prompt_intent.channels.disentangled.active` | recognized request form / channel evidence; How do X and Y differ? | `retrieve`, `disentangled` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
| `prompt_intent.channels.hyperbolic.active` | recognized request form / channel evidence; What type is X? | `retrieve`, `hyperbolic` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
| `prompt_intent.channels.identity.active` | recognized request form / channel evidence; Who is X? | `retrieve`, `identity` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
| `prompt_intent.channels.causal.active` | recognized request form / channel evidence; Why did X stop? | `retrieve`, `causal` | channel | All six channel nodes evaluate; active is a signal, not a graph skip or proof. |
