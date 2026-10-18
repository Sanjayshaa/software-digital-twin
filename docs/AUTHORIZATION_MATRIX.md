# Digital Twin Platform — Resource Authorization Matrix
**Document Version:** 1.1.0 (Phase 8.6.4 Security Closure)  
**Security Classification:** Engineering Specification  
**Enforcement Boundary:** Server-Side FastAPI Dependencies & SQLAlchemy Model Filters

---

## 1. Executive Summary

This document defines the authoritative, server-side resource authorization matrix for the Software Digital Twin platform. 

Security Invariant: **Authentication does NOT equal Authorization.**  
Possession of a valid JWT Bearer token establishes principal identity ($WHO$), but does not grant unrestricted access to multi-tenant or cross-user assets. Every resource lookup must be resolved against an explicit ownership or membership boundary.

---

## 2. Principal Roles & Taxonomy

| Role | Hierarchy Level | Description | Scope of Authority |
|---|---|---|---|
| **Anonymous / Unauthenticated** | Level 0 | Unauthenticated caller without Bearer token or invalid/expired credentials | Public endpoints only (`/health`, `/ready`, `/`, `/app`, `/docs`) |
| **Viewer** | Level 1 | Read-only authenticated team member | Read-only access to authorized repositories, snapshots, graphs, impact analysis |
| **Engineer / Owner** | Level 2 | Standard software engineer or repository creator | Full CRUD over owned repositories, scenarios, simulations, incidents, and telemetry |
| **Admin** | Level 3 | Global Digital Twin administrator | Universal access across all projects, repositories, users, and audit logs |

---

## 3. Authoritative Resource Authorization Matrix

| Resource Class | Action / Operation | HTTP Method & Route Pattern | Anonymous | Repository Owner | Authorized Member / Engineer | Cross-User Caller (Unauthorized) | Administrator |
|---|---|---|---|---|---|---|---|
| **Identity / Auth** | Register Account | `POST /api/v1/auth/register` | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| | Login / Issue Token | `POST /api/v1/auth/login` | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| | Inspect Identity | `GET /api/v1/auth/me` | **DENY (401)** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| | Logout / Revoke Token | `POST /api/v1/auth/logout` | **DENY (401)** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| **Repository** | List Repositories | `GET /repositories` | **ALLOW\*** | **ALLOW (Own)** | **ALLOW (Own)** | **DENY (Filtered)** | **ALLOW (All)** |
| | Onboard Local Directory | `POST /repositories/onboard` | **DENY (401)\*** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| | Ingest Public/GitHub Repo| `POST /repositories/ingest` | **DENY (401)\*** | **ALLOW** | **ALLOW** | **ALLOW** | **ALLOW** |
| | Inspect Repo Details | `GET /repositories/{repo_id}` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Delete Repository | `DELETE /repositories/{repo_id}` | **DENY (401)** | **ALLOW** | **DENY (403)** | **DENY (404)** | **ALLOW** |
| **Snapshots** | List Snapshots | `GET /repositories/{repo_id}/graph/snapshots` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Cross-Snapshot Diff | `GET /repositories/{repo_id}/changes/diff` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Mismatched Foreign Snapshot| Any route with `snapshot_B` | **DENY (400)** | **DENY (400)** | **DENY (400)** | **DENY (400)** | **DENY (400)** |
| **Digital Twin Graph**| Ego-Network / Projection | `GET /repositories/{repo_id}/graph` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Architecture Entities | `GET /repositories/{repo_id}/architecture` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Dependency Graph | `GET /repositories/{repo_id}/dependencies` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| **Change Impact** | Execute Impact Analysis | `POST /repositories/{repo_id}/impact-analysis` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Read Impact History | `GET /repositories/{repo_id}/impact-analysis/{id}` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| **Test Impact** | Execute Test Impact | `POST /repositories/{repo_id}/test-impact` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Read Test Catalog | `GET /repositories/{repo_id}/tests` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| **Risk Intelligence**| Compute Pre-Deploy Risk | `POST /repositories/{repo_id}/risk-analysis` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| **Scenarios (What-If)**| List Scenarios | `GET /repositories/{repo_id}/scenarios` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Inspect Scenario (SEC-03)| `GET /repositories/{repo_id}/scenarios/{id}` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Execute Simulation | `POST /repositories/{repo_id}/scenarios/{id}/analyze` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Delete Scenario (SEC-03)| `DELETE /repositories/{repo_id}/scenarios/{id}` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Foreign Scenario Delete | `DELETE /repositories/{repo_A}/scenarios/{scen_B}` | **DENY (404)** | **DENY (404)** | **DENY (404)** | **DENY (404)** | **DENY (404)** |
| **Incidents** | List Incidents | `GET /repositories/{repo_id}/incidents` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Inspect Incident (SEC-04)| `GET /repositories/{repo_id}/incidents/{id}` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Causal Investigation | `POST /repositories/{repo_id}/incidents/{id}/investigate` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Foreign Incident Access | `GET /repositories/{repo_A}/incidents/{inc_B}` | **DENY (404)** | **DENY (404)** | **DENY (404)** | **DENY (404)** | **DENY (404)** |
| **Runtime Events** | Query Telemetry | `GET /repositories/{repo_id}/runtime-events` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |
| | Ingest Telemetry | `POST /repositories/{repo_id}/runtime-events/ingest` | **DENY (401)** | **ALLOW** | **ALLOW** | **DENY (404)** | **ALLOW** |

*\*Note: Legacy/development unassigned repositories (`owner_id = NULL`) allow transparent reading during dev workspace initialization to maintain backward compatibility.*

---

## 4. Non-Disclosure Policy (404 vs 403)

In accordance with OWASP API Security Top 10 recommendations:
1. **401 Unauthorized**: Returned when authentication credentials are completely missing, expired, revoked, or have an invalid cryptographic signature.
2. **404 Not Found**: Returned when an authenticated principal attempts to access or mutate a repository, snapshot, scenario, or incident belonging to another user/tenant.  
   *Security Rationale:* Returning `403 Forbidden` confirms the existence of the victim's resource ID (enabling enumeration and reconnaissance). Returning `404 Not Found` treats the resource as non-existent to unauthorized callers.
3. **400 Bad Request**: Returned when foreign cross-repository parameters are submitted within the same request (e.g. attempting to run impact analysis for Repository A with Target Snapshot B).

---

## 5. Implementation Evidence & Regression Coverage

The matrix is verified by automated regression test suites across 58 security tests:
- `backend/tests/security/test_authentication.py` (Domain A & B: Login rate limiting, tokens, registration)
- `backend/tests/security/test_authorization.py` (Domain C, E, F: Cross-user repository ownership isolation)
- `backend/tests/security/test_idor.py` (Domain D & G: SEC-03 scenario and SEC-04 incident isolation)
- `backend/tests/security/test_cross_snapshot_isolation.py` (Domain F & AB)
- `backend/tests/security/test_request_limits.py` (Domain H & N: Body size limits and field bounds)
- `backend/tests/security/test_security_headers.py` (Domain Q & R: Strict CORS allowlist and security headers)
- `backend/tests/security/test_failure_atomicity.py` (Failure cleanup and transaction rollbacks)
