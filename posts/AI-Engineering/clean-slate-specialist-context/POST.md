---
title: "The context tax: why subagents need clean-slate state instead of full chat logs"
deck: "Inheriting coordinator history multiplies token bills by O(M * K * T) and triggers attention drift. Here is why zero-flight dispatch and declarative contracts keep multi-agent harnesses reliable."
date: 2026-10-12
domain: AI-Engineering
author: Robert Ketron
reading_time: 4 min read
canonical_url: "https://ketron.dev/blog/clean-slate-context"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/clean-slate-specialist-context/PAPER.md"
---

# The context tax: why subagents need clean-slate state instead of full chat logs

A coordinator agent spends 30 turns debugging an asynchronous race condition across a distributed pipeline. It finally isolates the bug to an unhandled zero-division case in a ten-line helper function and spawns a specialist subagent to apply the patch. The specialist inspects the file, updates the function, and confirms the test in three turns. Yet your API usage dashboard records nearly 240,000 input tokens for those three turns.

That surge occurs because the orchestrator passed the coordinator's entire 60,000-token conversation history into the subagent on every single turn. This pattern is common across multi-agent orchestration frameworks. In OpenAI Codex Multi-Agent v2, the `spawn_agent` tool defaults `fork_turns` to `"all"` when omitted. Similar transcript inheritance defaults appear across open-source agent frameworks. Beyond financial expense, this practice degrades the model's reasoning capacity.

## The math of the context tax

When an orchestrator coordinates complex engineering work, it delegates sub-tasks to multiple specialist subagents. If those subagents inherit the parent conversation history, token consumption scales aggressively:

$$\text{Total Inherited Tokens} = M \times K \times T_{\text{parent}}$$

Where $M$ is the number of subagents spawned, $K$ is the average execution turns per subagent, and $T_{\text{parent}}$ is the token depth of the parent session. If a coordinator at depth $T = 60{,}000$ tokens delegates tasks to $M = 4$ specialists running $K = 3$ turns each, the harness bills $720{,}000$ input tokens purely to re-read the parent's past turns.

Under a clean-slate model where $T = 0$ and the subagent receives only a concise 800-token task contract, those same four subagents process $9{,}600$ baseline input tokens. In a deterministic benchmark of 15 software engineering tasks across 75 trials, clean-slate dispatch reduced cumulative input context by an unweighted mean of 99.72% (655 tokens versus 235,765 tokens) across a standard three-turn tool loop.

## When chat logs become toxic distractors

Financial waste is only the visible penalty. The more serious failure mode is attention decay. In 2024, Liu et al. documented the U-shaped retrieval curve in language models ("Lost in the Middle"), showing that information placed in the middle of long contexts suffers steep recall degradation. In 2025, Chroma's research on "Context Rot" demonstrated that long conversational contexts populated with semantic distractors impair complex reasoning even when relevant data is present.

In our benchmark runs, parent histories contained realistic development chatter: discarded hypotheses, old compiler dumps, and deprecated function signatures. Under the 60k-token inherited baseline, 7 of 15 subagent trials (46.67%) suffered distractor collisions. Subagents inadvertently imported deprecated function names or obsolete configuration flags discussed 15 turns earlier, depressing the task pass rate to 53.33%. Under clean-slate dispatch, distractor collisions were 0.0% and the pass rate was 100.0%.

## The prompt caching myth

Harness developers often assume that provider prompt caching makes transcript inheritance harmless. While prompt caching reduces input token read prices by 50% to 80% on cached prefixes, it leaves three core operational bottlenecks unaddressed:

- **Context window exhaustion:** A subagent that inherits 80,000 tokens has little room remaining in a 128k context window to ingest build outputs, test logs, or large diffs.
- **Latency drag:** Time-to-first-token latency increases with context length regardless of whether tokens hit a cache.
- **Attention dilution remains active:** Cached tokens participate in self-attention calculations identically to uncached tokens. A distractor degrades model reasoning just as effectively from a cache.

## The zero-flight pattern: declarative contracts

To eliminate transcript inheritance safely, the harness must transmit intent through a structured declarative task contract rather than chat logs. In our harness architecture, every delegated spawn requires four explicit fields:

```yaml
task_contract:
  authority: "Execute local bugfix on synthetic calculation service. Do not modify external configs."
  scope: "Fix ZeroDivisionError in calculate_metric_v01() in handler.py. Fallback must be 0.0. Emit SYNTHETIC_MARKER_REPAIR_V01_OK."
  targets:
    - "src/synthetic_service/handler_v01.py"
  cost_layers: "Use ast-grep to locate calculate_metric_v01; do not perform tree walks. Use Headroom on test output."
```

Instead of pre-loading file dumps into the prompt, the specialist retrieves code Just-In-Time (JIT) using targeted search tools (such as `ast-grep` for syntax trees and `qmd` for markdown discovery). This guarantees maximum attention density on the active task.

## The one real tradeoff: the Context Omission Gap

Clean-slate delegation is not free. By withholding the transcript, you place the synthesis burden entirely on the coordinator. If the human operator specified in Turn 4 that "all changes must remain Python 3.10 compatible," and the coordinator forgets to include that constraint in the task contract, the clean-slate subagent will write modern Python 3.12 syntax and introduce a regression.

Mitigate this risk through schema-enforced dispatch templates, pre-spawn contract linters, and structured clarification protocols that allow a child agent to query missing parameters rather than inheriting the entire chat log.

## Harness implementation checklist

1. **Configure `fork_turns: "none"`:** Ensure all subagent spawn primitives disable history cloning by default.
2. **Treat chat transcripts as private to the coordinator:** Never forward full message arrays into child payloads.
3. **Enforce 4-part declarative contracts:** Require authority, scope, concrete file targets, and tool rules on every dispatch.
4. **Provide targeted search tools:** Give subagents structural AST inspection and indexed retrieval rather than full-repository preloads.
5. **Log tokens by agent tier:** Measure coordinator and subagent token consumption separately to detect context leakage early.

---

### Resources & Links

- **White paper:** [Read the full paper](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/clean-slate-specialist-context/PAPER.md)
- **Synthetic benchmark package:** [Browse the benchmark suite on GitHub](https://github.com/Koality-Assured/koality-whitepapers/tree/main/papers/AI-Engineering/clean-slate-specialist-context/supporting/benchmark)
- **Web route:** [ketron.dev/blog/clean-slate-context](https://ketron.dev/blog/clean-slate-context)
