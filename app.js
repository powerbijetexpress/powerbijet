// Otimizações de renderização global e alta performance de navegação
if (typeof Chart !== "undefined") {
    Chart.defaults.animation = false;
    Chart.defaults.responsive = true;
    Chart.defaults.maintainAspectRatio = false;
    Chart.defaults.font.family = "'Outfit', sans-serif";
}

// Base da API para suportar execução local (file://) e servidor web
const API_BASE = (window.location.protocol === 'file:' || !window.location.host) ? 'http://127.0.0.1:5000' : '';

// State Management - Armazena em memoria a lista total de remessas retornadas pela API
let allData = [];
// State Management - Armazena a lista de remessas apos a aplicacao de filtros locais ou de busca
let filteredData = [];
// Armazena o numero correspondente à pagina ativa na visualizacao da tabela detalhada
let currentPage = 1;
// Define a quantidade maxima de linhas a serem exibidas por pagina na tabela (limite de 10)
const rowsPerPage = 10;
// Armazena a string de busca de texto digitada pelo usuario no campo de pesquisa de remessas
let searchQuery = "";

// Variavel global para gerenciar e armazenar a instancia do grafico de status (Rosca)
let chartStatus = null;
// Variavel global para gerenciar a instancia do grafico de volume de recebimento (Barras)
let chartReceiving = null;
// Variavel global para gerenciar a instancia do grafico de volume de registro (Barras)
let chartRegistering = null;
// Variavel global para gerenciar a instancia do grafico de evolucao diaria de envios (Linhas)
let chartEvolution = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA SEM MOVIMENTAÇÃO ---
let activeTab = "general"; // "general", "sem-mov" ou "avaria"
let semMovData = [];
let semMovFilteredData = [];
let semMovCurrentPage = 1;
let semMovSearchQuery = "";

let chartSemMovBase = null;
let chartSemMovDestino = null;
let chartSemMovDelayBase = null;
let chartSemMovAgingDist = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA AVARIAS ---
let avariaData = [];
let avariaFilteredData = [];
let avariaCurrentPage = 1;
let avariaSearchQuery = "";

let chartAvariaColaborador = null;
let chartAvariaProduto = null;
let chartAvariaStatusDist = null;
let chartAvariaEvolution = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA VOLUME EXP DC BAU ---
let volumeExpData = [];
let chartVolumeExp = null;
let chartVolumeExpNaoChegou = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA VOLUMETRIA DIÁRIA ---
let volumetriaData = null;
let volumetriaFilteredRecords = [];
let chartVolumetriaComparativo = null;
let chartVolumetriaComposicao = null;
let chartVolumetriaStatus = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA RANKING & HORA A HORA ---
let rankingData = null;
let rankingFilteredOperadores = [];
let chartRankingHora = null;
let chartRankingTop10 = null;
let chartRankingSetores = null;

// --- NOVAS VARIÁVEIS DE ESTADO PARA CONTROLE BAURU ---
let controleDataCached = null;
let chartCtrlAvarias = null;
let chartCtrlSemMov = null;
let chartProdRecebimento = null;
let chartProdHeadcount = null;
let chartCtrlGestao = null;
let chartProdCompColeta = null;
let chartProdCompExp = null;
let chartProdCompLote = null;

// Captura do elemento input de data inicial dos filtros operacionais
const elStartDate = document.getElementById("filter-start-date");
// Captura do elemento input de data final dos filtros operacionais
const elEndDate = document.getElementById("filter-end-date");
// Captura do elemento select de estacao de recebimento dos filtros
const elReceiving = document.getElementById("filter-receiving");
// Captura do elemento select de estacao de registro dos filtros
const elRegistering = document.getElementById("filter-registering");
// Captura do elemento select de status dos filtros
const elStatus = document.getElementById("filter-status");
// Captura do botao para limpar e resetar todos os filtros ativos
const elResetFilters = document.getElementById("btn-reset-filters");
// Captura do botao de acionamento de download do PDF filtrado
const elPdfReport = document.getElementById("btn-pdf-report");

// Captura do elemento textual que exibira a quantidade total de remessas filtradas
const elValTotal = document.getElementById("val-total");
// Captura do elemento que exibira a quantidade total de remessas concluidas
const elValConcluidas = document.getElementById("val-concluidas");
// Captura do elemento que exibira a quantidade total de remessas pendentes
const elValPendentes = document.getElementById("val-pendentes");
// Captura do elemento que exibira a quantidade total de remessas criticas
const elValCriticas = document.getElementById("val-criticas");

// Captura do elemento que exibira a porcentagem de remessas concluidas do total
const elPctConcluidas = document.getElementById("pct-concluidas");
// Captura do elemento que exibira a porcentagem de remessas pendentes do total
const elPctPendentes = document.getElementById("pct-pendentes");
// Captura do elemento que exibira a porcentagem de remessas criticas do total
const elPctCriticas = document.getElementById("pct-criticas");

// Captura do corpo da tabela detalhada (tbody) onde as linhas serao geradas em JavaScript
const elTableBody = document.getElementById("table-body");
// Captura do campo de input de busca de texto por numero de remessa
const elTableSearch = document.getElementById("table-search-input");
// Captura do elemento que exibe a faixa de registros exibidos no rodape da tabela
const elTableInfo = document.getElementById("table-info");
// Captura do botao de retroceder paginacao na tabela
const elBtnPrev = document.getElementById("btn-prev");
// Captura do botao de avancar paginacao na tabela
const elBtnNext = document.getElementById("btn-next");
// Captura do elemento que exibe o numero da pagina corrente na paginacao da tabela
const elPageNum = document.getElementById("page-num");

// --- NOVOS SELETORES DE COMPONENTES ---
const elNavGeneral = document.getElementById("nav-general");
const elNavSemMov = document.getElementById("nav-sem-mov");
const elNavAvaria = document.getElementById("nav-avaria");
const elNavControle = document.getElementById("nav-controle");
const elPanelGeneral = document.getElementById("panel-general");
const elPanelSemMov = document.getElementById("panel-sem-mov");
const elPanelAvaria = document.getElementById("panel-avaria");
const elPanelControle = document.getElementById("panel-controle");
const elFiltersGeneral = document.getElementById("filters-general");
const elFiltersSemMov = document.getElementById("filters-sem-mov");
const elFiltersAvaria = document.getElementById("filters-avaria");
const elFiltersControle = document.getElementById("filters-controle");
const elNavProducao = document.getElementById("nav-producao");
const elPanelProducao = document.getElementById("panel-producao");
const elFiltersProducao = document.getElementById("filters-producao");

// --- NOVOS SELETORES PARA VOLUME EXP DC BAU ---
const elNavVolumeExp = document.getElementById("nav-volume-exp-dc-bau");
const elPanelVolumeExp = document.getElementById("panel-volume-exp-dc-bau");
const elFiltersVolumeExp = document.getElementById("filters-volume-exp-dc-bau");
const elVolumeExpDateFilter = document.getElementById("filter-volume-exp-date");
const elVolumeExpRefreshBtn = document.getElementById("btn-volume-exp-refresh");

// --- NOVOS SELETORES PARA RECEBIMENTO ---
const elNavRecebimento = document.getElementById("nav-recebimento");
const elPanelRecebimento = document.getElementById("panel-recebimento");
const elFiltersRecebimento = document.getElementById("filters-recebimento");
const elRecebimentoDateFilter = document.getElementById("filter-recebimento-date");
const elRecebimentoRefreshBtn = document.getElementById("btn-recebimento-refresh");

// --- NOVOS SELETORES PARA VOLUMETRIA DIÁRIA ---
const elNavVolumetria = document.getElementById("nav-volumetria");
const elPanelVolumetria = document.getElementById("panel-volumetria");
const elFiltersVolumetria = document.getElementById("filters-volumetria");
const elVolumetriaStatusViagemFilter = document.getElementById("filter-volumetria-status-viagem");
const elVolumetriaPddFilter = document.getElementById("filter-volumetria-pdd");
const elVolumetriaRefreshBtn = document.getElementById("btn-volumetria-refresh");
const elVolumetriaOpenUploadBtn = document.getElementById("btn-volumetria-open-upload");
const elVolumetriaUploadTrigger = document.getElementById("btn-volumetria-upload-trigger");
const elVolumetriaCopySummaryBtn = document.getElementById("btn-volumetria-copy-summary");
const elVolumetriaTableSearch = document.getElementById("volumetria-table-search");
const elBtnVolumetriaOpenAddTruck = document.getElementById("btn-volumetria-open-add-truck");
const elModalVolumetriaAddTruck = document.getElementById("modal-volumetria-add-truck");
const elBtnCloseVolumetriaAddTruck = document.getElementById("btn-close-volumetria-add-truck");
const elBtnCancelVolumetriaAddTruck = document.getElementById("btn-cancel-volumetria-add-truck");
const elFormVolumetriaAddTruck = document.getElementById("form-volumetria-add-truck");
const elModalVolumetriaUpload = document.getElementById("modal-volumetria-upload");
const elBtnCloseVolumetriaModal = document.getElementById("btn-close-volumetria-modal");
const elVolumetriaDropzone = document.getElementById("volumetria-dropzone");
const elVolumetriaFileInput = document.getElementById("volumetria-file-input");

// --- NOVOS SELETORES PARA RANKING & PRODUTIVIDADE ---
const elNavRanking = document.getElementById("nav-ranking");
const elPanelRanking = document.getElementById("panel-ranking");
const elFiltersRanking = document.getElementById("filters-ranking");
const elRankingSetorFilter = document.getElementById("filter-ranking-setor");
const elRankingTurnoFilter = document.getElementById("filter-ranking-turno");
const elRankingRefreshBtn = document.getElementById("btn-ranking-refresh");
const elRankingOpenUploadBtn = document.getElementById("btn-ranking-open-upload");
const elRankingUploadTrigger = document.getElementById("btn-ranking-upload-trigger");
const elBtnRankingClear = document.getElementById("btn-ranking-clear");
const elRankingTableSearch = document.getElementById("ranking-table-search");
const elModalRankingUpload = document.getElementById("modal-ranking-upload");
const elBtnCloseRankingModal = document.getElementById("btn-close-ranking-modal");
const elRankingDropzone = document.getElementById("ranking-dropzone");
const elRankingFileInput = document.getElementById("ranking-file-input");

// --- NOVOS SELETORES PARA CONTROLE DE PDAs ---
const elNavPda = document.getElementById("nav-pda");
const elPanelPda = document.getElementById("panel-pda");
const elFiltersPda = document.getElementById("filters-pda");
const elBtnPdaRefresh = document.getElementById("btn-pda-refresh");
const elBtnPdaRefreshTop = document.getElementById("btn-pda-refresh-top");
const elIframePda = document.getElementById("iframe-pda");
const elBtnPdaExternal = document.getElementById("btn-pda-external");
const elBtnPdaOpenTab = document.getElementById("btn-pda-open-tab");

// --- NOVOS SELETORES PARA REPORT DE INÍCIO DA OPERAÇÃO ---
const elNavReportInicio = document.getElementById("nav-report-inicio");
const elPanelReportInicio = document.getElementById("panel-report-inicio");
const elFiltersReportInicio = document.getElementById("filters-report-inicio");
const elBtnReportInicioSidebarSave = document.getElementById("btn-report-inicio-sidebar-save");
const elBtnReportInicioSidebarCopy = document.getElementById("btn-report-inicio-sidebar-copy");
const elBtnReportInicioSidebarRefresh = document.getElementById("btn-report-inicio-sidebar-refresh");



const elSidebar = document.getElementById("sidebar");
const elSidebarBackdrop = document.getElementById("sidebar-backdrop");
const elMobileSidebarToggle = document.getElementById("mobile-sidebar-toggle");
const elMobileSidebarClose = document.getElementById("mobile-sidebar-close");

const elAgingMultiselectTrigger = document.getElementById("aging-multiselect-trigger");
const elAgingMultiselectDropdown = document.getElementById("aging-multiselect-dropdown");
const elAgingSelectAll = document.getElementById("aging-select-all");
const elAgingOptionsContainer = document.getElementById("aging-options-container");
const elSemMovBase = document.getElementById("filter-sem-mov-base");
const elSemMovDestino = document.getElementById("filter-sem-mov-destino");

const elBtnSemMovReset = document.getElementById("btn-sem-mov-reset");
const elBtnSemMovPdf = document.getElementById("btn-sem-mov-pdf");

const elValSemMovTotal = document.getElementById("val-sem-mov-total");
const elValSemMovMulta = document.getElementById("val-sem-mov-multa");
const elValSemMovAging = document.getElementById("val-sem-mov-aging");
const elValSemMovMaxDias = document.getElementById("val-sem-mov-max-dias");

const elTableSemMovBody = document.getElementById("table-sem-mov-body");
const elTableSemMovSearch = document.getElementById("table-sem-mov-search-input");
const elTableSemMovInfo = document.getElementById("table-sem-mov-info");
const elBtnSemMovPrev = document.getElementById("btn-sem-mov-prev");
const elBtnSemMovNext = document.getElementById("btn-sem-mov-next");
const elPageSemMovNum = document.getElementById("page-sem-mov-num");

// --- SELETORES ESPECÍFICOS DE AVARIAS ---
const elAvariaStartDate = document.getElementById("filter-avaria-start-date");
const elAvariaEndDate = document.getElementById("filter-avaria-end-date");
const elAvariaBase = document.getElementById("filter-avaria-base");
const elAvariaColaborador = document.getElementById("filter-avaria-colaborador");
const elAvariaProduto = document.getElementById("filter-avaria-produto");
const elAvariaStatus = document.getElementById("filter-avaria-status");
const elBtnAvariaReset = document.getElementById("btn-avaria-reset");
const elBtnAvariaPdf = document.getElementById("btn-avaria-pdf");

const elValAvariaTotal = document.getElementById("val-avaria-total");
const elValAvariaColaboradores = document.getElementById("val-avaria-colaboradores");
const elValAvariaViagens = document.getElementById("val-avaria-viagens");
const elValAvariaTopProduto = document.getElementById("val-avaria-top-produto");

const elTableAvariaBody = document.getElementById("table-avaria-body");
const elTableAvariaSearch = document.getElementById("table-avaria-search-input");
const elTableAvariaInfo = document.getElementById("table-avaria-info");
const elBtnAvariaPrev = document.getElementById("btn-avaria-prev");
const elBtnAvariaNext = document.getElementById("btn-avaria-next");
const elPageAvariaNum = document.getElementById("page-avaria-num");

// Live Clock - Atualiza o horario de execucao do sistema a cada 1 segundo no cabecalho
function startClock() {
    // Captura o elemento do relogio localizado na barra superior do dashboard
    const elClock = document.getElementById("live-clock");
    // Configura a execucao repetitiva a cada 1000 milissegundos (1 segundo)
    setInterval(() => {
        // Instancia a data e hora do momento atual
        const now = new Date();
        // Atualiza o conteudo de texto com a representacao formatada de hora local (hh:mm:ss)
        elClock.textContent = now.toLocaleTimeString("pt-BR");
    }, 1000); // Fim do intervalo
}

// Custom Chart.js Plugin para renderizacao de rotulos de dados (valores) diretamente no grafico
const customDataLabelsPlugin = {
    // Identificador exclusivo exigido pelo Chart.js para o plugin
    id: 'customDataLabels',
    // Evento disparado imediatamente apos a renderizacao de todas as series de dados no canvas
    afterDatasetsDraw(chart, args, options) {
        // Captura o contexto de desenho 2D do canvas correspondente ao grafico
        const { ctx } = chart;
        // Salva o estado atual do pincel de desenho para nao interferir em outros elementos do chart
        ctx.save();
        // Define o tamanho da fonte, negrito e familia tipografica Outfit dos rotulos
        ctx.font = 'bold 11px Outfit';
        // Define a cor do texto dos rotulos como branco solido
        ctx.fillStyle = '#FFFFFF';
        // Centraliza horizontalmente o ponto de insercao do texto
        ctx.textAlign = 'center';
        // Define o alinhamento vertical do texto como meio
        ctx.textBaseline = 'middle';

        // Itera por cada um dos datasets do grafico (geralmente possui apenas um)
        chart.data.datasets.forEach((dataset, i) => {
            // Obtem os metadados internos de posicao e geometria calculados para o dataset correspondente
            const meta = chart.getDatasetMeta(i);
            // Itera por cada um dos pontos, fatias ou barras desenhados na tela
            meta.data.forEach((element, index) => {
                // Obtem o valor numerico correspondente ao item corrente do dataset
                const dataVal = dataset.data[index];
                // Ignora o item se o valor nao estiver definido, for nulo ou for igual a zero
                if (dataVal === undefined || dataVal === null || dataVal === 0) return;
                
                // Variaveis locais para armazenar a coordenada final (X, Y) do rotulo na tela
                let x, y;
                // Ajusta o posicionamento do texto conforme a tipagem especifica do grafico
                if (chart.config.type === 'doughnut') {
                    // Para o grafico de rosca, calcula o centro visual geométrico da fatia (tooltipPosition)
                    const center = element.tooltipPosition();
                    // Define a posicao X
                    x = center.x;
                    // Define a posicao Y
                    y = center.y;
                } else if (chart.config.type === 'line') {
                    // Para o grafico de linhas, centraliza no ponto X da linha
                    x = element.x;
                    // Desenha o texto 12 pixels acima do ponto de vertice no grafico
                    y = element.y - 12;
                } else { // bar
                    // Para o grafico de colunas, posiciona no centro horizontal da barra
                    x = element.x;
                    // Desenha o texto 10 pixels acima do topo da barra no grafico
                    y = element.y - 10;
                }
                
                // Define sombra escura para destacar a letra branca sobre fundos claros ou coloridos
                ctx.shadowColor = 'rgba(0, 0, 0, 0.9)';
                // Define o espalhamento suave da sombra em 3 pixels
                ctx.shadowBlur = 3;
                // Sem deslocamento horizontal da sombra
                ctx.shadowOffsetX = 0;
                // Deslocamento vertical de 1 pixel para baixo da sombra
                ctx.shadowOffsetY = 1;
                
                // Executa a escrita do texto do valor na coordenada de tela calculada
                ctx.fillText(dataVal, x, y);
            }); // Fim do loop de elementos do dataset
        }); // Fim do loop de datasets
        // Restaura as propriedades originais do pincel de desenho do canvas
        ctx.restore();
    } // Fim da funcao afterDatasetsDraw
};

// Registra globalmente o plugin de rótulos de dados customizados em todas as instancias futuras do Chart.js
if (typeof Chart !== "undefined" && typeof Chart.register === "function") {
    Chart.register(customDataLabelsPlugin);
}

// Função principal disparada na inicialização do dashboard
function initDashboardApp() {
    // Inicia a execucao do relogio no topo
    startClock();
    // Faz a requisicao inicial dos filtros e dados em paralelo para agilizar a leitura
    loadFilterDropdowns().then(() => refreshData());
    loadSemMovFilterDropdowns();
    loadAvariaFilterDropdowns();
    
    // Registra listeners com protecao de nulidade
    if (elStartDate) elStartDate.addEventListener("change", refreshData);
    if (elEndDate) elEndDate.addEventListener("change", refreshData);
    if (elReceiving) elReceiving.addEventListener("change", refreshData);
    if (elRegistering) elRegistering.addEventListener("change", refreshData);
    if (elStatus) elStatus.addEventListener("change", refreshData);
    
    if (elResetFilters) elResetFilters.addEventListener("click", resetFilters);
    if (elPdfReport) elPdfReport.addEventListener("click", generatePdfReport);
    
    if (elTableSearch) {
        elTableSearch.addEventListener("input", (e) => {
            searchQuery = e.target.value.trim().toLowerCase();
            currentPage = 1;
            renderTable();
        });
    }
    
    if (elBtnPrev) {
        elBtnPrev.addEventListener("click", () => {
            if (currentPage > 1) {
                currentPage--;
                renderTable();
            }
        });
    }
    
    // Registra evento de clique para avancar de pagina na tabela
    if (elBtnNext) {
        elBtnNext.addEventListener("click", () => {
            // Calcula a quantidade total de paginas com base na contagem de registros filtrados
            const totalPages = Math.ceil(filteredData.length / rowsPerPage);
            // Valida se nao esta na ultima pagina
            if (currentPage < totalPages) {
                // Incrementa o indice de pagina
                currentPage++;
                // Atualiza a renderizacao da tabela detalhada
                renderTable();
            }
        });
    }

    // --- OUVINTES DE EVENTOS DE NAVEGAÇÃO ENTRE ABAS ---
    if (elNavGeneral) elNavGeneral.addEventListener("click", () => switchTab("general"));
    if (elNavSemMov) elNavSemMov.addEventListener("click", () => switchTab("sem-mov"));
    if (elNavAvaria) elNavAvaria.addEventListener("click", () => switchTab("avaria"));
    if (elNavControle) elNavControle.addEventListener("click", () => switchTab("controle"));
    if (elNavProducao) elNavProducao.addEventListener("click", () => switchTab("producao"));
    if (elNavVolumeExp) elNavVolumeExp.addEventListener("click", () => switchTab("volume-exp-dc-bau"));
    if (elNavRecebimento) elNavRecebimento.addEventListener("click", () => switchTab("recebimento"));
    if (elNavVolumetria) elNavVolumetria.addEventListener("click", () => switchTab("volumetria"));
    if (elNavRanking) elNavRanking.addEventListener("click", () => switchTab("ranking"));
    if (elNavPda) elNavPda.addEventListener("click", () => switchTab("pda"));
    if (elNavReportInicio) elNavReportInicio.addEventListener("click", () => switchTab("report-inicio"));

    const refreshPdaFrame = () => {
        if (elIframePda) {
            try {
                if (elIframePda.contentWindow) {
                    elIframePda.contentWindow.postMessage({ action: 'syncNow' }, '*');
                }
            } catch(e) {}
            const currentSrc = elIframePda.src.split("?")[0];
            elIframePda.src = `${currentSrc}?t=${Date.now()}`;
        }
    };
    if (elBtnPdaRefresh) elBtnPdaRefresh.addEventListener("click", refreshPdaFrame);
    if (elBtnPdaRefreshTop) elBtnPdaRefreshTop.addEventListener("click", refreshPdaFrame);

    // Filtros Sem Movimentação
    if (elAgingMultiselectTrigger && elAgingMultiselectDropdown) {
        elAgingMultiselectTrigger.addEventListener("click", (e) => {
            e.stopPropagation();
            const display = elAgingMultiselectDropdown.style.display;
            elAgingMultiselectDropdown.style.display = (display === "none" || !display) ? "block" : "none";
        });
        
        elAgingMultiselectDropdown.addEventListener("click", (e) => {
            e.stopPropagation();
        });
        
        document.addEventListener("click", () => {
            elAgingMultiselectDropdown.style.display = "none";
        });
    }
    
    if (elAgingSelectAll) {
        elAgingSelectAll.addEventListener("change", (e) => {
            const isChecked = e.target.checked;
            const optionBoxes = document.querySelectorAll(".aging-checkbox");
            optionBoxes.forEach(cb => {
                cb.checked = isChecked;
            });
            updateAgingTriggerText();
            refreshSemMovData();
        });
    }

    if (elSemMovBase) elSemMovBase.addEventListener("change", refreshSemMovData);
    if (elSemMovDestino) elSemMovDestino.addEventListener("change", refreshSemMovData);
    
    if (elBtnSemMovReset) elBtnSemMovReset.addEventListener("click", resetSemMovFilters);
    if (elBtnSemMovPdf) elBtnSemMovPdf.addEventListener("click", generateSemMovPdfReport);
    
    // Busca na tabela Sem Movimentação
    if (elTableSemMovSearch) {
        elTableSemMovSearch.addEventListener("input", (e) => {
            semMovSearchQuery = e.target.value.trim().toLowerCase();
            semMovCurrentPage = 1;
            renderSemMovTable();
        });
    }
    
    // Paginação Sem Movimentação
    if (elBtnSemMovPrev) {
        elBtnSemMovPrev.addEventListener("click", () => {
            if (semMovCurrentPage > 1) {
                semMovCurrentPage--;
                renderSemMovTable();
            }
        });
    }
    
    if (elBtnSemMovNext) {
        elBtnSemMovNext.addEventListener("click", () => {
            const totalPages = Math.ceil(semMovFilteredData.length / rowsPerPage);
            if (semMovCurrentPage < totalPages) {
                semMovCurrentPage++;
                renderSemMovTable();
            }
        });
    }

    // Botão PDF Fechamento
    const elBtnControlePdfSidebar = document.getElementById("btn-controle-pdf-sidebar");
    if (elBtnControlePdfSidebar) {
        elBtnControlePdfSidebar.addEventListener("click", generateControlePdfReport);
    }

    // --- OUVINTES DE EVENTOS DA VISÃO VOLUME EXP DC BAU ---
    if (elNavVolumeExp) {
        elNavVolumeExp.addEventListener("click", () => switchTab("volume-exp-dc-bau"));
    }
    if (elVolumeExpDateFilter) {
        elVolumeExpDateFilter.addEventListener("change", renderVolumeExpDashboard);
    }
    if (elVolumeExpRefreshBtn) {
        elVolumeExpRefreshBtn.addEventListener("click", loadVolumeExpData);
    }
    
    // --- OUVINTES DE EVENTOS DA VISÃO RECEBIMENTO ---
    if (elNavRecebimento) {
        elNavRecebimento.addEventListener("click", () => switchTab("recebimento"));
    }
    if (elRecebimentoDateFilter) {
        elRecebimentoDateFilter.addEventListener("change", renderRecebimentoDashboard);
    }
    if (elRecebimentoRefreshBtn) {
        elRecebimentoRefreshBtn.addEventListener("click", loadRecebimentoFilters);
    }

    // --- OUVINTES DE EVENTOS DA VISÃO VOLUMETRIA DIÁRIA ---
    if (elNavVolumetria) {
        elNavVolumetria.addEventListener("click", () => switchTab("volumetria"));
    }
    if (elVolumetriaRefreshBtn) {
        elVolumetriaRefreshBtn.addEventListener("click", loadVolumetriaData);
    }
    if (elVolumetriaStatusViagemFilter) {
        elVolumetriaStatusViagemFilter.addEventListener("change", filterAndRenderVolumetria);
    }
    if (elVolumetriaPddFilter) {
        elVolumetriaPddFilter.addEventListener("change", filterAndRenderVolumetria);
    }
    if (elVolumetriaTableSearch) {
        elVolumetriaTableSearch.addEventListener("input", filterAndRenderVolumetria);
    }
    if (elVolumetriaOpenUploadBtn) {
        elVolumetriaOpenUploadBtn.addEventListener("click", () => {
            if (elModalVolumetriaUpload) elModalVolumetriaUpload.style.display = "flex";
        });
    }
    if (elVolumetriaUploadTrigger) {
        elVolumetriaUploadTrigger.addEventListener("click", () => {
            if (elModalVolumetriaUpload) elModalVolumetriaUpload.style.display = "flex";
        });
    }
    if (elBtnCloseVolumetriaModal) {
        elBtnCloseVolumetriaModal.addEventListener("click", () => {
            if (elModalVolumetriaUpload) elModalVolumetriaUpload.style.display = "none";
        });
    }
    if (elModalVolumetriaUpload) {
        elModalVolumetriaUpload.addEventListener("click", (e) => {
            if (e.target === elModalVolumetriaUpload) {
                elModalVolumetriaUpload.style.display = "none";
            }
        });
    }
    if (elVolumetriaDropzone && elVolumetriaFileInput) {
        elVolumetriaDropzone.addEventListener("click", () => {
            elVolumetriaFileInput.click();
        });
        elVolumetriaFileInput.addEventListener("change", (e) => {
            if (e.target.files.length > 0) {
                handleVolumetriaUpload(e.target.files[0]);
            }
        });
        
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            elVolumetriaDropzone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
        
        ['dragenter', 'dragover'].forEach(eventName => {
            elVolumetriaDropzone.addEventListener(eventName, () => {
                elVolumetriaDropzone.style.borderColor = "#3B82F6";
                elVolumetriaDropzone.style.background = "rgba(59, 130, 246, 0.15)";
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            elVolumetriaDropzone.addEventListener(eventName, () => {
                elVolumetriaDropzone.style.borderColor = "rgba(59, 130, 246, 0.4)";
                elVolumetriaDropzone.style.background = "rgba(59, 130, 246, 0.05)";
            }, false);
        });
        
        elVolumetriaDropzone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleVolumetriaUpload(files[0]);
            }
        }, false);
    }
    if (elVolumetriaCopySummaryBtn) {
        elVolumetriaCopySummaryBtn.addEventListener("click", copyVolumetriaSummary);
    }

    // Modal: Adicionar Caminhão Extra (Volumetria Diária)
    function closeVolumetriaAddTruckModal() {
        if (elModalVolumetriaAddTruck) {
            elModalVolumetriaAddTruck.style.display = "none";
        }
    }

    if (elBtnVolumetriaOpenAddTruck) {
        elBtnVolumetriaOpenAddTruck.addEventListener("click", () => {
            if (elModalVolumetriaAddTruck) {
                elModalVolumetriaAddTruck.style.display = "flex";
                const idInput = document.getElementById("add-vol-id-transporte");
                if (idInput) {
                    if (!idInput.value) {
                        const nextNum = (volumetriaData?.records?.length || 0) + 1;
                        idInput.value = `EXTRA-${nextNum < 10 ? '0' + nextNum : nextNum}`;
                    }
                    setTimeout(() => idInput.focus(), 60);
                }
            }
        });
    }

    if (elBtnCloseVolumetriaAddTruck) elBtnCloseVolumetriaAddTruck.addEventListener("click", closeVolumetriaAddTruckModal);
    if (elBtnCancelVolumetriaAddTruck) elBtnCancelVolumetriaAddTruck.addEventListener("click", closeVolumetriaAddTruckModal);

    if (elModalVolumetriaAddTruck) {
        elModalVolumetriaAddTruck.addEventListener("click", (e) => {
            if (e.target === elModalVolumetriaAddTruck) {
                closeVolumetriaAddTruckModal();
            }
        });
    }

    if (elFormVolumetriaAddTruck) {
        elFormVolumetriaAddTruck.addEventListener("submit", async (e) => {
            e.preventDefault();
            
            const idTransporte = (document.getElementById("add-vol-id-transporte")?.value || "").trim().toUpperCase();
            const pddSaida = (document.getElementById("add-vol-pdd-saida")?.value || "SP BRE").trim();
            const pedidoSistema = parseInt(document.getElementById("add-vol-pedido-sistema")?.value || "0", 10) || 0;
            const statusViagem = (document.getElementById("add-vol-status-viagem")?.value || "Concluído: 已完成").trim();
            const prevChegada = (document.getElementById("add-vol-previsao-chegada")?.value || "").trim();
            const chegadaReal = (document.getElementById("add-vol-chegada-real")?.value || "").trim();
            const inicioColeta = (document.getElementById("add-vol-inicio-coleta")?.value || "").trim();
            const fimColeta = (document.getElementById("add-vol-fim-coleta")?.value || "").trim();
            const status = (document.getElementById("add-vol-status")?.value || "").trim();
            const bipado = parseInt(document.getElementById("add-vol-bipado")?.value || "0", 10) || 0;
            const obs = (document.getElementById("add-vol-obs")?.value || "").trim();
            
            if (!idTransporte) {
                alert("Por favor, informe o ID de Transporte.");
                return;
            }
            
            if (!volumetriaData) {
                volumetriaData = { records: [], kpis: {}, data_referencia: new Date().toLocaleDateString("pt-BR") };
            }
            if (!volumetriaData.records) volumetriaData.records = [];
            
            const existingIdx = volumetriaData.records.findIndex(r => r.id_transporte === idTransporte);
            const newRecord = {
                id_transporte: idTransporte,
                pdd_saida: pddSaida,
                pedido_sistema: pedidoSistema,
                status_viagem: statusViagem,
                previsao_chegada: prevChegada || "--:--",
                chegada_real: chegadaReal || "",
                inicio_coleta: inicioColeta || "",
                fim_coleta: fimColeta || "",
                status: status || "",
                bipado: bipado,
                obs: obs || "Caminhão Extra"
            };
            
            if (existingIdx >= 0) {
                volumetriaData.records[existingIdx] = newRecord;
            } else {
                volumetriaData.records.push(newRecord);
            }
            
            populateVolumetriaFilters();
            filterAndRenderVolumetria();
            closeVolumetriaAddTruckModal();
            
            // Persiste imediatamente no banco de dados SQLite / Render
            await saveVolumetriaChanges();
            
            // Reseta formulário
            elFormVolumetriaAddTruck.reset();
            const defaultObs = document.getElementById("add-vol-obs");
            if (defaultObs) defaultObs.value = "Caminhão Extra";
        });
    }

    // --- OUVINTES DE EVENTOS DA VISÃO RANKING ---
    if (elRankingRefreshBtn) {
        elRankingRefreshBtn.addEventListener("click", loadRankingData);
    }
    if (elBtnRankingClear) {
        elBtnRankingClear.addEventListener("click", async () => {
            if (confirm("Deseja realmente limpar todos os dados do ranking para iniciar um novo turno (16h00 às 07h00)?")) {
                try {
                    const resp = await fetch(`${API_BASE}/api/ranking/clear`, { method: "POST" });
                    const res = await resp.json();
                    if (res && res.success) {
                        rankingData = res.data;
                        filterAndRenderRanking();
                        alert("Dados do ranking limpos com sucesso! Painel zerado para o novo turno.");
                    } else {
                        alert("Erro ao limpar dados: " + (res.error || "Desconhecido"));
                    }
                } catch (err) {
                    console.error("Erro ao limpar ranking:", err);
                    alert("Erro ao comunicar com o servidor.");
                }
            }
        });
    }
    if (elRankingSetorFilter) {
        elRankingSetorFilter.addEventListener("change", filterAndRenderRanking);
    }
    if (elRankingTurnoFilter) {
        elRankingTurnoFilter.addEventListener("change", filterAndRenderRanking);
    }
    if (elRankingTableSearch) {
        elRankingTableSearch.addEventListener("input", filterAndRenderRanking);
    }
    if (elRankingOpenUploadBtn) {
        elRankingOpenUploadBtn.addEventListener("click", () => {
            if (elModalRankingUpload) elModalRankingUpload.style.display = "flex";
        });
    }
    if (elRankingUploadTrigger) {
        elRankingUploadTrigger.addEventListener("click", () => {
            if (elModalRankingUpload) elModalRankingUpload.style.display = "flex";
        });
    }
    if (elBtnCloseRankingModal) {
        elBtnCloseRankingModal.addEventListener("click", () => {
            if (elModalRankingUpload) elModalRankingUpload.style.display = "none";
        });
    }
    if (elModalRankingUpload) {
        elModalRankingUpload.addEventListener("click", (e) => {
            if (e.target === elModalRankingUpload) {
                elModalRankingUpload.style.display = "none";
            }
        });
    }
    if (elRankingDropzone && elRankingFileInput) {
        elRankingDropzone.addEventListener("click", () => elRankingFileInput.click());
        elRankingFileInput.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleRankingUpload(e.target.files);
            }
        });
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            elRankingDropzone.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
        ['dragenter', 'dragover'].forEach(eventName => {
            elRankingDropzone.addEventListener(eventName, () => {
                elRankingDropzone.style.borderColor = "#3B82F6";
                elRankingDropzone.style.background = "rgba(59, 130, 246, 0.15)";
            }, false);
        });
        ['dragleave', 'drop'].forEach(eventName => {
            elRankingDropzone.addEventListener(eventName, () => {
                elRankingDropzone.style.borderColor = "rgba(59, 130, 246, 0.4)";
                elRankingDropzone.style.background = "rgba(59, 130, 246, 0.05)";
            }, false);
        });
        elRankingDropzone.addEventListener('drop', e => {
            const files = e.dataTransfer.files;
            if (files && files.length > 0) {
                handleRankingUpload(files);
            }
        }, false);
    }

    // Botões de upload individual por setor no modal
    const btnColeta = document.getElementById("btn-upload-coleta");
    const inpColeta = document.getElementById("ranking-file-coleta");
    if (btnColeta && inpColeta) {
        btnColeta.addEventListener("click", () => inpColeta.click());
        inpColeta.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleRankingUpload(e.target.files, "coleta");
            }
        });
    }

    const btnLote = document.getElementById("btn-upload-lote");
    const inpLote = document.getElementById("ranking-file-lote");
    if (btnLote && inpLote) {
        btnLote.addEventListener("click", () => inpLote.click());
        inpLote.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleRankingUpload(e.target.files, "lote");
            }
        });
    }

    const btnExp = document.getElementById("btn-upload-exp");
    const inpExp = document.getElementById("ranking-file-exp");
    if (btnExp && inpExp) {
        btnExp.addEventListener("click", () => inpExp.click());
        inpExp.addEventListener("change", (e) => {
            if (e.target.files && e.target.files.length > 0) {
                handleRankingUpload(e.target.files, "expedicao");
            }
        });
    }

    
    if (elAvariaStartDate) elAvariaStartDate.addEventListener("change", refreshAvariaData);
    if (elAvariaEndDate) elAvariaEndDate.addEventListener("change", refreshAvariaData);
    if (elAvariaBase) elAvariaBase.addEventListener("change", refreshAvariaData);
    if (elAvariaColaborador) elAvariaColaborador.addEventListener("change", refreshAvariaData);
    if (elAvariaProduto) elAvariaProduto.addEventListener("change", refreshAvariaData);
    if (elAvariaStatus) elAvariaStatus.addEventListener("change", refreshAvariaData);
    
    if (elBtnAvariaReset) elBtnAvariaReset.addEventListener("click", resetAvariaFilters);
    if (elBtnAvariaPdf) elBtnAvariaPdf.addEventListener("click", generateAvariaPdfReport);
    
    if (elTableAvariaSearch) {
        elTableAvariaSearch.addEventListener("input", (e) => {
            avariaSearchQuery = e.target.value.trim().toLowerCase();
            avariaCurrentPage = 1;
            renderAvariaTable();
        });
    }
    
    if (elBtnAvariaPrev) {
        elBtnAvariaPrev.addEventListener("click", () => {
            if (avariaCurrentPage > 1) {
                avariaCurrentPage--;
                renderAvariaTable();
            }
        });
    }
    
    if (elBtnAvariaNext) {
        elBtnAvariaNext.addEventListener("click", () => {
            const totalPages = Math.ceil(avariaFilteredData.length / rowsPerPage);
            if (avariaCurrentPage < totalPages) {
                avariaCurrentPage++;
                renderAvariaTable();
            }
        });
    }

    // Ouvintes de eventos para controle do menu lateral no celular (Mobile Sidebar)
    if (elMobileSidebarToggle) {
        elMobileSidebarToggle.addEventListener("click", () => {
            elSidebar.classList.add("active");
            elSidebarBackdrop.classList.add("active");
        });
    }
    
    if (elMobileSidebarClose) {
        elMobileSidebarClose.addEventListener("click", () => {
            elSidebar.classList.remove("active");
            elSidebarBackdrop.classList.remove("active");
        });
    }
    
    if (elSidebarBackdrop) {
        elSidebarBackdrop.addEventListener("click", () => {
            elSidebar.classList.remove("active");
            elSidebarBackdrop.classList.remove("active");
        });
    }

    // Inicializa Gestor do Report de Início da Operação
    initReportInicioManager();
}

