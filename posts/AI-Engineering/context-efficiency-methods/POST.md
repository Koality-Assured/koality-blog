---
title: "Token counts fell by 86.53%. Now test the task."
deck: "One synthetic run measured token reduction across 15 outputs. Task performance, provider cost, and caching were outside the test."
date: 2026-10-09
domain: AI-Engineering
author: Robert Ketron
reading_time: 3 min read
canonical_url: "https://ketron.dev/blog/context-efficiency-methods"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/context-efficiency-methods/PAPER.md"
---

# Token counts fell by 86.53%. Now test the task.

That number comes from 15 synthetic outputs. If you're evaluating context compression for an agent, the next check is whether it can still complete a task with the shorter output. This benchmark measured token counts and checked 25 exact strings. It didn't test task performance.

## Where the number came from

In a single pinned local run, Headroom AI 0.40.0 compressed 15 deterministic synthetic tool outputs: five JSON outputs, five build logs, and five `grep`-hit outputs. The reported mean reduction was 86.53%. By category, the means were 64.91% for JSON, 97.52% for build logs, and 97.16% for grep hits. A separate tiktoken count of serialized messages showed similar category-level reductions.

The fixtures use repeated padding and structure, and none came from production traffic. These results describe this set. Test outputs that resemble your workload before expecting similar reductions.

## What the marker check tells you

The run tracked 25 exact strings and checked whether each survived compression. All 25 remained in the serialized output, so the exact-string check passed.

That result doesn't establish whether the surrounding meaning stayed intact, whether an agent could answer correctly, or whether the transformation resisted prompt injection. Each needs its own check.

## What the run left open

Both measures were local token counts. The `gpt-4o` label selected a local tokenizer mapping in tiktoken; no model or provider was called. The paper has no provider usage records, cache hits, latency, or billing data.

The single run was on Windows x86_64. Headroom selected its pure-Python content-detection backend there; no other backend or independent replay was tested. The paper records a host/runtime condition, not evidence of a software defect.

## What to test next

Use this as a first pass for token reduction on a defined fixture set. The public benchmark package includes the fixture generator, version pins, run manifest, individual measures, and hashes, so you can inspect the setup or repeat the run. It remains one run, not an independent replication.

For your own evaluation, start with varied outputs that reflect the workload you need to support. Check whether the agent can complete representative tasks with the compressed context. Repeat across environments and independent runs.

Provider caching, cost, billing, and latency need a separate provider-backed evaluation with safe fixtures and usage records. This benchmark has no data for those outcomes.

---

### Resources & Links

- **White paper:** [Read the full paper](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/context-efficiency-methods/PAPER.md)
- **Synthetic benchmark package:** [Browse the benchmark suite on GitHub](https://github.com/Koality-Assured/koality-whitepapers/tree/main/papers/AI-Engineering/context-efficiency-methods/supporting/benchmark)
- **Web route:** [ketron.dev/blog/context-efficiency-methods](https://ketron.dev/blog/context-efficiency-methods)
