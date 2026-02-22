# Program Risk Early-Warning & Readiness Gate (PREWG)

**Status:** Design / placeholder. Implement when program-level visibility is required.

## Purpose

Turn HB signals (drift, asserts, trends) into **program-level readiness answers**: Ready / At Risk / Not Ready, with executive-safe reasons. Fits questions like “Are we on track?” and “Where is risk accumulating?”

## Gate definitions (placeholder)

| Gate | Typical criteria (to be configured) |
|------|-------------------------------------|
| **Pre-CDR** | Drift trend stable; no unresolved FAIL; baseline approved; assertion coverage above threshold. |
| **Pre-Flight** | Same as Pre-CDR plus: no critical metric drift; evidence pack available for last FAIL (if any). |
| **Pre-Delivery** | All above; regression confidence above threshold; no open baseline requests. |
| **Regression Exit** | Trend health, assertion stability, baseline volatility within limits. |

## Planned capabilities

- **Leading risk indicators:** Variance growth, margin erosion, config sensitivity (derived from drift + asserts).
- **Schedule protection metrics:** Regression confidence, stability half-life, rework probability.
- **Program rollups:** Risk heatmap, drift concentration, top 5 drivers across runs.

## Implementation (TODO)

- Add **gate definitions** in config (e.g. `config/readiness_gates.yaml`) with criteria and thresholds.
- Add **evaluation step** that consumes drift reports, assert results, and trend data and outputs Ready / At Risk / Not Ready + reasons.
- Expose via CLI (e.g. `hb readiness gate --gate Pre-CDR`) and/or report section.
- Optionally feed into WaveOS or dashboards.

## Reference

- `mvp/production-readiness.md` (PREWG add-on section).
