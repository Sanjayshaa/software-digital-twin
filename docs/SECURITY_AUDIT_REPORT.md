# Security Audit Report: AI-Powered Software Digital Twin

**Audit Date**: October 2026  
**Phase**: 8.6.4 — Security Closure & API Hardening Audit  
**Auditor**: Antigravity Autonomous Security Architecture Pair  
**Scope**: All backend API endpoints, models, acquisition services, AST parsers, engines, database queries, and configuration files.  
**Classification Standard**: `CONFIRMED_VULNERABILITY`, `SECURITY_WEAKNESS`, `MISSING_CONTROL`, `INSUFFICIENT_EVIDENCE`, `PASS`, `NOT_APPLICABLE`.  
**Hard Invariant**: *A repository is untrusted data. It may be cloned, read, parsed, indexed, normalized, modeled, and analyzed. It must NEVER be implicitly executed, built, installed, imported, or sourced.*

---

## 1. Executive Summary

This security audit concludes Phase 8.6 (8.6.1 through 8.6.4) with systematic code-level verification, adversarial testing, and end-to-end regression across all 30 security domains (A through AD).

### Key High-Level Findings & Status:
1. **SEC-01 (Filesystem Escape / Traversal)**: **FIXED**. Canonical path containment to approved workspace roots enforced; directory traversal sequences unconditionally blocked; outside-pointing symlinks pruned during scanning.
2. **SEC-02 (SSRF in Git Acquisition & Redirects)**: **FIXED**. Strict HTTPS scheme validation, credential stripping, custom port prohibition, loopback/private/link-local/cloud-metadata blocking, pre-resolution DNS checking (rejecting multi-homed records with private IPs), and git subprocess redirect blocking (`-c http.followRedirects=false`).
3. **SEC-03 & SEC-04 (Cross-Resource IDOR / BOLA)**: **FIXED**. Scenarios and Incidents strictly scoped to owning repository; cross-repository access or deletion deterministically returns HTTP 404 (non-disclosure).
4. **SEC-05 (Authentication & Object-Level Authorization)**: **FIXED**. PBKDF2-HMAC-SHA256 password hashing, signed JWT Bearer tokens, token revocation cache, User entity with Alembic migration `f1a2b3c4d5e6`, and repository ownership authorization.
5. **SEC-06 (Overly Permissive Wildcard CORS with Credentials)**: **FIXED**. CORS origins restricted to explicit configured list (`settings.CORS_ALLOWED_ORIGINS`). Configuration model strictly validates that wildcard `*` is never paired with credentials. Unauthorized origins receive 0 CORS headers.
6. **API Abuse & Request Size Governance**: **IMPLEMENTED**. 64KB body limit for auth endpoints, 10MB limit for general API endpoints (HTTP 413 `PAYLOAD_TOO_LARGE`). Login brute-force rate limiter (5 failed attempts = 300s lockout, HTTP 429). Bounded payload collections for scenarios, incidents, and telemetry.
7. **Analysis Resource Governance**: **IMPLEMENTED**. Scanner cumulative bytes ceiling (500MB), max files (50,000), max scan depth (30), max single file (50MB), path length limit (1024), symlink count limit (1000), scan duration limit (120s). Explicit structured truncation status (`is_truncated=True`, `truncation_reason=RESOURCE_LIMIT_EXCEEDED`).
8. **Failure Atomicity & Cleanup**: **IMPLEMENTED**. Failed repository acquisitions automatically clean up temporary directories and roll back database transactions, preventing orphan records or stale workspace files.
9. **Regression & Empirical Soundness**:
   - Security regression suite: **58 / 58 PASS**.
   - Total backend regression suite: **241 / 241 PASS**.
   - Real `LAB-RECORD-SYSTEM` twin metrics verified: 120 Changed, 29 Affected, 7 Multi-hop, 57 Evidence Paths (57/57 verified against DB), 2 affected tests, 3 unaffected tests, 114 unknown coverage.
   - Headless Chrome CDP Acceptance: **10 / 10 Steps Passed** (0 console errors, 0 failed API requests).

