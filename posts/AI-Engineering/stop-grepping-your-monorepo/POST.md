---
title: "Stop Grepping Your Monorepo: Why Layered BM25 and AST Slicing Beat Recursive LLM Dumps"
deck: "Giving coding agents unrestricted bash access to run recursive grep can dump thousands of unranked tokens into context. A local benchmark found that layered BM25 and AST slicing cut measured context volume by 60%; provider billing was not measured."
date: 2026-11-04
domain: AI-Engineering
author: Robert Ketron
reading_time: 6 min read
canonical_url: "https://ketron.dev/blog/stop-grepping-your-monorepo"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/empirical-retrieval-cost-layers/PAPER.md"
---

# Stop Grepping Your Monorepo: Why Layered BM25 and AST Slicing Beat Recursive LLM Dumps

Ask an autonomous coding agent to track down a bug in a multi-project repository, and watch what it types into its bash tool:

```bash
git grep -i "handle_webhook"
```

To a software engineer staring at a terminal, `git grep` is second nature. You scan twenty lines of output in two seconds, ignore eighteen of them, and click on the one file you actually care about.

To an LLM agent, that output is context the model has to process before it can choose the next file to inspect.

Because the agent cannot inspect the output outside its request context, every unranked match becomes part of the material it must evaluate. In the benchmark's naive arm, that leads to full-file reads and a 29,662-token single-turn context across five retrieval scenarios.

The effect compounds when the loop retains context across turns.

---

## The compounding math of the Context Tax

In the modeled multi-turn loop, retained conversation context is included in each subsequent request.

If an agent loads a 25,000-token file dump on Turn 2 of a 10-turn task, those tokens remain in the modeled context for the remaining turns. Provider billing and cache behavior are outside this example.

$$\text{Cumulative Context Volume} = \sum_{t=1}^{N} \left( C_0 + \sum_{i=1}^{t} \Delta c_i \right)$$

A single careless search at the start of a session, retained across 9 subsequent turns, creates **225,000 redundant token reads** in this model.

```text
Turn 1: User Prompt (500 tokens)
Turn 2: Grep & File Dump (+25,000 tokens) -> 25,500 total
Turn 3: Model reasoning & edit attempt    -> 26,000 total (includes 25k dump)
Turn 4: Test execution failure           -> 27,000 total (includes 25k dump)
...
Turn 10: Final commit                    -> 32,000 total (includes 25k dump)

Cumulative retained context reads for that single dump: 25,000 x 9 = 225,000 tokens.
```

Large amounts of irrelevant context can also make relevant evidence harder to retrieve. Liu et al.'s "Lost in the Middle" results establish a retrieval limitation in the tested long-context settings; this post does not claim a measured reasoning effect for coding agents.

---

## The solution: The 4-layer retrieval stack

Instead of treating an autonomous agent like a human with a bash prompt, we engineered a layered local retrieval pipeline in `Koality-Assured`:

```text
┌────────────────────────────────────────────────────────┐
│ Layer 1: Lexical BM25 (qmd search)                     │
│ -> 200ms latency, scored line snippets, no full files  │
└──────────────────────────┬─────────────────────────────┘
                           │ Miss or conceptual query
                           ▼
┌────────────────────────────────────────────────────────┐
│ Layer 2: Dense Semantic Vector (qmd vsearch)           │
│ -> Local embedding + cross-encoder (circuit breaker)   │
└──────────────────────────┬─────────────────────────────┘
                           │ Target identified
                           ▼
┌────────────────────────────────────────────────────────┐
│ Layer 3: Batch Line-Bounded Fetch (qmd multi-get -l 30)│
│ -> Single tool call, 30-line window, ~2.12x faster      │
└──────────────────────────┬─────────────────────────────┘
                           │ Code target?
                           ▼
┌────────────────────────────────────────────────────────┐
│ Layer 4: Concrete Syntax Tree Slicing (ast-grep)       │
│ -> Structural outlines; read functions, not files      │
└────────────────────────────────────────────────────────┘
```

### 1. BM25 with scored snippets (`qmd search`)

BM25 term weighting (Robertson & Zaragoza) computes true document relevance through term frequency saturation and document length normalization. 

When the agent queries our local indexer (`qmd search "isolate work git worktree"`), it does not get flat text lines. It gets structured JSON with scored snippets:

