#!/bin/sh
# Demo: run daemon with file-replay. Create a small telemetry JSONL, point daemon at it, run one cycle.
# Usage: ./tools/demo_daemon.sh

set -e
cd "$(dirname "$0")/.."
OUT=daemon_demo_output
mkdir -p "$OUT"

# Create minimal telemetry JSONL
TELEM="$OUT/telemetry.jsonl"
echo '{"metric":"avg_latency_ms","value":10.5,"unit":"ms"}' >> "$TELEM"
echo '{"metric":"max_latency_ms","value":22.0,"unit":"ms"}' >> "$TELEM"
echo '{"metric":"reset_count","value":0}' >> "$TELEM"

# Daemon config for file_replay
CFG="$OUT/daemon.yaml"
cat > "$CFG" << EOF
source: file_replay
path: $TELEM
interval_sec: 15
window_sec: 60
baseline_tag: golden
output_dir: $OUT/reports
db_path: $OUT/runs.db
metric_registry: metric_registry.yaml
baseline_policy: baseline_policy.yaml
alert_sinks: [stdout]
evidence_pack_on_fail: false
EOF

echo "Demo: run daemon with file_replay (Ctrl+C to stop)"
echo "Config: $CFG"
echo "Output: $OUT/reports"
python -m hb.cli daemon --config "$CFG"
