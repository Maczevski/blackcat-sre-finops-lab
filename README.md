# Aplicação de Observabilidade e Site Reliability Engineering: Otimização do Uso de Recursos Computacionais em Práticas de FinOps em Ambientes de Cloud

**Trabalho de Conclusão de Curso (TCC 2) — Bacharelado em Engenharia de Software**  
**Autoras:** Emilly Vitória Maczevski de Souza; Júlia Moraes de Oliveira  
**Orientador:** Prof. Willian Frohnhofer Zibikoski | **Coorientador:** Prof. Ruminiki Pavei Schmoeller  
**Região Experimental AWS:** `us-east-2` (Ohio) | **Orquestrador:** K3s `v1.34.6+k3s1` | **Gerador de Carga:** Grafana k6 `v0.49.0` (Intra-VPC)

---

## 1. Visão Geral e Delineamento Experimental (Matriz Fatorial $2 \times 2$)

Este repositório contém a infraestrutura declarativa Kubernetes (K3s), o código-fonte completo da aplicação **BlackCat** (Backend Spring Boot + Frontend Angular), a pilha de observabilidade (Prometheus + Node Exporter + Grafana), o motor de injeção de carga sintética (k6) e os scripts/dados censais de análise estatística e financeira dos quatro cenários experimentais (**A1, A2, B1 e B2**).

Como entre os pares **A1/A2** e **B1/B2** a única variável independente alterada dentro de cada estado de software é o dimensionamento vertical da instância AWS EC2 (`t3.small` vs. `t3.medium`), os artefatos da aplicação e os manifestos Kubernetes estão organizados em **dois tratamentos tecnológicos** (`01-ineficiente-A1-A2` e `02-otimizado-B1-B2`) que se combinam com as duas instâncias EC2 para formar os 4 cenários:

| Cenário | Pasta de Tratamento no Repositório | Instância AWS EC2 | vCPUs / RAM Física (Utilizável) | Tarifa IaaS (`us-east-2`) | Tag Imutável da Imagem AWS ECR | Limites K3s (`limits.cpu` / `memory`) | Configuração de Runtime JVM (OpenJDK 21) |
| :---: | :--- | :---: | :---: | :---: | :--- | :---: | :--- |
| **A1** *(Baseline)* | `01-ineficiente-A1-A2/` | `t3.small` | 2 vCPUs / 2 GiB (`1.905 MiB`) | US$ 0,0208 / h | `blackcat-backend:tcc-v4-actuator-v3` | `1200m` / `768Mi` | Ergonomia padrão (`MaxRAMPercentage=25%` $\rightarrow$ Heap Máx `185,62 MiB`) |
| **A2** *(Scale-Up Cego)* | `01-ineficiente-A1-A2/` | `t3.medium` | 2 vCPUs / 4 GiB (`3.832 MiB`) | US$ 0,0416 / h | `blackcat-backend:tcc-v4-actuator-v3` | `1200m` / `768Mi` | Ergonomia padrão (`MaxRAMPercentage=25%` $\rightarrow$ Heap Máx `185,62 MiB`) |
| **B1** *(Otimização SRE)* | `02-otimizado-B1-B2/` | `t3.medium` | 2 vCPUs / 4 GiB (`3.832 MiB`) | US$ 0,0416 / h | `blackcat-backend:tcc-v5-cenario-B` | `1500m` / `768Mi` | `JAVA_TOOL_OPTIONS="-XX:+UseG1GC -Xms384m -Xmx384m"` (Heap `384,00 MiB`) |
| **B2** *(Right-Sizing FinOps)* | `02-otimizado-B1-B2/` | `t3.small` | 2 vCPUs / 2 GiB (`1.905 MiB`) | US$ 0,0208 / h | `blackcat-backend:tcc-v5-cenario-B` | `1500m` / `768Mi` | `JAVA_TOOL_OPTIONS="-XX:+UseG1GC -Xms384m -Xmx384m"` (Heap `384,00 MiB`) |

---

