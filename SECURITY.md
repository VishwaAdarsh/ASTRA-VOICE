# ASTRA — Security Policy & Threat Model

```text
================================================================================
                                 A S T R A
                        Security & Defense Blueprint
================================================================================
```

* **Document Version:** 1.0.0
* **Status:** Authoritative Security Policy
* **Target Operating System:** Windows 10 / Windows 11

---

## 1. Security Hierarchy

The final authority order in Project ASTRA is strictly non-negotiable:

```text
SYSTEM (OS Boundaries & Hard Restrictions)
       ↓
SECURITY POLICY (Configuration & Security Controls)
       ↓
PERMISSION SYSTEM (SAFE, CONFIRM, RESTRICTED)
       ↓
TOOL REGISTRY (Explicit Tool Allowlist)
       ↓
USER AUTHORIZATION (Manual Confirmation Prompts)
       ↓
TASK / AUTOMATION ENGINE (Bounded Action Workflows)
       ↓
LLM REASONING (Model Output)
       ↓
MEMORY / WEB / VISION / UNTRUSTED DATA
```

> [!IMPORTANT]
> **Core Security Principle**: No LLM decision, scraped web page, OCR text, screenshot payload, or long-term memory entry can ever override system security policies or bypass granted tool permissions.

---

## 2. Threat Model Matrix (T1 – T15)

| ID | Threat | Attack Surface | Mitigation / Defensive Control | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **T1** | **Prompt Injection** | LLM text prompt inputs | Zero-Trust `<UNTRUSTED DATA>` XML tag wrapping & instruction-data separation in `PromptInjectionDefense`. | Low |
| **T2** | **Tool Abuse** | Tool execution parameters | Explicit `ToolRegistry` allowlists with parameter validation & permission checks. | Low |
| **T3** | **Path Traversal** | Filesystem tools | `PathResolver` normalization & folder allowlist enforcement (`Downloads`, `Documents`, `Desktop`). | Low |
| **T4** | **Command Injection** | Application launcher | Hardcoded application executable mapping (`app_allowlist`). No direct shell execution. | Low |
| **T5** | **Secret Exposure** | Console & file logs | `SecretRedactionFilter` masks API keys, Bearer tokens, and passwords automatically. | Low |
| **T6** | **Malicious Web Content** | Web fetch & research tools | Bounded HTTP fetch sizes (`MAX_FETCH_SIZE_MB = 1.0`), SSRF IP loopback blocking, HTML-to-text stripping. | Low |
| **T7** | **Malicious Documents** | Local file reader | Size limits (`MAX_FILE_SIZE_MB = 10.0`), plain-text parsing, no executable execution. | Low |
| **T8** | **Vision Injection** | OCR & visual analysis | Vision output treated strictly as untrusted text data (`<UNTRUSTED_VISION_DATA>`). | Low |
| **T9** | **Memory Injection** | Long-term memory store | Memory entries cannot convey tool authority or alter permission mode. | Low |
| **T10**| **Runaway Agent** | Autonomous task loop | Hard limits: `AGENT_MAX_STEPS = 20`, `AGENT_MAX_REPLANS = 5`, `TASK_TIMEOUT = 120.0s`. | Low |
| **T11**| **Runaway Automation** | Background triggers | Hard limits: `MAX_AUTOMATIONS = 50`, `MAX_ACTIVE_AUTOMATIONS = 20`, quiet hours (`23:00 - 07:00`). | Low |
| **T12**| **Resource Exhaustion** | System RAM / Disk / Network | Rotating log files (5MB x 3 backups), automatic temp vision PNG cleanup. | Low |
| **T13**| **Database Corruption** | SQLite database | Schema migrations, SQLite transactions, connection isolation. | Low |
| **T14**| **Crash Recovery Failure**| Application crash | `CrashRecoveryManager` audits tasks on startup, marking executing runs as `FAILED` (never auto-resumes dangerous actions). | Low |
| **T15**| **Unauthorized Access** | Local desktop interface | Local desktop user context only. No remote open ports or external network listening servers. | Low |

---

## 3. Reporting Security Vulnerabilities

To report a security vulnerability in Project ASTRA:
1. Open a confidential GitHub Security Advisory or report to the project maintainers.
2. Provide details of the vulnerability, affected component, and reproduction steps.