---

## 2. Audit Matrix Across Scope Domains (A to AD)

| Domain | Scope Area | Current Posture | Audit Classification |
|---|---|---|---|
| **A** | Authentication | PBKDF2-HMAC-SHA256, JWT Bearer tokens, active status checks | **PASS** |
| **B** | JWT / Session Security | HMAC-SHA256 signatures, expiration verification, revocation cache | **PASS** |
| **C** | Authorization / RBAC | Repository ownership boundary, role taxonomy (Viewer, Owner, Admin) | **PASS** |
| **D** | IDOR / BOLA | Scenario & Incident endpoints enforce repo matching with 404 | **PASS** |
| **E** | Cross-User / Cross-Repo Isolation | Verified via multi-user / multi-repo cross-boundary test fixtures | **PASS** |
| **F** | Snapshot Authorization | Foreign snapshots rejected with 400 in impact/tests | **PASS** |
| **G** | Analysis / Incident Authorization | Scoped strictly to repository ID; cross-repo access returns 404 | **PASS** |
| **H** | Rate Limiting & Abuse Resistance | Application-level login rate limiter (5 fails = 300s lockout) | **PASS** |
| **I** | Repository Acquisition Security | `shell=False`, argument array, clean environment, redirects disabled | **PASS** |
| **J** | SSRF | Private IPs, link-local, cloud metadata, multi-IP DNS, redirects blocked | **PASS** |
| **K** | Path Traversal | Canonical containment verification, traversal sequences blocked | **PASS** |
| **L** | Command Injection | Explicit argument list, no shell interpolation, sanitized environment | **PASS** |
| **M** | Malicious Repository Handling | Static AST parsing only; scripts/build tools never executed | **PASS** |
| **N** | Payload / Resource Exhaustion | 10MB global body limit, 64KB auth limit, 500MB cumulative repo scan limit | **PASS** |
| **O** | Secret & Credential Leakage | GitHub PATs not persisted; logs/sanitizer redacts secrets | **PASS** |
| **P** | API Input Validation | Pydantic validation, regex constraints on usernames/emails, payload bounds | **PASS** |
| **Q** | CORS / CSRF | Explicit origin allowlist; no wildcard with credentials; preflight verified | **PASS** |
| **R** | Security Headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, CSP | **PASS** |
| **S** | Database Access Boundaries | All queries scoped by repository/owner filters; ORM parameterized | **PASS** |
| **T** | SQL Injection | Zero raw string SQL concatenation; 100% ORM parameterized queries | **PASS** |
| **U** | Filesystem Isolation | Canonical path checks; temporary clone dirs isolated and cleaned on error | **PASS** |
| **V** | Dependency / Package Security | Dependencies pinned in requirements.txt; no external build scripts | **PASS** |
| **W** | Docker / Container Security | PostgreSQL exposed on dedicated port 5434; credentials configurable | **ACCEPTED RISK** |
| **X** | Frontend Security | Client-side HTML escaped via `escapeHtml()`; no direct eval | **PASS** |
| **Y** | Error / Stack-Trace Leakage | Unhandled exceptions handled; secrets redacted in error strings | **PASS** |
| **Z** | Logging & Telemetry Leakage | `sanitizer.py` redacts passwords, tokens, auth headers; PATs stripped | **PASS** |
| **AA**| GitHub Token / PAT Handling | Tokens injected only in memory for git clone; stripped from URL & stderr | **PASS** |
| **AB**| Cross-Snapshot Contamination | Virtual Twin simulations isolated in-memory; DB snapshots immutable | **PASS** |
| **AC**| Concurrent Request Isolation | Database sessions scoped per request (`get_db`), thread-safe limiters | **PASS** |
| **AD**| Security Regression Coverage | 58 dedicated automated security tests in `backend/tests/security/` | **PASS** |

---

## 3. Finding Log & Remediation History

