#!/usr/bin/env sh
# Quick test of send_event and receive_ack. Run from repo root: ./examples/cpp/run_tests.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== send_event (default) ==="
./send_event

echo ""
echo "=== send_event --status FAIL --system-id asset-002 ==="
./send_event --status FAIL --system-id asset-002

echo ""
echo "=== receive_ack with ACTION_ACK ==="
printf '%s\n' '{"type":"ACTION_ACK","action_id":"abc","action_allowed":true}' | ./receive_ack

echo ""
echo "=== pipeline: send_event | receive_ack ==="
./send_event | ./receive_ack

echo ""
echo "=== done ==="
