# Product Boundary — Modular Offerings for Selling

**Purpose:** Split the repo into clear **product layers** so you can sell and deploy distinct offerings: HB Core Engine, HB Runtime (real-time), HB Ops (UI + evidence), and HB DoD Package (secure + compliant). This makes the product sellable and contractable.

**References:** `docs/REPO_SUMMARY.md`, `docs/PRODUCTION_HB_DOD_ROADMAP.md`, `docs/COMPLIANCE_MATRIX.md`.

---

## 1. Product layers (conceptual)

| Layer | Name | Contents | Buyer / use case |
|-------|------|----------|-------------------|
| **L1** | **HB Core Engine** | Ingest, compare, metric registry, baseline selection, drift/invariant evaluation, report generation (HTML/JSON/PDF). No daemon, no live telemetry, no actions. | Labs that only need file-based post-test analysis; OEMs that embed compare logic. |
| **L2** | **HB Runtime** | Core + streaming evaluator, daemon, live ingest (MQTT/Kafka/syslog), actions, operational modes, real-time guarantees (see REALTIME_GUARANTEES). | Integration and test benches; continuous monitoring. |
| **L3** | **HB Ops** | Runtime + local UI, watch folder, feedback hub, support bundle, runbooks, admin guide. | Operators and program teams; “turnkey” single-node deployment. |
| **L4** | **HB DoD Package** | Ops + compliance (NIST/RMF mapping), evidence signing, custody, RBAC, KMS, V&V package, secure/offline install, HIL testbed. | DoD primes and government labs; ATO and certification. |

---

## 2. Mapping repo to layers

| Repo area | L1 Core | L2 Runtime | L3 Ops | L4 DoD |
|-----------|--------|------------|--------|--------|
| `hb/engine.py`, compare, report, registry, baseline | ✓ | ✓ | ✓ | ✓ |
| `hb/ingest/` (file sources only) | ✓ | — | — | — |
| `hb/ingest/` (MQTT, Kafka, syslog, file-replay) | — | ✓ | ✓ | ✓ |
| `hb/streaming/`, `hb runtime` | — | ✓ | ✓ | ✓ |
| `hb/daemon.py` | — | ✓ | ✓ | ✓ |
| `hb/actions/` | — | ✓ | ✓ | ✓ |
| `hb/modes.py` | — | ✓ | ✓ | ✓ |
| `hb/local_ui.py`, `hb ui`, watch, feedback | — | — | ✓ | ✓ |
| `hb/support.py`, runbooks, admin guide | — | — | ✓ | ✓ |
| Evidence signing, custody, RBAC, KMS, audit chain | — | — | ✓ | ✓ |
| COMPLIANCE_MATRIX, V&V package, secure install, HIL | — | — | — | ✓ |

---

## 3. Packaging options

- **Single kit (today):** One repo/build produces a kit that can run in “core-only” mode (no daemon, file-only) or full mode. Feature flags or subcommands can hide Runtime/Ops/DoD features for a “Core only” SKU.
- **Tiered kits (future):** Build and ship separate artifacts: e.g. `hb-core-*.zip`, `hb-runtime-*.zip`, `hb-ops-*.zip`, `hb-dod-*.zip`, each with appropriate deps and docs. License or entitlement can restrict which layer is enabled.
- **DoD package:** A superset kit + compliance binder (COMPLIANCE_MATRIX, V&V Test Plan/Procedures/Acceptance Criteria, KEY_MANAGEMENT, RUNBOOK, ADMIN_GUIDE) and optional secure/offline install bundle.

---

## 4. Licensing and entitlement

- **Core:** File-based ingest and compare; baseline and report. Lowest cost / eval.
- **Runtime:** Adds live telemetry, daemon, streaming, actions. Mid tier.
- **Ops:** Adds UI, watch, feedback, support tooling. Full operational tier.
- **DoD:** Adds compliance docs, V&V package, secure install, HIL. Premium / government.

Entitlement can be enforced by: (1) license file that lists enabled layers, (2) build-time exclusion (separate binaries), or (3) config flag that disables features when not licensed. Document in COMMERCIAL_RELEASE_CHECKLIST or DISTRIBUTOR_CHECKLIST.

---

## 5. Summary

- **HB Core Engine** = compare + file ingest + report + baseline (no live, no actions).
- **HB Runtime** = Core + streaming + daemon + live ingest + actions + modes.
- **HB Ops** = Runtime + UI + watch + feedback + support + runbooks.
- **HB DoD Package** = Ops + compliance matrix + V&V + secure install + HIL.

Splitting the repo into these layers (conceptually or in packaging) makes it clear what is being sold and what each customer gets. Implementation can remain one codebase with feature flags or separate build targets per layer.
