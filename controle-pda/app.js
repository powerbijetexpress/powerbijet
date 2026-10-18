/**
 * PAINEL DE CONTROLE DE PDAs - LÓGICA DA APLICAÇÃO (PERSISTÊNCIA 100% NO BANCO DE DADOS & REPORT DE INÍCIO)
 */

const STORAGE_KEYS = {
  REGISTROS: 'pda_control_registros_v1',
  FROTA: 'pda_control_frota_v1',
  AUTORIZADOS: 'pda_control_autorizados_v1',
  REPORT_INICIO: 'pda_control_report_inicio_v1'
};

// Lista de candidatos de URL da API com detecção automática de IP e fallback inteligente
function getApiCandidates() {
  const list = [];
  const custom = (localStorage.getItem('pda_custom_api_url') || '').trim();
  if (custom) list.push(custom.replace(/\/+$/, ''));

  if (typeof window !== 'undefined') {
    const loc = window.location;
    const proto = loc.protocol || '';
    const host = loc.hostname || '';

    // SE O SISTEMA ESTIVER ONLINE (Render, HTTPS ou HTTP em qualquer domínio/porta):
    // O caminho relativo '' é a MESMA origem do servidor Flask/Render e DEVE SER SEMPRE A 1ª OPÇÃO!
    if (proto === 'http:' || proto === 'https:') {
      list.push(''); // Mesma origem no Render (ex: https://xxx.onrender.com/api/pda/data)
    }

    // Se estiver em ambiente local de desenvolvimento (ex: Live Server)
    if (host === 'localhost' || host === '127.0.0.1') {
      list.push('http://localhost:5000');
      list.push('http://127.0.0.1:5000');
    }

    // Endereço de rede local (apenas se não estiver em HTTPS para evitar erro de Mixed Content)
    if (proto !== 'https:') {
      list.push('http://192.168.0.150:5000');
      if (host && host !== 'localhost' && host !== '127.0.0.1') {
        list.push(`http://${host}:5000`);
      }
    }
  }
  return Array.from(new Set(list));
}

let CURRENT_API_BASE = getApiCandidates()[0] || '';



// Report de Início da Operação Padrão
const DEFAULT_REPORT_INICIO = {
  data_ref: "*06/10/2026*",
  backlog_inicial: "692",
  volume_previsto: "53.903",
  inicio_operacao: "15:11",
  clts_presentes_18h: "32",
  absenteismo_18h: "4",
  clts_presentes_22h: "—",
  absenteismo_22h: "—",
  clts_presentes_23h: "—",
  absenteismo_23h: "—",
  diaristas_solicitados_15h: "20",
  diaristas_presentes_15h: "18",
  diaristas_solicitados_20h: "10",
  diaristas_presentes_20h: "—",
  phd_previsto: "—",
  obs_falta_injustificada: "4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA",
  obs_atestados: "N/A",
  obs_pontos_atencao: "N/A",
  raw_text: `📊 REPORT DE INÍCIO DA OPERAÇÃO

📅 Data: *06/10/2026*

📦 Backlog Inicial: 692
📦 Volume previsto: 53.903
🕒 Início da operação: 15:11
👥 CLTs presentes 18hrs: 32
❌ Absenteísmo 18hrs: 4
👥 CLTs presentes 22hrs: —
❌ Absenteísmo 22hrs: —
👷 Diaristas solicitados (15:00): 20
✅ Diaristas presentes (15:00): 18
👷 Diaristas solicitados (20:00): 10
✅ Diaristas presentes (20:00): —
📈 PHD previsto: —


📝 Observações:

- Falta injustificada: 4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA

- Atestados: N/A

- Pontos de atenção: N/A`
};

// Dados Padrão Iniciais Atualizados (4 Turnos)
const DEFAULT_AUTORIZADOS = {
  '08h': ['GIOVANNY', 'JOAO MENDES'],
  '14h': ['Vinicius Nascimento'],
  '15h': ['PABLO', 'CRISTIANE', 'ISABELLA', 'ANGELA', 'BRUNO', 'GABRIEL', 'JULIANA', 'VITORIA', 'LUAN'],
  '23h': ['Matheus Nascimento', 'Kaue pedrozo', 'Amanda', 'Gabriel oliveira', 'William', 'João Pedro']
};

const DEFAULT_SETORES = [
  'Expedição',
  'Lacre',
  'Esteira',
  'Recebimento',
  'Avaria',
  'Erro de triagem',
  'Criação de lote',
  'DROP'
];

class PDAControlApp {
  constructor() {
    this.registros = [];
    this.frota = [];
    this.autorizados = { ...DEFAULT_AUTORIZADOS };
    this.reportInicio = { ...DEFAULT_REPORT_INICIO };
    this.isOnline = false;
    this.isSyncing = false;
    this.lastDataHash = '';
    this.syncChannel = null;
    this.quadroFilterStatus = 'TODOS';
    this.chartPizzaSetoresEmUso = null;
    this.chartSetor = null;
    this.chartTurno = null;

    this.init();
  }

  normalizeStatus(status) {
    if (!status) return 'Disponível';
    const s = String(status).trim().toLowerCase();
    if (s.includes('devol') || s.includes('entreg')) return 'Devolvido';
    if (s.includes('uso') || s.includes('ocup') || s.includes('retir')) return 'Em Uso';
    if (s.includes('avar') || s.includes('manut') || s.includes('quebr') || s.includes('defe')) return 'Avaria';
    if (s.includes('disp') || s.includes('livr') || s.includes('ok')) return 'Disponível';
    return 'Disponível';
  }