### Finding SEC-01: Local Path Traversal / Host Filesystem Escape via `/onboard`
- **Classification**: `CONFIRMED_VULNERABILITY`
- **Status**: **FIXED** (Phase 8.6.3 Run 3)
- **Severity**: **CRITICAL (P0)**
- **Remediation**: Implemented `validate_safe_local_path()` enforcing canonical path resolution against `settings.ALLOWED_WORKSPACE_ROOTS`. Symlinks pointing outside repository root are pruned during scanning. Traversal sequences (`../`) rejected.
- **Evidence**: `test_path_traversal.py` (4/4 tests pass).

### Finding SEC-02: Server-Side Request Forgery (SSRF) in Git Acquisition
- **Classification**: `CONFIRMED_VULNERABILITY`
- **Status**: **FIXED** (Phase 8.6.3 Run 3 & Phase 8.6.4 Run 4)
- **Severity**: **HIGH (P1)**
- **Remediation**: Restricted schemes to `https`, stripped credentials, enforced port 443, blocked private/loopback/cloud-metadata IPs, added multi-IP DNS resolution checks (if any resolved IP is private, request is rejected), and disabled Git HTTP redirects via `-c http.followRedirects=false`.
- **Evidence**: `test_ssrf.py` (11/11 tests pass).

### Finding SEC-03: Cross-Resource IDOR in Scenario Deletion
- **Classification**: `CONFIRMED_VULNERABILITY`
- **Status**: **FIXED** (Phase 8.6.2 Run 2)
- **Severity**: **HIGH (P1)**
- **Remediation**: Scoped scenario queries to `project_id=repo.project_id`. Cross-repository scenario access returns HTTP 404 (non-disclosure policy).
- **Evidence**: `test_idor.py` & `test_authorization.py`.

### Finding SEC-04: Cross-Resource IDOR in Incident Causal Investigation
- **Classification**: `CONFIRMED_VULNERABILITY`
- **Status**: **FIXED** (Phase 8.6.2 Run 2)
- **Severity**: **HIGH (P1)**
- **Remediation**: Scoped incident lookups to `repository_id=repo.id`. Cross-repository incident access returns HTTP 404.
- **Evidence**: `test_idor.py` & `test_authorization.py`.

### Finding SEC-05: Missing Authentication & Authorization
- **Classification**: `MISSING_CONTROL`
- **Status**: **FIXED** (Phase 8.6.2 Run 2)
- **Severity**: **CRITICAL (P0)**
- **Remediation**: Applied Alembic migration `f1a2b3c4d5e6` creating `users` and `repositories.owner_id`. Implemented PBKDF2 hashing, signed JWT tokens, revocation cache, and `get_authorized_repository` dependency.
- **Evidence**: `test_authentication.py` & `test_authorization.py`.

### Finding SEC-06: Insecure Wildcard CORS Configuration with Credentials
- **Classification**: `SECURITY_WEAKNESS`
- **Status**: **FIXED** (Phase 8.6.4 Run 4)
- **Severity**: **MEDIUM (P2)**
- **Affected Component**: `backend/app/core/config.py` & `backend/main.py`
- **Remediation**:
  1. Configured explicit origin allowlist via `settings.CORS_ALLOWED_ORIGINS` (defaults to local dev origins `["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:8000", "http://127.0.0.1:8000"]`).
  2. Implemented model validator prohibiting wildcard origins `["*"]` when `CORS_ALLOW_CREDENTIALS` is enabled.
  3. Prohibited origin reflection and prefix/subdomain matching tricks (e.g. `evil.com`, `localhost.attacker.com`, `null`).
  4. Preflight `OPTIONS` requests receive appropriate CORS response headers only for explicitly permitted origins.
  5. Added HTTP security headers middleware injecting `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: frame-ancestors 'none'`.
- **Evidence**: `test_security_headers.py` (7/7 tests pass).

---

## 4. Subprocess Execution Inventory

All subprocess invocations in the backend codebase were audited:

