#!/usr/bin/env python3
import sys
import json
import math

scenario = sys.argv[1] if len(sys.argv) > 1 else "A1"
csv_path = f"/home/ubuntu/k6/results-cenario-{scenario}-raw.csv"
summary_path = f"/home/ubuntu/k6/results-cenario-{scenario}-summary.json"
out_path = f"/home/ubuntu/k6/cenario-{scenario}-exact-stats.json"

ops = {
    "http_req_duration": [],
    "op_login_duration": [],
    "op_catalogo_duration": [],
    "op_venda_duration": []
}
timeouts_60s = 0

with open(csv_path, "r", encoding="utf-8", errors="replace") as f:
    header = f.readline()
    for line in f:
        # metric_name,timestamp,metric_value,...
        parts = line.split(",", 3)
        if len(parts) >= 3:
            m = parts[0]
            if m in ops:
                try:
                    val = float(parts[2])
                    ops[m].append(val)
                    if m == "http_req_duration" and val >= 60000.0:
                        timeouts_60s += 1
                except ValueError:
                    pass

def calc_percentile(sorted_arr, p):
    if not sorted_arr:
        return 0.0
    k = (len(sorted_arr) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_arr[int(k)]
    return sorted_arr[int(f)] * (c - k) + sorted_arr[int(c)] * (k - f)

stats = {}
for k, arr in ops.items():
    arr.sort()
    n = len(arr)
    mean = sum(arr) / n if n else 0.0
    var = sum((x - mean) ** 2 for x in arr) / n if n else 0.0
    p25 = calc_percentile(arr, 25)
    p50 = calc_percentile(arr, 50)
    p75 = calc_percentile(arr, 75)
    p90 = calc_percentile(arr, 90)
    p95 = calc_percentile(arr, 95)
    p99 = calc_percentile(arr, 99)
    slo_500_ok = sum(1 for x in arr if x <= 500.0)
    slo_300_ok = sum(1 for x in arr if x <= 300.0)
    slo_800_ok = sum(1 for x in arr if x <= 800.0)
    slo_1200_ok = sum(1 for x in arr if x <= 1200.0)
    stats[k] = {
        "count": n,
        "mean": round(mean, 2),
        "std": round(math.sqrt(var), 2),
        "min": round(arr[0], 2) if n else 0.0,
        "p25": round(p25, 2),
        "p50": round(p50, 2),
        "p75": round(p75, 2),
        "iqr": round(p75 - p25, 2),
        "p90": round(p90, 2),
        "p95": round(p95, 2),
        "p99": round(p99, 2),
        "max": round(arr[-1], 2) if n else 0.0,
        "le_300ms_pct": round(100.0 * slo_300_ok / n, 2) if n else 0.0,
        "le_500ms_pct": round(100.0 * slo_500_ok / n, 2) if n else 0.0,
        "le_800ms_pct": round(100.0 * slo_800_ok / n, 2) if n else 0.0,
        "le_1200ms_pct": round(100.0 * slo_1200_ok / n, 2) if n else 0.0,
    }

stats["timeouts_60s"] = timeouts_60s

with open(summary_path, "r", encoding="utf-8") as sf:
    stats["k6_summary"] = json.load(sf)

with open(out_path, "w", encoding="utf-8") as out:
    json.dump(stats, out, indent=2)

print(json.dumps(stats, indent=2))
