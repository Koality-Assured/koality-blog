---
title: "A 0.95 gate is not a scoreboard: why context scrubbers must prioritize precision over noisy recall"
deck: "A synthetic evaluation compares a deterministic scanner with simple regex baselines, including the precision, recall, and output-size trade-offs the measurements actually show."
date: 2026-10-27
domain: AI-Engineering
author: Robert Ketron
reading_time: 5 min read
canonical_url: "https://ketron.dev/blog/precision-first-context-scrubbing"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/precision-first-context-scrubbing/PAPER.md"
---

# A 0.95 gate is not a scoreboard: why context scrubbers must prioritize precision over noisy recall

Consider an illustrative autonomous coding-agent workflow that runs a regex scan before opening a pull request. The scenario below is hypothetical; this benchmark did not run an agent or test whether findings change its behavior.

The linter scans the codebase and immediately flags four "Critical PII Leaks":
1. `host: "127.0.0.1"` &rarr; *Public IPv4 address detected!*
2. `adminEmail: "dev-null@example.com"` &rarr; *Customer email detected!*
3. `ssn: "000-12-3456"` &rarr; *US Social Security Number detected!*
4. `testCard: "4111-1111-1111-1111"` &rarr; *Visa credit card PAN detected!*

An engineer could inspect each finding. An agent could instead treat it as an issue to fix; this example illustrates a possible consequence rather than a measured outcome.

In this hypothetical, the agent might try to remediate the findings:
- It replaces `"127.0.0.1"` with `"[REDACTED]"`, crashing the local test server.
- It replaces the test-only value with `"[REDACTED]"`, potentially changing the behavior under test.
- It replaces `dev-null@example.com` with `"[REDACTED]"`, breaking unit test email assertions.

If those edits broke an assertion, the test suite could fail and require further work. This release does not measure that loop or its cost.

False-positive findings can add irrelevant tool output. Whether they harm agent task performance remains unmeasured here.

---

## The naive regex baseline: 46 false alarms in the synthetic corpus

For this benchmark, we compared the scanner with six simple unvalidated regex patterns. They are specific baselines included with the package, not a representative survey of all pre-commit hooks or DLP tools:
- Any four dot-separated numbers are assumed to be an IP address (`\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b`).
- Any sequence of 13 to 19 digits is assumed to be a credit card.
- Any nine-digit sequence is assumed to be an SSN.
- Any `user@domain.tld` is assumed to be a real personal email.

We compared the patterns with a 101-case synthetic corpus in `supporting/benchmark/corpus/labeled.jsonl`. It contains 13 documented fake Stripe card format markers, 3 MAC format markers from the IANA documentation range, and 85 negative controls. The labels describe format recognition only; no live personal data is included. There are no positive email, SSN, IPv4, or IPv6 cases.

The regex baseline produced **46 false positives**: 10 card-shaped matches, 8 SSN-shaped matches, 8 email matches, 15 IPv4 matches, 2 IPv6 matches, and 3 MAC matches. It also detected all 16 positive format markers, giving aggregate precision **0.2581** and recall **1.0000** on this corpus. These counts characterize only the supplied fixtures and patterns. The token cost is measured separately on a five-file workload below; the corpus count cannot be converted into a claim about thousands of context tokens.

---

## The solution: deterministic structural validation

The pinned `koality-pii-scanner` source combines regular-expression candidate extraction with structural and contextual checks. The benchmark shows the resulting trade-off on its test markers; it does not establish that every actual leak will be detected:

### 1. Credit Cards: Luhn Checksum + IIN Network Ranges

A candidate number between 13 and 19 digits must first match an allocated Issuer Identification Number (IIN) per ISO/IEC 7812 (e.g. Visa `4`, Mastercard `51-55` or `2221-2720`, Amex `34/37`). Then, it must satisfy the modulus-10 **Luhn algorithm**:

$$S = \sum_{i=0}^{n-1} f(d_i, i) \equiv 0 \pmod{10}$$