| Command | Caller Location | User Inputs | Shell Setting | Environment | Timeout | Filesystem / Network Effect |
|---|---|---|---|---|---|---|
| `git clone --depth 1 -c http.followRedirects=false -c core.symlinks=false -c credential.helper= <url> <workspace>` | `backend/app/services/acquisition/git_provider.py` | Validated HTTPS URL (no credentials, validated DNS) | `shell=False` (argv array) | Sanitized (`_get_sanitized_git_env()` with PATH, HOME, TMPDIR only) | 300 seconds | Clones remote git objects to temporary folder under `data/cloned_repos/` |
| `git log -n 1 --format=%H` | `backend/app/services/acquisition/git_provider.py` | Local workspace path | `shell=False` | Sanitized | 30 seconds | Reads commit hash from local git repo |

**Subprocess Invariant Verification**:
- Zero calls to `os.system`, `os.popen`, `check_output`, or `Popen(shell=True)`.
- No user-supplied string is interpolated into a shell command.
- Package managers (`npm`, `pip`, `setup.py`, `Makefile`, `mvn`, `gradle`) are NEVER executed.

---

## 5. Filesystem Path Inventory & Containment

| Path Category | Path Pattern | Trusted / Untrusted | Boundary Control |
|---|---|---|---|
| **A. Trusted Application Paths** | `/Users/sanjay/DIGITAL TWIN/backend/...` | Trusted | Static code, read-only at runtime |
| **B. Repository Paths** | Local onboarding directory | Untrusted | `validate_safe_local_path()` enforces canonical containment to allowed roots |
| **C. Temporary Ingestion Paths** | `data/cloned_repos/<uuid>/` | Untrusted data container | Managed by `acquire_github_repository()`; purged on acquisition error |
| **D. Generated Output Paths** | In-memory graphs & PostgreSQL tables | Trusted platform storage | Written via ORM transactions |
| **E. User-Controlled Paths** | Target path in `POST /onboard` | Untrusted | Canonical path containment, traversal sequence detection, symlink escape checks |

---

## 6. Resource Limits & Bounded Execution

The platform enforces explicit bounded behavior:

| Dimension | Configured Bound | Behavior on Violation | Structured Status |
|---|---|---|---|
| **Max Global Request Body** | 10 MB | HTTP 413 | `{"detail": "Request body exceeds maximum allowed size (10485760 bytes)"}` |
| **Max Auth Request Body** | 64 KB | HTTP 413 | `{"detail": "Request body exceeds maximum allowed size (65536 bytes)"}` |
| **Login Failed Attempts** | 5 attempts / 300s | HTTP 429 | `{"detail": "Too many failed login attempts. Try again later."}` |
| **Max Total Repo Bytes** | 500 MB (524,288,000 bytes) | Scan truncated | `is_truncated=True`, `truncation_reason=RESOURCE_LIMIT_EXCEEDED` |
| **Max Scan Files** | 50,000 files | Scan truncated | `is_truncated=True`, `truncation_reason=RESOURCE_LIMIT_EXCEEDED` |
| **Max Single File Size** | 50 MB | File skipped | Logged and excluded from AST parsing |
| **Max Directory Depth** | 30 directories | Traversal pruned | Subdirectories pruned |
| **Max Path Length** | 1,024 characters | Path skipped | File excluded |
| **Max Symlinks Count** | 1,000 symlinks | Symlinks skipped | Further symlinks ignored |
| **Max Scan Duration** | 120 seconds | Scan truncated | `is_truncated=True`, `truncation_reason=RESOURCE_LIMIT_EXCEEDED` |
| **Max Proposed Changes** | 100 changes | HTTP 422 | Pydantic validation error |
| **Max Incident Event IDs**| 1,000 event IDs | HTTP 422 | Pydantic validation error |

---

## 7. Open Findings, Accepted Risks & Residual Limitations

### Open Findings:
*None*. All identified findings (SEC-01 through SEC-06) have been mitigated, tested, and verified.

