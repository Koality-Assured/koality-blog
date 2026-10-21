---
title: "The reveal route returns an envelope: keeping secrets out of tool results"
deck: "An encrypted reveal response, local MCP secret use, and the limits of an offline Python simulation."
date: 2026-10-20
domain: AI-Engineering
author: Robert Ketron
reading_time: 5 min read
canonical_url: "https://ketron.dev/blog/reveal-route-returns-envelope"
related_whitepaper: "https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/zero-plaintext-vault-reveal/PAPER.md"
---

# The reveal route returns an envelope: keeping secrets out of tool results

Consider an agent that needs a database credential for a migration. A tool that returns the credential as text could include it in its result. This illustrative example uses a synthetic placeholder:

```json
{
  "status": "success",
  "password": "SENTINEL_CANARY_DATABASE_PASSWORD_00000000-0000-4000-8000-000000000003"
}
```

If a harness includes that tool result in later model requests, the credential may travel with the conversation history. Provider caching, logging, and retention behavior depends on the systems in use; this post does not measure those systems.

Tool designs should keep credential values out of model-facing tool results where the task allows the tool to use the credential locally.

---

## The API returns an encrypted envelope

In `llm-vault`, the standalone reveal endpoint (`POST /api/v1/secrets/:id/reveal`) returns an encrypted payload and a caller key envelope. The following shape is illustrative; the placeholder strings are synthetic and are not valid ciphertext:

```json
{
  "id": "sec_example_02",
  "vaultId": "vlt_example_01",
  "version": 1,
  "keyVersion": 1,
  "encryptedPayload": {
    "algorithm": "AES-256-GCM",
    "ciphertext": "SYNTHETIC_CIPHERTEXT_PLACEHOLDER",
    "iv": "SYNTHETIC_IV",
    "authTag": "SYNTHETIC_AUTH_TAG",
    "aad": "tenant_example:vlt_example_01:sec_example_02:1:1",
    "keyVersion": 1
  },
  "encryptedVaultKey": {
    "ciphertext": "SYNTHETIC_WRAPPED_KEY_PLACEHOLDER",
    "iv": "SYNTHETIC_WRAPPED_KEY_IV",
    "authTag": "SYNTHETIC_WRAPPED_KEY_AUTH_TAG",
    "aad": "SYNTHETIC_AGENT_AAD_PLACEHOLDER",
    "keyVersion": 1
  },
  "auditEventId": "evt_example_01"
}
```

The payload includes AES-256-GCM ciphertext and metadata. Its canonical AAD binds the tenant, vault, secret, version, and key version as five colon-delimited fields. The caller key envelope is a separate structure. These are source-code facts; this post does not run the API route.

The reveal response contains the encrypted payload rather than the decrypted secret value.

---

## Local secret use in the MCP process

The MCP client decrypts the payload locally using WebCrypto. The decrypted value exists in MCP process memory while the operation uses it.

For command execution, the registered tool is `vault_run_command`. It can resolve a vault handle, supply the credential to the command, and return the command result. This flow keeps the value out of the ordinary tool result by design, while the secret is still present in local process memory during use.

```text
┌────────────────────────────────────────────────────────────────────────┐
│ Illustrative local command flow                                      │
│                                                                        │
│ 1. Agent Loop ──► Calls MCP: vault_run_command(handle="...")          │
│ 2. MCP Server ──► Requests envelope from Vault API                     │
│ 3. MCP Server ──► Unwraps key & decrypts payload via WebCrypto in RAM │
│ 4. MCP Server ──► Supplies secret to the configured command            │
│ 5. Child Proc ──► Runs command, writes stdout/stderr                   │
│ 6. MCP Server ──► Scrubs stdout/stderr streams before replying         │
│ 7. MCP Server ──► Returns JSON: {"exitCode": 0, "stdout": "..."}       │
│                                                                        │
│ Example result omits the secret; other boundaries remain               │
└────────────────────────────────────────────────────────────────────────┘
```

The MCP server has a separate `getSecret` raw-reveal path. It requires `allowRawContextReveal` and out-of-band human confirmation. That flag does not change the API reveal route's envelope response.

---

## Output scrubbing covers selected variants

Commands may print credentials to `stdout` or `stderr`, so the MCP source includes output filtering for selected secret forms.

The source describes redaction of raw, trimmed, Base64, and URL-encoded variants. This is a pattern-based filter. It does not guarantee removal of partial secrets, unusual encodings, or other side-channel output. The Python benchmark included with the paper measures Python string replacement, not this TypeScript scrubber.

---

## What the offline simulation measures

The paper's offline Python simulation uses five synthetic examples: an API-key-shaped value, a PostgreSQL URI, a JWT-shaped placeholder, an SSH-key-shaped placeholder, and a webhook secret. Its fixed sentinel markers are patterned strings, not high-entropy random tokens. The runner constructs API-shaped JSON, an MCP-shaped result, a log string, and two prompt histories. It does not invoke `llm-vault`, `llm-vault-mcp`, a subprocess, an LLM, or a network API.

All five fixtures pass each constructed check. The naive histories contain eight literal sentinel appearances and ten raw credential appearances; the sandbox-shaped histories contain none of either. These values are reported separately because some sentinel strings occur inside the raw credentials.

Across the constructed three-turn histories, mean cumulative input tokens are 326.6 for the naive case and 193.8 for the sandbox-shaped case. The unweighted mean of the five per-fixture reductions is **35.26%**; the reduction between the displayed means is **40.66%**. This comparison describes the authored histories, not a live agent task.

---

## Three rules for agent tool builders

For tool builders, three useful design practices are:

1. Design tools to use credentials without returning their values in ordinary tool results when the action can be performed locally.
2. Document where decryption occurs and what local process memory contains during an operation.
3. Treat output scrubbing as a bounded filter. Test the required variants and handle the remaining output paths explicitly.

## Further reading

- [Paper #3: Zero-plaintext agent context](https://ketron.dev/wp/zero-plaintext-vault-reveal)
- [Claim-to-evidence ledger](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/zero-plaintext-vault-reveal/supporting/CLAIM-TO-EVIDENCE.md)
- [Reproducibility guide](https://github.com/Koality-Assured/koality-whitepapers/blob/main/papers/AI-Engineering/zero-plaintext-vault-reveal/supporting/REPRODUCIBILITY.md)
