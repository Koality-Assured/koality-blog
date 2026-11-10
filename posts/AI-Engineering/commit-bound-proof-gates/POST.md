---
title: "Commit-Bound Proof Gates: Why Agent Verification Needs Exact Git HEAD Checks"
deck: "A PASS status and exit code zero prove nothing once Git history shifts. Across 31 synthetic repository scenarios, enforcing exact HEAD matching alongside Git ancestry closed every post-proof bypass where ancestry-only checks still passed 28.57%."
date: 2026-11-10
domain: AI-Engineering
author: Koality-Assured
reading_time: 6 min read
canonical_url: "https://ketron.dev/blog/commit-bound-proof-gates"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/commit-bound-proof-gates/PAPER.md"
related_whitepaper_route: "https://ketron.dev/wp/commit-bound-proof-gates"
---

# Commit-Bound Proof Gates: Why Agent Verification Needs Exact Git HEAD Checks

When an autonomous coding agent finishes a patch, runs tests, and writes `"status": "PASS"` into a build log, that receipt tells you what passed at one point in time. It does not prove that the code sitting at `HEAD` when a pull request opens, or right before a human hits squash-merge, is the same commit the verifier tested.

Any ordinary Git operation between test completion and merge breaks an unbound receipt. Running `git commit --amend`, rebasing onto `main`, cherry-picking onto a release branch, stacking one quick post-review commit on top, or leaving uncommitted edits in the working tree changes the executable bytes while leaving a JSON `"PASS"` summary untouched.

