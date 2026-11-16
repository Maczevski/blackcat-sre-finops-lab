import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// ============================================================================
// 1. DEFINIÇÃO FORMAL DE SLIs / SLOs E MÉTRICAS INDIVIDUAIS POR OPERAÇÃO
// ============================================================================
// SLI Global de Disponibilidade (HTTP 2xx)
export const sliAvailability = new Rate('sli_availability');

// Métricas Individuais por Operação (Duração e Taxa de Sucesso)
export const durationCatalogo = new Trend('op_catalogo_duration', true);
export const durationLogin    = new Trend('op_login_duration', true);
export const durationVenda    = new Trend('op_venda_duration', true);

export const successCatalogo  = new Rate('op_catalogo_success');
export const successLogin     = new Rate('op_login_success');
export const successVenda     = new Rate('op_venda_success');

export const countVendas      = new Counter('op_venda_total_count');

// ============================================================================
// 2. SELEÇÃO DO MODO DE EXECUÇÃO (validate | pilot | official)
// ============================================================================
// - validate: Teste funcional rápido (1 VU, 3 iterações: 1 login, 1 catálogo, 1 venda)
// - pilot:    Teste piloto / fumaça curto de 3 minutos (até 15 VUs)
// - official: Rodada oficial do experimento de 60m em patamar estável a 15 VUs
const TEST_MODE = (__ENV.TEST_MODE || (__ENV.PILOT === 'true' ? 'pilot' : 'official')).toLowerCase();

const modeConfig = {
  validate: {
    vus: 1,
    iterations: 3,
  },
  smoke: {
    vus: 2,
    duration: '60s',
  },
  pilot: {
    stages: [
      { duration: '30s', target: 15 }, // Rampa rápida até 15 VUs
      { duration: '2m',  target: 15 }, // Patamar de validação de 2 min
      { duration: '30s', target: 0 },  // Ramp-down
    ],
  },
  official: {
    stages: [
      { duration: '2m',  target: 15 }, // Aquecimento gradual (Warm-up)
      { duration: '60m', target: 15 }, // Janela oficial de medição estável (60 min)
      { duration: '1m',  target: 0 },  // Ramp-down controlado
    ],
  },
};

const selectedConfig = modeConfig[TEST_MODE] || modeConfig.official;

export const options = Object.assign({}, selectedConfig, {
  hosts: {
    'blackcat.mugiwarasgroup.com.br': __ENV.TARGET_IP || '<EC2_K3S_IP>',
  },

  // ==========================================================================
  // THRESHOLDS DOS SLOs OFICIAIS DO TCC (Hipótese H2)
  // Alinhados com RTT físico (~140ms Brasil -> Ohio) e custo de BCrypt
  // ==========================================================================
  thresholds: {
    // SLO 1 (Latência Global): p50 <= 300ms e p95 <= 800ms
    'http_req_duration': ['p(50)<=300', 'p(95)<=800'],

    // SLO 2 (Taxa de Erros HTTP Global): Menor que 1,0%
    'http_req_failed': ['rate<0.01'],

    // SLO 3 (Disponibilidade Global HTTP 2xx): >= 99,0%
    'sli_availability': ['rate>=0.99'],

    // Monitoramento individual por operação
    'op_catalogo_duration': ['p(50)<=250', 'p(95)<=500'],
    'op_login_duration':    ['p(50)<=500', 'p(95)<=1200'],
    'op_venda_duration':    ['p(50)<=400', 'p(95)<=800'],
    'op_venda_success':     ['rate>=0.99'],
  },
});

// ============================================================================
// 3. CONFIGURAÇÃO DE AMBIENTE E CREDENCIAIS
// ============================================================================
const BASE_URL   = __ENV.BASE_URL || 'https://blackcat.mugiwarasgroup.com.br';
const ADMIN_USER = __ENV.ADMIN_USER || 'sre_admin_tcc';
const ADMIN_PASS = __ENV.ADMIN_PASS || '<ADMIN_PASSWORD>';
const USER_ID    = parseInt(__ENV.USER_ID || '1', 10);

