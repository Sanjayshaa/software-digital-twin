# Security Threat Model: AI-Powered Software Digital Twin

**Document Version**: 2.0.0  
**Phase**: 8.6.4 — Security Closure & API Hardening Baseline  
**Evaluation Target**: Core Engine, REST API, Database Storage, Ingestion, and UI Interfaces  
**Date**: October 2026  
**Status**: AUDITED & HARDENED BASELINE  
**Hard Security Invariant**: *A repository is untrusted data. It may be cloned, read, parsed, indexed, normalized, modeled, and analyzed. It must NEVER be implicitly executed, built, installed, imported, or sourced.*

---

## 1. System Overview & Architecture Flows

The **AI-Powered Software Digital Twin** is an automated forensic analysis platform that constructs high-fidelity, deterministic structural and behavioral graph models of software codebases to perform pre-deployment change impact analysis, test impact intelligence, blast-radius calculation, architectural drift detection, What-If simulation, and runtime incident causal correlation.

### Core Data Flow Architecture (Hardened)

```
[Untrusted Client / Web Browser / API Consumer]
           │
           │ HTTP / REST (Port 8000)
           ▼
┌────────────────────────────────────────────────────────┐
│ FastAPI Application Boundary                           │
│  - Security Headers Middleware (X-Frame, nosniff, CSP) │
│  - Payload Size Limiter (10MB Global, 64KB Auth)       │
│  - Login Rate Limiter (5 attempts / 300s lockout)      │
│  - Strict CORS Middleware (Explicit origins, no wildcard)│
│  - JWT Bearer Authentication & Principal Context       │
│  - 14 Domain Routers (Auth, Discovery, Graph, etc.)    │
└──────────────────────────┬─────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ▼                               ▼
┌──────────────────────┐       ┌──────────────────────┐
│ Repository Acquisit. │       │ Engine Runtime       │
│  - Strict HTTPS URL  │       │  - Tree-sitter AST   │
│  - DNS Multi-IP Pre- │       │  - Discovery Brain   │
│    Resolution Check  │       │  - Resource Bounds   │
│  - Redirects Banned  │       │  - Graph Projection  │
│  - Sanitized Subproc │       │  - Impact Propagator │
│  - Canonical Paths   │       │  - Test Impact Model │
└──────────┬───────────┘       │  - Risk Engine       │
           │                   │  - Virtual Twin Sim  │
           ▼                   │  - Incident Trace    │
┌──────────────────────┐       └──────────┬───────────┘
│ Host Filesystem      │                  │
│  - data/cloned_repos │                  ▼
│  - Bounded Ingestion │       ┌──────────────────────┐
│  - Canonical Chroot  │       │ PostgreSQL Database  │
└──────────────────────┘       │  - Port 5434         │
                               │  - SQLAlchemy ORM    │
                               │  - User & Repo Auth  │
                               │  - 40 Core Tables    │
                               └──────────────────────┘
```

---

## 2. Asset Classification & Sensitivity Tiers

| Asset Tier | Data Description | Confidentiality | Integrity | Availability | Storage Location | Protection Control |
|---|---|---|---|---|---|---|
| **Tier 1: Secrets & Credentials** | User password hashes, JWT Secret, GitHub PATs, PostgreSQL credentials. | **CRITICAL** | **CRITICAL** | **HIGH** | `users` table (PBKDF2-SHA256), in-memory during clone, `.env`. | Redaction in logs/telemetry, never stored in DB plaintext, stripped from Git subprocess environment. |
| **Tier 2: Proprietary Source Code** | Cloned repositories, AST structures, function signatures, file trees. | **HIGH** | **HIGH** | **HIGH** | `data/cloned_repos/`, `StructuralArtifact` table. | Canonical path confinement, ephemeral workspace cleanup, owner-scoped authorization. |
| **Tier 3: Twin Graph & Forensic Models** | 1,491+ Artifact relationships, dependency closures, test mappings, call graphs. | **MEDIUM** | **CRITICAL** | **HIGH** | `ArtifactRelationship`, `ProjectCapability` tables. | Parameterized ORM queries, immutable snapshot diffing, cross-snapshot isolation. |
| **Tier 4: Telemetry & Incidents** | Ingested runtime stack traces, error payloads, latencies. | **HIGH** | **HIGH** | **MEDIUM** | `RuntimeEvent`, `Incident` tables. | Automated secret sanitizer, bounded payload limits (1000 items, 100KB metadata). |
| **Tier 5: System Operational State** | Milestone progress, analysis run logs, What-If simulation diffs. | **LOW** | **HIGH** | **HIGH** | `AnalysisRun`, `Scenario` tables. | Scoped to owning repository, non-disclosure error handling. |

---

## 3. Audited Trust Boundaries & Controls

All 17 trust boundaries have been evaluated and hardened with automated regression tests:

### Boundary 1: Browser $\rightarrow$ Backend (HTTP API)
- **Trust Level**: **UNTRUSTED**.
- **Controls Implemented**:
  - Request body size limiter middleware (10MB global, 64KB auth endpoints) returning HTTP 413 `PAYLOAD_TOO_LARGE`.
  - Security headers middleware injecting `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin`, `Content-Security-Policy: frame-ancestors 'none'`.
  - CORS middleware configured with explicit allowed origins list; wildcard origin combined with credentials strictly prohibited by invariant.
  - Pydantic models with explicit boundary constraints (e.g. `max_length=100` on proposed changes).

