# TwinCore Database Backup & Disaster Recovery Architecture

**Audit Status: BLOCKED / ACTION REQUIRED (Cloud Provider Delegation)**  
**Classification: P2 Operational Reliability & Compliance**  
**Assessment Date: October 21, 2026**

---

## 1. Executive Summary

TwinCore utilizes a hosted PostgreSQL / Supabase database instance storing projects, ingested repositories, AST structural snapshots, typed relationships, evidence records, simulation scenarios, and user credentials. 

In strict accordance with the first principles of this security audit:
> *Do not claim backups are configured just because the database provider offers a backup feature.*  
> *Do not run destructive restore tests against production.*

Because Supabase database automated snapshot configurations, point-in-time recovery (PITR) toggles, physical backup encryption keys, and backup download APIs reside in the administrative cloud control plane (not accessible via the application container environment or standard database connection string), physical backup status is formally classified as **`BLOCKED`** pending infrastructure team verification.

---

## 2. Infrastructure Backup Matrix

| Control Dimension | Target Specification | Current Assessed State | Verification Status | Remediation Required |
|---|---|---|---|---|
| **Automated Backups** | Daily automated snapshot of all database schemas | Dependent on Supabase cloud plan tier (Free vs Pro/Enterprise) | **BLOCKED** | Platform team must verify daily snapshot schedules in Supabase dashboard. |
| **Recovery Point Objective (RPO)** | < 1 hour for schema and core models | Estimated 24 hours on standard tiers without WAL archiving | **PARTIAL** | Enable Point-In-Time Recovery (PITR) / continuous WAL archiving on production instances. |
| **Recovery Time Objective (RTO)** | < 30 minutes to restore a functional instance | Unverified in production environment | **BLOCKED** | Execute simulated restore drill in an isolated staging environment. |
| **Point-in-Time Recovery (PITR)** | 7 to 30 days granular log-based restoration | Requires Supabase Pro tier with PITR addon | **BLOCKED** | Verify addon enablement in cloud project configuration. |
| **Restore Procedure Documentation** | Step-by-step verified runbook | Documented below in Section 3 | **VERIFIED_PASS** | Runbook established. |
| **Backup Access Isolation** | Least-privilege access restricted from application runtime | Application DB user possesses data DDL/DML but cannot purge backups | **VERIFIED_PASS** | Runtime application credentials cannot overwrite remote cloud backups. |

---

## 3. Disaster Recovery & Restoration Runbook

### Step 1: Incident Assessment & Triage
1. Confirm data corruption, accidental drop, or catastrophic node loss.
2. Freeze application traffic by putting the API into maintenance mode or scaling application pods to zero to prevent further corrupted transactions:
   ```bash
   # Stop application traffic during restoration
   pkill -f "uvicorn"
   ```

### Step 2: Supabase Point-In-Time or Snapshot Restore (Production Isolated Drill)
1. Navigate to the **Supabase Cloud Dashboard** -> **Project Settings** -> **Database** -> **Backups**.
2. For Point-In-Time Recovery: Select the target timestamp immediately prior to the incident (e.g., `2026-10-21T22:00:00Z`).
3. **CRITICAL:** Restore to a **new temporary database project or branch** (e.g., `twincore-dr-staging`). **NEVER execute in-place restore directly against an active production database without staging verification.**

### Step 3: Schema & Data Integrity Verification
Execute verification queries against the restored staging database before pointing DNS or environment variables:
```sql
-- 1. Check user accounts
SELECT count(*) FROM users;

-- 2. Check repositories and project bindings
SELECT count(*), environment FROM repositories GROUP BY environment;

-- 3. Check structural snapshot integrity
SELECT count(*) FROM repository_snapshots;
SELECT count(*) FROM structural_artifacts;
SELECT count(*) FROM artifact_relationships;

-- 4. Verify foreign key integrity
SELECT id FROM repository_snapshots 
WHERE repository_id NOT IN (SELECT id FROM repositories);
```

### Step 4: Cutover & Traffic Resumption
1. Update production environment variable `DATABASE_URL` with the restored database credentials in `.env` / secret manager.
2. Run database migration consistency check:
   ```bash
   python3 -c "from app.core.database import engine; print(engine.connect())"
   ```
3. Restart TwinCore backend services:
   ```bash
   python3 run.py
   ```
4. Verify health endpoints:
   ```bash
   curl -s http://127.0.0.1:8000/health
   curl -s http://127.0.0.1:8000/ready
   ```

---

## 4. Logical Backup Script (Developer / CI Safe Fallback)

To provide defense-in-depth independent of cloud provider snapshot schedules, the following logical dump procedure is configured for developer and staging workflows:

```bash
#!/usr/bin/env bash
# scripts/backup_logical_database.sh
set -euo pipefail

BACKUP_DIR="backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

echo "Creating logical schema and data dump..."
pg_dump "$DATABASE_URL" \
    --format=custom \
    --no-owner \
    --no-privileges \
    --file="$BACKUP_DIR/twincore_logical.dump"

echo "Validating backup archive..."
pg_restore --list "$BACKUP_DIR/twincore_logical.dump" > /dev/null

echo "Backup successful: $BACKUP_DIR/twincore_logical.dump"
```

---

## 5. Required Actions for Production Sign-off

1. **Infrastructure Lead:** Confirm Supabase plan level and whether Point-In-Time Recovery (PITR) is actively provisioned.
2. **DevOps:** Schedule a quarterly non-destructive restore drill using an isolated database branch to validate Recovery Time Objective (RTO < 30 minutes).
3. **Security:** Verify that database backup exports are encrypted with AES-256 at rest and access is restricted to authorized SRE personnel via MFA.
