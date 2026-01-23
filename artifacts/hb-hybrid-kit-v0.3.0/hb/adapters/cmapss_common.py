import math


EXPECTED_COLUMNS = 26


def _load_rows(path):
    rows = []
    with open(path, "r") as f:
        for line_num, line in enumerate(f, start=1):
            stripped = line.strip()
            if not stripped:
                continue
            parts = stripped.split()
            rows.append((line_num, parts))
    return rows


def _parse_rows(rows, expected_columns):
    parsed = []
    for line_num, parts in rows:
        if len(parts) != expected_columns:
            raise ValueError(
                f"schema error: expected {expected_columns} columns, got {len(parts)} at line {line_num}"
            )
        try:
            engine_id = int(parts[0])
            cycle = int(parts[1])
            values = [float(value) for value in parts[2:]]
        except ValueError as exc:
            raise ValueError(f"schema error: non-numeric value at line {line_num}") from exc
        parsed.append([engine_id, cycle] + values)
    if not parsed:
        raise ValueError("schema error: no rows found")
    return parsed


def parse(path, expected_columns=EXPECTED_COLUMNS):
    rows = _load_rows(path)
    parsed = _parse_rows(rows, expected_columns)

    sensor_values = []
    for row in parsed:
        sensor_values.extend(row[5:])

    if not sensor_values:
        raise ValueError("schema error: missing sensor values")

    mean = sum(sensor_values) / len(sensor_values)
    variance = sum((value - mean) ** 2 for value in sensor_values) / len(sensor_values)
    std = math.sqrt(variance)

    return {
        "cmapss_sensor_mean": {"value": mean, "unit": None, "tags": None},
        "cmapss_sensor_std": {"value": std, "unit": None, "tags": None},
    }
