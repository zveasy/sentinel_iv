# Decision Record Schema Evolution

## Version compatibility policy

- **v1.0** (current): `schema_version` optional for backward compatibility; `decision_confidence` optional.
- **Forward compatibility**: Consumers must ignore unknown top-level keys. New optional fields may be added in minor versions.
- **Backward compatibility**: v1 consumers can read v1.0 records; records without `schema_version` are treated as v1.0.

## Schema evolution rules

1. **No removal** of existing fields without a major version bump.
2. **New optional fields** allowed in minor versions (e.g. 1.1).
3. **Required new fields** only in a new major version with migration path (e.g. v2 with defaulting or migration script).

## Migration

- **v1 → v2** (future): If v2 adds required fields, provide a migration script that:
  - Reads v1 `decision_record.json` (or evidence pack manifest).
  - Writes v2 record with defaults for new required fields.
- Migration scripts live under `tools/` (e.g. `tools/migrate_decision_record_v1_to_v2.py`).

## Verifying old evidence

Use `hb verify-decision --decision <path> --evidence <evidence_pack_dir>` to re-run compare from evidence; works with v1.0 decision records and evidence packs.