// Dispara a inicialização assim que o DOM estiver pronto ou imediatamente se já carregou
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDashboardApp);
} else {
    initDashboardApp();
}

// Funcao assincrona para requisitar opcoes disponiveis e preencher os dropdowns de filtros
async function loadFilterDropdowns() {
    try {
        // Faz a chamada à rota de metadados de filtros da API local
        const response = await fetch(`${API_BASE}/api/filters?_=${Date.now()}`);
        // Converte a resposta em objeto JSON JavaScript
        const data = await response.json();
        
        // Verifica se a API retornou datas validas
        if (data.min_date && data.max_date) {
            // Define o limite minimo do seletor de data inicial
            elStartDate.min = data.min_date;
            // Define o limite maximo do seletor de data inicial
            elStartDate.max = data.max_date;
            // Define o limite minimo do seletor de data final
            elEndDate.min = data.min_date;
            // Define o limite maximo do seletor de data final
            elEndDate.max = data.max_date;
            
            // Define a data inicial selecionada padrao como a data mais antiga da planilha
            elStartDate.value = data.min_date;
            // Define a data final selecionada padrao como a data mais recente da planilha
            elEndDate.value = data.max_date;
        }
        
        // Itera inserindo as estacoes de recebimento encontradas no dropdown select correspondente
        data.receiving_stations.forEach(st => {
            // Instancia uma tag option vazia
            const opt = document.createElement("option");
            // Define a propriedade de valor da option
            opt.value = st;
            // Define a string visivel da option
            opt.textContent = st;
            // Insere a option dentro do dropdown de recebimento
            elReceiving.appendChild(opt);
        });
        
        // Itera inserindo as estacoes de registro encontradas no dropdown select correspondente
        data.registering_stations.forEach(st => {
            // Instancia uma tag option vazia
            const opt = document.createElement("option");
            // Define o valor da option
            opt.value = st;
            // Define o texto visivel
            opt.textContent = st;
            // Insere no dropdown de registro
            elRegistering.appendChild(opt);
        });
        
        // Itera populando os status operacional localizados na planilha de dados
        data.statuses.forEach(st => {
            // Instancia tag option vazia
            const opt = document.createElement("option");
            // Atribui o valor do status
            opt.value = st;
            // Atribui o texto visivel
            opt.textContent = st;
            // Insere no select de status
            elStatus.appendChild(opt);
        });
        
    } catch (err) {
        // Trata e loga qualquer falha de conexao com a API
        console.error("Erro ao carregar filtros:", err);
    }
}

// Funcao principal para requisitar a lista atualizada de dados do backend conforme os filtros
async function refreshData() {
    // Monta os parametros de busca HTTP obtidos das selecoes do usuario nos dropdowns
    const params = new URLSearchParams({
        // Obtem data inicial do input
        start_date: elStartDate.value,
        // Obtem data final do input
        end_date: elEndDate.value,
        // Obtem estacao de recebimento escolhida
        receiving_station: elReceiving.value,
        // Obtem estacao de registro escolhida
        registering_station: elRegistering.value,
        // Obtem status operacional escolhido
        status: elStatus.value
    });
    
    try {
        // Executa as requisições à API em paralelo para diminuir o tempo de resposta pela metade
        const [response, evolutionResponse] = await Promise.all([
            fetch(`${API_BASE}/api/data?${params.toString()}&_=${Date.now()}`),
            fetch(`${API_BASE}/api/data_evolution?${params.toString()}&_=${Date.now()}`).catch(evoErr => {
                console.error("Erro ao carregar dados de evolução:", evoErr);
                return null;
            })
        ]);
        
        allData = await response.json();
        const evolutionData = evolutionResponse ? await evolutionResponse.json().catch(() => []) : [];
        
        // Clona a lista de dados brutos na lista de dados ativos filtrados
        filteredData = [...allData];
        // Reinicia a pagina ativa da visualizacao da tabela
        currentPage = 1;
        
        // Atualiza os cartoes de indicadores KPIs do dashboard
        updateKPIs();
        // Atualiza a renderizacao dos graficos interativos no canvas passando os dados de evolução
        renderCharts(evolutionData);
        // Atualiza as linhas visiveis na tabela detalhada
        renderTable();
        
    } catch (err) {
        // Loga falhas no console
        console.error("Erro ao carregar dados:", err);
    }
}

// Reseta todos os seletores de filtros para o estado original padrão (geral)
function resetFilters() {
    // Volta a data de inicio para a data minima permitida
    elStartDate.value = elStartDate.min;
    // Volta a data final para a data maxima permitida
    elEndDate.value = elEndDate.max;
    // Seleciona a opcao de exibir todas as estacoes de recebimento
    elReceiving.value = "Todas";
    // Seleciona a opcao de exibir todas as estacoes de registro
    elRegistering.value = "Todas";
    // Seleciona a opcao de exibir todos os status operacionais
    elStatus.value = "Todos";
    // Limpa a barra de pesquisa de remessas
    elTableSearch.value = "";
    // Limpa a string de busca em memoria
    searchQuery = "";
    // Dispara a recarga de dados do servidor resetando a tela
    refreshData();
}

// Atualiza os valores numericos e percentuais exibidos nos cards de KPIs superiores
function updateKPIs() {
    // Quantidade total de registros carregados na busca atual
    const total = allData.length;
    // Altera o texto do card de total de remessas na tela
    elValTotal.textContent = total;
    
    // Tratamento preventivo de divisao por zero caso nao seja encontrada nenhuma remessa
    if (total === 0) {
        // Atribui zero às concluidas
        elValConcluidas.textContent = 0;
        // Atribui zero às pendentes
        elValPendentes.textContent = 0;
        // Atribui zero às criticas
        elValCriticas.textContent = 0;
        // Zera percentuais
        elPctConcluidas.textContent = "0%";
        // Zera percentuais
        elPctPendentes.textContent = "0%";
        // Zera percentuais
        elPctCriticas.textContent = "0%";
        // Encerra a funcao
        return;
    }
    
    // Filtra e conta a quantidade de remessas com categoria mapeada igual a Concluída
    const concluidas = allData.filter(d => d.categoria === 'Concluída').length;
    // Filtra e conta a quantidade de remessas com categoria mapeada igual a Pendente
    const pendentes = allData.filter(d => d.categoria === 'Pendente').length;
    // Filtra e conta a quantidade de remessas com categoria mapeada igual a Crítica
    const criticas = allData.filter(d => d.categoria === 'Crítica').length;
    
    // Insere no respectivo elemento da tela a contagem numerica calculada de concluidas
    elValConcluidas.textContent = concluidas;
    // Insere no respectivo elemento da tela a contagem de pendentes
    elValPendentes.textContent = pendentes;
    // Insere no respectivo elemento da tela a contagem de criticas
    elValCriticas.textContent = criticas;
    
    // Calcula e exibe a porcentagem correspondente ao grupo concluida formatado com uma casa decimal
    elPctConcluidas.textContent = `${((concluidas / total) * 100).toFixed(1)}%`;
    // Calcula e exibe a porcentagem correspondente ao grupo pendente
    elPctPendentes.textContent = `${((pendentes / total) * 100).toFixed(1)}%`;
    // Calcula e exibe a porcentagem correspondente ao grupo critica
    elPctCriticas.textContent = `${((criticas / total) * 100).toFixed(1)}%`;
}

// Funcao auxiliar para retornar a configuracao estrutural de opcoes comuns a graficos Chart.js
const getChartConfig = (type, data, options = {}) => {
    // Retorna o objeto completo no formato exigido pela instancia do Chart.js
    return {
        // Tipo do grafico (doughnut, bar, line)
        type: type,
        // Conjunto de dados (labels e datasets)
        data: data,
        // Dicionario de opcoes customizadas
        options: {
            // Garante que o canvas se ajuste dinamicamente ao container responsivo da tela
            responsive: true,
            // Permite que o container CSS defina a altura do grafico, sem manter proporcao fixa de tela
            maintainAspectRatio: false,
            // Configuracao do bloco de plugins graficos
            plugins: {
                // Configuracao da legenda do grafico
                legend: {
                    // Estiliza a fonte das legendas
                    labels: {
                        // Define a cor cinza claro para a legenda das cores
                        color: '#9CA3AF',
                        // Define a familia tipografica Outfit de tamanho 11
                        font: { family: 'Outfit', size: 11 }
                    }
                }
            },
            // Se o grafico for do tipo rosca (doughnut), nao inclui eixos cartesianos X/Y na configuracao
            scales: type !== 'doughnut' ? {
                // Configuracoes do Eixo X das categorias
                x: {
                    // Configuracoes de linhas de grade horizontais
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    // Estiliza os textos de categorias no eixo X
                    ticks: { color: '#9CA3AF', font: { family: 'Outfit' } }
                },
                // Configuracoes do Eixo Y dos valores
                y: {
                    // Linhas de grade verticais finas
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    // Estiliza os numeros de escala no eixo Y
                    ticks: { color: '#9CA3AF', font: { family: 'Outfit' } },
                    // Adiciona margem de 10% de folga no topo do eixo para evitar que os rótulos de dados fiquem cortados
                    grace: '10%'
                }
            } : {}, // Eixos cartesianos apenas para bar/line, vazio para doughnut
            // Mescla opcoes especificas adicionais passadas por parametro
            ...options
        }
    };
};

// Renderiza e atualiza todas as instancias dos graficos conforme a carga atual de dados em memoria
function renderCharts(evolutionData = []) {
    // 1. GRAFICO DE ROSCA: QUANTIDADE POR STATUS
    // Dicionario local para somar volumes por status operacional
    const statusCounts = {};
    // Itera somando a frequencia de cada status na lista filtrada
    allData.forEach(d => {
        // Soma mais um ao contador do status correspondente
        statusCounts[d.status] = (statusCounts[d.status] || 0) + 1;
    });
    
    // Mapeamento de cores padronizadas dos status para as fatias do grafico
    const statusColors = {
        'assinado': '#10B981', // Verde
        'expedido não chegou': '#EF4444', // Vermelho
        'recebido na base': '#3B82F6', // Azul vibrante
        'recebido em outra base': '#F59E0B', // Laranja vibrante
        'Devolução': '#DC2626', // Vermelho escuro
        'na base DC BAU': '#06B6D4', // Ciano
        'entregador': '#8B5CF6', // Roxo vibrante
        'interceptado': '#EC4899', // Rosa/Pink
        'erro triagem': '#F43F5E' // Coral/Rose
    };
    
    // Converte chaves do dicionario em array de labels
    const labelsStatus = Object.keys(statusCounts);
    // Converte valores em array de dados
    const dataStatus = Object.values(statusCounts);
    // Mapeia cada label com sua respectiva cor hexadecimal de paleta ou cinza padrao (com normalizacao preventiva de case)
    const colorsStatus = labelsStatus.map(lbl => {
        const cleaned = lbl.trim();
        return statusColors[cleaned] || statusColors[cleaned.toLowerCase()] || '#6B7280';
    });
    
    // Se a instancia do grafico ja existir na tela, destroi ela para liberar memoria e recriar limpa
    if (chartStatus) chartStatus.destroy();
    // Instancia o novo grafico de Rosca de status
    chartStatus = new Chart(document.getElementById("chart-status"), getChartConfig('doughnut', {
        // Nome dos status
        labels: labelsStatus,
        // Serie de dados
        datasets: [{
            // Contagem numerica das fatias
            data: dataStatus,
            // Cores das fatias
            backgroundColor: colorsStatus,
            // Espessura da borda divisoria de 1 pixel
            borderWidth: 1,
            // Cor escura da borda combinando com a cor do card
            borderColor: '#0F131E'
        }]
    }, {
        // Opcoes adicionais especificas: move as legendas para a direita
        plugins: {
            legend: {
                position: 'right',
                // Define tamanho menor para nao amontoar as legendas na rosca
                labels: { color: '#9CA3AF', font: { family: 'Outfit', size: 10 } }
            }
        }
    }));
    
    // 2. GRAFICO DE BARRAS: ESTACAO DE RECEBIMENTO
    // Dicionario auxiliar para somar contagem por estacoes de recebimento
    const recCounts = {};
    // Itera preenchendo as contagens
    allData.forEach(d => {
        // Soma mais um para a estacao de recebimento correspondente
        recCounts[d.estacao_recebimento] = (recCounts[d.estacao_recebimento] || 0) + 1;
    });
    
    // Se a instancia de recebimento ja existir, destroi ela
    if (chartReceiving) chartReceiving.destroy();
    // Instancia o grafico de colunas de recebimento
    chartReceiving = new Chart(document.getElementById("chart-receiving"), getChartConfig('bar', {
        // Nome das estacoes de recebimento no eixo X
        labels: Object.keys(recCounts),
        // Serie de dados
        datasets: [{
            // Label da serie
            label: 'Volume de Recebimento',
            // Valores quantitativos
            data: Object.values(recCounts),
            // Cor azul solido das colunas
            backgroundColor: '#3B82F6',
            // Arredonda as pontas superiores das colunas em 6 pixels para visual moderno
            borderRadius: 6
        }]
    }));
    
    // 3. GRAFICO DE BARRAS: ESTACAO DE REGISTRO (TOP 5)
    // Dicionario auxiliar para somar volumes das estacoes de registro
    const regCounts = {};
    // Itera populando as contagens de registro
    allData.forEach(d => {
        // Soma mais um para a estacao correspondente
        regCounts[d.estacao_registro] = (regCounts[d.estacao_registro] || 0) + 1;
    });
    
    // Converte o dicionario de registro em array ordenado decrescentemente para extrair o Top 5
    const topReg = Object.entries(regCounts)
        // Ordena comparando as quantidades (elemento [1]) de forma decrescente
        .sort((a, b) => b[1] - a[1])
        // Corta o array para manter apenas as 5 primeiras posicoes
        .slice(0, 5);
        
    // Destroi o grafico de registro anterior se ele existir
    if (chartRegistering) chartRegistering.destroy();
    // Instancia o grafico Top 5 de registros
    chartRegistering = new Chart(document.getElementById("chart-registering"), getChartConfig('bar', {
        // Nomes das top 5 estacoes mapeadas no eixo X
        labels: topReg.map(e => e[0]),
        // Serie de dados
        datasets: [{
            // Titulo da serie
            label: 'Volume de Registro',
            // Quantidades correspondentes ao Top 5
            data: topReg.map(e => e[1]),
            // Cor verde das colunas do grafico
            backgroundColor: '#10B981',
            // Arredondamento do topo das colunas em 6 pixels
            borderRadius: 6
        }]
    }));
    
    // 4. GRAFICO DE LINHA: EVOLUCAO DIARIA DE ENVIOS
    // Dicionario para mapear e somar volumes de envios por data (YYYY-MM-DD)
    const dailyCounts = {};
    // Itera por todos os registros filtrados de evolução (inclui os 5 dias anteriores)
    const chartSourceData = (evolutionData && evolutionData.length > 0) ? evolutionData : allData;
    chartSourceData.forEach(d => {
        // Extrai a parte da data da string de envio (ex: "24/06/2026 10:47:12" -> "24/06/2026")
        const parts = d.hora_envio.split(" ")[0].split("/");
        // Monta a string no formato ISO (YYYY-MM-DD) para ordenacao cronologica correta
        const dateKey = `${parts[2]}-${parts[1]}-${parts[0]}`;
        // Soma mais um ao respectivo dia
        dailyCounts[dateKey] = (dailyCounts[dateKey] || 0) + 1;
    });
    
    // Ordena as datas de forma crescente
    const sortedDates = Object.keys(dailyCounts).sort();
    // Cria array com os volumes ordenados cronologicamente
    const dataEvolution = sortedDates.map(d => dailyCounts[d]);
    // Cria labels amigaveis formatadas em padrao brasileiro de dia e mes (DD/MM) para o eixo X
    const labelsEvolution = sortedDates.map(d => {
        // Separa partes ano, mes, dia
        const parts = d.split("-");
        // Retorna Dia/Mes
        return `${parts[2]}/${parts[1]}`;
    });
    
    // Destroi o grafico anterior de evolucao se existir
    if (chartEvolution) chartEvolution.destroy();
    // Instancia o grafico de linhas continuo
    chartEvolution = new Chart(document.getElementById("chart-evolution"), getChartConfig('line', {
        // Datas no formato DD/MM no eixo X
        labels: labelsEvolution,
        // Serie de dados de linhas
        datasets: [{
            // Label descritivo
            label: 'Remessas Enviadas',
            // Volumes diarios ordenados
            data: dataEvolution,
            // Cor azul solido do contorno da linha
            borderColor: '#3B82F6',
            // Cor azul translúcida para preenchimento de area abaixo da linha
            backgroundColor: 'rgba(59, 130, 246, 0.1)',
            // Habilita o preenchimento sob a linha (efeito area chart)
            fill: true,
            // Define a suavidade das curvas da linha (curva de Bezier) em 0.3
            tension: 0.3,
            // Espessura da linha do grafico de 2 pixels
            borderWidth: 2,
            // Cor do preenchimento interno das bolinhas nos vertices de cada dia
            pointBackgroundColor: '#3B82F6',
            // Raio de 3 pixels para as bolinhas dos vertices
            pointRadius: 3
        }]
    }));
}

// Renderiza a Tabela Detalhada de Registros com suporte a busca local e paginação
function renderTable() {
    // Se houver algum texto digitado na barra de pesquisa
    if (searchQuery) {
        // Filtra a lista ativa mantendo apenas registros cujo codigo de remessa contenha a string digitada
        filteredData = allData.filter(d => d.remessa.toLowerCase().includes(searchQuery));
    } else {
        // Caso contrario, mantem a lista total ativa
        filteredData = [...allData];
    }
    
    // Quantidade total de registros após o filtro de busca local aplicado
    const total = filteredData.length;
    // Calcula o total de paginas necessarias dividindo o total de registros por 10 e arredondando para cima
    const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
    
    // Garante que a pagina corrente nao ultrapasse o limite maximo de paginas calculado
    if (currentPage > totalPages) currentPage = totalPages;
    
    // Calcula o indice inicial do fatiamento do array conforme a pagina atual
    const startIndex = (currentPage - 1) * rowsPerPage;
    // Calcula o limite final do fatiamento cuidando para nao exceder o tamanho da lista
    const endIndex = Math.min(startIndex + rowsPerPage, total);
    // Fatia a lista exibindo apenas os 10 itens correspondentes à pagina ativa
    const paginatedData = filteredData.slice(startIndex, endIndex);
    
    // Limpa as linhas anteriores da tabela
    elTableBody.innerHTML = "";
    
    // Valida se nao ha registros sob a busca local
    if (paginatedData.length === 0) {
        // Exibe uma linha com mensagem informativa de dados nao localizados
        elTableBody.innerHTML = `<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Nenhum registro encontrado.</td></tr>`;
        // Atualiza a contagem informativa do rodape
        elTableInfo.textContent = "Mostrando 0 de 0 registros";
        // Desativa o botao de voltar pagina
        elBtnPrev.disabled = true;
        // Desativa o botao de avancar pagina
        elBtnNext.disabled = true;
        // Retorna o numero da pagina corrente como 1
        elPageNum.textContent = "1";
        // Encerra a funcao
        return;
    }
    
    // Itera construindo dinamicamente as linhas HTML da tabela em lote único
    elTableBody.innerHTML = paginatedData.map(row => {
        let badgeClass = "badge-pendente"; // Pendentes: amarelo/laranja por padrao
        if (row.categoria === 'Concluída') badgeClass = "badge-concluido";
        if (row.categoria === 'Crítica') badgeClass = "badge-critico";
        return `
            <tr>
                <td><b>${row.remessa}</b></td>
                <td>${row.hora_envio}</td>
                <td>${row.estacao_recebimento}</td>
                <td>${row.estacao_registro}</td>
                <td><span class="badge ${badgeClass}">${row.status}</span></td>
            </tr>
        `;
    }).join("");
    
    // Atualiza o rodape da tabela informando o intervalo de registros exibidos (ex: Mostrando 1-10 de 280)
    elTableInfo.textContent = `Mostrando ${startIndex + 1}-${endIndex} de ${total} registros`;
    // Altera o indicador textual da pagina ativa
    elPageNum.textContent = currentPage;
    // Desativa o botao de voltar se o usuario ja estiver na primeira pagina
    elBtnPrev.disabled = currentPage === 1;
    // Desativa o botao de avancar se o usuario ja estiver na ultima pagina
    elBtnNext.disabled = currentPage === totalPages;
}

