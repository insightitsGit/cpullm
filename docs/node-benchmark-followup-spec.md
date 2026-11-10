# Node benchmark follow-up

The 1.13.0 installed-wheel run exercised 27 core graph nodes. It exposed two behavior gaps. Deep-search replies could deliver text without a top-level outcome. The event-frame route answered an attribute of an object but missed a direct question about what the actor acted on.

1. Give deep replies an explicit answer status and preserve the evidence selected by the final response judge. A search result by itself does not establish an answer. Unsupported or rejected answers keep their refusal status.
2. Recognize supported direct event-object questions such as “What did John eat?” and resolve them against the actor and action in an authorized source passage. Missing or ambiguous objects should abstain. Preserve citation provenance.
3. Expand math and discovery benchmark coverage with multiple live requests and positive and negative controls. Check outputs and evidence as well as executed nodes. Replay the original apple and deep-search prompts and record any remaining gaps.