An invalid test value may satisfy a broad digit-pattern regex but fail the Luhn check. The benchmark includes labeled negative controls for such values; it does not validate active payment accounts.

### 2. Network Addresses: Globally Routable Unicast Verification

Instead of naive regex matching on dotted quads, the scanner passes candidate IPs directly to Python's `ipaddress` library and checks `addr.is_global and not addr.is_multicast`.

The implementation excludes address classes such as:
- Private RFC 1918 subnets (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`)
- Loopback bindings (`127.0.0.0/8` and `::1`)
- Documentation prefixes (`192.0.2.0/24`, `198.51.100.0/24`, `203.0.113.0/24`, `2001:db8::/32`)
- Shared CGNAT address space (`100.64.0.0/10`)
- Several explicit placeholder/resolver addresses configured in the pinned source.

These implementation rules do not guarantee that every server configuration is free of false alerts; the benchmark measures only its stated fixtures.

### 3. US SSNs: SSA Structure + Contextual Anchoring

Per the Social Security Administration's randomization rules, area numbers `000`, `666`, and `900–999` are unissued, group `00` is invalid, and serial `0000` is invalid.

For an unformatted nine-digit candidate, the scanner requires **contextual keyword anchoring**: `ssn` or `social security` must appear within 20 non-digit characters. The corpus uses the SSA-invalid `000-12-3456` as a negative control; it does not include positive SSN cases.

### 4. Emails: RFC 2606 Reserved Domain Suppression

Any email address ending in `.test`, `.example`, `.invalid`, `.localhost`, `example.com`, `example.org`, or `example.net` is suppressed at the token level.

### 5. Line-Length Skip Behavior and ReDoS Limits

The scanner checks for lines longer than 10,000 characters and records an overlength skip. In one measured call, a 24 KB line was skipped in 46.656 ms. The benchmark did not run an unprotected or adversarial regex, so this observation does not establish ReDoS resistance, a worst-case runtime bound, or elimination of hangs.

---

## The results: precision, recall, and output-size trade-offs

Across the same 101 cases, the deterministic scanner produced 8 true positives, 1 false positive, and 8 false negatives: aggregate **precision 0.8889** and **recall 0.5000**. It detected 5 of 13 positive card-format markers and all 3 positive MAC-format markers, with 1 MAC false positive. The other four categories have no positive examples, so their recall cannot be computed. The baseline measured precision 0.2581 and recall 1.0000.

The scanner repository has a configured 0.95 corpus-test floor, but that threshold is not a measured result for this publication: on this fixture set, observed deterministic recall is 0.5000. See the [pinned corpus-test source](https://github.com/Koality-Assured/koality-pii-scanner/blob/514f708e8890add75a963ff771245c1256394323/tests/test_corpus.py).

On a separate five-file all-negative synthetic workload, the baseline emitted 17 findings and 912 serialized JSON tokens; the deterministic scanner emitted 0 findings and 1 token (911 fewer tokens, 99.89%). One run on a host reported as `Windows-10-10.0.26200-SP0` scanned 10,000 generated lines in 1.599 seconds (6,253.6 lines/second); a 100-line scan call took 7.48 ms. These are fixture- and environment-specific observations, not context-window or latency guarantees.

---

## Stop building noisy guardrails

These measurements show that the deterministic scanner emitted less finding JSON on one all-negative workload, while missing half of the positive format markers in the labeled corpus. No agent, LLM self-scrubbing system, real PII detector, or task outcome was evaluated.

The results support measuring both false positives and false negatives on workload-specific fixtures. They do not establish complete data containment; teams should evaluate the scanner against their own requirements and representative data.

---

*For the confusion matrix, fixture limits, and reproduction instructions, read the full white paper: [Precision-First Context Scrubbing: Measuring Synthetic Format-Marker Detection and Finding-Output Size](/wp/precision-first-context-scrubbing).*