// Formas de pagamento estritamente válidas segundo VendaService.validarVenda()
const FORMAS_PAGAMENTO = [
  'Pix',
  'Cartão de Crédito',
  'Cartão de Débito',
  'Dinheiro',
];

// ============================================================================
// CONTEXTO DE SESSÃO DINÂMICA DO USUÁRIO VIRTUAL (VU-LOCAL)
// No k6, variáveis declaradas no escopo do módulo são isoladas por VU.
// Cada VU mantém seu próprio token JWT e timestamp de obtenção, renovando-o
// continuamente nas operações de login (60% do tráfego).
// ============================================================================
let vuToken = null;
let vuTokenTimestamp = 0;

// ============================================================================
// 4. ETAPA DE SETUP (Autenticação prévia e verificação de prontidão)
// ============================================================================
export function setup() {
  if (!ADMIN_PASS) {
    throw new Error(
      'Variável ADMIN_PASS não informada. Execute passando -e ADMIN_PASS="sua_senha".'
    );
  }

  const headers = { 'Content-Type': 'application/json' };
  const loginPayload = JSON.stringify({
    username: ADMIN_USER,
    password: ADMIN_PASS,
  });

  console.log(`[Setup] Modo selecionado: ${TEST_MODE.toUpperCase()}`);
  console.log(`[Setup] Verificando prontidão e autenticando em ${BASE_URL}/api/login/logar...`);
  const loginRes = http.post(`${BASE_URL}/api/login/logar`, loginPayload, { headers });

  if (loginRes.status !== 200) {
    throw new Error(
      `Falha crítica no login do setup: Status ${loginRes.status} - ${loginRes.body}`
    );
  }

  const initialToken = loginRes.body.trim();
  console.log(`[Setup] Prontidão confirmada. Token inicial de validação obtido.`);
  return { initialToken };
}

// ============================================================================
// 5. FUNÇÕES DAS OPERAÇÕES DE NEGÓCIO E RENOVAÇÃO DINÂMICA DE TOKEN
// ============================================================================

function executarLogin(jsonHeaders) {
  const loginPayload = JSON.stringify({
    username: ADMIN_USER,
    password: ADMIN_PASS,
  });

  const res = http.post(`${BASE_URL}/api/login/logar`, loginPayload, {
    headers: jsonHeaders,
    tags: { operation: 'auth_login' },
  });

  const isSuccess = res.status === 200;
  sliAvailability.add(isSuccess);
  successLogin.add(isSuccess);
  durationLogin.add(res.timings.duration);

  // Armazena e atualiza dinamicamente o Bearer Token no contexto da VU
  if (isSuccess && res.body && res.body.trim().length > 20) {
    vuToken = res.body.trim();
    vuTokenTimestamp = Date.now();
  }

  check(res, {
    '[Login] status 200': (r) => r.status === 200,
    '[Login] token JWT presente': (r) => r.body && r.body.trim().length > 20,
  });

  return isSuccess;
}

