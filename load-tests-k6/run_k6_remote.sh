#!/usr/bin/env bash
# ==============================================================================
# Executor Automatizado da Bateria de Carga Oficial (k6 v0.49.0)
# Uso: ./run_k6_remote.sh <CENARIO: A1|A2|B1|B2> <TARGET_IP> <ADMIN_PASS>
# ==============================================================================
set +e

SCENARIO="${1:-A1}"
TARGET_IP="${2:-<EC2_K3S_IP>}"
ADMIN_PASS="${3:-${ADMIN_PASS:-<ADMIN_PASSWORD>}}"

START_EPOCH=$(date -u +%s)
START_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
START_BRT=$(TZ="America/Sao_Paulo" date +"%Y-%m-%dT%H:%M:%S-03:00")

cat <<EOF > "cenario-${SCENARIO}-timestamps.env"
SCENARIO=${SCENARIO}
TARGET_IP=${TARGET_IP}
START_EPOCH=${START_EPOCH}
START_UTC=${START_UTC}
START_BRT=${START_BRT}
EOF

k6 run \
  -e BASE_URL=https://blackcat.mugiwarasgroup.com.br \
  -e TARGET_IP="${TARGET_IP}" \
  -e ADMIN_USER=sre_admin_tcc \
  -e ADMIN_PASS="${ADMIN_PASS}" \
  -e TEST_MODE=official \
  -o experimental-prometheus-rw \
  -e K6_PROMETHEUS_RW_SERVER_URL="http://${TARGET_IP}:30090/api/v1/write" \
  -e K6_PROMETHEUS_RW_TREND_STATS="p(50),p(95),p(99),avg" \
  -e K6_PROMETHEUS_RW_PUSH_INTERVAL=2s \
  --out "csv=results-cenario-${SCENARIO}-raw.csv" \
  --summary-export="results-cenario-${SCENARIO}-summary.json" \
  load-test.js 2>&1 | tee "cenario-${SCENARIO}-execution.log"

END_EPOCH=$(date -u +%s)
END_UTC=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
END_BRT=$(TZ="America/Sao_Paulo" date +"%Y-%m-%dT%H:%M:%S-03:00")

cat <<EOF >> "cenario-${SCENARIO}-timestamps.env"
END_EPOCH=${END_EPOCH}
END_UTC=${END_UTC}
END_BRT=${END_BRT}
DURATION_SECONDS=$((END_EPOCH - START_EPOCH))
EOF