## 2. Rastreabilidade das Imagens ECR e Diferencial Técnico (`v4` vs. `v5`)

1. **Tratamento 01 — Baseline Ineficiente (`01-ineficiente-A1-A2/` | Tag `:tcc-v4-actuator-v3`):**
   * **Código-Fonte (`app-backend/src/main/java/app/Entity/Produto.java`):** A entidade JPA `Produto` mapeia a relação `@OneToMany(mappedBy = "produto") private List<ProdutoVenda> produtosVenda` sem a anotação `@JsonIgnore`. Durante a listagem de catálogo (`GET /api/produto/findAll`), o serializador Jackson percorre recursivamente todo o histórico de itens de venda de cada produto, inflando os payloads JSON para ~4 MB por requisição (> 31 GiB de tráfego em 60 minutos).
   * **Manifesto K3s (`k3s-manifests/backend-deployment.yaml`):** Não define `JAVA_TOOL_OPTIONS`. O OpenJDK 21 aplica a heurística padrão de containers (`MaxRAMPercentage=25%` sobre `limits.memory: 768Mi`), restringindo a JVM Heap a **185,62 MiB** tanto na `t3.small` (A1) quanto na `t3.medium` (A2), desencadeando *GC Thrashing* (~1,7–1,8 pausas/s e > 90 ms/s de congelamento *Stop-The-World*) e saturação de CPU no teto de `1.200 mCPU`.

2. **Tratamento 02 — Otimizado SRE & FinOps (`02-otimizado-B1-B2/` | Tag `:tcc-v5-cenario-B`):**
   * **Código-Fonte (`app-backend/src/main/java/app/Entity/Produto.java`):** Adiciona `@JsonIgnore` sobre `produtosVenda` e `getProdutosVenda()`, eliminando a serialização recursiva e reduzindo o tráfego de rede (*Data Egress*) em **99,79%** (de > 31,9 GiB para ~71–74 MiB em 60 minutos).
   * **Manifesto K3s (`k3s-manifests/backend-deployment.yaml`):** Parametriza explicitamente `JAVA_TOOL_OPTIONS="-XX:+UseG1GC -Xms384m -Xmx384m"` (elevando a Heap útil para **384,00 MiB** dentro do mesmo limite de container de `768Mi`) e expande `limits.cpu` para `1500m`, reduzindo o tempo de pausa de GC em **99,6%** (para ~0,32–0,37 ms/s) e viabilizando o *Right-Sizing* vertical seguro da `t3.medium` (B1) para a `t3.small` (B2).

---

## 3. Estrutura de Diretórios do Repositório

```text
blackcat-sre-finops-lab/
├── README.md                          # Documentação científica, matriz 2x2 e guia de reprodução
├── .gitignore                         # Regras de exclusão de segredos, binários e temporários
├── .env.example                       # Template higienizado de variáveis de ambiente e credenciais
├── 01-ineficiente-A1-A2/              # Tratamento Baseline Ineficiente (Imagem ECR :tcc-v4-actuator-v3, JVM padrão)
│   ├── app-backend/                   # Projeto Spring Boot completo (Produto.java sem @JsonIgnore, Actuator, Liquibase)
│   └── k3s-manifests/                 # backend-deployment.yaml (limits 1200m CPU / 768Mi RAM, sem JAVA_TOOL_OPTIONS)
├── 02-otimizado-B1-B2/                # Tratamento Otimizado (Imagem ECR :tcc-v5-cenario-B, G1GC + Heap 384m)
│   ├── app-backend/                   # Projeto Spring Boot completo (Produto.java com @JsonIgnore, Actuator, Liquibase)
│   └── k3s-manifests/                 # backend-deployment.yaml (limits 1500m CPU / 768Mi RAM + JAVA_TOOL_OPTIONS)
├── infra-base-k3s/                    # Recursos compartilhados entre todos os 4 cenários
│   ├── app-frontend/                  # Projeto Angular 18 completo, Dockerfile e proxy reverso Nginx (blackcat.conf)
│   ├── kubernetes/                    # namespace, mysql (statefulset, configmap, secret higienizado), frontend, services e ingress
│   └── observability/                 # prometheus.yml, rules.yml, prometheus-stack.yaml, node-exporter.yaml e dashboard Grafana JSON
├── load-tests-k6/                     # Motor de carga sintética em malha fechada (Grafana k6 v0.49.0)
│   ├── load-test.js                   # Script oficial (60 min steady-state, 15 VUs, mix 60/20/20 e thresholds de SLOs)
│   └── run_k6_remote.sh               # Wrapper bash para execução autônoma e registro de timestamps UTC
└── analysis/                          # Consolidação FinOps (C_UT) e Inferência Estatística (Delta de Cliff)
    ├── scripts/                       # Scripts Python para coleta PromQL, processamento k6 e cálculo de C_UT / Delta de Cliff
    └── data/                          # Sumários JSON/CSV consolidados dos cenários A1, A2, B1 e B2
```