// Direciona o navegador para baixar o PDF com as mesmas configuracoes de filtros ativas na tela
function generatePdfReport() {
    // Monta os query parameters contendo as strings de selecao atuais dos filtros do dashboard
    const params = new URLSearchParams({
        // Obtem data inicial do seletor
        start_date: elStartDate.value,
        // Obtem data final do seletor
        end_date: elEndDate.value,
        // Obtem estacao de recebimento do seletor
        receiving_station: elReceiving.value,
        // Obtem estacao de registro do seletor
        registering_station: elRegistering.value,
        // Obtem status operacional do seletor
        status: elStatus.value
    });
    
    // Redireciona o navegador para a rota de geracao de PDF da API local com os parametros anexados
    window.location.href = `${API_BASE}/api/generate_pdf?${params.toString()}&_=${Date.now()}`;
}

// --- NOVAS FUNÇÕES DA VISÃO SEM MOVIMENTAÇÃO ---

// Cache de timestamp das abas para navegação instantânea (evita recarregamento repetido em navegações rápidas)
const tabLastLoaded = {};
function shouldReloadTab(tab, ttlMs = 120000) {
    const now = Date.now();
    if (!tabLastLoaded[tab] || (now - tabLastLoaded[tab] > ttlMs)) {
        tabLastLoaded[tab] = now;
        return true;
    }
    return false;
}

// Alterna a aba ativa no dashboard
function switchTab(tab) {
    if (tab === activeTab) return;
    activeTab = tab;
    
    // Fecha a barra lateral no mobile após selecionar uma aba
    if (window.innerWidth <= 768) {
        if (elSidebar) elSidebar.classList.remove("active");
        if (elSidebarBackdrop) elSidebarBackdrop.classList.remove("active");
    }
    
    // Desativa todos os itens de navegação
    document.querySelectorAll(".nav-item").forEach(item => item.classList.remove("active"));
    
    // Ativa o item correspondente
    const elNavActive = document.getElementById(`nav-${tab}`);
    if (elNavActive) elNavActive.classList.add("active");
    
    // Esconde todos os painéis e filtros
    const panels = ["general", "sem-mov", "avaria", "controle", "producao", "volume-exp-dc-bau", "recebimento", "volumetria", "ranking", "pda", "report-inicio"];
    panels.forEach(p => {
        const elPanel = document.getElementById(`panel-${p}`);
        const elFilters = document.getElementById(`filters-${p}`);
        if (elPanel) elPanel.style.display = "none";
        if (elFilters) elFilters.style.display = "none";
    });
    
    // Exibe o painel e filtros da aba selecionada
    const elPanelActive = document.getElementById(`panel-${tab}`);
    const elFiltersActive = document.getElementById(`filters-${tab}`);
    if (elPanelActive) {
        elPanelActive.style.display = "flex";
    }
    if (elFiltersActive) {
        elFiltersActive.style.display = "block";
    }
    
    if (tab === "general") {
        document.querySelector(".nav-title h1").textContent = "Expedido Não Chegou";
        document.querySelector(".nav-title p").textContent = "Visão executiva operacional de remessas e tráfego";
        if (shouldReloadTab(tab)) refreshData();
    } else if (tab === "sem-mov") {
        document.querySelector(".nav-title h1").textContent = "Sem Movimentação";
        document.querySelector(".nav-title p").textContent = "Análise de contratos parados, multas e aging por base";
        if (shouldReloadTab(tab)) refreshSemMovData();
    } else if (tab === "avaria") {
        document.querySelector(".nav-title h1").textContent = "Controle de Avarias";
        document.querySelector(".nav-title p").textContent = "Visão executiva de danos a produtos e desempenho de colaboradores";
        if (shouldReloadTab(tab)) refreshAvariaData();
    } else if (tab === "controle") {
        document.querySelector(".nav-title h1").textContent = "Fechamento";
        document.querySelector(".nav-title p").textContent = "Relatório consolidado operacional, recebimento de veículos, RH e fechamento de turno";
        if (shouldReloadTab(tab)) loadControleData();
    } else if (tab === "producao") {
        document.querySelector(".nav-title h1").textContent = "Produção e Produtividade";
        document.querySelector(".nav-title p").textContent = "Indicadores de produtividade por canal, PPH e alocação de equipe do DC Bauru";
        if (shouldReloadTab(tab)) loadProducaoData();
    } else if (tab === "volume-exp-dc-bau") {
        document.querySelector(".nav-title h1").textContent = "Volume Expedido DC Bauru";
        document.querySelector(".nav-title p").textContent = "Controle de volumes previstos, recebidos e cargas não entregues por veículo";
        if (shouldReloadTab(tab)) loadVolumeExpData();
    } else if (tab === "recebimento") {
        document.querySelector(".nav-title h1").textContent = "Recebimento";
        document.querySelector(".nav-title p").textContent = "Controle e análise de volumes recebidos, coletas e lotes da planilha Recebimento";
        if (shouldReloadTab(tab)) loadRecebimentoFilters();
    } else if (tab === "volumetria") {
        document.querySelector(".nav-title h1").textContent = "Controle de Volumetria Diária";
        document.querySelector(".nav-title p").textContent = "Acompanhamento diário de pedidos do sistema, bipagem no piso e volumetria por viagem";
        if (shouldReloadTab(tab)) loadVolumetriaData();
    } else if (tab === "ranking") {
        document.querySelector(".nav-title h1").textContent = "Ranking & Produtividade";
        document.querySelector(".nav-title p").textContent = "Classificação de operadores, bipes por setor e evolução de produtividade hora a hora";
        if (shouldReloadTab(tab)) loadRankingData();
    } else if (tab === "pda") {
        document.querySelector(".nav-title h1").textContent = "Controle de PDAs";
        document.querySelector(".nav-title p").textContent = "Quadro geral de gestão, retiradas e devoluções dos 36 PDAs do DC Bauru";
        if (elIframePda) {
            const targetUrl = window.location.protocol === "file:" ? "controle-pda/index.html" : "/pda/";
            if (!elIframePda.src || elIframePda.src === "about:blank" || (!elIframePda.src.includes("controle-pda") && !elIframePda.src.includes("/pda/"))) {
                elIframePda.src = targetUrl;
            } else {
                try {
                    if (elIframePda.contentWindow) {
                        elIframePda.contentWindow.postMessage({ action: 'syncNow' }, '*');
                    }
                } catch(e) {}
            }
            if (elBtnPdaExternal) elBtnPdaExternal.href = targetUrl;
            if (elBtnPdaOpenTab) elBtnPdaOpenTab.href = targetUrl;
        }
    } else if (tab === "report-inicio") {
        document.querySelector(".nav-title h1").textContent = "Report de Início da Operação";
        document.querySelector(".nav-title p").textContent = "Acompanhamento operacional inicial, presença de CLTs, diaristas e metas do turno";
        if (typeof loadReportInicioData === "function") {
            loadReportInicioData();
        }
    }
}

// Carrega os dropdowns de filtros para a visão Sem Movimentação
async function loadSemMovFilterDropdowns() {
    try {
        const response = await fetch(`${API_BASE}/api/sem_mov/filters?_=${Date.now()}`);
        const data = await response.json();
        
        // Limpa opções anteriores mantendo a padrão
        elAgingOptionsContainer.innerHTML = '';
        elSemMovBase.innerHTML = '<option value="Todas">Todas as Bases</option>';
        elSemMovDestino.innerHTML = '<option value="Todos">Todos os Destinos</option>';
        
        // Popula checkboxes de Aging
        data.aging.forEach(val => {
            const label = document.createElement("label");
            label.innerHTML = `
                <input type="checkbox" class="aging-checkbox" value="${val}" checked>
                <span>${val}</span>
            `;
            elAgingOptionsContainer.appendChild(label);
            
            // Listener individual de checkbox
            label.querySelector("input").addEventListener("change", () => {
                const checkedBoxes = document.querySelectorAll(".aging-checkbox:checked");
                const allBoxes = document.querySelectorAll(".aging-checkbox");
                
                elAgingSelectAll.checked = (checkedBoxes.length === allBoxes.length);
                updateAgingTriggerText();
                refreshSemMovData();
            });
        });
        
        // Atualiza o texto do botão trigger
        updateAgingTriggerText();
        
        data.base.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elSemMovBase.appendChild(opt);
        });
        
        data.destino.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elSemMovDestino.appendChild(opt);
        });
    } catch (err) {
        console.error("Erro ao carregar filtros de sem movimentação:", err);
    }
}

// Obtém a lista de agings selecionados
function getSelectedAgings() {
    const checkedBoxes = document.querySelectorAll(".aging-checkbox:checked");
    const allBoxes = document.querySelectorAll(".aging-checkbox");
    
    if (checkedBoxes.length === allBoxes.length && allBoxes.length > 0) {
        return ["Todos"];
    }
    
    if (checkedBoxes.length === 0) {
        return ["Nenhum"]; // Indica nenhum selecionado
    }
    
    const selected = [];
    checkedBoxes.forEach(cb => selected.push(cb.value));
    return selected;
}

// Atualiza o texto descritivo no trigger do multi-select de Aging
function updateAgingTriggerText() {
    const checkedBoxes = document.querySelectorAll(".aging-checkbox:checked");
    const allBoxes = document.querySelectorAll(".aging-checkbox");
    const span = elAgingMultiselectTrigger.querySelector("span");
    
    if (allBoxes.length === 0) {
        span.textContent = "Carregando...";
        return;
    }
    
    if (checkedBoxes.length === allBoxes.length) {
        span.textContent = "Todos os Agings";
    } else if (checkedBoxes.length === 0) {
        span.textContent = "Nenhum selecionado";
    } else if (checkedBoxes.length === 1) {
        span.textContent = checkedBoxes[0].value;
    } else {
        span.textContent = `${checkedBoxes.length} selecionados`;
    }
}

// Atualiza os dados da visão Sem Movimentação conforme filtros ativos
async function refreshSemMovData() {
    const selectedAgings = getSelectedAgings();
    
    // Se nenhum estiver selecionado, podemos retornar vazio imediatamente ou enviar "Nenhum"
    if (selectedAgings.length === 1 && selectedAgings[0] === "Nenhum") {
        semMovData = [];
        semMovFilteredData = [];
        semMovCurrentPage = 1;
        updateSemMovKPIs();
        renderSemMovCharts();
        renderSemMovTable();
        return;
    }
    
    const params = new URLSearchParams({
        base: elSemMovBase.value,
        destino: elSemMovDestino.value
    });
    
    selectedAgings.forEach(val => {
        params.append("aging", val);
    });
    
    try {
        const response = await fetch(`${API_BASE}/api/sem_mov/data?${params.toString()}&_=${Date.now()}`);
        semMovData = await response.json();
        if (!Array.isArray(semMovData)) semMovData = semMovData?.records || [];
        semMovFilteredData = [...semMovData];
        semMovCurrentPage = 1;
        
        updateSemMovKPIs();
        renderSemMovCharts();
        renderSemMovTable();
    } catch (err) {
        console.error("Erro ao carregar dados de sem movimentação:", err);
    }
}

// Limpa filtros da visão Sem Movimentação
function resetSemMovFilters() {
    // Marca todos os checkboxes
    const optionBoxes = document.querySelectorAll(".aging-checkbox");
    optionBoxes.forEach(cb => {
        cb.checked = true;
    });
    elAgingSelectAll.checked = true;
    updateAgingTriggerText();
    
    elSemMovBase.value = "Todas";
    elSemMovDestino.value = "Todos";
    elTableSemMovSearch.value = "";
    semMovSearchQuery = "";
    refreshSemMovData();
}

// Atualiza cards de KPIs superiores da visão Sem Movimentação
function updateSemMovKPIs() {
    const total = semMovData.length;
    elValSemMovTotal.textContent = total;
    
    if (total === 0) {
        elValSemMovMulta.textContent = "R$ 0,00";
        elValSemMovAging.textContent = "0 dias";
        elValSemMovMaxDias.textContent = "0 dias";
        return;
    }
    
    // Soma multas
    const totalMulta = semMovData.reduce((acc, row) => acc + row.multa, 0);
    // Média de dias
    const avgDias = semMovData.reduce((acc, row) => acc + row.dias_sem_mov, 0) / total;
    // Maior atraso
    const maxDias = Math.max(...semMovData.map(row => row.dias_sem_mov));
    
    elValSemMovMulta.textContent = `R$ ${totalMulta.toLocaleString("pt-BR", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    elValSemMovAging.textContent = `${avgDias.toFixed(1)} dias`;
    elValSemMovMaxDias.textContent = `${maxDias} dias`;
}

// Renderiza os gráficos da visão Sem Movimentação
function renderSemMovCharts() {
    // 1. Contratos por Base
    const baseCounts = {};
    semMovData.forEach(d => {
        baseCounts[d.base] = (baseCounts[d.base] || 0) + 1;
    });
    
    const baseLabels = Object.keys(baseCounts).sort((a, b) => baseCounts[b] - baseCounts[a]);
    const baseValues = baseLabels.map(l => baseCounts[l]);
    
    if (chartSemMovBase) chartSemMovBase.destroy();
    chartSemMovBase = new Chart(document.getElementById("chart-sem-mov-base"), getChartConfig('bar', {
        labels: baseLabels,
        datasets: [{
            label: 'Quantidade de Contratos',
            data: baseValues,
            backgroundColor: '#3B82F6',
            borderRadius: 6
        }]
    }));
    
    // 2. Contratos por Destino (Top 5)
    const destCounts = {};
    semMovData.forEach(d => {
        destCounts[d.destino] = (destCounts[d.destino] || 0) + 1;
    });
    
    const destLabelsSorted = Object.keys(destCounts).sort((a, b) => destCounts[b] - destCounts[a]);
    const topDestLabels = destLabelsSorted.slice(0, 5);
    const topDestValues = topDestLabels.map(l => destCounts[l]);
    
    if (chartSemMovDestino) chartSemMovDestino.destroy();
    chartSemMovDestino = new Chart(document.getElementById("chart-sem-mov-destino"), getChartConfig('bar', {
        labels: topDestLabels,
        datasets: [{
            label: 'Quantidade de Contratos',
            data: topDestValues,
            backgroundColor: '#10B981',
            borderRadius: 6
        }]
    }));
    
    // 3. Média Dias Sem Mov por Base
    // Agrupa e calcula a média
    const baseDelays = {};
    const baseDelaysCount = {};
    semMovData.forEach(d => {
        baseDelays[d.base] = (baseDelays[d.base] || 0) + d.dias_sem_mov;
        baseDelaysCount[d.base] = (baseDelaysCount[d.base] || 0) + 1;
    });
    
    const baseDelayLabels = Object.keys(baseDelays);
    const baseDelayAverages = baseDelayLabels.map(l => +(baseDelays[l] / baseDelaysCount[l]).toFixed(1));
    
    // Ordena decrescente
    const delayData = baseDelayLabels.map((l, i) => ({ label: l, val: baseDelayAverages[i] }))
        .sort((a, b) => b.val - a.val);
        
    if (chartSemMovDelayBase) chartSemMovDelayBase.destroy();
    chartSemMovDelayBase = new Chart(document.getElementById("chart-sem-mov-delay-base"), getChartConfig('bar', {
        labels: delayData.map(d => d.label),
        datasets: [{
            label: 'Média de Dias Parados',
            data: delayData.map(d => d.val),
            backgroundColor: '#F59E0B',
            borderRadius: 6
        }]
    }));
    
    // 4. Distribuição por Aging (Doughnut)
    const agingCounts = {};
    semMovData.forEach(d => {
        agingCounts[d.aging] = (agingCounts[d.aging] || 0) + 1;
    });
    
    const agingLabels = Object.keys(agingCounts);
    const agingValues = Object.values(agingCounts);
    
    const colorsList = ['#EF4444', '#F59E0B', '#3B82F6', '#10B981', '#8B5CF6', '#EC4899', '#6B7280', '#111827'];
    const agingColors = agingLabels.map((_, i) => colorsList[i % colorsList.length]);
    
    if (chartSemMovAgingDist) chartSemMovAgingDist.destroy();
    chartSemMovAgingDist = new Chart(document.getElementById("chart-sem-mov-aging-dist"), getChartConfig('doughnut', {
        labels: agingLabels,
        datasets: [{
            data: agingValues,
            backgroundColor: agingColors,
            borderWidth: 1,
            borderColor: '#0F131E'
        }]
    }, {
        plugins: {
            legend: {
                position: 'right',
                labels: { color: '#9CA3AF', font: { family: 'Outfit', size: 9 } }
            }
        }
    }));
}

// Renderiza a tabela da visão Sem Movimentação com suporte a paginação e busca
function renderSemMovTable() {
    if (semMovSearchQuery) {
        semMovFilteredData = semMovData.filter(d => d.remessa.toLowerCase().includes(semMovSearchQuery));
    } else {
        semMovFilteredData = [...semMovData];
    }
    
    const total = semMovFilteredData.length;
    const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
    
    if (semMovCurrentPage > totalPages) semMovCurrentPage = totalPages;
    
    const startIndex = (semMovCurrentPage - 1) * rowsPerPage;
    const endIndex = Math.min(startIndex + rowsPerPage, total);
    const paginatedData = semMovFilteredData.slice(startIndex, endIndex);
    
    elTableSemMovBody.innerHTML = "";
    
    if (paginatedData.length === 0) {
        elTableSemMovBody.innerHTML = `<tr><td colspan="8" style="text-align: center; color: var(--text-muted);">Nenhum contrato encontrado.</td></tr>`;
        elTableSemMovInfo.textContent = "Mostrando 0 de 0 registros";
        elBtnSemMovPrev.disabled = true;
        elBtnSemMovNext.disabled = true;
        elPageSemMovNum.textContent = "1";
        return;
    }
    
    elTableSemMovBody.innerHTML = paginatedData.map(row => `
        <tr>
            <td><b>${row.remessa}</b></td>
            <td>${row.ultima_operacao.split(" ")[0]}</td>
            <td>${row.tipo_problematico}</td>
            <td><span class="badge badge-critico">${row.aging}</span></td>
            <td>${row.dias_sem_mov} dias</td>
            <td>R$ ${row.multa.toLocaleString("pt-BR", { minimumFractionDigits: 2 })}</td>
            <td>${row.base}</td>
            <td>${row.destino}</td>
        </tr>
    `).join("");
    
    elTableSemMovInfo.textContent = `Mostrando ${startIndex + 1}-${endIndex} de ${total} registros`;
    elPageSemMovNum.textContent = semMovCurrentPage;
    elBtnSemMovPrev.disabled = semMovCurrentPage === 1;
    elBtnSemMovNext.disabled = semMovCurrentPage === totalPages;
}

// Direciona download do relatório PDF filtrado para a visão Sem Movimentação
function generateSemMovPdfReport() {
    const selectedAgings = getSelectedAgings();
    const params = new URLSearchParams({
        base: elSemMovBase.value,
        destino: elSemMovDestino.value
    });
    selectedAgings.forEach(val => {
        params.append("aging", val);
    });
    window.location.href = `${API_BASE}/api/sem_mov/generate_pdf?${params.toString()}&_=${Date.now()}`;
}

// --- SEÇÃO DE FUNÇÕES DO MÓDULO DE AVARIAS ---

// Carrega os dropdowns de filtros para a visão de Avarias
async function loadAvariaFilterDropdowns() {
    try {
        const response = await fetch(`${API_BASE}/api/avaria/filters?_=${Date.now()}`);
        const data = await response.json();
        
        // Limpa opções anteriores mantendo as padrões
        elAvariaBase.innerHTML = '<option value="Todas">Todas as Bases</option>';
        elAvariaColaborador.innerHTML = '<option value="Todos">Todos os Colaboradores</option>';
        elAvariaProduto.innerHTML = '<option value="Todos">Todos os Produtos</option>';
        elAvariaStatus.innerHTML = '<option value="Todos">Todos os Status</option>';
        
        // Define limites e valores das datas
        if (data.min_date && data.max_date) {
            elAvariaStartDate.min = data.min_date;
            elAvariaStartDate.max = data.max_date;
            elAvariaEndDate.min = data.min_date;
            elAvariaEndDate.max = data.max_date;
            
            elAvariaStartDate.value = data.min_date;
            elAvariaEndDate.value = data.max_date;
        }
        
        // Popula Base de Origem
        data.base.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elAvariaBase.appendChild(opt);
        });
        
        // Popula Colaboradores
        data.colaborador.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elAvariaColaborador.appendChild(opt);
        });
        
        // Popula Produtos
        data.produto.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elAvariaProduto.appendChild(opt);
        });
        
        // Popula Status
        data.status.forEach(val => {
            const opt = document.createElement("option");
            opt.value = val;
            opt.textContent = val;
            elAvariaStatus.appendChild(opt);
        });
    } catch (err) {
        console.error("Erro ao carregar filtros de avarias:", err);
    }
}

// Atualiza os dados da visão de Avarias conforme filtros ativos
async function refreshAvariaData() {
    const params = new URLSearchParams({
        start_date: elAvariaStartDate.value,
        end_date: elAvariaEndDate.value,
        base: elAvariaBase.value,
        colaborador: elAvariaColaborador.value,
        produto: elAvariaProduto.value,
        status: elAvariaStatus.value
    });
    
    try {
        // Executa as requisições de Avarias em paralelo
        const [response, evolutionResponse] = await Promise.all([
            fetch(`${API_BASE}/api/avaria/data?${params.toString()}&_=${Date.now()}`),
            fetch(`${API_BASE}/api/avaria/data_evolution?${params.toString()}&_=${Date.now()}`).catch(evoErr => {
                console.error("Erro ao carregar dados de evolução de avarias:", evoErr);
                return null;
            })
        ]);
        
        avariaData = await response.json();
        if (!Array.isArray(avariaData)) avariaData = avariaData?.records || [];
        const avariaEvolutionData = evolutionResponse ? await evolutionResponse.json().catch(() => []) : [];
        
        avariaFilteredData = [...avariaData];
        avariaCurrentPage = 1;
        
        updateAvariaKPIs();
        renderAvariaCharts(avariaEvolutionData);
        renderAvariaTable();
    } catch (err) {
        console.error("Erro ao carregar dados de avarias:", err);
    }
}

// Limpa filtros da visão de Avarias
function resetAvariaFilters() {
    // Busca limites de datas anteriores nos atributos do elemento
    elAvariaStartDate.value = elAvariaStartDate.min || "";
    elAvariaEndDate.value = elAvariaEndDate.max || "";
    
    elAvariaBase.value = "Todas";
    elAvariaColaborador.value = "Todos";
    elAvariaProduto.value = "Todos";
    elAvariaStatus.value = "Todos";
    
    elTableAvariaSearch.value = "";
    avariaSearchQuery = "";
    
    refreshAvariaData();
}

// Atualiza cards de KPIs superiores da visão de Avarias
function updateAvariaKPIs() {
    const total = avariaData.length;
    elValAvariaTotal.textContent = total;
    
    if (total === 0) {
        elValAvariaColaboradores.textContent = "0";
        elValAvariaViagens.textContent = "0";
        elValAvariaTopProduto.textContent = "-";
        return;
    }
    
    // Contagem de colaboradores únicos
    const colabs = new Set(avariaData.map(d => d.nome));
    elValAvariaColaboradores.textContent = colabs.size;
    
    // Contagem de viagens (carros) únicas
    const viagens = new Set(avariaData.map(d => d.id_de_viagem));
    elValAvariaViagens.textContent = viagens.size;
    
    // Identifica o produto mais afetado
    const prodCounts = {};
    avariaData.forEach(d => {
        prodCounts[d.produto] = (prodCounts[d.produto] || 0) + 1;
    });
    const topProduct = Object.keys(prodCounts).reduce((a, b) => prodCounts[a] > prodCounts[b] ? a : b, "-");
    elValAvariaTopProduto.textContent = topProduct;
}

// Renderiza os quatro gráficos de Avarias
function renderAvariaCharts(avariaEvolutionData = []) {
    // 1. Avarias por Colaborador
    const colabCounts = {};
    avariaData.forEach(d => {
        colabCounts[d.nome] = (colabCounts[d.nome] || 0) + 1;
    });
    const colabLabels = Object.keys(colabCounts).sort((a, b) => colabCounts[b] - colabCounts[a]);
    const colabValues = colabLabels.map(l => colabCounts[l]);
    
    if (chartAvariaColaborador) chartAvariaColaborador.destroy();
    chartAvariaColaborador = new Chart(document.getElementById("chart-avaria-colaborador"), getChartConfig('bar', {
        labels: colabLabels,
        datasets: [{
            label: 'Ocorrências',
            data: colabValues,
            backgroundColor: '#3B82F6',
            borderRadius: 6
        }]
    }));
    
    // 2. Avarias por Categoria de Produto
    const prodCounts = {};
    avariaData.forEach(d => {
        prodCounts[d.produto] = (prodCounts[d.produto] || 0) + 1;
    });
    const prodLabels = Object.keys(prodCounts).sort((a, b) => prodCounts[b] - prodCounts[a]);
    const prodValues = prodLabels.map(l => prodCounts[l]);
    
    if (chartAvariaProduto) chartAvariaProduto.destroy();
    chartAvariaProduto = new Chart(document.getElementById("chart-avaria-produto"), getChartConfig('bar', {
        labels: prodLabels,
        datasets: [{
            label: 'Ocorrências',
            data: prodValues,
            backgroundColor: '#10B981',
            borderRadius: 6
        }]
    }));
    
    // 3. Distribuição por Status (Classificação)
    const statusCounts = {};
    avariaData.forEach(d => {
        statusCounts[d.status] = (statusCounts[d.status] || 0) + 1;
    });
    const statusLabels = Object.keys(statusCounts);
    const statusValues = Object.values(statusCounts);
    
    const colorsList = ['#3B82F6', '#EF4444', '#F59E0B', '#10B981', '#8B5CF6', '#EC4899', '#6B7280'];
    const statusColors = statusLabels.map((_, i) => colorsList[i % colorsList.length]);
    
    if (chartAvariaStatusDist) chartAvariaStatusDist.destroy();
    chartAvariaStatusDist = new Chart(document.getElementById("chart-avaria-status-dist"), getChartConfig('doughnut', {
        labels: statusLabels,
        datasets: [{
            data: statusValues,
            backgroundColor: statusColors,
            borderWidth: 1,
            borderColor: '#0F131E'
        }]
    }, {
        plugins: {
            legend: {
                position: 'right',
                labels: { color: '#9CA3AF', font: { family: 'Outfit', size: 9 } }
            }
        }
    }));
    
    // 4. Evolução Diária de Avarias (Line Chart)
    const dailyCounts = {};
    const chartSourceData = (avariaEvolutionData && avariaEvolutionData.length > 0) ? avariaEvolutionData : avariaData;
    chartSourceData.forEach(d => {
        // Agrupa por data formatada
        const dateStr = d.data.split(" ")[0];
        dailyCounts[dateStr] = (dailyCounts[dateStr] || 0) + 1;
    });
    
    // Ordena as datas cronologicamente
    const dailyLabels = Object.keys(dailyCounts).sort((a, b) => {
        const partsA = a.split("/");
        const partsB = b.split("/");
        return new Date(partsA[2], partsA[1]-1, partsA[0]) - new Date(partsB[2], partsB[1]-1, partsB[0]);
    });
    const dailyValues = dailyLabels.map(l => dailyCounts[l]);
    
    if (chartAvariaEvolution) chartAvariaEvolution.destroy();
    chartAvariaEvolution = new Chart(document.getElementById("chart-avaria-evolution"), getChartConfig('line', {
        labels: dailyLabels,
        datasets: [{
            label: 'Ocorrências por Dia',
            data: dailyValues,
            borderColor: '#EF4444',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            fill: true,
            tension: 0.3,
            borderWidth: 2,
            pointRadius: 3
        }]
    }));
}

// Renderiza a tabela da visão de Avarias
function renderAvariaTable() {
    if (avariaSearchQuery) {
        avariaFilteredData = avariaData.filter(d => 
            d.id_de_viagem.toLowerCase().includes(avariaSearchQuery) ||
            d.nome.toLowerCase().includes(avariaSearchQuery) ||
            d.produto.toLowerCase().includes(avariaSearchQuery) ||
            d.id_produto.toString().includes(avariaSearchQuery)
        );
    } else {
        avariaFilteredData = [...avariaData];
    }
    
    const total = avariaFilteredData.length;
    const totalPages = Math.max(1, Math.ceil(total / rowsPerPage));
    
    if (avariaCurrentPage > totalPages) avariaCurrentPage = totalPages;
    
    const startIndex = (avariaCurrentPage - 1) * rowsPerPage;
    const endIndex = Math.min(startIndex + rowsPerPage, total);
    const paginatedData = avariaFilteredData.slice(startIndex, endIndex);
    
    elTableAvariaBody.innerHTML = "";
    
    if (paginatedData.length === 0) {
        elTableAvariaBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--text-muted);">Nenhuma ocorrência encontrada.</td></tr>`;
        elTableAvariaInfo.textContent = "Mostrando 0 de 0 registros";
        elBtnAvariaPrev.disabled = true;
        elBtnAvariaNext.disabled = true;
        elPageAvariaNum.textContent = "1";
        return;
    }
    
    elTableAvariaBody.innerHTML = paginatedData.map(row => {
        let badgeClass = "badge-concluido";
        if (row.status.includes("Barrado")) badgeClass = "badge-critico";
        if (row.status.includes("Descarte")) badgeClass = "badge-critico";
        if (row.status.includes("Incompleta")) badgeClass = "badge-pendente";
        
        return `
            <tr>
                <td>${row.data}</td>
                <td><b>${row.id_de_viagem}</b></td>
                <td>${row.base_de_origem}</td>
                <td>${row.produto}</td>
                <td><span class="badge ${badgeClass}">${row.status}</span></td>
                <td>${row.id_produto}</td>
                <td>${row.nome}</td>
            </tr>
        `;
    }).join("");
    
    elTableAvariaInfo.textContent = `Mostrando ${startIndex + 1}-${endIndex} de ${total} registros`;
    elPageAvariaNum.textContent = avariaCurrentPage;
    elBtnAvariaPrev.disabled = avariaCurrentPage === 1;
    elBtnAvariaNext.disabled = avariaCurrentPage === totalPages;
}

