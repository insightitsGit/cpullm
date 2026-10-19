# cpu-llm question times, 18 October 2026

GitHub: https://github.com/insightitsGit/cpullm/blob/main/docs/benchmark-cpu-llm-2026-10-18.md

Seven questions, one process, after the appliance was already open. Startup is separate from the question times. No cloud model was called. There is no Grok or Gemini latency in this file.

| Field | Value |
| --- | --- |
| Commit | `8c327bc` |
| Machine | `DESKTOP-H3RO1EI` |
| Command | `$env:PYTHONPATH = "src"; python C:\Users\parva\AppData\Local\Temp\cpullm_bench.py` |
| Startup | 11.5 s |
| Questions | 7 |

| Question | Milliseconds | Spoken result |
| --- | --- | --- |
| What is the European lobster? | 667.5 | The stored definition, then four more stored sentences from the same article |
| What is a knowledge base? | 167.0 | Abstained. The defining sentence was the first retrieved passage and was not spoken |
| What is breadth-first search? | 119.5 | The stored definition, then three neighboring primer sentences |
| What is a rational agent? | 127.1 | The stored definition, then two neighboring primer sentences |
| What is natural language? | 111.9 | The stored definition, then two neighboring primer sentences |
| What is the capital of France? | 189.4 | Stored sentences about a "France Area" office and about Manila. Paris was not spoken |
| Who wrote Romeo and Juliet? | 265.3 | Withheld. No answer |

Sorted question times: 111.9, 119.5, 127.1, 167.0, 189.4, 265.3, 667.5. The middle value is 167.0 ms.
