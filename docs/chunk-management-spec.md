# Chunk inventory and deletion

Chunk management is available in the current source checkout. An inventory counts active PostgreSQL rows visible to the caller at query time. A source filter uses the ingested filename or source prefix and matches paragraph IDs within that source. It counts source membership. Semantic retrieval is a separate operation.

## Inventory

Use `How many chunks do we have?`, `How many chunks are there in notes.pdf?`, or `List chunks for notes.pdf.` The same operation is available as `app.chunk_inventory(source=None, limit=50, offset=0, caller=...)` and authenticated `POST /v1/chunks`.

The receipt contains `source_prefix`, `chunk_count`, `chunk_ids`, and `next_offset`. The count and page are read in one database statement. IDs sort by document ID. The page limit is 1–200. Omit the source for a KB-wide count within caller scope. Retired versions are excluded. Concurrent ingestion or deletion can change subsequent pages.

## Approval and confirmation

1. Ask `Delete chunk notes-p0001.` or call `app.delete_chunk("notes-p0001")`. Review the exact ID, preview, and SHA-256 digest in the receipt. A preview makes no deletion.
2. After approval, call `app.delete_chunk("notes-p0001", confirmation=token)` with the same caller, or send the ID and token to authenticated `POST /v1/delete-chunk`. For HTTP previews, omit the token.
3. Inspect the status. `confirmation_required` means review is pending. `invalid_confirmation` means a fresh preview is required. `chunk_not_found` means there is no row with that ID. `deleted` confirms the exact deletion.

The token expires after five minutes and is bound to the appliance instance, tenant, caller, exact ID, and PostgreSQL row revision. Re-ingestion or correction can invalidate it. Each sibling chunk and correction version needs its own confirmation. The operation removes the vector row and document-keyed graph, knowledge graph, word index, and optional resonance tags. Shared resonance and word-relation records are retained. Cleanup spans multiple stores, and only PostgreSQL participates in its transaction. The legacy `/v1/delete` operation deletes an entire source.

## Team roles

Authenticated credentials default to `reader` when `role` is omitted. Readers can inspect inventory within their allowed sources. Previewing or confirming a chunk deletion and deleting a whole source require `"role": "admin"` in the trusted credential file and access to the target. Unknown roles fail authentication. Reload the service after changing credentials. In standalone Python, omitting the caller context uses local operator access. A team application should authenticate its callers and use the scoped service entry point.

See the [OpenAPI specification](openapi.json) for the HTTP payloads.