### Boundary 2: Browser $\rightarrow$ Authentication
- **Trust Level**: **UNTRUSTED**.
- **Controls Implemented**:
  - Registration input validation enforcing alphanumeric usernames (`^[a-zA-Z0-9_\-\.]+$`), valid email format, and password length (8-128 chars).
  - PBKDF2-HMAC-SHA256 password hashing.
  - JWT Bearer authentication with HMAC-SHA256 signatures, expiration checks, and in-memory revocation cache for instant logout invalidation.
  - Application-level login rate limiter (5 failed attempts per username locks out for 300 seconds, HTTP 429).

### Boundary 3: User $\rightarrow$ Repository URL (Git Acquisition)
- **Trust Level**: **UNTRUSTED**.
- **Controls Implemented**:
  - Strict HTTPS scheme enforcement, credential stripping, and standard port (443) verification in `is_safe_clone_url`.
  - Multi-IP DNS pre-resolution verification: resolves all IPs for the hostname and rejects the request if ANY resolved address is private, loopback, link-local, or cloud metadata.
  - Git subprocess redirect prevention: Git clone command explicitly passes `-c http.followRedirects=false`, `-c core.symlinks=false`, and `-c credential.helper=`.
  - Sanitized environment variables passed to `git clone` (strips all secrets, database passwords, and PATs).

### Boundary 4: User $\rightarrow$ Uploaded / Local Repository
- **Trust Level**: **UNTRUSTED**.
- **Controls Implemented**:
  - Canonical path resolution using `Path.resolve()` and strict containment check (`candidate.relative_to(root)`) against approved workspace roots (`settings.ALLOWED_WORKSPACE_ROOTS`).
  - Unconditional rejection of root directory, system directories (`/etc`, `/var`, `/usr`, `/System`, etc.), and directory traversal sequences (`../`).
  - Outside-pointing symlinks and symlinked directories are safely pruned during scanning without executing target files.

### Boundary 5: GitHub $\rightarrow$ Backend
- **Trust Level**: **UNTRUSTED**.
- **Controls Implemented**:
  - Subprocess execution strictly uses `shell=False`, argument list, and 300s timeout.
  - Git configuration `-c core.symlinks=false` prevents git from materializing malicious symlinks during clone.
  - Ephemeral clone directory automatically cleaned up on failure via `shutil.rmtree()`.

### Boundary 6: Repository $\rightarrow$ Analyzer Runtime
- **Trust Level**: **UNTRUSTED DATA**.
- **Controls Implemented**:
  - Static AST analysis using Tree-sitter parsers; zero execution of package managers (`npm`, `pip`, `setup.py`, `Makefile`, etc.).
  - Resource limits: `MAX_SINGLE_FILE_SIZE = 50 MB`, `MAX_TOTAL_REPO_BYTES = 500 MB`, `MAX_TOTAL_FILES = 50,000`, `MAX_SCAN_DEPTH = 30`, `MAX_PATH_LENGTH = 1024`, `MAX_SYMLINKS_COUNT = 1000`, `MAX_SCAN_DURATION_SECONDS = 120`.
  - Structured truncation reporting (`is_truncated=True`, `truncation_reason=RESOURCE_LIMIT_EXCEEDED`) rather than silent truncation.

### Boundary 7: User A $\rightarrow$ User B Data & Repositories
- **Trust Level**: **UNTRUSTED / HOSTILE**.
- **Controls Implemented**:
  - Object-level ownership enforcement via `get_authorized_repository` dependency.
  - Cross-user repository, scenario, or incident access deterministically returns HTTP 404 (non-disclosure policy preventing resource ID enumeration).
  - Cross-repository snapshot comparisons in impact or test engines are rejected with HTTP 400.

---

## 4. Threat Analysis via STRIDE (Post-Hardening Status)

| Threat Class | Vector Description | Hardened System State | Severity | Posture |
|---|---|---|---|---|
| **Spoofing** | Callers forging identity or accessing unauthorized repositories. | PBKDF2-SHA256 password hashing, signed JWT Bearer tokens, repository ownership checks. | **CRITICAL (P0)** | **MITIGATED** |
| **Tampering** | Unauthorized mutation of scenarios, incidents, or repository graphs. | Object-level authorization, non-disclosure 404 policy, immutable snapshot diffing. | **HIGH (P1)** | **MITIGATED** |
| **Repudiation** | Mutating actions without user attribution. | Repository records link to authenticated `owner_id`. | **MEDIUM (P2)** | **MITIGATED** |
| **Information Disclosure** | Path traversal, overly permissive CORS, SSRF redirects, or secret leakage. | Canonical containment, explicit origin CORS allowlist, Git redirect blocking, DNS multi-IP check, telemetry secret sanitizer. | **HIGH (P1)** | **MITIGATED** |
| **Denial of Service** | Resource exhaustion via huge repos, nested symlinks, or brute-force login flooding. | Request body limits (10MB/64KB), login rate limiter (5 fails/300s), cumulative scan limits (500MB, 50k files, 120s timeout). | **HIGH (P1)** | **MITIGATED** |
| **Elevation of Privilege** | Path traversal via `/onboard` to inspect host directories. | Canonical path resolution contained to approved roots; system directories blocked. | **CRITICAL (P0)** | **MITIGATED** |