// Direciona download do relatório PDF filtrado para a visão de Avarias
function generateAvariaPdfReport() {
    const params = new URLSearchParams({
        start_date: elAvariaStartDate.value,
        end_date: elAvariaEndDate.value,
        base: elAvariaBase.value,
        colaborador: elAvariaColaborador.value,
        produto: elAvariaProduto.value,
        status: elAvariaStatus.value
    });
    
    window.location.href = `${API_BASE}/api/avaria/generate_pdf?${params.toString()}&_=${Date.now()}`;
}

// --- NOVAS FUNÇÕES PARA VISÃO CONTROLE BAURU ---

async function loadControleData() {
    try {
        const response = await fetch(`${API_BASE}/api/controle/data?_=${Date.now()}`);
        const data = await response.json();
        
        if (data.error) {
            console.error(data.error);
            return;
        }
        
        controleDataCached = data;
        
        // 1. Preenche KPIs Principais
        const kpis = data.kpis;
        document.getElementById("val-ctrl-presentes").textContent = (kpis["Colaboradores Presentes"] !== undefined && kpis["Colaboradores Presentes"] !== null) ? kpis["Colaboradores Presentes"] : "-";
        document.getElementById("val-ctrl-pph").textContent = (kpis["PPH"] !== undefined && kpis["PPH"] !== null) ? parseFloat(kpis["PPH"]).toFixed(2) : "-";
        document.getElementById("val-ctrl-recebido").textContent = (kpis["Volume Recebido"] !== undefined && kpis["Volume Recebido"] !== null) ? kpis["Volume Recebido"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-expedido").textContent = (kpis["Volume Expedido"] !== undefined && kpis["Volume Expedido"] !== null) ? kpis["Volume Expedido"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-backlog").textContent = (kpis["Backlog Final"] !== undefined && kpis["Backlog Final"] !== null) ? kpis["Backlog Final"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-erros-triagem").textContent = (kpis["Erros de Triagem"] !== undefined && kpis["Erros de Triagem"] !== null) ? kpis["Erros de Triagem"].toLocaleString("pt-BR") : "-";
        
        // 2. Preenche Detalhes de RH
        document.getElementById("val-ctrl-hc-total").textContent = kpis["HC Total Disponível"] || "-";
        document.getElementById("val-ctrl-presentes-rh").textContent = kpis["Colaboradores Presentes"] || "-";
        document.getElementById("val-ctrl-hc-presente").textContent = kpis["HC Presente"] || "-";
        document.getElementById("val-ctrl-diaristas").textContent = kpis["Diaristas"] || "-";
        document.getElementById("val-ctrl-folgas").textContent = kpis["Folgas"] !== undefined ? kpis["Folgas"] : "-";
        document.getElementById("val-ctrl-faltas").textContent = kpis["Faltas"] || "-";
        document.getElementById("val-ctrl-atestados").textContent = kpis["Atestados"] || "-";
        document.getElementById("val-ctrl-produtividade-phh").textContent = kpis["PPH"] ? parseFloat(kpis["PPH"]).toFixed(2) : "-";
        
        if (kpis["% Presença"]) {
            let pres = parseFloat(kpis["% Presença"]);
            if (pres < 2.0 && pres > 0) {
                document.getElementById("val-ctrl-presenca-pct").textContent = (pres * 100).toFixed(1) + "%";
            } else {
                document.getElementById("val-ctrl-presenca-pct").textContent = pres.toFixed(1) + "%";
            }
        } else {
            document.getElementById("val-ctrl-presenca-pct").textContent = "-";
        }
        
        // 3. Preenche Detalhes de Volumes
        document.getElementById("val-ctrl-backlog-anterior").textContent = kpis["Backlog Inicial"] ? kpis["Backlog Inicial"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-vol-planejado").textContent = kpis["Volume Planejado"] ? kpis["Volume Planejado"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-coletas").textContent = kpis["Coletas Realizadas"] ? kpis["Coletas Realizadas"].toLocaleString("pt-BR") : "-";
        
        if (kpis["% Expedição"]) {
            let exp = parseFloat(kpis["% Expedição"]);
            if (exp <= 1.0 && exp > 0) {
                document.getElementById("val-ctrl-exp-pct").textContent = (exp * 100).toFixed(1) + "%";
            } else {
                document.getElementById("val-ctrl-exp-pct").textContent = exp.toFixed(1) + "%";
            }
        } else {
            document.getElementById("val-ctrl-exp-pct").textContent = "-";
        }
        
        document.getElementById("val-ctrl-exp-bre").textContent = kpis["BRE (SOC)"] ? kpis["BRE (SOC)"].toLocaleString("pt-BR") : "-";
        document.getElementById("val-ctrl-exp-rao").textContent = kpis["RAO (SOC)"] ? kpis["RAO (SOC)"].toLocaleString("pt-BR") : "-";
        
        // 4. Preenche Tabela e Gráfico de Gestão (Backlog e Sem Mov)
        const gest = data.gestao || {};
        document.getElementById("gestao-date-badge").textContent = gest.date ? gest.date : "-";
        
        const elGestBody = document.getElementById("table-controle-gestao-body");
        elGestBody.innerHTML = "";
        
        if (gest.backlog_inicial) {
            // Helper para inserir uma linha na tabela de gestão
            function addGestRow(label, cells, isPct = false) {
                const tr = document.createElement("tr");
                
                const tdLabel = document.createElement("td");
                tdLabel.style.fontWeight = "600";
                tdLabel.style.padding = "6px";
                tdLabel.textContent = label;
                tr.appendChild(tdLabel);
                
                cells.forEach(c => {
                    const td = document.createElement("td");
                    td.style.textAlign = "center";
                    td.style.padding = "6px";
                    if (isPct && c !== "-") {
                        td.style.fontWeight = "600";
                        td.textContent = c;
                    } else if (typeof c === "number") {
                        td.textContent = c.toLocaleString("pt-BR");
                    } else {
                        td.textContent = c;
                    }
                    tr.appendChild(td);
                });
                
                elGestBody.appendChild(tr);
            }
            
            addGestRow("Backlog Inicial", [gest.backlog_inicial["1_dia"], "-", "-", "-", "-", gest.backlog_inicial["total"]]);
            addGestRow("Backlog Final", [gest.backlog_final["1_dia"], "-", "-", "-", "-", gest.backlog_final["total"]]);
            addGestRow("Variação Backlog", [gest.variacao_backlog["1_dia"], "-", "-", "-", "-", gest.variacao_backlog["total"]], true);
            addGestRow("Sem Mov Inicial", [gest.sem_mov_inicial["1_dia"], gest.sem_mov_inicial["2_4_dias"], gest.sem_mov_inicial["5_dias"], gest.sem_mov_inicial["6_9_dias"], gest.sem_mov_inicial["10_dias_mais"], gest.sem_mov_inicial["total"]]);
            addGestRow("Sem Mov Final", [gest.sem_mov_final["1_dia"], gest.sem_mov_final["2_4_dias"], gest.sem_mov_final["5_dias"], gest.sem_mov_final["6_9_dias"], gest.sem_mov_final["10_dias_mais"], gest.sem_mov_final["total"]]);
            addGestRow("Variação Sem Mov", [gest.variacao_sem_mov["1_dia"], gest.variacao_sem_mov["2_4_dias"], gest.variacao_sem_mov["5_dias"], gest.variacao_sem_mov["6_9_dias"], gest.variacao_sem_mov["10_dias_mais"], gest.variacao_sem_mov["total"]], true);
            
            // Renderiza o gráfico de Gestão (Sem Movimentação Inicial vs Final)
            const labelsGest = ['1 Dia', '2 a 4 dias', '5 dias', '6 a 9 dias', '10 Dias +'];
            const dataSemMovIni = [
                gest.sem_mov_inicial["1_dia"],
                gest.sem_mov_inicial["2_4_dias"],
                gest.sem_mov_inicial["5_dias"],
                gest.sem_mov_inicial["6_9_dias"],
                gest.sem_mov_inicial["10_dias_mais"]
            ];
            const dataSemMovFim = [
                gest.sem_mov_final["1_dia"],
                gest.sem_mov_final["2_4_dias"],
                gest.sem_mov_final["5_dias"],
                gest.sem_mov_final["6_9_dias"],
                gest.sem_mov_final["10_dias_mais"]
            ];
            
            if (chartCtrlGestao) chartCtrlGestao.destroy();
            
            const ctxGest = document.getElementById("chart-controle-gestao").getContext("2d");
            chartCtrlGestao = new Chart(ctxGest, getChartConfig('bar', {
                labels: labelsGest,
                datasets: [
                    {
                        label: 'Sem Mov Inicial',
                        data: dataSemMovIni,
                        backgroundColor: '#EF4444', // Vermelho para estado inicial
                        borderRadius: 4
                    },
                    {
                        label: 'Sem Mov Final',
                        data: dataSemMovFim,
                        backgroundColor: '#10B981', // Verde para estado final (progresso)
                        borderRadius: 4
                    }
                ]
            }, {
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#9CA3AF', font: { family: 'Outfit', size: 10 } }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#9CA3AF', font: { family: 'Outfit', size: 10 } }
                    },
                    y: {
                        ticks: { color: '#9CA3AF', font: { family: 'Outfit', size: 10 } },
                        grid: { color: 'rgba(75, 85, 99, 0.2)' }
                    }
                }
            }));
        } else {
            elGestBody.innerHTML = `<tr><td colspan="7" style="text-align: center;">Nenhum dado de gestão disponível.</td></tr>`;
        }
        
        // 5. Preenche Tabela de Transporte
        const elTranspBody = document.getElementById("table-controle-transp-body");
        if (data.transporte && data.transporte.length > 0) {
            elTranspBody.innerHTML = data.transporte.map(row => `
                <tr>
                    <td><strong>${row["VEÍCULO / SC"] || row["VECULO / SC"] || "-"}</strong></td>
                    <td>${row["VOL. PLANEJADO"] ? parseInt(row["VOL. PLANEJADO"]).toLocaleString("pt-BR") : "0"}</td>
                    <td>${row["VOL. RECEBIDO"] ? parseInt(row["VOL. RECEBIDO"]).toLocaleString("pt-BR") : "0"}</td>
                    <td>${row["PREVISÃO"] || row["PREVISO"] || "-"}</td>
                    <td>${row["CHEGADA"] || "-"}</td>
                    <td>${row["DESLACRE"] || "-"}</td>
                    <td>${row["FIN. BIPAGEM"] || "-"}</td>
                    <td><span class="badge badge-concluido">${row["STATUS"] || "FINALIZADO"}</span></td>
                    <td><code>${row["ID's"] || "-"}</code></td>
                </tr>
            `).join("");
        } else {
            elTranspBody.innerHTML = `<tr><td colspan="9" style="text-align: center;">Nenhum recebimento registrado.</td></tr>`;
        }

        // 5.5. Preenche Tabela de Taxa de Expedição no Prazo (HUB -> PDD)
        const taxaPrazo = data.taxa_expedicao_prazo || {};
        const taxaItems = taxaPrazo.items || [];
        const taxaTotais = taxaPrazo.totais || {};
        
        const elTaxaBody = document.getElementById("table-taxa-expedicao-prazo-body");
        const elTaxaFoot = document.getElementById("table-taxa-expedicao-prazo-footer");
        const badgeTaxaGeral = document.getElementById("badge-taxa-exp-geral");
        const badgeTaxaTotal = document.getElementById("badge-taxa-exp-total");
        
        if (badgeTaxaGeral) {
            badgeTaxaGeral.textContent = `Taxa Geral: ${taxaTotais.taxa_prazo_str || "-"}`;
            const pctG = taxaTotais.taxa_prazo || 0;
            if (pctG >= 0.90) {
                badgeTaxaGeral.className = "badge badge-concluido";
            } else if (pctG >= 0.70) {
                badgeTaxaGeral.className = "badge badge-em-andamento";
            } else {
                badgeTaxaGeral.className = "badge badge-critico";
            }
        }
        if (badgeTaxaTotal) {
            badgeTaxaTotal.textContent = `Total: ${(taxaTotais.qtd_expedir || 0).toLocaleString("pt-BR")} pacotes`;
        }
        
        if (elTaxaBody) {
            if (taxaItems.length > 0) {
                elTaxaBody.innerHTML = taxaItems.map(row => {
                    const pctVal = row.taxa_prazo || 0;
                    let badgeClass = "badge-concluido";
                    let badgeText = "OK";
                    if (pctVal < 0.70) {
                        badgeClass = "badge-critico";
                        badgeText = "CRÍTICO";
                    } else if (pctVal < 0.90) {
                        badgeClass = "badge-em-andamento";
                        badgeText = "ATENÇÃO";
                    }
                    
                    const rotaLabel = row.ref_data ? `${row.rota} <span style="font-size: 11px; color: #9CA3AF; font-weight: normal;">(Ref: ${row.ref_data})</span>` : row.rota;
                    
                    return `
                        <tr>
                            <td><strong>${rotaLabel}</strong></td>
                            <td style="text-align: right;">${(row.qtd_expedir || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align: right; color: #10B981; font-weight: 600;">${(row.no_prazo || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align: right; color: ${row.fora_prazo > 0 ? '#EF4444' : '#9CA3AF'}; font-weight: ${row.fora_prazo > 0 ? '600' : 'normal'};">${(row.fora_prazo || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align: right;">${(row.anormalidade || 0).toLocaleString("pt-BR")}</td>
                            <td style="text-align: center; font-weight: 700; color: ${pctVal >= 0.90 ? '#10B981' : (pctVal >= 0.70 ? '#F59E0B' : '#EF4444')};">${row.taxa_prazo_str || "-"}</td>
                            <td style="text-align: center;"><span class="badge ${badgeClass}">${badgeText}</span></td>
                        </tr>
                    `;
                }).join("");
            } else {
                elTaxaBody.innerHTML = `<tr><td colspan="7" style="text-align: center;">Nenhum dado de taxa de expedição no prazo informado.</td></tr>`;
            }
        }
        
        if (elTaxaFoot) {
            if (taxaItems.length > 0 && taxaTotais.qtd_expedir > 0) {
                const pctGeral = taxaTotais.taxa_prazo || 0;
                let geralBadgeClass = pctGeral >= 0.90 ? "badge-concluido" : (pctGeral >= 0.70 ? "badge-em-andamento" : "badge-critico");
                let geralBadgeText = pctGeral >= 0.90 ? "OK" : (pctGeral >= 0.70 ? "ATENÇÃO" : "CRÍTICO");
                
                elTaxaFoot.innerHTML = `
                    <tr>
                        <td><strong>TOTAL CONSOLIDADO</strong></td>
                        <td style="text-align: right;">${(taxaTotais.qtd_expedir || 0).toLocaleString("pt-BR")}</td>
                        <td style="text-align: right; color: #10B981;">${(taxaTotais.no_prazo || 0).toLocaleString("pt-BR")}</td>
                        <td style="text-align: right; color: ${taxaTotais.fora_prazo > 0 ? '#EF4444' : '#9CA3AF'};">${(taxaTotais.fora_prazo || 0).toLocaleString("pt-BR")}</td>
                        <td style="text-align: right;">${(taxaTotais.anormalidade || 0).toLocaleString("pt-BR")}</td>
                        <td style="text-align: center; color: ${pctGeral >= 0.90 ? '#10B981' : (pctGeral >= 0.70 ? '#F59E0B' : '#EF4444')};">${taxaTotais.taxa_prazo_str || "-"}</td>
                        <td style="text-align: center;"><span class="badge ${geralBadgeClass}">${geralBadgeText}</span></td>
                    </tr>
                `;
            } else {
                elTaxaFoot.innerHTML = "";
            }
        }
        
        // 6. Preenche Tabelas de Expedição por Rota (Duas tabelas lado a lado)
        if (data.expedicao_detalhe && data.expedicao_detalhe.length > 0) {
            const sortedExp = [...data.expedicao_detalhe].sort((a, b) => {
                const volA = String(a.vol).toUpperCase().trim();
                const volB = String(b.vol).toUpperCase().trim();
                const isA_Cancelled = (volA === "CANCELADO" || volA.startsWith("CANCEL"));
                const isB_Cancelled = (volB === "CANCELADO" || volB.startsWith("CANCEL"));
                
                if (isA_Cancelled && !isB_Cancelled) return 1;
                if (!isA_Cancelled && isB_Cancelled) return -1;
                
                return String(a.route).localeCompare(String(b.route), 'pt-BR');
            });
            
            // Dividir as rotas entre as duas tabelas
            const half = Math.ceil(sortedExp.length / 2);
            const firstHalf = sortedExp.slice(0, half);
            const secondHalf = sortedExp.slice(half);
            
            const populateTable = (elementId, dataList) => {
                const elBody = document.getElementById(elementId);
                if (!elBody) return;
                if (dataList.length > 0) {
                    elBody.innerHTML = dataList.map(row => {
                        let volStr = row.vol;
                        if (typeof row.vol === 'number') {
                            volStr = row.vol.toLocaleString("pt-BR");
                        } else if (!isNaN(parseFloat(row.vol))) {
                            volStr = parseFloat(row.vol).toLocaleString("pt-BR");
                        }
                        
                        const badgeClass = row.status === "OK" ? "badge-concluido" : "badge-critico";
                        
                        return `
                            <tr>
                                <td><strong>${row.route}</strong></td>
                                <td style="text-align: right;">${volStr}</td>
                                <td style="text-align: right;">${row.departure}</td>
                                <td style="text-align: right;">${row.cutoff}</td>
                                <td style="text-align: center;"><span class="badge ${badgeClass}">${row.status}</span></td>
                            </tr>
                        `;
                    }).join("");
                } else {
                    elBody.innerHTML = `<tr><td colspan="5" style="text-align: center;">Nenhuma expedição registrada.</td></tr>`;
                }
            };
            
            populateTable("table-controle-expedicao-body-1", firstHalf);
            populateTable("table-controle-expedicao-body-2", secondHalf);
        }

        // 6.5. Gera o Resumo de Fechamento de Turno
        const txtResumo = document.getElementById("txt-resumo-fechamento");
        if (txtResumo) {
            let totalRoutes = 0;
            let routesOk = 0;
            let routesDelayed = [];
            
            if (data.expedicao_detalhe && data.expedicao_detalhe.length > 0) {
                totalRoutes = data.expedicao_detalhe.length;
                data.expedicao_detalhe.forEach(r => {
                    if (r.status === "OK") {
                        routesOk++;
                    } else {
                        routesDelayed.push(r.route);
                    }
                });
            }
            
            const dateStr = (data.gestao && data.gestao.date) ? data.gestao.date : "-";
            const blInicial = (data.gestao && data.gestao.backlog_inicial) ? data.gestao.backlog_inicial.total : 0;
            const blFinal = (data.gestao && data.gestao.backlog_final) ? data.gestao.backlog_final.total : 0;
            const blVar = (data.gestao && data.gestao.variacao_backlog) ? data.gestao.variacao_backlog.total : "0,00%";
            
            const smInicial = (data.gestao && data.gestao.sem_mov_inicial) ? data.gestao.sem_mov_inicial.total : 0;
            const smFinal = (data.gestao && data.gestao.sem_mov_final) ? data.gestao.sem_mov_final.total : 0;
            const smVar = (data.gestao && data.gestao.variacao_sem_mov) ? data.gestao.variacao_sem_mov.total : "0,00%";

            // Parse rich KPI metrics
            const kpis = data.kpis || {};
            const volPlanejado = kpis["Volume Planejado"] ? kpis["Volume Planejado"].toLocaleString("pt-BR") : "-";
            const volRecebido = kpis["Volume Recebido"] ? kpis["Volume Recebido"].toLocaleString("pt-BR") : "-";
            const volExpedido = kpis["Volume Expedido"] ? kpis["Volume Expedido"].toLocaleString("pt-BR") : "-";
            
            let pctExpedicao = "-";
            if (kpis["% Expedição"]) {
                pctExpedicao = (kpis["% Expedição"] * 100).toFixed(2).replace(".", ",") + "%";
            }
            
            const presentes = kpis["Colaboradores Presentes"] || "-";
            const diaristas = kpis["Diaristas"] || "-";
            const faltas = kpis["Faltas"] || "-";
            const atestados = kpis["Atestados"] || "-";
            
            let pphVal = "-";
            if (kpis["PPH"]) {
                pphVal = parseFloat(kpis["PPH"]).toFixed(2).replace(".", ",");
            }
            
            const triagem = kpis["Erros de Triagem"] || "-";
            const avarias = kpis["Avarias"] || "-";
            
            let motivosStr = "";
            if (data.fechamento && data.fechamento.motivos && data.fechamento.motivos.length > 0) {
                motivosStr = data.fechamento.motivos.map(m => `• ${m}`).join("\n");
            } else {
                motivosStr = "Nenhum motivo registrado.";
            }

            // Formatar data como DD/MM/YYYY
            let formattedDate = "__/__/__";
            if (dateStr && dateStr !== "-") {
                const parts = dateStr.split(" ")[0].split("-");
                if (parts.length === 3) {
                    formattedDate = `${parts[2]}/${parts[1]}/${parts[0]}`;
                } else if (dateStr.includes("/")) {
                    formattedDate = dateStr.split(" ")[0];
                }
            }

            let slaVal = "-";
            if (kpis["SLA Expediço"]) {
                slaVal = (kpis["SLA Expediço"] * 100).toFixed(2).replace(".", ",") + "%";
            } else if (kpis["SLA Expedição"]) {
                slaVal = (kpis["SLA Expedição"] * 100).toFixed(2).replace(".", ",") + "%";
            }

            const hcRealizado = kpis["HC Presente"] || kpis["HC Realizado"] || presentes;

            let pendenciasStr = "";
            if (data.fechamento && data.fechamento.motivos && data.fechamento.motivos.length > 0) {
                pendenciasStr = data.fechamento.motivos.map(m => `- ${m}`).join("\n");
            } else {
                pendenciasStr = "-\n-";
            }

            const coletas = kpis["Coletas Realizadas"] || 0;
            
            let inicioOperacao = "-";
            if (data.transporte && data.transporte.length > 0) {
                const deslacres = data.transporte
                    .map(r => r["DESLACRE"])
                    .filter(v => v && v !== "-" && v !== "HH:MM");
                if (deslacres.length > 0) {
                    deslacres.sort();
                    inicioOperacao = deslacres[0].substring(0, 5);
                }
            }

            let fimOperacao = "-";
            if (data.expedicao_detalhe && data.expedicao_detalhe.length > 0) {
                const departures = data.expedicao_detalhe
                    .map(r => r.departure)
                    .filter(v => v && v !== "-" && v !== "HH:MM");
                if (departures.length > 0) {
                    departures.sort();
                    fimOperacao = departures[departures.length - 1].substring(0, 5);
                }
            }

            // Taxa de Expedição no Prazo (HUB -> PDD)
            const taxaPrazoInfo = data.taxa_expedicao_prazo || {};
            const taxaItemsList = taxaPrazoInfo.items || [];
            const taxaTotaisObj = taxaPrazoInfo.totais || {};
            
            let taxaGeralStr = taxaTotaisObj.taxa_prazo_str || "-";
            let slaPercent = taxaGeralStr !== "-" ? taxaGeralStr : "-";
            if (slaPercent === "-") {
                let rawSla = kpis["SLA Expedição"] || kpis["SLA Expediço"] || kpis["SLA"];
                if (rawSla !== undefined && rawSla !== null) {
                    let val = parseFloat(rawSla);
                    if (!isNaN(val)) {
                        if (val <= 1.0) {
                            val = val * 100;
                        }
                        slaPercent = val % 1 === 0 ? val.toFixed(0) + "%" : val.toFixed(2).replace(".", ",") + "%";
                    }
                }
            }

            let summaryText = `🎯 RESUMO DE FECHAMENTO OPERACIONAL\n\n`;
            summaryText += `📅 Data: ${formattedDate}\n\n`;
            
            summaryText += `📦Backlog inicial:${blInicial.toLocaleString("pt-BR")}\n`;
            summaryText += `🚚Volume recebido: ${volRecebido}\n`;
            summaryText += `🚚Coleta: ${coletas.toLocaleString("pt-BR")}\n\n`;
            
            summaryText += `🕒Inicio da operação: ${inicioOperacao}\n`;
            summaryText += `🏁Fim da Operação: ${fimOperacao}\n`;
            summaryText += `⏰ Horário de corte: ${routesDelayed.length === 0 ? '✅' : '❌'}\n\n`;
            
            summaryText += `🚚 Rotas expedidas: ${totalRoutes}\n`;
            summaryText += `📦 Pacotes expedidos: ${volExpedido}\n`;
            summaryText += `📦 Backlog final: ${blFinal.toLocaleString("pt-BR")}\n\n`;

            if (taxaTotaisObj && taxaTotaisObj.qtd_expedir > 0) {
                summaryText += `⏱️ Taxa de Exp. no Prazo (HUB->PDD): ${taxaGeralStr}\n`;
                if (taxaItemsList && taxaItemsList.length > 0) {
                    taxaItemsList.forEach(item => {
                        const rName = item.rota || "Rota";
                        summaryText += `   • ${rName}: ${item.taxa_prazo_str} (Prazo: ${item.no_prazo.toLocaleString("pt-BR")} | Fora: ${item.fora_prazo.toLocaleString("pt-BR")})\n`;
                    });
                }
                summaryText += `\n`;
            }
            
            summaryText += `📊 SLA: ${slaPercent}\n`;
            summaryText += `❌ Erros de triagem: ${triagem}\n\n`;
            
            summaryText += `Ponto de impacto:`;
            if (routesDelayed.length > 0) {
                summaryText += ` Atraso nas rotas: ${routesDelayed.join(", ")}`;
            }

            txtResumo.value = summaryText;

            const btnCopiar = document.getElementById("btn-copiar-resumo");
            if (btnCopiar && !btnCopiar.dataset.listenerAdded) {
                btnCopiar.dataset.listenerAdded = "true";
                btnCopiar.addEventListener("click", () => {
                    txtResumo.select();
                    txtResumo.setSelectionRange(0, 99999);
                    navigator.clipboard.writeText(txtResumo.value).then(() => {
                        const originalHTML = btnCopiar.innerHTML;
                        btnCopiar.innerHTML = `<i class="fa-solid fa-check"></i> Copiado!`;
                        btnCopiar.style.background = "#10B981";
                        setTimeout(() => {
                            btnCopiar.innerHTML = originalHTML;
                            btnCopiar.style.background = "";
                        }, 2000);
                    }).catch(err => {
                        console.error("Erro ao copiar texto:", err);
                    });
                });
            }
        }
        
        // 7. Renderiza Gráficos
        renderControleCharts(data.analitico);
        
    } catch (error) {
        console.error("Error loading Controle Bauru data:", error);
    }
}

function renderControleCharts(analitico) {
    if (!analitico || !analitico.dates) return;
    
    // 1. Gráfico de Avarias (Quantidade e Valor)
    const elAvarias = document.getElementById("chart-ctrl-avarias");
    if (elAvarias) {
        const ctxAvarias = elAvarias.getContext ? elAvarias.getContext("2d") : elAvarias;
        if (chartCtrlAvarias) {
            chartCtrlAvarias.destroy();
        }
        
        chartCtrlAvarias = new Chart(ctxAvarias, {
            type: 'bar',
            data: {
                labels: analitico.dates,
                datasets: [
                    {
                        label: 'Quantidade de Avarias',
                        data: analitico.avaria_qnt || [],
                        backgroundColor: 'rgba(59, 130, 246, 0.7)',
                        borderColor: 'rgba(59, 130, 246, 1)',
                        borderWidth: 1,
                        yAxisID: 'y'
                    },
                    {
                        label: 'Valor Acumulado (R$)',
                        data: analitico.avaria_val || [],
                        type: 'line',
                        borderColor: 'rgba(239, 68, 68, 1)',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        borderWidth: 2,
                        tension: 0.3,
                        yAxisID: 'y1'
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        labels: { color: '#E5E7EB', font: { family: 'Outfit' } }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9CA3AF', font: { family: 'Outfit' } }
                    },
                    y: {
                        type: 'linear',
                        display: true,
                        position: 'left',
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9CA3AF', font: { family: 'Outfit' } },
                        title: { display: true, text: 'Quantidade', color: '#9CA3AF' }
                    },
                    y1: {
                        type: 'linear',
                        display: true,
                        position: 'right',
                        grid: { drawOnChartArea: false },
                        ticks: {
                            color: '#9CA3AF',
                            font: { family: 'Outfit' },
                            callback: function(value) {
                                return 'R$ ' + value.toLocaleString('pt-BR');
                            }
                        },
                        title: { display: true, text: 'Valor (R$)', color: '#9CA3AF' }
                    }
                }
            }
        });
    }
    
    // 2. Gráfico de Sem Movimentação (Inicial vs. Final)
    const elSemMov = document.getElementById("chart-ctrl-semmov");
    if (elSemMov) {
        const ctxSemMov = elSemMov.getContext ? elSemMov.getContext("2d") : elSemMov;
        if (chartCtrlSemMov) {
            chartCtrlSemMov.destroy();
        }
    
    chartCtrlSemMov = new Chart(ctxSemMov, {
        type: 'line',
        data: {
            labels: analitico.dates,
            datasets: [
                {
                    label: 'Sem Movimentação Inicial',
                    data: analitico.sem_mov_ini,
                    borderColor: 'rgba(245, 158, 11, 1)',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    borderWidth: 2,
                    tension: 0.3
                },
                {
                    label: 'Sem Movimentação Final',
                    data: analitico.sem_mov_fim,
                    borderColor: 'rgba(16, 185, 129, 1)',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    borderWidth: 2,
                    tension: 0.3
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#E5E7EB', font: { family: 'Outfit' } }
                }
            },
            scales: {
                x: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#9CA3AF', font: { family: 'Outfit' } }
                },
                y: {
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#9CA3AF', font: { family: 'Outfit' } },
                    title: { display: true, text: 'Quantidade de Pacotes', color: '#9CA3AF' }
                }
            }
        }
    });
    }
}

