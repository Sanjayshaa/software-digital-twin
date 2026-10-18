# Runtime Privacy Boundary & Zero-Customer-Data Invariant

**Specification Date**: October 4, 2026  
**Auditor & Verification**: Antigravity Security & Privacy Subsystem  
**Scope**: Batch Runtime Event Ingestion, Gateway Sanitization, Entity Correlation, and Adversarial Testing  
**Status**: ENFORCED & VERIFIED  

---

## 1. Executive Summary & Core Invariant

The Software Digital Twin models the **software architecture, dependency topology, and operational health** of a system—not customer activity or business records.

### The Invariant
> Under no circumstances does customer PII, confidential credentials, authorization tokens, or payment card information enter the Digital Twin database, memory representations, or analytical graphs.

Claims of "zero PII" are not marketing assertions; they are technically enforced and proven via deterministic unit and integration tests in [`backend/tests/security/test_runtime_privacy_boundary.py`](file:///Users/sanjay/DIGITAL%20TWIN%20/backend/tests/security/test_runtime_privacy_boundary.py).

---

## 2. Ingestion Model Disclosure

1. **Current Capability**: JSON and JSONL batch ingestion via authenticated API endpoint `POST /repositories/{id}/runtime-events/ingest`.
2. **Strict Disclosures**:
   - The system does **not** implement continuous background network sniffing, eBPF kernel probes, or live customer-data telemetry streaming in Phase 8.8.
   - Any ingested runtime events must be submitted explicitly through authenticated endpoints or test harness batches.
   - All runtime events are scrubbed synchronously before being passed to entity correlators or persisted in the `runtime_events` table.

---

## 3. Privacy Gateway Architecture

The Privacy Gateway consists of two deterministic sanitization passes:

```
Raw Runtime Payload
       │
       ▼
[ Layer 1: Key-Pattern Scrubbing ]  ──► Replaces matching sensitive keys with "[REDACTED]"
       │
       ▼
[ Layer 2: In-String Regex Scrubbing ] ──► Replaces embedded JWTs, emails, phone numbers,
       │                                     credit card numbers, and API tokens
       ▼
[ Layer 3: Recursive Traversal ]   ──► Recursively sanitizes nested dicts, lists, and strings
       │
       ▼
Sanitized Operational Telemetry  ──► Correlated to Structural Artifacts via Entity Correlator
```

### 3.1 Key-Pattern Scrubbing (`SENSITIVE_KEY_PATTERNS`)
Any dictionary key matching the following regexes has its entire value replaced with `"[REDACTED]"`:
- **Authentication**: `password`, `passwd`, `pwd`, `secret`, `private[-_]?key`, `token`, `jwt`, `api[-_]?key`, `auth(?:orization)?`, `bearer`, `cookie`, `session[-_]?(?:id|token)?`
- **PII / Identity**: `email`, `phone`, `mobile`, `telephone`, `cell`, `ssn`, `social[-_]?security`, `tax[-_]?id`, `dob`, `birth[-_]?date`, `date[-_]?of[-_]?birth`
- **Customer / Account Identifiers**: `customer[-_]?id`, `client[-_]?id`, `user[-_]?id`, `account[-_]?(?:number|id)`
- **Payment & Financial**: `card[-_]?(?:number|no)`, `credit[-_]?card`, `debit[-_]?card`, `cvv`, `cvc`, `pan[-_]?number`
- **Physical Address**: `address`, `street`, `zip[-_]?code`, `postal[-_]?code`, `billing[-_]?address`

### 3.2 In-String Value Regexes (`SENSITIVE_VALUE_REGEXES`)
Even if sensitive data is placed in non-sensitive keys (such as `log`, `message`, `error_stack`, or `query`), the gateway detects and redacts:
- **JWTs**: `\beyJ[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\.[a-zA-Z0-9_-]{10,}\b` ➔ `[REDACTED_JWT]`
- **Bearer Tokens**: `Bearer\s+[A-Za-z0-9\-._~+/]+=*` ➔ `Bearer [REDACTED_TOKEN]`
- **Key-Value Secrets**: `(?:password|token|secret|api_key|access_token|refresh_token|auth)=([^\s&]+)` ➔ `\1[REDACTED]`
- **GitHub PATs**: `\b(?:ghp|gho|ghu|ghs|ghr)_[A-Za-z0-9_]{36,}\b` ➔ `[REDACTED_GITHUB_TOKEN]`
- **SaaS API Keys**:
  - OpenAI / Anthropic: `\bsk-[a-zA-Z0-9]{20,}\b` ➔ `[REDACTED_API_KEY]`
  - AWS Access Keys: `\bAKIA[0-9A-Z]{16}\b` ➔ `[REDACTED_AWS_KEY]`
  - Stripe Keys: `\b(?:sk_live|pk_live)_[0-9a-zA-Z]{24,}\b` ➔ `[REDACTED_STRIPE_KEY]`
- **Email Addresses**: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,7}\b` ➔ `[REDACTED_EMAIL]`
- **Credit Card / PAN**: `\b(?:\d{4}[ -]?){3}\d{4}\b` and 15–16 digit numbers ➔ `[REDACTED_CARD]`
- **Phone Numbers**: `\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b` ➔ `[REDACTED_PHONE]`

---

## 4. Preferred Operational Telemetry Contract

The Digital Twin strictly focuses on operational telemetry needed for architectural correlation:

| Field | Purpose | Example |
|---|---|---|
| `service` | Architectural component namespace | `"payment_service"` |
| `route` | HTTP endpoint route path | `"/api/v1/checkout"` |
| `method` | HTTP method verb | `"POST"` |
| `status` | HTTP response status code | `500` |
| `latency_ms` | Request execution duration | `142.5` |
| `error_type` | Exception / failure class | `"DatabaseConnectionTimeout"` |
| `environment` | Deployment tier | `"production"` |
| `timestamp` | UTC event occurrence time | `"2026-10-04T12:00:00Z"` |
| `trace_id` | Distributed trace correlation | `"4bf92f3577b34da6a3ce929d0e0e4736"` |
| `span_id` | Operation span identifier | `"00f067aa0ba902b7"` |

---

## 5. Adversarial Verification Matrix

Verified in [`backend/tests/security/test_runtime_privacy_boundary.py`](file:///Users/sanjay/DIGITAL%20TWIN%20/backend/tests/security/test_runtime_privacy_boundary.py):

| Test Case | Attack Vector / Payload | Expected Behavior | Status |
|---|---|---|---|
| `test_email_redaction_in_keys_and_values` | Direct email keys + embedded email in log text | Keys sanitized to `[REDACTED]`, text replaced with `[REDACTED_EMAIL]` | **PASS** |
| `test_phone_number_redaction` | US and international phone numbers in text and keys | Key sanitized, log text replaced with `[REDACTED_PHONE]` | **PASS** |
| `test_customer_and_account_id_redaction` | `customer_id`, `client_id`, `account_number`, `ssn`, `tax_id` | All customer keys sanitized to `[REDACTED]` | **PASS** |
| `test_address_and_postal_redaction` | `street`, `address`, `zip_code`, `postal_code`, `billing_address` | All address keys sanitized to `[REDACTED]` | **PASS** |
| `test_payment_and_credit_card_redaction` | Visa, Mastercard, AMEX PANs + CVV | Card keys sanitized, card numbers in logs replaced with `[REDACTED_CARD]` | **PASS** |
| `test_jwt_token_redaction` | Raw base64 HMAC JWT in attributes and error messages | JWT key sanitized, JWT string replaced with `[REDACTED_JWT]` | **PASS** |
| `test_api_keys_and_secret_redaction` | GitHub PATs, OpenAI `sk-`, AWS `AKIA`, Stripe `sk_live` | API key keys sanitized, string patterns replaced with specific tokens | **PASS** |
| `test_cookies_and_authorization_headers` | Session cookies and `Authorization: Bearer` headers | Redacted to `Bearer [REDACTED_TOKEN]` and `[REDACTED]` | **PASS** |
| `test_deeply_nested_adversarial_payload` | Multi-tier dicts and lists containing mixed PII and credentials | Recursively sanitized without dropping operational telemetry | **PASS** |
