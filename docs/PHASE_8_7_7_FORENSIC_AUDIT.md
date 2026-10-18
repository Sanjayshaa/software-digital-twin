# Phase 8.7.7 — Forensic Audit Report: Zero-Trust Workspace Isolation & Real Browser Proof

**Audit Date**: October 4, 2026  
**Auditor**: Antigravity Automated Verification & Security Subsystem  
**Classification**: Engineering Forensic Audit (Step 1 — No Code Changes)  
**Target Repository**: Software Digital Twin (`TwinCore`)  

---

## 1. Executive Summary

This forensic audit investigates the root causes of repository metadata leaks, stale workspace rendering, and boot-time layout shifts observed in previous evaluations. Specifically, it addresses why repositories such as:
- `CampusBridge`
- `Sanjayshaa_Lab_record_system_485aee8a`
- `lab-record-management-system`
- `Sanjayshaa_internship-portal`
- `LAB-RECORD-SYSTEM`
- `octocat_Hello-World`
- `validation-repo-ab-test`
- `real_validation_repo`
- `SolarisCalculator`

were previously visible to unauthenticated guests or cross-tenant sessions.

The audit examined every stage of the backend authorization and ingestion lifecycle, the frontend boot and state-machine transitions, persisted client storage, and fallback mechanisms across all 7 routers and UI components.

---

## 2. Inventory & Forensic Source of Visible Repositories

Every repository name observed in the browser originates from one of two underlying storage mechanisms in this development environment:

### A. PostgreSQL Database (`digital_twin_postgres` on Port 5434)
The primary persistence store for the digital twin is PostgreSQL (`digitaltwin_db`). In the `repositories` table, historical records were created during previous development phases (Phases 1 through 8.7):
1. **`CampusBridge`** (ID: `1dafa8df-4083-47b4-9021-d8a47a897aa8` / `7466fa85-9856-429a-8e2b-280fcb58c5ef`): Created during initial validation runs.
2. **`Sanjayshaa_Lab_record_system_485aee8a`** & **`Sanjayshaa_LAB-RECORD-SYSTEM_994af338`**: Cloned and synthesized from GitHub during Part 10 verification.
3. **`Sanjayshaa_internship-portal_e11c8415`**: Cloned and synthesized from GitHub during integration testing.
4. **`octocat_Hello-World`**: Created during public GitHub onboarding test scripts.
5. **`validation-repo-ab-test`**: Created during A/B impact testing in `tests/test_impact.py`.
6. **`SolarisCalculator`**: Created during Phase 8.7 local folder onboarding verification targeting `/Users/sanjay/DIGITAL TWIN /real_validation_repo`.

**Forensic Finding on Database Records**:  
Prior to Phase 8.7.6, the `repositories` table schema did not include an `owner_id` column. When migration `f1a2b3c4d5e6_authentication_and_user_ownership.py` added `owner_id` (nullable foreign key to `users.id`), all existing repositories were migrated with `owner_id = NULL`. Because early router code did not filter by `owner_id`, every unowned repository was returned by `GET /repositories` to every visitor.

### B. Filesystem Workspaces (`data/cloned_repos/`)
Cloned git repositories reside under `data/cloned_repos/`:
- `data/cloned_repos/Sanjayshaa_campusbridge_a7074787/`
- `data/cloned_repos/Sanjayshaa_Lab_record_system_485aee8a/`
- `data/cloned_repos/Sanjayshaa_LAB-RECORD-SYSTEM_994af338/`
- `data/cloned_repos/Sanjayshaa_internship-portal_e11c8415/`

These filesystem directories serve as the source tree parsed by Tree-sitter during structural twin synthesis.

---

## 3. Backend Lifecycle & Object-Level Authorization Audit

### 3.1 Authentication & Principal Resolution (`backend/app/core/auth.py`)
- **Tokens**: Issues signed HMAC-SHA256 JWT access tokens containing claims: `sub` (User ID), `username`, `email`, `role`, and `exp`.
- **Dependency**: `get_current_user_optional(credentials)` extracts and validates the Bearer token. If no token is provided, it returns `None` (representing an unauthenticated guest). If an invalid or expired token is provided, it raises `401 Unauthorized`.
- **Enforcement**: `require_authenticated_user` rejects unauthenticated callers with `401 Unauthorized`.

### 3.2 Repository Listing (`GET /repositories` in `backend/app/api/graph.py`)
- **Guest Handling**: 
  ```python
  if not principal:
      return []
  ```
  Returns `[]` (empty list) for guests.
- **Authenticated Handling**:
  ```python
  if not principal.is_admin:
      query = query.filter(Repository.owner_id == principal.user_id)
  ```
  Filters by `owner_id == principal.user_id`.