---

## 4. Passo a Passo para Reprodução Experimental

### Pré-requisitos
* **Nó do Cluster (SUT):** Instância AWS EC2 Ubuntu 22.04 LTS (`t3.small` para A1/B2 ou `t3.medium` para A2/B1) na região `us-east-2` com K3s (`v1.34+`) instalado.
* **Nó Injetor de Carga:** Instância AWS EC2 `t3.small` dedicada na mesma VPC/Sub-rede (`us-east-2a`) com Grafana k6 `v0.49.0` instalado.
* **Configuração de Variáveis:** Copie `.env.example` para `.env` e substitua os placeholders `<AWS_ACCOUNT_ID>`, `<DB_PASSWORD>`, `<EC2_K3S_IP>` e `<ADMIN_PASSWORD>` nos manifestos antes do deploy.

### Etapa 1 — Provisionar a Infraestrutura Base e Observabilidade no K3s
No nó K3s, aplique os recursos base (Namespace, MySQL 8.4, Frontend, Services, Ingress e Stack Prometheus/Node Exporter):

```bash
# 1. Criar namespaces e infraestrutura de banco de dados + frontend
kubectl apply -f infra-base-k3s/kubernetes/namespace.yaml
kubectl apply -f infra-base-k3s/kubernetes/mysql/
kubectl apply -f infra-base-k3s/kubernetes/frontend-deployment.yaml
kubectl apply -f infra-base-k3s/kubernetes/frontend-service.yaml
kubectl apply -f infra-base-k3s/kubernetes/backend-service.yaml
kubectl apply -f infra-base-k3s/kubernetes/blackcat-ingress.yaml

# 2. Implantar a pilha de observabilidade (Prometheus NodePort 30090 + Node Exporter + Grafana)
kubectl apply -f infra-base-k3s/observability/namespace.yaml
kubectl apply -f infra-base-k3s/observability/node-exporter.yaml
kubectl apply -f infra-base-k3s/observability/prometheus-stack.yaml
kubectl apply -f infra-base-k3s/observability/grafana.yaml
```

### Etapa 2 — Aplicar o Tratamento do Cenário Desejado (A1/A2 ou B1/B2)

* **Para reproduzir o Cenário A1 (em `t3.small`) ou Cenário A2 (em `t3.medium`):**
  ```bash
  kubectl apply -f 01-ineficiente-A1-A2/k3s-manifests/backend-deployment.yaml
  kubectl rollout status deployment/backend -n blackcat --timeout=120s
  ```

* **Para reproduzir o Cenário B1 (em `t3.medium`) ou Cenário B2 (em `t3.small`):**
  ```bash
  kubectl apply -f 02-otimizado-B1-B2/k3s-manifests/backend-deployment.yaml
  kubectl rollout status deployment/backend -n blackcat --timeout=120s
  ```

### Etapa 3 — Executar a Bateria de Carga de 60 Minutos (15 VUs) a partir da VM Injetora
Na VM injetora intra-VPC, execute o script automatizado do k6 passando o identificador do cenário (`A1`, `A2`, `B1` ou `B2`), o IP do nó K3s e a senha do usuário de teste:

