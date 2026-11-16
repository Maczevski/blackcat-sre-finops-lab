#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.parse
import math

scenario = sys.argv[1] if len(sys.argv) > 1 else "A1"
prom_ip = sys.argv[2] if len(sys.argv) > 2 else "<EC2_K3S_IP>"
start_ts = int(sys.argv[3]) if len(sys.argv) > 3 else 1793136974
end_ts = int(sys.argv[4]) if len(sys.argv) > 4 else 1793140755
out_path = sys.argv[5] if len(sys.argv) > 5 else f"../data/cenario-{scenario}/prometheus-metrics-{scenario}.json"

queries = {
    "cpu_host_pct": '100 - (avg(rate(node_cpu_seconds_total{mode="idle"}[1m])) * 100)',
    "cpu_backend_mcpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="blackcat", pod=~"backend.*", container!=""}[1m])) * 1000',
    "cpu_mysql_mcpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="blackcat", pod=~"mysql-0.*", container="mysql"}[1m])) * 1000',
    "cpu_frontend_mcpu": 'sum(rate(container_cpu_usage_seconds_total{namespace="blackcat", pod=~"frontend.*", container!=""}[1m])) * 1000',
    "ram_host_total_mib": 'node_memory_MemTotal_bytes / 1048576',
    "ram_host_used_mib": '(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / 1048576',
    "ram_host_used_pct": '((node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes) * 100',
    "swap_used_mib": '(node_memory_SwapTotal_bytes - node_memory_SwapFree_bytes) / 1048576',
    "ws_backend_mib": 'sum(container_memory_working_set_bytes{namespace="blackcat", pod=~"backend.*", container!=""}) / 1048576',
    "ws_mysql_mib": 'sum(container_memory_working_set_bytes{namespace="blackcat", pod=~"mysql-0.*", container="mysql"}) / 1048576',
    "ws_frontend_mib": 'sum(container_memory_working_set_bytes{namespace="blackcat", pod=~"frontend.*", container!=""}) / 1048576',
    "jvm_heap_used_mib": 'sum(jvm_memory_used_bytes{area="heap"}) / 1048576',
    "jvm_heap_max_mib": 'sum(jvm_memory_max_bytes{area="heap"}) / 1048576',
    "jvm_gc_pause_rate": 'sum(rate(jvm_gc_pause_seconds_count[1m]))',
    "jvm_gc_pause_time_ms_per_s": 'sum(rate(jvm_gc_pause_seconds_sum[1m])) * 1000',
    "hikari_active": 'hikaricp_connections_active',
    "hikari_pending": 'hikaricp_connections_pending',
}

def calc_p(sorted_arr, p):
    if not sorted_arr:
        return 0.0
    k = (len(sorted_arr) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_arr[int(k)]
    return sorted_arr[int(f)] * (c - k) + sorted_arr[int(c)] * (k - f)

results = {"scenario": scenario, "start_epoch": start_ts, "end_epoch": end_ts, "series": {}, "summary": {}}

for name, q in queries.items():
    params = urllib.parse.urlencode({"query": q, "start": start_ts, "end": end_ts, "step": "15s"})
    url = f"http://{prom_ip}:30090/api/v1/query_range?{params}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            res_list = data.get("data", {}).get("result", [])
            pts = []
            if res_list:
                for ts_val in res_list[0].get("values", []):
                    ts, v = int(ts_val[0]), float(ts_val[1])
                    if not math.isnan(v):
                        pts.append([ts, round(v, 3)])
            results["series"][name] = pts
            vals = sorted([p[1] for p in pts])
            if vals:
                results["summary"][name] = {
                    "samples": len(vals),
                    "mean": round(sum(vals) / len(vals), 2),
                    "min": round(vals[0], 2),
                    "p50": round(calc_p(vals, 50), 2),
                    "p95": round(calc_p(vals, 95), 2),
                    "max": round(vals[-1], 2),
                }
            else:
                results["summary"][name] = {"samples": 0, "mean": 0.0, "min": 0.0, "p50": 0.0, "p95": 0.0, "max": 0.0}
    except Exception as e:
        results["summary"][name] = {"error": str(e)}

import os
os.makedirs(os.path.dirname(out_path), exist_ok=True)
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)

print(json.dumps(results["summary"], indent=2))