- **VULNERABILITY IDENTIFIED (SEC-VULN-01)**:  
  Line 69 in `graph.py`:
  ```python
  if environment:
      target_env = environment.upper()
      if target_env in ["USER", "TEST", "FIXTURE"]:
          query = query.filter(Repository.environment == target_env)
  ```
  When the client does *not* provide an `environment` query parameter, `environment` defaults to `None`. In that scenario, `query.filter(Repository.environment == target_env)` is bypassed entirely. As a result, test repositories created in pytest runs with `environment = "TEST"` or `"FIXTURE"` that happen to match an owner ID are not excluded from production user queries.

### 3.3 Authoritative Repository Resolution (`resolve_authorized_repo` in `backend/app/core/auth.py`)
- **Resolution**:
  ```python
  repo = db.query(Repository).filter(or_(
      Repository.id == repository_id,
      Repository.name == repository_id,
      Repository.local_path == repository_id,
  )).first()
  ```
- **VULNERABILITY IDENTIFIED (SEC-VULN-02)**:  
  Line 364 in `auth.py`:
  ```python
  # System fixtures without an owner are accessible for internal test harnesses
  if repo.owner_id is None and repo.environment in ["TEST", "FIXTURE"]:
      return repo
  ```
  If a repository exists in the database with `owner_id IS NULL` and `environment == "TEST"` (which is how `Repository.__init__` automatically marks all repositories when created during pytest), an unauthenticated guest sending a direct request (e.g. `GET /repositories/{id}/overview` or `GET /repositories/{id}/graph`) was granted access because `resolve_authorized_repo` returned `repo` instead of `None`. In a production SaaS environment, test fixtures must never be exposed over the public HTTP API.

### 3.4 Ingestion & Creation Vulnerabilities (`backend/app/api/graph.py`)
- **VULNERABILITY IDENTIFIED (SEC-VULN-03 - Cross-Tenant Collision & Hijacking)**:  
  In `connect_github_repository` (Line 369):
  ```python
  repo = db.query(Repository).filter_by(remote_url=acquisition.remote_url).first()
  if repo:
      ...
      if principal and repo.owner_id is None:
          repo.owner_id = principal.user_id
  ```
  The lookup keys *only* on `remote_url` globally. If User A connects `https://github.com/org/repo`, and later User B connects the same public URL, User B is given a reference to User A's repository record or steals ownership if `owner_id` was `None`.  
  **Required Invariant**: Each user must receive their own isolated `Repository` entity (`filter_by(remote_url=..., owner_id=principal.user_id)`).

- **VULNERABILITY IDENTIFIED (SEC-VULN-04 - Unauthenticated Persistent Repositories)**:  
  In lines 270, 385, and 514:
  ```python
  owner_id=principal.user_id if principal else None
  ```
  If an unauthenticated guest connects a repository, it creates a persistent repository with `owner_id = None`. Because guests receive `[]` from `/repositories`, this repository becomes orphaned or accessible via SEC-VULN-02.  
  **Required Invariant**: Repository creation must strictly require an authenticated principal (`owner_id = principal.user_id`), or require the guest to sign in before repository creation.

---

## 4. Frontend Lifecycle & State Machine Forensic Audit

### 4.1 State Machine Lifecycle (`backend/app/static/twin.js`)
The application executes the following deterministic lifecycle on `DOMContentLoaded`:
1. `setAppState('BOOT')` → Adds `booting` class to `document.body`.
2. `checkAuthentication()` → Inspects `localStorage.getItem('jwt_token')` and calls `/api/v1/auth/me`.
3. If guest (`!state.user`):
   - Removes `selected_repo_id` and `selected_snapshot_id` from `localStorage`.
   - Fetches `GET /repositories` (returns `[]`).
   - Transitions to `state-signed-out`.
   - Sets hero title: *"Welcome to Software Digital Twin"*.
   - Hides `#no-repo-existing-codebases-section`.
   - Hides top selectors, search bar, sidebar, and ingest/incident buttons.