function generateControlePdfReport() {
    window.location.href = `${API_BASE}/api/controle/generate_pdf?_=${Date.now()}`;
}

async function loadProducaoData() {
    try {
        const response = await fetch(`${API_BASE}/api/producao/data?_=${Date.now()}`);
        const data = await response.json();
        
        if (!data) return;
        
        const totais = data?.totais || { coleta: 0, expedicao: 0, lote: 0, pico_hora: "-" };
        
        let showColeta = totais.coleta > 0;
        let showExpedicao = totais.expedicao > 0;
        let showLote = totais.lote > 0;
        
        // Se tudo for zero, mostra tudo por padrão
        if (!showColeta && !showExpedicao && !showLote) {
            showColeta = true;
            showExpedicao = true;
            showLote = true;
        }
        
        // 1. Popula e exibe/oculta os KPIs de Produção
        const elTotColeta = document.getElementById("val-prod-tot-coleta");
        if (elTotColeta) elTotColeta.textContent = (totais.coleta || 0).toLocaleString("pt-BR");
        const elTotExp = document.getElementById("val-prod-tot-expedicao");
        if (elTotExp) elTotExp.textContent = (totais.expedicao || 0).toLocaleString("pt-BR");
        const elTotLote = document.getElementById("val-prod-tot-lote");
        if (elTotLote) elTotLote.textContent = (totais.lote || 0).toLocaleString("pt-BR");
        const elPico = document.getElementById("val-prod-pico-hora");
        if (elPico) elPico.textContent = totais.pico_hora || "-";
        
        const cardColeta = document.getElementById("kpi-prod-coleta");
        const cardExpedicao = document.getElementById("kpi-prod-expedicao");
        const cardLote = document.getElementById("kpi-prod-lote");
        if (cardColeta) cardColeta.style.display = showColeta ? "flex" : "none";
        if (cardExpedicao) cardExpedicao.style.display = showExpedicao ? "flex" : "none";
        if (cardLote) cardLote.style.display = showLote ? "flex" : "none";
        
        // 2. Popula os títulos e rodapé da tabela dinâmica
        const tableProd = document.getElementById("table-prod-hourly");
        if (tableProd) {
            const thead = tableProd.querySelector("thead");
            const tfoot = tableProd.querySelector("tfoot");
            
            let headerHtml = `<tr><th style="text-align: center; width: 100px;">Hora</th>`;
            if (showColeta) headerHtml += `<th style="text-align: right; color: #60A5FA;">Coleta de Chegada</th>`;
            if (showExpedicao) headerHtml += `<th style="text-align: right; color: #34D399;">Expedição</th>`;
            if (showLote) headerHtml += `<th style="text-align: right; color: #F59E0B;">Criação de Lote</th>`;
            headerHtml += `</tr>`;
            thead.innerHTML = headerHtml;
            
            let footerHtml = `<tr style="border-top: 2px solid rgba(255,255,255,0.15); font-weight: bold; background: rgba(255,255,255,0.03);">`;
            footerHtml += `<td style="text-align: center; color: #E5E7EB;">TOTAL</td>`;
            if (showColeta) footerHtml += `<td style="text-align: right; color: #60A5FA;" id="foot-prod-coleta">${totais.coleta !== undefined && totais.coleta !== null ? totais.coleta.toLocaleString("pt-BR") : "0"}</td>`;
            if (showExpedicao) footerHtml += `<td style="text-align: right; color: #34D399;" id="foot-prod-expedicao">${totais.expedicao !== undefined && totais.expedicao !== null ? totais.expedicao.toLocaleString("pt-BR") : "0"}</td>`;
            if (showLote) footerHtml += `<td style="text-align: right; color: #F59E0B;" id="foot-prod-lote">${totais.lote !== undefined && totais.lote !== null ? totais.lote.toLocaleString("pt-BR") : "0"}</td>`;
            footerHtml += `</tr>`;
            tfoot.innerHTML = footerHtml;
        }
        
        // 3. Popula a tabela de resumo por hora dinamicamente
        const elHourlyBody = document.getElementById("table-prod-hourly-body");
        if (elHourlyBody) {
            const activeColumns = 1 + (showColeta ? 1 : 0) + (showExpedicao ? 1 : 0) + (showLote ? 1 : 0);
            if (data.bipagens_hora && data.bipagens_hora.length > 0) {
                elHourlyBody.innerHTML = data.bipagens_hora.map(row => {
                    let rowHtml = `<td style="text-align: center;"><strong>${row.hora}</strong></td>`;
                    if (showColeta) rowHtml += `<td style="text-align: right; color: #60A5FA;">${row.coleta !== undefined && row.coleta !== null ? row.coleta.toLocaleString("pt-BR") : "0"}</td>`;
                    if (showExpedicao) rowHtml += `<td style="text-align: right; color: #34D399;">${row.expedicao !== undefined && row.expedicao !== null ? row.expedicao.toLocaleString("pt-BR") : "0"}</td>`;
                    if (showLote) rowHtml += `<td style="text-align: right; color: #F59E0B;">${row.lote !== undefined && row.lote !== null ? row.lote.toLocaleString("pt-BR") : "0"}</td>`;
                    return `<tr>${rowHtml}</tr>`;
                }).join("");
            } else {
                elHourlyBody.innerHTML = `<tr><td colspan="${activeColumns}" style="text-align: center;">Nenhum registro encontrado.</td></tr>`;
            }
        }
        
        // 4. Popula e exibe/oculta Ranking - Coleta de Chegada
        const cardRankColeta = document.getElementById("card-rank-coleta");
        if (cardRankColeta) cardRankColeta.style.display = showColeta ? "block" : "none";
        
        const elRankColetaBody = document.getElementById("table-rank-coleta-body");
        if (elRankColetaBody) {
            const list = data.rankings.coleta;
            if (list && list.length > 0) {
                elRankColetaBody.innerHTML = list.map(row => `
                    <tr>
                        <td style="text-align: center;"><strong>${row.posicao}</strong></td>
                        <td>${row.nome}</td>
                        <td style="text-align: right; font-weight: 500;">${row.count.toLocaleString("pt-BR")}</td>
                    </tr>
                `).join("");
            } else {
                elRankColetaBody.innerHTML = `<tr><td colspan="3" style="text-align: center;">Nenhum registro.</td></tr>`;
            }
        }
        
        // 5. Popula e exibe/oculta Ranking - Expedição
        const cardRankExp = document.getElementById("card-rank-exp");
        if (cardRankExp) cardRankExp.style.display = showExpedicao ? "block" : "none";
        
        const elRankExpBody = document.getElementById("table-rank-exp-body");
        if (elRankExpBody) {
            const list = data.rankings.expedicao;
            if (list && list.length > 0) {
                elRankExpBody.innerHTML = list.map(row => `
                    <tr>
                        <td style="text-align: center;"><strong>${row.posicao}</strong></td>
                        <td>${row.nome}</td>
                        <td style="text-align: right; font-weight: 500;">${row.count.toLocaleString("pt-BR")}</td>
                    </tr>
                `).join("");
            } else {
                elRankExpBody.innerHTML = `<tr><td colspan="3" style="text-align: center;">Nenhum registro.</td></tr>`;
            }
        }
        
        // 6. Popula e exibe/oculta Ranking - Criação de Lote
        const cardRankLote = document.getElementById("card-rank-lote");
        if (cardRankLote) cardRankLote.style.display = showLote ? "block" : "none";
        
        const elRankLoteBody = document.getElementById("table-rank-lote-body");
        if (elRankLoteBody) {
            const list = data.rankings.lote;
            if (list && list.length > 0) {
                elRankLoteBody.innerHTML = list.map(row => `
                    <tr>
                        <td style="text-align: center;"><strong>${row.posicao}</strong></td>
                        <td>${row.nome}</td>
                        <td style="text-align: right; font-weight: 500;">${row.count.toLocaleString("pt-BR")}</td>
                    </tr>
                `).join("");
            } else {
                elRankLoteBody.innerHTML = `<tr><td colspan="3" style="text-align: center;">Nenhum registro.</td></tr>`;
            }
        }
        
        // 7. Render/Update Comparison Charts
        const targetHours = [
            '18:00', '19:00', '20:00', '21:00', '22:00', '23:00',
            '00:00', '01:00', '02:00', '03:00', '04:00', '05:00',
            '06:00', '07:00', '08:00'
        ];
        
        // Exibe/oculta as seções de comparativos
        const cardCompColeta = document.getElementById("card-prod-comparativo-coleta");
        const cardCompExp = document.getElementById("card-prod-comparativo-expedicao");
        const cardCompLote = document.getElementById("card-prod-comparativo-lote");
        
        if (cardCompColeta) cardCompColeta.style.display = showColeta ? "block" : "none";
        if (cardCompExp) cardCompExp.style.display = showExpedicao ? "block" : "none";
        if (cardCompLote) cardCompLote.style.display = showLote ? "block" : "none";

        const dateRecente = data.data_ref || "-";
        const dateAnterior = (data.anterior && data.anterior.data_ref) ? data.anterior.data_ref : "-";
        const dateRetrasado = (data.retrasado && data.retrasado.data_ref) ? data.retrasado.data_ref : "-";
        const subtitleText = `Comparativo: ${dateRetrasado} (2 Dias Atrás) | ${dateAnterior} (Dia Anterior) | ${dateRecente} (Dia Recente)`;
        
        // Atualiza legendas de datas
        if (showColeta && document.getElementById("txt-prod-comp-datas-coleta")) {
            document.getElementById("txt-prod-comp-datas-coleta").textContent = subtitleText;
        }
        if (showExpedicao && document.getElementById("txt-prod-comp-datas-expedicao")) {
            document.getElementById("txt-prod-comp-datas-expedicao").textContent = subtitleText;
        }
        if (showLote && document.getElementById("txt-prod-comp-datas-lote")) {
            document.getElementById("txt-prod-comp-datas-lote").textContent = subtitleText;
        }

        // Função auxiliar para renderizar cada gráfico comparativo
        function renderCompChart(canvasId, key, recentColor, anteriorColor, retrasadoColor, currentInstanceVarName) {
            const ctx = document.getElementById(canvasId);
            if (!ctx) return null;
            
            const recentHourlyMap = {};
            if (data.bipagens_hora) {
                data.bipagens_hora.forEach(item => {
                    recentHourlyMap[item.hora] = item[key];
                });
            }
            
            const anteriorHourlyMap = {};
            if (data.anterior && data.anterior.bipagens_hora) {
                data.anterior.bipagens_hora.forEach(item => {
                    anteriorHourlyMap[item.hora] = item[key];
                });
            }
            
            const retrasadoHourlyMap = {};
            if (data.retrasado && data.retrasado.bipagens_hora) {
                data.retrasado.bipagens_hora.forEach(item => {
                    retrasadoHourlyMap[item.hora] = item[key];
                });
            }
            
            const recentSeries = targetHours.map(h => recentHourlyMap[h] || 0);
            const anteriorSeries = targetHours.map(h => anteriorHourlyMap[h] || 0);
            const retrasadoSeries = targetHours.map(h => retrasadoHourlyMap[h] || 0);
            
            // Destrói instância anterior
            if (currentInstanceVarName === 'coleta' && chartProdCompColeta) chartProdCompColeta.destroy();
            if (currentInstanceVarName === 'expedicao' && chartProdCompExp) chartProdCompExp.destroy();
            if (currentInstanceVarName === 'lote' && chartProdCompLote) chartProdCompLote.destroy();
            
            const ctx2d = ctx.getContext("2d");
            const gradientRecent = ctx2d.createLinearGradient(0, 0, 0, 300);
            // Extrai a cor em formato RGB para o gradiente
            let rgbBase = "99, 102, 241"; // Indigo padrão
            if (recentColor.startsWith('#')) {
                const hex = recentColor.replace('#', '');
                if (hex.length === 6) {
                    const r = parseInt(hex.substring(0, 2), 16);
                    const g = parseInt(hex.substring(2, 4), 16);
                    const b = parseInt(hex.substring(4, 6), 16);
                    rgbBase = `${r}, ${g}, ${b}`;
                }
            }
            
            gradientRecent.addColorStop(0, `rgba(${rgbBase}, 0.35)`);
            gradientRecent.addColorStop(1, `rgba(${rgbBase}, 0.0)`);
            
            const labelSuffix = key === 'coleta' ? 'Coleta' : (key === 'expedicao' ? 'Expedição' : 'Lote');
            
            const chartInstance = new Chart(ctx, {
                type: 'line',
                data: {
                    labels: targetHours,
                    datasets: [
                        {
                            label: `Dia Recente (${labelSuffix})`,
                            data: recentSeries,
                            borderColor: recentColor,
                            backgroundColor: gradientRecent,
                            borderWidth: 3,
                            fill: true,
                            tension: 0.35,
                            pointBackgroundColor: recentColor,
                            pointBorderColor: '#FFFFFF',
                            pointHoverRadius: 6
                        },
                        {
                            label: `Dia Anterior (${labelSuffix})`,
                            data: anteriorSeries,
                            borderColor: anteriorColor,
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            borderDash: [5, 5],
                            fill: false,
                            tension: 0.35,
                            pointBackgroundColor: anteriorColor,
                            pointBorderColor: '#FFFFFF',
                            pointHoverRadius: 4
                        },
                        {
                            label: `2 Dias Atrás (${labelSuffix})`,
                            data: retrasadoSeries,
                            borderColor: retrasadoColor,
                            backgroundColor: 'transparent',
                            borderWidth: 2,
                            borderDash: [2, 2],
                            fill: false,
                            tension: 0.35,
                            pointBackgroundColor: retrasadoColor,
                            pointBorderColor: '#FFFFFF',
                            pointHoverRadius: 4
                        }
                    ]
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    plugins: {
                        legend: {
                            position: 'top',
                            labels: {
                                color: '#E5E7EB',
                                font: { family: 'Outfit', size: 12 }
                            }
                        },
                        tooltip: {
                            backgroundColor: 'rgba(17, 24, 39, 0.95)',
                            titleFont: { family: 'Outfit', size: 13, weight: 'bold' },
                            bodyFont: { family: 'Outfit', size: 12 },
                            borderColor: 'rgba(255, 255, 255, 0.1)',
                            borderWidth: 1,
                            padding: 10,
                            displayColors: true
                        }
                    },
                    scales: {
                        x: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#9CA3AF', font: { family: 'Outfit' } }
                        },
                        y: {
                            grid: { color: 'rgba(255, 255, 255, 0.05)' },
                            ticks: { color: '#9CA3AF', font: { family: 'Outfit' } },
                            title: { display: true, text: `Bipagens de ${labelSuffix}`, color: '#9CA3AF', font: { family: 'Outfit' } }
                        }
                    }
                }
            });
            
            return chartInstance;
        }
        
        // Renderiza cada um dos gráficos se a operação estiver ativa
        if (showColeta) {
            chartProdCompColeta = renderCompChart("chart-prod-comp-coleta", "coleta", "#10B981", "#34D399", "#A7F3D0", "coleta");
        }
        if (showExpedicao) {
            chartProdCompExp = renderCompChart("chart-prod-comp-expedicao", "expedicao", "#3B82F6", "#60A5FA", "#93C5FD", "expedicao");
        }
        if (showLote) {
            chartProdCompLote = renderCompChart("chart-prod-comp-lote", "lote", "#F59E0B", "#FBBF24", "#FDE68A", "lote");
        }
        
    } catch (error) {
        console.error("Error loading Producao data:", error);
    }
}

// Funções para manipulação de Upload de arquivos de Produção (.txt)
function handleFileSelect(input, type) {
    const file = input.files[0];
    if (!file) return;
    uploadProducaoFile(file, type);
}

function uploadProducaoFile(file, type) {
    const statusMsg = document.getElementById("upload-status-msg");
    const dz = document.getElementById(`dz-${type}`);
    if (!statusMsg || !dz) return;
    
    // Apaga/zera apenas as informações do tipo de arquivo que está sendo enviado para manter os outros comparativos ativos
    if (type === 'coleta') {
        document.getElementById("val-prod-tot-coleta").textContent = "-";
        const elFoot = document.getElementById("foot-prod-coleta");
        if (elFoot) elFoot.textContent = "";
        const elRankColetaBody = document.getElementById("table-rank-coleta-body");
        if (elRankColetaBody) elRankColetaBody.innerHTML = `<tr><td colspan="3" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Atualizando...</td></tr>`;
    } else if (type === 'expedicao') {
        document.getElementById("val-prod-tot-expedicao").textContent = "-";
        const elFoot = document.getElementById("foot-prod-expedicao");
        if (elFoot) elFoot.textContent = "";
        const elRankExpBody = document.getElementById("table-rank-exp-body");
        if (elRankExpBody) elRankExpBody.innerHTML = `<tr><td colspan="3" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Atualizando...</td></tr>`;
    } else if (type === 'lote') {
        document.getElementById("val-prod-tot-lote").textContent = "-";
        const elFoot = document.getElementById("foot-prod-lote");
        if (elFoot) elFoot.textContent = "";
        const elRankLoteBody = document.getElementById("table-rank-lote-body");
        if (elRankLoteBody) elRankLoteBody.innerHTML = `<tr><td colspan="3" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Atualizando...</td></tr>`;
    }
    
    document.getElementById("val-prod-pico-hora").textContent = "-";
    
    const elHourlyBody = document.getElementById("table-prod-hourly-body");
    if (elHourlyBody) {
        elHourlyBody.innerHTML = `<tr><td colspan="4" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin" style="margin-right: 6px;"></i> Atualizando resumo de bipagens...</td></tr>`;
    }
    
    // Mostra status carregando
    statusMsg.style.display = "block";
    statusMsg.style.background = "rgba(59, 130, 246, 0.15)";
    statusMsg.style.color = "#60A5FA";
    statusMsg.innerHTML = `<i class="fa-solid fa-spinner fa-spin" style="margin-right: 6px;"></i> Enviando...`;
    
    const formData = new FormData();
    formData.append("file", file);
    formData.append("type", type);
    
    const progressContainer = document.getElementById("upload-progress-container");
    const progressBar = document.getElementById("upload-progress-bar");
    if (progressContainer && progressBar) {
        progressContainer.style.display = "block";
        progressBar.style.width = "0%";
        progressBar.style.background = "#3B82F6"; // Azul durante envio
    }
    
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/producao/upload", true);
    
    xhr.upload.addEventListener("progress", (e) => {
        if (e.lengthComputable) {
            const percentComplete = (e.loaded / e.total) * 100;
            if (progressBar) progressBar.style.width = `${percentComplete}%`;
        }
    });
    
    xhr.onload = () => {
        if (xhr.status === 200) {
            try {
                const data = JSON.parse(xhr.responseText);
                if (data.success) {
                    statusMsg.style.background = "rgba(16, 185, 129, 0.15)";
                    statusMsg.style.color = "#34D399";
                    statusMsg.innerHTML = `<i class="fa-solid fa-circle-check" style="margin-right: 6px;"></i> ${data.message}`;
                    
                    if (progressBar) {
                        progressBar.style.width = "100%";
                        progressBar.style.background = "#10B981"; // Verde ao concluir
                    }
                    
                    // Recarrega os dados de produção dinamicamente
                    loadProducaoData();
                    
                    // Limpa o input
                    const fileInput = document.getElementById(`input-${type}`);
                    if (fileInput) fileInput.value = "";
                    
                    // Oculta mensagem e barra após 4 segundos
                    setTimeout(() => {
                        statusMsg.style.display = "none";
                        if (progressContainer) progressContainer.style.display = "none";
                    }, 4000);
                } else {
                    statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
                    statusMsg.style.color = "#F87171";
                    statusMsg.innerHTML = `<i class="fa-solid fa-circle-xmark" style="margin-right: 6px;"></i> ${data.message}`;
                    if (progressBar) progressBar.style.background = "#EF4444"; // Vermelho em erro
                }
            } catch (err) {
                statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
                statusMsg.style.color = "#F87171";
                statusMsg.innerHTML = `<i class="fa-solid fa-circle-xmark" style="margin-right: 6px;"></i> Resposta inválida do servidor.`;
                if (progressBar) progressBar.style.background = "#EF4444";
            }
        } else {
            statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
            statusMsg.style.color = "#F87171";
            statusMsg.innerHTML = `<i class="fa-solid fa-circle-xmark" style="margin-right: 6px;"></i> Erro no upload (Status ${xhr.status}).`;
            if (progressBar) progressBar.style.background = "#EF4444";
        }
    };
    
    xhr.onerror = (err) => {
        statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
        statusMsg.style.color = "#F87171";
        statusMsg.innerHTML = `<i class="fa-solid fa-circle-xmark" style="margin-right: 6px;"></i> Erro na comunicação com o servidor.`;
        if (progressBar) progressBar.style.background = "#EF4444";
        console.error("Erro no upload:", err);
    };
    
    xhr.send(formData);
}

// Configura Drag and Drop para os Dropzones
document.addEventListener("DOMContentLoaded", () => {
    const types = ['coleta', 'expedicao', 'lote'];
    
    types.forEach(type => {
        const dz = document.getElementById(`dz-${type}`);
        if (!dz) return;
        
        // Evita comportamentos padrão
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            dz.addEventListener(eventName, e => {
                e.preventDefault();
                e.stopPropagation();
            }, false);
        });
        
        // Estilos ao arrastar por cima
        ['dragenter', 'dragover'].forEach(eventName => {
            dz.addEventListener(eventName, () => {
                dz.classList.add('dragover');
            }, false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            dz.addEventListener(eventName, () => {
                dz.classList.remove('dragover');
            }, false);
        });
        
        // Processa o arquivo solto
        dz.addEventListener('drop', e => {
            const dt = e.dataTransfer;
            const files = dt.files;
            if (files.length > 0) {
                const file = files[0];
                if (file.name.endsWith('.txt')) {
                    uploadProducaoFile(file, type);
                } else {
                    const statusMsg = document.getElementById("upload-status-msg");
                    if (statusMsg) {
                        statusMsg.style.display = "block";
                        statusMsg.style.background = "rgba(239, 68, 68, 0.15)";
                        statusMsg.style.color = "#F87171";
                        statusMsg.innerHTML = `<i class="fa-solid fa-triangle-exclamation" style="margin-right: 6px;"></i> Apenas arquivos .txt são permitidos.`;
                    }
                }
            }
        }, false);
    });
});

// --- COMPONENTES DA ABA VOLUME EXP DC BAU ---

// Carrega os dados brutos da API
async function loadVolumeExpData() {
    try {
        const elTableBody = document.getElementById("table-volume-exp-body");
        if (elTableBody) {
            elTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando dados...</td></tr>`;
        }
        
        const response = await fetch(`${API_BASE}/api/volume_exp_dc_bau/data?_=${Date.now()}`);
        if (!response.ok) throw new Error("Erro na requisição da API.");
        
        volumeExpData = await response.json();
        if (!Array.isArray(volumeExpData)) volumeExpData = volumeExpData?.records || [];
        
        populateVolumeExpFilters();
        renderVolumeExpDashboard();
    } catch (err) {
        console.error("Erro ao carregar dados de Volume Exp:", err);
        const elTableBody = document.getElementById("table-volume-exp-body");
        if (elTableBody) {
            elTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center; color: var(--danger);">Erro ao carregar dados do arquivo Controle exp.txt. Verifique se o arquivo está na pasta correta.</td></tr>`;
        }
    }
}

// Popula o filtro de datas
function populateVolumeExpFilters() {
    if (!elVolumeExpDateFilter) return;
    
    // Armazena valor selecionado atualmente
    const currentVal = elVolumeExpDateFilter.value;
    
    // Obtém todas as datas únicas
    const dates = [...new Set(volumeExpData.map(item => item.data))].filter(Boolean);
    
    // Limpa e repopula
    elVolumeExpDateFilter.innerHTML = '<option value="Todas">Todas as Datas</option>';
    dates.forEach(date => {
        const opt = document.createElement("option");
        opt.value = date;
        opt.textContent = date;
        elVolumeExpDateFilter.appendChild(opt);
    });
    
    // Restaura valor se existia e ainda está disponível
    if (dates.includes(currentVal)) {
        elVolumeExpDateFilter.value = currentVal;
    } else {
        elVolumeExpDateFilter.value = "Todas";
    }
}

