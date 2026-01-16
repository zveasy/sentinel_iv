import os
import sqlite3
import time
from datetime import datetime, timezone


def init_db(path):
    dir_name = os.path.dirname(path)
    if dir_name:
        os.makedirs(dir_name, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            program TEXT,
            subsystem TEXT,
            test_name TEXT,
            environment TEXT,
            build_sha TEXT,
            build_id TEXT,
            start_utc TEXT,
            end_utc TEXT,
            source_system TEXT,
            registry_hash TEXT,
            status TEXT,
            baseline_run_id TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_tags (
            tag TEXT PRIMARY KEY,
            run_id TEXT,
            registry_hash TEXT,
            created_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_approvals (
            approval_id TEXT PRIMARY KEY,
            run_id TEXT,
            tag TEXT,
            approved_by TEXT,
            reason TEXT,
            approved_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS baseline_requests (
            request_id TEXT PRIMARY KEY,
            run_id TEXT,
            tag TEXT,
            requested_by TEXT,
            reason TEXT,
            status TEXT,
            requested_at TEXT,
            approved_at TEXT
        )
        """
    )
    cursor = conn.execute("PRAGMA table_info(runs)")
    columns = {row[1] for row in cursor.fetchall()}
    if "registry_hash" not in columns:
        conn.execute("ALTER TABLE runs ADD COLUMN registry_hash TEXT")
    cursor = conn.execute("PRAGMA table_info(baseline_approvals)")
    approval_columns = {row[1] for row in cursor.fetchall()}
    if "request_id" not in approval_columns:
        conn.execute("ALTER TABLE baseline_approvals ADD COLUMN request_id TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS metrics (
            run_id TEXT,
            metric TEXT,
            value REAL,
            unit TEXT,
            tags TEXT
        )
        """
    )
    conn.commit()
    return conn


def _execute_with_retry(conn, query, params=(), retries=3, delay=0.25):
    attempt = 0
    while True:
        try:
            conn.execute(query, params)
            return
        except sqlite3.OperationalError as exc:
            if "locked" in str(exc).lower() and attempt < retries:
                attempt += 1
                time.sleep(delay)
                continue
            raise


def upsert_run(conn, run_meta, status, baseline_run_id=None, registry_hash=None):
    _execute_with_retry(
        conn,
        """
        INSERT INTO runs (
            run_id, program, subsystem, test_name, environment,
            build_sha, build_id, start_utc, end_utc, source_system,
            registry_hash, status, baseline_run_id, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(run_id) DO UPDATE SET
            status=excluded.status,
            baseline_run_id=excluded.baseline_run_id
        """,
        (
            run_meta["run_id"],
            run_meta.get("program"),
            run_meta.get("subsystem"),
            run_meta.get("test_name"),
            run_meta.get("environment"),
            run_meta.get("build", {}).get("git_sha"),
            run_meta.get("build", {}).get("build_id"),
            run_meta.get("timestamps", {}).get("start_utc"),
            run_meta.get("timestamps", {}).get("end_utc"),
            run_meta.get("toolchain", {}).get("source_system"),
            registry_hash,
            status,
            baseline_run_id,
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()


def replace_metrics(conn, run_id, metrics):
    _execute_with_retry(conn, "DELETE FROM metrics WHERE run_id = ?", (run_id,))
    for row in metrics:
        _execute_with_retry(
            conn,
            "INSERT INTO metrics (run_id, metric, value, unit, tags) VALUES (?, ?, ?, ?, ?)",
            (run_id, row["metric"], row["value"], row.get("unit"), row.get("tags")),
        )
    conn.commit()


def fetch_metrics(conn, run_id):
    cursor = conn.execute(
        "SELECT metric, value, unit, tags FROM metrics WHERE run_id = ?",
        (run_id,),
    )
    metrics = {}
    for metric, value, unit, tags in cursor.fetchall():
        metrics[metric] = {"value": value, "unit": unit, "tags": tags}
    return metrics


def select_baseline(conn, run_meta, policy, registry_hash=None):
    tag = policy.get("tag")
    warn_on_mismatch = policy.get("warn_on_mismatch", False)

    if tag:
        cursor = conn.execute(
            "SELECT run_id, registry_hash FROM baseline_tags WHERE tag = ?",
            (tag,),
        )
        row = cursor.fetchone()
        if row:
            warning = None
            if warn_on_mismatch and registry_hash and row[1] and row[1] != registry_hash:
                warning = f"baseline registry hash mismatch ({row[1]} != {registry_hash})"
            return row[0], "tag", warning
        return None, "tag_not_found", None

    query = """
        SELECT run_id, status
        FROM runs
        WHERE program = ? AND subsystem = ? AND test_name = ?
        ORDER BY created_at DESC
    """
    params = (
        run_meta.get("program"),
        run_meta.get("subsystem"),
        run_meta.get("test_name"),
    )
    cursor = conn.execute(query, params)
    rows = cursor.fetchall()
    if not rows:
        return None, "no_runs", None
    for run_id, status in rows:
        if status == "PASS":
            return run_id, "last_pass", None
    if policy.get("fallback") == "latest":
        return rows[0][0], "fallback_latest", None
    return None, "no_pass", None


def set_baseline_tag(conn, tag, run_id, registry_hash):
    _execute_with_retry(
        conn,
        """
        INSERT INTO baseline_tags (tag, run_id, registry_hash, created_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(tag) DO UPDATE SET
            run_id=excluded.run_id,
            registry_hash=excluded.registry_hash,
            created_at=excluded.created_at
        """,
        (tag, run_id, registry_hash, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()


def list_baseline_tags(conn):
    cursor = conn.execute(
        "SELECT tag, run_id, registry_hash, created_at FROM baseline_tags ORDER BY created_at DESC"
    )
    return cursor.fetchall()


def add_baseline_approval(conn, approval_id, run_id, tag, approved_by, reason, request_id=None):
    conn.execute(
        """
        INSERT INTO baseline_approvals (
            approval_id, run_id, tag, approved_by, reason, approved_at, request_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            approval_id,
            run_id,
            tag,
            approved_by,
            reason,
            datetime.now(timezone.utc).isoformat(),
            request_id,
        ),
    )
    conn.commit()


def list_baseline_approvals(conn, limit=50):
    cursor = conn.execute(
        """
        SELECT approval_id, run_id, tag, approved_by, reason, approved_at, request_id
        FROM baseline_approvals
        ORDER BY approved_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def add_baseline_request(conn, request_id, run_id, tag, requested_by, reason):
    conn.execute(
        """
        INSERT INTO baseline_requests (
            request_id, run_id, tag, requested_by, reason, status, requested_at, approved_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            request_id,
            run_id,
            tag,
            requested_by,
            reason,
            "pending",
            datetime.now(timezone.utc).isoformat(),
            None,
        ),
    )
    conn.commit()


def list_baseline_requests(conn, limit=50):
    cursor = conn.execute(
        """
        SELECT request_id, run_id, tag, requested_by, reason, status, requested_at, approved_at
        FROM baseline_requests
        ORDER BY requested_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()


def get_baseline_request(conn, request_id=None, run_id=None, tag=None):
    if request_id:
        cursor = conn.execute(
            """
            SELECT request_id, run_id, tag, requested_by, reason, status, requested_at, approved_at
            FROM baseline_requests
            WHERE request_id = ?
            """,
            (request_id,),
        )
        return cursor.fetchone()
    if run_id and tag:
        cursor = conn.execute(
            """
            SELECT request_id, run_id, tag, requested_by, reason, status, requested_at, approved_at
            FROM baseline_requests
            WHERE run_id = ? AND tag = ?
            ORDER BY requested_at DESC
            LIMIT 1
            """,
            (run_id, tag),
        )
        return cursor.fetchone()
    return None


def set_baseline_request_status(conn, request_id, status, approved_at=None):
    _execute_with_retry(
        conn,
        """
        UPDATE baseline_requests
        SET status = ?, approved_at = ?
        WHERE request_id = ?
        """,
        (status, approved_at, request_id),
    )
    conn.commit()


def count_baseline_approvals(conn, request_id=None, run_id=None, tag=None):
    if request_id:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM baseline_approvals WHERE request_id = ?",
            (request_id,),
        )
    else:
        cursor = conn.execute(
            "SELECT COUNT(*) FROM baseline_approvals WHERE run_id = ? AND tag = ?",
            (run_id, tag),
        )
    return cursor.fetchone()[0]


def run_exists(conn, run_id):
    cursor = conn.execute("SELECT 1 FROM runs WHERE run_id = ? LIMIT 1", (run_id,))
    return cursor.fetchone() is not None


def list_runs(conn, limit=20):
    cursor = conn.execute(
        """
        SELECT run_id, status, program, subsystem, test_name, created_at
        FROM runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    return cursor.fetchall()
