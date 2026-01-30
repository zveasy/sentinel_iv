#!/usr/bin/env python3
import argparse
import html
import os
import sqlite3


def fetch_rows(conn, query, params=()):
    cursor = conn.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    return columns, cursor.fetchall()


def print_table(columns, rows):
    widths = [len(col) for col in columns]
    for row in rows:
        widths = [max(widths[i], len(str(row[i]))) for i in range(len(columns))]
    header = " | ".join(col.ljust(widths[i]) for i, col in enumerate(columns))
    divider = "-+-".join("-" * widths[i] for i in range(len(columns)))
    print(header)
    print(divider)
    for row in rows:
        print(" | ".join(str(row[i]).ljust(widths[i]) for i in range(len(columns))))


def list_runs(conn, limit):
    columns, rows = fetch_rows(
        conn,
        """
        SELECT run_id, summary, drift_count, created_at, report_dir
        FROM runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    print_table(columns, rows)


def show_run(conn, run_id):
    columns, rows = fetch_rows(
        conn,
        "SELECT * FROM runs WHERE run_id = ?",
        (run_id,),
    )
    if not rows:
        print("run not found")
        return
    print_table(columns, rows)


def write_trend(conn, out_path, limit):
    columns, rows = fetch_rows(
        conn,
        """
        SELECT run_id, summary, drift_count, created_at, report_dir
        FROM runs
        ORDER BY created_at DESC
        LIMIT ?
        """,
        (limit,),
    )
    drift_idx = columns.index("drift_count") if "drift_count" in columns else None
    drift_values = []
    if drift_idx is not None:
        for row in reversed(rows):
            try:
                drift_values.append(int(row[drift_idx]))
            except Exception:
                drift_values.append(0)

    def _sparkline(values, width=420, height=80):
        if not values:
            return "<div class=\"muted\">No trend data available.</div>"
        min_v = min(values)
        max_v = max(values)
        span = max(max_v - min_v, 1)
        step = width / max(len(values) - 1, 1)
        points = []
        for idx, val in enumerate(values):
            x = round(idx * step, 2)
            y = round(height - ((val - min_v) / span) * height, 2)
            points.append(f"{x},{y}")
        points_str = " ".join(points)
        last = points[-1].split(",")
        return (
            f"<svg width=\"{width}\" height=\"{height}\" viewBox=\"0 0 {width} {height}\" "
            "preserveAspectRatio=\"none\">"
            f"<polyline fill=\"none\" stroke=\"#0e6f8a\" stroke-width=\"2\" points=\"{points_str}\" />"
            f"<circle r=\"3\" cx=\"{last[0]}\" cy=\"{last[1]}\" fill=\"#d9822b\" />"
            "</svg>"
        )

    sparkline_html = _sparkline(drift_values)
    rows_html = []
    for row in rows:
        cells = "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row)
        rows_html.append(f"<tr>{cells}</tr>")
    table_rows = "\n".join(rows_html)
    header_cells = "".join(f"<th>{html.escape(col)}</th>" for col in columns)
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>Sentinel-IV Run Trends</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f3f3f3; }}
    .trend-card {{ margin-bottom: 18px; padding: 12px 14px; border: 1px solid #e2e8f0; border-radius: 8px; background: #fbfbfb; }}
    .trend-title {{ font-weight: 600; margin-bottom: 6px; }}
    .muted {{ color: #666; font-size: 13px; }}
  </style>
</head>
<body>
  <h1>Run Trend Summary</h1>
  <div class="trend-card">
    <div class="trend-title">Drift Count Trend</div>
    {sparkline_html}
  </div>
  <table>
    <thead>
      <tr>{header_cells}</tr>
    </thead>
    <tbody>
      {table_rows}
    </tbody>
  </table>
</body>
</html>
"""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w") as f:
        f.write(html_doc)
    print(f"wrote trend report to {out_path}")


def main():
    parser = argparse.ArgumentParser(description="Sentinel-IV registry tools")
    parser.add_argument(
        "--registry",
        default="mvp/registry/runs.db",
        help="SQLite registry path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list recent runs")
    list_parser.add_argument("--limit", type=int, default=20)

    show_parser = subparsers.add_parser("show", help="show run details")
    show_parser.add_argument("run_id")

    trend_parser = subparsers.add_parser("trend", help="write trend HTML report")
    trend_parser.add_argument("--out", default="mvp/reports/trend.html")
    trend_parser.add_argument("--limit", type=int, default=50)

    args = parser.parse_args()
    conn = sqlite3.connect(args.registry)
    if args.command == "list":
        list_runs(conn, args.limit)
    elif args.command == "show":
        show_run(conn, args.run_id)
    elif args.command == "trend":
        write_trend(conn, args.out, args.limit)


if __name__ == "__main__":
    main()
