---
title: "Stop Grepping Your Monorepo: Why Layered BM25 and AST Slicing Beat Recursive LLM Dumps"
deck: "Giving coding agents unrestricted bash access to run recursive grep dumps thousands of unranked tokens into context. Here is why layered BM25 and AST slicing cut context burn by 60% and slash multi-turn bills by 92%."
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

To an LLM agent, however, that command is financial and cognitive poison.

Because the agent cannot "glance" at output without ingesting it, all twenty unranked matches flood into the context window. To evaluate the matches, the model's next tool call reads the entire file. Then the next file. Within two turns, the agent has dumped 30,000 tokens of raw source code, build scripts, and test logs into conversation history.

In a single-turn prompt, that might cost a fraction of a cent. But autonomous agents run in multi-turn loops.

---

## The compounding math of the Context Tax

In multi-turn agent harnesses (Claude Code, Cursor, Windsurf, or custom agent swarms), the model re-ingests its entire conversational history on every turn. 

If your agent loads a bloated 25,000-token file dump on Turn 2 of a 10-turn task, those 25,000 tokens don't disappear on Turn 3. They get re-serialized, re-transmitted, and re-billed on Turn 3, Turn 4, Turn 5, all the way through Turn 10.

$$\text{Cumulative Context Tax} = \sum_{t=1}^{N} \left( C_0 + \sum_{i=1}^{t} \Delta c_i \right) \times P_{\text{input}}$$

A single careless search at the start of a session billable across 9 subsequent turns creates **225,000 redundant token reads**.

```text
Turn 1: User Prompt (500 tokens)
Turn 2: Grep & File Dump (+25,000 tokens) -> 25,500 total
Turn 3: Model reasoning & edit attempt    -> 26,000 total (includes 25k dump)
Turn 4: Test execution failure           -> 27,000 total (includes 25k dump)
...
Turn 10: Final commit                    -> 32,000 total (includes 25k dump)

Cumulative tokens billed for that single dump: 25,000 x 9 = 225,000 tokens.
```

Worse than the bill is the reasoning penalty. Flooding context with thousands of irrelevant lines triggers the "Lost in the Middle" attention degradation proven by Liu et al. Critical system instructions and architectural constraints get drowned out by incidental comments and test mocks.

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
│ -> Single tool call, 30-line window, 5.2x speedup      │
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

In our repository benchmarks, `qmd search` achieved an average search latency of **204ms**, with a Fleet Mean Reciprocal Rank (MRR) of **0.9286** and Precision@1 of **85.7%**.

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

The agent sees every class, method, and signature in 45 tokens instead of 3,500 tokens. Once it identifies that `match_route` holds the bug, it requests only lines 45–60. In our benchmarks, AST outline extraction consistently delivered **91.5% to 94.5% token savings** over full-file reads.

### 3. Consolidated batch retrieval (`qmd multi-get -l 30`)

If the agent needs context across three related files, sequential `read_file` calls waste time and cause context chatter.

`qmd multi-get` batches the request into an atomic CLI invocation with strict line bounding:

```bash
qmd multi-get doc1,doc2,doc3 --format md -l 30
```

The `-l 30` flag truncates matches to a 30-line envelope around the target section. In our benchmark, batch multi-get ran in **179.32ms** compared to **945.17ms** for sequential reads—a **5.27x speedup factor** while cutting character payload by 60%.

---

## The empirical proof: 60% token cut, 92% cost savings

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
| Multi-Doc Retrieval Latency | 945.17 ms | 179.32 ms | **5.27x faster** |

### The prompt caching multiplier

Because Arm B returns structured, deterministic document snippets, it preserves prompt prefix stability. Turns 2 through 10 hit prompt cache discounts (90% on Anthropic, 75% on Google and OpenAI).

Here is the total bill across 5 developer tasks in a 10-turn session:

| Model Tier | Arm A Cost | Arm B Cost | Net Savings |
| :--- | :---: | :---: | :---: |
| **Claude 3.5 Sonnet** | \$0.8899 | \$0.0669 | **92.48%** |
| **Claude 5.5 Sonnet** | \$0.4449 | \$0.0335 | **92.48%** |
| **Gemini 3.8 Flash** | \$0.0445 | \$0.0057 | **87.15%** |
| **GPT-4o** | \$0.7415 | \$0.1615 | **78.22%** |

On Claude 3.5 Sonnet, that represents an immediate **92.48% reduction in inference spend**.

---

## Three rules for your agent toolchain

If you are building an AI coding harness or an MCP server, apply these three rules:

1. **Remove recursive grep from your agent's default tools.** Unconstrained `grep -r` is an invitation for token bloat. Replace it with an indexed BM25 search tool that returns scored excerpts.
2. **Require AST outlines before code reads.** Never let an agent read a 2,000-line source file just to find where a function is defined. Force an outline step first.
3. **Isolate your indexing database in a detached worktree.** If your agent search tool writes to a local SQLite database or vector cache in the developer's working directory, it will dirty `git status` and bust prompt caches. Run your indexer in a detached worktree.

---

*For the complete mathematical formulation of the Context Tax, our full claim-to-evidence ledger, and the offline reproducible benchmark suite, read the full white paper: [Empirical Retrieval Cost Layers in Autonomous Agent Systems](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/empirical-retrieval-cost-layers/PAPER.md).*