> **Read the companion white paper:** [open the full white paper on ketron.dev](https://ketron.dev/wp/commit-bound-proof-gates) for the 31-scenario Git mutation matrix, the formal `proof.schema.json` specification, the claim-to-evidence ledger, and the reproducible Python benchmark. You can also inspect the [source paper on GitHub](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/commit-bound-proof-gates/PAPER.md).

---

## The loophole hidden inside `git merge-base --is-ancestor`

During a public audit of `Koality-Assured/agent-factory` (commit `5106dd2db`) and four downstream target repositories (`core-harness-wiki#8`, `ai-harness-core#21`, `harness-cli#36`, and `koality-image-find#3`–`#4`), two patterns stood out. First, `agent-factory` specified exact branch-tip matching (`target_commit_sha == branch_tip`) for PR creation, yet its merge-validation skill specified `git merge-base --is-ancestor <target_commit_sha> <branch_tip>` alone and had no `proof.schema.json` or Python validator in `scripts/`. Second, two live PR summaries recorded `--is-ancestor main HEAD`, which verifies branch freshness against `main` rather than checking the tested commit SHA.

An ancestry check catches history rewrites (`--amend`, `rebase`, `cherry-pick`) because those commands mint unreachable commit objects. It fails open, however, when someone stacks a new unverified commit `C2` on top of the tested commit `C1`:

```text
Verified commit:    C1  <-- proof.json ("target_commit_sha": C1, "status": "PASS")
                     │
Unverified edit:    C2  <-- HEAD (adds bypass or review fix without re-running Kenji)

git merge-base --is-ancestor C1 C2   -> exit 0 (C1 is an ancestor of C2!)
HEAD == target_commit_sha            -> FAIL   (C2 != C1)
```

Across 31 offline synthetic Git repositories spanning Python, Go, and JavaScript (`10` measured runs per scenario, `310` gate evaluations per arm), that single difference accounted for the biggest real-world failure gap:

| Gate arm | Overall accuracy | Fail-closed rate | False-accept rate | Median latency (`p50`) |
| :--- | :---: | :---: | :---: | :---: |
| `naive_status_only` (`status == PASS`, `exit_code == 0`) | 29.03% | 21.43% | 78.57% | 0.1692 ms |
| `ancestry_only` (`merge-base --is-ancestor`) | 74.19% | 71.43% | 28.57% | 81.6019 ms |
| `strict_commit_bound` (`HEAD == SHA` + ancestry + clean tree + attestation) | **100.00%** | **100.00%** | **0.00%** | 104.0581 ms |

The `ancestry_only` gate failed open on `8/28` negative scenarios: all `3/3` unverified trailing commits, `2/4` detached-HEAD or dirty-worktree states, and `3/15` self-signed or missing negative-routing proofs. Requiring exact `HEAD == target_commit_sha`, `^[0-9a-f]{40}$` commit syntax, non-boolean `exit_code == 0`, clean tracked worktrees (`git status --porcelain --untracked-files=no`), `author_id != reviewer_id`, and cross-model diversity closed every negative case at a `22.46 ms` median increase over `ancestry_only`.

---

## Why file-count routing under-escalates security fixes

Running a full 11-agent review sweep on a markdown typo wastes tokens and time, yet simple heuristics cut corners in the wrong places. Across 16 synthetic multi-language diffs (`8` safe `direct` diffs and `8` high-risk `full-assurance` diffs):

- Defaulting everything to `full-assurance` scored `50.00%` accuracy (`100.00%` over-escalation on safe docs, semver bumps, and test-backed bugfixes).
- Routing `<= 1` changed file to `direct` scored `43.75%` (`7/16`), over-escalating `50.00%` (`4/8`) of two-file diffs (three code-plus-test fixes and one two-file documentation typo edit) while under-escalating `62.50%` (`5/8`) of single-file diffs touching JWT checks, Go lease mutexes, path sanitization, API endpoints, and JSON Schemas.
- Normalizing CamelCase and `snake_case` identifiers (so `RequirePermission` splits into `Require Permission` instead of hiding from word-boundary regex) before screening security, concurrency, schema, and cross-module boundaries reached `100.00%` (`16/16`) with `0.00%` under-escalation at `0.0271 ms` p50 latency.

---

## What our controlled blind-review trial actually showed

Removing an author's self-justifying explanation before security review (`nadia` blind review) is a core principle of clean-slate verification. To test it empirically, we built four multi-language seeded-defect diffs (a Go `RLock`/`Lock` lease race `CWE-362`, a Python ancestry-only gate bypass `CWE-345`, a Node.js missing-separator directory escape `CWE-22`, and a Python `except Exception: return True` fail-open handler `CWE-636`) and confirmed every seeded defect failed its reproduction test.

We then dispatched paired `blind` (diff + spec only) and `non_blind` (diff + spec + persuasive author rationale) packets to clean-slate `Gemini 3.8 Flash (High)` reviewer subagents:

- **Arm B (`blind`):** `4/4` `BLOCK` verdicts (`100.0%` critical seeded-defect catch rate), `15` total findings (`5` critical, `1` high, `7` medium, `2` low).
- **Arm A (`non_blind`):** `4/4` `BLOCK` verdicts (`100.0%` critical seeded-defect catch rate), `14` total findings (`5` critical, `2` high, `6` medium, `1` low).

The binary verdict delta was `0.0%`. On narrow single-file diffs evaluated in clean-slate context against explicit specifications, persuasive author notes did not fool the reviewer into approving any seeded defect, though the blind pass caught one extra medium edge case on same-owner lease re-acquisition and `ttl <= 0`. Whether larger multi-file pull requests or secondary model families show stronger author-anchoring divergence remains an open, unmeasured question.

---

## Three rules for autonomous promotion pipelines

1. **Bind verification receipts to exact Git commits, not branch names or `"PASS"` text.** Enforce `HEAD == target_commit_sha`, `git merge-base --is-ancestor`, and a clean tracked worktree in deterministic CI or gate code right before PR creation and again before merge.
2. **Validate proofs on the PR branch before squash merge.** GitHub squash merges mint a new commit on `main` whose parent is the previous `main` tip; keep post-merge provenance intact with standardized `X-Factory-Run` and `X-Factory-Ledger-ID` commit trailers.
3. **Never route execution tiers by changed-file count.** Screen normalized identifiers for auth, concurrency, schema, and public-API boundaries, and dispatch reviewers clean-slate with explicit invariant specs rather than chat transcripts.

---

*For the full 31-scenario matrix, candidate `proof.schema.json`, NIST AI RMF 1.0 and OWASP 2026 mappings, and reproducible Python test suite, read the [full white paper on ketron.dev](https://ketron.dev/wp/commit-bound-proof-gates) or inspect the [source paper on GitHub](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/commit-bound-proof-gates/PAPER.md).*