function obterAuthHeaders(jsonHeaders) {
  const agora = Date.now();
  const maxIdadeTokenMs = 30 * 60 * 1000; // 30 minutos de tolerância máxima (TTL oficial é de 60m)

  // Mecanismo de fallback/refresh automático: se ausente ou com mais de 30 minutos, renova
  if (!vuToken || (agora - vuTokenTimestamp) > maxIdadeTokenMs) {
    executarLogin(jsonHeaders);
  }

  return {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${vuToken}`,
  };
}

function executarConsultaCatalogo(authHeaders) {
  const res = http.get(`${BASE_URL}/api/produto/findAll?ativo=true`, {
    headers: authHeaders,
    tags: { operation: 'catalogo_findAll' },
  });

  const isSuccess = res.status === 200;
  sliAvailability.add(isSuccess);
  successCatalogo.add(isSuccess);
  durationCatalogo.add(res.timings.duration);

  check(res, {
    '[Catálogo] status 200': (r) => r.status === 200,
    '[Catálogo] retornou lista não vazia': (r) => {
      try {
        const body = JSON.parse(r.body);
        return Array.isArray(body) && body.length >= 20;
      } catch (_) {
        return false;
      }
    },
  });
}

function executarCadastroVenda(authHeaders, iterIndex) {
  // Seleção determinística de produtos ativos (IDs 1 a 20 da migration 003-seed-products)
  // Garante reprodutibilidade idêntica entre Baseline e Cenário Otimizado
  const prodId1 = (iterIndex % 20) + 1;
  const prodId2 = ((iterIndex + 7) % 20) + 1;
  const formaPag = FORMAS_PAGAMENTO[iterIndex % FORMAS_PAGAMENTO.length];
  const desconto = (iterIndex % 3) * 5; // 0%, 5% ou 10%

  const vendaPayload = JSON.stringify({
    formaPagamento: formaPag,
    desconto: desconto,
    usuario: { id: USER_ID },
    produtosVenda: [
      { quantidade: 1, produto: { id: prodId1 } },
      { quantidade: 2, produto: { id: prodId2 } },
    ],
  });

  const res = http.post(`${BASE_URL}/api/venda/save`, vendaPayload, {
    headers: authHeaders,
    tags: { operation: 'venda_save' },
  });

  const isSuccess = res.status >= 200 && res.status < 300;
  sliAvailability.add(isSuccess);
  successVenda.add(isSuccess);
  durationVenda.add(res.timings.duration);
  if (isSuccess) {
    countVendas.add(1);
  }

  check(res, {
    '[Venda] status 200': (r) => r.status === 200,
    '[Venda] confirmação de sucesso': (r) => r.body && r.body.includes('sucesso'),
  });
}

// ============================================================================
// 6. LOOP PRINCIPAL DO USUÁRIO VIRTUAL (VU)
// Distribuição aprovada com orientador (60m):
//   - 60% Autenticação JWT com BCrypt (POST /api/login/logar) -> Renova token
//   - 20% Consulta de Catálogo         (GET /api/produto/findAll?ativo=true)
//   - 20% Registro de Venda            (POST /api/venda/save)
// ============================================================================
export default function (data) {
  const jsonHeaders = { 'Content-Type': 'application/json' };

  // Inicialização no primeiro ciclo da VU: se a VU ainda não tem token, herda o inicial do setup
  if (!vuToken && data && data.initialToken) {
    vuToken = data.initialToken;
    vuTokenTimestamp = Date.now();
  }

  if (TEST_MODE === 'validate') {
    // No modo validate (3 iterações), executa deterministically 1 de cada operação
    if (__ITER === 0) {
      executarLogin(jsonHeaders);
    } else if (__ITER === 1) {
      const authHeaders = obterAuthHeaders(jsonHeaders);
      executarConsultaCatalogo(authHeaders);
    } else {
      const authHeaders = obterAuthHeaders(jsonHeaders);
      executarCadastroVenda(authHeaders, __ITER);
    }
    sleep(0.5);
    return;
  }

  // Ciclo determinístico de 10 operações por VU:
  // 6 Login (60%), 2 Catálogo (20%), 2 Vendas (20%)
  const step = (__ITER + __VU) % 10;

  if (step < 6) {
    // 60%: Login intensivo em CPU/BCrypt (steps 0, 1, 2, 3, 4, 5)
    // Atualiza continuamente vuToken e vuTokenTimestamp a cada ciclo
    executarLogin(jsonHeaders);
  } else if (step < 8) {
    // 20%: Consulta de Catálogo (steps 6, 7)
    // Garante token dinâmico atualizado via obterAuthHeaders()
    const authHeaders = obterAuthHeaders(jsonHeaders);
    executarConsultaCatalogo(authHeaders);
  } else {
    // 20%: Registro de Venda (steps 8, 9)
    // Garante token dinâmico atualizado via obterAuthHeaders()
    const authHeaders = obterAuthHeaders(jsonHeaders);
    executarCadastroVenda(authHeaders, __ITER);
  }

  // Pacing controlado entre requisições (300ms)
  sleep(0.3);
}