// Renderiza os KPIs, a tabela e o gráfico
function renderVolumeExpDashboard() {
    if (!volumeExpData || volumeExpData.length === 0) {
        // Zera os KPIs
        document.getElementById("val-vol-exp-previsto").textContent = "-";
        document.getElementById("val-vol-exp-recebido").textContent = "-";
        document.getElementById("val-vol-exp-nao-chegou").textContent = "-";
        document.getElementById("val-vol-exp-eficiencia").textContent = "-";
        const elTableBody = document.getElementById("table-volume-exp-body");
        if (elTableBody) {
            elTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center;">Nenhum registro encontrado no arquivo.</td></tr>`;
        }
        return;
    }
    
    const selectedDate = elVolumeExpDateFilter ? elVolumeExpDateFilter.value : "Todas";
    
    // Filtra os dados
    const filtered = selectedDate === "Todas" 
        ? volumeExpData 
        : volumeExpData.filter(item => item.data === selectedDate);
        
    // Calcula KPIs
    let totalPrevisto = 0;
    let totalRecebido = 0;
    let totalNaoChegou = 0;
    
    filtered.forEach(item => {
        totalPrevisto += Number(item.volume_previsto) || 0;
        totalRecebido += Number(item.volume_recebido) || 0;
        totalNaoChegou += Number(item.quantidade_nao_chegou) || 0;
    });
    
    const eficienciaGlobal = totalPrevisto > 0 ? (totalRecebido / totalPrevisto) * 100 : 0;
    
    // Atualiza elementos de KPIs
    document.getElementById("val-vol-exp-previsto").textContent = totalPrevisto.toLocaleString('pt-BR');
    document.getElementById("val-vol-exp-recebido").textContent = totalRecebido.toLocaleString('pt-BR');
    document.getElementById("val-vol-exp-nao-chegou").textContent = totalNaoChegou.toLocaleString('pt-BR');
    document.getElementById("val-vol-exp-eficiencia").textContent = eficienciaGlobal.toFixed(1) + '%';
    
    // Cor do KPI de eficiência no topo (padrão diretoria: 98%-102% verde, 90-98/102-110 amarelo, desvios drásticos vermelho)
    const elKpiEficiencia = document.getElementById("kpi-vol-exp-eficiencia");
    if (elKpiEficiencia) {
        const valIcon = elKpiEficiencia.querySelector(".kpi-icon");
        if (valIcon) {
            if (eficienciaGlobal >= 98 && eficienciaGlobal <= 102) {
                valIcon.className = "kpi-icon icon-green";
            } else if ((eficienciaGlobal >= 90 && eficienciaGlobal < 98) || (eficienciaGlobal > 102 && eficienciaGlobal <= 110)) {
                valIcon.className = "kpi-icon icon-yellow";
            } else {
                valIcon.className = "kpi-icon icon-red";
            }
        }
    }

    // Função auxiliar para calcular o status e cor condicional (Diferença e Eficiência)
    function getVolumeExpStatus(previsto, recebido) {
        if (previsto <= 0) {
            if (recebido === 0) {
                return {
                    badgeClass: "badge-concluido",
                    icon: "fa-circle-check",
                    label: "Sem desvio",
                    eficiencia: 100
                };
            }
            return {
                badgeClass: "badge-critico",
                icon: "fa-circle-xmark",
                label: "Desvio drástico (volume não planejado)",
                eficiencia: 0
            };
        }
        const ef = (recebido / previsto) * 100;
        
        // 🟢 Verde: Variação aceitável (entre 98% e 102%)
        if (ef >= 98 && ef <= 102) {
            return {
                badgeClass: "badge-concluido",
                icon: "fa-circle-check",
                label: "Variação aceitável (±2%)",
                eficiencia: ef
            };
        }
        // 🟡 Amarelo: Desvios moderados (90% a 97.9% ou 102.1% a 110%)
        if ((ef >= 90 && ef < 98) || (ef > 102 && ef <= 110)) {
            return {
                badgeClass: "badge-pendente",
                icon: "fa-triangle-exclamation",
                label: "Desvio moderado",
                eficiencia: ef
            };
        }
        // 🔴 Vermelho: Desvios drásticos (< 90% ou > 110%)
        return {
            badgeClass: "badge-critico",
            icon: "fa-circle-xmark",
            label: "Desvio drástico",
            eficiencia: ef
        };
    }

    // Formata a diferença com sinal explícito (+ para falta, - para sobra)
    function formatDiferencaStr(val) {
        if (val > 0) return `+${val.toLocaleString('pt-BR')}`;
        if (val < 0) return `-${Math.abs(val).toLocaleString('pt-BR')}`;
        return '0';
    }
    
    // Renderiza a Tabela
    const elTableBody = document.getElementById("table-volume-exp-body");
    const elTableFooter = document.getElementById("table-volume-exp-footer");

    if (elTableBody) {
        if (filtered.length === 0) {
            elTableBody.innerHTML = `<tr><td colspan="7" style="text-align: center;">Nenhum registro encontrado para esta data.</td></tr>`;
            if (elTableFooter) elTableFooter.innerHTML = '';
        } else {
            elTableBody.innerHTML = filtered.map(item => {
                const previsto = Number(item.volume_previsto) || 0;
                const recebido = Number(item.volume_recebido) || 0;
                const naoChegou = Number(item.quantidade_nao_chegou) || 0;
                const diferenca = previsto - recebido;
                
                const statusInfo = getVolumeExpStatus(previsto, recebido);
                const diffStr = formatDiferencaStr(diferenca);
                const diffTooltip = diferenca > 0 
                    ? `Falta física: faltaram ${diferenca.toLocaleString('pt-BR')} itens` 
                    : (diferenca < 0 ? `Sobra física: ${Math.abs(diferenca).toLocaleString('pt-BR')} itens acima do planejado` : 'Volume conforme planejado');
                
                // Chip do ID de Viagem / Manifesto (SRTR...)
                let tripChipHtml = '';
                if (item.id_viagem) {
                    const cleanId = String(item.id_viagem).replace(/'/g, "\\'");
                    tripChipHtml = `
                        <div style="margin-top: 3px;">
                            <span class="trip-id-chip" title="ID da Viagem / Manifesto: ${item.id_viagem} (Clique para copiar)" onclick="copyTripId(event, '${cleanId}')">
                                <i class="fa-solid fa-barcode"></i> ${item.id_viagem}
                            </span>
                        </div>
                    `;
                }
                
                // Badge de Diferença
                const diffBadgeHtml = `
                    <span class="badge ${statusInfo.badgeClass}" title="${diffTooltip} | ${statusInfo.label}" style="display: inline-flex; align-items: center; gap: 4px; font-weight: 700;">
                        <i class="fa-solid ${statusInfo.icon}" style="font-size: 10px;"></i> ${diffStr}
                    </span>
                `;
                
                // Badge de Eficiência
                const eficienciaBadgeHtml = `
                    <span class="badge ${statusInfo.badgeClass}" title="${statusInfo.label}" style="padding: 4px 8px; border-radius: 12px; font-weight: 700; font-size: 11px;">
                        ${statusInfo.eficiencia.toFixed(1)}%
                    </span>
                `;
                
                return `
                    <tr>
                        <td>${item.data || '-'}</td>
                        <td>
                            <div style="display: flex; flex-direction: column;">
                                <span style="font-weight: 600; color: #E5E7EB;">${item.carro || '-'}</span>
                                ${tripChipHtml}
                            </div>
                        </td>
                        <td style="text-align: right; font-weight: 500;">${previsto.toLocaleString('pt-BR')}</td>
                        <td style="text-align: right; font-weight: 500;">${recebido.toLocaleString('pt-BR')}</td>
                        <td style="text-align: right;">${diffBadgeHtml}</td>
                        <td style="text-align: right; font-weight: 600; color: ${naoChegou > 0 ? '#FCA5A5' : '#9CA3AF'};">
                            <span title="Expedido Não Chegou">${naoChegou.toLocaleString('pt-BR')}</span>
                        </td>
                        <td style="text-align: center;">${eficienciaBadgeHtml}</td>
                    </tr>
                `;
            }).join('');

            // Renderiza Linha de Consolidação / Totalizador no Rodapé (tfoot)
            if (elTableFooter) {
                const totalDiferenca = totalPrevisto - totalRecebido;
                const totalStatus = getVolumeExpStatus(totalPrevisto, totalRecebido);
                const totalDiffStr = formatDiferencaStr(totalDiferenca);

                elTableFooter.innerHTML = `
                    <tr>
                        <td colspan="2" class="total-label">
                            <span style="display: flex; align-items: center; gap: 8px;">
                                <i class="fa-solid fa-calculator" style="color: var(--color-blue); font-size: 13px;"></i>
                                TOTAL DO CICLO (${filtered.length} ${filtered.length === 1 ? 'fluxo' : 'fluxos'})
                            </span>
                        </td>
                        <td style="text-align: right; font-weight: 800; color: #FFFFFF;">
                            ${totalPrevisto.toLocaleString('pt-BR')}
                        </td>
                        <td style="text-align: right; font-weight: 800; color: #FFFFFF;">
                            ${totalRecebido.toLocaleString('pt-BR')}
                        </td>
                        <td style="text-align: right;">
                            <span class="badge ${totalStatus.badgeClass}" title="Saldo Líquido Consolidado: ${totalDiferenca > 0 ? 'Falta total' : (totalDiferenca < 0 ? 'Sobra total' : 'Exato')} | ${totalStatus.label}" style="display: inline-flex; align-items: center; gap: 4px; font-weight: 800;">
                                <i class="fa-solid ${totalStatus.icon}" style="font-size: 10px;"></i> ${totalDiffStr}
                            </span>
                        </td>
                        <td style="text-align: right; font-weight: 800; color: ${totalNaoChegou > 0 ? '#FCA5A5' : '#9CA3AF'};">
                            <span title="Total Geral de Loss Prevention (Expedido Não Chegou)" style="display: inline-flex; align-items: center; gap: 5px; justify-content: flex-end;">
                                ${totalNaoChegou > 0 ? '<i class="fa-solid fa-shield-halved" style="color: var(--color-red); font-size: 11px;"></i>' : ''}
                                ${totalNaoChegou.toLocaleString('pt-BR')}
                            </span>
                        </td>
                        <td style="text-align: center;">
                            <span class="badge ${totalStatus.badgeClass}" title="Eficiência consolidada do ciclo" style="padding: 4px 8px; border-radius: 12px; font-weight: 800; font-size: 11px;">
                                ${eficienciaGlobal.toFixed(1)}%
                            </span>
                        </td>
                    </tr>
                `;
            }
        }
    }
    
    // Renderiza o Gráfico de Barras Agrupadas
    renderVolumeExpChart(filtered);
    renderVolumeExpNaoChegouChart(filtered);
}

// Função utilitária para cópia de ID de viagem com feedback visual toast
window.copyTripId = function(event, id) {
    if (event) {
        event.stopPropagation();
        event.preventDefault();
    }
    if (!id) return;

    const notify = () => {
        let toast = document.getElementById("copy-toast-notification");
        if (!toast) {
            toast = document.createElement("div");
            toast.id = "copy-toast-notification";
            toast.className = "copy-toast";
            document.body.appendChild(toast);
        }
        toast.innerHTML = `<i class="fa-solid fa-circle-check"></i> <span>ID <strong>${id}</strong> copiado para a área de transferência!</span>`;
        toast.classList.add("show");
        
        if (window._copyToastTimer) clearTimeout(window._copyToastTimer);
        window._copyToastTimer = setTimeout(() => {
            toast.classList.remove("show");
        }, 2500);
    };

    if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(id).then(notify).catch(() => {
            fallbackCopy(id, notify);
        });
    } else {
        fallbackCopy(id, notify);
    }
};

function fallbackCopy(text, callback) {
    const el = document.createElement("textarea");
    el.value = text;
    el.style.position = "fixed";
    el.style.opacity = "0";
    document.body.appendChild(el);
    el.select();
    try {
        document.execCommand("copy");
        if (callback) callback();
    } catch (e) {
        alert(`ID da Viagem: ${text}`);
    }
    document.body.removeChild(el);
}

// Função auxiliar para renderizar o gráfico Chart.js
function renderVolumeExpChart(data) {
    const ctx = document.getElementById("chart-volume-exp-comparativo");
    if (!ctx) return;
    
    // Destrói gráfico anterior se existir
    if (chartVolumeExp) {
        chartVolumeExp.destroy();
    }
    
    // Agrupa dados por carro para o gráfico
    const labels = data.map(item => item.carro || 'Desconhecido');
    const previstoData = data.map(item => Number(item.volume_previsto) || 0);
    const recebidoData = data.map(item => Number(item.volume_recebido) || 0);
    
    // Cria novo gráfico usando getChartConfig
    chartVolumeExp = new Chart(ctx, getChartConfig('bar', {
        labels: labels,
        datasets: [
            {
                label: 'Volume Previsto',
                data: previstoData,
                backgroundColor: 'rgba(59, 130, 246, 0.65)',
                borderColor: '#3B82F6',
                borderWidth: 1,
                borderRadius: 4
            },
            {
                label: 'Volume Recebido',
                data: recebidoData,
                backgroundColor: 'rgba(16, 185, 129, 0.65)',
                borderColor: '#10B981',
                borderWidth: 1,
                borderRadius: 4
            }
        ]
    }, {
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context) {
                        let label = context.dataset.label || '';
                        if (label) label += ': ';
                        if (context.parsed.y !== null) {
                            label += context.parsed.y.toLocaleString('pt-BR') + ' vol';
                        }
                        return label;
                    }
                }
            }
        }
    }));
}

// Função auxiliar para renderizar o gráfico de Expedido Não Chegou por Carro
function renderVolumeExpNaoChegouChart(data) {
    const ctx = document.getElementById("chart-volume-exp-nao-chegou-dist");
    if (!ctx) return;
    
    // Destrói gráfico anterior se existir
    if (chartVolumeExpNaoChegou) {
        chartVolumeExpNaoChegou.destroy();
    }
    
    // Filtra apenas carros com quantidades de não chegou maiores que zero
    const filteredData = data.filter(item => (Number(item.quantidade_nao_chegou) || 0) > 0);
    
    if (filteredData.length === 0) {
        // Se não houver cargas não entregues, mostra uma rosca verde bonita indicando sucesso
        chartVolumeExpNaoChegou = new Chart(ctx, getChartConfig('doughnut', {
            labels: ['Sem Ocorrências'],
            datasets: [{
                data: [1],
                backgroundColor: ['rgba(16, 185, 129, 0.2)'],
                borderColor: ['#10B981'],
                borderWidth: 1
            }]
        }, {
            plugins: {
                tooltip: {
                    callbacks: {
                        label: () => ' 100% de eficiência de entrega'
                    }
                }
            }
        }));
        return;
    }
    
    const labels = filteredData.map(item => item.carro || 'Desconhecido');
    const values = filteredData.map(item => Number(item.quantidade_nao_chegou) || 0);
    
    // Cores dinâmicas para o gráfico
    const colorPalette = [
        '#EF4444', // Vermelho
        '#F59E0B', // Amarelo
        '#3B82F6', // Azul
        '#10B981', // Verde
        '#8B5CF6', // Roxo
        '#EC4899', // Rosa
        '#06B6D4'  // Ciano
    ];
    
    const bgColors = colorPalette.slice(0, labels.length).map(c => c + 'a6'); // Adiciona transparência alfa (~65%)
    
    chartVolumeExpNaoChegou = new Chart(ctx, getChartConfig('doughnut', {
        labels: labels,
        datasets: [{
            data: values,
            backgroundColor: bgColors.length > 0 ? bgColors : ['rgba(239, 68, 68, 0.65)'],
            borderColor: colorPalette.slice(0, labels.length),
            borderWidth: 1
        }]
    }, {
        plugins: {
            tooltip: {
                callbacks: {
                    label: function(context) {
                        const val = context.raw || 0;
                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                        const pct = total > 0 ? ((val / total) * 100).toFixed(1) + '%' : '0%';
                        return ` ${context.label}: ${val.toLocaleString('pt-BR')} vol (${pct})`;
                    }
                }
            }
        }
    }));
}

// --- FUNÇÕES DA VISÃO RECEBIMENTO ---

let chartRecebimentoComparativo = null;
let chartRecebimentoHistorico = null;

// Carrega os filtros de data para a aba Recebimento
async function loadRecebimentoFilters() {
    try {
        const response = await fetch(`${API_BASE}/api/recebimento/filters?_=${Date.now()}`);
        const data = await response.json();
        
        const elDateFilter = document.getElementById("filter-recebimento-date");
        if (!elDateFilter) return;
        
        elDateFilter.innerHTML = '';
        
        if (data.dates && data.dates.length > 0) {
            data.dates.forEach(date => {
                const opt = document.createElement("option");
                opt.value = date;
                opt.textContent = date;
                elDateFilter.appendChild(opt);
            });
            // Carrega e desenha os dados da primeira data (mais recente)
            renderRecebimentoDashboard();
        } else {
            elDateFilter.innerHTML = '<option value="">Sem datas disponíveis</option>';
        }
    } catch (err) {
        console.error("Erro ao carregar filtros de recebimento:", err);
    }
}

// Busca os dados da data selecionada e renderiza os KPIs, Tabela e Gráfico Consolidados
async function renderRecebimentoDashboard() {
    try {
        const elDateFilter = document.getElementById("filter-recebimento-date");
        if (!elDateFilter) return;
        
        const dateVal = elDateFilter.value;
        if (!dateVal) return;
        
        const response = await fetch(`${API_BASE}/api/recebimento/data?date=${dateVal}&_=${Date.now()}`);
        const data = await response.json();
        
        // Dicionário para consolidar os volumes por carro (somando Tabela 1 e Tabela 2)
        const consolidated = {};
        
        const mergeData = (tableData) => {
            if (!tableData) return;
            tableData.forEach(d => {
                const car = d.car.trim();
                if (!consolidated[car]) {
                    consolidated[car] = {
                        car: car,
                        total: 0,
                        coleta: 0,
                        lote: 0,
                        sem_bipe: 0
                    };
                }
                consolidated[car].total += d.total;
                consolidated[car].coleta += d.coleta;
                consolidated[car].lote += d.lote;
                consolidated[car].sem_bipe += d.sem_bipe;
            });
        };
        
        mergeData(data.left_table);
        mergeData(data.right_table);
        
        const listData = Object.values(consolidated);
        
        // Puxa o recebimento total do dia do JSON retornado pelo backend
        const recebTotal = data.recebimento_total || 0;
        
        // Calcula o total geral de "Sem Bipe de Coleta de Chegada"
        let semBipeSum = 0;
        listData.forEach(d => {
            semBipeSum += d.sem_bipe;
        });
        
        // Calcula a diferença total (Recebimento - Sem Bipe)
        const diferenca = recebTotal - semBipeSum;
        
        // Calcula as porcentagens
        const pctSemBipe = recebTotal > 0 ? ((semBipeSum / recebTotal) * 100).toFixed(1) + '%' : '0.0%';
        const pctEficiencia = recebTotal > 0 ? ((diferenca / recebTotal) * 100).toFixed(1) + '%' : '0.0%';
        
        // Atualiza os KPIs consolidados na tela
        const elTotalDia = document.getElementById("val-receb-total-dia");
        const elSemBipe = document.getElementById("val-receb-sem-bipe");
        const elDiferenca = document.getElementById("val-receb-diferenca");
        const elPctSemBipe = document.getElementById("pct-receb-sem-bipe");
        const elPctEficiencia = document.getElementById("pct-receb-eficiencia");
        
        if (elTotalDia) elTotalDia.textContent = recebTotal.toLocaleString('pt-BR');
        if (elSemBipe) elSemBipe.textContent = semBipeSum.toLocaleString('pt-BR');
        if (elDiferenca) elDiferenca.textContent = diferenca.toLocaleString('pt-BR');
        if (elPctSemBipe) elPctSemBipe.textContent = pctSemBipe;
        if (elPctEficiencia) elPctEficiencia.textContent = pctEficiencia;
        
        // Popula Tabela Consolidada
        const tbody = document.getElementById("table-recebimento-body");
        if (tbody) {
            if (listData.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-muted);">Nenhum dado encontrado</td></tr>';
            } else {
                tbody.innerHTML = listData.map(d => `
                    <tr>
                        <td><b>${d.car}</b></td>
                        <td style="text-align: right; font-weight: 600; color: var(--text-primary);">${d.total.toLocaleString('pt-BR')}</td>
                        <td style="text-align: right;">${d.coleta.toLocaleString('pt-BR')}</td>
                        <td style="text-align: right;">${d.lote.toLocaleString('pt-BR')}</td>
                        <td style="text-align: right; color: var(--color-yellow); font-weight: 500;">${d.sem_bipe.toLocaleString('pt-BR')}</td>
                    </tr>
                `).join("");
            }
        }
        
        // Renderiza o Gráfico de Colunas Único com a Diferença (Coleta Chegada - Inserido Lote) por Caminhão
        const labels = listData.map(d => d.car);
        // Calcula a diferença para cada carro (d.coleta - d.lote)
        const diffs = listData.map(d => d.coleta - d.lote);
        
        if (chartRecebimentoComparativo) chartRecebimentoComparativo.destroy();
        
        const canvas = document.getElementById("chart-recebimento-comparativo");
        if (canvas) {
            chartRecebimentoComparativo = new Chart(canvas, getChartConfig('bar', {
                labels: labels,
                datasets: [
                    {
                        label: 'Diferença (Coleta Chegada - Inserido Lote)',
                        data: diffs,
                        backgroundColor: '#EF4444', // Vermelho vibrante para alertar
                        borderRadius: 6
                    }
                ]
            }));
        }

        // --- RENDERIZAÇÃO DO HISTÓRICO COMPARATIVO (ÚLTIMOS 5 DIAS) ---
        const historyList = data.history || [];
        
        // Renderiza Gráfico Comparativo do Histórico (Linha com apenas o total sem bipe)
        const histLabels = historyList.map(h => h.date);
        const histSemBipe = historyList.map(h => h.sem_bipe_total);
        
        if (chartRecebimentoHistorico) chartRecebimentoHistorico.destroy();
        
        const canvasHist = document.getElementById("chart-recebimento-historico");
        if (canvasHist) {
            chartRecebimentoHistorico = new Chart(canvasHist, getChartConfig('line', {
                labels: histLabels,
                datasets: [
                    {
                        label: 'Total Sem Bipe',
                        data: histSemBipe,
                        borderColor: '#EF4444', // Vermelho vibrante
                        backgroundColor: 'rgba(239, 68, 68, 0.1)', // Vermelho translúcido
                        borderWidth: 3,
                        fill: true,
                        tension: 0.3
                    }
                ]
            }));
        }
    } catch (err) {
        console.error("Erro ao carregar e consolidar os dados de recebimento:", err);
    }
}


// ====================================================
// FUNÇÕES DA VISÃO VOLUMETRIA DIÁRIA
// ====================================================

// Variáveis de controle de debounce e status de salvamento para Volumetria
let volumetriaSaveTimeout = null;
let volumetriaStatusHideTimeout = null;

function showVolumetriaSaveStatus(state) {
    const el = document.getElementById("volumetria-save-status");
    if (!el) return;
    if (volumetriaStatusHideTimeout) clearTimeout(volumetriaStatusHideTimeout);
    
    if (state === "saving") {
        el.style.display = "inline-flex";
        el.style.alignItems = "center";
        el.style.gap = "4px";
        el.style.opacity = "1";
        el.style.background = "rgba(245, 158, 11, 0.2)";
        el.style.color = "#FBBF24";
        el.style.borderColor = "rgba(245, 158, 11, 0.4)";
        el.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    } else if (state === "saved") {
        el.style.display = "inline-flex";
        el.style.alignItems = "center";
        el.style.gap = "4px";
        el.style.opacity = "1";
        el.style.background = "rgba(16, 185, 129, 0.2)";
        el.style.color = "#34D399";
        el.style.borderColor = "rgba(16, 185, 129, 0.4)";
        el.innerHTML = '<i class="fa-solid fa-check"></i> Salvo com sucesso!';
        volumetriaStatusHideTimeout = setTimeout(() => {
            el.style.opacity = "0";
            setTimeout(() => { el.style.display = "none"; }, 300);
        }, 2000);
    } else if (state === "error") {
        el.style.display = "inline-flex";
        el.style.alignItems = "center";
        el.style.gap = "4px";
        el.style.opacity = "1";
        el.style.background = "rgba(239, 68, 68, 0.2)";
        el.style.color = "#F87171";
        el.style.borderColor = "rgba(239, 68, 68, 0.4)";
        el.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> Erro ao salvar';
    }
}

// Salva alterações de volumetria no backend (SQLite + JSON)
async function saveVolumetriaChanges() {
    if (!volumetriaData) return;
    showVolumetriaSaveStatus("saving");
    try {
        const resp = await fetch(`${API_BASE}/api/volumetria/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(volumetriaData)
        });
        if (resp.ok) {
            const resJson = await resp.json();
            if (resJson.success && resJson.data) {
                volumetriaData.updated_at = resJson.data.updated_at || volumetriaData.updated_at;
                const elLastUpdate = document.getElementById("volumetria-last-update");
                if (elLastUpdate) elLastUpdate.textContent = volumetriaData.updated_at;
            }
            showVolumetriaSaveStatus("saved");
        } else {
            showVolumetriaSaveStatus("error");
        }
    } catch (err) {
        console.error("Erro ao salvar dados de volumetria:", err);
        showVolumetriaSaveStatus("error");
    }
}

function debouncedSaveVolumetria(delay = 400) {
    if (volumetriaSaveTimeout) clearTimeout(volumetriaSaveTimeout);
    showVolumetriaSaveStatus("saving");
    volumetriaSaveTimeout = setTimeout(() => {
        saveVolumetriaChanges();
    }, delay);
}

// Carrega os dados brutos da API de Volumetria
async function loadVolumetriaData() {
    try {
        const tbody = document.getElementById("table-volumetria-body");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando dados de volumetria...</td></tr>`;
        }
        
        const response = await fetch(`${API_BASE}/api/volumetria/data?_=${Date.now()}`);
        if (!response.ok) throw new Error("Erro na requisição da API de volumetria.");
        
        volumetriaData = await response.json();
        
        populateVolumetriaFilters();
        filterAndRenderVolumetria();
    } catch (err) {
        console.error("Erro ao carregar dados de volumetria:", err);
        const tbody = document.getElementById("table-volumetria-body");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--danger); padding: 20px;">Erro ao carregar dados de volumetria.</td></tr>`;
        }
    }
}

// Popula os filtros de Status de Viagem e PDD
function populateVolumetriaFilters() {
    if (!volumetriaData || !volumetriaData.records) return;
    
    const statusViagemSelect = document.getElementById("filter-volumetria-status-viagem");
    const pddSelect = document.getElementById("filter-volumetria-pdd");
    
    if (statusViagemSelect) {
        const currStatus = statusViagemSelect.value;
        const statuses = [...new Set(volumetriaData.records.map(r => r.status_viagem).filter(Boolean))];
        statusViagemSelect.innerHTML = '<option value="Todos">Todos os Status</option>';
        statuses.forEach(st => {
            const opt = document.createElement("option");
            opt.value = st;
            opt.textContent = st;
            statusViagemSelect.appendChild(opt);
        });
        if (statuses.includes(currStatus)) statusViagemSelect.value = currStatus;
    }
    
    if (pddSelect) {
        const currPdd = pddSelect.value;
        const pdds = [...new Set(volumetriaData.records.map(r => r.pdd_saida).filter(Boolean))];
        pddSelect.innerHTML = '<option value="Todos">Todos os PDDs</option>';
        pdds.forEach(p => {
            const opt = document.createElement("option");
            opt.value = p;
            opt.textContent = p;
            pddSelect.appendChild(opt);
        });
        if (pdds.includes(currPdd)) pddSelect.value = currPdd;
    }
}

// Aplica filtros e renderiza o dashboard completo de Volumetria
function filterAndRenderVolumetria() {
    if (!volumetriaData) return;
    
    const statusViagemFilter = document.getElementById("filter-volumetria-status-viagem")?.value || "Todos";
    const pddFilter = document.getElementById("filter-volumetria-pdd")?.value || "Todos";
    const searchQuery = (document.getElementById("volumetria-table-search")?.value || "").trim().toLowerCase();
    
    let records = volumetriaData.records || [];
    
    if (statusViagemFilter !== "Todos") {
        records = records.filter(r => r.status_viagem === statusViagemFilter);
    }
    if (pddFilter !== "Todos") {
        records = records.filter(r => r.pdd_saida === pddFilter);
    }
    if (searchQuery) {
        records = records.filter(r => 
            (r.id_transporte && r.id_transporte.toLowerCase().includes(searchQuery)) ||
            (r.pdd_saida && r.pdd_saida.toLowerCase().includes(searchQuery)) ||
            (r.status_viagem && r.status_viagem.toLowerCase().includes(searchQuery)) ||
            (r.obs && r.obs.toLowerCase().includes(searchQuery))
        );
    }
    
    function getPddPrio(pdd) {
        const p = (pdd || "").toUpperCase();
        if (p.includes("SP BRE") || p.includes("BRE")) return 1;
        if (p.includes("SN RAO") || p.includes("RAO")) return 2;
        if (p.includes("IBG")) return 3;
        if (p.includes("EXT")) return 4;
        return 5;
    }

    records.sort((a, b) => {
        const prioA = getPddPrio(a.pdd_saida);
        const prioB = getPddPrio(b.pdd_saida);
        if (prioA !== prioB) return prioA - prioB;
        
        const pddA = (a.pdd_saida || "").toUpperCase();
        const pddB = (b.pdd_saida || "").toUpperCase();
        if (pddA !== pddB) return pddA.localeCompare(pddB);
        
        const prevA = a.previsao_chegada || "";
        const prevB = b.previsao_chegada || "";
        if (prevA && prevB) return prevA.localeCompare(prevB);
        
        return (a.id_transporte || "").localeCompare(b.id_transporte || "");
    });
    
    volumetriaFilteredRecords = records;
    
    // Atualiza cabeçalhos
    const elRefDate = document.getElementById("volumetria-ref-date");
    if (elRefDate) elRefDate.textContent = volumetriaData.data_referencia || "-";
    
    const elLastUpdate = document.getElementById("volumetria-last-update");
    if (elLastUpdate) elLastUpdate.textContent = volumetriaData.updated_at || "-";
    
    // Atualiza KPIs Globais
    const kpis = volumetriaData.kpis || {};
    
    // Calcula totais da seleção filtrada se houver filtro ativo
    const isFiltered = (statusViagemFilter !== "Todos" || pddFilter !== "Todos" || searchQuery !== "");
    const sumPrevisto = records.reduce((acc, r) => acc + (Number(r.pedido_sistema) || 0), 0);
    const sumBipados = records.reduce((acc, r) => acc + (Number(r.bipado) || 0), 0);
    const coletas = (volumetriaData.coletas !== undefined && volumetriaData.coletas !== null) ? Number(volumetriaData.coletas) : (Number(kpis.coletas) || 0);
    
    const valPrevisto = isFiltered ? sumPrevisto : (kpis.previsto || sumPrevisto);
    const valBipados = sumBipados;
    const valTotalPiso = valBipados + coletas;
    const valDiferenca = valBipados - valPrevisto;
    const valEficiencia = valPrevisto > 0 ? ((valBipados / valPrevisto) * 100) : 100;
    
    // Preenche elementos de KPIs
    const elPrev = document.getElementById("val-vol-previsto");
    const elBip = document.getElementById("val-vol-bipados");
    const elCol = document.getElementById("val-vol-coletas");
    const elTotPiso = document.getElementById("val-vol-total-piso");
    
    if (elPrev) elPrev.textContent = valPrevisto.toLocaleString("pt-BR");
    if (elBip) elBip.textContent = valBipados.toLocaleString("pt-BR");
    if (elCol) elCol.textContent = coletas.toLocaleString("pt-BR");
    if (elTotPiso) elTotPiso.textContent = valTotalPiso.toLocaleString("pt-BR");
    
    const elDiff = document.getElementById("val-vol-diferenca");
    const elEfic = document.getElementById("pct-vol-eficiencia");
    if (elDiff) {
        elDiff.textContent = (valDiferenca >= 0 ? "+" : "") + valDiferenca.toLocaleString("pt-BR");
        elDiff.style.color = valDiferenca >= 0 ? "#34D399" : "#F87171";
    }
    if (elEfic) {
        elEfic.textContent = valEficiencia.toFixed(1) + "%";
        elEfic.className = valEficiencia >= 100 ? "kpi-pct pct-green" : "kpi-pct pct-yellow";
    }
    
    // Configura botões de edição de Coletas e Previsto
    const btnEditColetas = document.getElementById("btn-edit-vol-coletas");
    if (btnEditColetas && !btnEditColetas.dataset.bound) {
        btnEditColetas.dataset.bound = "true";
        btnEditColetas.addEventListener("click", async () => {
            const curVal = (volumetriaData.coletas !== undefined && volumetriaData.coletas !== null) ? volumetriaData.coletas : (volumetriaData.kpis?.coletas || 10790);
            const inputVal = prompt("Informe o novo volume de Coletas para a Volumetria Diária:", curVal);
            if (inputVal !== null && inputVal.trim() !== "") {
                const parsed = parseInt(inputVal.replace(/\D/g, ""), 10);
                if (!isNaN(parsed) && parsed >= 0) {
                    volumetriaData.coletas = parsed;
                    if (!volumetriaData.kpis) volumetriaData.kpis = {};
                    volumetriaData.kpis.coletas = parsed;
                    filterAndRenderVolumetria();
                    await saveVolumetriaChanges();

                    // Sincroniza com o Ranking
                    if (rankingData) {
                        if (!rankingData.kpis) rankingData.kpis = {};
                        rankingData.kpis.coletas = parsed;
                        filterAndRenderRanking();
                    }
                }
            }
        });
    }

    const btnEditPrev = document.getElementById("btn-edit-vol-previsto");
    if (btnEditPrev && !btnEditPrev.dataset.bound) {
        btnEditPrev.dataset.bound = "true";
        btnEditPrev.addEventListener("click", async () => {
            const curVal = volumetriaData.kpis?.previsto || sumPrevisto;
            const inputVal = prompt("Informe o novo volume Previsto para a Volumetria Diária:", curVal);
            if (inputVal !== null && inputVal.trim() !== "") {
                const parsed = parseInt(inputVal.replace(/\D/g, ""), 10);
                if (!isNaN(parsed) && parsed >= 0) {
                    if (!volumetriaData.kpis) volumetriaData.kpis = {};
                    volumetriaData.kpis.previsto = parsed;
                    filterAndRenderVolumetria();
                    await saveVolumetriaChanges();

                    // Sincroniza com o Ranking
                    if (rankingData) {
                        if (!rankingData.kpis) rankingData.kpis = {};
                        rankingData.kpis.previsto = parsed;
                        filterAndRenderRanking();
                    }
                }
            }
        });
    }

    // Renderiza tabela e gráficos
    renderVolumetriaTable(records, sumPrevisto, sumBipados);
    renderVolumetriaCharts(records, valBipados, coletas);
}

