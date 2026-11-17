"""User-visible views over finalized evidence and calculation receipts."""

from html import escape
import json


def evidence_delivery(response):
    blocked = {"blocked", "refused", "external_unverified"}
    if response.get("answer_status", response.get("status")) in blocked:
        return response
    entries = [response]
    entries.extend(task["result"] for task in (response.get("task_results") or ())
                   if isinstance(task.get("result"), dict))
    sources = []
    seen = set()
    calculations = []
    for entry in entries:
        if entry.get("answer_status") in blocked or entry.get("guard_decision") not in (None, "allow"):
            continue
        for role, field in (("answer", "answer_evidence"), ("supporting", "supporting_evidence")):
            for item in entry.get(field) or []:
                if not isinstance(item, dict):
                    continue
                source_id, excerpt = item.get("document_id"), item.get("span") or item.get("quote")
                if not isinstance(source_id, str) or not isinstance(excerpt, str) or not excerpt:
                    continue
                key = source_id, excerpt, role
                if key in seen:
                    continue
                seen.add(key)
                source = dict(document_id=source_id, excerpt=excerpt, role=role)
                for name in ("page", "chapter", "title", "start", "end", "chunk_sha256", "span_hash", "source_version"):
                    if name in item:
                        source[name] = item[name]
                sources.append(source)
        calculation = entry.get("calculation")
        if isinstance(calculation, dict) and calculation not in calculations:
            calculations.append(calculation)
        for card in (entry.get("research_workspace") or {}).get("cards", ()):
            for item in card["premises"]:
                source_id, excerpt = item.get("document_id"), item.get("span") or item.get("quote")
                if isinstance(source_id, str) and isinstance(excerpt, str) and excerpt:
                    sources.append(dict(document_id=source_id, excerpt=excerpt, role="research_premise",
                                        option_id=card["id"]))
    if sources or calculations:
        response["evidence_panel"] = dict(schema="evidence-panel-v1", sources=sources, calculations=calculations)
    return response


def render_evidence_panel(panel):
    """Render expandable, escaped excerpts, suitable for embedding in a client."""
    parts = ['<section aria-label="Evidence">']
    for source in panel["sources"]:
        label = " · ".join(str(source[key]) for key in ("title", "document_id", "chapter", "page") if key in source)
        parts.append(f'<details><summary>{escape(label)}</summary><pre>{escape(source["excerpt"])}</pre></details>')
    for calculation in panel["calculations"]:
        content = escape(json.dumps(calculation, ensure_ascii=False, indent=2, default=str))
        parts.append(f"<details><summary>Calculation</summary><pre>{content}</pre></details>")
    parts.append("</section>")
    return "".join(parts)
