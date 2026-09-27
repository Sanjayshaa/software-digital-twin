# Runtime Evidence Model & Ingestion Pipeline

## 1. Overview

The **Runtime Evidence** subsystem ingests, normalizes, sanitizes, and correlates operational events (logs, errors, traces, spans, deployments) with structural Digital Twin entities.

```
 Runtime Telemetry (JSON / JSONL / OpenTelemetry)
                       │
                       ▼
             [Credential Sanitizer]  ── (Redacts keys, tokens, auth headers)
                       │
                       ▼
          [Payload Validator & Normalizer]  ── (Pydantic, 100 KB payload bounds)
                       │
                       ▼
           [Entity Correlation Engine]  ── (Matches symbol, service, file, route)
                       │
                       ▼
         PostgreSQL (runtime_events table)  ── (Normalized, Indexed, Immutable)
```

## 2. Event Taxonomy

Normalized runtime events support the following event types:
- `REQUEST`: HTTP/gRPC ingress request
- `TRACE`: Distributed trace root
- `SPAN`: Single span execution segment
- `LOG`: General application log entry
- `ERROR`: Operational or business error
- `EXCEPTION`: Unhandled language exception or panic
- `DEPLOYMENT`: Software deployment or release event
- `STARTUP`: Process or container initialization
- `SHUTDOWN`: Graceful or abrupt termination
- `HEALTH_CHECK`: Liveness / readiness probe
- `DATABASE_EVENT`: Database query, migration, or connection issue
- `EXTERNAL_CALL`: Outbound egress network call
- `CUSTOM`: User-defined domain telemetry

Severities: `DEBUG`, `INFO`, `WARN`, `ERROR`, `CRITICAL`.

## 3. Data Privacy & Credential Redaction

Runtime evidence can contain sensitive data. Before persistence or downstream analysis, the **`RuntimeSanitizer`** recursively inspects all keys and text values:
- **Redacted Keys**: Keys matching patterns such as `*password*`, `*secret*`, `*token*`, `*api_key*`, `*auth*`, `*bearer*`, `*cookie*`, `*private_key*`, `*credential*`.
- **Masking**: Values are replaced with `[REDACTED]`.
- **String Inspection**: Bearer tokens, PEM private keys, and authorization header patterns inside messages or JSON strings are sanitized.
- **Fail-Safe Logging**: Raw unredacted payloads are never output to log files or standard streams during ingestion failures.

## 4. Entity Correlation Engine

Correlation between runtime events and Digital Twin artifacts is completely deterministic:
1. **Direct Qualified Symbol Match (Confidence 0.95)**:
   - When event attributes contain `symbol` or `function_name` matching a `StructuralArtifact.name` or `qualified_name`.
2. **File Path Match (Confidence 0.85)**:
   - When event attributes or message contain file references matching `StructuralArtifact.location`.
3. **Route / API Match (Confidence 0.90)**:
   - When request path matches an `API_ENDPOINT` artifact route.
4. **Service Name Match (Confidence 0.70)**:
   - When `service_name` or `service` matches a component module or service artifact.
5. **Unmatched (Confidence 0.0)**:
   - Preserved with full normalized metadata, queryable by trace_id or time window without speculative hallucination.

## 5. Large-Scale Safety & Bounded Ingestion

- **Payload Limit**: Configurable maximum event payload size (default 100 KB). Over-limit events are rejected safely.
- **Batch Limits**: Ingestion API caps requests to 5,000 events per call.
- **Pagination & Time Filtering**: Query API enforces default limit 50, maximum limit 500, with required indexing on `repository_id`, `snapshot_id`, `timestamp`, `service_name`, and `trace_id`.
- **Object Storage Preparedness**: PostgreSQL stores bounded normalized metadata and indexed query keys. Future large-scale deployments can stream raw multimegabyte payloads to external blob storage.

## 6. API Endpoints

- `POST /repositories/{id}/runtime-events/ingest`: Ingests an array of raw events, returning ingestion and correlation metrics.
- `GET /repositories/{id}/runtime-events`: Paginated query endpoint with filters for `event_type`, `severity`, `service_name`, `trace_id`, `since`, and `until`.
- `GET /repositories/{id}/runtime-events/{event_id}`: Retrieves single normalized event.
- `GET /repositories/{id}/evidence/runtime`: Summarizes runtime evidence statistics and correlation health.
