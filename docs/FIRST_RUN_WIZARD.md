# First-Run Wizard — UX Design

**Purpose:** “A new engineer can install, run a sample, and interpret results in 30 minutes.” First-run wizard in UI: choose workspace, set DB paths, import registry, set baseline policy; guided baseline creation and approval; clear error messaging.

**References:** `bin/hb ui`, local UI flow, `docs/PROGRAM_ONBOARDING.md`.

---

## 1. First-run wizard (design)

**Steps (in order):**

1. **Welcome** — “Set up Harmony Bridge in a few steps. All data stays on this machine.”
2. **Workspace** — Choose workspace directory (default `~/.harmony_bridge`). Create if missing; set `HB_REPORTS_DIR`, `HB_DB_PATH` relative or absolute.
3. **DB path** — Confirm or set `HB_DB_PATH` (e.g. `{workspace}/runs.db`). If DB doesn’t exist, offer “Initialize new registry.”
4. **Metric registry** — Upload or select path to `metric_registry.yaml`; validate and show “N metrics loaded.” Option: “Use default registry” for demo.
5. **Baseline policy** — Upload or select `baseline_policy.yaml`; or “Use defaults (no approval required).”
6. **Sample run** — “Run a sample comparison?” → Run `hb run` on bundled sample (no_drift_pass + single_metric_drift); show report link and status (PASS / PASS_WITH_DRIFT).
7. **Done** — “You’re ready. Go to Compare to analyze your own data.”

**Persistence:** Save workspace and paths in workspace config (e.g. `{workspace}/config.json`) so next launch skips wizard or offers “Change settings.”

---

## 2. Guided baseline creation and approval (UI)

- **Create baseline:** “Set baseline” flow: select a run from list (or upload run artifact), choose tag (e.g. golden), confirm. If governance enabled: “Request baseline” → enters request; “Approve” (if role allows) with reason.
- **Approval UI:** List pending requests; Approve / Reject with reason code; show approval history.

---

## 3. Support bundle and “send to me” (local)

- **Support bundle:** Already in UI: “Export Support Bundle” → writes zip to user-selected path (report + logs + manifest; no raw inputs). No upload; “send to me” = save to local path or attach to ticket in customer’s own process.
- **Clarify in UI:** “Bundle is saved locally. Attach it to your support ticket or email from your machine.”

---

## 4. Clear error messaging for schema issues

- **Single fix message:** When ingest or schema validation fails, show one clear message: e.g. “Missing required column ‘Metric’. Add a column named ‘Metric’ to your CSV or use a schema that maps your columns.” Point to PROGRAM_ONBOARDING or schema doc.
- **Implementation:** In ingest adapters and validation, raise or return a single, user-facing string (e.g. `HBError` with message); UI displays it in an error banner with “How to fix” link.

---

## 5. Definition of done

- A new engineer can install, run a sample (wizard or CLI), and interpret results in 30 minutes.
- First-run wizard: at least design doc (this file) and optionally stub routes in UI.
- Guided baseline create/approve in UI (or clear CLI instructions in onboarding).
- Support bundle export (existing) with “local only” messaging.
- Schema/validation errors show a single fix message and link to doc.
