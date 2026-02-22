# Acceptance Test Plan and Readiness Gates

Map acceptance scenarios to production readiness gates so we can trace “what must pass” before release.

## Readiness gates (PREWG)

| Gate | Purpose | HB commands / checks |
|------|--------|----------------------|
| **Pre-CDR** | Ready for critical design review | `hb readiness gate --gate Pre-CDR`; baseline set with quality gate; registry validated |
| **Pre-Flight** | Ready for flight / deployment | `hb readiness gate --gate Pre-Flight`; analyze run with PASS or PASS_WITH_DRIFT; evidence pack on FAIL |
| **Regression-Exit** | Regression suite passed | CI: pytest; benchmark_compare; CMAPSS regression when data available |
| **Release** | Safe to tag release | SBOM generate + verify; no critical vulns (pip-audit); version bumped |

## Trace matrix: scenario → gate

| Scenario | Pre-CDR | Pre-Flight | Regression-Exit | Release |
|----------|---------|------------|-----------------|---------|
| Metric registry loads and validates | ✓ | ✓ | ✓ | ✓ |
| Baseline set enforces quality gate | ✓ | ✓ | — | — |
| Analyze produces status (PASS / PASS_WITH_DRIFT / FAIL) | ✓ | ✓ | ✓ | — |
| Report includes correlation_id and baseline_confidence | — | ✓ | — | — |
| Replay reproduces same decision from slice + config | — | ✓ | ✓ | — |
| Determinism: same input → same compare result | — | — | ✓ | — |
| Golden compare vector matches | — | — | ✓ | ✓ |
| Fault injection (value_corruption, stuck_at, etc.) runs | — | — | ✓ | — |
| SBOM generated and verified | — | — | — | ✓ |
| No plaintext secrets in config (when HB_REJECT_PLAINTEXT_SECRETS=1) | ✓ | ✓ | ✓ | ✓ |

## Running acceptance checks

- **Pre-Flight gate in CI:** See `docs/PRE_FLIGHT_GATE.md`. Run `hb analyze` (or `hb run`) and exit non-zero when status is FAIL; publish report artifact.
- **Determinism:** `pytest tests/test_determinism.py`.
- **Golden compare:** `pytest tests/test_golden_compare.py`.
- **SBOM:** `python tools/generate_sbom.py --out SBOM.md --from-installed` then `python tools/verify_sbom.py SBOM.md`.