### Accepted Risks:
1. **Container Database Default Password in Dev Compose**: `docker-compose.yml` uses default credentials (`postgres`/`postgres`) for local container orchestration. Acceptable for isolated local development; production deployment requires environment variable injection from a secret manager (e.g. AWS Secrets Manager or HashiCorp Vault).
2. **In-Memory Rate Limiting**: The login rate limiter operates in-memory within the FastAPI application instance. In a distributed multi-replica deployment, rate limiting should be migrated to Redis. Acceptable for single-process architectures.
3. **Local Workspace Allowlist Scope**: In development mode, `ALLOWED_WORKSPACE_ROOTS` defaults to the project root directory. Deployments allowing local onboarding must configure explicit workspace directories.

### Residual Limitations:
1. **Testing Demonstrates Presence of Tested Controls, Not Universal Absence of Bugs**: While 241 regression tests and 58 security tests pass, automated test suites verify specified invariants, not all possible attack surfaces.
2. **No Egress Proxy**: While Git HTTP redirects and DNS rebinding attacks are mitigated at the application and git configuration level, the host environment lacks an isolated network egress proxy. Repositories requiring air-gapped security should run worker tasks inside un-routed containers.

---

## 8. Comprehensive Multi-Phase Production Audit (Phases 1 — 13)

### Executive Summary of Completed Hardening:
- **Phase 1 (Baseline & Architecture)**: Full codebase mapped. All existing uncommitted changes and forensic capabilities preserved without fabrication.
- **Phase 2 (Authentication Lifecycle)**: Implemented password complexity enforcement, single-use expiring password reset token vault, email verification, session cookie issuance (`HttpOnly`, `SameSite=Lax`), and user account deletion.
- **Phase 3 (Authorization & IDOR Closure)**: Audited and hardened all endpoints in `backend/app/api/analysis.py`, `backend/app/api/discovery.py`, and `backend/app/api/graph.py`. Universal enforcement of `resolve_authorized_repo` preventing cross-user and unauthenticated data disclosure (HTTP 404 non-disclosure pattern).
- **Phase 4 (Input Validation & Zip Slip Remediation)**: Archive extraction in `backend/app/api/graph.py` hardened against Zip Slip and Tar Slip attacks using `os.path.commonpath` verification.
- **Phase 5 (Secrets & Configuration)**: Environment configuration sanitized, `.env.example` verified with placeholders only. No raw credentials logged or exposed.
- **Phase 6 (Rate Limiting & Abuse Defense)**: Sliding window rate limiters protecting authentication endpoints (`auth_action_limiter`, 10/min) and expensive analysis operations (`expensive_op_limiter`, 30/min).
- **Phase 7 (Frontend Experience & Reliability)**: Wired real forgot-password API flow, added profile account deletion trigger with multi-step confirmation, established legal navigation links, and removed permanent loading spinners.
- **Phase 8 (Privacy & Legal Governance)**: Delivered production-grade `/privacy` and `/terms` HTML pages disclosing data retention, local AST scanning boundaries, and transactional account deletion.
- **Phase 9 (Database Backup & Disaster Recovery)**: Documented in `docs/DATABASE_BACKUP_AND_DISASTER_RECOVERY.md`. Cloud provider PITR/automated snapshot audit marked `BLOCKED / ACTION REQUIRED` pending infrastructure access.
- **Phase 10 (Security Headers & Observability)**: `X-Request-ID` correlation IDs injected on all requests; `Permissions-Policy`, `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, and `X-Frame-Options: DENY` enforced.
- **Phase 11 (Monitoring & Safe Masking)**: Global exception handler masks internal tracebacks in production while preserving correlation IDs for server-side troubleshooting.
- **Phase 12 (Targeted Verification)**: Verified via `backend/tests/security/test_security_audit_hardening.py` (7/7 PASS), `backend/tests/test_live_workflow_integration.py` (7/7 PASS), `backend/tests/test_discovery_assessment.py` (15/15 PASS), and `backend/tests/test_cross_repository_forensics.py` (6/6 PASS). Total 35 verified passing tests in audit session.
- **Phase 13 (Readiness Decision)**: **`READY_WITH_LIMITATIONS`** (Operational sign-off on Supabase automated cloud backup schedule required for full production readiness).
