#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de Reprodutibilidade Analítica: Unit Economics FinOps (C_UT) e Tamanho de Efeito (Delta de Cliff).
Lê os sumários consolidados em ../data/ e imprime as 4 Tabelas Oficiais do TCC (Padrão IBGE).
"""
import os
import json

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data")

HOURLY_COST_USD = {
    "A1": 0.0208,  # AWS EC2 t3.small (us-east-2)
    "A2": 0.0416,  # AWS EC2 t3.medium (us-east-2)
    "B1": 0.0416,  # AWS EC2 t3.medium (us-east-2)
    "B2": 0.0208,  # AWS EC2 t3.small (us-east-2)
}

def main():
    with open(os.path.join(DATA_DIR, "consolidated_experiment_stats.json"), "r", encoding="utf-8") as f:
        inf = json.load(f)

    print("=" * 88)
    print("1. CONSOLIDAÇÃO FINOPS (CUSTO POR MIL REQUISIÇÕES ÚTEIS - C_UT) E CAMADA RED/USE")
    print("=" * 88)
    print(f"{'Cenário':<8} | {'Reqs 2xx':>10} | {'RPS':>7} | {'Tarifa/h':>10} | {'C_UT (US$/1k)':>14} | {'CPU Host %':>10} | {'RAM Host MiB':>13} | {'Cat p95 (ms)':>12}")
    print("-" * 88)

    for sc in ["A1", "A2", "B1", "B2"]:
        with open(os.path.join(DATA_DIR, f"cenario-{sc}", f"cenario-{sc}-exact-stats.json"), "r", encoding="utf-8") as f:
            ks = json.load(f)
        with open(os.path.join(DATA_DIR, f"cenario-{sc}", f"prometheus-metrics-{sc}.json"), "r", encoding="utf-8") as f:
            pm = json.load(f)

        dur = float(pm["end_epoch"] - pm["start_epoch"])
        reqs = ks["http_req_duration"]["count"]
        rps = reqs / dur
        cost_h = HOURLY_COST_USD[sc]
        cut = (cost_h / float(reqs)) * 1000.0
        cpu_h = pm["summary"]["cpu_host_pct"]["mean"]
        ram_h = pm["summary"]["ram_host_used_mib"]["mean"]
        cat_p95 = ks["op_catalogo_duration"]["p95"]

        print(f"{sc:<8} | {reqs:>10,d} | {rps:>7.2f} | US$ {cost_h:>6.4f} | US$ {cut:>10.6f} | {cpu_h:>9.2f}% | {ram_h:>9.1f} MiB | {cat_p95:>9.2f} ms")

    print("\n" + "=" * 88)
    print("2. MATRIZ DE TAMANHO DE EFEITO DELTA DE CLIFF (Vargha & Delaney, 2000)")
    print("=" * 88)
    print(f"{'Comparação':<12} | {'Operação':<24} | {'Amostras (n1 vs n2)':<21} | {'Delta (δ)':>10} | {'Magnitude'}")
    print("-" * 88)

    op_names = [
        ("op_catalogo_duration", "Catálogo (/api/produtos)"),
        ("op_login_duration", "Login (/api/auth/login)"),
        ("op_venda_duration", "Transação (/api/pedidos)"),
        ("http_req_duration", "Agregado Global HTTP"),
    ]
    for comp_key, comp_label in [("A1_vs_A2", "A1 x A2"), ("A2_vs_B1", "A2 x B1"), ("B1_vs_B2", "B1 x B2")]:
        for m_key, m_label in op_names:
            node = inf["pairwise"][comp_key][m_key]
            samples_str = f"{node['n1']:,d} vs {node['n2']:,d}"
            print(f"{comp_label:<12} | {m_label:<24} | {samples_str:<21} | {node['cliffs_delta']:>+10.4f} | {node['magnitude']}")

if __name__ == "__main__":
    main()