// Renderiza as linhas e rodapé da tabela de Volumetria
function renderVolumetriaTable(records, sumPrevisto, sumBipados) {
    const tbody = document.getElementById("table-volumetria-body");
    if (!tbody) return;
    
    tbody.innerHTML = "";
    
    if (records.length === 0) {
        tbody.innerHTML = `<tr><td colspan="12" style="text-align: center; color: var(--text-muted); padding: 20px;">Nenhuma viagem encontrada com os filtros selecionados.</td></tr>`;
        return;
    }
    
    records.forEach(row => {
        // Formata badge de status de viagem
        let badgeViagemClass = "volumetria-badge-transito";
        let iconViagem = "fa-truck-fast";
        const svLower = (row.status_viagem || "").toLowerCase();
        if (svLower.includes("concluído") || svLower.includes("concluido") || svLower.includes("完成")) {
            badgeViagemClass = "volumetria-badge-concluido";
            iconViagem = "fa-circle-check";
        } else if (svLower.includes("programado") || svLower.includes("调度")) {
            badgeViagemClass = "volumetria-badge-programado";
            iconViagem = "fa-clock";
        }
        
        function getStatusSelectStyle(st) {
            const s = (st || "").toUpperCase().trim();
            if (s.includes("FINALIZ")) {
                return 'background: #991B1B; color: #FFFFFF; border: 1px solid rgba(239, 68, 68, 0.6); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            } else if (s.includes("CANCEL")) {
                return 'background: rgba(239, 68, 68, 0.25); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            } else if (s.includes("TRÂNSITO") || s.includes("TRANSITO")) {
                return 'background: rgba(99, 102, 241, 0.25); color: #818CF8; border: 1px solid rgba(99, 102, 241, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            } else if (s.includes("PISO")) {
                return 'background: rgba(16, 185, 129, 0.25); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            } else if (s.includes("PÁTIO") || s.includes("PATIO")) {
                return 'background: rgba(245, 158, 11, 0.25); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            } else if (s === "" || s === "-" || s.includes("BRANCO") || s.includes("VAZIO")) {
                return 'background: rgba(156, 163, 175, 0.15); color: #9CA3AF; border: 1px solid rgba(156, 163, 175, 0.35); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            }
            // EM ANDAMENTO (padrão)
            return 'background: rgba(59, 130, 246, 0.25); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
        }

        const stUpper = (row.status || "").toUpperCase().trim();
        const stBadgeStyle = getStatusSelectStyle(stUpper);

        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td><strong style="color: #60A5FA; letter-spacing: 0.3px; font-size: 11px;">${row.id_transporte || "-"}</strong></td>
            <td><span class="${badgeViagemClass}"><i class="fa-solid ${iconViagem}"></i> ${row.status_viagem || "-"}</span></td>
            <td><strong style="color: #FFFFFF; font-size: 11.5px;">${row.pdd_saida || "-"}</strong></td>
            <td style="text-align: right; font-weight: 600; color: #E5E7EB; font-size: 11.5px;">${(Number(row.pedido_sistema) || 0).toLocaleString("pt-BR")}</td>
            <td style="text-align: center;">
                <input type="text" class="volumetria-cell-input" data-id="${row.id_transporte || ''}" data-field="previsao_chegada" value="${row.previsao_chegada || ''}" placeholder="--:--" title="Editar Previsão de Chegada">
            </td>
            <td style="text-align: center;">
                <input type="text" class="volumetria-cell-input" data-id="${row.id_transporte || ''}" data-field="chegada_real" value="${row.chegada_real || ''}" placeholder="--:--" title="Editar Horário de Chegada Real">
            </td>
            <td style="text-align: center;">
                <input type="text" class="volumetria-cell-input" data-id="${row.id_transporte || ''}" data-field="inicio_coleta" value="${row.inicio_coleta || ''}" placeholder="--:--" title="Editar Início de Coleta">
            </td>
            <td style="text-align: center;">
                <input type="text" class="volumetria-cell-input" data-id="${row.id_transporte || ''}" data-field="fim_coleta" value="${row.fim_coleta || ''}" placeholder="--:--" title="Editar Fim de Coleta">
            </td>
            <td style="text-align: center;">
                <select class="volumetria-status-select" data-id="${row.id_transporte || ''}" data-field="status" style="${stBadgeStyle}">
                    <option value="" ${stUpper === '' || stUpper === '-' || stUpper.includes('BRANCO') ? 'selected' : ''}>-- EM BRANCO --</option>
                    <option value="NO PÁTIO" ${stUpper.includes('PÁTIO') || stUpper.includes('PATIO') || stUpper.includes('PROGRAM') || stUpper.includes('PLANEJ') ? 'selected' : ''}>NO PÁTIO</option>
                    <option value="EM TRÂNSITO" ${stUpper.includes('TRÂNSITO') || stUpper.includes('TRANSITO') ? 'selected' : ''}>EM TRÂNSITO</option>
                    <option value="EM ANDAMENTO" ${stUpper === 'EM ANDAMENTO' || (stUpper.includes('ANDAMENTO') && !stUpper.includes('TRANSIT') && !stUpper.includes('TRÂNSIT')) ? 'selected' : ''}>EM ANDAMENTO</option>
                    <option value="NO PISO" ${stUpper.includes('PISO') ? 'selected' : ''}>NO PISO</option>
                    <option value="FINALIZADO" ${stUpper.includes('FINALIZ') ? 'selected' : ''}>FINALIZADO</option>
                    <option value="CANCELADO" ${stUpper.includes('CANCEL') ? 'selected' : ''}>CANCELADO</option>
                </select>
            </td>
            <td><input type="text" class="volumetria-obs-input" data-id="${row.id_transporte || ''}" data-field="obs" value="${row.obs ? String(row.obs).replace(/"/g, '&quot;') : ''}" placeholder="OBS..." title="Clique para editar"></td>
            <td style="text-align: right;">
                <input type="number" class="volumetria-cell-input volumetria-bipado-input" data-id="${row.id_transporte || ''}" data-field="bipado" value="${Number(row.bipado) || 0}" min="0" step="1" placeholder="0" title="Editar Volume Bipado">
            </td>
            <td style="text-align: center;">
                <button type="button" class="btn-delete-vol-truck" data-id="${row.id_transporte || ''}" title="Excluir Viagem / Caminhão ${row.id_transporte || ''}" style="background: none; border: none; color: #EF4444; opacity: 0.6; cursor: pointer; padding: 3px 6px; font-size: 11.5px; border-radius: 4px; transition: all 0.2s;" onmouseover="this.style.opacity='1'; this.style.background='rgba(239,68,68,0.15)'" onmouseout="this.style.opacity='0.6'; this.style.background='none'">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </td>
        `;
        tbody.appendChild(tr);
    });

    // Adiciona listener para exclusão de viagem/caminhão
    tbody.querySelectorAll(".btn-delete-vol-truck").forEach(btn => {
        btn.addEventListener("click", async (e) => {
            e.stopPropagation();
            const trId = btn.getAttribute("data-id");
            if (!trId) return;
            if (confirm(`Deseja realmente remover o caminhão/viagem ${trId}?`)) {
                if (volumetriaData && volumetriaData.records) {
                    volumetriaData.records = volumetriaData.records.filter(r => r.id_transporte !== trId);
                    populateVolumetriaFilters();
                    filterAndRenderVolumetria();
                    await saveVolumetriaChanges();
                    try {
                        await fetch(`${API_BASE}/api/volumetria/delete`, {
                            method: "POST",
                            headers: { "Content-Type": "application/json" },
                            body: JSON.stringify({ id_transporte: trId })
                        });
                    } catch(err){}
                }
            }
        });
    });

    // Adiciona listener para campos de texto/hora/número (chegada, inicio_coleta, fim_coleta, obs, bipado)
    tbody.querySelectorAll(".volumetria-cell-input, .volumetria-obs-input").forEach(input => {
        const updateRowFromInput = (e, immediateSave = false) => {
            const trId = e.target.getAttribute("data-id");
            const field = e.target.getAttribute("data-field");
            let val = e.target.value;
            if (field === "bipado") {
                val = Number(val) || 0;
            }
            if (volumetriaData && volumetriaData.records) {
                const targetRow = volumetriaData.records.find(r => r.id_transporte === trId);
                if (targetRow && field) {
                    targetRow[field] = val;
                    
                    // Se alterou bipado, recalcula KPIs, rodapé e gráficos instantaneamente
                    if (field === "bipado") {
                        const recs = volumetriaFilteredRecords || volumetriaData.records;
                        const newSumBipados = recs.reduce((acc, r) => acc + (Number(r.bipado) || 0), 0);
                        const newSumPrevisto = recs.reduce((acc, r) => acc + (Number(r.pedido_sistema) || 0), 0);
                        const coletas = (volumetriaData.coletas !== undefined && volumetriaData.coletas !== null) ? Number(volumetriaData.coletas) : (volumetriaData.kpis?.coletas || 0);
                        const newTotalPiso = newSumBipados + coletas;
                        const newDiff = newSumBipados - newSumPrevisto;
                        const newEfic = newSumPrevisto > 0 ? ((newSumBipados / newSumPrevisto) * 100) : 100;
                        
                        const elBip = document.getElementById("val-vol-bipados");
                        const elTotPiso = document.getElementById("val-vol-total-piso");
                        const elDiff = document.getElementById("val-vol-diferenca");
                        const elEfic = document.getElementById("pct-vol-eficiencia");
                        const footBip = document.getElementById("foot-vol-bipado");
                        
                        if (elBip) elBip.textContent = newSumBipados.toLocaleString("pt-BR");
                        if (elTotPiso) elTotPiso.textContent = newTotalPiso.toLocaleString("pt-BR");
                        if (footBip) footBip.textContent = newSumBipados.toLocaleString("pt-BR");
                        if (elDiff) {
                            elDiff.textContent = (newDiff >= 0 ? "+" : "") + newDiff.toLocaleString("pt-BR");
                            elDiff.style.color = newDiff >= 0 ? "#34D399" : "#F87171";
                        }
                        if (elEfic) {
                            elEfic.textContent = newEfic.toFixed(1) + "%";
                            elEfic.className = newEfic >= 100 ? "kpi-pct pct-green" : "kpi-pct pct-yellow";
                        }
                        renderVolumetriaCharts(recs, newSumBipados, coletas);
                    }
                    
                    if (immediateSave) {
                        if (volumetriaSaveTimeout) clearTimeout(volumetriaSaveTimeout);
                        saveVolumetriaChanges();
                    } else {
                        debouncedSaveVolumetria(400);
                    }
                }
            }
        };

        input.addEventListener("input", (e) => updateRowFromInput(e, false));
        input.addEventListener("change", (e) => updateRowFromInput(e, true));
        input.addEventListener("blur", (e) => updateRowFromInput(e, true));
    });

    // Adiciona listener para dropdown de Status
    tbody.querySelectorAll(".volumetria-status-select").forEach(select => {
        select.addEventListener("change", async (e) => {
            const trId = e.target.getAttribute("data-id");
            const newStatus = e.target.value;
            
            // Atualiza estilo visual do select imediatamente
            function getStyleForStatus(st) {
                const s = (st || "").toUpperCase().trim();
                if (s.includes("FINALIZ")) {
                    return 'background: #991B1B; color: #FFFFFF; border: 1px solid rgba(239, 68, 68, 0.6); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                } else if (s.includes("CANCEL")) {
                    return 'background: rgba(239, 68, 68, 0.25); color: #F87171; border: 1px solid rgba(239, 68, 68, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                } else if (s.includes("TRÂNSITO") || s.includes("TRANSITO")) {
                    return 'background: rgba(99, 102, 241, 0.25); color: #818CF8; border: 1px solid rgba(99, 102, 241, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                } else if (s.includes("PISO")) {
                    return 'background: rgba(16, 185, 129, 0.25); color: #34D399; border: 1px solid rgba(16, 185, 129, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                } else if (s.includes("PÁTIO") || s.includes("PATIO")) {
                    return 'background: rgba(245, 158, 11, 0.25); color: #FBBF24; border: 1px solid rgba(245, 158, 11, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                } else if (s === "" || s === "-" || s.includes("BRANCO") || s.includes("VAZIO")) {
                    return 'background: rgba(156, 163, 175, 0.15); color: #9CA3AF; border: 1px solid rgba(156, 163, 175, 0.35); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
                }
                return 'background: rgba(59, 130, 246, 0.25); color: #60A5FA; border: 1px solid rgba(59, 130, 246, 0.5); font-weight: 700; padding: 2px 8px; border-radius: 12px; font-size: 10px; letter-spacing: 0.3px; outline: none; cursor: pointer;';
            }
            e.target.style.cssText = getStyleForStatus(newStatus);
            
            if (volumetriaData && volumetriaData.records) {
                const targetRow = volumetriaData.records.find(r => r.id_transporte === trId);
                if (targetRow) {
                    targetRow.status = newStatus;
                    if (volumetriaSaveTimeout) clearTimeout(volumetriaSaveTimeout);
                    await saveVolumetriaChanges();
                }
            }
        });
    });
    
    // Atualiza Totais do Rodapé
    const footPrev = document.getElementById("foot-vol-previsto");
    const footBip = document.getElementById("foot-vol-bipado");
    if (footPrev) footPrev.textContent = sumPrevisto.toLocaleString("pt-BR");
    if (footBip) footBip.textContent = sumBipados.toLocaleString("pt-BR");
}

// Renderiza os gráficos do painel de Volumetria
function renderVolumetriaCharts(records, totalBipados, coletas) {
    // 1. Gráfico Comparativo: Pedido Sistema vs Bipado por PDD
    const ctxComp = document.getElementById("chart-volumetria-comparativo");
    if (ctxComp) {
        if (chartVolumetriaComparativo) chartVolumetriaComparativo.destroy();
        
        const labels = records.map(r => `${r.pdd_saida} (${(r.id_transporte || '').slice(-5)})`);
        const pedidos = records.map(r => Number(r.pedido_sistema) || 0);
        const bipados = records.map(r => Number(r.bipado) || 0);
        
        chartVolumetriaComparativo = new Chart(ctxComp, getChartConfig('bar', {
            labels: labels,
            datasets: [
                {
                    label: 'Pedido Sistema (Previsto)',
                    data: pedidos,
                    backgroundColor: 'rgba(59, 130, 246, 0.75)',
                    borderColor: '#3B82F6',
                    borderWidth: 1,
                    borderRadius: 6
                },
                {
                    label: 'Volume Bipado (Real)',
                    data: bipados,
                    backgroundColor: 'rgba(16, 185, 129, 0.75)',
                    borderColor: '#10B981',
                    borderWidth: 1,
                    borderRadius: 6
                }
            ]
        }));
    }
    
    // 2. Gráfico de Rosca: Composição do Piso (Bipados vs Coletas)
    const ctxCompPiso = document.getElementById("chart-volumetria-composicao");
    if (ctxCompPiso) {
        if (chartVolumetriaComposicao) chartVolumetriaComposicao.destroy();
        
        chartVolumetriaComposicao = new Chart(ctxCompPiso, getChartConfig('doughnut', {
            labels: ['Bipados no Piso', 'Coletas'],
            datasets: [{
                data: [totalBipados, coletas],
                backgroundColor: [
                    '#10B981', // Verde para bipados
                    '#F59E0B'  // Amarelo para coletas
                ],
                borderWidth: 2,
                borderColor: '#111827'
            }]
        }, {
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#E5E7EB', font: { family: 'Outfit', size: 11 } }
                }
            }
        }));
    }
    
    // 3. Gráfico de Status de Viagem
    const ctxStatus = document.getElementById("chart-volumetria-status");
    if (ctxStatus) {
        if (chartVolumetriaStatus) chartVolumetriaStatus.destroy();
        
        const dist = {};
        records.forEach(r => {
            const sv = r.status_viagem || "Outro";
            dist[sv] = (dist[sv] || 0) + 1;
        });
        
        const labels = Object.keys(dist);
        const counts = Object.values(dist);
        
        chartVolumetriaStatus = new Chart(ctxStatus, getChartConfig('doughnut', {
            labels: labels,
            datasets: [{
                data: counts,
                backgroundColor: [
                    '#3B82F6', // Azul
                    '#10B981', // Verde
                    '#F59E0B', // Amarelo
                    '#8B5CF6'  // Roxo
                ],
                borderWidth: 2,
                borderColor: '#111827'
            }]
        }, {
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#E5E7EB', font: { family: 'Outfit', size: 10 } }
                }
            }
        }));
    }
}

// Upload de planilha de volumetria
async function handleVolumetriaUpload(file) {
    const statusBox = document.getElementById("volumetria-upload-status");
    if (statusBox) {
        statusBox.style.display = "block";
        statusBox.style.background = "rgba(59, 130, 246, 0.2)";
        statusBox.style.color = "#60A5FA";
        statusBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processando planilha...`;
    }
    
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const response = await fetch(`${API_BASE}/api/volumetria/upload`, {
            method: "POST",
            body: formData
        });
        
        const res = await response.json();
        
        if (res.success) {
            if (statusBox) {
                statusBox.style.background = "rgba(16, 185, 129, 0.2)";
                statusBox.style.color = "#34D399";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${res.message || "Planilha importada com sucesso!"}`;
            }
            volumetriaData = res.data;
            populateVolumetriaFilters();
            filterAndRenderVolumetria();
            
            setTimeout(() => {
                if (elModalVolumetriaUpload) elModalVolumetriaUpload.style.display = "none";
                if (statusBox) statusBox.style.display = "none";
            }, 1200);
        } else {
            if (statusBox) {
                statusBox.style.background = "rgba(239, 68, 68, 0.2)";
                statusBox.style.color = "#F87171";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${res.error || "Erro ao processar planilha."}`;
            }
        }
    } catch (err) {
        console.error("Erro no upload de volumetria:", err);
        if (statusBox) {
            statusBox.style.background = "rgba(239, 68, 68, 0.2)";
            statusBox.style.color = "#F87171";
            statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Falha na comunicação com o servidor.`;
        }
    }
}

// Copia resumo da Volumetria Diária formatado para WhatsApp/Mensagens
function copyVolumetriaSummary() {
    if (!volumetriaData) return;
    
    const k = volumetriaData.kpis || {};
    const refDate = volumetriaData.data_referencia || new Date().toLocaleDateString("pt-BR");
    const records = volumetriaData.records || [];
    
    let text = `*📊 CONTROLE DE VOLUMETRIA DIÁRIA - DC BAURU*\n`;
    text += `📅 Data: ${refDate}\n\n`;
    
    text += `*1. INDICADORES DO PISO*\n`;
    text += `📥 Previsto (Sistema): ${(k.previsto || 0).toLocaleString("pt-BR")}\n`;
    text += `📦 Bipados (Piso): ${(k.bipados || 0).toLocaleString("pt-BR")}\n`;
    text += `🚚 Coletas: ${(k.coletas || 0).toLocaleString("pt-BR")}\n`;
    text += `🏢 *Total no Piso:* ${(k.total_no_piso || 0).toLocaleString("pt-BR")}\n`;
    text += `⚡ Eficiência / Aderência: ${(k.eficiencia || 100).toFixed(1)}%\n\n`;
    
    text += `*2. DETALHAMENTO DE VIAGENS (${records.length})*\n`;
    records.forEach(r => {
        text += `▫️ *${r.id_transporte}* (${r.pdd_saida}): ${(r.bipado || 0).toLocaleString("pt-BR")} bipados | Pedido: ${(r.pedido_sistema || 0).toLocaleString("pt-BR")} | [${r.status || 'FINALIZADO'}]\n`;
    });
    
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById("btn-volumetria-copy-summary");
        if (btn) {
            const orig = btn.innerHTML;
            btn.innerHTML = `<i class="fa-solid fa-check"></i> Copiado!`;
            btn.style.background = "#10B981";
            setTimeout(() => {
                btn.innerHTML = orig;
                btn.style.background = "";
            }, 2000);
        }
    }).catch(err => {
        console.error("Erro ao copiar texto:", err);
    });
}


// ====================================================
// FUNÇÕES DA VISÃO RANKING & PRODUTIVIDADE HORA A HORA
// ====================================================

// Carrega os dados brutos da API de Ranking
async function loadRankingData() {
    try {
        const tbody = document.getElementById("table-ranking-body");
        const tbodyH = document.getElementById("table-ranking-horas-body");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando dados de ranking...</td></tr>`;
        }
        if (tbodyH) {
            tbodyH.innerHTML = `<tr><td colspan="27" style="text-align: center; padding: 20px;"><i class="fa-solid fa-spinner fa-spin"></i> Carregando matriz hora a hora...</td></tr>`;
        }
        
        // Garante sincronização de coletas com a Volumetria Diária
        if (!volumetriaData) {
            try {
                const volResp = await fetch(`${API_BASE}/api/volumetria/data?_=${Date.now()}`);
                if (volResp.ok) {
                    volumetriaData = await volResp.json();
                }
            } catch (e) {
                console.warn("Aviso ao carregar volumetria para ranking:", e);
            }
        }

        // Garante carregamento do Backlog do Fechamento (DC Bauru)
        if (!controleDataCached) {
            try {
                const ctrlResp = await fetch(`${API_BASE}/api/controle/data?_=${Date.now()}`);
                if (ctrlResp.ok) {
                    controleDataCached = await ctrlResp.json();
                }
            } catch (e) {
                console.warn("Aviso ao carregar controle para ranking:", e);
            }
        }

        const response = await fetch(`${API_BASE}/api/ranking/data?_=${Date.now()}`);
        if (!response.ok) throw new Error("Erro na requisição da API de ranking.");
        
        rankingData = await response.json();
        
        filterAndRenderRanking();
    } catch (err) {
        console.error("Erro ao carregar dados de ranking:", err);
        const tbody = document.getElementById("table-ranking-body");
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--danger); padding: 20px;">Erro ao carregar ranking de operadores.</td></tr>`;
        }
    }
}