```json
[
  {
    "docid": "ai-tooling/skills/meta/isolate-work/SKILL.md",
    "score": 0.942,
    "lines": "25-32",
    "snippet": "Run `python scripts/routing/spawn_worktree.py create --slug <task>` before mutating..."
  }
]
```

The agent gets the exact file anchor and the exact command it needs in 180 tokens—without reading the rest of the 500-line skill document.

In the cited public reports, `qmd search` measured a p50 latency of **187.77ms**, with Fleet Mean Reciprocal Rank (MRR) of **0.9062** and Precision@1 of **81.2%**.

### 2. AST outlines instead of full files (`ast-grep outline`)

When an agent needs to inspect a code file, naive agents dump the entire module.

Instead, our harness mandates an outline-first rule using `ast-grep` and Tree-sitter:

```bash
ast-grep outline src/core/router.py
```

Output:
```text
class Router:
  def __init__(self, config_path: str) -> None: ...
  def match_route(self, request: Request) -> Route: ...
  def dispatch(self, route: Route) -> Response: ...
```

The agent sees every class, method, and signature before requesting a narrower range. The cited multi-trial report measured estimated AST-output savings of **93.3%** for Python scripts, **90.5%** for agent-card YAML, and **94.5%** for skill frontmatter.

### 3. Consolidated batch retrieval (`qmd multi-get -l 30`)

If the agent needs context across three related files, sequential `read_file` calls waste time and cause context chatter.

`qmd multi-get` batches the request into an atomic CLI invocation with strict line bounding:

```bash
qmd multi-get doc1,doc2,doc3 --format md -l 30
```

The `-l 30` flag bounds the returned context around the target section. The cited QMD suite measured batch multi-get at **189.3ms** versus **400.6ms** for two serial reads—about **2.12x faster** while cutting the reported character payload by 60%.

---

## The empirical proof: a 60% context cut

To measure the real-world difference, we evaluated five canonical developer retrieval scenarios on the `ai-router` production codebase:
1. Worktree isolation policy and spawning scripts.
2. AST-grep configuration and pattern extraction.
3. STRIDE threat model assessment agent spec.
4. Confluence document sync tools and CQL search.
5. Model pricing tables and cost estimation algorithms.

We ran each scenario under two arms:
- **Arm A:** Standard shell `git grep` and full-file reading.
- **Arm B:** Layered QMD BM25 `search`, `ast-grep outline`, and bounded `multi-get`.

| Metric | Arm A (Raw Grep + Read) | Arm B (Layered Retrieval) | Savings |
| :--- | :---: | :---: | :---: |
| Single-Turn Context Ingested | 29,662 tokens | 11,746 tokens | **60.40%** |
| 10-Turn Cumulative Compounding | 296,620 tokens | 117,460 tokens | **179,160 tokens** |
| Multi-Doc Retrieval Latency | 400.6 ms | 189.3 ms | **~2.12x faster** |

### What the benchmark does not measure

The benchmark measures local context volume and retrieval latency. It does not send requests to model APIs, observe cache hits, or estimate billed cost. Provider behavior differs: [Anthropic prompt caching](https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching) uses cache controls and stable prefixes; [Gemini context caching](https://ai.google.dev/gemini-api/docs/caching) documents model-specific thresholds and cached-token telemetry; and [OpenAI prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching) documents model-dependent cacheable lengths and usage fields. A stable retrieval output may help cache reuse, but any dollar impact requires provider-specific measurements.

---

## Three rules for your agent toolchain

If you are building an AI coding harness or an MCP server, apply these three rules:

1. **Remove recursive grep from your agent's default tools.** Unconstrained `grep -r` is an invitation for token bloat. Replace it with an indexed BM25 search tool that returns scored excerpts.
2. **Require AST outlines before code reads.** Never let an agent read a 2,000-line source file just to find where a function is defined. Force an outline step first.
3. **Isolate your indexing database in a detached worktree.** If your agent search tool writes to a local SQLite database or vector cache in the developer's working directory, it can dirty `git status`. A detached worktree keeps index writes out of the active branch; any prompt-cache effect still needs provider-specific telemetry.

---

*For the complete mathematical formulation of the Context Tax, our full claim-to-evidence ledger, and the offline reproducible benchmark suite, read the full white paper: [Empirical Retrieval Cost Layers in Autonomous Agent Systems](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/empirical-retrieval-cost-layers/PAPER.md).*