  init() {
    this.loadStorage();
    this.ensure40Pdas();
    this.startClock();
    this.updateResponsaveisByTurno('15h');
    this.renderAll();
    this.setupEventListeners();
    this.setupRealtimeSync();

    // Busca inicial imediata do Banco de Dados
    this.fetchFromDatabase();

    // Polling contínuo de alta frequência (a cada 1.2s) para sincronização em tempo real entre computadores e celulares
    setInterval(() => this.fetchFromDatabase(true), 1200);

    // Sincroniza imediatamente quando a aba ganha foco ou visibilidade
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        this.fetchFromDatabase(true);
      }
    });
    window.addEventListener('focus', () => {
      this.fetchFromDatabase(true);
    });
  }

  setupRealtimeSync() {
    // Canal Broadcast em tempo real para sincronização instantânea (0ms) entre todas as abas e janelas abertas
    try {
      if (typeof BroadcastChannel !== 'undefined') {
        this.syncChannel = new BroadcastChannel('dc_bauru_pda_realtime_sync');
        this.syncChannel.onmessage = (event) => {
          if (event.data && event.data.type === 'PDA_DATA_CHANGED') {
            this.handleIncomingBroadcast(event.data.payload);
          }
        };
      }
    } catch (e) {}

    // Listener de Storage (localStorage) como garantia secundária de sincronização entre abas
    window.addEventListener('storage', (e) => {
      if (e.key && Object.values(STORAGE_KEYS).includes(e.key)) {
        this.loadStorage();
        this.renderAll();
      }
    });
  }

  broadcastChange() {
    const payload = {
      frota: this.frota,
      registros: this.registros,
      autorizados: this.autorizados,
      reportInicio: this.reportInicio,
      timestamp: Date.now()
    };
    if (this.syncChannel) {
      try {
        this.syncChannel.postMessage({ type: 'PDA_DATA_CHANGED', payload });
      } catch (e) {}
    }
    try {
      if (window.parent && window.parent !== window) {
        window.parent.postMessage({ action: 'pdaDataUpdated', payload }, '*');
      }
    } catch (e) {}
  }

  handleIncomingBroadcast(payload) {
    if (!payload) return;
    if (Array.isArray(payload.frota)) this.frota = payload.frota;
    if (Array.isArray(payload.registros)) this.registros = payload.registros;
    if (payload.autorizados) this.autorizados = payload.autorizados;
    if (payload.reportInicio) this.reportInicio = payload.reportInicio;
    this.renderAll();
  }

  // Garantir que os novos turnos e novos responsáveis existam
  ensureNewTurnosAndSectors() {
    let changed = false;
    if (!this.autorizados['08h']) {
      this.autorizados['08h'] = ['GIOVANNY', 'JOAO MENDES'];
      changed = true;
    }
    if (!this.autorizados['14h']) {
      this.autorizados['14h'] = ['Vinicius Nascimento'];
      changed = true;
    }
    if (!this.autorizados['15h']) {
      this.autorizados['15h'] = ['PABLO', 'CRISTIANE', 'ISABELLA', 'ANGELA', 'BRUNO', 'GABRIEL', 'JULIANA', 'VITORIA', 'LUAN'];
      changed = true;
    } else {
      ['JULIANA', 'VITORIA', 'LUAN'].forEach(nome => {
        if (!this.autorizados['15h'].includes(nome)) {
          this.autorizados['15h'].push(nome);
          changed = true;
        }
      });
    }
    if (changed) {
      this.saveAutorizados(false);
    }
  }

  normalizePdaCode(code) {
    if (!code) return '';
    const digits = String(code).replace(/\D/g, '');
    if (digits === '') return String(code).trim().toUpperCase();
    const num = parseInt(digits, 10);
    return `PDA-${num < 10 ? '0' + num : num}`;
  }

  // Garantir que exatamente os 51 PDAs (PDA-00 a PDA-50) existam na frota sem duplicatas
  ensure51Pdas() {
    let changed = false;

    // 1. Normalizar códigos existentes e remover duplicatas
    const uniqueMap = new Map();
    (this.frota || []).forEach(item => {
      if (!item || !item.codigo) return;
      const normCod = this.normalizePdaCode(item.codigo);
      if (!uniqueMap.has(normCod)) {
        uniqueMap.set(normCod, {
          codigo: normCod,
          status: this.normalizeStatus(item.status),
          obs: item.obs || 'OK'
        });
      } else {
        changed = true;
      }
    });

    // 2. Garantir PDA-00 até PDA-50 (51 PDAs)
    for (let i = 0; i <= 50; i++) {
      const num = i < 10 ? `0${i}` : `${i}`;
      const codigo = `PDA-${num}`;
      if (!uniqueMap.has(codigo)) {
        uniqueMap.set(codigo, {
          codigo: codigo,
          status: 'Disponível',
          obs: 'OK'
        });
        changed = true;
      }
    }

    // 3. Ordenar numericamente 0..50
    this.frota = Array.from(uniqueMap.values()).sort((a, b) => {
      const numA = parseInt(a.codigo.replace(/\D/g, '') || '0', 10);
      const numB = parseInt(b.codigo.replace(/\D/g, '') || '0', 10);
      return numA - numB;
    });

    // Normalizar referências nos registros também
    if (Array.isArray(this.registros)) {
      this.registros.forEach(r => {
        if (r.pda) {
          const norm = this.normalizePdaCode(r.pda);
          if (r.pda !== norm) {
            r.pda = norm;
            changed = true;
          }
        }
      });
    }

    if (changed) {
      this.saveFrota(false);
    }
  }

  ensure40Pdas() {
    return this.ensure51Pdas();
  }

  initDefaultFrota() {
    this.frota = [];
    for (let i = 0; i <= 50; i++) {
      const num = i < 10 ? `0${i}` : `${i}`;
      this.frota.push({
        codigo: `PDA-${num}`,
        status: 'Disponível',
        obs: 'OK'
      });
    }
  }

  initSampleRegistros() {
    this.registros = [];
  }

  // Carregar dados locais (Cache Inicial Rápido para não travar tela)
  loadStorage() {
    const regRaw = localStorage.getItem(STORAGE_KEYS.REGISTROS);
    const frotaRaw = localStorage.getItem(STORAGE_KEYS.FROTA);
    const autRaw = localStorage.getItem(STORAGE_KEYS.AUTORIZADOS);
    const repRaw = localStorage.getItem(STORAGE_KEYS.REPORT_INICIO);

    if (autRaw) {
      try { 
        this.autorizados = JSON.parse(autRaw); 
      } catch(e) { 
        this.autorizados = { ...DEFAULT_AUTORIZADOS }; 
      }
    } else {
      this.autorizados = { ...DEFAULT_AUTORIZADOS };
    }

    if (frotaRaw) {
      try { 
        this.frota = JSON.parse(frotaRaw);
        if (!Array.isArray(this.frota) || this.frota.length === 0) {
          this.initDefaultFrota();
        } else {
          this.frota.forEach(p => p.status = this.normalizeStatus(p.status));
        }
      } catch(e) { 
        this.initDefaultFrota(); 
      }
    } else {
      this.initDefaultFrota();
    }

    if (regRaw) {
      try { 
        this.registros = JSON.parse(regRaw); 
        if (!Array.isArray(this.registros)) {
          this.registros = [];
        } else {
          this.registros.forEach(r => r.status = this.normalizeStatus(r.status));
        }
      } catch(e) { 
        this.registros = []; 
      }
    } else {
      this.registros = [];
    }

    if (repRaw) {
      try { this.reportInicio = JSON.parse(repRaw); } catch(e) { this.reportInicio = { ...DEFAULT_REPORT_INICIO }; }
    } else {
      this.reportInicio = { ...DEFAULT_REPORT_INICIO };
    }
  }

  applyServerData(data) {
    if (!data) return;

    const srvFrota = data.frota || [];
    const srvAut = data.autorizados || {};
    const srvReg = data.registros || [];
    const srvRep = data.report_inicio;

    const currentHash = JSON.stringify({
      f: srvFrota,
      r: srvReg,
      a: srvAut,
      rep: srvRep
    });

    // Se o hash é idêntico ao atual, não é necessário reconstruir o DOM
    if (currentHash === this.lastDataHash) {
      return;
    }
    this.lastDataHash = currentHash;

    if (Array.isArray(srvFrota) && srvFrota.length > 0) {
      srvFrota.forEach(p => p.status = this.normalizeStatus(p.status));
      this.frota = srvFrota;
      this.ensure40Pdas();
      localStorage.setItem(STORAGE_KEYS.FROTA, JSON.stringify(this.frota));
    }

    if (srvAut && Object.keys(srvAut).length > 0) {
      this.autorizados = srvAut;
      localStorage.setItem(STORAGE_KEYS.AUTORIZADOS, JSON.stringify(this.autorizados));
    }

    if (Array.isArray(srvReg)) {
      srvReg.forEach(r => r.status = this.normalizeStatus(r.status));
      this.registros = srvReg;
      localStorage.setItem(STORAGE_KEYS.REGISTROS, JSON.stringify(this.registros));
    }

    if (srvRep && typeof srvRep === 'object') {
      this.reportInicio = srvRep;
      localStorage.setItem(STORAGE_KEYS.REPORT_INICIO, JSON.stringify(this.reportInicio));
    }

    this.renderAll();
    this.broadcastChange();
  }

  // Método unificado e resiliente de comunicação com a API (com rotação automática de IP/porta)
  async requestApi(path, options = {}) {
    const candidates = CURRENT_API_BASE !== null 
      ? [CURRENT_API_BASE, ...getApiCandidates().filter(c => c !== CURRENT_API_BASE)] 
      : getApiCandidates();

    for (const base of candidates) {
      try {
        const url = `${base}${path}`;
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 3500);
        const resp = await fetch(url, { ...options, signal: controller.signal });
        clearTimeout(timeoutId);

        if (resp.ok) {
          CURRENT_API_BASE = base;
          this.isOnline = true;
          this.updateDbStatusBadge(true);
          return await resp.json();
        }
      } catch (err) {
        // Tenta o próximo candidato
      }
    }
    this.isOnline = false;
    this.updateDbStatusBadge(false);
    throw new Error('Servidor central offline ou inacessível.');
  }

  // Conexão e Sincronização 100% com o Banco de Dados (SQLite/PostgreSQL) - FONTE ÚNICA DA VERDADE
  async fetchFromDatabase(silent = false) {
    if (this.isSyncing) return;
    try {
      const json = await this.requestApi(`/api/pda/data?_=${Date.now()}`, {
        method: 'GET',
        headers: { 
          'Accept': 'application/json',
          'Cache-Control': 'no-cache'
        }
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
        if (!silent) {
          console.log('[PDA] Sincronizado com o Banco de Dados via:', CURRENT_API_BASE || 'mesma origem');
        }
      }
    } catch (err) {
      if (!silent) {
        console.warn('[PDA] Conexão com API indisponível (usando dados locais):', err.message);
      }
    }
  }

  updateDbStatusBadge(online) {
    const badge = document.getElementById('dbStatusBadge');
    const dot = document.getElementById('dbStatusDot');
    const text = document.getElementById('dbStatusText');
    if (!badge || !text) return;

    if (online) {
      badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-950/40 text-emerald-300 border border-emerald-500/30 cursor-pointer';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-emerald-400 animate-pulse';
      text.innerText = 'Online (BD Sincronizado)';
      badge.title = `Modo Online: Conectado ao Servidor Central (${CURRENT_API_BASE || 'localhost'}). Clique para ver/alterar IP.`;
    } else {
      badge.className = 'flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-rose-950/60 text-rose-300 border border-rose-500/50 cursor-pointer animate-pulse';
      if (dot) dot.className = 'w-2 h-2 rounded-full bg-rose-400';
      text.innerText = 'Offline (Sem Servidor)';
      badge.title = 'Atenção: Não foi possível conectar ao Servidor Central. Clique para configurar o IP.';
    }
  }

  showServerConfigModal() {
    const current = localStorage.getItem('pda_custom_api_url') || CURRENT_API_BASE || 'http://192.168.0.150:5000';
    const newUrl = prompt(`Configuração do Servidor Central (DC Bauru):\n\nStatus: ${this.isOnline ? '🟢 ONLINE (Conectado)' : '🔴 OFFLINE (Sem Conexão)'}\nServidor Atual: ${current}\n\nSe você estiver no Tablet/Celular e o IP do computador mudou, digite o endereço do servidor abaixo (ex: http://192.168.0.150:5000):`, current);
    if (newUrl !== null && newUrl.trim() !== '') {
      const cleanUrl = newUrl.trim().replace(/\/+$/, '');
      localStorage.setItem('pda_custom_api_url', cleanUrl);
      CURRENT_API_BASE = cleanUrl;
      this.showToast(`Endereço do servidor definido como: ${cleanUrl}. Reconectando...`, 'info');
      this.fetchFromDatabase();
    }
  }

  async syncToDatabase(silent = false) {
    this.isSyncing = true;
    try {
      const payload = {
        frota: this.frota.map(p => ({ ...p, status: this.normalizeStatus(p.status) })),
        autorizados: this.autorizados,
        registros: this.registros.map(r => ({ ...r, status: this.normalizeStatus(r.status) })),
        report_inicio: this.reportInicio
      };
      const json = await this.requestApi('/api/pda/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (json && json.data) {
        this.applyServerData(json.data);
      }
    } catch (e) {
      // Offline fallback
    } finally {
      this.isSyncing = false;
    }
  }

  saveRegistros(sync = true) {
    localStorage.setItem(STORAGE_KEYS.REGISTROS, JSON.stringify(this.registros));
    this.broadcastChange();
    if (sync) this.syncToDatabase(true);
  }

  saveFrota(sync = true) {
    localStorage.setItem(STORAGE_KEYS.FROTA, JSON.stringify(this.frota));
    this.broadcastChange();
    if (sync) this.syncToDatabase(true);
  }

  saveAutorizados(sync = true) {
    localStorage.setItem(STORAGE_KEYS.AUTORIZADOS, JSON.stringify(this.autorizados));
    this.broadcastChange();
    if (sync) this.syncToDatabase(true);
  }

  saveReportInicioToStorage(sync = true) {
    localStorage.setItem(STORAGE_KEYS.REPORT_INICIO, JSON.stringify(this.reportInicio));
    this.broadcastChange();
    if (sync) {
      this.requestApi('/api/pda/report_inicio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(this.reportInicio)
      }).catch(() => {});
    }
  }

  // Relógio
  startClock() {
    const updateTime = () => {
      const now = new Date();
      const clockEl = document.getElementById('liveClock');
      const dateEl = document.getElementById('liveDate');
      if (clockEl) clockEl.innerText = now.toLocaleTimeString('pt-BR');
      if (dateEl) dateEl.innerText = now.toLocaleDateString('pt-BR', { weekday: 'short', day: '2-digit', month: '2-digit', year: 'numeric' });
    };
    updateTime();
    setInterval(updateTime, 1000);
  }

  // Atualizar Lista de Responsáveis ao Mudar Turno (08h, 14h, 15h, 23h)
  updateResponsaveisByTurno(turno) {
    const select = document.getElementById('selectResponsavel');

    ['08h', '14h', '15h', '23h'].forEach(t => {
      const lbl = document.getElementById(`labelTurno${t}`);
      if (lbl) {
        if (t === turno) {
          lbl.className = 'flex items-center justify-center gap-1.5 p-2 border rounded-lg cursor-pointer font-medium text-xs text-slate-900 bg-slate-100 border-slate-400';
        } else {
          lbl.className = 'flex items-center justify-center gap-1.5 p-2 border rounded-lg cursor-pointer font-medium text-xs text-slate-600 bg-white border-slate-200';
        }
      }
    });

    if (!select) return;

    select.innerHTML = '<option value="">-- Selecione o Responsável --</option>';
    const lista = this.autorizados[turno] || [];

    lista.forEach(nome => {
      const opt = document.createElement('option');
      opt.value = nome;
      opt.innerText = nome;
      select.appendChild(opt);
    });
  }

  // Dropdown Form com preservação do valor selecionado
  populatePdaSelect() {
    const selectPda = document.getElementById('selectPda');
    if (!selectPda) return;
    const currentVal = selectPda.value;

    selectPda.innerHTML = '<option value="">-- Selecione um PDA Disponível --</option>';
    const disponiveis = this.frota.filter(p => this.normalizeStatus(p.status) === 'Disponível');
    disponiveis.sort((a, b) => {
      const numA = parseInt(a.codigo.replace(/\D/g, '') || '0', 10);
      const numB = parseInt(b.codigo.replace(/\D/g, '') || '0', 10);
      return numA - numB;
    });

    disponiveis.forEach(pda => {
      const opt = document.createElement('option');
      opt.value = pda.codigo;
      opt.innerText = `${pda.codigo} (Disponível)`;
      selectPda.appendChild(opt);
    });

    if (currentVal && disponiveis.some(p => p.codigo === currentVal)) {
      selectPda.value = currentVal;
    }
  }

  // --- QUADRO DOS PDAS (PDA-00 a PDA-50) ---
  filterQuadro(status) {
    this.quadroFilterStatus = status;

    const btnMappings = [
      { id: 'filterBtnTODOS', match: 'TODOS' },
      { id: 'filterBtnDisponivel', match: 'Disponível' },
      { id: 'filterBtnEmUso', match: 'Em Uso' },
      { id: 'filterBtnAvaria', match: 'Avaria' }
    ];

    btnMappings.forEach(b => {
      const btn = document.getElementById(b.id);
      if (btn) {
        const isMatch = (b.match === 'TODOS' && status === 'TODOS') ||
                        (b.match !== 'TODOS' && this.normalizeStatus(b.match) === this.normalizeStatus(status));
        if (isMatch) {
          btn.className = 'px-2.5 py-1 rounded font-semibold bg-white text-slate-800 shadow-sm border border-slate-300';
        } else {
          btn.className = 'px-2.5 py-1 rounded font-semibold text-slate-500 hover:text-slate-800';
        }
      }
    });

    this.renderQuadro36();
  }

  renderQuadro36() {
    const container = document.getElementById('grid36PdasContainer');
    if (!container) return;

    const searchTerm = (document.getElementById('searchQuadroPda')?.value || '').trim().toLowerCase();

    // Ordenar do PDA-00 ao PDA-50
    let ordenados = [...this.frota];
    ordenados.sort((a, b) => {
      const numA = parseInt(a.codigo.replace(/\D/g, '') || '0', 10);
      const numB = parseInt(b.codigo.replace(/\D/g, '') || '0', 10);
      return numA - numB;
    });

    let filtrados = ordenados.filter(pda => {
      const normStatus = this.normalizeStatus(pda.status);
      const matchSearch = pda.codigo.toLowerCase().includes(searchTerm);
      const matchStatus = (this.quadroFilterStatus === 'TODOS') ||
                          (this.normalizeStatus(this.quadroFilterStatus) === normStatus);
      return matchSearch && matchStatus;
    });

    if (filtrados.length === 0) {
      container.innerHTML = `<div class="col-span-full text-center py-10 text-slate-400 font-medium text-xs">Nenhum PDA encontrado com os filtros selecionados.</div>`;
      return;
    }

    let html = '';
    filtrados.forEach(pda => {
      const normStatus = this.normalizeStatus(pda.status);
      const regAtual = normStatus === 'Em Uso' ? this.registros.find(r => r.pda === pda.codigo && this.normalizeStatus(r.status) === 'Em Uso') : null;

      if (normStatus === 'Em Uso') {
        const dataRet = regAtual ? new Date(regAtual.dataRetirada) : null;
        let tempoTxt = '--';
        if (dataRet && !isNaN(dataRet.getTime())) {
          const diffMs = Math.max(0, new Date() - dataRet);
          const hrs = Math.floor(diffMs / (1000 * 60 * 60));
          const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
          tempoTxt = `${hrs}h ${mins}m`;
        }

        html += `
          <div class="bg-slate-50 rounded-xl border border-amber-300 p-3 shadow-xs transition flex flex-col justify-between space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-sm font-bold text-slate-900 tracking-tight">${pda.codigo}</span>
              <span class="w-2 h-2 rounded-full bg-amber-500"></span>
            </div>
            <div class="text-xs text-slate-700 space-y-0.5">
              <span class="text-[10px] font-bold text-amber-800 bg-amber-100 px-1.5 py-0.5 rounded inline-block mb-0.5">${regAtual ? regAtual.setor : 'Em Uso'}</span>
              <p class="font-semibold text-slate-900 truncate text-[10px]">${regAtual ? regAtual.responsavel : 'Em Uso'}</p>
              <p class="text-[9px] text-slate-400">T. ${regAtual ? regAtual.turno : '--'} &bull; ${tempoTxt}</p>
            </div>
            <button onclick="pdaApp.openModalDevolucao('${regAtual ? regAtual.id : pda.codigo}')" class="w-full bg-amber-700 hover:bg-amber-800 text-white font-medium py-1.5 px-2 rounded-lg text-xs transition flex items-center justify-center gap-1">
              <i class="fa-solid fa-rotate-left text-[10px]"></i> Devolver
            </button>
          </div>
        `;
      } else if (normStatus === 'Avaria') {
        html += `
          <div class="bg-slate-50 rounded-xl border border-rose-300 p-3 shadow-xs transition flex flex-col justify-between space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-sm font-bold text-slate-900 tracking-tight">${pda.codigo}</span>
              <span class="w-2 h-2 rounded-full bg-rose-500"></span>
            </div>
            <div class="text-xs text-rose-800 space-y-0.5">
              <span class="text-[10px] font-semibold text-rose-800 bg-rose-50 px-1.5 py-0.5 rounded inline-block mb-0.5">Avaria</span>
              <p class="text-[9px] text-slate-500 truncate" title="${pda.obs || 'Manutenção'}">${pda.obs || 'Manutenção'}</p>
            </div>
            <button onclick="pdaApp.toggleStatusPda('${pda.codigo}')" class="w-full bg-slate-600 hover:bg-slate-700 text-white font-medium py-1.5 px-2 rounded-lg text-xs transition flex items-center justify-center gap-1">
              <i class="fa-solid fa-wrench text-[10px]"></i> Liberar
            </button>
          </div>
        `;
      } else {
        // Disponível (default fallback para nunca deixar vazio)
        html += `
          <div class="bg-white rounded-xl border border-slate-200 p-3 shadow-xs hover:border-emerald-300 hover:shadow-sm transition flex flex-col justify-between space-y-2.5">
            <div class="flex items-center justify-between">
              <span class="text-sm font-bold text-slate-800 tracking-tight">${pda.codigo}</span>
              <span class="w-2 h-2 rounded-full bg-emerald-500"></span>
            </div>
            <div>
              <span class="text-[10px] font-semibold text-emerald-800 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200 inline-block mb-0.5">Disponível</span>
              <p class="text-[9px] text-slate-400">Estoque</p>
            </div>
            <button onclick="pdaApp.openModalRetiradaRapida('${pda.codigo}')" class="w-full bg-slate-700 hover:bg-slate-800 text-white font-medium py-1.5 px-2 rounded-lg text-xs transition flex items-center justify-center gap-1">
              <i class="fa-solid fa-arrow-right-from-bracket text-[10px]"></i> Retirar
            </button>
          </div>
        `;
      }
    });

    container.innerHTML = html;
  }

  // MODAL DE RETIRADA RÁPIDA
  openModalRetiradaRapida(codigoPda) {
    const elCod = document.getElementById('modalRetiradaPdaCodigo');
    const elHid = document.getElementById('modalRetiradaPdaHidden');
    const elObs = document.getElementById('inputModalObs');
    if (elCod) elCod.innerText = codigoPda;
    if (elHid) elHid.value = codigoPda;
    if (elObs) elObs.value = '';
    
    const r15 = document.querySelector('input[name="modalTurno"][value="15h"]');
    if (r15) r15.checked = true;

    this.updateModalResponsaveis('15h');
    document.getElementById('modalRetiradaRapida')?.classList.remove('hidden');
  }

  closeModalRetiradaRapida() {
    document.getElementById('modalRetiradaRapida')?.classList.add('hidden');
  }

  updateModalResponsaveis(turno) {
    const select = document.getElementById('selectModalResponsavel');

    ['08h', '14h', '15h', '23h'].forEach(t => {
      const lbl = document.getElementById(`labelModalTurno${t}`);
      if (lbl) {
        if (t === turno) {
          lbl.className = 'flex items-center justify-center gap-1.5 p-2 border rounded-lg cursor-pointer font-medium text-xs text-slate-900 bg-slate-100 border-slate-400';
        } else {
          lbl.className = 'flex items-center justify-center gap-1.5 p-2 border rounded-lg cursor-pointer font-medium text-xs text-slate-600 bg-white border-slate-200';
        }
      }
    });

    if (!select) return;
    select.innerHTML = '<option value="">-- Selecione o Responsável --</option>';

    const lista = this.autorizados[turno] || [];
    lista.forEach(nome => {
      const opt = document.createElement('option');
      opt.value = nome;
      opt.innerText = nome;
      select.appendChild(opt);
    });
  }

  async confirmRetiradaRapida(e) {
    if (e && e.preventDefault) e.preventDefault();

    const pdaCodigo = (document.getElementById('modalRetiradaPdaHidden')?.value || '').trim();
    const turno = document.querySelector('input[name="modalTurno"]:checked')?.value || '15h';
    const responsavel = (document.getElementById('selectModalResponsavel')?.value || '').trim();
    const setor = (document.getElementById('selectModalSetor')?.value || '').trim();
    const obs = (document.getElementById('inputModalObs')?.value || '').trim();

    if (!responsavel || !setor || !pdaCodigo) {
      this.showToast('Preencha os campos obrigatórios (Responsável e Setor).', 'warning');
      return;
    }

    const novoRegistro = {
      id: 'REG-' + Date.now(),
      pda: pdaCodigo,
      turno: turno,
      responsavel: responsavel,
      setor: setor,
      dataRetirada: new Date().toISOString(),
      dataDevolucao: null,
      status: 'Em Uso',
      obsRetirada: obs || null,
      obsDevolucao: null,
      estadoDevolucao: null
    };

    this.registros.unshift(novoRegistro);

    const pdaItem = this.frota.find(p => p.codigo === pdaCodigo);
    if (pdaItem) {
      pdaItem.status = 'Em Uso';
      pdaItem.obs = 'Em Uso';
    }

    this.saveRegistros(false);
    this.saveFrota(false);

    this.closeModalRetiradaRapida();
    this.renderAll();

    // Persiste imediatamente no Banco de Dados SQLite/PostgreSQL
    try {
      const json = await this.requestApi('/api/pda/registro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(novoRegistro)
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
        this.showToast(`Retirada do ${pdaCodigo} sincronizada no Banco Central!`, 'success');
      }
    } catch (err) {
      this.showToast(`Retirada salva localmente no aparelho (Servidor Offline).`, 'warning');
      this.syncToDatabase(true);
    }
  }

  async handleRetirada(e) {
    if (e && e.preventDefault) e.preventDefault();

    const turno = document.querySelector('input[name="turno"]:checked')?.value || '15h';
    const responsavel = (document.getElementById('selectResponsavel')?.value || '').trim();
    const setor = (document.getElementById('selectSetor')?.value || '').trim();
    const pdaCodigo = (document.getElementById('selectPda')?.value || '').trim();
    const obsRetirada = (document.getElementById('inputObsRetirada')?.value || '').trim();

    if (!responsavel || !setor || !pdaCodigo) {
      this.showToast('Por favor, preencha todos os campos obrigatórios (Responsável, Setor e PDA).', 'warning');
      return;
    }

    const novoRegistro = {
      id: 'REG-' + Date.now(),
      pda: pdaCodigo,
      turno: turno,
      responsavel: responsavel,
      setor: setor,
      dataRetirada: new Date().toISOString(),
      dataDevolucao: null,
      status: 'Em Uso',
      obsRetirada: obsRetirada || null,
      obsDevolucao: null,
      estadoDevolucao: null
    };

    this.registros.unshift(novoRegistro);

    const pdaItem = this.frota.find(p => p.codigo === pdaCodigo);
    if (pdaItem) {
      pdaItem.status = 'Em Uso';
      pdaItem.obs = 'Em Uso';
    }

    this.saveRegistros(false);
    this.saveFrota(false);

    const form = document.getElementById('formRetirada');
    if (form) form.reset();

    const rTurno = document.querySelector(`input[name="turno"][value="${turno}"]`);
    if (rTurno) rTurno.checked = true;
    this.updateResponsaveisByTurno(turno);

    this.renderAll();

    // Persiste imediatamente no Banco de Dados SQLite/PostgreSQL
    try {
      const json = await this.requestApi('/api/pda/registro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(novoRegistro)
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
        this.showToast(`Retirada do ${pdaCodigo} sincronizada no Banco Central!`, 'success');
      }
    } catch (err) {
      this.showToast(`Retirada salva localmente no aparelho (Servidor Offline).`, 'warning');
      this.syncToDatabase(true);
    }
  }

  openModalDevolucao(registroIdOrPda) {
    if (!registroIdOrPda) return;

    let reg = this.registros.find(r => r.id === registroIdOrPda);
    if (!reg) {
      reg = this.registros.find(r => r.pda === registroIdOrPda && this.normalizeStatus(r.status) === 'Em Uso');
    }
    if (!reg) {
      reg = this.registros.find(r => r.pda === registroIdOrPda);
    }

    const pdaCodigo = reg ? reg.pda : registroIdOrPda;
    const regId = reg ? reg.id : ('REG-' + Date.now());

    const elId = document.getElementById('modalRegistroId');
    const elPda = document.getElementById('modalPdaCodigo');
    const elResp = document.getElementById('modalPdaResponsavel');
    const elTurno = document.getElementById('modalPdaTurno');
    const elSetor = document.getElementById('modalPdaSetor');
    const elDataRet = document.getElementById('modalPdaDataRetirada');
    const elObs = document.getElementById('modalObsDevolucao');
    const elEstado = document.getElementById('modalEstadoDevolucao');

    if (elId) elId.value = regId;
    if (elPda) elPda.innerText = pdaCodigo;
    if (elResp) elResp.innerText = reg ? reg.responsavel : 'Em Uso';
    if (elTurno) elTurno.innerText = reg ? `Turno ${reg.turno}` : 'Turno 15h';
    if (elSetor) elSetor.innerText = reg ? reg.setor : 'Expedição';
    if (elDataRet) elDataRet.innerText = (reg && reg.dataRetirada) ? new Date(reg.dataRetirada).toLocaleString('pt-BR') : new Date().toLocaleString('pt-BR');
    if (elObs) elObs.value = '';
    if (elEstado) elEstado.value = 'Perfeito Estado';

    document.getElementById('modalDevolucao')?.classList.remove('hidden');
  }

  closeModalDevolucao() {
    document.getElementById('modalDevolucao')?.classList.add('hidden');
  }

  async confirmDevolucao(e) {
    if (e && e.preventDefault) e.preventDefault();

    const regId = document.getElementById('modalRegistroId')?.value || '';
    const pdaCodigo = (document.getElementById('modalPdaCodigo')?.innerText || '').trim();
    const estado = document.getElementById('modalEstadoDevolucao')?.value || 'Perfeito Estado';
    const obsDevolucao = (document.getElementById('modalObsDevolucao')?.value || '').trim();

    let reg = this.registros.find(r => r.id === regId);
    if (!reg && pdaCodigo) {
      reg = this.registros.find(r => r.pda === pdaCodigo && this.normalizeStatus(r.status) === 'Em Uso');
    }

    if (!reg) {
      reg = {
        id: regId || ('REG-' + Date.now()),
        pda: pdaCodigo,
        turno: (document.getElementById('modalPdaTurno')?.innerText || '15h').replace('Turno ', '').trim() || '15h',
        responsavel: (document.getElementById('modalPdaResponsavel')?.innerText || 'Operador').trim(),
        setor: (document.getElementById('modalPdaSetor')?.innerText || 'Expedição').trim(),
        dataRetirada: new Date().toISOString(),
        dataDevolucao: new Date().toISOString(),
        status: estado === 'Com Avaria' ? 'Avaria' : 'Devolvido',
        obsRetirada: null,
        obsDevolucao: obsDevolucao || null,
        estadoDevolucao: estado
      };
      this.registros.unshift(reg);
    } else {
      reg.dataDevolucao = new Date().toISOString();
      reg.estadoDevolucao = estado;
      reg.obsDevolucao = obsDevolucao || null;
      reg.status = (estado === 'Com Avaria') ? 'Avaria' : 'Devolvido';
    }

    const pdaItem = this.frota.find(p => p.codigo === (reg ? reg.pda : pdaCodigo));
    if (pdaItem) {
      if (estado === 'Com Avaria') {
        pdaItem.status = 'Avaria';
        pdaItem.obs = obsDevolucao || 'Danificado na devolução';
      } else {
        pdaItem.status = 'Disponível';
        pdaItem.obs = 'OK';
      }
    }

    this.saveRegistros(false);
    this.saveFrota(false);

    this.closeModalDevolucao();
    this.renderAll();

    // Persiste imediatamente no Banco de Dados SQLite/PostgreSQL
    try {
      const json = await this.requestApi('/api/pda/registro', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(reg)
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
        this.showToast(`Devolução do ${reg ? reg.pda : pdaCodigo} salva no Banco Central!`, 'success');
      }
    } catch (err) {
      this.showToast(`Devolução salva localmente no aparelho (Servidor Offline).`, 'warning');
      this.syncToDatabase(true);
    }
  }

  renderAll() {
    this.populatePdaSelect();
    this.renderKPIs();
    this.renderQuadro36();
    this.renderListaEmUso();
    this.renderHistorico();
    this.renderCharts();
    this.renderConfigLists();
  }

  renderKPIs() {
    const totalFrota = this.frota.length;
    const emUso = this.frota.filter(p => this.normalizeStatus(p.status) === 'Em Uso').length;
    const disponiveis = this.frota.filter(p => this.normalizeStatus(p.status) === 'Disponível').length;
    const avarias = this.frota.filter(p => this.normalizeStatus(p.status) === 'Avaria').length;

    const elTotal = document.getElementById('kpiTotalFrota');
    const elEmUso = document.getElementById('kpiEmUso');
    const elDisp = document.getElementById('kpiDisponiveis');
    const elAvar = document.getElementById('kpiAvarias');
    const elBadge = document.getElementById('badgeCountEmUso');

    if (elTotal) elTotal.innerText = totalFrota;
    if (elEmUso) elEmUso.innerText = emUso;
    if (elDisp) elDisp.innerText = disponiveis;
    if (elAvar) elAvar.innerText = avarias;
    if (elBadge) elBadge.innerText = `${emUso} em uso`;
  }

  renderListaEmUso() {
    const container = document.getElementById('listEmUsoContainer');
    if (!container) return;

    const ativos = this.registros.filter(r => this.normalizeStatus(r.status) === 'Em Uso');

    if (ativos.length === 0) {
      container.innerHTML = `
        <div class="text-center py-10 text-slate-400">
          <i class="fa-solid fa-box-open text-3xl mb-2 text-emerald-400"></i>
          <p class="text-xs font-medium">Nenhum PDA em uso no momento. Todos os coletores estão disponíveis no estoque!</p>
        </div>
      `;
      return;
    }

    let html = '';
    ativos.forEach(reg => {
      const dataRet = new Date(reg.dataRetirada);
      const diffMs = !isNaN(dataRet.getTime()) ? Math.max(0, new Date() - dataRet) : 0;
      const horasUso = Math.floor(diffMs / (1000 * 60 * 60));
      const minUso = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));

      const alertaHora = horasUso >= 8 ? 'border-amber-300 bg-amber-50/30' : 'border-slate-200 bg-white';

      html += `
        <div class="p-3.5 rounded-xl border ${alertaHora} shadow-xs flex flex-col sm:flex-row sm:items-center justify-between gap-2.5">
          <div class="space-y-0.5">
            <div class="flex items-center gap-2">
              <span class="text-sm font-bold text-slate-800 bg-slate-100 px-2 py-0.5 rounded border border-slate-300">${reg.pda}</span>
              <span class="text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">Turno ${reg.turno}</span>
              <span class="text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-100 text-slate-700">${reg.setor}</span>
              ${horasUso >= 8 ? '<span class="text-[10px] font-semibold bg-amber-100 text-amber-800 px-1.5 py-0.5 rounded">+8h Em Uso</span>' : ''}
            </div>
            <div class="text-xs text-slate-600">
              <p><strong>Responsável:</strong> <span class="font-medium text-slate-800">${reg.responsavel}</span></p>
              <p class="text-slate-400 text-[10px]">Retirado às ${!isNaN(dataRet.getTime()) ? dataRet.toLocaleTimeString('pt-BR', { hour: '2-digit', minute: '2-digit' }) : '--:--'} (${horasUso}h ${minUso}m atrás)</p>
            </div>
          </div>
          <div>
            <button onclick="pdaApp.openModalDevolucao('${reg.id}')" class="w-full sm:w-auto bg-amber-700 hover:bg-amber-800 text-white text-xs font-medium px-3.5 py-1.5 rounded-lg transition flex items-center justify-center gap-1.5">
              <i class="fa-solid fa-rotate-left text-xs"></i> Devolver
            </button>
          </div>
        </div>
      `;
    });

    container.innerHTML = html;
  }

  async toggleStatusPda(codigo) {
    const pda = this.frota.find(p => p.codigo === codigo);
    if (!pda) return;

    const curr = this.normalizeStatus(pda.status);
    if (curr === 'Disponível') {
      pda.status = 'Avaria';
      pda.obs = 'Manutenção preventiva/avaria';
    } else if (curr === 'Avaria') {
      pda.status = 'Disponível';
      pda.obs = 'OK';
    } else if (curr === 'Em Uso') {
      this.showToast('Este PDA está em uso! Faça a devolução primeiro.', 'warning');
      return;
    }

    this.saveFrota(false);
    this.renderAll();

    // Persiste imediatamente no Banco de Dados
    try {
      const json = await this.requestApi('/api/pda/frota', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo: pda.codigo, status: pda.status, obs: pda.obs })
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
      }
    } catch (err) {
      this.syncToDatabase(true);
    }
  }

  renderHistorico() {
    const tbody = document.getElementById('tableHistoricoBody');
    if (!tbody) return;

    const sSearch = (document.getElementById('filterHistSearch')?.value || '').toLowerCase();
    const sTurno = document.getElementById('filterHistTurno')?.value || '';
    const sSetor = document.getElementById('filterHistSetor')?.value || '';
    const sStatus = document.getElementById('filterHistStatus')?.value || '';

    let filtrados = this.registros.filter(r => {
      const normRStatus = this.normalizeStatus(r.status);
      const matchSearch = r.responsavel.toLowerCase().includes(sSearch) || r.pda.toLowerCase().includes(sSearch);
      const matchTurno = !sTurno || r.turno === sTurno;
      const matchSetor = !sSetor || r.setor === sSetor;
      const matchStatus = !sStatus || normRStatus === this.normalizeStatus(sStatus) || r.status === sStatus;
      return matchSearch && matchTurno && matchSetor && matchStatus;
    });

    if (filtrados.length === 0) {
      tbody.innerHTML = `<tr><td colspan="9" class="p-5 text-center text-slate-400 text-xs">Nenhum registro encontrado.</td></tr>`;
      return;
    }

    let html = '';
    filtrados.forEach(r => {
      const retDate = new Date(r.dataRetirada);
      const devDate = r.dataDevolucao ? new Date(r.dataDevolucao) : null;

      let duracao = '--';
      if (devDate && !isNaN(devDate.getTime()) && !isNaN(retDate.getTime())) {
        const diffMs = Math.max(0, devDate - retDate);
        const hrs = Math.floor(diffMs / (1000 * 60 * 60));
        const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        duracao = `${hrs}h ${mins}m`;
      } else if (!isNaN(retDate.getTime())) {
        const diffMs = Math.max(0, new Date() - retDate);
        const hrs = Math.floor(diffMs / (1000 * 60 * 60));
        const mins = Math.floor((diffMs % (1000 * 60 * 60)) / (1000 * 60));
        duracao = `${hrs}h ${mins}m (em andamento)`;
      }

      const normSt = this.normalizeStatus(r.status);
      let statusBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-amber-100 text-amber-800">Em Uso</span>`;
      if (normSt === 'Devolvido' || r.status === 'Devolvido') statusBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-emerald-100 text-emerald-800">Devolvido</span>`;
      if (normSt === 'Avaria') statusBadge = `<span class="px-2 py-0.5 rounded font-semibold bg-rose-100 text-rose-800">Avaria</span>`;

      html += `
        <tr class="hover:bg-slate-50 transition">
          <td class="p-2.5 font-bold text-slate-800">${r.pda}</td>
          <td class="p-2.5 font-medium text-slate-700">${r.responsavel}</td>
          <td class="p-2.5">${r.turno}</td>
          <td class="p-2.5">${r.setor}</td>
          <td class="p-2.5 text-[11px]">${!isNaN(retDate.getTime()) ? retDate.toLocaleString('pt-BR') : '--'}</td>
          <td class="p-2.5 text-[11px]">${devDate && !isNaN(devDate.getTime()) ? devDate.toLocaleString('pt-BR') : '--'}</td>
          <td class="p-2.5 text-[11px] font-semibold">${duracao}</td>
          <td class="p-2.5 text-[11px]">${statusBadge}</td>
          <td class="p-2.5 text-right space-x-1">
            ${normSt === 'Em Uso' ? `<button onclick="pdaApp.openModalDevolucao('${r.id}')" class="text-xs bg-amber-700 text-white px-2 py-0.5 rounded font-medium">Devolver</button>` : ''}
            <button onclick="pdaApp.deleteRegistro('${r.id}')" class="text-xs text-rose-500 hover:text-rose-700 p-0.5"><i class="fa-solid fa-trash"></i></button>
          </td>
        </tr>
      `;
    });

    tbody.innerHTML = html;
  }

  async deleteRegistro(id) {
    if (!confirm('Excluir este registro do histórico?')) return;
    this.registros = this.registros.filter(r => r.id !== id);
    this.saveRegistros(false);
    this.renderAll();

    try {
      const json = await this.requestApi(`/api/pda/registro?id=${encodeURIComponent(id)}`, {
        method: 'DELETE'
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
      }
    } catch (err) {
      this.syncToDatabase(true);
    }
  }

  // DASHBOARD & GRÁFICOS
  renderCharts() {
    const ctxPizza = document.getElementById('chartPizzaSetoresEmUso')?.getContext('2d');
    const ctxSetor = document.getElementById('chartSetor')?.getContext('2d');
    const ctxTurno = document.getElementById('chartTurno')?.getContext('2d');

    if (!ctxSetor || !ctxTurno) return;

    // 1. Contagem de PDAs ATUALMENTE EM USO Por Setor (Incluindo DROP)
    const emUsoPorSetor = {};
    DEFAULT_SETORES.forEach(s => emUsoPorSetor[s] = 0);

    const ativosEmUso = this.registros.filter(r => this.normalizeStatus(r.status) === 'Em Uso');
    ativosEmUso.forEach(r => {
      if (emUsoPorSetor[r.setor] !== undefined) {
        emUsoPorSetor[r.setor]++;
      } else {
        emUsoPorSetor[r.setor] = 1;
      }
    });

    if (this.chartPizzaSetoresEmUso) this.chartPizzaSetoresEmUso.destroy();
    if (ctxPizza) {
      this.chartPizzaSetoresEmUso = new Chart(ctxPizza, {
        type: 'pie',
        data: {
          labels: Object.keys(emUsoPorSetor),
          datasets: [{
            data: Object.values(emUsoPorSetor),
            backgroundColor: [
              '#475569', // Expedição
              '#059669', // Lacre
              '#d97706', // Esteira
              '#6b21a8', // Recebimento
              '#dc2626', // Avaria
              '#0891b2', // Erro de triagem
              '#4b5563', // Criação de lote
              '#0f766e'  // DROP
            ],
            borderWidth: 1.5,
            borderColor: '#ffffff'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: {
              position: 'right',
              labels: {
                font: { size: 11, weight: '500' },
                padding: 8,
                color: '#334155'
              }
            },
            tooltip: {
              callbacks: {
                label: function(context) {
                  const label = context.label || '';
                  const val = context.raw || 0;
                  const total = context.dataset.data.reduce((a, b) => a + b, 0);
                  const pct = total > 0 ? ((val / total) * 100).toFixed(1) : 0;
                  return ` ${label}: ${val} PDA(s) em uso (${pct}%)`;
                }
              }
            }
          }
        }
      });
    }

    // 2. Histórico de Retiradas Por Setor (Gráfico de Barras)
    const setorCounts = {};
    DEFAULT_SETORES.forEach(s => setorCounts[s] = 0);
    this.registros.forEach(r => {
      setorCounts[r.setor] = (setorCounts[r.setor] || 0) + 1;
    });

    if (this.chartSetor) this.chartSetor.destroy();
    this.chartSetor = new Chart(ctxSetor, {
      type: 'bar',
      data: {
        labels: Object.keys(setorCounts),
        datasets: [{
          label: 'Total de Retiradas',
          data: Object.values(setorCounts),
          backgroundColor: '#475569',
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { display: false } },
        scales: {
          y: { ticks: { color: '#64748b' }, grid: { color: '#f1f5f9' } },
          x: { ticks: { color: '#64748b' }, grid: { display: false } }
        }
      }
    });

    // 3. Contagem por Turno dos PDAs em Uso (08h, 14h, 15h, 23h)
    const t08Count = this.registros.filter(r => r.turno === '08h' && this.normalizeStatus(r.status) === 'Em Uso').length;
    const t14Count = this.registros.filter(r => r.turno === '14h' && this.normalizeStatus(r.status) === 'Em Uso').length;
    const t15Count = this.registros.filter(r => r.turno === '15h' && this.normalizeStatus(r.status) === 'Em Uso').length;
    const t23Count = this.registros.filter(r => r.turno === '23h' && this.normalizeStatus(r.status) === 'Em Uso').length;

    if (this.chartTurno) this.chartTurno.destroy();
    this.chartTurno = new Chart(ctxTurno, {
      type: 'doughnut',
      data: {
        labels: ['Turno 08h', 'Turno 14h', 'Turno 15h', 'Turno 23h'],
        datasets: [{
          data: [t08Count, t14Count, t15Count, t23Count],
          backgroundColor: ['#0284c7', '#7c3aed', '#334155', '#059669']
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { labels: { color: '#334155', font: { size: 11 } } }
        }
      }
    });
  }

  renderConfigLists() {
    ['08h', '14h', '15h', '23h'].forEach(t => {
      const listEl = document.getElementById(`listConfigTurno${t}`);
      if (listEl) {
        listEl.innerHTML = (this.autorizados[t] || []).map(n => `
          <li class="flex items-center justify-between bg-slate-50 px-2 py-1 rounded border border-slate-200">
            <span>${n}</span>
            <button onclick="pdaApp.removeResponsavel('${t}', '${n}')" class="text-rose-500 hover:text-rose-700 text-xs"><i class="fa-solid fa-xmark"></i></button>
          </li>
        `).join('');
      }
    });
  }

  async addResponsavel(e) {
    e.preventDefault();
    const turno = document.getElementById('addRespTurno').value;
    const nome = document.getElementById('addRespNome').value.trim();

    if (!nome) return;
    if (!this.autorizados[turno]) this.autorizados[turno] = [];

    if (this.autorizados[turno].includes(nome)) {
      this.showToast('Este responsável já está cadastrado para este turno.', 'warning');
      return;
    }

    this.autorizados[turno].push(nome);
    this.saveAutorizados(false);
    document.getElementById('addRespNome').value = '';
    this.renderAll();
    this.showToast(`${nome} adicionado ao Turno ${turno}!`, 'success');

    try {
      const json = await this.requestApi('/api/pda/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autorizados: this.autorizados })
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
      }
    } catch (err) {}
  }

  async removeResponsavel(turno, nome) {
    this.autorizados[turno] = (this.autorizados[turno] || []).filter(n => n !== nome);
    this.saveAutorizados(false);
    this.renderAll();
    this.showToast(`${nome} removido do Turno ${turno}.`, 'info');

    try {
      const json = await this.requestApi('/api/pda/sync', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ autorizados: this.autorizados })
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
      }
    } catch (err) {}
  }

  async addPda(e) {
    e.preventDefault();
    const codigo = document.getElementById('addPdaCodigo').value.trim().toUpperCase();

    if (!codigo) return;
    if (this.frota.some(p => p.codigo === codigo)) {
      this.showToast('Este código de PDA já existe na frota.', 'warning');
      return;
    }

    this.frota.push({ codigo: codigo, status: 'Disponível', obs: 'Novo cadastrado' });
    this.saveFrota(false);
    document.getElementById('addPdaCodigo').value = '';
    this.renderAll();
    this.showToast(`${codigo} cadastrado com sucesso!`, 'success');

    try {
      const json = await this.requestApi('/api/pda/frota', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ codigo: codigo, status: 'Disponível', obs: 'Novo cadastrado' })
      });
      if (json && json.success && json.data) {
        this.applyServerData(json.data);
      }
    } catch (err) {}
  }

  exportExcel() {
    if (typeof XLSX === 'undefined') {
      this.showToast('Biblioteca SheetJS não carregada.', 'error');
      return;
    }

    const data = this.registros.map(r => ({
      'ID Registro': r.id,
      'PDA': r.pda,
      'Turno': r.turno,
      'Responsável': r.responsavel,
      'Setor': r.setor,
      'Data Retirada': r.dataRetirada ? new Date(r.dataRetirada).toLocaleString('pt-BR') : '',
      'Data Devolução': r.dataDevolucao ? new Date(r.dataDevolucao).toLocaleString('pt-BR') : '',
      'Status': r.status,
      'Estado Devolução': r.estadoDevolucao || '',
      'Obs Retirada': r.obsRetirada || '',
      'Obs Devolução': r.obsDevolucao || ''
    }));

    const ws = XLSX.utils.json_to_sheet(data);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, "Controle_PDAs");

    XLSX.writeFile(wb, `Controle_PDAs_${new Date().toISOString().slice(0, 10)}.xlsx`);
    this.showToast('Relatório Excel exportado com sucesso!', 'success');
  }

  exportBackupJSON() {
    const backupData = {
      registros: this.registros,
      frota: this.frota,
      autorizados: this.autorizados,
      exportedAt: new Date().toISOString()
    };

    const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(backupData, null, 2));
    const dlAnchor = document.createElement('a');
    dlAnchor.setAttribute("href", dataStr);
    dlAnchor.setAttribute("download", `backup_pda_control_${new Date().toISOString().slice(0, 10)}.json`);
    document.body.appendChild(dlAnchor);
    dlAnchor.click();
    dlAnchor.remove();

    this.showToast('Backup JSON gerado!', 'success');
  }

  importBackupJSON(e) {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const data = JSON.parse(event.target.result);
        if (data.registros && data.frota && data.autorizados) {
          this.registros = data.registros;
          this.frota = data.frota;
          this.autorizados = data.autorizados;

          this.saveRegistros();
          this.saveFrota();
          this.saveAutorizados();

          this.renderAll();
          this.showToast('Dados restaurados com sucesso!', 'success');
        } else {
          this.showToast('Arquivo de backup inválido ou incompatível.', 'error');
        }
      } catch (err) {
        this.showToast('Erro ao ler o arquivo JSON.', 'error');
      }
    };
    reader.readAsText(file);
  }

  async resetSystem() {
    if (!confirm('Deseja resetar a frota para os 40 PDAs padrão?')) return;
    localStorage.removeItem(STORAGE_KEYS.REGISTROS);
    localStorage.removeItem(STORAGE_KEYS.FROTA);
    localStorage.removeItem(STORAGE_KEYS.AUTORIZADOS);
    localStorage.removeItem(STORAGE_KEYS.REPORT_INICIO);
    try {
      await this.requestApi('/api/pda/reset', { method: 'POST' });
    } catch (e) {}
    location.reload();
  }

  // --- MÉTODOS DO REPORT DE INÍCIO DA OPERAÇÃO ---
  getFormattedReportInicioText() {
    if (this.reportInicio.raw_text && this.reportInicio.raw_text.trim().length > 20) {
      return this.reportInicio.raw_text;
    }
    const r = this.reportInicio;
    let dataVal = r.data_ref || "*06/10/2026*";
    if (!dataVal.startsWith("*") && !dataVal.endsWith("*")) {
      dataVal = `*${dataVal}*`;
    }

    return `📊 REPORT DE INÍCIO DA OPERAÇÃO

📅 Data: ${dataVal}

📦 Backlog Inicial: ${r.backlog_inicial || '692'}
📦 Volume previsto: ${r.volume_previsto || '65.129'}
🕒 Início da operação: ${r.inicio_operacao || '15:11'}
👥 CLTs presentes 18hrs: ${r.clts_presentes_18h || '32'}
❌ Absenteísmo 18hrs: ${r.absenteismo_18h || '4'}
👥 CLTs presentes 23hrs: ${r.clts_presentes_23h || '— 60'}
❌ Absenteísmo 23hrs: ${r.absenteismo_23h || '— 4'}
👷 Diaristas solicitados (15:00): ${r.diaristas_solicitados_15h || '20'}
✅ Diaristas presentes (15:00): ${r.diaristas_presentes_15h || '18'}
👷 Diaristas solicitados (20:00): ✅ Diaristas presentes (20:00): ${r.diaristas_presentes_20h || '—'} 📈 PHD previsto: ${r.phd_previsto || '—'} 

📝 Observações:

- Falta injustificada:  ${r.obs_falta_injustificada || '—'} 

- Atestados:  ${r.obs_atestados || '-'} 

- Pontos de atenção: ${r.obs_pontos_atencao || 'N/A'}`;
  }

  openModalReportInicio() {
    const r = this.reportInicio;
    
    // Atualiza cards de resumo
    const cleanData = (r.data_ref || '06/10/2026').replace(/\*/g, '');
    const cardData = document.getElementById('cardRepData');
    if (cardData) cardData.innerText = `${cleanData} • ${r.inicio_operacao || '15:11'}`;

    const cardVol = document.getElementById('cardRepVolume');
    if (cardVol) cardVol.innerText = `${r.backlog_inicial || '692'} / ${r.volume_previsto || '65.129'}`;

    const cardClt = document.getElementById('cardRepClt');
    if (cardClt) cardClt.innerText = `${r.clts_presentes_18h || '32'} (18h) | ${(r.clts_presentes_23h || '60').replace(/—\s*/g, '')} (23h)`;

    const cardDia = document.getElementById('cardRepDiaristas');
    if (cardDia) cardDia.innerText = `${r.diaristas_presentes_15h || '18'} / ${r.diaristas_solicitados_15h || '20'} pres.`;

    // Atualiza texto formatado
    const txtArea = document.getElementById('txtReportInicioFormatado');
    if (txtArea) {
      txtArea.value = this.getFormattedReportInicioText();
    }

    // Modo visualização padrão
    document.getElementById('viewReportContainer')?.classList.remove('hidden');
    document.getElementById('formEditReportInicio')?.classList.add('hidden');
    const lbl = document.getElementById('lblToggleEditReport');
    if (lbl) lbl.innerText = 'Editar Dados';

    document.getElementById('modalReportInicio')?.classList.remove('hidden');
  }

  closeModalReportInicio() {
    document.getElementById('modalReportInicio')?.classList.add('hidden');
  }

  async copyReportInicioToClipboard() {
    const text = this.getFormattedReportInicioText();
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        const txtArea = document.getElementById('txtReportInicioFormatado');
        if (txtArea) {
          txtArea.select();
          document.execCommand('copy');
        }
      }
      
      const btn = document.getElementById('btnCopyReportInicio');
      if (btn) {
        const originalHtml = btn.innerHTML;
        btn.innerHTML = '<i class="fa-solid fa-check"></i> <span>Copiado com Sucesso!</span>';
        btn.classList.remove('bg-emerald-600', 'hover:bg-emerald-700');
        btn.classList.add('bg-emerald-700');
        setTimeout(() => {
          btn.innerHTML = originalHtml;
          btn.classList.add('bg-emerald-600', 'hover:bg-emerald-700');
          btn.classList.remove('bg-emerald-700');
        }, 2200);
      }

      this.showToast('📊 Report de Início copiado para a Área de Transferência! Pronto para colar no WhatsApp.', 'success');
    } catch (e) {
      this.showToast('Não foi possível copiar automaticamente. Selecione e copie o texto abaixo.', 'warning');
    }
  }

  toggleEditReportInicio() {
    const viewCont = document.getElementById('viewReportContainer');
    const formEdit = document.getElementById('formEditReportInicio');
    const lbl = document.getElementById('lblToggleEditReport');
    if (!viewCont || !formEdit) return;

    if (formEdit.classList.contains('hidden')) {
      const r = this.reportInicio;
      const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
      
      setVal('repInputData', r.data_ref || '*06/10/2026*');
      setVal('repInputInicio', r.inicio_operacao || '15:11');
      setVal('repInputBacklog', r.backlog_inicial || '692');
      setVal('repInputVolume', r.volume_previsto || '65.129');
      setVal('repInputClt18', r.clts_presentes_18h || '32');
      setVal('repInputAbs18', r.absenteismo_18h || '4');
      setVal('repInputClt23', r.clts_presentes_23h || '— 60');
      setVal('repInputAbs23', r.absenteismo_23h || '— 4');
      setVal('repInputDiaristasSol15', r.diaristas_solicitados_15h || '20');
      setVal('repInputDiaristasPres15', r.diaristas_presentes_15h || '18');
      setVal('repInputDiaristasPres20', r.diaristas_presentes_20h || '—');
      setVal('repInputPhd', r.phd_previsto || '—');
      setVal('repInputObsFalta', r.obs_falta_injustificada || '—');
      setVal('repInputObsAtestados', r.obs_atestados || '-');
      setVal('repInputObsAtencao', r.obs_pontos_atencao || 'N/A');
      setVal('repInputRawText', this.getFormattedReportInicioText());

      viewCont.classList.add('hidden');
      formEdit.classList.remove('hidden');
      if (lbl) lbl.innerText = 'Ver Formatado';
    } else {
      viewCont.classList.remove('hidden');
      formEdit.classList.add('hidden');
      if (lbl) lbl.innerText = 'Editar Dados';
    }
  }

  async saveReportInicio(e) {
    if (e && e.preventDefault) e.preventDefault();

    const getVal = (id) => (document.getElementById(id)?.value || '').trim();

    this.reportInicio = {
      data_ref: getVal('repInputData') || '*06/10/2026*',
      inicio_operacao: getVal('repInputInicio') || '15:11',
      backlog_inicial: getVal('repInputBacklog') || '692',
      volume_previsto: getVal('repInputVolume') || '65.129',
      clts_presentes_18h: getVal('repInputClt18') || '32',
      absenteismo_18h: getVal('repInputAbs18') || '4',
      clts_presentes_23h: getVal('repInputClt23') || '— 60',
      absenteismo_23h: getVal('repInputAbs23') || '— 4',
      diaristas_solicitados_15h: getVal('repInputDiaristasSol15') || '20',
      diaristas_presentes_15h: getVal('repInputDiaristasPres15') || '18',
      diaristas_solicitados_20h: '—',
      diaristas_presentes_20h: getVal('repInputDiaristasPres20') || '—',
      phd_previsto: getVal('repInputPhd') || '—',
      obs_falta_injustificada: getVal('repInputObsFalta') || '—',
      obs_atestados: getVal('repInputObsAtestados') || '-',
      obs_pontos_atencao: getVal('repInputObsAtencao') || 'N/A',
      raw_text: getVal('repInputRawText') || ''
    };

    this.saveReportInicioToStorage(true);
    this.openModalReportInicio();
    this.showToast('✅ Report de Início salvo no Banco de Dados com sucesso!', 'success');
  }

  renderReportInicioPane() {
    const r = this.reportInicio;
    const cleanData = (r.data_ref || '06/10/2026').replace(/\*/g, '');
    
    // Cards de resumo no topo do painel
    const elData = document.getElementById('paneRepData');
    if (elData) elData.innerText = `${cleanData} (${r.inicio_operacao || '15:11'})`;

    const elVol = document.getElementById('paneRepVolume');
    if (elVol) elVol.innerText = `${r.backlog_inicial || '692'} / ${r.volume_previsto || '65.129'}`;

    const elClt = document.getElementById('paneRepClt');
    if (elClt) elClt.innerText = `${r.clts_presentes_18h || '32'} (18h) | ${r.clts_presentes_23h || '60'} (23h)`;

    const elDia = document.getElementById('paneRepDiaristas');
    if (elDia) elDia.innerText = `${r.diaristas_presentes_15h || '18'} / ${r.diaristas_solicitados_15h || '20'} pres.`;

    // Popula inputs do formulário do painel
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
    setVal('paneInputData', r.data_ref || '*06/10/2026*');
    setVal('paneInputInicio', r.inicio_operacao || '15:11');
    setVal('paneInputBacklog', r.backlog_inicial || '692');
    setVal('paneInputVolume', r.volume_previsto || '65.129');
    setVal('paneInputClt18', r.clts_presentes_18h || '32');
    setVal('paneInputAbs18', r.absenteismo_18h || '4');
    setVal('paneInputClt23', r.clts_presentes_23h || '— 60');
    setVal('paneInputAbs23', r.absenteismo_23h || '— 4');
    setVal('paneInputDiaristasSol15', r.diaristas_solicitados_15h || '20');
    setVal('paneInputDiaristasPres15', r.diaristas_presentes_15h || '18');
    setVal('paneInputDiaristasPres20', r.diaristas_presentes_20h || '—');
    setVal('paneInputPhd', r.phd_previsto || '—');
    setVal('paneInputObsFalta', r.obs_falta_injustificada || '—');
    setVal('paneInputObsAtestados', r.obs_atestados || '-');
    setVal('paneInputObsAtencao', r.obs_pontos_atencao || 'N/A');

    // Popula textarea do WhatsApp no painel
    const txtPane = document.getElementById('paneTxtReportFormatado');
    if (txtPane) {
      txtPane.value = this.getFormattedReportInicioText();
    }
  }

  async saveReportInicioFromPane(e) {
    if (e && e.preventDefault) e.preventDefault();
    const getVal = (id) => (document.getElementById(id)?.value || '').trim();

    this.reportInicio = {
      data_ref: getVal('paneInputData') || '*06/10/2026*',
      inicio_operacao: getVal('paneInputInicio') || '15:11',
      backlog_inicial: getVal('paneInputBacklog') || '692',
      volume_previsto: getVal('paneInputVolume') || '65.129',
      clts_presentes_18h: getVal('paneInputClt18') || '32',
      absenteismo_18h: getVal('paneInputAbs18') || '4',
      clts_presentes_23h: getVal('paneInputClt23') || '— 60',
      absenteismo_23h: getVal('paneInputAbs23') || '— 4',
      diaristas_solicitados_15h: getVal('paneInputDiaristasSol15') || '20',
      diaristas_presentes_15h: getVal('paneInputDiaristasPres15') || '18',
      diaristas_solicitados_20h: '—',
      diaristas_presentes_20h: getVal('paneInputDiaristasPres20') || '—',
      phd_previsto: getVal('paneInputPhd') || '—',
      obs_falta_injustificada: getVal('paneInputObsFalta') || '—',
      obs_atestados: getVal('paneInputObsAtestados') || '-',
      obs_pontos_atencao: getVal('paneInputObsAtencao') || 'N/A',
      raw_text: ''
    };

    this.saveReportInicioToStorage(true);
    this.renderReportInicioPane();
    this.showToast('✅ Report de Início salvo no Banco de Dados com sucesso!', 'success');
  }

  switchTab(tabName) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.add('hidden'));

    const targetBtn = document.getElementById(`tab-${tabName}`);
    const targetPane = document.getElementById(`pane-${tabName}`);

    if (targetBtn) targetBtn.classList.add('active');
    if (targetPane) targetPane.classList.remove('hidden');

    if (tabName === 'dashboard') {
      setTimeout(() => this.renderCharts(), 100);
    } else if (tabName === 'report-inicio') {
      this.renderReportInicioPane();
    }
  }

  showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `pointer-events-auto px-3.5 py-2.5 rounded-lg shadow-md text-xs font-medium text-white flex items-center gap-2 transform transition-all duration-300 translate-y-2 opacity-0`;

    let bgClass = 'bg-slate-800';
    let icon = 'fa-circle-info';

    if (type === 'success') { bgClass = 'bg-slate-800'; icon = 'fa-circle-check text-emerald-400'; }
    if (type === 'warning') { bgClass = 'bg-slate-800'; icon = 'fa-triangle-exclamation text-amber-400'; }
    if (type === 'error') { bgClass = 'bg-slate-800'; icon = 'fa-circle-xmark text-rose-400'; }

    toast.classList.add(bgClass);
    toast.innerHTML = `<i class="fa-solid ${icon}"></i> <span>${message}</span>`;

    container.appendChild(toast);

    setTimeout(() => {
      toast.classList.remove('translate-y-2', 'opacity-0');
    }, 10);

    setTimeout(() => {
      toast.classList.add('opacity-0', 'translate-y-2');
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  setupEventListeners() {
    window.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        this.closeModalDevolucao();
        this.closeModalRetiradaRapida();
        this.closeModalReportInicio();
      }
    });

    window.addEventListener('hashchange', () => {
      const tab = window.location.hash.replace('#', '');
      if (tab) this.switchTab(tab);
    });

    window.addEventListener('message', (e) => {
      if (e.data && (e.data.action === 'switchTab' || e.data.action === 'syncNow' || e.data.action === 'refresh')) {
        if (e.data.tab) this.switchTab(e.data.tab);
        this.fetchFromDatabase(true);
      }
    });

    if (window.location.hash) {
      const initialTab = window.location.hash.replace('#', '');
      if (initialTab) {
        setTimeout(() => this.switchTab(initialTab), 150);
      }
    }
  }
}

let pdaApp;

function initPdaControlApp() {
  if (!pdaApp) {
    pdaApp = new PDAControlApp();
    window.pdaApp = pdaApp;
  }
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initPdaControlApp);
} else {
  initPdaControlApp();
}