// Aplica filtros e renderiza o dashboard de Ranking e Matriz Hora a Hora
function filterAndRenderRanking() {
    if (!rankingData) return;
    
    const setorFilter = document.getElementById("filter-ranking-setor")?.value || "Todos";
    const turnoFilter = document.getElementById("filter-ranking-turno")?.value || "Todos";
    const searchQuery = (document.getElementById("ranking-table-search")?.value || "").trim().toLowerCase();
    
    let ops = rankingData.operadores || [];
    
    // Filtro de Setor
    if (setorFilter !== "Todos") {
        ops = ops.filter(o => o.setor === setorFilter);
    }
    
    // Filtro de Turno (T1: 06-13h, T2: 14-21h, T3: 22-05h)
    if (turnoFilter !== "Todos") {
        ops = ops.filter(o => {
            const hMap = o.horas || {};
            if (turnoFilter === "T1") {
                const bT1 = [6,7,8,9,10,11,12,13].reduce((acc, h) => acc + (hMap[strH(h)] || 0), 0);
                return bT1 > 0;
            } else if (turnoFilter === "T2") {
                const bT2 = [14,15,16,17,18,19,20,21].reduce((acc, h) => acc + (hMap[strH(h)] || 0), 0);
                return bT2 > 0;
            } else if (turnoFilter === "T3") {
                const bT3 = [22,23,0,1,2,3,4,5].reduce((acc, h) => acc + (hMap[strH(h)] || 0), 0);
                return bT3 > 0;
            }
            return true;
        });
    }
    
    function strH(h) {
        return String(h).padStart(2, '0');
    }
    
    // Filtro de Busca por Nome
    if (searchQuery) {
        ops = ops.filter(o => (o.operador || "").toLowerCase().includes(searchQuery));
    }
    
    rankingFilteredOperadores = ops;
    
    // 1. Atualiza Data de Referência
    const elDataRef = document.getElementById("ranking-data-ref");
    if (elDataRef) elDataRef.textContent = rankingData.data_referencia || "--/--/----";
    
    // 2. Extrai ou calcula totais hora a hora e por setor do Ranking
    const turnHours = ['13','14','15','16','17','18','19','20','21','22','23','00','01','02','03','04','05','06'];
    const horaObj = rankingData.hora_a_hora || {};
    const mapColetaH = horaObj.coleta || {};
    const mapExpH = horaObj.expedicao || {};
    const mapLoteH = horaObj.lote || {};
    
    let sumColetaTurno = 0;
    let sumExpTurno = 0;
    let sumLoteTurno = 0;
    let sumTotalTurno = 0;
    
    turnHours.forEach(h => {
        const vColeta = Number(mapColetaH[h]) || 0;
        const vExp = Number(mapExpH[h]) || 0;
        const vLote = Number(mapLoteH[h]) || 0;
        const vTot = vColeta + vExp + vLote;
        
        sumColetaTurno += vColeta;
        sumExpTurno += vExp;
        sumLoteTurno += vLote;
        sumTotalTurno += vTot;
    });

    const totColeta = sumColetaTurno > 0 ? sumColetaTurno : ops.reduce((acc, o) => acc + (Number(o.bipes_coleta) || 0), 0);
    const totLote = sumLoteTurno > 0 ? sumLoteTurno : ops.reduce((acc, o) => acc + (Number(o.bipes_lote) || 0), 0);
    const totExp = sumExpTurno > 0 ? sumExpTurno : ops.reduce((acc, o) => acc + (Number(o.bipes_expedicao) || 0), 0);
    const totBipesGeral = totColeta + totLote + totExp || ops.reduce((acc, o) => acc + (Number(o.total_bipes) || 0), 0);
    
    // Bipado: EXATAMENTE o volume total da coluna de Coleta de Chegada do ranking
    let bipadoVal = totColeta;
    
    // Previsto: obtém diretamente da Volumetria Diária (ou dos KPIs sincronizados)
    let previstoVal = 0;
    if (volumetriaData) {
        if (volumetriaData.kpis && volumetriaData.kpis.previsto !== undefined && volumetriaData.kpis.previsto !== null) {
            previstoVal = Number(volumetriaData.kpis.previsto);
        } else if (volumetriaData.records && volumetriaData.records.length > 0) {
            previstoVal = volumetriaData.records.reduce((acc, r) => acc + (Number(r.pedido_sistema) || 0), 0);
        }
    }
    if (!previstoVal && rankingData.kpis && rankingData.kpis.previsto) {
        previstoVal = Number(rankingData.kpis.previsto);
    }
    if (!previstoVal || isNaN(previstoVal) || previstoVal <= 0) {
        previstoVal = 27262;
    }
    
    // Coletas: obtém diretamente da Volumetria Diária
    let coletasVal = (volumetriaData && volumetriaData.coletas !== undefined && volumetriaData.coletas !== null) 
        ? Number(volumetriaData.coletas) 
        : (volumetriaData?.kpis?.coletas !== undefined && volumetriaData?.kpis?.coletas !== null) 
            ? Number(volumetriaData.kpis.coletas) 
            : (rankingData.kpis?.coletas !== undefined && rankingData.kpis?.coletas !== null)
                ? Number(rankingData.kpis.coletas)
                : 10790;
                
    // 3. Renderiza os 3 Cards de Topo
    const elPrevisto = document.getElementById("val-ranking-previsto");
    const elBipado = document.getElementById("val-ranking-bipado");
    const elColetas = document.getElementById("val-ranking-coletas");
    
    if (elPrevisto) elPrevisto.textContent = previstoVal.toLocaleString("pt-BR");
    if (elBipado) elBipado.textContent = bipadoVal.toLocaleString("pt-BR");
    if (elColetas) elColetas.textContent = coletasVal.toLocaleString("pt-BR");
    
    // Configura Botão de Edição do Previsto (sincronizado com a Volumetria Diária)
    const btnEditPrevisto = document.getElementById("btn-edit-ranking-previsto");
    if (btnEditPrevisto && !btnEditPrevisto.dataset.bound) {
        btnEditPrevisto.dataset.bound = "true";
        btnEditPrevisto.addEventListener("click", async () => {
            const cur = (volumetriaData?.kpis?.previsto) || (rankingData.kpis ? rankingData.kpis.previsto : previstoVal) || 27262;
            const inputVal = prompt("Informe o novo volume Previsto para o fechamento:", cur);
            if (inputVal !== null && inputVal.trim() !== "") {
                const parsed = parseInt(inputVal.replace(/\D/g, ""), 10);
                if (!isNaN(parsed) && parsed >= 0) {
                    if (!rankingData.kpis) rankingData.kpis = {};
                    rankingData.kpis.previsto = parsed;

                    // Atualiza e persiste também na Volumetria Diária
                    if (volumetriaData) {
                        if (!volumetriaData.kpis) volumetriaData.kpis = {};
                        volumetriaData.kpis.previsto = parsed;
                        filterAndRenderVolumetria();
                        await saveVolumetriaChanges();
                    }

                    filterAndRenderRanking();
                    await saveRankingChanges();
                }
            }
        });
    }

    // Configura Botão de Edição das Coletas
    const btnEditColetas = document.getElementById("btn-edit-ranking-coletas");
    if (btnEditColetas && !btnEditColetas.dataset.bound) {
        btnEditColetas.dataset.bound = "true";
        btnEditColetas.addEventListener("click", async () => {
            const cur = (volumetriaData && volumetriaData.coletas !== undefined) ? volumetriaData.coletas : (rankingData.kpis?.coletas || 10790);
            const inputVal = prompt("Informe o novo volume de Coletas:", cur);
            if (inputVal !== null && inputVal.trim() !== "") {
                const parsed = parseInt(inputVal.replace(/\D/g, ""), 10);
                if (!isNaN(parsed) && parsed >= 0) {
                    if (!rankingData.kpis) rankingData.kpis = {};
                    rankingData.kpis.coletas = parsed;

                    // Atualiza e persiste também na Volumetria Diária
                    if (volumetriaData) {
                        volumetriaData.coletas = parsed;
                        if (!volumetriaData.kpis) volumetriaData.kpis = {};
                        volumetriaData.kpis.coletas = parsed;
                        filterAndRenderVolumetria();
                        await saveVolumetriaChanges();
                    }
                    
                    filterAndRenderRanking();
                    await saveRankingChanges();
                }
            }
        });
    }

    
    // 4. Constrói e Renderiza Tabela 1: Geral Hora a Hora
    const tbodyGeral = document.getElementById("table-ranking-geral-hora-body");
    const tfootGeral = document.getElementById("table-ranking-geral-hora-footer");
    
    if (tbodyGeral) {
        tbodyGeral.innerHTML = "";
        
        if (sumTotalTurno === 0) {
            tbodyGeral.innerHTML = `
                <tr>
                    <td colspan="4" style="text-align: center; padding: 22px 14px; color: #9CA3AF;">
                        <i class="fa-solid fa-inbox" style="font-size: 22px; margin-bottom: 6px; display: block; opacity: 0.5;"></i>
                        Nenhum volume digitalizado no turno atual (16h00 às 07h00).<br>
                        <span style="font-size: 11px; opacity: 0.8;">Faça o upload da planilha do B.I para visualizar o hora a hora e ranking.</span>
                    </td>
                </tr>
            `;
        } else {
            tbodyGeral.innerHTML = turnHours.map(h => {
                const vColeta = Number(mapColetaH[h]) || 0;
                const vLote = Number(mapLoteH[h]) || 0;
                const vExp = Number(mapExpH[h]) || 0;
                return `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 6px 12px; text-align: center; font-weight: 700; color: #FFFFFF; background: rgba(30, 58, 138, 0.25); border: 1px solid rgba(255,255,255,0.06); font-family: monospace; font-size: 12px;">${h}:00</td>
                        <td style="padding: 6px 12px; text-align: right; color: ${vColeta > 0 ? '#93C5FD' : '#6B7280'}; font-weight: ${vColeta > 0 ? '700' : '400'}; border: 1px solid rgba(255,255,255,0.06);">${vColeta.toLocaleString("pt-BR")}</td>
                        <td style="padding: 6px 12px; text-align: right; color: ${vLote > 0 ? '#FDE68A' : '#6B7280'}; font-weight: ${vLote > 0 ? '700' : '400'}; border: 1px solid rgba(255,255,255,0.06);">${vLote.toLocaleString("pt-BR")}</td>
                        <td style="padding: 6px 12px; text-align: right; color: ${vExp > 0 ? '#C4B5FD' : '#6B7280'}; font-weight: ${vExp > 0 ? '700' : '400'}; border: 1px solid rgba(255,255,255,0.06);">${vExp.toLocaleString("pt-BR")}</td>
                    </tr>
                `;
            }).join("");
        }
    }
    
    if (tfootGeral) {
        tfootGeral.innerHTML = `
            <tr style="background: #1E3A8A; color: #FFFFFF; font-weight: 800;">
                <td style="padding: 8px 12px; text-align: center; border: 1px solid rgba(255,255,255,0.15); font-weight: 800;">TOTAL</td>
                <td style="padding: 8px 12px; text-align: right; border: 1px solid rgba(255,255,255,0.15); color: #93C5FD; font-size: 13px;">${sumColetaTurno.toLocaleString("pt-BR")}</td>
                <td style="padding: 8px 12px; text-align: right; border: 1px solid rgba(255,255,255,0.15); color: #FDE68A; font-size: 13px;">${sumLoteTurno.toLocaleString("pt-BR")}</td>
                <td style="padding: 8px 12px; text-align: right; border: 1px solid rgba(255,255,255,0.15); color: #C4B5FD; font-size: 13px;">${sumExpTurno.toLocaleString("pt-BR")}</td>
            </tr>
        `;
    }
    
    // 5. Renderiza Seção 2: Rankings por Setor (3 Tabelas Lado a Lado - TOP 10)
    
    // A) Coleta de Chegada (Top 10)
    const opsColetaAll = ops
        .filter(o => (Number(o.bipes_coleta) > 0) || (o.setor === 'Coleta de Chegadas'))
        .map(o => ({ ...o, qtd_setor: Number(o.bipes_coleta) > 0 ? Number(o.bipes_coleta) : Number(o.total_bipes) || 0 }))
        .filter(o => o.qtd_setor > 0)
        .sort((a, b) => b.qtd_setor - a.qtd_setor);
    const opsColeta = opsColetaAll.slice(0, 10);
        
    const elBadgeColeta = document.getElementById("badge-total-op-coleta");
    if (elBadgeColeta) elBadgeColeta.textContent = `Top 10 (${opsColetaAll.length} total)`;
    
    const tbodyColeta = document.getElementById("table-ranking-sector-coleta-body");
    if (tbodyColeta) {
        if (opsColeta.length === 0) {
            tbodyColeta.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 14px; color: #9CA3AF;">Nenhum registro para Coleta.</td></tr>`;
        } else {
            tbodyColeta.innerHTML = opsColeta.map((op, idx) => {
                const pos = idx + 1;
                let posHtml = `<span style="font-weight: 700; color: #9CA3AF;">${pos}</span>`;
                if (pos === 1) posHtml = `<span style="font-size: 13px;">🥇 1</span>`;
                else if (pos === 2) posHtml = `<span style="font-size: 13px;">🥈 2</span>`;
                else if (pos === 3) posHtml = `<span style="font-size: 13px;">🥉 3</span>`;
                return `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 4px 6px; text-align: center; border: 1px solid rgba(255,255,255,0.05);">${posHtml}</td>
                        <td style="padding: 4px 8px; border: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #FFFFFF; font-size: 11px;">${op.operador || "-"}</td>
                        <td style="padding: 4px 8px; text-align: right; border: 1px solid rgba(255,255,255,0.05); font-weight: 700; color: #93C5FD; font-size: 11.5px;">${op.qtd_setor.toLocaleString("pt-BR")}</td>
                    </tr>
                `;
            }).join("");
        }
    }
    
    // B) Expedição (Top 10)
    const opsExpAll = ops
        .filter(o => (Number(o.bipes_expedicao) > 0) || (o.setor === 'Expedição'))
        .map(o => ({ ...o, qtd_setor: Number(o.bipes_expedicao) > 0 ? Number(o.bipes_expedicao) : Number(o.total_bipes) || 0 }))
        .filter(o => o.qtd_setor > 0)
        .sort((a, b) => b.qtd_setor - a.qtd_setor);
    const opsExp = opsExpAll.slice(0, 10);
        
    const elBadgeExp = document.getElementById("badge-total-op-exp");
    if (elBadgeExp) elBadgeExp.textContent = `Top 10 (${opsExpAll.length} total)`;
    
    const tbodyExp = document.getElementById("table-ranking-sector-exp-body");
    if (tbodyExp) {
        if (opsExp.length === 0) {
            tbodyExp.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 14px; color: #9CA3AF;">Nenhum registro para Expedição.</td></tr>`;
        } else {
            tbodyExp.innerHTML = opsExp.map((op, idx) => {
                const pos = idx + 1;
                let posHtml = `<span style="font-weight: 700; color: #9CA3AF;">${pos}</span>`;
                if (pos === 1) posHtml = `<span style="font-size: 13px;">🥇 1</span>`;
                else if (pos === 2) posHtml = `<span style="font-size: 13px;">🥈 2</span>`;
                else if (pos === 3) posHtml = `<span style="font-size: 13px;">🥉 3</span>`;
                return `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 4px 6px; text-align: center; border: 1px solid rgba(255,255,255,0.05);">${posHtml}</td>
                        <td style="padding: 4px 8px; border: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #FFFFFF; font-size: 11px;">${op.operador || "-"}</td>
                        <td style="padding: 4px 8px; text-align: right; border: 1px solid rgba(255,255,255,0.05); font-weight: 700; color: #C4B5FD; font-size: 11.5px;">${op.qtd_setor.toLocaleString("pt-BR")}</td>
                    </tr>
                `;
            }).join("");
        }
    }
    
    // C) Criação de Lote (Top 10)
    const opsLoteAll = ops
        .filter(o => (Number(o.bipes_lote) > 0) || (o.setor === 'Inserido em Lote'))
        .map(o => ({ ...o, qtd_setor: Number(o.bipes_lote) > 0 ? Number(o.bipes_lote) : Number(o.total_bipes) || 0 }))
        .filter(o => o.qtd_setor > 0)
        .sort((a, b) => b.qtd_setor - a.qtd_setor);
    const opsLote = opsLoteAll.slice(0, 10);
        
    const elBadgeLote = document.getElementById("badge-total-op-lote");
    if (elBadgeLote) elBadgeLote.textContent = `Top 10 (${opsLoteAll.length} total)`;
    
    const tbodyLote = document.getElementById("table-ranking-sector-lote-body");
    if (tbodyLote) {
        if (opsLote.length === 0) {
            tbodyLote.innerHTML = `<tr><td colspan="3" style="text-align: center; padding: 14px; color: #9CA3AF;">Nenhum registro para Criação de Lote.</td></tr>`;
        } else {
            tbodyLote.innerHTML = opsLote.map((op, idx) => {
                const pos = idx + 1;
                let posHtml = `<span style="font-weight: 700; color: #9CA3AF;">${pos}</span>`;
                if (pos === 1) posHtml = `<span style="font-size: 13px;">🥇 1</span>`;
                else if (pos === 2) posHtml = `<span style="font-size: 13px;">🥈 2</span>`;
                else if (pos === 3) posHtml = `<span style="font-size: 13px;">🥉 3</span>`;
                return `
                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.05);">
                        <td style="padding: 4px 6px; text-align: center; border: 1px solid rgba(255,255,255,0.05);">${posHtml}</td>
                        <td style="padding: 4px 8px; border: 1px solid rgba(255,255,255,0.05); font-weight: 600; color: #FFFFFF; font-size: 11px;">${op.operador || "-"}</td>
                        <td style="padding: 4px 8px; text-align: right; border: 1px solid rgba(255,255,255,0.05); font-weight: 700; color: #FDE68A; font-size: 11.5px;">${op.qtd_setor.toLocaleString("pt-BR")}</td>
                    </tr>
                `;
            }).join("");
        }
    }
    
    // 6. Renderiza Gráficos
    renderRankingCharts(ops, turnHours, mapColetaH, mapExpH, mapLoteH, sumColetaTurno, sumLoteTurno, sumExpTurno);
}

// Renderiza os gráficos do módulo Ranking
function renderRankingCharts(ops, turnHours, mapColetaH, mapExpH, mapLoteH, totColeta, totLote, totExp) {
    // 1. Gráfico Curva Hora a Hora
    const ctxHora = document.getElementById("chart-ranking-hora");
    if (ctxHora) {
        if (chartRankingHora) chartRankingHora.destroy();
        
        const labels = turnHours.map(h => `${h}:00`);
        const dataColeta = turnHours.map(h => Number(mapColetaH[h]) || 0);
        const dataExp = turnHours.map(h => Number(mapExpH[h]) || 0);
        const dataLote = turnHours.map(h => Number(mapLoteH[h]) || 0);
        const dataTotal = turnHours.map(h => (Number(mapColetaH[h]) || 0) + (Number(mapExpH[h]) || 0) + (Number(mapLoteH[h]) || 0));
        
        chartRankingHora = new Chart(ctxHora, getChartConfig('line', {
            labels: labels,
            datasets: [
                {
                    label: 'Total Geral',
                    data: dataTotal,
                    borderColor: '#10B981',
                    backgroundColor: 'rgba(16, 185, 129, 0.15)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.35,
                    pointRadius: 4,
                    pointHoverRadius: 6
                },
                {
                    label: 'Coleta de Chegada',
                    data: dataColeta,
                    borderColor: '#3B82F6',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 3
                },
                {
                    label: 'Criação de Lote',
                    data: dataLote,
                    borderColor: '#F59E0B',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 3
                },
                {
                    label: 'Expedição',
                    data: dataExp,
                    borderColor: '#8B5CF6',
                    backgroundColor: 'transparent',
                    borderWidth: 2,
                    tension: 0.35,
                    pointRadius: 3
                }
            ]
        }, {
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(255, 255, 255, 0.05)' },
                    ticks: { color: '#9CA3AF' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#9CA3AF', maxRotation: 0 }
                }
            },
            plugins: {
                legend: {
                    position: 'top',
                    labels: { color: '#E5E7EB', font: { family: 'Outfit', size: 11 } }
                }
            }
        }));
    }
    
    // 2. Gráfico Bipes por Setor (Rosca)
    const ctxSetores = document.getElementById("chart-ranking-setores");
    if (ctxSetores) {
        if (chartRankingSetores) chartRankingSetores.destroy();
        
        chartRankingSetores = new Chart(ctxSetores, getChartConfig('doughnut', {
            labels: ['Coleta de Chegada', 'Criação de Lote', 'Expedição'],
            datasets: [{
                data: [totColeta, totLote, totExp],
                backgroundColor: ['#3B82F6', '#F59E0B', '#8B5CF6'],
                borderWidth: 2,
                borderColor: '#111827'
            }]
        }, {
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#E5E7EB', font: { family: 'Outfit', size: 11 } }
                }
            }
        }));
    }
}

// Salva alterações de Ranking no servidor
async function saveRankingChanges() {
    if (!rankingData) return;
    const elStatus = document.getElementById("ranking-save-status");
    if (elStatus) {
        elStatus.style.display = "inline-flex";
        elStatus.style.background = "rgba(245, 158, 11, 0.2)";
        elStatus.style.color = "#FBBF24";
        elStatus.style.opacity = "1";
        elStatus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Salvando...';
    }
    
    try {
        const resp = await fetch(`${API_BASE}/api/ranking/save`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(rankingData)
        });
        if (resp.ok) {
            if (elStatus) {
                elStatus.style.background = "rgba(16, 185, 129, 0.2)";
                elStatus.style.color = "#34D399";
                elStatus.innerHTML = '<i class="fa-solid fa-check"></i> Salvo com sucesso!';
                setTimeout(() => { elStatus.style.opacity = "0"; }, 2000);
            }
        }
    } catch (err) {
        console.error("Erro ao salvar dados de ranking:", err);
    }
}

// Realiza o Upload e Processamento de Planilha(s) de Digitalização / Bipes
async function handleRankingUpload(filesOrFile, sector = null) {
    const statusBox = document.getElementById("ranking-upload-status");
    let files = [];
    if (filesOrFile instanceof FileList || Array.isArray(filesOrFile)) {
        files = Array.from(filesOrFile);
    } else if (filesOrFile instanceof File) {
        files = [filesOrFile];
    }
    
    if (files.length === 0) return;
    
    if (statusBox) {
        statusBox.style.display = "block";
        statusBox.style.background = "rgba(59, 130, 246, 0.2)";
        statusBox.style.color = "#60A5FA";
        const fileNames = files.map(f => f.name).join(", ");
        statusBox.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Processando ${files.length} arquivo(s) (${fileNames})... Aguarde!`;
    }
    
    const formData = new FormData();
    files.forEach(f => {
        formData.append("files", f);
    });
    if (sector) {
        formData.append("sector", sector);
    }
    
    try {
        const response = await fetch(`${API_BASE}/api/ranking/upload`, {
            method: "POST",
            body: formData
        });
        
        let res;
        try {
            const rawText = await response.text();
            try {
                res = JSON.parse(rawText);
            } catch (jsonErr) {
                res = { success: false, error: `Resposta inválida do servidor (${response.status}): ${rawText.slice(0, 150)}` };
            }
        } catch (readErr) {
            res = { success: false, error: `Erro ao ler resposta: ${readErr.message}` };
        }
        
        if (res && res.success) {
            if (statusBox) {
                statusBox.style.background = "rgba(16, 185, 129, 0.2)";
                statusBox.style.color = "#34D399";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-check"></i> ${res.message || "Planilhas processadas com sucesso!"}`;
            }
            rankingData = res.data;
            filterAndRenderRanking();
            
            setTimeout(() => {
                const modal = document.getElementById("modal-ranking-upload");
                if (modal) modal.style.display = "none";
                if (statusBox) statusBox.style.display = "none";
            }, 1800);
        } else {
            if (statusBox) {
                statusBox.style.background = "rgba(239, 68, 68, 0.2)";
                statusBox.style.color = "#F87171";
                statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> ${res.error || "Erro ao processar planilhas."}`;
            }
        }
    } catch (err) {
        console.error("Erro no upload de ranking:", err);
        if (statusBox) {
            statusBox.style.background = "rgba(239, 68, 68, 0.2)";
            statusBox.style.color = "#F87171";
            statusBox.innerHTML = `<i class="fa-solid fa-circle-xmark"></i> Falha na comunicação com o servidor (${err.message}). Verifique se o servidor Python (run.bat) está em execução.`;
        }
    }
}



// ==============================================================================
// GESTÃO DO REPORT DE INÍCIO DA OPERAÇÃO (100% NO BANCO DE DADOS)
// ==============================================================================
function formatReportInicioText(r) {
    if (r.raw_text && r.raw_text.trim().length > 30) {
        return r.raw_text;
    }
    let dataVal = r.data_ref || "*06/10/2026*";
    if (!dataVal.startsWith("*") && !dataVal.endsWith("*")) {
        dataVal = `*${dataVal}*`;
    }

    const clt22 = r.clts_presentes_22h || r.clts_presentes_23h || '—';
    const abs22 = r.absenteismo_22h || r.absenteismo_23h || '—';

    return `📊 REPORT DE INÍCIO DA OPERAÇÃO

📅 Data: ${dataVal}

📦 Backlog Inicial: ${r.backlog_inicial || '692'}
📦 Volume previsto: ${r.volume_previsto || '53.903'}
🕒 Início da operação: ${r.inicio_operacao || '15:11'}
👥 CLTs presentes 18hrs: ${r.clts_presentes_18h || '32'}
❌ Absenteísmo 18hrs: ${r.absenteismo_18h || '4'}
👥 CLTs presentes 22hrs: ${clt22}
❌ Absenteísmo 22hrs: ${abs22}
👷 Diaristas solicitados (15:00): ${r.diaristas_solicitados_15h || '20'}
✅ Diaristas presentes (15:00): ${r.diaristas_presentes_15h || '18'}
👷 Diaristas solicitados (20:00): ${r.diaristas_solicitados_20h || '10'}
✅ Diaristas presentes (20:00): ${r.diaristas_presentes_20h || '—'}
📈 PHD previsto: ${r.phd_previsto || '—'}


📝 Observações:

- Falta injustificada: ${r.obs_falta_injustificada || '4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA'}

- Atestados: ${r.obs_atestados || 'N/A'}

- Pontos de atenção: ${r.obs_pontos_atencao || 'N/A'}`;
}

let reportInicioCurrentData = {
    data_ref: "*06/10/2026*",
    inicio_operacao: "15:11",
    backlog_inicial: "692",
    volume_previsto: "53.903",
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
    raw_text: ""
};

function updateReportInicioUI(data) {
    if (data) {
        reportInicioCurrentData = { ...reportInicioCurrentData, ...data };
    }
    const r = reportInicioCurrentData;
    const cleanData = (r.data_ref || '06/10/2026').replace(/\*/g, '');

    // 1. Cards de Destaque / KPIs
    const cData = document.getElementById("rep-kpi-data");
    if (cData) cData.innerText = `${cleanData} (${r.inicio_operacao || '15:11'})`;

    const cVol = document.getElementById("rep-kpi-volume");
    if (cVol) cVol.innerText = `${r.backlog_inicial || '692'} / ${r.volume_previsto || '53.903'}`;

    const cClt = document.getElementById("rep-kpi-clt");
    const clt22Val = r.clts_presentes_22h || r.clts_presentes_23h || '—';
    if (cClt) cClt.innerText = `${r.clts_presentes_18h || '32'} (18h) | ${clt22Val} (22h)`;

    const cDia = document.getElementById("rep-kpi-diaristas");
    const dia20Sol = r.diaristas_solicitados_20h || '10';
    const dia20Pres = r.diaristas_presentes_20h || '—';
    if (cDia) cDia.innerText = `${r.diaristas_presentes_15h || '18'}/${r.diaristas_solicitados_15h || '20'} (15h) | ${dia20Pres}/${dia20Sol} (20h)`;

    // 2. Formulário Principal do Painel
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = val || ''; };
    setVal("panel-rep-data", r.data_ref || '*06/10/2026*');
    setVal("panel-rep-inicio", r.inicio_operacao || '15:11');
    setVal("panel-rep-backlog", r.backlog_inicial || '692');
    setVal("panel-rep-volume", r.volume_previsto || '53.903');
    setVal("panel-rep-clt18", r.clts_presentes_18h || '32');
    setVal("panel-rep-abs18", r.absenteismo_18h || '4');
    setVal("panel-rep-clt22", clt22Val);
    setVal("panel-rep-abs22", r.absenteismo_22h || r.absenteismo_23h || '—');
    setVal("panel-rep-diasol15", r.diaristas_solicitados_15h || '20');
    setVal("panel-rep-diapres15", r.diaristas_presentes_15h || '18');
    setVal("panel-rep-diasol20", dia20Sol);
    setVal("panel-rep-diapres20", dia20Pres);
    setVal("panel-rep-phd", r.phd_previsto || '—');
    setVal("panel-rep-falta", r.obs_falta_injustificada || '4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA');
    setVal("panel-rep-atestados", r.obs_atestados || 'N/A');
    setVal("panel-rep-atencao", r.obs_pontos_atencao || 'N/A');

    // 3. Textarea WhatsApp Preview
    const txtPreview = document.getElementById("panel-rep-preview-text");
    if (txtPreview) {
        txtPreview.value = formatReportInicioText(r);
    }
}

async function loadReportInicioData() {
    try {
        const res = await fetch(`${API_BASE}/api/pda/report_inicio?_=${Date.now()}`);
        if (res.ok) {
            const data = await res.json();
            const reportObj = data.report || data;
            if (reportObj && Object.keys(reportObj).length > 0) {
                updateReportInicioUI(reportObj);
            }
        }
    } catch (e) {
        console.error("Erro ao carregar report_inicio:", e);
    }
}

async function saveReportInicioData() {
    const getVal = (id) => (document.getElementById(id)?.value || '').trim();
    const feedback = document.getElementById("panel-rep-feedback");

    const updated = {
        data_ref: getVal("panel-rep-data") || '*06/10/2026*',
        inicio_operacao: getVal("panel-rep-inicio") || '15:11',
        backlog_inicial: getVal("panel-rep-backlog") || '692',
        volume_previsto: getVal("panel-rep-volume") || '53.903',
        clts_presentes_18h: getVal("panel-rep-clt18") || '32',
        absenteismo_18h: getVal("panel-rep-abs18") || '4',
        clts_presentes_22h: getVal("panel-rep-clt22") || '—',
        absenteismo_22h: getVal("panel-rep-abs22") || '—',
        diaristas_solicitados_15h: getVal("panel-rep-diasol15") || '20',
        diaristas_presentes_15h: getVal("panel-rep-diapres15") || '18',
        diaristas_solicitados_20h: getVal("panel-rep-diasol20") || '10',
        diaristas_presentes_20h: getVal("panel-rep-diapres20") || '—',
        phd_previsto: getVal("panel-rep-phd") || '—',
        obs_falta_injustificada: getVal("panel-rep-falta") || '4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA',
        obs_atestados: getVal("panel-rep-atestados") || 'N/A',
        obs_pontos_atencao: getVal("panel-rep-atencao") || 'N/A',
        raw_text: ''
    };

    try {
        const res = await fetch(`${API_BASE}/api/pda/report_inicio`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });
        if (res.ok) {
            updateReportInicioUI(updated);
            if (feedback) {
                feedback.style.display = "block";
                feedback.style.background = "rgba(16, 185, 129, 0.2)";
                feedback.style.color = "#34D399";
                feedback.style.border = "1px solid rgba(16, 185, 129, 0.4)";
                feedback.innerHTML = '<i class="fa-solid fa-circle-check"></i> Salvo com sucesso no Banco de Dados!';
                setTimeout(() => { feedback.style.display = "none"; }, 3500);
            }
        }
    } catch (err) {
        console.error("Erro ao salvar report de início:", err);
        if (feedback) {
            feedback.style.display = "block";
            feedback.style.background = "rgba(239, 68, 68, 0.2)";
            feedback.style.color = "#F87171";
            feedback.style.border = "1px solid rgba(239, 68, 68, 0.4)";
            feedback.innerHTML = '<i class="fa-solid fa-circle-xmark"></i> Erro ao salvar dados no servidor.';
            setTimeout(() => { feedback.style.display = "none"; }, 3500);
        }
    }
}

async function copyReportInicioToClipboard(buttonEl) {
    const text = formatReportInicioText(reportInicioCurrentData);
    const txtPreview = document.getElementById("panel-rep-preview-text");
    try {
        if (navigator.clipboard && navigator.clipboard.writeText) {
            await navigator.clipboard.writeText(text);
        } else if (txtPreview) {
            txtPreview.select();
            document.execCommand("copy");
        }
        if (buttonEl) {
            const originalHtml = buttonEl.innerHTML;
            buttonEl.innerHTML = '<i class="fa-solid fa-check text-emerald-400"></i> Copiado!';
            setTimeout(() => { buttonEl.innerHTML = originalHtml; }, 2000);
        }
    } catch (err) {
        console.error("Erro ao copiar:", err);
    }
}

function initReportInicioManager() {
    const form = document.getElementById("form-report-inicio-panel");
    const btnCopy = document.getElementById("btn-rep-panel-copy");
    const btnCopyTop = document.getElementById("btn-rep-panel-copy-top");
    const btnSidebarCopy = document.getElementById("btn-report-inicio-sidebar-copy");
    const btnSidebarSave = document.getElementById("btn-report-inicio-sidebar-save");
    const btnRefresh = document.getElementById("btn-rep-panel-refresh");
    const btnSidebarRefresh = document.getElementById("btn-report-inicio-sidebar-refresh");

    // Live update of preview while typing
    const formInputs = [
        "panel-rep-data", "panel-rep-inicio", "panel-rep-backlog", "panel-rep-volume",
        "panel-rep-clt18", "panel-rep-abs18", "panel-rep-clt22", "panel-rep-abs22",
        "panel-rep-diasol15", "panel-rep-diapres15", "panel-rep-diasol20", "panel-rep-diapres20", "panel-rep-phd",
        "panel-rep-falta", "panel-rep-atestados", "panel-rep-atencao"
    ];

    formInputs.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.addEventListener("input", () => {
                const getVal = (i) => (document.getElementById(i)?.value || '').trim();
                const temp = {
                    data_ref: getVal("panel-rep-data"),
                    inicio_operacao: getVal("panel-rep-inicio"),
                    backlog_inicial: getVal("panel-rep-backlog"),
                    volume_previsto: getVal("panel-rep-volume"),
                    clts_presentes_18h: getVal("panel-rep-clt18"),
                    absenteismo_18h: getVal("panel-rep-abs18"),
                    clts_presentes_22h: getVal("panel-rep-clt22"),
                    absenteismo_22h: getVal("panel-rep-abs22"),
                    diaristas_solicitados_15h: getVal("panel-rep-diasol15"),
                    diaristas_presentes_15h: getVal("panel-rep-diapres15"),
                    diaristas_solicitados_20h: getVal("panel-rep-diasol20"),
                    diaristas_presentes_20h: getVal("panel-rep-diapres20"),
                    phd_previsto: getVal("panel-rep-phd"),
                    obs_falta_injustificada: getVal("panel-rep-falta"),
                    obs_atestados: getVal("panel-rep-atestados"),
                    obs_pontos_atencao: getVal("panel-rep-atencao"),
                    raw_text: ''
                };
                reportInicioCurrentData = { ...reportInicioCurrentData, ...temp };
                const txtPreview = document.getElementById("panel-rep-preview-text");
                if (txtPreview) txtPreview.value = formatReportInicioText(reportInicioCurrentData);
            });
        }
    });

    if (form) {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            saveReportInicioData();
        });
    }

    if (btnSidebarSave) {
        btnSidebarSave.addEventListener("click", () => {
            saveReportInicioData();
        });
    }

    if (btnCopy) btnCopy.addEventListener("click", () => copyReportInicioToClipboard(btnCopy));
    if (btnCopyTop) btnCopyTop.addEventListener("click", () => copyReportInicioToClipboard(btnCopyTop));
    if (btnSidebarCopy) btnSidebarCopy.addEventListener("click", () => copyReportInicioToClipboard(btnSidebarCopy));

    if (btnRefresh) btnRefresh.addEventListener("click", loadReportInicioData);
    if (btnSidebarRefresh) btnSidebarRefresh.addEventListener("click", loadReportInicioData);

    // Carregamento inicial em segundo plano
    loadReportInicioData();
}



