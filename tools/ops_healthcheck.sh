#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-$(cd "$(dirname "$0")/.." && pwd)}"
LOG_DIR="${LOG_DIR:-$ROOT_DIR/logs}"
REPORTS_DIR="${REPORTS_DIR:-$ROOT_DIR/mvp/reports}"
DB_PATH="${DB_PATH:-$ROOT_DIR/runs.db}"
DISK_MAX_MB="${DISK_MAX_MB:-5120}"
BASELINE_POLICY="${BASELINE_POLICY:-$ROOT_DIR/baseline_policy.yaml}"
RUN_SOURCE="${RUN_SOURCE:-$ROOT_DIR/samples/cases/no_drift_pass/current_source.csv}"
RUN_META="${RUN_META:-$ROOT_DIR/samples/cases/no_drift_pass/current_run_meta.json}"
ENCRYPT_KEY="${ENCRYPT_KEY:-}"
ALERT_EMAIL="${ALERT_EMAIL:-}"

mkdir -p "$LOG_DIR"

LOG_FILE="$LOG_DIR/ops_healthcheck_$(date +"%Y%m%d%H%M%S").log"

detect_mail_cmd() {
  if [[ -n "${MAIL_CMD:-}" ]]; then
    echo "$MAIL_CMD"
    return
  fi
  if command -v mail >/dev/null 2>&1; then
    echo "mail"
    return
  fi
  if command -v mailx >/dev/null 2>&1; then
    echo "mailx"
    return
  fi
  if command -v sendmail >/dev/null 2>&1; then
    echo "sendmail"
    return
  fi
  echo ""
}

send_alert() {
  local subject="$1"
  local mail_cmd
  mail_cmd="$(detect_mail_cmd)"
  if [[ -z "$ALERT_EMAIL" ]]; then
    echo "alert skipped: ALERT_EMAIL not set" >>"$LOG_FILE"
    return
  fi
  if [[ -z "$mail_cmd" ]]; then
    echo "alert skipped: no mailer available" >>"$LOG_FILE"
    return
  fi
  if [[ "$mail_cmd" == "sendmail" ]]; then
    {
      echo "Subject: $subject"
      echo "To: $ALERT_EMAIL"
      echo
      cat "$LOG_FILE"
    } | sendmail -t
  else
    cat "$LOG_FILE" | "$mail_cmd" -s "$subject" "$ALERT_EMAIL"
  fi
}

on_error() {
  local line="$1"
  echo "ops healthcheck failed at line $line: $(date -u +"%Y-%m-%dT%H:%M:%SZ")" >>"$LOG_FILE"
  send_alert "[HB] ops healthcheck failed"
}

trap 'on_error $LINENO' ERR

{
  echo "ops healthcheck start: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  "$ROOT_DIR/tools/ops_demo_check.sh" "$RUN_SOURCE" "$RUN_META" "" "$REPORTS_DIR" "$BASELINE_POLICY"
  "$ROOT_DIR/tools/validate_backup_restore.sh" "$DB_PATH" "$ROOT_DIR/backups/validation" "$ENCRYPT_KEY"
  "$ROOT_DIR/tools/check_disk_usage.sh" "$REPORTS_DIR" "$DB_PATH" "$DISK_MAX_MB"
  echo "ops healthcheck ok: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
} | tee "$LOG_FILE"