4. If authenticated (`state.user`):
   - Fetches `GET /repositories` (returns User's owned repos).
   - If user has no repositories: transitions to `state-signed-in-no-repo` with *"Welcome back, [Username]"*.
   - If user has repositories and valid `selected_repo_id`: validates ownership, transitions to `state-workspace-active`, loads snapshots, and renders the overview.
   - If user has repositories but no selected repository: transitions to `state-signed-in-no-repo`, renders *"Your Codebases"* list with explicit `[ Open Workspace ]` buttons.
5. `finishBoot()`:
   - Awaits `document.fonts.ready` (with a 400ms timeout) to guarantee Material Symbols font ligatures are decoded before display.
   - Removes `booting` class from `document.body`.
   - `#boot-screen` fades out with zero layout shift.

### 4.2 Audit of Fallback Behaviors
- **`repositories[0]` / `repos[0]`**: Not present in `twin.js`. Repositories are never silently auto-selected without explicit user action or validated `localStorage` matching.
- **`snapshots[0]` fallback**:
  Found in three non-critical simulation/testing handlers:
  - Line 3189: `(state.snapshots[0] ? state.snapshots[0].id : null)` in `loadTestsView`.
  - Line 5841: `state.snapshots[0]?.id` in `loadSimulationView`.
  - Line 5928: `state.snapshots[0]?.id` in `runSimulationAction`.
  **Finding**: In the primary header selector, snapshots are never auto-selected without explicit user intent (`state.currentSnapshotId = null` by default).

### 4.3 Persisted Client Storage (`localStorage`)
The client stores exactly three keys in `localStorage`:
1. `jwt_token`: Bearer authentication token. Cleared upon logout or HTTP 401.
2. `selected_repo_id`: ID of the currently selected repository. Validated against `GET /repositories` on boot; cleared if invalid or unauthorized.
3. `selected_snapshot_id`: ID of the currently active snapshot. Validated against `/snapshots`; cleared if invalid.

**VULNERABILITY IDENTIFIED (SEC-VULN-05 - Name Collision in Storage Validation)**:  
In `startApplicationStateMachine` (Line 1362):
```javascript
const matched = validRepos.find(r => r.id === targetRepo || r.name === targetRepo);
```
Matching by `name` creates a cross-tenant risk if User A and User B have a repository with the same name. Validation must match strictly on `r.id === targetRepo`.

---

## 5. Summary of Identified Vulnerabilities

| Vulnerability ID | Component | Description | Impact | Severity |
| :--- | :--- | :--- | :--- | :--- |
| **SEC-VULN-01** | `graph.py` | `GET /repositories` does not default to `environment == "USER"`. | Test/Fixture repositories could leak into authenticated user lists if created with user's ID. | **Medium** |
| **SEC-VULN-02** | `auth.py` | `resolve_authorized_repo` permits unowned `TEST`/`FIXTURE` repositories to be read by unauthenticated guests. | Guests querying historical test repository IDs can view their graph and snapshots. | **High** |
| **SEC-VULN-03** | `graph.py` | `connect_github_repository` queries by `remote_url` alone without scoping by `owner_id`. | If two users clone the same public repo, they share the same database entity. | **High** |
| **SEC-VULN-04** | `graph.py` | Acquisition endpoints allow unauthenticated guests to create unowned (`owner_id = None`) repositories. | Creates orphaned repositories that pollute the database. | **Medium** |
| **SEC-VULN-05** | `twin.js` | Persisted workspace validation matches by `r.name === targetRepo` instead of strictly `r.id === targetRepo`. | Could cause incorrect workspace binding if names collide across users. | **Low** |
| **SEC-VULN-06** | `twin.js` | Fallback expressions `snapshots[0]` exist in simulation handlers. | Could lead to unintended default snapshot execution if no snapshot is chosen. | **Low** |

---

## 6. Zero-Trust Architecture & Remediation Invariants for Phase 8.7.7

### Invariant 1: Absolute Guest Isolation
- `GET /repositories` for unauthenticated callers returns `[]` (HTTP 200) with zero metadata.
- All repository-scoped endpoints (`/graph`, `/snapshots`, `/overview`, `/components`, `/impact-analysis`, `/test-impact`, `/risk-analysis`, `/incidents`, `/runtime-events`, `/processes`, `/simulate`) strictly return `404 Not Found` for unauthenticated callers.
- Unowned repositories with `owner_id IS NULL` are inaccessible to guests over the public HTTP API, even if `environment` is `TEST` or `FIXTURE`. Internal test fixtures are accessible only within pytest test execution via explicit test harnesses.

### Invariant 2: Multi-Tenant Object-Level RBAC
- Authenticated User A can query only repositories where `repo.owner_id == User A.id` and `repo.environment == "USER"`.
- Authenticated User B requesting User A's repository receives `404 Not Found` across all endpoints (non-disclosure policy).
- GitHub/Local/ZIP repository creation creates an isolated entity scoped to `owner_id = principal.user_id`.

### Invariant 3: Hard Refresh Zero-Flash Guarantee
- `<body class="booting state-signed-out ...">` starts with `#boot-screen` visible and `#app-shell` hidden (`visibility: hidden !important;`).
- Shell is revealed only after font decoding (`document.fonts.ready`), auth check, and repository validation complete.
- Disconnected guests see zero selectors, zero search bar, zero sidebar, and zero repository lists.

---
*End of Forensic Audit Report.*
