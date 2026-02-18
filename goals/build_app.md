# build_app.md - Context Engineering Template (5+2)

Status: draft
Owner:
Date:
Project:

## 0. Executive Summary
- One-liner:
- Why now:
- Target release date:

## 1) Architect (Bauplan)

### 1.1 Problem
- What exact problem are we solving?
- Current pain/time/cost:
- Why existing solutions are insufficient:

### 1.2 User
- Primary user persona:
- Secondary persona (optional):
- User jobs-to-be-done:

### 1.3 Success (Definition of Done)
- DoD metric 1:
- DoD metric 2:
- Non-functional acceptance (latency, uptime, etc.):
- Demo scenario that must work end-to-end:

### 1.4 Constraints
- Time:
- Budget:
- Compliance/Security:
- Runtime/platform limits:

### 1.5 Non-goals
- Explicitly out of scope:

Architect gate (must be green):
- [ ] Problem is concrete and measurable.
- [ ] User + DoD are explicit.
- [ ] Constraints/non-goals are written.

Architect artifacts:
- PRD/Goal summary
- DoD checklist

---

## 2) Trace (Technische Blaupause)

### 2.1 Data schema
- Main entities:
- Key fields:
- Ownership/lifecycle of each entity:

### 2.2 Integrations map
- External system 1:
  - Endpoint(s):
  - Auth method:
  - Rate limits:
- External system 2:
  - Endpoint(s):
  - Auth method:
  - Rate limits:

### 2.3 Tech stack
- Frontend:
- Backend:
- Storage:
- Queue/Worker (if any):
- Hosting/Deploy:

### 2.4 Planned data flow
1. Input enters via:
2. Validation happens in:
3. Processing happens in:
4. Persistence happens in:
5. Output delivered via:

Trace gate (must be green):
- [ ] Data model documented.
- [ ] Integrations/auth clear.
- [ ] Stack fixed (no tool roulette).

Trace artifacts:
- Architecture note
- Data flow diagram (simple text/mermaid is enough)

---

## 3) Link (Verbindungspruefung)

### 3.1 Integration checks
- API reachability check result:
- Auth check result:
- Minimal request/response smoke result:

### 3.2 Failure notes
- Known unstable endpoints:
- Required retries/timeouts:

Link gate (must be green):
- [ ] Every required endpoint responds.
- [ ] Auth works with intended scopes.
- [ ] At least one successful roundtrip per integration.

Link artifacts:
- Link test log (commands + responses)

---

## 4) Assemble (Schichtweiser Zusammenbau)

### 4.1 Layer plan
1. Foundation layer (storage/connectivity):
2. Logic layer (domain/backend):
3. Interface layer (API/UI):

### 4.2 Build steps
- Step A:
  - Deliverable:
  - Test:
- Step B:
  - Deliverable:
  - Test:
- Step C:
  - Deliverable:
  - Test:

### 4.3 Change isolation
- Files/services touched per step:
- Rollback approach:

Assemble gate (must be green):
- [ ] Built in layers, not one-shot.
- [ ] Every layer has a verification step.
- [ ] Regressions are tracked per step.

Assemble artifacts:
- Incremental commits
- Verification outputs per layer

---

## 5) Stress Test (Belastungsprobe)

### 5.1 Functional tests
- Happy path tests:
- Expected outcomes:

### 5.2 Edge cases
- Empty input:
- Invalid input:
- Timeout/downstream failure:
- Concurrent requests:

### 5.3 Error handling
- User-visible error behavior:
- Logging behavior:
- Retry/fallback policy:

Stress Test gate (must be green):
- [ ] Core user flow passes.
- [ ] Critical edge cases handled.
- [ ] Errors are controlled and observable.

Stress Test artifacts:
- Test matrix
- Failure examples with expected handling

---

## 6) Validate (Production gate)

### 6.1 Security/correctness
- AuthN/AuthZ checks:
- Data isolation checks:
- Secret handling checks:
- Input/output validation checks:

### 6.2 Compliance/readiness
- Privacy requirements:
- Auditability requirements:

Validate gate (must be green):
- [ ] Security checklist complete.
- [ ] No blocker-level correctness issue open.

Validate artifacts:
- Security checklist
- Sign-off notes

---

## 7) Monitor (Production operation)

### 7.1 Telemetry
- Core metrics:
- SLO/SLA targets:
- Alert thresholds:

### 7.2 Logging/tracing
- Structured logs:
- Trace IDs:
- Retention policy:

### 7.3 Product signals
- Success funnel:
- Drop-off points:
- Cost per run/request:

Monitor gate (must be green):
- [ ] Metrics + alerts live.
- [ ] Logs are useful for incident debugging.
- [ ] Product-level signals collected.

Monitor artifacts:
- Dashboard links
- Alert runbook

---

## Final Go/No-Go
- Decision:
- Open risks:
- Owner for unresolved items:
- Planned revisit date:

## Notes
- Deterministic outcome is a direction, not an absolute guarantee.
- If a phase is red, stop and return to the last green phase.