```bash
cd load-tests-k6
chmod +x run_k6_remote.sh
./run_k6_remote.sh B2 <EC2_K3S_IP> "<ADMIN_PASSWORD>"
```
> O protocolo executa **2 minutos de rampa de aquecimento (*warm-up*)**, **60 minutos contínuos em patamar fixo de 15 VUs** (60% `POST /api/login/logar`, 20% `GET /api/produto/findAll?ativo=true`, 20% `POST /api/venda/save` com *think time* de `0,3s`) e **1 minuto de *ramp-down***.

### Etapa 4 — Coletar as Séries Temporais do Prometheus e Reproduzir a Análise FinOps / Estatística
Após o término da bateria, colete as séries temporais do Prometheus e execute o script de consolidação para verificar o Custo por Mil Requisições Úteis ($C_{UT}$) e a matriz de tamanho de efeito **Delta de Cliff ($\delta$)**:

```bash
cd analysis/scripts

# 1. (Opcional) Coletar métricas de um novo ensaio diretamente da API do Prometheus:
python collect_prometheus_metrics.py B2 <EC2_K3S_IP> <START_EPOCH> <END_EPOCH>

# 2. Reproduzir as tabelas consolidadas de Unit Economics (C_UT) e Delta de Cliff (δ) dos 4 cenários:
python reproduce_finops_and_cliffs_delta.py
```

---

## 5. Síntese dos Resultados Oficiais Consolidados

| Indicador Experimental | Cenário A1 (`t3.small` `:v4`) | Cenário A2 (`t3.medium` `:v4`) | Cenário B1 (`t3.medium` `:v5`) | Cenário B2 (`t3.small` `:v5`) |
| :--- | :---: | :---: | :---: | :---: |
| **Requisições Concluídas em 60 min (HTTP 2xx)** | 40.796 | 41.513 | 86.755 | **89.904** |
| **Vazão Efetiva Média (Throughput RPS)** | 10,79 RPS | 10,97 RPS | 22,93 RPS | **23,77 RPS** |
| **Volume Trafegado (*Data Egress*)** | 31,93 GiB | 33,09 GiB | 71,42 MiB | **73,98 MiB** |
| **CPU Host Média / $p_{95}$ / Pico Máximo (%)** | 77,98% / 82,81% / 84,42% | 77,43% / 82,09% / 82,74% | 82,12% / 84,06% / 84,47% | **81,55% / 83,78% / 84,52%** |
| **RAM Física Host Alocada Média (MiB / %)** | 1.618,2 MiB (84,9%) | 1.618,2 MiB (46,1%) | 1.953,4 MiB (51,0%) | **1.647,8 MiB (86,5%)** |
| **Tempo de Congelamento por GC (ms/s)** | 92,56 ms/s | 90,56 ms/s | 0,37 ms/s | **0,32 ms/s** |
| **Catálogo (`/api/produtos`): $p_{50}$ / $p_{95}$ (SLO $\le 500\text{ ms}$)** | 1.292,12 / 3.067,54 ms | 1.211,86 / 2.758,03 ms | 55,02 / 155,83 ms | **53,33 / 128,58 ms** |
| **Agregado Global HTTP: $p_{50}$ / $p_{95}$ (ms)** | 774,83 / 2.081,97 ms | 750,37 / 1.880,28 ms | 321,57 / 725,04 ms | **303,07 / 679,58 ms** |
| **Custo por Mil Requisições Úteis ($C_{UT}$)** | US$ 0,000510 | US$ 0,001002 | US$ 0,000480 | **US$ 0,000231** |
| **Delta de Cliff ($\delta$) Global nas Transições Causais** | — | $\delta(\text{A1}\times\text{A2}) = +0,0325$ *(Desprezível)* | $\delta(\text{A2}\times\text{B1}) = +0,5829$ *(Grande)* | $\delta(\text{B1}\times\text{B2}) = +0,0350$ *(Desprezível)* |
