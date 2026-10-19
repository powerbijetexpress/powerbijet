# Importacao da biblioteca de sistema do Python para lidar com caminhos de arquivos e pastas
import os
import json
import time
import socket
import subprocess
from collections import Counter
# Importacao da biblioteca sys para gerenciar recursos do interpretador Python e codificacao do console
import sys
# Importacao do modulo de fluxo de bytes em memoria io para armazenar o PDF temporariamente
import io
# Importacao do modulo matematico math para operacoes auxiliares (arredondamento, log, etc.)
import math
# Importacao do objeto datetime para capturar e formatar datas e horas do relatorio
from datetime import datetime
# Importacao da biblioteca pandas para manipulacao estruturada de tabelas e dados logisticos
import pandas as pd
# Importacao de classes centrais do Flask para servir paginas, JSON e transferir arquivos gerados
from flask import Flask, jsonify, request, send_file, render_template, send_from_directory, redirect, Response

# Importacao do modulo de Banco de Dados relacional SQLite
import db

# Configura a codificacao do console de saida padrao (stdout) para utf-8, evitando erros de acentos no Windows
sys.stdout.reconfigure(encoding='utf-8')

# Importacao da classe principal de tamanho de pagina A4 e da funcao que rotaciona para paisagem (landscape)
from reportlab.lib.pagesizes import A4, landscape
# Importacao das classes de fluxo de elementos do ReportLab para construir paginas estruturadas de PDF
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether
)
# Importacao das funcoes de estilo padrao do ReportLab para estilizar paragrafos de texto
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
# Importacao do modulo de cores do ReportLab para gerenciar paletas visuais e preenchimentos
from reportlab.lib import colors
# Importacao do objeto de renderizacao de PDF do ReportLab (canvas) para desenhar elementos graficos basicos
from reportlab.pdfgen import canvas
# Importacao das formas geometricas vetoriais basicas para desenhar graficos personalizados no PDF
from reportlab.graphics.shapes import Drawing, Rect, String, Line
# Importacao do componente grafico de Rosca/Pizza (Pie) nativo do ReportLab
from reportlab.graphics.charts.piecharts import Pie
# Importacao do componente grafico de Barras Verticais (VerticalBarChart) nativo do ReportLab
from reportlab.graphics.charts.barcharts import VerticalBarChart
# Importacao do componente grafico de Linhas (LinePlot) nativo do ReportLab
from reportlab.graphics.charts.lineplots import LinePlot

# Inicializacao da aplicacao Flask para gerenciar as rotas do dashboard web local
app = Flask(__name__)
# Permite upload de planilhas pesadas do B.I (até 500 MB)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024

# Controla o tempo da última atualização da planilha de controle em memória
_last_controle_download_time = 0.0

# Controla o tempo da última atualização da planilha de avarias em memória
_last_avaria_download_time = 0.0

# Desativa o cache do navegador para rotas dinamicas e garante headers CORS
@app.after_request
def add_header(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, Accept, X-Requested-With'
    if request.path.startswith('/api/') or request.path.startswith('/pda') or request.path.endswith('.js') or request.path.endswith('.html') or request.path.endswith('.css'):
        response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, post-check=0, pre-check=0, max-age=0'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '-1'
    return response


# Definicao do nome do arquivo Excel contendo as remessas logisticas a serem tratadas
DATA_FILE = "exp nao chegou.xlsx"
CONTROLE_BAU_FILE = "CONTROLE DC BAU.xlsx"

# ====================================================
# INFRAESTRUTURA DE CACHE DE ARQUIVOS E DOWNLOADS ASSÍNCRONOS
# ====================================================
import threading

_memory_cache = {}
_downloading_files = set()

def download_in_background(url, target_path):
    global _downloading_files
    if target_path in _downloading_files:
        return
        
    def worker():
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            temp_path = target_path + ".download"
            with urllib.request.urlopen(req, timeout=30) as response:
                content = response.read()
            if content and len(content) > 1000:
                if os.path.exists(target_path):
                    try:
                        with open(target_path, 'rb') as f_old:
                            if f_old.read() == content:
                                # Conteúdo idêntico: não altera o arquivo para preservar cache em memória
                                return
                    except Exception:
                        pass
                with open(temp_path, 'wb') as f:
                    f.write(content)
                if os.path.exists(temp_path):
                    try:
                        os.replace(temp_path, target_path)
                    except Exception:
                        if os.path.exists(target_path):
                            try:
                                os.remove(target_path)
                            except Exception:
                                pass
                        try:
                            os.rename(temp_path, target_path)
                        except Exception:
                            pass
                    print(f"[CACHE] Download concluído com sucesso em segundo plano para: {target_path}")
        except Exception as e:
            print(f"[CACHE] Erro no download em background para {target_path}: {e}")
        finally:
            _downloading_files.discard(target_path)
            
    _downloading_files.add(target_path)
    t = threading.Thread(target=worker, daemon=True)
    t.start()

def get_from_cache(file_path, parse_fn, *args, **kwargs):
    global _memory_cache
    if not os.path.exists(file_path):
        return parse_fn(*args, **kwargs)
        
    mtime = os.path.getmtime(file_path)
    cache_entry = _memory_cache.get(file_path)
    
    if cache_entry is None or cache_entry['mtime'] != mtime:
        # Se o arquivo não está em cache ou foi atualizado no disco, re-parseia
        data = parse_fn(*args, **kwargs)
        _memory_cache[file_path] = {
            'mtime': mtime,
            'data': data
        }
        return data
        
    return cache_entry['data']


# Dicionario de mapeamento para categorizar os status brutos em grupos executivos menores e faceis de analisar
STATUS_MAP = {
    # Concluidas: Remessas devidamente entregues e assinadas pelo destinatario
    'assinado': 'Concluída',
    # Pendentes: Remessas localizadas fisicamente em trânsito ou aguardando processamento na base
    'recebido na base': 'Pendente',
    # Pendentes: Remessas localizadas na base especifica DC BAU
    'na base DC BAU': 'Pendente',
    # Pendentes: Remessas que deram entrada em alguma base diferente da planejada
    'recebido em outra base': 'Pendente',
    # Criticas: Remessas despachadas que nao deram entrada no destino (atrasadas ou extraviadas)
    'expedido não chegou': 'Crítica',
    # Criticas: Remessas que retornaram ao remetente devido a problemas de entrega
    'Devolução': 'Crítica',
    # Outros status logisticos
    'entregador': 'Pendente',
    'interceptado': 'Crítica',
    'erro triagem': 'Crítica'
}

# Mapeamento dos horários de corte por destino/rota
CUTOFF_MAP = {
    # Cortes 01:30
    'BRE (SOC)': '01:30',
    'PPB': '01:30',
    'PPB (2º Carro)': '01:30',
    'ARU': '01:30',
    'AND': '01:30',
    'OSW': '01:30',
    'PNP': '01:30',
    
    # Cortes 04:00
    'AVR': '04:00',
    'MII': '04:00',
    'PPB-SP': '01:30',
    'MII-SP': '04:00',
    'ARA': '04:00',
    'ARU 02 (484)': '04:00',
    'ARU (2º Carro)': '04:00',
    'OUR': '04:00',
    'ASI': '04:00',
    'BAU': '04:00',
    'JAU': '04:00',
    'BTC': '04:00',
    'IBG': '04:00',
    'LCP': '04:00',
    'BAU 02': '04:00',
    'BAU 03': '04:00',
    'LNS': '04:00',
    'DCN': '04:00',
    'AUR': '04:00',
    'ITAP': '04:00',
    'TPA': '04:00',
    'GRC': '04:00',
    'GNS': '04:00',
    'BRB': '04:00',
    'GRR': '04:00',
    'BGI': '04:00',
    'F MII': '04:00',
    'RAO (SOC)': '04:00'
}

# Funcao de carregamento e higienizacao dos dados logisticos contidos no arquivo do Excel (leitura bruta do disco)
def _load_data_raw():
    # Valida se o arquivo Excel configurado na constante existe no diretorio atual
    if not os.path.exists(DATA_FILE):
        # Retorna um DataFrame vazio caso o arquivo Excel nao seja encontrado para evitar que a app quebre
        return pd.DataFrame()
    
    # Faz a leitura da planilha Excel utilizando o Pandas em memória para evitar travar o arquivo no disco (Windows)
    with open(DATA_FILE, 'rb') as f:
        file_bytes = io.BytesIO(f.read())
    df = pd.read_excel(file_bytes)
    
    # Padroniza os nomes das colunas da tabela para nomenclatura em minusculo e sem caracteres especiais chineses
    df.columns = ['remessa', 'hora_envio', 'estacao_recebimento', 'estacao_registro', 'status']
    
    # Converte a coluna de data de envio para o tipo datetime do Pandas para permitir filtros temporais precisos
    df['hora_envio'] = pd.to_datetime(df['hora_envio'], errors='coerce')
    
    # Remove as linhas do DataFrame onde a data de envio nao pôde ser lida ou esta nula (NaT)
    df = df.dropna(subset=['hora_envio'])
    
    # Ordena as linhas da tabela de forma crescente pela data e hora de envio das remessas
    df = df.sort_values(by='hora_envio')
    
    # Trata as colunas de texto removendo espacos extras no comeco e no fim de cada string
    df['estacao_recebimento'] = df['estacao_recebimento'].astype(str).str.strip()
    # Trata a coluna estacao_registro removendo espacos extras nas pontas
    df['estacao_registro'] = df['estacao_registro'].astype(str).str.strip()
    # Trata a coluna status removendo espacos extras nas pontas
    df['status'] = df['status'].astype(str).str.strip()
    
    # Normalizacao de status operacionais para evitar divergencia de maiusculas/minusculas e erros de digitacao
    def normalize_status(val):
        val_lower = val.lower().strip()
        if 'expedido' in val_lower and 'chegou' in val_lower:
            return 'expedido não chegou'
        if 'expedio' in val_lower and 'chegou' in val_lower:
            return 'expedido não chegou'
        if val_lower == 'assinado':
            return 'assinado'
        if val_lower == 'recebido na base':
            return 'recebido na base'
        if val_lower == 'recebido em outra base':
            return 'recebido em outra base'
        if val_lower == 'na base dc bau':
            return 'na base DC BAU'
        if val_lower in ('devolução', 'devolucao'):
            return 'Devolução'
        if val_lower == 'entregador':
            return 'entregador'
        if val_lower == 'interceptado':
            return 'interceptado'
        if val_lower == 'erro triagem':
            return 'erro triagem'
        return val
        
    df['status'] = df['status'].apply(normalize_status)
    
    # Funcao interna para formatar o codigo de identificacao da remessa, limpando pontos decimais indesejados
    def clean_remessa(val):
        # Tenta converter o valor numerico em inteiro e depois string para evitar exibicao como float (ex: .0)
        try:
            # Converte float para int e depois para string limpa
            return str(int(float(val)))
        # Se falhar (por ser texto), limpa os espacos e retorna o valor original como string
        except:
            # Retorna valor original sem espacos extras
            return str(val).strip()
            
    # Aplica a funcao interna de limpeza a toda a coluna de identificadores das remessas
    df['remessa'] = df['remessa'].apply(clean_remessa)
    
    # Cria uma nova coluna mapeando os status brutos para as categorias executivas (Concluida, Pendente, Critica)
    df['categoria'] = df['status'].map(lambda x: STATUS_MAP.get(x, 'Pendente'))
    
    # Retorna o DataFrame limpo e estruturado para uso nas APIs e relatorio
    return df

# Funcao publica com cache em memoria para evitar leituras repetidas do disco
def load_data():
    return get_from_cache(DATA_FILE, _load_data_raw)

# Funcao para filtrar o DataFrame com base nos parametros de busca enviados pelo frontend
def filter_dataframe(df, filters):
    # Retorna o DataFrame imediatamente se ele estiver vazio, evitando processamentos desnecessarios
    if df.empty:
        # Retorna vazio
        return df
        
    # Obtem a data inicial do filtro a partir dos parametros recebidos
    start_date = filters.get('start_date')
    # Obtem a data final do filtro a partir dos parametros recebidos
    end_date = filters.get('end_date')
    # Obtem a estacao de recebimento selecionada a partir dos parametros
    rec_station = filters.get('receiving_station')
    # Obtem a estacao de registro selecionada a partir dos parametros
    reg_station = filters.get('registering_station')
    # Obtem o status operacional selecionado a partir dos parametros
    status = filters.get('status')
    
    # Faz uma copia local do DataFrame para evitar alteracoes no objeto de cache global
    filtered_df = df.copy()
    
    # Aplica o filtro de data inicial se ele tiver sido fornecido pelo usuario
    if start_date:
        # Mantem registros maiores ou iguais à data inicial convertida
        filtered_df = filtered_df[filtered_df['hora_envio'] >= pd.to_datetime(start_date)]
    # Aplica o filtro de data final se ele tiver sido fornecido pelo usuario
    if end_date:
        # Calcula a data limite somando um dia menos um segundo para cobrir todo o ultimo dia escolhido
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        # Mantem registros menores ou iguais à data limite calculada
        filtered_df = filtered_df[filtered_df['hora_envio'] <= end_dt]
    # Aplica o filtro de estacao de recebimento se for diferente de 'Todas'
    if rec_station and rec_station != 'Todas':
        # Mantem registros onde a estacao de recebimento seja exatamente a selecionada
        filtered_df = filtered_df[filtered_df['estacao_recebimento'] == rec_station]
    # Aplica o filtro de estacao de registro se for diferente de 'Todas'
    if reg_station and reg_station != 'Todas':
        # Mantem registros onde a estacao de registro seja exatamente a selecionada
        filtered_df = filtered_df[filtered_df['estacao_registro'] == reg_station]
    # Aplica o filtro de status se for diferente de 'Todos'
    if status and status != 'Todos':
        # Mantem registros onde o status seja exatamente o selecionado
        filtered_df = filtered_df[filtered_df['status'] == status]
        
    # Retorna a tabela filtrada finalizada
    return filtered_df

# Definicao do nome do arquivo Excel contendo as remessas sem movimentacao
SEM_MOV_FILE = "sem mov.xlsx"

def _load_sem_mov_data_raw():
    if not os.path.exists(SEM_MOV_FILE):
        return pd.DataFrame()
    
    # Leitura da aba Export do Excel em memória para evitar travar o arquivo no disco (Windows)
    with open(SEM_MOV_FILE, 'rb') as f:
        file_bytes = io.BytesIO(f.read())
    df = pd.read_excel(file_bytes, sheet_name="Export")
    
    # Padroniza as colunas mapeando os nomes para evitar erros se colunas novas/extras forem adicionadas (como Supervisor)
    col_map = {}
    for col in df.columns:
        c_clean = str(col).strip().lower()
        c_clean = c_clean.replace('á', 'a').replace('é', 'e').replace('í', 'i').replace('ó', 'o').replace('ú', 'u')
        c_clean = c_clean.replace('ã', 'a').replace('õ', 'a').replace('ç', 'c').replace('?', '')
        c_clean = c_clean.replace(' ', '_').replace('ª', '').replace('º', '')
        
        if c_clean == 'remessa':
            col_map[col] = 'remessa'
        elif c_clean == 'ultima_operacao':
            col_map[col] = 'ultima_operacao'
        elif c_clean == 'base_responsavel':
            col_map[col] = 'base_responsavel'
        elif c_clean in ['ultima_operacao.1', 'ultima_operacao_tipo']:
            col_map[col] = 'ultima_operacao_tipo'
        elif 'tipo_problematico' in c_clean:
            col_map[col] = 'tipo_problematico'
        elif c_clean == 'aging':
            col_map[col] = 'aging'
        elif 'dias_sem_mov' in c_clean:
            col_map[col] = 'dias_sem_mov'
        elif 'multa' in c_clean:
            col_map[col] = 'multa'
        elif c_clean == 'base':
            col_map[col] = 'base'
        elif c_clean == 'destino':
            col_map[col] = 'destino'

    df = df.rename(columns=col_map)
    expected_cols = ['remessa', 'ultima_operacao', 'base_responsavel', 'ultima_operacao_tipo', 'tipo_problematico', 'aging', 'dias_sem_mov', 'multa', 'base', 'destino']
    for col in expected_cols:
        if col not in df.columns:
            df[col] = None
    df = df[expected_cols]
    
    # Converte ultima_operacao para datetime
    df['ultima_operacao'] = pd.to_datetime(df['ultima_operacao'], errors='coerce')
    
    # Remove linhas sem data
    df = df.dropna(subset=['ultima_operacao'])
    
    # Limpa remessa
    def clean_remessa(val):
        try:
            return str(int(float(val)))
        except:
            return str(val).strip()
    df['remessa'] = df['remessa'].apply(clean_remessa)
    
    # Trata strings e NaNs
    df['base_responsavel'] = df['base_responsavel'].fillna('Não informado').astype(str).str.strip()
    df['ultima_operacao_tipo'] = df['ultima_operacao_tipo'].fillna('Não informado').astype(str).str.strip()
    df['tipo_problematico'] = df['tipo_problematico'].fillna('Não informado').astype(str).str.strip()
    df['aging'] = df['aging'].fillna('Não informado').astype(str).str.strip()
    df['base'] = df['base'].fillna('Não informado').astype(str).str.strip()
    df['destino'] = df['destino'].fillna('Não informado').astype(str).str.strip()
    
    df['dias_sem_mov'] = pd.to_numeric(df['dias_sem_mov'], errors='coerce').fillna(0).astype(int)
    df['multa'] = pd.to_numeric(df['multa'], errors='coerce').fillna(0.0)
    
    df = df.sort_values(by='ultima_operacao', ascending=False)
    
    return df

# Funcao publica com cache em memoria para evitar leituras repetidas do disco
def load_sem_mov_data():
    return get_from_cache(SEM_MOV_FILE, _load_sem_mov_data_raw)

def filter_sem_mov_dataframe(df, filters):
    if df.empty:
        return df
        
    # Suporta getlist para múltiplos parâmetros 'aging' (vindo de requisições GET)
    if hasattr(filters, 'getlist'):
        aging_list = filters.getlist('aging')
    else:
        aging_val = filters.get('aging')
        aging_list = [aging_val] if aging_val else []
        
    # Se vier como string separada por vírgula em alguns requests
    if len(aging_list) == 1 and ',' in aging_list[0]:
        aging_list = [x.strip() for x in aging_list[0].split(',') if x.strip()]
        
    base = filters.get('base')
    destino = filters.get('destino')
    
    filtered_df = df.copy()
    
    # Se aging_list contiver valores que não sejam 'Todos' e não estiver vazio
    if aging_list and not any(x in ['Todos', 'Todas', ''] for x in aging_list):
        filtered_df = filtered_df[filtered_df['aging'].isin(aging_list)]
        
    if base and base != 'Todas':
        filtered_df = filtered_df[filtered_df['base'] == base]
    if destino and destino != 'Todos':
        filtered_df = filtered_df[filtered_df['destino'] == destino]
        
    return filtered_df

# Classe customizada de canvas do ReportLab para aplicar numeracao dinamica de paginas e rodapes
class NumberedCanvas(canvas.Canvas):
    # Construtor da classe herdada que inicializa a lista de estados de paginas
    def __init__(self, *args, **kwargs):
        # Chama o construtor da classe base canvas.Canvas
        super().__init__(*args, **kwargs)
        # Inicializa a lista vazia para armazenar as paginas capturadas durante a primeira passada
        self._saved_page_states = []

    # Sobrescreve o metodo showPage para capturar o estado da pagina antes de ir para a proxima
    def showPage(self):
        # Salva o dicionario de propriedades internas da pagina corrente na lista local
        self._saved_page_states.append(dict(self.__dict__))
        # Chama a rotina nativa para iniciar uma nova pagina em branco no documento
        self._startPage()

    # Sobrescreve o metodo save para renderizar os cabecalhos e rodapes na segunda passada do motor
    def save(self):
        # Obtem a quantidade total de paginas geradas no documento final
        num_pages = len(self._saved_page_states)
        # Itera por cada um dos estados de paginas salvos anteriormente
        for state in self._saved_page_states:
            # Atualiza o dicionario da instancia atual com o estado historico da pagina correspondente
            self.__dict__.update(state)
            # Desenha as bordas, cabecalhos, rodapes e numeracoes na pagina ativa
            self.draw_page_decorations(num_pages)
            # Chama o metodo showPage da classe base para efetivar a renderizacao da pagina tratada
            super().showPage()
        # Salva o arquivo PDF no buffer final
        super().save()

    # Metodo interno para desenhar elementos de layout corporativo em cada pagina do PDF
    def draw_page_decorations(self, page_count):
        # Largura padrao da pagina A4 em orientacao paisagem (landscape)
        width = 841.89
        # Altura padrao da pagina A4 em orientacao paisagem (landscape)
        height = 595.27
        # Margem esquerda e de inicio dos tracados
        left_m = 40
        # Margem direita limite para os textos e linhas
        right_m = 801.89
        
        # Condicao para ignorar cabecalho, rodape e bordas na capa (Pagina 1)
        if self._pageNumber == 1:
            # Inicia o salvamento de estado do pincel
            self.saveState()
            # Define a cor do retangulo de destaque lateral da capa (azul escuro)
            self.setFillColor(colors.HexColor('#1E3A8A'))
            # Desenha um retangulo de destaque vertical no canto esquerdo da capa
            self.rect(0, 0, 20, height, fill=True, stroke=False)
            # Altera o preenchimento para azul claro
            self.setFillColor(colors.HexColor('#3B82F6'))
            # Desenha uma segunda listra menor ao lado da faixa escura
            self.rect(20, 0, 10, height, fill=True, stroke=False)
            # Restaura o pincel ao estado padrao do canvas
            self.restoreState()
            # Retorna e interrompe o metodo para nao desenhar cabeçalhos/rodapés na capa
            return
            
        # Ativa o pincel para desenhar elementos de layout das paginas internas
        self.saveState()
        # Define a fonte e o tamanho de letra dos cabecalhos e rodapes
        self.setFont("Helvetica", 8)
        # Define a cor cinza médio para os textos auxiliares de pagina
        self.setFillColor(colors.HexColor('#4B5563'))
        
        # Desenha o titulo do sistema no cabecalho à esquerda
        self.drawString(left_m, height - 30, "Dashboard Logístico — Relatório Executivo")
        # Desenha a data e hora em que o relatorio foi emitido no cabecalho à direita
        self.drawRightString(right_m, height - 30, f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        # Define a cor cinza claro para a linha divisoria do cabecalho
        self.setStrokeColor(colors.HexColor('#E5E7EB'))
        # Define a largura fina da linha divisoria do cabecalho
        self.setLineWidth(0.5)
        # Desenha a linha horizontal que separa o cabecalho do conteudo util da pagina
        self.line(left_m, height - 35, right_m, height - 35)
        
        # Desenha o nome do sistema no rodape à esquerda
        self.drawString(left_m, 20, "Nome do sistema: Dashboard Logístico")
        # Desenha a mensagem de confidencialidade centralizada no rodape
        self.drawCentredString(width / 2.0, 20, "Confidencial - Para Uso Interno")
        # Desenha a numeracao dinamica de paginas no rodape à direita ("Página X de Y")
        self.drawRightString(right_m, 20, f"Página {self._pageNumber} de {page_count}")
        # Desenha a linha horizontal de delimitacao superior do rodape
        self.line(left_m, 30, right_m, 30)
        
        # Restaura o estado grafico anterior do pincel
        self.restoreState()

# Rota principal do Flask que serve a interface visual do dashboard
@app.route('/')
def index():
    # Renderiza e retorna o arquivo index.html localizado na pasta de templates
    return render_template('index.html')

# Endpoint da API para retornar os valores unicos para populacao inicial dos filtros
@app.route('/api/filters')
def get_filters():
    # Carrega todos os dados da planilha de entrada
    df = load_data()
    # Verifica se os dados estao vazios (planilha ausente ou limpa)
    if df.empty:
        # Retorna valores vazios no formato estruturado para o frontend
        return jsonify({
            'receiving_stations': [],
            'registering_stations': [],
            'statuses': [],
            'min_date': '',
            'max_date': ''
        })
        
    # Obtem a lista ordenada sem duplicados das estacoes de recebimento encontradas
    rec_stations = sorted(df['estacao_recebimento'].unique().tolist())
    # Obtem a lista ordenada de todas as estacoes de registro identificadas
    reg_stations = sorted(df['estacao_registro'].unique().tolist())
    # Obtem a lista ordenada de todos os status logisticos encontrados
    statuses = sorted(df['status'].unique().tolist())
    
    # Obtem a data minima de envio formatada em padrão ISO
    min_date = df['hora_envio'].min().strftime('%Y-%m-%d')
    # Obtem a data maxima de envio formatada em padrão ISO
    max_date = df['hora_envio'].max().strftime('%Y-%m-%d')
    
    # Retorna os metadados dos filtros em formato JSON para o cliente
    return jsonify({
        'receiving_stations': rec_stations,
        'registering_stations': reg_stations,
        'statuses': statuses,
        'min_date': min_date,
        'max_date': max_date
    })

# Endpoint da API para retornar a lista de registros filtrados com base na busca ativa
@app.route('/api/data')
def get_data():
    # Carrega a base bruta da planilha
    df = load_data()
    # Valida se a planilha possui dados
    if df.empty:
        # Retorna uma lista JSON vazia caso nao existam dados
        return jsonify([])
        
    # Aplica os filtros recebidos via URL query parameters
    filtered_df = filter_dataframe(df, request.args)
    
    if filtered_df.empty:
        return jsonify([])

    # Extração vetorizada de alta velocidade (substitui iterrows lento)
    cols = ['remessa', 'hora_envio', 'estacao_recebimento', 'estacao_registro', 'status', 'categoria']
    df_out = filtered_df[cols].copy()
    df_out['hora_envio'] = df_out['hora_envio'].dt.strftime('%d/%m/%Y %H:%M:%S')
    return jsonify(df_out.to_dict(orient='records'))

# Endpoint da API para retornar a lista de registros estendidos (5 dias anteriores + filtro) para o grafico de evolucao
@app.route('/api/data_evolution')
def get_data_evolution():
    # Carrega a base bruta da planilha
    df = load_data()
    # Valida se a planilha possui dados
    if df.empty:
        # Retorna uma lista JSON vazia caso nao existam dados
        return jsonify([])
        
    # Copia os filtros da requisição para poder modificar a data inicial
    filters = dict(request.args)
    start_date = filters.get('start_date')
    if start_date:
        try:
            # Subtrai 5 dias da data de inicio selecionada
            dt = pd.to_datetime(start_date)
            filters['start_date'] = (dt - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        except Exception as e:
            pass
            
    # Aplica os filtros recebidos via URL com a data de início modificada
    filtered_df = filter_dataframe(df, filters)
    
    if filtered_df.empty:
        return jsonify([])

    # Extração vetorizada de alta velocidade (substitui iterrows lento)
    cols = ['remessa', 'hora_envio', 'estacao_recebimento', 'estacao_registro', 'status', 'categoria']
    df_out = filtered_df[cols].copy()
    df_out['hora_envio'] = df_out['hora_envio'].dt.strftime('%d/%m/%Y %H:%M:%S')
    return jsonify(df_out.to_dict(orient='records'))

# Endpoint da API que constroi e devolve para download o Relatorio Executivo PDF filtrado
@app.route('/api/generate_pdf')
def generate_pdf():
    # Carrega a base bruta da planilha
    df = load_data()
    # Valida se existem dados para processar
    if df.empty:
        # Retorna um erro caso nao haja nenhum registro
        return "Erro: Base de dados vazia ou não encontrada.", 404
        
    # Aplica os filtros ativos de busca no DataFrame
    filtered_df = filter_dataframe(df, request.args)
    # Conta a quantidade de remessas que cairam sob a filtragem
    total_records = len(filtered_df)
    
    # Identifica o intervalo de datas do relatorio ativo para colocar na capa
    if not filtered_df.empty:
        # Menor data encontrada formatada em padrao nacional
        min_date_str = filtered_df['hora_envio'].min().strftime('%d/%m/%Y')
        # Maior data encontrada formatada em padrao nacional
        max_date_str = filtered_df['hora_envio'].max().strftime('%d/%m/%Y')
    else:
        # Fallback caso nao haja registros
        min_date_str = "N/A"
        # Fallback caso nao haja registros
        max_date_str = "N/A"
        
    # Concatena as strings para formatar a string de exibicao do periodo de analise
    periodo_analisado = f"{min_date_str} a {max_date_str}"
    
    # Cria um objeto de arquivo em memoria para receber a geracao de bytes do PDF
    buffer = io.BytesIO()
    
    # Define a estrutura do documento ReportLab em orientacao Paisagem (Landscape)
    doc = SimpleDocTemplate(
        buffer,
        # Define o tamanho de pagina como A4 rotacionado em paisagem
        pagesize=landscape(A4),
        # Margem esquerda de 40 pontos
        leftMargin=40,
        # Margem direita de 40 pontos
        rightMargin=40,
        # Margem superior de 50 pontos para acomodar o cabecalho
        topMargin=50,
        # Margem inferior de 50 pontos para acomodar o rodape
        bottomMargin=50
    )
    
    # Cria uma folha de estilos padrao do ReportLab
    styles = getSampleStyleSheet()
    
    # Estilo customizado para o Titulo da Capa
    title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=30,
        leading=36,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=15
    )
    
    # Estilo customizado para o Subtitulo da Capa
    subtitle_style = ParagraphStyle(
        'CoverSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=30
    )
    
    # Estilo em negrito para os labels de metadados na Capa
    metadata_label = ParagraphStyle(
        'MetaLabel',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#1F2937')
    )
    
    # Estilo comum para os valores de metadados na Capa
    metadata_value = ParagraphStyle(
        'MetaValue',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    
    # Estilo estrutural para titulos de secoes do relatorio
    section_title = ParagraphStyle(
        'SectionTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=10
    )
    
    # Estilo de texto em negrito comum para células de tabela
    body_bold = ParagraphStyle(
        'BodyBold',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#1F2937')
    )
    
    # Estilo de texto padrão comum para celulas de tabela
    body_text = ParagraphStyle(
        'BodyText',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=11,
        textColor=colors.HexColor('#4B5563')
    )
    
    # Estilo de texto branco em negrito para o cabecalho de tabelas
    body_text_white = ParagraphStyle(
        'BodyTextWhite',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=11,
        textColor=colors.white
    )
    
    # Estilo para titulos dos cartoes de KPIs no PDF
    card_title = ParagraphStyle(
        'CardTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#4B5563'),
        alignment=1
    )
    
    # Estilo para os valores numericos internos dos cartoes de KPIs
    card_value = ParagraphStyle(
        'CardValue',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    # Lista 'story' que armazenara sequencialmente os elementos do documento
    story = []
    
    # ----------------------------------------------------
    # PAGE 1: CAPA
    # ----------------------------------------------------
    # Adiciona um espacamento inicial para centralizar verticalmente o titulo na capa
    story.append(Spacer(1, 100))
    # Adiciona o titulo principal na capa
    story.append(Paragraph("Relatório Executivo Logístico", title_style))
    # Adiciona o subtitulo do sistema logo abaixo
    story.append(Paragraph("Sistema de Monitoramento de Entregas", subtitle_style))
    # Espacamento entre o titulo e a tabela de metadados
    story.append(Spacer(1, 40))
    
    # Estrutura dos dados de metadados da capa
    meta_data = [
        # Campo de data e hora de geracao
        [Paragraph("Data e hora de geração:", metadata_label), Paragraph(datetime.now().strftime('%d/%m/%Y às %H:%M'), metadata_value)],
        # Campo de periodo de analise ativo
        [Paragraph("Período analisado:", metadata_label), Paragraph(periodo_analisado, metadata_value)],
        # Campo de contagem total de registros
        [Paragraph("Registros analisados:", metadata_label), Paragraph(f"{total_records} remessas", metadata_value)],
        # Campo de indicacao se o relatorio possui filtros ativos
        [Paragraph("Status do Relatório:", metadata_label), Paragraph("Geral" if len(request.args) == 0 or all(v == 'Todas' or v == 'Todos' or v == '' for v in request.args.values()) else "Filtrado", metadata_value)]
    ]
    # Cria a tabela de metadados
    meta_table = Table(meta_data, colWidths=[150, 400])
    # Define a formatacao e preenchimento da tabela de metadados
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    # Adiciona a tabela de metadados na historia do PDF
    story.append(meta_table)
    
    # Insere uma quebra de pagina para separar a capa da primeira pagina de conteudo
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 2: RESUMO EXECUTIVO & INDICADORES OPERACIONAIS
    # ----------------------------------------------------
    # Adiciona o titulo da secao na Pagina 2
    story.append(Paragraph("Resumo Executivo & Indicadores Operacionais", section_title))
    
    # Calcula os valores consolidados para a secao executiva
    total = len(filtered_df)
    # Se houver registros na busca corrente, calcula as metricas operacionais
    if total > 0:
        # Quantidade de remessas na categoria Concluida
        concluidas = len(filtered_df[filtered_df['categoria'] == 'Concluída'])
        # Quantidade de remessas na categoria Pendente
        pendentes = len(filtered_df[filtered_df['categoria'] == 'Pendente'])
        # Quantidade de remessas na categoria Critica
        criticas = len(filtered_df[filtered_df['categoria'] == 'Crítica'])
        
        # Percentual correspondente às concluidas
        pct_concluidas = (concluidas / total) * 100
        # Percentual correspondente às pendentes
        pct_pendentes = (pendentes / total) * 100
        # Percentual correspondente às criticas
        pct_criticas = (criticas / total) * 100
        
        # Conta a frequencia de cada status operacional
        status_counts = filtered_df['status'].value_counts()
        # Obtem o status que mais apareceu na filtragem
        most_common_status = status_counts.index[0] if not status_counts.empty else 'N/A'
        
        # Conta a frequencia de remessas registradas por estacao
        reg_counts = filtered_df['estacao_registro'].value_counts()
        # Obtem a estacao de registro de maior volume no periodo
        most_active_station = reg_counts.index[0] if not reg_counts.empty else 'N/A'
    # Fallback caso a tabela esteja totalmente vazia de dados
    else:
        # Inicializa tudo zerado para nao causar erros de divisao por zero
        concluidas = pendentes = criticas = 0
        # Percentuais zerados
        pct_concluidas = pct_pendentes = pct_criticas = 0
        # Nomes padrão
        most_common_status = "N/A"
        # Nomes padrão
        most_active_station = "N/A"
        
    # Estrutura dos cartoes de KPI a serem desenhados lado a lado no topo da pagina
    kpi_data = [
        # Linha 1: Titulos dos cartoes
        [
            Paragraph("TOTAL DE REMESSAS", card_title),
            Paragraph("REMESSAS CONCLUÍDAS", card_title),
            Paragraph("REMESSAS PENDENTES", card_title),
            Paragraph("REMESSAS CRÍTICAS", card_title)
        ],
        # Linha 2: Valores consolidados e porcentagens coloridas
        [
            Paragraph(f"{total}", card_value),
            Paragraph(f"{concluidas}<br/><font size=8 textColor='#10B981'>{pct_concluidas:.1f}%</font>", card_value),
            Paragraph(f"{pendentes}<br/><font size=8 textColor='#F59E0B'>{pct_pendentes:.1f}%</font>", card_value),
            Paragraph(f"{criticas}<br/><font size=8 textColor='#EF4444'>{pct_criticas:.1f}%</font>", card_value)
        ]
    ]
    # Cria a tabela de KPIs dividindo a largura util em 4 colunas de 190 pontos
    kpi_table = Table(kpi_data, colWidths=[190, 190, 190, 190])
    # Aplica estilos de fundo, borda, espacamento e alinhamento centralizado aos cartoes
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    # Adiciona a tabela de KPIs ao fluxo do relatorio
    story.append(kpi_table)
    # Adiciona um espacamento vertical antes da proxima secao
    story.append(Spacer(1, 15))
    
    # Lista para acumular os elementos a serem exibidos do lado esquerdo (Insights e Tabela)
    left_flowables = []
    
    # Adiciona titulo da subsecao de Insights
    left_flowables.append(Paragraph("Insights Operacionais", ParagraphStyle('Sub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'))))
    # Define o texto em HTML dos insights operacionais, preenchendo as variaveis calculadas
    insights_html = f"""
    Durante o período analisado foram processadas <b>{total}</b> remessas.<br/><br/>
    A taxa de conclusão operacional foi de <b>{pct_concluidas:.1f}%</b>.<br/><br/>
    A estação com maior volume de registro foi <b>{most_active_station}</b>.<br/><br/>
    Foram identificadas <b>{pendentes + criticas}</b> remessas pendentes de conclusão.<br/><br/>
    O status mais recorrente foi <b>{most_common_status}</b>.
    """
    # Adiciona o paragrafo formatado à lista esquerda
    left_flowables.append(Paragraph(insights_html, ParagraphStyle('InsBody', parent=body_text, fontSize=9.5, leading=14)))
    # Adiciona espaco vertical
    left_flowables.append(Spacer(1, 15))
    
    # Adiciona titulo da subsecao de Indicadores
    left_flowables.append(Paragraph("Tabela de Indicadores Operacionais", ParagraphStyle('Sub2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'))))
    
    # Cria o cabecalho da tabela de indicadores operacionais
    indicators_headers = [Paragraph("Status", body_text_white), Paragraph("Quantidade", body_text_white), Paragraph("Percentual", body_text_white)]
    # Inicializa a lista de linhas contendo apenas o cabecalho
    indicators_rows = [indicators_headers]
    # Se houver registros, itera populando a tabela
    if total > 0:
        # Itera por cada status e sua contagem
        for status, count in status_counts.items():
            # Calcula a porcentagem correspondente ao status
            pct = (count / total) * 100
            # Adiciona a linha contendo o status, quantidade e porcentagem formatada
            indicators_rows.append([
                Paragraph(status, body_text),
                Paragraph(f"{count}", body_text),
                Paragraph(f"{pct:.1f}%", body_text)
            ])
    # Caso contrario, insere linha informativa de falta de dados
    else:
        # Linha informativa vazia
        indicators_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    # Instancia a tabela de indicadores operacionais definindo a largura das colunas
    ind_table = Table(indicators_rows, colWidths=[200, 100, 100])
    # Aplica estilos de cabecalho, cores de linhas alternadas (zebrada) e grades
    ind_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    # Adiciona a tabela à lista esquerda
    left_flowables.append(ind_table)
    
    # Lista para acumular os elementos a serem exibidos do lado direito (Grafico de Rosca)
    right_flowables = []
    # Adiciona o titulo da secao do grafico à direita
    right_flowables.append(Paragraph("Distribuição de Status", ParagraphStyle('Sub3', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'), alignment=1)))
    
    # Cria uma area de desenho vetorial (Drawing) de 300x200 pontos para receber o grafico
    pie_drawing = Drawing(300, 200)
    # Instancia o grafico de Pizza (Pie) do ReportLab
    pc = Pie()
    # Posição horizontal central do circulo
    pc.x = 80
    # Posição vertical central do circulo
    pc.y = 30
    # Largura do grafico de pizza
    pc.width = 140
    # Altura do grafico de pizza
    pc.height = 140
    
    # Se houver registros, plota os dados
    if total > 0:
        # Define os valores numericos das fatias
        pc.data = status_counts.values.tolist()
        # Cria os rotulos de legenda com porcentagens
        pc.labels = [f"{lbl} ({pct:.1f}%)" for lbl, pct in zip(status_counts.index, (status_counts.values / total * 100))]
        
        # Paleta de cores padronizada do relatorio
        status_colors = {
            'assinado': colors.HexColor('#10B981'),
            'expedido não chegou': colors.HexColor('#EF4444'),
            'recebido na base': colors.HexColor('#3B82F6'),
            'recebido em outra base': colors.HexColor('#F59E0B'),
            'Devolução': colors.HexColor('#DC2626'),
            'na base DC BAU': colors.HexColor('#06B6D4'),
            'entregador': colors.HexColor('#8B5CF6'),
            'interceptado': colors.HexColor('#EC4899'),
            'erro triagem': colors.HexColor('#F43F5E')
        }
        # Aplica as cores correspondentes a cada fatia do grafico (usando fallback de cor caso nao mapeada)
        for idx, lbl in enumerate(status_counts.index):
            # Associa a cor do status ao fatiamento do grafico
            pc.slices[idx].fillColor = status_colors.get(lbl, colors.HexColor('#6B7280'))
    # Se nao houver dados, desenha circulo cinza padrao
    else:
        # Valores de fallback
        pc.data = [1]
        # Rotulo de fallback
        pc.labels = ['Sem dados']
        # Cor de fallback
        pc.slices[0].fillColor = colors.HexColor('#E5E7EB')
        
    # Define a largura das linhas divisórias das fatias
    pc.slices.strokeWidth = 0.5
    # Define a cor das bordas divisórias como branca
    pc.slices.strokeColor = colors.white
    # Adiciona o componente grafico de pizza à area de desenho
    pie_drawing.add(pc)
    # Adiciona o desenho vetorial à lista direita
    right_flowables.append(pie_drawing)
    
    # Cria uma tabela invisivel para posicionar o conteudo da esquerda e da direita lado a lado
    layout_data = [[left_flowables, right_flowables]]
    # Divide a largura de 761 pontos: 420 pontos à esquerda, 341 pontos à direita
    layout_table = Table(layout_data, colWidths=[420, 341])
    # Define o alinhamento no topo e remove margens internas da tabela de layout
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    # Adiciona a tabela de layout ao fluxo do relatorio
    story.append(layout_table)
    
    # Quebra de pagina
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 3: ANÁLISE POR ESTAÇÃO DE RECEBIMENTO E REGISTRO
    # ----------------------------------------------------
    # Adiciona o titulo da secao na Pagina 3
    story.append(Paragraph("Análise por Estação de Recebimento e Registro", section_title))
    
    # Calcula as contagens de remessas por estacoes
    rec_counts = filtered_df['estacao_recebimento'].value_counts()
    # Contagens de estacoes de registro
    reg_counts = filtered_df['estacao_registro'].value_counts()
    
    # Cabecalho da tabela de estacoes de recebimento
    rec_headers = [Paragraph("Estação Recebimento", body_text_white), Paragraph("Qtd Processada", body_text_white), Paragraph("Percentual", body_text_white)]
    # Inicializa a lista de linhas com o cabecalho
    rec_rows = [rec_headers]
    # Se houver registros, popula a tabela
    if total > 0:
        # Itera por estacao e quantidade
        for est, count in rec_counts.items():
            # Porcentagem correspondente à estacao
            pct = (count / total) * 100
            # Adiciona linha
            rec_rows.append([Paragraph(est, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    # Caso contrario, insere linha de fallback
    else:
        # Linha informativa
        rec_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    # Instancia a tabela de estacoes de recebimento
    rec_table = Table(rec_rows, colWidths=[180, 95, 80])
    # Estiliza a tabela com cabecalho colorido, linhas alternadas e grades
    rec_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    # Cabecalho da tabela de estacoes de registro
    reg_headers = [Paragraph("Estação Registro", body_text_white), Paragraph("Qtd Processada", body_text_white), Paragraph("Percentual", body_text_white)]
    # Inicializa a lista de linhas
    reg_rows = [reg_headers]
    # Se houver registros, popula a tabela
    if total > 0:
        # Define limite de exibicao para evitar tabelas muito extensas na mesma pagina (max 8)
        top_n = 8
        # Se houver mais estacoes do que o limite, agrupa as demais como "Outros"
        if len(reg_counts) > top_n:
            # Obtem as top 8 estacoes de maior volume
            top_reg = reg_counts.head(top_n)
            # Soma a quantidade de todas as demais estacoes
            other_sum = reg_counts.iloc[top_n:].sum()
            # Popula as top 8 linhas
            for est, count in top_reg.items():
                # Porcentagem correspondente
                pct = (count / total) * 100
                # Adiciona linha
                reg_rows.append([Paragraph(est, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
            # Adiciona a linha somada de "Outras Estações" em negrito
            reg_rows.append([Paragraph("Outras Estações", body_bold), Paragraph(f"{other_sum}", body_bold), Paragraph(f"{(other_sum/total)*100:.1f}%", body_bold)])
        # Se estiver dentro do limite, popula normalmente
        else:
            # Itera de forma normal
            for est, count in reg_counts.items():
                # Porcentagem correspondente
                pct = (count / total) * 100
                # Adiciona linha
                reg_rows.append([Paragraph(est, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    # Fallback se nao houver dados
    else:
        # Linha vazia
        reg_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    # Instancia a tabela de estacoes de registro
    reg_table = Table(reg_rows, colWidths=[180, 95, 80])
    # Estiliza a tabela com cabecalho colorido, linhas alternadas e grades
    reg_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    # Cria os graficos vetoriais para estacoes de recebimento e registro
    # Desenho esquerdo: recebimento
    rec_drawing = Drawing(355, 140)
    # Instancia o grafico de Barras Verticais do ReportLab
    rec_chart = VerticalBarChart()
    # Margem interna a partir da borda esquerda
    rec_chart.x = 40
    # Margem interna a partir da borda inferior
    rec_chart.y = 20
    # Altura util do grafico de barras
    rec_chart.height = 100
    # Largura util do grafico de barras
    rec_chart.width = 300
    # Se houver dados de recebimento
    if not rec_counts.empty:
        # Passa a lista de contagens envelopada em lista bidimensional
        rec_chart.data = [rec_counts.values.tolist()]
        # Passa a lista dos nomes das estacoes no eixo X
        rec_chart.categoryAxis.categoryNames = rec_counts.index.tolist()
    else:
        # Fallback zerado
        rec_chart.data = [[0]]
        # Fallback de labels
        rec_chart.categoryAxis.categoryNames = ['N/A']
    # Valor minimo do eixo Y
    rec_chart.valueAxis.valueMin = 0
    # Valor maximo do eixo Y (maior contagem encontrada mais margem de 10)
    rec_chart.valueAxis.valueMax = int(rec_counts.max()) + 10 if not rec_counts.empty else 100
    # Define o intervalo dos ticks horizontais do eixo Y
    rec_chart.valueAxis.valueStep = max(10, int((rec_counts.max() / 5) / 10) * 10) if not rec_counts.empty else 20
    # Define a cor de preenchimento das barras como azul claro
    rec_chart.bars[0].fillColor = colors.HexColor('#3B82F6')
    # Ajusta o tamanho da fonte do eixo X
    rec_chart.categoryAxis.labels.fontSize = 7
    # Ajusta o tamanho da fonte do eixo Y
    rec_chart.valueAxis.labels.fontSize = 7
    # Adiciona o grafico de barras à area de desenho
    rec_drawing.add(rec_chart)
    
    # Desenho direito: registro (Top 5 para legibilidade grafica)
    reg_drawing = Drawing(355, 140)
    # Instancia o grafico de barras verticais do ReportLab
    reg_chart = VerticalBarChart()
    # Margem esquerda interna
    reg_chart.x = 40
    # Margem inferior interna
    reg_chart.y = 20
    # Altura do grafico
    reg_chart.height = 100
    # Largura do grafico
    reg_chart.width = 300
    # Filtra as top 5 estacoes de maior volume
    top5_reg = reg_counts.head(5)
    # Se houver dados de registro
    if not top5_reg.empty:
        # Passa a lista das contagens
        reg_chart.data = [top5_reg.values.tolist()]
        # Passa os nomes das top 5 no eixo X
        reg_chart.categoryAxis.categoryNames = top5_reg.index.tolist()
    else:
        # Fallback zerado
        reg_chart.data = [[0]]
        # Fallback de labels
        reg_chart.categoryAxis.categoryNames = ['N/A']
    # Limite minimo
    reg_chart.valueAxis.valueMin = 0
    # Limite maximo do eixo Y
    reg_chart.valueAxis.valueMax = int(reg_counts.max()) + 5 if not reg_counts.empty else 100
    # Passos de escala no eixo Y
    reg_chart.valueAxis.valueStep = max(5, int((reg_counts.max() / 5) / 5) * 5) if not reg_counts.empty else 20
    # Define a cor das barras como verde claro
    reg_chart.bars[0].fillColor = colors.HexColor('#10B981')
    # Ajusta a fonte do eixo X
    reg_chart.categoryAxis.labels.fontSize = 7
    # Ajusta a fonte do eixo Y
    reg_chart.valueAxis.labels.fontSize = 7
    # Adiciona o grafico ao desenho direito
    reg_drawing.add(reg_chart)
    
    # Monta a lista de elementos do lado esquerdo (tabela e grafico de recebimento)
    left_station_flowables = [
        Paragraph("Volume por Estação de Recebimento", ParagraphStyle('SubS1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        rec_table,
        Spacer(1, 10),
        rec_drawing
    ]
    
    # Monta a lista de elementos do lado direito (tabela e grafico de registro)
    right_station_flowables = [
        Paragraph("Volume por Estação de Registro (Top 8 / 5 Gráfico)", ParagraphStyle('SubS2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        reg_table,
        Spacer(1, 10),
        reg_drawing
    ]
    
    # Coloca os blocos de recebimento e registro lado a lado usando tabela de layout invisivel
    station_layout_data = [[left_station_flowables, right_station_flowables]]
    # Divide a largura de 761 pontos em 380 pontos para esquerda e 381 pontos para direita
    station_layout = Table(station_layout_data, colWidths=[380, 381])
    # Alinha os blocos no topo e zera as margens internas da tabela
    station_layout.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    # Adiciona o painel de layout de estacoes ao fluxo do documento
    story.append(station_layout)
    
    # Quebra de pagina
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 4: EVOLUÇÃO DIÁRIA & OCORRÊNCIAS PENDENTES
    # ----------------------------------------------------
    # Adiciona o titulo da secao na Pagina 4
    story.append(Paragraph("Evolução Diária e Ocorrências Pendentes", section_title))
    
    # Filtra o DataFrame especificamente para o gráfico, incluindo os 5 dias anteriores
    chart_filters = dict(request.args)
    chart_start_date = chart_filters.get('start_date')
    if chart_start_date:
        try:
            # Subtrai 5 dias da data de início selecionada para o gráfico do PDF
            dt = pd.to_datetime(chart_start_date)
            chart_filters['start_date'] = (dt - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        except Exception as e:
            pass
    chart_df = filter_dataframe(df, chart_filters)
    # Agrupa as remessas por data e faz contagem de volumes por dia para o gráfico
    daily_series = chart_df.groupby(chart_df['hora_envio'].dt.date).size()
    
    # Cria a area de desenho vetorial de largura cheia (760 pontos) para o grafico de linha
    line_drawing = Drawing(760, 140)
    # Instancia o grafico de Linha (LinePlot) do ReportLab
    lp = LinePlot()
    # Define a margem esquerda interna do grafico de linhas
    lp.x = 40
    # Define a margem inferior interna do grafico de linhas
    lp.y = 20
    # Altura do grafico de linha
    lp.height = 100
    # Largura total util do grafico de linha
    lp.width = 680
    
    # Se houver registros na serie diaria
    if not daily_series.empty:
        # Lista para armazenar as coordenadas de pontos (X, Y)
        data_points = []
        # Lista para armazenar as strings de datas formatadas
        date_labels = []
        # Itera preenchendo as listas auxiliares
        for idx, (dt, val) in enumerate(daily_series.items()):
            # Adiciona o ponto (indice_sequencial, quantidade)
            data_points.append((idx, val))
            # Adiciona o label do dia e mes correspondentes
            date_labels.append(dt.strftime('%d/%m'))
            
        # Adiciona a lista de pontos envelopada em lista de series
        lp.data = [data_points]
        # Dicionario para mapear indices decimais para suas respectivas datas textuais
        x_ticks = {}
        # Define passos de intervalo para nao empilhar datas no eixo X (exibe ate 8 datas)
        step = max(1, len(date_labels) // 8)
        # Popula o mapeamento do eixo X
        for i in range(0, len(date_labels), step):
            # Mapeia indice inteiro para a string correspondente
            x_ticks[i] = date_labels[i]
        # Garante a inserção do ultimo dia da serie
        if (len(date_labels) - 1) not in x_ticks:
            # Mapeia ultimo indice para ultima data
            x_ticks[len(date_labels) - 1] = date_labels[-1]
            
        # Define os limites do eixo X correspondendo aos indices da serie
        lp.xValueAxis.valueMin = 0
        # Limite maximo do eixo X
        lp.xValueAxis.valueMax = len(date_labels) - 1
        # Passos do eixo X
        lp.xValueAxis.valueStep = step
        # Ajusta a fonte do eixo X
        lp.xValueAxis.labels.fontSize = 7
        # Associa a funcao lambda para formatar os labels do eixo X usando o dicionario mapeado
        lp.xValueAxis.labelTextFormat = lambda val: x_ticks.get(int(round(val)), '')
    # Fallback caso a busca de dados esteja zerada
    else:
        # Ponto padrao
        lp.data = [[(0, 0)]]
        # Limites minimos padrao
        lp.xValueAxis.valueMin = 0
        # Limites maximos padrao
        lp.xValueAxis.valueMax = 1
        # Passo padrao
        lp.xValueAxis.valueStep = 1
        
    # Limites do eixo Y do grafico de linha
    lp.yValueAxis.valueMin = 0
    # Limite maximo (maior volume diario somado de 5 de margem)
    lp.yValueAxis.valueMax = int(daily_series.max()) + 5 if not daily_series.empty else 100
    # Passos de ticks do eixo Y
    lp.yValueAxis.valueStep = max(5, int((daily_series.max() / 5) / 5) * 5) if not daily_series.empty else 20
    # Ajusta tamanho da fonte dos numeros do eixo Y
    lp.yValueAxis.labels.fontSize = 7
    # Define a cor azul escuro da linha do grafico
    lp.lines[0].strokeColor = colors.HexColor('#1E3A8A')
    # Define a espessura da linha
    lp.lines[0].strokeWidth = 2
    
    # Adiciona o componente grafico de linha ao desenho vetorial
    line_drawing.add(lp)
    
    # Adiciona o subtitulo do grafico de evolucao diaria
    story.append(Paragraph("Evolução Diária de Remessas (Volume por Dia de Envio)", ParagraphStyle('LineSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))))
    # Adiciona o grafico de linha ao fluxo
    story.append(line_drawing)
    # Adiciona espaco vertical
    story.append(Spacer(1, 15))
    
    # Secao de Ocorrencias Pendentes (exclusivo para remessas nao concluidas)
    story.append(Paragraph("Detalhamento de Ocorrências Pendentes / Críticas", ParagraphStyle('PendSub', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'))))
    # Paragrafo de descricao operacional da tabela
    story.append(Paragraph("Lista contendo as ocorrências pendentes e críticas (exibindo as 50 mais antigas no período para otimização):", ParagraphStyle('PendDesc', parent=body_text, spaceAfter=10)))
    
    # Filtra o DataFrame mantendo apenas as remessas que nao estao na categoria Concluída
    non_completed_df = filtered_df[filtered_df['categoria'] != 'Concluída']
    
    # Define o cabecalho de colunas da tabela de ocorrencias pendentes
    pending_headers = [
        Paragraph("Remessa", body_text_white),
        Paragraph("Hora de Envio", body_text_white),
        Paragraph("Estação Recebimento", body_text_white),
        Paragraph("Estação Registro", body_text_white),
        Paragraph("Status", body_text_white)
    ]
    
    # Inicializa a lista de linhas da tabela contendo o cabecalho
    pending_table_rows = [pending_headers]
    
    # Se houver ocorrencias pendentes na tabela filtrada, popula
    if not non_completed_df.empty:
        # Limita a tabela para os 50 registros mais antigos/críticos para melhorar a performance e reduzir o tamanho do PDF
        sorted_non_completed = non_completed_df.head(50)
        
        # Mapeamento de estilos de fontes coloridas para destacar status na tabela
        status_text_styles = {
            # Vermelho para remessas que expediram mas nao chegaram
            'expedido não chegou': ParagraphStyle('RedText', parent=body_text, textColor=colors.HexColor('#DC2626'), fontName='Helvetica-Bold'),
            # Vermelho escuro para remessas em devolucao
            'Devolução': ParagraphStyle('DarkRedText', parent=body_text, textColor=colors.HexColor('#991B1B'), fontName='Helvetica-Bold'),
            # Amarelo/Laranja para remessas recebidas na base
            'Recebido na base': ParagraphStyle('YellowText', parent=body_text, textColor=colors.HexColor('#D97706'), fontName='Helvetica-Bold'),
            # Amarelo/Laranja para remessas recebidas em outra base
            'Recebido em outra base': ParagraphStyle('LightYellowText', parent=body_text, textColor=colors.HexColor('#D97706'), fontName='Helvetica-Bold'),
            # Azul escuro para remessas na base DC BAU
            'na base DC BAU': ParagraphStyle('BlueText', parent=body_text, textColor=colors.HexColor('#2563EB'), fontName='Helvetica-Bold')
        }
        
        # Itera por cada linha do DataFrame de ocorrencias pendentes limitado
        for _, row in sorted_non_completed.iterrows():
            # Obtem o status operacional bruto da linha
            status_val = row['status']
            # Associa o estilo de cor correspondente ou usa estilo de texto comum
            st_style = status_text_styles.get(status_val, body_text)
            
            # Adiciona a linha estruturada contendo as informacoes da remessa pendente
            pending_table_rows.append([
                Paragraph(row['remessa'], body_text),
                Paragraph(row['hora_envio'].strftime('%d/%m/%Y %H:%M:%S'), body_text),
                Paragraph(row['estacao_recebimento'], body_text),
                Paragraph(row['estacao_registro'], body_text),
                Paragraph(row['status'], st_style)
            ])
    # Se nao houver nenhuma pendencia no periodo, insere linha informativa
    else:
        # Linha informativa vazia
        pending_table_rows.append([
            Paragraph("Nenhuma ocorrência pendente no período analisado.", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text)
        ])
        
    # Instancia a tabela final das ocorrencias definindo a largura das colunas
    # Nota: Colunas somam exatamente 761 de largura (130 + 140 + 160 + 160 + 171). 
    # repeatRows=1 faz o cabecalho se repetir em todas as paginas caso ocorra quebra de paginas
    pending_table = Table(pending_table_rows, colWidths=[130, 140, 160, 160, 171], repeatRows=1)
    # Estiliza com fundo colorido no cabecalho, zebra nas linhas e divisoria fina
    pending_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    # Adiciona a tabela de ocorrencias pendentes ao fluxo do PDF
    story.append(pending_table)
    
    # Inicia a geracao fisica do PDF a partir dos elementos contidos no story
    # Passa a classe NumberedCanvas em canvasmaker para realizar as duas passadas de paginacao
    doc.build(story, canvasmaker=NumberedCanvas)
    
    # Move o cursor de leitura do buffer em memoria de volta para o comeco (posicao 0)
    buffer.seek(0)
    
    # Captura a data/hora atual formatada para compor o nome do arquivo final de download
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    # Define o nome exato do arquivo requisitado: Relatorio_Logistico_AAAAMMDD_HHMM.pdf
    filename = f"Relatorio_Logistico_{now_str}.pdf"
    
    # Retorna o arquivo de bytes gerado como anexo pronto para download imediato no browser
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

@app.route('/api/sem_mov/filters')
def get_sem_mov_filters():
    df = load_sem_mov_data()
    if df.empty:
        return jsonify({
            'aging': [],
            'base': [],
            'destino': []
        })
    
    aging_list = sorted(df['aging'].unique().tolist())
    if 'Não informado' in aging_list:
        aging_list.remove('Não informado')
        aging_list.append('Não informado')
        
    base_list = sorted(df['base'].unique().tolist())
    if 'Não informado' in base_list:
        base_list.remove('Não informado')
        base_list.append('Não informado')
        
    destino_list = sorted(df['destino'].unique().tolist())
    if 'Não informado' in destino_list:
        destino_list.remove('Não informado')
        destino_list.append('Não informado')
        
    return jsonify({
        'aging': aging_list,
        'base': base_list,
        'destino': destino_list
    })

@app.route('/api/sem_mov/data')
def get_sem_mov_data():
    df = load_sem_mov_data()
    if df.empty:
        return jsonify([])
    
    filtered_df = filter_sem_mov_dataframe(df, request.args)
    
    search = request.args.get('search', '').strip().lower()
    if search:
        filtered_df = filtered_df[filtered_df['remessa'].str.lower().str.contains(search)]
        
    if filtered_df.empty:
        return jsonify([])

    cols = ['remessa', 'ultima_operacao', 'base_responsavel', 'ultima_operacao_tipo', 'tipo_problematico', 'aging', 'dias_sem_mov', 'multa', 'base', 'destino']
    df_out = filtered_df[cols].copy()
    df_out['ultima_operacao'] = df_out['ultima_operacao'].dt.strftime('%d/%m/%Y %H:%M:%S')
    df_out['dias_sem_mov'] = df_out['dias_sem_mov'].astype(int)
    df_out['multa'] = df_out['multa'].astype(float)
    return jsonify(df_out.to_dict(orient='records'))

@app.route('/api/sem_mov/generate_pdf')
def generate_sem_mov_pdf():
    df = load_sem_mov_data()
    if df.empty:
        return "Erro: Base de dados vazia ou não encontrada.", 404
        
    filtered_df = filter_sem_mov_dataframe(df, request.args)
    total_records = len(filtered_df)
    
    total_multa = float(filtered_df['multa'].sum())
    avg_dias = float(filtered_df['dias_sem_mov'].mean()) if total_records > 0 else 0.0
    max_dias = int(filtered_df['dias_sem_mov'].max()) if total_records > 0 else 0
    
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CoverTitleSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitleSM',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=30
    )
    
    metadata_label = ParagraphStyle(
        'MetaLabelSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#1F2937')
    )
    
    metadata_value = ParagraphStyle(
        'MetaValueSM',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    
    section_title = ParagraphStyle(
        'SectionTitleSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=10
    )
    
    body_bold = ParagraphStyle(
        'BodyBoldSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1F2937')
    )
    
    body_text = ParagraphStyle(
        'BodyTextSM',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#4B5563')
    )
    
    body_text_white = ParagraphStyle(
        'BodyTextWhiteSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    
    card_title = ParagraphStyle(
        'CardTitleSM',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#4B5563'),
        alignment=1
    )
    
    card_value = ParagraphStyle(
        'CardValueSM',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    story = []
    
    # ----------------------------------------------------
    # PAGE 1: CAPA
    # ----------------------------------------------------
    story.append(Spacer(1, 100))
    story.append(Paragraph("Relatório de Remessas Sem Movimentação", title_style))
    story.append(Paragraph("Visão Executiva de Atrasos e Multas Operacionais", subtitle_style))
    story.append(Spacer(1, 40))
    
    meta_data = [
        [Paragraph("Data e hora de geração:", metadata_label), Paragraph(datetime.now().strftime('%d/%m/%Y às %H:%M'), metadata_value)],
        [Paragraph("Contratos Analisados:", metadata_label), Paragraph(f"{total_records} remessas", metadata_value)],
        [Paragraph("Filtros Aplicados:", metadata_label), Paragraph("Geral" if all(v == 'Todas' or v == 'Todos' or v == '' for v in request.args.values()) else "Filtrado", metadata_value)]
    ]
    meta_table = Table(meta_data, colWidths=[150, 400])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 2: RESUMO EXECUTIVO & MULTAS
    # ----------------------------------------------------
    story.append(Paragraph("Resumo Executivo & Multas Operacionais", section_title))
    
    kpi_data = [
        [
            Paragraph("TOTAL SEM MOVIMENTAÇÃO", card_title),
            Paragraph("MULTA ACUMULADA", card_title),
            Paragraph("MÉDIA DIAS SEM MOVIMENTO", card_title),
            Paragraph("MAIOR ATRASO REGISTRADO", card_title)
        ],
        [
            Paragraph(f"{total_records}", card_value),
            Paragraph(f"R$ {total_multa:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), card_value),
            Paragraph(f"{avg_dias:.1f} dias", card_value),
            Paragraph(f"{max_dias} dias", card_value)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[190, 190, 190, 190])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))
    
    left_flowables = []
    left_flowables.append(Paragraph("Insights Operacionais", ParagraphStyle('SubSM1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'))))
    
    insights_html = f"""
    Foram identificadas <b>{total_records}</b> remessas em atraso na operação.<br/><br/>
    O valor total projetado em multas operacionais acumula <b>R$ {total_multa:,.2f}</b>.<br/><br/>
    O atraso médio das remessas sem movimentação é de <b>{avg_dias:.1f} dias</b>, com um pico crítico de <b>{max_dias} dias</b> no maior atraso encontrado.<br/><br/>
    Esses atrasos geram custos operacionais e penalidades diretas por descumprimento de prazos.
    """.replace(",", "X").replace(".", ",").replace("X", ".")
    
    left_flowables.append(Paragraph(insights_html, ParagraphStyle('InsBodySM', parent=body_text, fontSize=9.5, leading=14)))
    
    right_flowables = []
    right_flowables.append(Paragraph("Distribuição por Aging", ParagraphStyle('SubSM2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'), alignment=1)))
    
    aging_counts = filtered_df['aging'].value_counts()
    
    pie_drawing = Drawing(300, 200)
    pc = Pie()
    pc.x = 80
    pc.y = 30
    pc.width = 140
    pc.height = 140
    
    if total_records > 0:
        pc.data = aging_counts.values.tolist()
        pc.labels = [f"{lbl} ({val})" for lbl, val in zip(aging_counts.index, aging_counts.values)]
        
        pie_colors = [
            colors.HexColor('#EF4444'),
            colors.HexColor('#F59E0B'),
            colors.HexColor('#3B82F6'),
            colors.HexColor('#10B981'),
            colors.HexColor('#8B5CF6'),
            colors.HexColor('#EC4899'),
            colors.HexColor('#6B7280'),
            colors.HexColor('#111827')
        ]
        for idx in range(len(aging_counts)):
            pc.slices[idx].fillColor = pie_colors[idx % len(pie_colors)]
    else:
        pc.data = [1]
        pc.labels = ['Sem dados']
        pc.slices[0].fillColor = colors.HexColor('#E5E7EB')
        
    pc.slices.strokeWidth = 0.5
    pc.slices.strokeColor = colors.white
    pie_drawing.add(pc)
    right_flowables.append(pie_drawing)
    
    layout_data = [[left_flowables, right_flowables]]
    layout_table = Table(layout_data, colWidths=[420, 341])
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 3: ANÁLISE POR BASE E DESTINO
    # ----------------------------------------------------
    story.append(Paragraph("Análise de Contratos por Base e Destino", section_title))
    
    base_counts = filtered_df['base'].value_counts()
    dest_counts = filtered_df['destino'].value_counts()
    
    base_headers = [Paragraph("Base Origem", body_text_white), Paragraph("Remessas", body_text_white), Paragraph("Percentual", body_text_white)]
    base_rows = [base_headers]
    if total_records > 0:
        for b, count in base_counts.items():
            pct = (count / total_records) * 100
            base_rows.append([Paragraph(b, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    else:
        base_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    base_table = Table(base_rows, colWidths=[180, 95, 80])
    base_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    dest_headers = [Paragraph("Destino", body_text_white), Paragraph("Remessas", body_text_white), Paragraph("Percentual", body_text_white)]
    dest_rows = [dest_headers]
    if total_records > 0:
        top_n = 8
        if len(dest_counts) > top_n:
            top_dest = dest_counts.head(top_n)
            other_sum = dest_counts.iloc[top_n:].sum()
            for d, count in top_dest.items():
                pct = (count / total_records) * 100
                dest_rows.append([Paragraph(d, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
            dest_rows.append([Paragraph("Outros Destinos", body_bold), Paragraph(f"{other_sum}", body_bold), Paragraph(f"{(other_sum/total_records)*100:.1f}%", body_bold)])
        else:
            for d, count in dest_counts.items():
                pct = (count / total_records) * 100
                dest_rows.append([Paragraph(d, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    else:
        dest_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    dest_table = Table(dest_rows, colWidths=[180, 95, 80])
    dest_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    left_side = [
        Paragraph("Quantidade por Base", ParagraphStyle('BaseTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        base_table
    ]
    
    right_side = [
        Paragraph("Quantidade por Destino (Top 8)", ParagraphStyle('DestTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        dest_table
    ]
    
    layout_table_2 = Table([[left_side, right_side]], colWidths=[380, 381])
    layout_table_2.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table_2)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 4: DETALHAMENTO DE CONTRATOS SEM MOVIMENTAÇÃO
    # ----------------------------------------------------
    story.append(Paragraph("Detalhamento de Remessas Sem Movimentação", section_title))
    story.append(Paragraph("Lista de remessas sem movimentação registradas sob o filtro ativo (exibindo as 30 mais críticas com maior atraso):", ParagraphStyle('SMDesc', parent=body_text, spaceAfter=10)))
    
    pending_headers = [
        Paragraph("Remessa", body_text_white),
        Paragraph("Última Op.", body_text_white),
        Paragraph("Problema", body_text_white),
        Paragraph("Aging", body_text_white),
        Paragraph("Dias", body_text_white),
        Paragraph("Multa", body_text_white),
        Paragraph("Origem", body_text_white),
        Paragraph("Destino", body_text_white)
    ]
    
    pending_table_rows = [pending_headers]
    if not filtered_df.empty:
        sorted_sm = filtered_df.sort_values(by='dias_sem_mov', ascending=False)
        for _, row in sorted_sm.head(30).iterrows():
            pending_table_rows.append([
                Paragraph(row['remessa'], body_text),
                Paragraph(row['ultima_operacao'].strftime('%d/%m/%Y'), body_text),
                Paragraph(row['tipo_problematico'], body_text),
                Paragraph(row['aging'], body_text),
                Paragraph(f"{int(row['dias_sem_mov'])} d", body_text),
                Paragraph(f"R$ {float(row['multa']):.2f}", body_text),
                Paragraph(row['base'], body_text),
                Paragraph(row['destino'], body_text)
            ])
    else:
        pending_table_rows.append([
            Paragraph("Nenhuma ocorrência encontrada.", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text)
        ])
        
    pending_table = Table(pending_table_rows, colWidths=[90, 70, 190, 110, 50, 60, 90, 101], repeatRows=1)
    pending_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(pending_table)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    
    buffer.seek(0)
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Relatorio_Sem_Movimentacao_{now_str}.pdf"
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# ====================================================
# SEÇÃO DO MÓDULO DE AVARIAS
# ====================================================

AVARIA_FILE = "avaria.xlsx"

def _load_avaria_data_raw(file_path=AVARIA_FILE):
    # Tenta baixar a versão mais recente das avarias do Google Sheets apenas se o cache expirou (30 segundos)
    global _last_avaria_download_time
    import time
    cache_limit = 30  # segundos
    file_exists = os.path.exists(AVARIA_FILE)
    is_recent = file_exists and (time.time() - _last_avaria_download_time < cache_limit)
    
    if not file_exists:
        try:
            url = 'https://docs.google.com/spreadsheets/d/1j7i4WmvzNUDHD6s7HqUUEcwRFjusk25hHD6I3qelLRU/export?format=xlsx'
            import urllib.request
            # Download com timeout de 15s para evitar travamento da requisição (apenas na primeira carga do app)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=15) as response:
                with open(AVARIA_FILE, 'wb') as f:
                    f.write(response.read())
            _last_avaria_download_time = time.time()
        except Exception as e_dl:
            print(f"Erro ao baixar planilha de avarias do Google Sheets de forma síncrona: {e_dl}.")
    elif not is_recent:
        # Se o arquivo já existe mas está antigo, atualiza em segundo plano sem bloquear a requisição atual
        url = 'https://docs.google.com/spreadsheets/d/1j7i4WmvzNUDHD6s7HqUUEcwRFjusk25hHD6I3qelLRU/export?format=xlsx'
        download_in_background(url, AVARIA_FILE)
        _last_avaria_download_time = time.time()

    if not os.path.exists(file_path):
        return pd.DataFrame()
    
    try:
        # Leitura de todas as abas que representam datas (ex: 30.06, 01.07) e concatenação delas em memória para evitar travar o arquivo no disco (Windows)
        import openpyxl
        import re
        date_sheet_pattern = re.compile(r'^\d{2}\.\d{2}$')
        
        with open(file_path, 'rb') as f:
            file_bytes = io.BytesIO(f.read())
            
        dfs = []
        with pd.ExcelFile(file_bytes, engine='openpyxl') as xl:
            sheet_names = [s for s in xl.sheet_names if date_sheet_pattern.match(s)]
            if not sheet_names:
                sheet_names = xl.sheet_names
            
            for sheet_name in sheet_names:
                df_sheet = pd.read_excel(xl, sheet_name=sheet_name)
                if not df_sheet.empty:
                    dfs.append(df_sheet)
                
        if not dfs:
            return pd.DataFrame()
            
        df = pd.concat(dfs, ignore_index=True)
        
        # Padroniza nomes das colunas
        df.columns = [c.strip().lower() for c in df.columns]
        
        # Mapeia nomes das colunas para remover espaços e caracteres especiais
        df = df.rename(columns={
            'id de viagem': 'id_de_viagem',
            'base de origem': 'base_de_origem',
            'id produto': 'id_produto'
        })
        
        # Ignora linhas onde qualquer uma das colunas obrigatórias está vazia/nula (deve estar 100% preenchida)
        cols_to_check = ['data', 'id_de_de_viagem', 'base_de_origem', 'produto', 'status', 'id_produto', 'nome']
        # Corrige possíveis nomes errados se existirem
        cols_to_check = ['data', 'id_de_viagem', 'base_de_origem', 'produto', 'status', 'id_produto', 'nome']
        df = df.dropna(subset=[c for c in cols_to_check if c in df.columns])
        
        for col in cols_to_check:
            if col in df.columns:
                df = df[df[col].astype(str).str.strip() != '']
                df = df[df[col].astype(str).str.strip().str.lower() != 'nan']
            
        # Converte coluna de data para datetime
        df['data'] = pd.to_datetime(df['data'], errors='coerce')
        df = df.dropna(subset=['data'])
        
        # Preenche campos nulos e formata strings
        df['id_de_viagem'] = df['id_de_viagem'].astype(str).str.strip()
        df['base_de_origem'] = df['base_de_origem'].fillna('Não informado').astype(str).str.strip()
        df['produto'] = df['produto'].fillna('Outros').astype(str).str.strip().str.title()
        df['status'] = df['status'].fillna('Não informado').astype(str).str.strip()
        df['nome'] = df['nome'].fillna('Não informado').astype(str).str.strip()
        df['id_produto'] = pd.to_numeric(df['id_produto'], errors='coerce').fillna(0).astype(int)
        
        # Padroniza Status e Nomes
        df['status'] = df['status'].str.strip().str.title()
        df['nome'] = df['nome'].str.strip().str.title()
        
        # Ordena decrescente pela data da ocorrência
        df = df.sort_values(by='data', ascending=False)
        
        return df
    except Exception as e:
        print(f"Erro ao processar arquivo de avarias: {e}")
        return pd.DataFrame()

# Funcao publica com cache em memoria para evitar leituras repetidas do disco
def load_avaria_data():
    file_path = AVARIA_FILE
    temp_path = AVARIA_FILE + ".tmp"
    
    # Se o arquivo temporário existe e é mais recente que o arquivo principal,
    # usamos o arquivo temporário como fonte de dados ativa (evita travamento por Excel no Windows).
    active_file = file_path
    if os.path.exists(temp_path):
        if not os.path.exists(file_path) or os.path.getmtime(temp_path) > os.path.getmtime(file_path):
            active_file = temp_path
            
    return get_from_cache(active_file, _load_avaria_data_raw, active_file)

def filter_avaria_dataframe(df, filters):
    if df.empty:
        return df
        
    start_date = filters.get('start_date')
    end_date = filters.get('end_date')
    base = filters.get('base')
    colaborador = filters.get('colaborador')
    produto = filters.get('produto')
    status = filters.get('status')
    
    filtered_df = df.copy()
    
    # Filtros de data
    if start_date:
        filtered_df = filtered_df[filtered_df['data'] >= pd.to_datetime(start_date)]
    if end_date:
        end_dt = pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)
        filtered_df = filtered_df[filtered_df['data'] <= end_dt]
        
    # Filtros categóricos
    if base and base != 'Todas':
        filtered_df = filtered_df[filtered_df['base_de_origem'] == base]
    if colaborador and colaborador != 'Todos':
        filtered_df = filtered_df[filtered_df['nome'] == colaborador]
    if produto and produto != 'Todos':
        filtered_df = filtered_df[filtered_df['produto'] == produto]
    if status and status != 'Todos':
        filtered_df = filtered_df[filtered_df['status'] == status]
        
    return filtered_df

# Endpoint de filtros de Avarias
@app.route('/api/avaria/filters')
def get_avaria_filters():
    df = load_avaria_data()
    if df.empty:
        return jsonify({
            'base': [],
            'colaborador': [],
            'produto': [],
            'status': [],
            'min_date': '',
            'max_date': ''
        })
        
    base_list = sorted(df['base_de_origem'].unique().tolist())
    colab_list = sorted(df['nome'].unique().tolist())
    prod_list = sorted(df['produto'].unique().tolist())
    status_list = sorted(df['status'].unique().tolist())
    
    min_date = df['data'].min().strftime('%Y-%m-%d')
    max_date = df['data'].max().strftime('%Y-%m-%d')
    
    return jsonify({
        'base': base_list,
        'colaborador': colab_list,
        'produto': prod_list,
        'status': status_list,
        'min_date': min_date,
        'max_date': max_date
    })

# Endpoint de dados de Avarias
@app.route('/api/avaria/data')
def get_avaria_data():
    df = load_avaria_data()
    if df.empty:
        return jsonify([])
        
    filtered_df = filter_avaria_dataframe(df, request.args)
    
    search = request.args.get('search', '').strip().lower()
    if search:
        # Busca por id de viagem, id do produto, nome do colaborador ou produto
        filtered_df = filtered_df[
            filtered_df['id_de_viagem'].str.lower().str.contains(search) |
            filtered_df['id_produto'].astype(str).str.contains(search) |
            filtered_df['nome'].str.lower().str.contains(search) |
            filtered_df['produto'].str.lower().str.contains(search)
        ]
        
    if filtered_df.empty:
        return jsonify([])

    df_out = pd.DataFrame({
        'data': filtered_df['data'].dt.strftime('%d/%m/%Y'),
        'id_de_viagem': filtered_df['id_de_viagem'].fillna('-').astype(str).str.strip().replace({'nan': '-', 'None': '-'}),
        'base_de_origem': filtered_df['base_de_origem'].fillna('-').astype(str).str.strip(),
        'produto': filtered_df['produto'].fillna('-').astype(str).str.strip(),
        'status': filtered_df['status'].fillna('-').astype(str).str.strip(),
        'id_produto': filtered_df['id_produto'].fillna(0).astype(int),
        'nome': filtered_df['nome'].fillna('-').astype(str).str.strip()
    })
    return jsonify(df_out.to_dict(orient='records'))

# Endpoint de dados de Avarias com histórico de 5 dias para o gráfico de evolução
@app.route('/api/avaria/data_evolution')
def get_avaria_data_evolution():
    df = load_avaria_data()
    if df.empty:
        return jsonify([])
        
    # Copia os filtros da requisição para poder modificar a data inicial
    filters = dict(request.args)
    start_date = filters.get('start_date')
    if start_date:
        try:
            # Subtrai 5 dias da data de início selecionada
            dt = pd.to_datetime(start_date)
            filters['start_date'] = (dt - pd.Timedelta(days=5)).strftime('%Y-%m-%d')
        except Exception as e:
            pass
            
    filtered_df = filter_avaria_dataframe(df, filters)
    
    search = request.args.get('search', '').strip().lower()
    if search:
        filtered_df = filtered_df[
            filtered_df['id_de_viagem'].str.lower().str.contains(search) |
            filtered_df['id_produto'].astype(str).str.contains(search) |
            filtered_df['nome'].str.lower().str.contains(search) |
            filtered_df['produto'].str.lower().str.contains(search)
        ]
        
    if filtered_df.empty:
        return jsonify([])

    df_out = pd.DataFrame({
        'data': filtered_df['data'].dt.strftime('%d/%m/%Y'),
        'id_de_viagem': filtered_df['id_de_viagem'].fillna('-').astype(str).str.strip().replace({'nan': '-', 'None': '-'}),
        'base_de_origem': filtered_df['base_de_origem'].fillna('-').astype(str).str.strip(),
        'produto': filtered_df['produto'].fillna('-').astype(str).str.strip(),
        'status': filtered_df['status'].fillna('-').astype(str).str.strip(),
        'id_produto': filtered_df['id_produto'].fillna(0).astype(int),
        'nome': filtered_df['nome'].fillna('-').astype(str).str.strip()
    })
    return jsonify(df_out.to_dict(orient='records'))

# Endpoint do Relatório PDF de Avarias
@app.route('/api/avaria/generate_pdf')
def generate_avaria_pdf():
    df = load_avaria_data()
    if df.empty:
        return "Erro: Base de dados vazia ou não encontrada.", 404
        
    filtered_df = filter_avaria_dataframe(df, request.args)
    total_records = len(filtered_df)
    
    # Métricas consolidadas
    unique_colabs = filtered_df['nome'].nunique() if total_records > 0 else 0
    unique_viagens = filtered_df['id_de_viagem'].nunique() if total_records > 0 else 0
    top_product = filtered_df['produto'].mode()[0] if total_records > 0 and not filtered_df['produto'].empty else 'N/A'
    
    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=40,
        rightMargin=40,
        topMargin=50,
        bottomMargin=50
    )
    
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle(
        'CoverTitleAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=28,
        leading=34,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=15
    )
    
    subtitle_style = ParagraphStyle(
        'CoverSubtitleAV',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=30
    )
    
    metadata_label = ParagraphStyle(
        'MetaLabelAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#1F2937')
    )
    
    metadata_value = ParagraphStyle(
        'MetaValueAV',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=11,
        leading=14,
        textColor=colors.HexColor('#4B5563')
    )
    
    section_title = ParagraphStyle(
        'SectionTitleAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=10
    )
    
    body_bold = ParagraphStyle(
        'BodyBoldAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#1F2937')
    )
    
    body_text = ParagraphStyle(
        'BodyTextAV',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#4B5563')
    )
    
    body_text_white = ParagraphStyle(
        'BodyTextWhiteAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )
    
    card_title = ParagraphStyle(
        'CardTitleAV',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#4B5563'),
        alignment=1
    )
    
    card_value = ParagraphStyle(
        'CardValueAV',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1
    )
    
    story = []
    
    # ----------------------------------------------------
    # PAGE 1: CAPA
    # ----------------------------------------------------
    story.append(Spacer(1, 100))
    story.append(Paragraph("Relatório de Controle de Avarias", title_style))
    story.append(Paragraph("Visão Executiva de Danos a Produtos e Status de Liberação", subtitle_style))
    story.append(Spacer(1, 40))
    
    meta_data = [
        [Paragraph("Data e hora de geração:", metadata_label), Paragraph(datetime.now().strftime('%d/%m/%Y às %H:%M'), metadata_value)],
        [Paragraph("Avarias Registradas:", metadata_label), Paragraph(f"{total_records} ocorrências", metadata_value)],
        [Paragraph("Filtros Aplicados:", metadata_label), Paragraph("Geral" if all(v == 'Todas' or v == 'Todos' or v == '' for v in request.args.values()) else "Filtrado", metadata_value)]
    ]
    meta_table = Table(meta_data, colWidths=[150, 400])
    meta_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(meta_table)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 2: RESUMO EXECUTIVO & KPIs
    # ----------------------------------------------------
    story.append(Paragraph("Resumo Executivo & Status de Avarias", section_title))
    
    kpi_data = [
        [
            Paragraph("TOTAL AVARIAS", card_title),
            Paragraph("COLABORADORES", card_title),
            Paragraph("TOTAL VIAGENS (CARROS)", card_title),
            Paragraph("PRODUTO MAIS AFETADO", card_title)
        ],
        [
            Paragraph(f"{total_records}", card_value),
            Paragraph(f"{unique_colabs}", card_value),
            Paragraph(f"{unique_viagens}", card_value),
            Paragraph(f"{top_product}", card_value)
        ]
    ]
    kpi_table = Table(kpi_data, colWidths=[190, 190, 190, 190])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 15))
    
    left_flowables = []
    left_flowables.append(Paragraph("Insights de Operação", ParagraphStyle('SubAV1', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'))))
    
    insights_html = f"""
    Durante o período de análise, foram consolidadas <b>{total_records}</b> ocorrências de avarias no sistema.<br/><br/>
    Um total de <b>{unique_colabs}</b> colaboradores foram mapeados com ocorrências ativas, distribuídos em <b>{unique_viagens}</b> viagens (carros) diferentes.<br/><br/>
    O produto com maior incidência de avarias é <b>{top_product}</b>.<br/><br/>
    O monitoramento constante dessas ocorrências por viagem e equipe de colaboradores ajuda a reduzir perdas e otimizar processos logísticos.
    """
    left_flowables.append(Paragraph(insights_html, ParagraphStyle('InsBodyAV', parent=body_text, fontSize=9.5, leading=14)))
    
    right_flowables = []
    right_flowables.append(Paragraph("Classificação (Status)", ParagraphStyle('SubAV2', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=11, leading=14, spaceAfter=8, textColor=colors.HexColor('#1E3A8A'), alignment=1)))
    
    status_counts = filtered_df['status'].value_counts()
    
    pie_drawing = Drawing(300, 200)
    pc = Pie()
    pc.x = 80
    pc.y = 30
    pc.width = 140
    pc.height = 140
    
    if total_records > 0:
        pc.data = status_counts.values.tolist()
        pc.labels = [f"{lbl} ({val})" for lbl, val in zip(status_counts.index, status_counts.values)]
        
        pie_colors = [
            colors.HexColor('#3B82F6'),
            colors.HexColor('#EF4444'),
            colors.HexColor('#F59E0B'),
            colors.HexColor('#10B981'),
            colors.HexColor('#8B5CF6'),
            colors.HexColor('#EC4899')
        ]
        for idx in range(len(status_counts)):
            pc.slices[idx].fillColor = pie_colors[idx % len(pie_colors)]
    else:
        pc.data = [1]
        pc.labels = ['Sem dados']
        pc.slices[0].fillColor = colors.HexColor('#E5E7EB')
        
    pc.slices.strokeWidth = 0.5
    pc.slices.strokeColor = colors.white
    pie_drawing.add(pc)
    right_flowables.append(pie_drawing)
    
    layout_table = Table([[left_flowables, right_flowables]], colWidths=[420, 341])
    layout_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 3: ANÁLISE POR COLABORADOR E PRODUTO
    # ----------------------------------------------------
    story.append(Paragraph("Distribuição por Colaborador e Categoria de Produto", section_title))
    
    colab_counts = filtered_df['nome'].value_counts()
    prod_counts = filtered_df['produto'].value_counts()
    
    colab_headers = [Paragraph("Colaborador", body_text_white), Paragraph("Ocorrências", body_text_white), Paragraph("Percentual", body_text_white)]
    colab_rows = [colab_headers]
    if total_records > 0:
        top_c = 8
        if len(colab_counts) > top_c:
            top_colabs = colab_counts.head(top_c)
            other_sum_c = colab_counts.iloc[top_c:].sum()
            for c, count in top_colabs.items():
                pct = (count / total_records) * 100
                colab_rows.append([Paragraph(c, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
            colab_rows.append([Paragraph("Outros Colaboradores", body_bold), Paragraph(f"{other_sum_c}", body_bold), Paragraph(f"{(other_sum_c/total_records)*100:.1f}%", body_bold)])
        else:
            for c, count in colab_counts.items():
                pct = (count / total_records) * 100
                colab_rows.append([Paragraph(c, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    else:
        colab_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    colab_table = Table(colab_rows, colWidths=[180, 95, 80])
    colab_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    prod_headers = [Paragraph("Produto", body_text_white), Paragraph("Ocorrências", body_text_white), Paragraph("Percentual", body_text_white)]
    prod_rows = [prod_headers]
    if total_records > 0:
        top_p = 8
        if len(prod_counts) > top_p:
            top_prods = prod_counts.head(top_p)
            other_sum_p = prod_counts.iloc[top_p:].sum()
            for p, count in top_prods.items():
                pct = (count / total_records) * 100
                prod_rows.append([Paragraph(p, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
            prod_rows.append([Paragraph("Outros Produtos", body_bold), Paragraph(f"{other_sum_p}", body_bold), Paragraph(f"{(other_sum_p/total_records)*100:.1f}%", body_bold)])
        else:
            for p, count in prod_counts.items():
                pct = (count / total_records) * 100
                prod_rows.append([Paragraph(p, body_text), Paragraph(f"{count}", body_text), Paragraph(f"{pct:.1f}%", body_text)])
    else:
        prod_rows.append([Paragraph("Sem dados", body_text), Paragraph("0", body_text), Paragraph("0%", body_text)])
        
    prod_table = Table(prod_rows, colWidths=[180, 95, 80])
    prod_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    left_side = [
        Paragraph("Avarias por Colaborador", ParagraphStyle('ColabTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        colab_table
    ]
    
    right_side = [
        Paragraph("Avarias por Categoria de Produto", ParagraphStyle('ProdTitle', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=10, leading=12, spaceAfter=5, textColor=colors.HexColor('#1E3A8A'))),
        prod_table
    ]
    
    layout_table_2 = Table([[left_side, right_side]], colWidths=[380, 381])
    layout_table_2.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 0),
        ('TOPPADDING', (0,0), (-1,-1), 0),
    ]))
    story.append(layout_table_2)
    
    story.append(PageBreak())
    
    # ----------------------------------------------------
    # PAGE 4: DETALHAMENTO DE AVARIAS
    # ----------------------------------------------------
    story.append(Paragraph("Detalhamento de Ocorrências de Avarias", section_title))
    story.append(Paragraph("Lista contendo as ocorrências de avarias sob os filtros ativos (top 30 mais recentes):", ParagraphStyle('AVDesc', parent=body_text, spaceAfter=10)))
    
    pending_headers = [
        Paragraph("Data", body_text_white),
        Paragraph("ID de Viagem (Carro)", body_text_white),
        Paragraph("Base", body_text_white),
        Paragraph("Produto", body_text_white),
        Paragraph("Status", body_text_white),
        Paragraph("Colaborador", body_text_white)
    ]
    
    pending_table_rows = [pending_headers]
    if not filtered_df.empty:
        sorted_df = filtered_df.sort_values(by='data', ascending=False)
        for _, row in sorted_df.head(30).iterrows():
            pending_table_rows.append([
                Paragraph(row['data'].strftime('%d/%m/%Y'), body_text),
                Paragraph(row['id_de_viagem'], body_text),
                Paragraph(row['base_de_origem'], body_text),
                Paragraph(row['produto'], body_text),
                Paragraph(row['status'], body_text),
                Paragraph(row['nome'], body_text)
            ])
    else:
        pending_table_rows.append([
            Paragraph("Nenhuma ocorrência encontrada.", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text),
            Paragraph("", body_text)
        ])
        
    pending_table = Table(pending_table_rows, colWidths=[80, 140, 60, 140, 180, 161], repeatRows=1)
    pending_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0,0), (-1,-1), 'LEFT'),
        ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ('TOPPADDING', (0,0), (-1,-1), 4),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    
    story.append(pending_table)
    
    doc.build(story, canvasmaker=NumberedCanvas)
    
    buffer.seek(0)
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Relatorio_Avarias_{now_str}.pdf"
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

def _load_controle_bau_data_raw(file_path=CONTROLE_BAU_FILE):
    # Tenta baixar a versão mais recente do Google Sheets apenas se o cache expirou (30 segundos)
    global _last_controle_download_time
    import time
    cache_limit = 120  # segundos (evita downloads repetidos em intervalos curtíssimos)
    file_exists = os.path.exists(CONTROLE_BAU_FILE)
    is_recent = file_exists and (time.time() - _last_controle_download_time < cache_limit)
    
    if not file_exists:
        try:
            url = 'https://docs.google.com/spreadsheets/d/1-56uyCw7VeyyCKIOQqLGtbgyOqmfSIJRG-N9_rbuGWE/export?format=xlsx'
            import urllib.request
            # Download com timeout de 10s para evitar travamento da requisição (apenas na primeira carga do app)
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                with open(CONTROLE_BAU_FILE, 'wb') as f:
                    f.write(response.read())
            _last_controle_download_time = time.time()
        except Exception as e_dl:
            print(f"Erro ao baixar planilha do Google Sheets de forma síncrona: {e_dl}.")
    elif not is_recent:
        # Se o arquivo já existe mas está antigo, atualiza em segundo plano sem bloquear a requisição atual
        url = 'https://docs.google.com/spreadsheets/d/1-56uyCw7VeyyCKIOQqLGtbgyOqmfSIJRG-N9_rbuGWE/export?format=xlsx'
        download_in_background(url, CONTROLE_BAU_FILE)
        _last_controle_download_time = time.time()

    if not os.path.exists(file_path):
        return None
    
    try:
        # Abre o arquivo em memória para evitar travá-lo no Windows durante operações concorrentes
        with open(file_path, 'rb') as f:
            file_bytes = io.BytesIO(f.read())
            
        with pd.ExcelFile(file_bytes, engine='openpyxl') as xl:
            sheet_names = xl.sheet_names
            
            # Carrega horários de corte dinâmicos se a aba "Corte" existir
            corte_map = {}
            corte_sheet = next((s for s in sheet_names if s.upper() == "CORTE"), None)
            if corte_sheet:
                try:
                    df_corte = pd.read_excel(xl, sheet_name=corte_sheet)
                    col_rota = None
                    col_hora = None
                    for col in df_corte.columns:
                        col_str = str(col).strip().upper()
                        if "ROTA" in col_str:
                            col_rota = col
                        elif "HORA" in col_str or "PREVISTA" in col_str or "CORTE" in col_str:
                            col_hora = col
                            
                    if col_rota is not None and col_hora is not None:
                        for _, row_c in df_corte.iterrows():
                            r_val = row_c[col_rota]
                            h_val = row_c[col_hora]
                            if pd.notna(r_val) and pd.notna(h_val):
                                route_name = str(r_val).strip()
                                if isinstance(h_val, pd.Timestamp):
                                    time_str = h_val.strftime('%H:%M')
                                elif type(h_val).__name__ == 'time':
                                    time_str = h_val.strftime('%H:%M')
                                else:
                                    h_str = str(h_val).strip()
                                    import re
                                    m = re.match(r'^(\d{1,2}):(\d{2})', h_str)
                                    if m:
                                        time_str = f"{int(m.group(1)):02d}:{m.group(2)}"
                                    else:
                                        time_str = h_str
                                corte_map[route_name] = time_str
                except Exception as e_corte:
                    print(f"Erro ao ler aba Corte: {e_corte}")

            kpis = {}
            recebimento_vol = {}
            expedicao_vol = {}
            taxa_expedicao_prazo = {"items": [], "totais": {}}
            
            if "Gemini" in sheet_names:
                df_gemini = pd.read_excel(xl, sheet_name="Gemini", header=None)
                current_section = None
                for idx, row in df_gemini.iterrows():
                    key = row[1]
                    val = row[2]
                    if pd.notna(key):
                        key_str = str(key).strip()
                        if key_str == "INF GERAIS":
                            current_section = "geral"
                            continue
                        elif key_str == "RECEBIMENTO":
                            current_section = "recebimento"
                            continue
                        elif key_str in ["EXPEDIÇÃO", "EXPEDICAO"]:
                            current_section = "expedicao"
                            continue
                        
                        if isinstance(val, pd.Timestamp):
                            val_formatted = val.strftime('%Y-%m-%d')
                        elif isinstance(val, (int, float)):
                            if pd.isna(val):
                                val_formatted = 0
                            elif isinstance(val, float) and val.is_integer():
                                val_formatted = int(val)
                            else:
                                val_formatted = val
                        else:
                            val_formatted = str(val).strip()
                        
                        if current_section == "geral":
                            kpis[key_str] = val_formatted
                        elif current_section == "recebimento":
                            recebimento_vol[key_str] = val_formatted
                        elif current_section == "expedicao":
                            expedicao_vol[key_str] = val_formatted
            elif "Operacao" in sheet_names:
                df_oper = pd.read_excel(xl, sheet_name="Operacao", header=None)
                
                def get_val(r, c):
                    if r < len(df_oper) and c < len(df_oper.columns):
                        val = df_oper.iloc[r, c]
                        if pd.notna(val):
                            if isinstance(val, pd.Timestamp):
                                return val.strftime('%Y-%m-%d')
                            elif isinstance(val, (int, float)):
                                if isinstance(val, float) and val.is_integer():
                                    return int(val)
                                return val
                            return str(val).strip()
                    return 0
                    
                date_val = "-"
                for col_idx in range(len(df_oper.columns)):
                    cell = df_oper.iloc[0, col_idx]
                    if pd.notna(cell) and ("202" in str(cell) or isinstance(cell, pd.Timestamp)):
                        if isinstance(cell, pd.Timestamp):
                            date_val = cell.strftime('%Y-%m-%d')
                        else:
                            date_val = str(cell).strip()
                        break
                
                kpis['Data'] = date_val
                kpis['HC Total Disponível'] = get_val(4, 1)
                kpis['HC Operacionais'] = get_val(4, 5)
                kpis['Faltas'] = get_val(4, 9)
                kpis['Colaboradores Presentes'] = get_val(5, 1)
                kpis['Diaristas'] = get_val(5, 5)
                kpis['Atestados'] = get_val(5, 9)
                kpis['Folgas'] = get_val(6, 5)
                kpis['PPH'] = get_val(6, 9)
                kpis['Backlog Inicial'] = get_val(10, 1)
                kpis['Volume Planejado'] = get_val(10, 5)
                kpis['Volume Recebido'] = get_val(10, 9)
                kpis['Coletas Realizadas'] = get_val(11, 1)
                kpis['Volume Expedido'] = get_val(11, 5)
                kpis['Backlog Final'] = get_val(11, 9)
                kpis['Erros de Triagem'] = get_val(16, 1)
                kpis['Avarias'] = get_val(16, 5)
                kpis['Total Ocorrências'] = get_val(16, 9)
                
                kpis['BRE (SOC)'] = get_val(12, 5)
                kpis['RAO (SOC)'] = get_val(12, 9)
                kpis['% Presença'] = get_val(6, 1)

                # Parse Taxa de Expedição no Prazo (HUB -> PDD) da aba Operação
                taxa_items = []
                route_rows_map = {}
                r_rotas_hdr = None
                for r in range(len(df_oper)):
                    val0 = str(df_oper.iloc[r, 0]).strip().upper() if pd.notna(df_oper.iloc[r, 0]) else ''
                    if val0 == 'ROTA':
                        r_rotas_hdr = r
                        sub_r = r + 1
                        idx = 0
                        while sub_r < len(df_oper):
                            val_r0 = df_oper.iloc[sub_r, 0]
                            if pd.isna(val_r0) or str(val_r0).strip() == '' or 'COLA' in str(val_r0).upper():
                                break
                            rota = str(val_r0).strip()
                            ref_d = df_oper.iloc[sub_r, 2] if df_oper.shape[1] > 2 and pd.notna(df_oper.iloc[sub_r, 2]) else ''
                            if isinstance(ref_d, (datetime, pd.Timestamp)):
                                ref_d_str = ref_d.strftime('%d/%m')
                            else:
                                ref_d_str = str(ref_d).split()[0] if ref_d else ''
                            route_rows_map[idx] = {'rota': rota, 'ref_data': ref_d_str}
                            idx += 1
                            sub_r += 1
                        break

                cola_hdr_r = None
                for r in range(len(df_oper)):
                    for c in range(min(5, df_oper.shape[1])):
                        v = str(df_oper.iloc[r, c]).strip().upper() if pd.notna(df_oper.iloc[r, c]) else ''
                        if 'COLA TAXA' in v:
                            cola_hdr_r = r + 1
                            break
                    if cola_hdr_r is not None:
                        break

                if cola_hdr_r is not None:
                    sub_r = cola_hdr_r + 1
                    idx = 0
                    while sub_r < len(df_oper):
                        val_a = df_oper.iloc[sub_r, 0]
                        if pd.isna(val_a) or str(val_a).strip() == '':
                            break
                        try:
                            qtd_exp = int(float(val_a))
                        except:
                            break

                        def _safe_n(c_idx, is_pct=False):
                            if c_idx < df_oper.shape[1] and pd.notna(df_oper.iloc[sub_r, c_idx]):
                                try:
                                    f = float(df_oper.iloc[sub_r, c_idx])
                                    return f if is_pct else int(f)
                                except:
                                    return 0.0 if is_pct else 0
                            return 0.0 if is_pct else 0

                        no_prazo = _safe_n(1)
                        fora_prazo = _safe_n(2)
                        anormalidade = _safe_n(3)
                        taxa_raw = _safe_n(4, is_pct=True)
                        taxa_val = taxa_raw / 100.0 if taxa_raw > 1.0 else taxa_raw
                        taxa_str = f'{taxa_val * 100:.2f}%'.replace('.', ',')

                        rota_info = route_rows_map.get(idx, {})
                        rota_name = rota_info.get('rota', f'Rota {idx+1}')
                        ref_data = rota_info.get('ref_data', '')

                        taxa_items.append({
                            'rota': rota_name,
                            'ref_data': ref_data,
                            'qtd_expedir': qtd_exp,
                            'no_prazo': no_prazo,
                            'fora_prazo': fora_prazo,
                            'anormalidade': anormalidade,
                            'taxa_prazo': taxa_val,
                            'taxa_prazo_str': taxa_str
                        })
                        idx += 1
                        sub_r += 1

                # Fallback para tabela direta caso COLA não esteja presente
                if not taxa_items and r_rotas_hdr is not None:
                    sub_r = r_rotas_hdr + 1
                    while sub_r < len(df_oper):
                        val_r0 = df_oper.iloc[sub_r, 0]
                        if pd.isna(val_r0) or str(val_r0).strip() == '' or 'COLA' in str(val_r0).upper():
                            break
                        rota = str(val_r0).strip()
                        def _safe_r(c_idx, is_pct=False):
                            if c_idx < df_oper.shape[1] and pd.notna(df_oper.iloc[sub_r, c_idx]):
                                try:
                                    f = float(df_oper.iloc[sub_r, c_idx])
                                    return f if is_pct else int(f)
                                except:
                                    return 0.0 if is_pct else 0
                            return 0.0 if is_pct else 0

                        qtd_exp = _safe_r(1)
                        ref_d = df_oper.iloc[sub_r, 2] if df_oper.shape[1] > 2 and pd.notna(df_oper.iloc[sub_r, 2]) else ''
                        ref_d_str = ref_d.strftime('%d/%m') if isinstance(ref_d, (datetime, pd.Timestamp)) else (str(ref_d).split()[0] if ref_d else '')
                        no_prazo = _safe_r(4)
                        fora_prazo = _safe_r(5)
                        taxa_raw = _safe_r(6, is_pct=True)
                        taxa_val = taxa_raw / 100.0 if taxa_raw > 1.0 else taxa_raw
                        taxa_str = f'{taxa_val * 100:.2f}%'.replace('.', ',')

                        if qtd_exp > 0 or no_prazo > 0 or fora_prazo > 0:
                            taxa_items.append({
                                'rota': rota,
                                'ref_data': ref_d_str,
                                'qtd_expedir': qtd_exp,
                                'no_prazo': no_prazo,
                                'fora_prazo': fora_prazo,
                                'anormalidade': 0,
                                'taxa_prazo': taxa_val,
                                'taxa_prazo_str': taxa_str
                            })
                        sub_r += 1

                tot_exp = sum(i['qtd_expedir'] for i in taxa_items)
                tot_np = sum(i['no_prazo'] for i in taxa_items)
                tot_fp = sum(i['fora_prazo'] for i in taxa_items)
                tot_an = sum(i['anormalidade'] for i in taxa_items)
                taxa_geral = (tot_np / tot_exp) if tot_exp > 0 else 0.0
                taxa_geral_str = f'{taxa_geral * 100:.2f}%'.replace('.', ',')

                taxa_expedicao_prazo = {
                    'items': taxa_items,
                    'totais': {
                        'qtd_expedir': tot_exp,
                        'no_prazo': tot_np,
                        'fora_prazo': tot_fp,
                        'anormalidade': tot_an,
                        'taxa_prazo': taxa_geral,
                        'taxa_prazo_str': taxa_geral_str
                    }
                }
                
                if tot_exp > 0:
                    kpis['SLA Expedição'] = taxa_geral
                    kpis['Taxa Expedição no Prazo'] = taxa_geral_str
                    kpis['SLA'] = taxa_geral_str
                            
            # Override/add "Erros de Triagem" from "Resumo" sheet as requested by the user
            try:
                df_resumo = pd.read_excel(xl, sheet_name="Resumo", header=None)
                for idx, row in df_resumo.iterrows():
                    first_val = str(row[0]).strip() if pd.notna(row[0]) else ""
                    if "ERROS DE TRIAGEM" in first_val.upper():
                        val = row[1]
                        if pd.notna(val):
                            try:
                                kpis["Erros de Triagem"] = int(float(val))
                            except:
                                kpis["Erros de Triagem"] = val
                        break
            except Exception as e_resumo:
                print(f"Error parsing Resumo sheet for Erros de Triagem: {e_resumo}")
     
            # Calcular chaves ausentes de KPIs de RH e volumes para compatibilidade
            hc_operacionais = kpis.get('HC Operacionais', 0)
            diaristas = kpis.get('Diaristas', 0)
            faltas = kpis.get('Faltas', 0)
            atestados = kpis.get('Atestados', 0)
            
            kpis['HC Presente'] = hc_operacionais
            
            # Só faz o cálculo manual do HC total se ele não tiver sido lido ou for zero
            if not kpis.get('HC Total Disponível'):
                kpis['HC Total Disponível'] = hc_operacionais + faltas + atestados
                
            # Só calcula o % Presença manualmente se ele não foi lido diretamente da planilha
            if '% Presença' not in kpis or kpis['% Presença'] is None:
                colab_presentes = kpis.get('Colaboradores Presentes', 0)
                hc_total = kpis['HC Total Disponível']
                if hc_total > 0:
                    kpis['% Presença'] = colab_presentes / hc_total
                else:
                    kpis['% Presença'] = 0.0
                
            vol_expedido = kpis.get('Volume Expedido', 0)
            vol_planejado = kpis.get('Volume Planejado', 0)
            coletas = kpis.get('Coletas Realizadas', 0)
            backlog_inicial = kpis.get('Backlog Inicial', 0)
            total_vol = vol_planejado + coletas + backlog_inicial
            if total_vol > 0:
                kpis['% Expedição'] = vol_expedido / total_vol
            else:
                kpis['% Expedição'] = 0.0
     
            if 'BRE (SOC)' in expedicao_vol:
                kpis['BRE (SOC)'] = expedicao_vol['BRE (SOC)']
            if 'RAO (SOC)' in expedicao_vol:
                kpis['RAO (SOC)'] = expedicao_vol['RAO (SOC)']
                            
            # 2. Parse Transporte
            df_transp = pd.read_excel(xl, sheet_name="Transporte", header=None)
            
            # Parse SLA value from Transporte sheet dynamically
            sla_val_found = None
            for r in range(len(df_transp)):
                for c in range(len(df_transp.columns)):
                    val = df_transp.iloc[r, c]
                    if pd.notna(val) and str(val).strip().upper() == "SLA:":
                        if c + 1 < len(df_transp.columns):
                            right_val = df_transp.iloc[r, c + 1]
                            if pd.notna(right_val):
                                try:
                                    sla_val_found = float(right_val)
                                except:
                                    pass
                        break
                if sla_val_found is not None:
                    break
                    
            if sla_val_found is not None:
                if "SLA Expediço" not in kpis:
                    kpis["SLA Expediço"] = sla_val_found
                if "SLA Expedição" not in kpis:
                    kpis["SLA Expedição"] = sla_val_found
     
            header_idx = -1
            for idx, row in df_transp.iterrows():
                if any(isinstance(val, str) and "VEÍCULO / SC" in val.upper() for val in row):
                    header_idx = idx
                    break
                    
            transporte_rows = []
            if header_idx != -1:
                headers = [str(h).strip() for h in df_transp.iloc[header_idx]]
                for idx in range(header_idx + 2, len(df_transp)):
                    row = df_transp.iloc[idx]
                    first_val = str(row[0]).strip() if pd.notna(row[0]) else ""
                    if not first_val or "TOTAL" in first_val.upper():
                        break
                    
                    row_dict = {}
                    for col_idx, h in enumerate(headers):
                        if h and h != "nan":
                            val = row[col_idx]
                            if pd.isna(val):
                                val_str = ""
                            elif isinstance(val, pd.Timestamp):
                                val_str = val.strftime('%H:%M:%S')
                            elif type(val).__name__ == 'time':
                                val_str = val.strftime('%H:%M:%S')
                            elif isinstance(val, float) and val.is_integer():
                                val_str = int(val)
                            else:
                                val_str = str(val).strip()
                            row_dict[h] = val_str
                    transporte_rows.append(row_dict)
                    
            # Parse detalhado das rotas de expedição da aba Transporte
            exp_header_idx = -1
            for idx, row in df_transp.iterrows():
                first_val = str(row[0]).strip() if pd.notna(row[0]) else ""
                if "BASE DESTINO" in first_val.upper():
                    exp_header_idx = idx
                    break
                    
            expedicao_detalhe = []
            if exp_header_idx != -1:
                for idx in range(exp_header_idx + 2, len(df_transp)):
                    row = df_transp.iloc[idx]
                    route = str(row[0]).strip() if pd.notna(row[0]) else ""
                    
                    if not route or "TOTAL" in route.upper():
                        break
                    
                    vol_val = row[1]
                    if pd.isna(vol_val) or str(vol_val).strip() == "":
                        vol = 0
                    elif isinstance(vol_val, (int, float)):
                        vol = int(vol_val)
                    else:
                        vol = str(vol_val).strip()
                    
                    dep_time_val = row[3]
                    if pd.isna(dep_time_val) or str(dep_time_val).strip() == "":
                        dep_time = "-"
                    elif isinstance(dep_time_val, pd.Timestamp):
                        dep_time = dep_time_val.strftime('%H:%M:%S')
                    elif type(dep_time_val).__name__ == 'time':
                        dep_time = dep_time_val.strftime('%H:%M:%S')
                    else:
                        dep_time = str(dep_time_val).strip()
                    
                    sla_val = str(row[4]).strip() if pd.notna(row[4]) else ""
                    
                    # SN RAO e SP BRE não possuem horário de corte (status sempre OK)
                    is_no_cutoff_route = any(x in route.upper() for x in ["BRE", "RAO", "SP BRE", "SN RAO"])
                    
                    if is_no_cutoff_route:
                        cutoff = "-"
                        status = "OK"
                    else:
                        cutoff = corte_map.get(route) or CUTOFF_MAP.get(route, "04:00")
                        if route == 'PPB (2º Carro)':
                            status = "OK"
                        elif "DENTRO" in sla_val.upper():
                            status = "OK"
                        else:
                            status = "FORA"
                    
                    expedicao_detalhe.append({
                        "route": route,
                        "vol": vol,
                        "cutoff": cutoff,
                        "departure": dep_time,
                        "status": status
                    })
                    
            # 3. Parse Fechamento
            fech_sheet = "Resumo" if "Resumo" in sheet_names else ("Fechamento" if "Fechamento" in sheet_names else None)
            motivos = []
            pontos = []
            if fech_sheet:
                df_fech = pd.read_excel(xl, sheet_name=fech_sheet, header=None)
                mode = None
                for idx, row in df_fech.iterrows():
                    val = str(row[0]).strip() if pd.notna(row[0]) else ""
                    if "MOTIVOS" in val.upper():
                        mode = "motivos"
                        continue
                    elif "PONTOS" in val.upper():
                        mode = "pontos"
                        continue
                    elif val == "" or "J&T EXPRESS" in val or "DATA:" in val:
                        continue
                        
                    if mode == "motivos":
                        motivos.append(val)
                    elif mode == "pontos":
                        pontos.append(val)
                    
            # 4. Parse Analítico
            def safe_int(val, default=0):
                if pd.isna(val) or val == "" or str(val).strip().lower() in ("nan", "-", "não informado", "nao informado"):
                    return default
                try:
                    return int(float(str(val).strip()))
                except:
                    return default
     
            def safe_float(val, default=0.0):
                if pd.isna(val) or val == "" or str(val).strip().lower() in ("nan", "-", "não informado", "nao informado"):
                    return default
                try:
                    return float(str(val).strip())
                except:
                    return default
     
            df_ana = pd.read_excel(xl, sheet_name="Análitico", header=None)
            dates = []
            avaria_qnt = []
            avaria_val = []
            sem_mov_ini = []
            sem_mov_fim = []
            
            for col_idx in range(2, df_ana.shape[1]):
                date_val = df_ana.iloc[1, col_idx]
                if pd.notna(date_val):
                    date_str = str(date_val).strip()
                    if "TOTAL" in date_str.upper() or len(date_str) < 5:
                        continue
                    if isinstance(date_val, pd.Timestamp):
                        date_str = date_val.strftime('%d/%m')
                    else:
                        if ' ' in date_str:
                            try:
                                date_str = datetime.strptime(date_str.split()[0], '%Y-%m-%d').strftime('%d/%m')
                            except:
                                date_str = date_str.split()[0]
                    dates.append(date_str)
                    
                    av_q = df_ana.iloc[2, col_idx]
                    avaria_qnt.append(safe_int(av_q))
                    
                    av_v = df_ana.iloc[3, col_idx]
                    avaria_val.append(safe_float(av_v))
                    
                    sm_i = df_ana.iloc[5, col_idx]
                    sem_mov_ini.append(safe_int(sm_i))
                    
                    sm_f = df_ana.iloc[6, col_idx]
                    sem_mov_fim.append(safe_int(sm_f))
                    
            analitico = {
                "dates": dates,
                "avaria_qnt": avaria_qnt,
                "avaria_val": avaria_val,
                "sem_mov_ini": sem_mov_ini,
                "sem_mov_fim": sem_mov_fim
            }
            
            # 5. Parse Gestão
            gestao = {}
            try:
                df_gest = pd.read_excel(xl, sheet_name="Gestao", header=None)
                d_val = df_gest.iloc[1, 4]
                gest_date = d_val.strftime('%d/%m/%Y') if isinstance(d_val, datetime) or hasattr(d_val, 'strftime') else str(d_val)
                
                def clean_int(val):
                    if pd.isna(val) or val == "" or str(val).strip() == "nan" or str(val).strip() == "-":
                        return 0
                    try:
                        return int(float(val))
                    except:
                        return 0
                        
                def format_pct(val):
                    if pd.isna(val) or val == "" or str(val).strip() == "nan" or str(val).strip() == "-":
                        return "0,00%"
                    try:
                        pct_val = float(val) * 100
                        return f"{pct_val:.2f}%".replace('.', ',')
                    except:
                        return str(val).strip()
                
                gestao = {
                    "date": gest_date,
                    "backlog_inicial": {
                        "1_dia": clean_int(df_gest.iloc[3, 4]),
                        "total": clean_int(df_gest.iloc[3, 9])
                    },
                    "backlog_final": {
                        "1_dia": clean_int(df_gest.iloc[4, 4]),
                        "total": clean_int(df_gest.iloc[4, 9])
                    },
                    "sem_mov_inicial": {
                        "1_dia": clean_int(df_gest.iloc[5, 4]),
                        "2_4_dias": clean_int(df_gest.iloc[5, 5]),
                        "5_dias": clean_int(df_gest.iloc[5, 6]),
                        "6_9_dias": clean_int(df_gest.iloc[5, 7]),
                        "10_dias_mais": clean_int(df_gest.iloc[5, 8]),
                        "total": clean_int(df_gest.iloc[5, 9])
                    },
                    "sem_mov_final": {
                        "1_dia": clean_int(df_gest.iloc[6, 4]),
                        "2_4_dias": clean_int(df_gest.iloc[6, 5]),
                        "5_dias": clean_int(df_gest.iloc[6, 6]),
                        "6_9_dias": clean_int(df_gest.iloc[6, 7]),
                        "10_dias_mais": clean_int(df_gest.iloc[6, 8]),
                        "total": clean_int(df_gest.iloc[6, 9])
                    },
                    "variacao_backlog": {
                        "1_dia": format_pct(df_gest.iloc[7, 4]),
                        "total": format_pct(df_gest.iloc[7, 9])
                    },
                    "variacao_sem_mov": {
                        "1_dia": format_pct(df_gest.iloc[8, 4]),
                        "2_4_dias": format_pct(df_gest.iloc[8, 5]),
                        "5_dias": format_pct(df_gest.iloc[8, 6]),
                        "6_9_dias": format_pct(df_gest.iloc[8, 7]),
                        "10_dias_mais": format_pct(df_gest.iloc[8, 8]),
                        "total": format_pct(df_gest.iloc[8, 9])
                    }
                }
            except Exception as e_gest:
                print(f"Error parsing Gestao sheet: {e_gest}")
                gestao = {}
                
            return {
                "kpis": kpis,
                "recebimento_vol": recebimento_vol,
                "expedicao_vol": expedicao_vol,
                "expedicao_detalhe": expedicao_detalhe,
                "transporte": transporte_rows,
                "fechamento": {
                    "motivos": motivos,
                    "pontos": pontos
                },
                "analitico": analitico,
                "gestao": gestao,
                "taxa_expedicao_prazo": taxa_expedicao_prazo
            }
    except Exception as e:
        print(f"Error parsing CONTROLE DC BAU.xlsx: {e}")
        return None

# Funcao publica com cache em memoria para evitar leituras repetidas do disco
def load_controle_bau_data():
    file_path = CONTROLE_BAU_FILE
    temp_path = CONTROLE_BAU_FILE + ".tmp"
    
    # Se o arquivo temporário existe e é mais recente que o arquivo principal,
    # usamos o arquivo temporário como fonte de dados ativa (evita travamento por Excel no Windows).
    active_file = file_path
    if os.path.exists(temp_path) and os.path.getsize(temp_path) > 1000:
        if not os.path.exists(file_path) or os.path.getmtime(temp_path) > os.path.getmtime(file_path):
            active_file = temp_path
            
    return get_from_cache(active_file, _load_controle_bau_data_raw, active_file)

# Configurações de arquivos de texto de beeps
COLETA_TXT_FILE = "Coleta de chegada.txt"
EXPEDICAO_TXT_FILE = "Expedição.txt"
LOTE_TXT_FILE = "Inserido em lote.txt"

COLETA_ANT_FILE = "Coleta de chegada_anterior.txt"
EXPEDICAO_ANT_FILE = "Expedição_anterior.txt"
LOTE_ANT_FILE = "Inserido em lote_anterior.txt"

COLETA_RET_FILE = "Coleta de chegada_retrasado.txt"
EXPEDICAO_RET_FILE = "Expedição_retrasado.txt"
LOTE_RET_FILE = "Inserido em lote_retrasado.txt"

def get_operational_date(dt_str):
    # dt_str format: "YYYY-MM-DD HH:MM:SS" or "DD/MM/YYYY HH:MM:SS" etc.
    from datetime import datetime, timedelta
    dt = None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            dt = datetime.strptime(dt_str.strip(), fmt)
            break
        except Exception:
            continue
    if dt is None:
        try:
            # Fallback parsing
            clean_str = dt_str.replace("T", " ").strip()
            parts = clean_str.split(" ")
            date_part = parts[0]
            time_part = parts[1] if len(parts) > 1 else "00:00:00"
            hour = int(time_part.split(":")[0])
            
            if "/" in date_part:
                d, m, y = date_part.split("/")
                if len(y) == 2:
                    y = "20" + y
                date_part = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            
            if hour < 8:
                y, m, d = map(int, date_part.split("-"))
                dt_temp = datetime(y, m, d) - timedelta(days=1)
                return dt_temp.strftime("%Y-%m-%d")
            return date_part
        except Exception:
            try:
                return dt_str.split(" ")[0].split("T")[0]
            except Exception:
                return None
    
    if dt.hour < 8:
        dt_op = dt - timedelta(days=1)
    else:
        dt_op = dt
    return dt_op.strftime("%Y-%m-%d")

def get_file_date(file_path):
    if not os.path.exists(file_path):
        return None
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            f.readline() # skip header
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 2:
                    dt_str = parts[1].strip()
                    val = get_operational_date(dt_str)
                    if val:
                        return val
    except Exception:
        pass
    return None

try:
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd(), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as env_f:
            for line in env_f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip()
except Exception:
    pass

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "")

def supabase_request(table, method="GET", query_params="", payload=None):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    import urllib.request
    import json
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    if query_params:
        url += f"?{query_params}"
        
    headers = {
        "apikey": SUPABASE_KEY,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    if SUPABASE_KEY.startswith("eyJ"):
        headers["Authorization"] = f"Bearer {SUPABASE_KEY}"
    
    if method == "POST" and payload:
        headers["Prefer"] = "resolution=merge-duplicates"
        
    data_bytes = None
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        
    req = urllib.request.Request(url, headers=headers, method=method, data=data_bytes)
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            res_data = response.read()
            if res_data:
                return json.loads(res_data.decode("utf-8"))
            return []
    except Exception as e:
        print(f"Supabase error on {table} ({method}): {e}")
        return None

def load_production_data_from_supabase():
    res_dates = supabase_request("production_hourly", method="GET", query_params="select=operational_date&order=operational_date.desc")
    dates = []
    if res_dates:
        for r in res_dates:
            d = r.get("operational_date")
            if d and d not in dates:
                dates.append(d)
                if len(dates) == 3:
                    break
                    
    empty_dataset = {
        'bipagens_hora': [],
        'totais': {'coleta': 0, 'expedicao': 0, 'lote': 0, 'total': 0, 'pico_hora': '-'},
        'rankings': {'coleta': [], 'expedicao': [], 'lote': []},
        'data_ref': '-'
    }
    
    if not dates:
        return {
            'bipagens_hora': [],
            'totais': {'coleta': 0, 'expedicao': 0, 'lote': 0, 'total': 0, 'pico_hora': '-'},
            'rankings': {'coleta': [], 'expedicao': [], 'lote': []},
            'data_ref': '-',
            'anterior': empty_dataset,
            'retrasado': empty_dataset
        }
        
    date_filter = ",".join([f'"{d}"' for d in dates])
    hourly_rows = supabase_request("production_hourly", method="GET", query_params=f"operational_date=in.({date_filter})&order=operational_date.desc")
    ranking_rows = supabase_request("production_rankings", method="GET", query_params=f"operational_date=in.({date_filter})&order=operational_date.desc,position.asc")
    
    hourly_by_date = {d: [] for d in dates}
    if hourly_rows:
        for r in hourly_rows:
            d = r.get('operational_date')
            if d in hourly_by_date:
                hourly_by_date[d].append(r)
            
    rankings_by_date = {d: {'coleta': [], 'expedicao': [], 'lote': []} for d in dates}
    if ranking_rows:
        for r in ranking_rows:
            d = r.get('operational_date')
            t = r.get('type')
            if d in rankings_by_date and t in rankings_by_date[d]:
                rankings_by_date[d][t].append({
                    'posicao': r.get('position', 1),
                    'nome': r.get('operator_name', '-'),
                    'count': r.get('count', 0)
                })
            
    def build_dataset(date_str):
        rows = hourly_by_date.get(date_str, [])
        target_hours = [
            '18:00', '19:00', '20:00', '21:00', '22:00', '23:00',
            '00:00', '01:00', '02:00', '03:00', '04:00', '05:00',
            '06:00', '07:00', '08:00'
        ]
        
        hourly_map = {h: {'coleta': 0, 'expedicao': 0, 'lote': 0} for h in target_hours}
        for r in rows:
            h = r.get('hour')
            if h in hourly_map:
                hourly_map[h] = {
                    'coleta': r.get('coleta', 0) or 0,
                    'expedicao': r.get('expedicao', 0) or 0,
                    'lote': r.get('lote', 0) or 0
                }
                
        tot_coleta = sum(hourly_map[h]['coleta'] for h in target_hours)
        tot_exp = sum(hourly_map[h]['expedicao'] for h in target_hours)
        tot_lote = sum(hourly_map[h]['lote'] for h in target_hours)
        tot_all = tot_coleta + tot_exp + tot_lote
        
        pico_hora = "-"
        pico_val = 0
        for h in target_hours:
            c = hourly_map[h]['coleta']
            if c > pico_val:
                pico_val = c
                pico_hora = f"{h} ({c:,}".replace(",", ".") + ")"
                
        last_active_idx = 0
        for idx, h in enumerate(target_hours):
            c = hourly_map[h]['coleta']
            e = hourly_map[h]['expedicao']
            l = hourly_map[h]['lote']
            if c > 0 or e > 0 or l > 0:
                last_active_idx = idx
                
        active_target_hours = target_hours[:last_active_idx+1] if last_active_idx > 0 else target_hours
        
        bipagens_hora = []
        for h in active_target_hours:
            c = hourly_map[h]['coleta']
            e = hourly_map[h]['expedicao']
            l = hourly_map[h]['lote']
            bipagens_hora.append({
                'hora': h,
                'coleta': c,
                'expedicao': e,
                'lote': l,
                'total': c + e + l
            })
            
        try:
            parts = date_str.split("-")
            ref_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
        except Exception:
            ref_date = date_str
            
        return {
            'bipagens_hora': bipagens_hora,
            'totais': {
                'coleta': tot_coleta,
                'expedicao': tot_exp,
                'lote': tot_lote,
                'total': tot_all,
                'pico_hora': pico_hora
            },
            'rankings': rankings_by_date.get(date_str, {'coleta': [], 'expedicao': [], 'lote': []}),
            'data_ref': ref_date
        }
        
    recent_data = build_dataset(dates[0])
    anterior_data = build_dataset(dates[1]) if len(dates) > 1 else empty_dataset
    retrasado_data = build_dataset(dates[2]) if len(dates) > 2 else empty_dataset
    
    return {
        'bipagens_hora': recent_data['bipagens_hora'],
        'totais': recent_data['totais'],
        'rankings': recent_data['rankings'],
        'data_ref': recent_data['data_ref'],
        'anterior': anterior_data,
        'retrasado': retrasado_data
    }

def parse_production_dataset(coleta_path, expedicao_path, lote_path):
    # Mapeamento de operadores para Inserido em lote
    operator_name_map = {
        'TTSIDCBAU': 'TEMPORARIO TSI DCBAU',
        '01877120': 'Kauê Willi santos de Jesus',
        '01765507': 'João Batista Ferreira',
        '01801690': 'Thyago Oliveira Souza',
        '01865960': 'Amanda Laureano Magalhães',
        '01946199': 'PETERSON LUIZ DIAS TEIXEIRA',
        '01914197': 'Igor William Romão',
        '01899858DCBAU': 'Juliano Pires Filho',
        '01930491': 'João victor marin mariano',
        '01801689': 'Pablo Antônio Garcia Silva',
        '01930584': 'João Batista Ferreira',
        '01930502': 'Juliano Pires Filho',
        '01897865DCBAU': 'TEMPORARIO TSI DCBAU'
    }
    
    # Hours list (18:00 to 08:00)
    target_hours = [
        '18:00', '19:00', '20:00', '21:00', '22:00', '23:00',
        '00:00', '01:00', '02:00', '03:00', '04:00', '05:00',
        '06:00', '07:00', '08:00'
    ]
    
    # Initialize hourly beeps
    hourly_data = {h: {'coleta': 0, 'expedicao': 0, 'lote': 0} for h in target_hours}
    
    # Operator counters
    op_coleta = Counter()
    op_exp = Counter()
    op_lote = Counter()
    
    # Parse function
    def parse_txt(file_path, op_counter, hour_field_key, is_lote=False):
        if not file_path or not os.path.exists(file_path):
            return 0
        total_records = 0
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            header = f.readline() # Skip header
            for line in f:
                parts = line.strip().split("\t")
                if len(parts) >= 3:
                    total_records += 1
                    dt_str = parts[1].strip()
                    op = parts[2].strip()
                    
                    # Map operator names for Lote
                    if is_lote:
                        op = operator_name_map.get(op, op)
                    
                    op_counter[op] += 1
                    
                    try:
                        # Extract hour: e.g. "18" from "2026-06-30 18:11:33"
                        if " " in dt_str:
                            dt_part = dt_str.split(" ")[1]
                        elif "T" in dt_str:
                            dt_part = dt_str.split("T")[1]
                        else:
                            dt_part = dt_str[-8:]
                        h_part = dt_part.split(":")[0].strip()
                        h = h_part.zfill(2)
                        hour_key = f"{h}:00"
                        if hour_key in hourly_data:
                            hourly_data[hour_key][hour_field_key] += 1
                    except Exception:
                        pass
        return total_records

    tot_coleta = parse_txt(coleta_path, op_coleta, 'coleta')
    tot_exp = parse_txt(expedicao_path, op_exp, 'expedicao')
    tot_lote = parse_txt(lote_path, op_lote, 'lote', is_lote=True)
    
    # Format hourly list
    bipagens_hora = []
    tot_h_coleta = 0
    tot_h_exp = 0
    tot_h_lote = 0
    tot_h_all = 0
    
    # Encontra a última hora que possui alguma atividade (bipagem)
    last_active_idx = 0
    for idx, h in enumerate(target_hours):
        c = hourly_data[h]['coleta']
        e = hourly_data[h]['expedicao']
        l = hourly_data[h]['lote']
        if c > 0 or e > 0 or l > 0:
            last_active_idx = idx
            
    # Filtra os horários para exibir apenas os que têm beeps até a última hora ativa
    active_target_hours = target_hours[:last_active_idx+1] if last_active_idx > 0 else target_hours
    
    for h in active_target_hours:
        c = hourly_data[h]['coleta']
        e = hourly_data[h]['expedicao']
        l = hourly_data[h]['lote']
        t = c + e + l
        
        tot_h_coleta += c
        tot_h_exp += e
        tot_h_lote += l
        tot_h_all += t
        
        bipagens_hora.append({
            'hora': h,
            'coleta': c,
            'expedicao': e,
            'lote': l,
            'total': t
        })
        
    # Find peak hour for Coleta de Chegada only
    pico_hora = "-"
    pico_val = 0
    for h in target_hours:
        c = hourly_data[h]['coleta']
        if c > pico_val:
            pico_val = c
            pico_hora = f"{h} ({c:,}".replace(",", ".") + ")"
        
    # Format rankings (top 5)
    def format_ranking(counter):
        sorted_ops = sorted(counter.items(), key=lambda x: x[1], reverse=True)
        ranking = []
        for idx, (op, count) in enumerate(sorted_ops[:5]):
            # Format name to first and second name (handling prepositions)
            parts = op.split()
            if len(parts) >= 2:
                if parts[1].lower() in ['de', 'da', 'do', 'dos', 'e'] and len(parts) >= 3:
                    short_name = f"{parts[0]} {parts[1]} {parts[2]}"
                else:
                    short_name = f"{parts[0]} {parts[1]}"
            else:
                short_name = op
                
            ranking.append({
                'posicao': idx + 1,
                'nome': short_name,
                'count': count
            })
        return ranking
        
    ranking_coleta = format_ranking(op_coleta)
    ranking_exp = format_ranking(op_exp)
    ranking_lote = format_ranking(op_lote)
    
    # Extrai a data de referência
    ref_date = None
    for path in [coleta_path, expedicao_path, lote_path]:
        d = get_file_date(path)
        if d:
            try:
                parts = d.split("-")
                ref_date = f"{parts[2]}/{parts[1]}/{parts[0]}"
            except Exception:
                ref_date = d
            break
            
    return {
        'bipagens_hora': bipagens_hora,
        'totais': {
            'coleta': tot_h_coleta,
            'expedicao': tot_h_exp,
            'lote': tot_h_lote,
            'total': tot_h_all,
            'pico_hora': pico_hora
        },
        'rankings': {
            'coleta': ranking_coleta,
            'expedicao': ranking_exp,
            'lote': ranking_lote
        },
        'data_ref': ref_date or "-"
    }

_producao_cache = {'mtimes': {}, 'data': None}

def load_producao_txt_data():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            data = load_production_data_from_supabase()
            if data:
                return data
        except Exception as e:
            print(f"Erro ao carregar dados do Supabase, usando local: {e}")

    dir_path = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    
    coleta_path = os.path.join(dir_path, COLETA_TXT_FILE)
    expedicao_path = os.path.join(dir_path, EXPEDICAO_TXT_FILE)
    lote_path = os.path.join(dir_path, LOTE_TXT_FILE)
    
    coleta_ant_path = os.path.join(dir_path, COLETA_ANT_FILE)
    expedicao_ant_path = os.path.join(dir_path, EXPEDICAO_ANT_FILE)
    lote_ant_path = os.path.join(dir_path, LOTE_ANT_FILE)
    
    coleta_ret_path = os.path.join(dir_path, COLETA_RET_FILE)
    expedicao_ret_path = os.path.join(dir_path, EXPEDICAO_RET_FILE)
    lote_ret_path = os.path.join(dir_path, LOTE_RET_FILE)
    
    all_files = [
        coleta_path, expedicao_path, lote_path,
        coleta_ant_path, expedicao_ant_path, lote_ant_path,
        coleta_ret_path, expedicao_ret_path, lote_ret_path
    ]
    current_mtimes = {f: (os.path.getmtime(f) if os.path.exists(f) else 0) for f in all_files}
    global _producao_cache
    if _producao_cache['data'] is not None and _producao_cache['mtimes'] == current_mtimes:
        return _producao_cache['data']
    
    recent_data = parse_production_dataset(coleta_path, expedicao_path, lote_path)
    anterior_data = parse_production_dataset(coleta_ant_path, expedicao_ant_path, lote_ant_path)
    retrasado_data = parse_production_dataset(coleta_ret_path, expedicao_ret_path, lote_ret_path)
    
    result = {
        'bipagens_hora': recent_data['bipagens_hora'],
        'totais': recent_data['totais'],
        'rankings': recent_data['rankings'],
        'data_ref': recent_data['data_ref'],
        'anterior': {
            'bipagens_hora': anterior_data['bipagens_hora'],
            'totais': anterior_data['totais'],
            'data_ref': anterior_data['data_ref']
        },
        'retrasado': {
            'bipagens_hora': retrasado_data['bipagens_hora'],
            'totais': retrasado_data['totais'],
            'data_ref': retrasado_data['data_ref']
        }
    }
    _producao_cache['mtimes'] = current_mtimes
    _producao_cache['data'] = result
    return result


@app.route('/api/producao/data')
def get_producao_data():
    data = load_producao_txt_data()
    return jsonify(data)

@app.route('/api/producao/upload', methods=['POST'])
def upload_producao_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "message": "Nenhum arquivo enviado"}), 400
        
    file = request.files['file']
    file_type = request.form.get('type')
    
    if not file or file.filename == '':
        return jsonify({"success": False, "message": "Arquivo inválido"}), 400
        
    if file_type == 'coleta':
        target_name = COLETA_TXT_FILE
    elif file_type == 'expedicao':
        target_name = EXPEDICAO_TXT_FILE
    elif file_type == 'lote':
        target_name = LOTE_TXT_FILE
    else:
        return jsonify({"success": False, "message": "Tipo de arquivo inválido"}), 400
        
    try:
        dir_path = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
        target_path = os.path.join(dir_path, target_name)
        
        # 1. Parse date of the uploaded file
        uploaded_date = None
        file.seek(0)
        header = file.readline()
        # Read up to 50 lines to find a valid date
        for _ in range(50):
            line = file.readline()
            if not line:
                break
            if isinstance(line, bytes):
                line = line.decode('utf-8', errors='ignore')
            parts = line.strip().split("\t")
            if len(parts) >= 2:
                dt_str = parts[1].strip()
                val = get_operational_date(dt_str)
                if val:
                    uploaded_date = val
                    break
        file.seek(0) # Reset stream
        
        # 2. Get target paths for the specific file type being uploaded
        if file_type == 'coleta':
            active_path = os.path.join(dir_path, COLETA_TXT_FILE)
            ant_path = os.path.join(dir_path, COLETA_ANT_FILE)
            ret_path = os.path.join(dir_path, COLETA_RET_FILE)
        elif file_type == 'expedicao':
            active_path = os.path.join(dir_path, EXPEDICAO_TXT_FILE)
            ant_path = os.path.join(dir_path, EXPEDICAO_ANT_FILE)
            ret_path = os.path.join(dir_path, EXPEDICAO_RET_FILE)
        else:
            active_path = os.path.join(dir_path, LOTE_TXT_FILE)
            ant_path = os.path.join(dir_path, LOTE_ANT_FILE)
            ret_path = os.path.join(dir_path, LOTE_RET_FILE)
            
        current_date = get_file_date(active_path)
                
        # 3. If dates differ (and both exist/are valid), rotate files
        should_rotate = False
        if uploaded_date and current_date and uploaded_date != current_date:
            should_rotate = True

        if should_rotate:
            import shutil
            # Rotate anterior -> retrasado
            if os.path.exists(ant_path):
                try:
                    shutil.copy2(ant_path, ret_path)
                except Exception:
                    pass
            elif os.path.exists(ret_path):
                try:
                    os.remove(ret_path)
                except Exception:
                    pass
            
            # Rotate active -> anterior
            if os.path.exists(active_path):
                try:
                    shutil.copy2(active_path, ant_path)
                except Exception:
                    pass
            elif os.path.exists(ant_path):
                try:
                    os.remove(ant_path)
                except Exception:
                    pass
            
            pass
                        
                        
        # 4. Save the uploaded file
        file.save(target_path)
        global _producao_cache
        _producao_cache['data'] = None
        
        # 5. If Supabase is configured, upload the parsed dataset to Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                parsed = parse_production_dataset(
                    target_path if file_type == 'coleta' else None,
                    target_path if file_type == 'expedicao' else None,
                    target_path if file_type == 'lote' else None
                )
                
                ref_date = parsed.get('data_ref', '-')
                if ref_date != '-':
                    try:
                        parts = ref_date.split("/")
                        db_date = f"{parts[2]}-{parts[1]}-{parts[0]}"
                    except Exception:
                        db_date = ref_date
                        
                    # Fetch existing hourly beeps for this date
                    existing_rows = supabase_request("production_hourly", method="GET", query_params=f"operational_date=eq.{db_date}")
                    existing_map = {}
                    if existing_rows:
                        for r in existing_rows:
                            existing_map[r['hour']] = r
                            
                    # Merge data and prepare payload
                    payload_hourly = []
                    for row in parsed['bipagens_hora']:
                        h = row['hora']
                        new_val = row[file_type]
                        
                        exist = existing_map.get(h, {})
                        exist_coleta = exist.get('coleta', 0) or 0
                        exist_expedicao = exist.get('expedicao', 0) or 0
                        exist_lote = exist.get('lote', 0) or 0
                        
                        merged_coleta = new_val if file_type == 'coleta' else exist_coleta
                        merged_expedicao = new_val if file_type == 'expedicao' else exist_expedicao
                        merged_lote = new_val if file_type == 'lote' else exist_lote
                        
                        payload_hourly.append({
                            "operational_date": db_date,
                            "hour": h,
                            "coleta": merged_coleta,
                            "expedicao": merged_expedicao,
                            "lote": merged_lote
                        })
                        
                    if payload_hourly:
                        supabase_request("production_hourly", method="POST", payload=payload_hourly)
                        
                    # Save rankings
                    supabase_request("production_rankings", method="DELETE", query_params=f"operational_date=eq.{db_date}&type=eq.{file_type}")
                    
                    new_rankings = parsed['rankings'][file_type]
                    payload_rankings = []
                    for r in new_rankings:
                        payload_rankings.append({
                            "operational_date": db_date,
                            "type": file_type,
                            "position": r['posicao'],
                            "operator_name": r['nome'],
                            "count": r['count']
                        })
                    if payload_rankings:
                        supabase_request("production_rankings", method="POST", payload=payload_rankings)
            except Exception as e_sb:
                print(f"Error syncing with Supabase: {e_sb}")
                
        return jsonify({"success": True, "message": f"Arquivo de {file_type} atualizado com sucesso!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Erro ao salvar arquivo: {str(e)}"}), 500

@app.route('/api/controle/data')
def get_controle_data():
    data = load_controle_bau_data()
    if data is None:
        return jsonify({"error": "Erro ao ler dados da planilha CONTROLE DC BAU.xlsx"}), 500
    return jsonify(data)

def get_volume_exp_trip_id_map():
    id_map = {}
    try:
        ctrl_data = load_controle_bau_data()
        transp = ctrl_data.get('transporte', []) if ctrl_data else []
        for item in transp:
            veh = str(item.get('VEÍCULO / SC', '')).strip().upper()
            trip_id = str(item.get("ID's", '')).strip()
            if veh and trip_id:
                id_map[veh] = trip_id
    except Exception as e:
        print(f"[Volume Exp] Aviso ao carregar mapa de IDs de viagem: {e}")
    return id_map

def match_volume_exp_trip_id(car_name, id_map):
    if not car_name:
        return ""
    import re
    car_upper = car_name.strip().upper()
    if car_upper in id_map:
        return id_map[car_upper]
    norm = re.sub(r'^(SP\s+|F\s+)', '', car_upper)
    norm = re.sub(r'(-SP|-MG)$', '', norm).strip()
    if norm in id_map:
        return id_map[norm]
    for k, v in id_map.items():
        if k in car_upper or car_upper in k or k in norm or norm in k:
            return v
    return ""

def load_controle_exp_txt_data():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    filepath = os.path.join(base_dir, "Controle exp.txt")
    if not os.path.exists(filepath):
        return []
    return get_from_cache(filepath, _load_controle_exp_txt_data_raw, filepath)

def _load_controle_exp_txt_data_raw(filepath):
    import re
    print(f"[Volume Exp] Lendo arquivo em: {filepath}")
    
    # Carrega mapa de IDs de viagem cadastrados no Controle DC Bauru
    trip_id_map = get_volume_exp_trip_id_map()
    
    data_list = []
    current_date = ""
    
    # Regex para capturar data nos formatos DD.MM.YYYY, DD/MM/YYYY, DD-MM-YYYY ou YYYY-MM-DD
    date_regex = re.compile(
        r'\b(?P<day>\d{2})[./-](?P<month>\d{2})[./-](?P<year>\d{4})\b|\b(?P<year4>\d{4})[./-](?P<month2>\d{2})[./-](?P<day2>\d{2})\b'
    )
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    except Exception:
        try:
            with open(filepath, 'r', encoding='latin-1') as f:
                lines = f.readlines()
        except Exception:
            return []
            
    current_block = {}
    
    def finalize_block(block, dt):
        if not block:
            return
        if dt and "data" not in block:
            block["data"] = dt
        if "volume_previsto" in block and "volume_recebido" in block:
            # Se id_viagem não foi informado no txt, tenta enriquecer pelo nome do carro
            if not block.get("id_viagem"):
                car_name = block.get("carro", "")
                m_id = match_volume_exp_trip_id(car_name, trip_id_map)
                if m_id:
                    block["id_viagem"] = m_id
                else:
                    block["id_viagem"] = ""
            data_list.append(block)

    for line in lines:
        line_str = line.strip()
        if not line_str:
            if current_block:
                finalize_block(current_block, current_date)
                current_block = {}
            continue
            
        # Match date in the line
        match = date_regex.search(line_str)
        if match:
            # Se casar o padrão DD.MM.YYYY
            if match.group('day'):
                day = match.group('day')
                month = match.group('month')
                year = match.group('year')
                current_date = f"{day}/{month}/{year}"
            # Se casar o padrão YYYY-MM-DD
            elif match.group('year4'):
                year = match.group('year4')
                month = match.group('month2')
                day = match.group('day2')
                current_date = f"{day}/{month}/{year}"
            continue
            
        if "volume previsto" in line_str.lower():
            # Se já começamos um bloco anteriormente e encontramos outro "Volume Previsto"
            # sem que houvesse uma linha vazia antes, salva o bloco anterior
            if current_block and "volume_previsto" in current_block:
                finalize_block(current_block, current_date)
                current_block = {}
                
            val = line_str.split(":", 1)[1].strip()
            try:
                current_block["volume_previsto"] = int(val)
            except Exception:
                current_block["volume_previsto"] = val
            continue
            
        if "volume recebido" in line_str.lower():
            val = line_str.split(":", 1)[1].strip()
            try:
                current_block["volume_recebido"] = int(val)
            except Exception:
                current_block["volume_recebido"] = val
            continue
            
        if "expedido não chegou" in line_str.lower() or "expedido nao chegou" in line_str.lower():
            prefix = "expedido não chegou" if "expedido não chegou" in line_str.lower() else "expedido nao chegou"
            pos_prefix = line_str.lower().find(prefix)
            sub_str = line_str[pos_prefix + len(prefix):].strip()
            if ":" in sub_str:
                carro, qtd = sub_str.split(":", 1)
                current_block["carro"] = carro.strip()
                try:
                    current_block["quantidade_nao_chegou"] = int(qtd.strip())
                except Exception:
                    current_block["quantidade_nao_chegou"] = qtd.strip()
            else:
                current_block["carro"] = sub_str
                current_block["quantidade_nao_chegou"] = 0
            continue
            
        # Leitura direta de Manifesto / Tarefa / Viagem / SRTR se existir na linha
        lower_line = line_str.lower()
        if any(lower_line.startswith(p) for p in ["manifesto", "viagem", "tarefa", "id:", "id da viagem", "id de viagem"]) or "srtr" in lower_line:
            # Se já começamos um bloco anteriormente e encontramos um novo identificador de viagem sem linha vazia
            if current_block and ("volume_previsto" in current_block or "carro" in current_block):
                finalize_block(current_block, current_date)
                current_block = {}
                
            m_srtr = re.search(r'\b(SRTR\w+)\b', line_str, re.IGNORECASE)
            if m_srtr:
                current_block["id_viagem"] = m_srtr.group(1).upper()
            elif ":" in line_str:
                current_block["id_viagem"] = line_str.split(":", 1)[1].strip()
            else:
                current_block["id_viagem"] = line_str.strip()
            continue
            
    if current_block:
        finalize_block(current_block, current_date)
            
    return data_list

@app.route('/api/volume_exp_dc_bau/data')
def get_volume_exp_dc_bau_data():
    try:
        data = load_controle_exp_txt_data()
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": f"Erro ao ler controle de expedicao: {str(e)}"}), 500

@app.route('/api/controle/generate_pdf')
def generate_controle_pdf():
    data = load_controle_bau_data()
    if not data:
        return "Erro: Dados de controle não encontrados.", 404
        
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        leftMargin=40,
        rightMargin=40,
        topMargin=60,
        bottomMargin=60
    )
    
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'DocTitleCtrl',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=colors.HexColor('#1E3A8A'),
        spaceAfter=5
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitleCtrl',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=12,
        leading=14,
        textColor=colors.HexColor('#4B5563'),
        spaceAfter=15
    )
    
    section_title = ParagraphStyle(
        'SectionTitleCtrl',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=10,
        spaceAfter=10
    )
    
    body_text = ParagraphStyle(
        'BodyCtrl',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#1F2937')
    )
    
    body_bold = ParagraphStyle(
        'BodyBoldCtrl',
        parent=body_text,
        fontName='Helvetica-Bold'
    )
    
    body_text_white = ParagraphStyle(
        'BodyWhiteCtrl',
        parent=body_text,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    
    # Custom styles for the route table (2 columns side-by-side)
    route_body_style = ParagraphStyle(
        'RouteBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=7.5,
        leading=9,
        textColor=colors.HexColor('#1F2937')
    )
    route_body_left = ParagraphStyle(
        'RouteBodyLeft',
        parent=route_body_style,
        alignment=0
    )
    route_body_left_bold = ParagraphStyle(
        'RouteBodyLeftBold',
        parent=route_body_left,
        fontName='Helvetica-Bold'
    )
    route_body_right = ParagraphStyle(
        'RouteBodyRight',
        parent=route_body_style,
        alignment=2
    )
    route_body_center = ParagraphStyle(
        'RouteBodyCenter',
        parent=route_body_style,
        alignment=1
    )
    route_body_center_bold = ParagraphStyle(
        'RouteBodyCenterBold',
        parent=route_body_center,
        fontName='Helvetica-Bold'
    )
    route_hdr_left = ParagraphStyle(
        'RouteHdrLeft',
        parent=route_body_left_bold,
        textColor=colors.white
    )
    route_hdr_right = ParagraphStyle(
        'RouteHdrRight',
        parent=route_body_right,
        fontName='Helvetica-Bold',
        textColor=colors.white
    )
    route_hdr_center = ParagraphStyle(
        'RouteHdrCenter',
        parent=route_body_center_bold,
        textColor=colors.white
    )
    
    kpi_title_style = ParagraphStyle(
        'KpiTitleCtrl',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#4B5563'),
        alignment=1 # Center
    )
    
    kpi_val_style = ParagraphStyle(
        'KpiValCtrl',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1E3A8A'),
        alignment=1 # Center
    )
    
    bullet_style = ParagraphStyle(
        'BulletCtrl',
        parent=body_text,
        leftIndent=15,
        firstLineIndent=-10,
        spaceAfter=5
    )

    story = []
    
    # --- PAGE 1: TITLE, KPIS, RH & VOLUMES ---
    story.append(Paragraph("Fechamento de Turno", title_style))
    story.append(Paragraph(f"DC Bauru - Relatório Consolidado Operacional | Data: {data['kpis'].get('Data', '-')}", subtitle_style))
    
    # KPIs Row
    kpis = data['kpis']
    kpi_data = [
        [
            Paragraph("Total Presentes", kpi_title_style),
            Paragraph("Produtividade (PPH)", kpi_title_style),
            Paragraph("Volume Recebido", kpi_title_style),
            Paragraph("Volume Expedido", kpi_title_style),
            Paragraph("Backlog Final", kpi_title_style),
            Paragraph("Erros de Triagem", kpi_title_style)
        ],
        [
            Paragraph(str(kpis.get('Colaboradores Presentes', '-')), kpi_val_style),
            Paragraph(f"{kpis.get('PPH', 0.0):.2f}" if isinstance(kpis.get('PPH'), (int, float)) else str(kpis.get('PPH', '-')), kpi_val_style),
            Paragraph(f"{kpis.get('Volume Recebido', 0):,}".replace(',', '.') if isinstance(kpis.get('Volume Recebido'), int) else str(kpis.get('Volume Recebido', '-')), kpi_val_style),
            Paragraph(f"{kpis.get('Volume Expedido', 0):,}".replace(',', '.') if isinstance(kpis.get('Volume Expedido'), int) else str(kpis.get('Volume Expedido', '-')), kpi_val_style),
            Paragraph(f"{kpis.get('Backlog Final', 0):,}".replace(',', '.') if isinstance(kpis.get('Backlog Final'), int) else str(kpis.get('Backlog Final', '-')), kpi_val_style),
            Paragraph(f"{kpis.get('Erros de Triagem', 0):,}".replace(',', '.') if isinstance(kpis.get('Erros de Triagem'), int) else str(kpis.get('Erros de Triagem', '-')), kpi_val_style)
        ]
    ]
    
    kpi_table = Table(kpi_data, colWidths=[127, 127, 127, 127, 127, 127])
    kpi_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor('#F9FAFB')),
        ('BOX', (0,0), (-1,-1), 1, colors.HexColor('#E5E7EB')),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 8),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(kpi_table)
    story.append(Spacer(1, 20))
    
    # RH & Volumes side-by-side
    rh_rows = [
        [Paragraph("Recursos Humanos", body_text_white), Paragraph("", body_text_white)],
        [Paragraph("HC Total Disponível", body_text), Paragraph(str(kpis.get('HC Total Disponível', '-')), body_bold)],
        [Paragraph("Total Presentes", body_text), Paragraph(str(kpis.get('Colaboradores Presentes', '-')), body_bold)],
        [Paragraph("% Presença", body_text), Paragraph(f"{kpis.get('% Presença')*100:.1f}%" if isinstance(kpis.get('% Presença'), (int, float)) and kpis.get('% Presença') <= 2.0 else f"{kpis.get('% Presença')}%" if kpis.get('% Presença') else "-", body_bold)],
        [Paragraph("H.C. Presente", body_text), Paragraph(str(kpis.get('HC Presente', '-')), body_bold)],
        [Paragraph("Diaristas", body_text), Paragraph(str(kpis.get('Diaristas', '-')), body_bold)],
        [Paragraph("Folgas", body_text), Paragraph(str(kpis.get('Folgas', '-')), body_bold)],
        [Paragraph("Faltas", body_text), Paragraph(str(kpis.get('Faltas', '-')), body_bold)],
        [Paragraph("Atestados", body_text), Paragraph(str(kpis.get('Atestados', '-')), body_bold)],
        [Paragraph("Produtividade (PHH)", body_text), Paragraph(f"{kpis.get('PPH', 0.0):.2f}" if isinstance(kpis.get('PPH'), (int, float)) else str(kpis.get('PPH', '-')), body_bold)]
    ]
    rh_table = Table(rh_rows, colWidths=[240, 120])
    rh_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('SPAN', (0,0), (1,0)),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    
    exp_pct = kpis.get('% Expedição', 0.0)
    exp_pct_str = f"{exp_pct*100:.1f}%" if isinstance(exp_pct, (int, float)) and exp_pct <= 2.0 else f"{exp_pct}%" if exp_pct else "-"
    
    vol_rows = [
        [Paragraph("Fluxo de Volumes", body_text_white), Paragraph("", body_text_white)],
        [Paragraph("Backlog Anterior", body_text), Paragraph(f"{kpis.get('Backlog Inicial', 0):,}".replace(',', '.') if isinstance(kpis.get('Backlog Inicial'), int) else str(kpis.get('Backlog Inicial', '-')), body_bold)],
        [Paragraph("Volume Planejado", body_text), Paragraph(f"{kpis.get('Volume Planejado', 0):,}".replace(',', '.') if isinstance(kpis.get('Volume Planejado'), int) else str(kpis.get('Volume Planejado', '-')), body_bold)],
        [Paragraph("Coleta Realizada", body_text), Paragraph(f"{kpis.get('Coletas Realizadas', 0):,}".replace(',', '.') if isinstance(kpis.get('Coletas Realizadas'), int) else str(kpis.get('Coletas Realizadas', '-')), body_bold)],
        [Paragraph("% Expedição", body_text), Paragraph(exp_pct_str, body_bold)],
        [Paragraph("Expedido BRE (SOC)", body_text), Paragraph(f"{kpis.get('BRE (SOC)', 0):,}".replace(',', '.') if isinstance(kpis.get('BRE (SOC)'), int) else str(kpis.get('BRE (SOC)', '-')), body_bold)],
        [Paragraph("Expedido RAO (SOC)", body_text), Paragraph(f"{kpis.get('RAO (SOC)', 0):,}".replace(',', '.') if isinstance(kpis.get('RAO (SOC)'), int) else str(kpis.get('RAO (SOC)', '-')), body_bold)]
    ]
    vol_table = Table(vol_rows, colWidths=[240, 120])
    vol_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')),
        ('SPAN', (0,0), (1,0)),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
    ]))
    
    layout_table_1 = Table([[rh_table, vol_table]], colWidths=[381, 381])
    layout_table_1.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTMARGIN', (0,0), (0,0), 20),
    ]))
    story.append(layout_table_1)
    
    story.append(PageBreak())
    
    # --- PAGE 2: TRANSPORTE & FECHAMENTO NOTES ---
    story.append(Paragraph("Recebimento de Veículos (Transporte)", section_title))
    
    transp_headers = [
        Paragraph("Veículo / SC", body_text_white),
        Paragraph("Vol. Plan.", body_text_white),
        Paragraph("Vol. Rec.", body_text_white),
        Paragraph("Previsão", body_text_white),
        Paragraph("Chegada", body_text_white),
        Paragraph("Deslacre", body_text_white),
        Paragraph("Fin. Bipagem", body_text_white),
        Paragraph("Status", body_text_white),
        Paragraph("ID Viagem", body_text_white)
    ]
    
    transp_table_rows = [transp_headers]
    for row in data['transporte']:
        transp_table_rows.append([
            Paragraph(str(row.get('VEÍCULO / SC', row.get('VECULO / SC', '-'))), body_bold),
            Paragraph(f"{row.get('VOL. PLANEJADO', 0):,}".replace(',', '.') if isinstance(row.get('VOL. PLANEJADO'), int) else str(row.get('VOL. PLANEJADO', '-')), body_text),
            Paragraph(f"{row.get('VOL. RECEBIDO', 0):,}".replace(',', '.') if isinstance(row.get('VOL. RECEBIDO'), int) else str(row.get('VOL. RECEBIDO', '-')), body_text),
            Paragraph(str(row.get('PREVISÃO', row.get('PREVISO', '-'))), body_text),
            Paragraph(str(row.get('CHEGADA', '-')), body_text),
            Paragraph(str(row.get('DESLACRE', '-')), body_text),
            Paragraph(str(row.get('FIN. BIPAGEM', '-')), body_text),
            Paragraph(str(row.get('STATUS', 'FINALIZADO')), body_text),
            Paragraph(str(row.get("ID's", '-')), body_text)
        ])
        
    transp_table = Table(transp_table_rows, colWidths=[80, 80, 80, 70, 70, 70, 80, 80, 152])
    transp_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
    ]))
    story.append(transp_table)
    # 4. Tabela e Gráfico de Gestão (Backlog & Sem Mov) no PDF
    gest = data.get('gestao', {})
    gest_table_rows = [
        [
            Paragraph("<b>Indicador</b>", body_text_white),
            Paragraph("<b>1 Dia</b>", body_text_white),
            Paragraph("<b>2 a 4 d</b>", body_text_white),
            Paragraph("<b>5 dias</b>", body_text_white),
            Paragraph("<b>6 a 9 d</b>", body_text_white),
            Paragraph("<b>10 D+</b>", body_text_white),
            Paragraph("<b>Total</b>", body_text_white)
        ]
    ]
    
    if gest:
        def fmt_num(v):
            if v == 0 or v == "-":
                return "-"
            return f"{v:,}".replace(',', '.')
            
        b_ini = gest.get('backlog_inicial', {})
        b_fim = gest.get('backlog_final', {})
        b_var = gest.get('variacao_backlog', {})
        
        s_ini = gest.get('sem_mov_inicial', {})
        s_fim = gest.get('sem_mov_final', {})
        s_var = gest.get('variacao_sem_mov', {})
        
        gest_table_rows.append([
            Paragraph("Backlog Inicial", body_text),
            Paragraph(fmt_num(b_ini.get('1_dia', 0)), body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph(fmt_num(b_ini.get('total', 0)), body_text)
        ])
        gest_table_rows.append([
            Paragraph("Backlog Final", body_text),
            Paragraph(fmt_num(b_fim.get('1_dia', 0)), body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph("-", body_text),
            Paragraph(fmt_num(b_fim.get('total', 0)), body_text)
        ])
        gest_table_rows.append([
            Paragraph("Variação Backlog", body_bold),
            Paragraph(str(b_var.get('1_dia', '-')), body_bold),
            Paragraph("-", body_bold),
            Paragraph("-", body_bold),
            Paragraph("-", body_bold),
            Paragraph("-", body_bold),
            Paragraph(str(b_var.get('total', '-')), body_bold)
        ])
        gest_table_rows.append([
            Paragraph("Sem Mov Inicial", body_text),
            Paragraph(fmt_num(s_ini.get('1_dia', 0)), body_text),
            Paragraph(fmt_num(s_ini.get('2_4_dias', 0)), body_text),
            Paragraph(fmt_num(s_ini.get('5_dias', 0)), body_text),
            Paragraph(fmt_num(s_ini.get('6_9_dias', 0)), body_text),
            Paragraph(fmt_num(s_ini.get('10_dias_mais', 0)), body_text),
            Paragraph(fmt_num(s_ini.get('total', 0)), body_text)
        ])
        gest_table_rows.append([
            Paragraph("Sem Mov Final", body_text),
            Paragraph(fmt_num(s_fim.get('1_dia', 0)), body_text),
            Paragraph(fmt_num(s_fim.get('2_4_dias', 0)), body_text),
            Paragraph(fmt_num(s_fim.get('5_dias', 0)), body_text),
            Paragraph(fmt_num(s_fim.get('6_9_dias', 0)), body_text),
            Paragraph(fmt_num(s_fim.get('10_dias_mais', 0)), body_text),
            Paragraph(fmt_num(s_fim.get('total', 0)), body_text)
        ])
        gest_table_rows.append([
            Paragraph("Variação Sem Mov", body_bold),
            Paragraph(str(s_var.get('1_dia', '-')), body_bold),
            Paragraph(str(s_var.get('2_4_dias', '-')), body_bold),
            Paragraph(str(s_var.get('5_dias', '-')), body_bold),
            Paragraph(str(s_var.get('6_9_dias', '-')), body_bold),
            Paragraph(str(s_var.get('10_dias_mais', '-')), body_bold),
            Paragraph(str(s_var.get('total', '-')), body_bold)
        ])
    else:
        gest_table_rows.append([Paragraph("Sem dados de gestão", body_text)] + [Paragraph("-", body_text)] * 6)
        
    gest_pdf_table = Table(gest_table_rows, colWidths=[160, 100, 100, 100, 100, 100, 100])
    gest_pdf_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
        ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ('TOPPADDING', (0,0), (-1,-1), 5),
        ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
        ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (1,0), (-1,-1), 'CENTER')
    ]))
    
    # Gráfico comparativo de Sem Mov (Largura completa)
    gest_drawing = Drawing(760, 160)
    gest_chart = VerticalBarChart()
    gest_chart.x = 40
    gest_chart.y = 20
    gest_chart.height = 120
    gest_chart.width = 680
    
    if gest:
        gest_chart.data = [
            [s_ini.get('1_dia', 0), s_ini.get('2_4_dias', 0), s_ini.get('5_dias', 0), s_ini.get('6_9_dias', 0), s_ini.get('10_dias_mais', 0)],
            [s_fim.get('1_dia', 0), s_fim.get('2_4_dias', 0), s_fim.get('5_dias', 0), s_fim.get('6_9_dias', 0), s_fim.get('10_dias_mais', 0)]
        ]
    else:
        gest_chart.data = [[0, 0, 0, 0, 0], [0, 0, 0, 0, 0]]
        
    gest_chart.categoryAxis.categoryNames = ['1 Dia', '2 a 4 dias', '5 dias', '6 a 9 dias', '10 Dias +']
    gest_chart.valueAxis.valueMin = 0
    max_val = max(max(gest_chart.data[0]), max(gest_chart.data[1]))
    gest_chart.valueAxis.valueMax = int(max_val) + 10 if max_val > 0 else 100
    gest_chart.valueAxis.valueStep = max(10, int((max_val / 5) / 10) * 10) if max_val > 0 else 20
    
    gest_chart.bars[0].fillColor = colors.HexColor('#EF4444')
    gest_chart.bars[1].fillColor = colors.HexColor('#10B981')
    gest_chart.categoryAxis.labels.fontSize = 8
    gest_chart.valueAxis.labels.fontSize = 8
    gest_drawing.add(gest_chart)
        
    # Detalhamento de Expedição (Rotas)
    exp_detalhe = data.get('expedicao_detalhe', [])
    
    def get_sort_key(item):
        route_name = str(item.get('route', '')).strip()
        vol = str(item.get('vol', '')).strip().upper()
        is_cancelled = (vol == 'CANCELADO')
        return (is_cancelled, route_name.lower())
        
    sorted_exp = sorted(exp_detalhe, key=get_sort_key)
    
    # Divide as rotas dinamicamente ao meio (lado a lado) para balanceamento perfeito
    half = math.ceil(len(sorted_exp) / 2)
    first_half = sorted_exp[:half]
    second_half = sorted_exp[half:]
    
    def build_route_table(data_list):
        rows = [
            [
                Paragraph("<b>Destino / Rota</b>", route_hdr_left),
                Paragraph("<b>Volume Expedido</b>", route_hdr_right),
                Paragraph("<b>Hora Real de Saída</b>", route_hdr_right),
                Paragraph("<b>Horário de Corte</b>", route_hdr_right),
                Paragraph("<b>Status</b>", route_hdr_center)
            ]
        ]
        
        if not data_list:
            rows.append([
                Paragraph("Nenhuma expedição registrada.", route_body_center),
                "", "", "", ""
            ])
            
        for row in data_list:
            route = row.get('route', '-')
            vol = row.get('vol', 0)
            dep = row.get('departure', '-')
            cutoff = row.get('cutoff', '-')
            status = row.get('status', '-')
            
            if isinstance(vol, (int, float)):
                vol_str = f"{int(vol):,}".replace(',', '.')
            else:
                vol_str = str(vol)
                
            if status == "OK":
                status_p = Paragraph('<font color="#10B981"><b>OK</b></font>', route_body_center_bold)
            else:
                status_p = Paragraph('<font color="#EF4444"><b>FORA</b></font>', route_body_center_bold)
                
            rows.append([
                Paragraph(route, route_body_left_bold),
                Paragraph(vol_str, route_body_right),
                Paragraph(dep, route_body_right),
                Paragraph(cutoff, route_body_right),
                status_p
            ])
            
        col_widths = [110, 65, 75, 70, 50]  # Total: 370
        t = Table(rows, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#10B981')), # Green header to match expedition theme
            ('BOTTOMPADDING', (0,0), (-1,-1), 3),
            ('TOPPADDING', (0,0), (-1,-1), 3),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        if not data_list:
            t.setStyle(TableStyle([
                ('SPAN', (0,1), (-1,1)),
            ]))
        return t
        
    # Adiciona a seção de Gestão na Página 3
    story.append(PageBreak())
    story.append(Paragraph("Gestão de Turno", section_title))
    story.append(Paragraph("<b>Gestão de Backlog & Sem Movimentação</b>", ParagraphStyle('GestTitle', parent=body_bold, fontSize=11, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)))
    story.append(gest_pdf_table)
    story.append(Spacer(1, 15))
    story.append(gest_drawing)
    
    # Adiciona a seção de Expedição na Página 4 (permitindo quebra automática para a pág 5 se necessário)
    story.append(PageBreak())
    story.append(Paragraph("Detalhamento de Expedição (Rotas)", section_title))
    story.append(Paragraph("<b>Expedição por Rota</b>", ParagraphStyle('ExpTitle', parent=body_bold, fontSize=11, textColor=colors.HexColor('#10B981'), spaceAfter=8)))
    
    # Divide as tabelas em blocos para evitar LayoutError por estouro de página
    chunk_size = 15
    for i in range(0, len(first_half), chunk_size):
        first_half_chunk = first_half[i:i+chunk_size]
        second_half_chunk = second_half[i:i+chunk_size]
        
        t1 = build_route_table(first_half_chunk)
        t2 = build_route_table(second_half_chunk)
        
        exp_pdf_table = Table([[t1, '', '', t2]], colWidths=[370, 10, 10, 370])
        exp_pdf_table.setStyle(TableStyle([
            ('VALIGN', (0,0), (-1,-1), 'TOP'),
            ('LEFTPADDING', (0,0), (-1,-1), 0),
            ('RIGHTPADDING', (0,0), (-1,-1), 0),
            ('TOPPADDING', (0,0), (-1,-1), 0),
            ('BOTTOMPADDING', (0,0), (-1,-1), 0),
            ('LINEBEFORE', (2,0), (2,-1), 0.5, colors.HexColor('#D1D5DB')), # Linha separadora vertical
        ]))
        story.append(exp_pdf_table)
        story.append(Spacer(1, 15))

    # Adiciona a seção de Taxa de Expedição no Prazo (HUB -> PDD) no PDF
    taxa_prazo_data = data.get('taxa_expedicao_prazo', {})
    taxa_items = taxa_prazo_data.get('items', [])
    taxa_totais = taxa_prazo_data.get('totais', {})
    if taxa_items:
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Taxa de Expedição no Prazo (HUB &rarr; PDD)</b>", ParagraphStyle('TaxaTitle', parent=body_bold, fontSize=11, textColor=colors.HexColor('#1E3A8A'), spaceAfter=8)))
        taxa_headers = [
            Paragraph("<b>Destino / Rota</b>", route_hdr_left),
            Paragraph("<b>Qtd a Expedir</b>", route_hdr_right),
            Paragraph("<b>No Prazo</b>", route_hdr_right),
            Paragraph("<b>Fora do Prazo</b>", route_hdr_right),
            Paragraph("<b>Anormalidade</b>", route_hdr_right),
            Paragraph("<b>Taxa no Prazo</b>", route_hdr_center),
            Paragraph("<b>Status</b>", route_hdr_center)
        ]
        taxa_rows = [taxa_headers]
        for it in taxa_items:
            pct = it.get('taxa_prazo', 0.0)
            status_color = '#10B981' if pct >= 0.90 else ('#F59E0B' if pct >= 0.70 else '#EF4444')
            status_txt = 'OK' if pct >= 0.90 else ('ATENÇÃO' if pct >= 0.70 else 'CRÍTICO')
            rota_txt = f"{it.get('rota')} ({it.get('ref_data')})" if it.get('ref_data') else str(it.get('rota', '-'))
            taxa_rows.append([
                Paragraph(rota_txt, route_body_left_bold),
                Paragraph(f"{it.get('qtd_expedir', 0):,}".replace(',', '.'), route_body_right),
                Paragraph(f"{it.get('no_prazo', 0):,}".replace(',', '.'), route_body_right),
                Paragraph(f"{it.get('fora_prazo', 0):,}".replace(',', '.'), route_body_right),
                Paragraph(f"{it.get('anormalidade', 0):,}".replace(',', '.'), route_body_right),
                Paragraph(f"<font color='{status_color}'><b>{it.get('taxa_prazo_str', '-')}</b></font>", route_body_center),
                Paragraph(f"<font color='{status_color}'><b>{status_txt}</b></font>", route_body_center_bold)
            ])
        if taxa_totais and taxa_totais.get('qtd_expedir', 0) > 0:
            tot_pct = taxa_totais.get('taxa_prazo', 0.0)
            tot_color = '#10B981' if tot_pct >= 0.90 else ('#F59E0B' if tot_pct >= 0.70 else '#EF4444')
            tot_status = 'OK' if tot_pct >= 0.90 else ('ATENÇÃO' if tot_pct >= 0.70 else 'CRÍTICO')
            taxa_rows.append([
                Paragraph("<b>TOTAL CONSOLIDADO</b>", route_body_left_bold),
                Paragraph(f"<b>{taxa_totais.get('qtd_expedir', 0):,}</b>".replace(',', '.'), route_body_right),
                Paragraph(f"<b>{taxa_totais.get('no_prazo', 0):,}</b>".replace(',', '.'), route_body_right),
                Paragraph(f"<b>{taxa_totais.get('fora_prazo', 0):,}</b>".replace(',', '.'), route_body_right),
                Paragraph(f"<b>{taxa_totais.get('anormalidade', 0):,}</b>".replace(',', '.'), route_body_right),
                Paragraph(f"<font color='{tot_color}'><b>{taxa_totais.get('taxa_prazo_str', '-')}</b></font>", route_body_center),
                Paragraph(f"<font color='{tot_color}'><b>{tot_status}</b></font>", route_body_center_bold)
            ])
        t_taxa = Table(taxa_rows, colWidths=[150, 100, 100, 100, 100, 100, 110])
        t_taxa.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.HexColor('#1E3A8A')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ('TOPPADDING', (0,0), (-1,-1), 4),
            ('LEFTPADDING', (0,0), (-1,-1), 6),
            ('RIGHTPADDING', (0,0), (-1,-1), 6),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, colors.HexColor('#F3F4F6')]),
            ('GRID', (0,0), (-1,-1), 0.5, colors.HexColor('#E5E7EB')),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ]))
        story.append(t_taxa)
        story.append(Spacer(1, 15))
    
    doc.build(story, canvasmaker=NumberedCanvas)
    
    buffer.seek(0)
    now_str = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"Relatorio_Fechamento_{now_str}.pdf"
    
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )

# Constants and helpers for Recebimento
RECEBIMENTO_FILE = 'Recebimento.xlsx'

def _load_recebimento_data_raw():
    if not os.path.exists(RECEBIMENTO_FILE):
        return {}
        
    try:
        import openpyxl
        import datetime
        # Carrega a planilha avaliando as fórmulas para obter valores numéricos
        wb = openpyxl.load_workbook(RECEBIMENTO_FILE, data_only=True)
        if 'Planilha1' not in wb.sheetnames:
            return {}
        ws = wb['Planilha1']
        
        records = []
        date_recebimento = {}
        r = 1
        max_r = ws.max_row
        
        current_date = None
        current_car = None
        current_total = 0
        current_coleta = 0
        current_lote = 0
        current_sem_bipe = 0
        
        while r <= max_r:
            val_a = ws.cell(row=r, column=1).value
            val_b = ws.cell(row=r, column=2).value
            val_c = ws.cell(row=r, column=3).value
            
            if val_a is not None:
                val_a_str = str(val_a).strip().lower()
                
                # 1. Identifica cabeçalho de data. A data em si estará na linha seguinte (r+1)
                if val_a_str == 'data':
                    next_val = ws.cell(row=r+1, column=1).value
                    if next_val is not None:
                        if isinstance(next_val, (datetime.datetime, datetime.date)):
                            current_date = next_val.strftime('%d.%m.%Y')
                        else:
                            # Tenta tratar strings e normaliza
                            current_date = str(next_val).strip()
                    r += 2
                    continue
                    
                # 2. Identifica cabeçalho do carro/caminhão. O nome do veículo está na coluna B (val_b)
                elif val_a_str == 'carro':
                    current_car = str(val_b).strip() if val_b is not None else None
                    
                # 3. Identifica a linha de Recebimento do dia
                elif val_a_str == 'recebimento':
                    try:
                        date_recebimento[current_date] = int(float(val_b)) if val_b is not None else 0
                    except:
                        date_recebimento[current_date] = 0
                    
                # 4. Identifica sub-itens de recebimento (Verifica 'sem bipe' antes para evitar colisão com 'coleta de chegada')
                elif 'sem bipe' in val_a_str:
                    try:
                        current_sem_bipe = int(float(val_b)) if val_b is not None else 0
                    except:
                        current_sem_bipe = 0
                    
                    # 'sem bipe' é o último item do bloco. Salva o registro consolidado
                    if current_car:
                        records.append({
                            'date': current_date,
                            'car': current_car,
                            'total': current_total,
                            'coleta': current_coleta,
                            'lote': current_lote,
                            'sem_bipe': current_sem_bipe
                        })
                        # Limpa variáveis específicas do veículo
                        current_car = None
                        current_total = 0
                        current_coleta = 0
                        current_lote = 0
                        current_sem_bipe = 0
                        
                elif 'coleta de chegada' in val_a_str:
                    try:
                        current_coleta = int(float(val_b)) if val_b is not None else 0
                    except:
                        current_coleta = 0
                    try:
                        current_total = int(float(val_c)) if val_c is not None else 0
                    except:
                        current_total = 0
                        
                elif 'inserido em lote' in val_a_str:
                    try:
                        current_lote = int(float(val_b)) if val_b is not None else 0
                    except:
                        current_lote = 0
            r += 1
            
        return {
            'records': records,
            'date_recebimento': date_recebimento
        }
    except Exception as e:
        print("Erro ao processar Recebimento.xlsx:", e)
        return {}

def load_recebimento_data():
    return get_from_cache(RECEBIMENTO_FILE, _load_recebimento_data_raw)

@app.route('/api/recebimento/filters')
def get_recebimento_filters():
    data = load_recebimento_data()
    dates = set()
    if 'records' in data:
        for r in data['records']:
            if r['date']:
                dates.add(r['date'])
    sorted_dates = sorted(list(dates), key=lambda d: [int(x) for x in d.split('.') if x.isdigit()][::-1], reverse=True)
    return jsonify({
        'dates': sorted_dates
    })

@app.route('/api/recebimento/data')
def get_recebimento_data():
    date_val = request.args.get('date')
    data = load_recebimento_data()
    
    dates = set()
    if 'records' in data:
        for r in data['records']:
            if r['date']:
                dates.add(r['date'])
    sorted_dates = sorted(list(dates), key=lambda d: [int(x) for x in d.split('.') if x.isdigit()][::-1], reverse=True)
    
    if not date_val and sorted_dates:
        date_val = sorted_dates[0]
        
    filtered = []
    if 'records' in data:
        filtered = [r for r in data['records'] if r['date'] == date_val]
        
    recebimento_vol = data.get('date_recebimento', {}).get(date_val, 0)
    
    # Histórico de comparação com até 4 dias anteriores (totalizando 5 dias, ordenados cronologicamente do mais antigo para o mais recente)
    history = []
    try:
        idx = sorted_dates.index(date_val)
        target_dates = sorted_dates[idx : idx + 5]
        for d in target_dates[::-1]:
            d_records = [r for r in data.get('records', []) if r['date'] == d]
            d_sem_bipe = sum(r['sem_bipe'] for r in d_records)
            d_recebimento = data.get('date_recebimento', {}).get(d, 0)
            history.append({
                'date': d,
                'recebimento_total': d_recebimento,
                'sem_bipe_total': d_sem_bipe
            })
    except Exception as ex:
        print("Erro ao calcular histórico:", ex)
        
    return jsonify({
        'date': date_val,
        'recebimento_total': recebimento_vol,
        'left_table': filtered,
        'right_table': [],
        'history': history
    })


# ====================================================
# MÓDULO DE CONTROLE DE VOLUMETRIA DIÁRIA
# ====================================================
VOLUMETRIA_JSON_FILE = "volumetria_data.json"
VOLUMETRIA_EXCEL_FILE = "volumetria.xlsx"

def _load_volumetria_data_internal():
    # 1. Tenta carregar do arquivo JSON estruturado (onde estão as edições salvas)
    if os.path.exists(VOLUMETRIA_JSON_FILE):
        try:
            with open(VOLUMETRIA_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if data and "records" in data and len(data["records"]) > 0:
                    return _process_volumetria_kpis(data)
        except Exception as e:
            print("Erro ao ler volumetria_data.json:", e)
    return None

ALLOWED_VOLUMETRIA_PDD = ['SP BRE', 'SN RAO', 'F IBG-SP', 'EXT -MG']

def _sort_volumetria_records(records):
    """Ordena os registros da Volumetria Diária agrupando por base (SP BRE, SN RAO, IBG, EXT) e horário."""
    if not records:
        return []
        
    def sort_key(r):
        pdd = str(r.get("pdd_saida") or "").strip().upper()
        if "SP BRE" in pdd or "BRE" in pdd:
            pdd_prio = 1
        elif "SN RAO" in pdd or "RAO" in pdd:
            pdd_prio = 2
        elif "IBG" in pdd:
            pdd_prio = 3
        elif "EXT" in pdd:
            pdd_prio = 4
        else:
            pdd_prio = 5
        
        prev = str(r.get("previsao_chegada") or "").strip()
        id_tr = str(r.get("id_transporte") or "")
        return (pdd_prio, pdd, prev, id_tr)

    return sorted(records, key=sort_key)

def _is_allowed_volumetria_car(pdd, route_name='', status=''):
    pdd_clean = str(pdd or '').strip().upper()
    status_clean = str(status or '').upper()
    route_clean = str(route_name or '').strip().upper()
    
    # Exclui explicitamente 'DC EXT'
    if 'DC EXT' in pdd_clean or 'DC EXT' in route_clean:
        return False
        
    for allowed in ALLOWED_VOLUMETRIA_PDD:
        a_norm = allowed.replace(' ', '').replace('-', '').upper()
        p_norm = pdd_clean.replace(' ', '').replace('-', '').upper()
        r_norm = route_clean.replace(' ', '').replace('-', '').upper()
        if a_norm in p_norm or p_norm in a_norm or a_norm in r_norm or pdd_clean == allowed.upper():
            return True
    return False

def _parse_volumetria_excel(file_path):
    try:
        # 1. Carrega o arquivo via pandas (suporta .xlsx, .xls e .csv)
        df = None
        ext = file_path.rsplit('.', 1)[-1].lower() if '.' in file_path else ''
        if ext == 'csv':
            try:
                df = pd.read_csv(file_path, encoding='utf-8')
            except Exception:
                df = pd.read_csv(file_path, encoding='latin1', sep=None, engine='python')
        else:
            try:
                df = pd.read_excel(file_path)
            except Exception as e_pd:
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(file_path, data_only=True)
                    sheet = wb["Volumetria"] if "Volumetria" in wb.sheetnames else wb.active
                    data = list(sheet.values)
                    if data and len(data) > 1:
                        df = pd.DataFrame(data[1:], columns=data[0])
                except Exception:
                    raise e_pd

        if df is None or len(df) == 0:
            return None

        # Limpa nomes de colunas
        df.columns = [str(c).strip() for c in df.columns]
        
        def find_col(possible_names, exclude_names=None):
            if exclude_names is None:
                exclude_names = []
            for name in possible_names:
                for col in df.columns:
                    c_low = col.lower()
                    if name in c_low and not any(exc in c_low for exc in exclude_names):
                        return col
            return None

        col_id = find_col(['tarefa de transporte', 'id_transporte', 'id transporte', 'transporte'])
        col_status_v = find_col(['status de viagem', 'status da viagem', 'status viagem', 'status'])
        col_pdd = find_col(['pdd de saida', 'pdd de saída', 'pdd saida', 'pdd saída', 'pdd', 'origem'], exclude_names=['chegada'])
        col_rota = find_col(['nome da rota', 'nome da viagem', 'rota', 'viagem'])
        col_pedido = find_col(['pedido mãe', 'pedido mae', 'pedido sistema', 'pedido sist', 'volume previsto', 'previsto'])
        col_prev_chegada = find_col(['previsão de chegada', 'previsao de chegada', 'previsão chegada', 'previsao chegada', 'hora de saída planejada', 'hora de saida planejada', 'hora estimada de chegada', 'chegada planejada', 'previsão'], exclude_names=['pdd', 'estação', 'descarregamento'])
        col_chegada_real = find_col(['tempo real de chegada', 'chegada real', 'horário de chegada', 'horario de chegada', 'hora real de chegada', 'chegada'], exclude_names=['pdd', 'estação', 'descarregamento', 'planejada', 'previsão', 'previsao'])
        col_inicio = find_col(['horário do bipe de carregamento para expedição', 'horario do bipe', 'início coleta', 'inicio coleta', 'horário de check-in do motorista', 'check-in'])
        col_fim = find_col(['horário de lacração do veículo', 'horario de lacracao', 'fim coleta', 'hora de saída real', 'hora de saida real', 'horário de check-out do codutor'])
        col_bipado = find_col(['volume bipado', 'bipados', 'bipado'])
        col_obs = find_col(['obs', 'observações', 'observacao', 'observacoes'])

        def format_time_val(val):
            if pd.isna(val) or val is None or str(val).strip() in ['', 'nan', 'NaT', 'None']:
                return ''
            if isinstance(val, (datetime, pd.Timestamp)):
                return val.strftime('%H:%M')
            s = str(val).strip()
            if ' ' in s:
                s = s.split(' ')[1]
            parts = s.split(':')
            if len(parts) >= 2:
                return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
            return s

        def format_int_val(val):
            if pd.isna(val) or val is None:
                return 0
            if isinstance(val, (int, float)):
                return int(val)
            s = str(val).strip()
            if not s or s.lower() == 'nan':
                return 0
            if ',' in s and '.' in s:
                s = s.replace('.', '').replace(',', '.')
            elif ',' in s:
                s = s.replace(',', '.')
            try:
                return int(float(s))
            except:
                return 0

        # Extrai data de referência se possível (da coluna de saída planejada ou criação)
        ref_date = datetime.now().strftime("%d/%m/%Y")
        col_data = find_col(['hora de saída planejada', 'hora de saida planejada', 'previsão de chegada', 'data e hora de criação', 'data criacao', 'data'])
        if col_data and len(df[col_data].dropna()) > 0:
            first_val = df[col_data].dropna().iloc[0]
            if isinstance(first_val, (datetime, pd.Timestamp)):
                ref_date = first_val.strftime("%d/%m/%Y")
            elif isinstance(first_val, str) and len(first_val) >= 10:
                try:
                    d_part = first_val[:10]
                    if '-' in d_part:
                        dt = datetime.strptime(d_part, "%Y-%m-%d")
                        ref_date = dt.strftime("%d/%m/%Y")
                    elif '/' in d_part:
                        ref_date = d_part
                except:
                    pass

        records = []
        coletas_val = 10790
        backlog_val = 0

        for _, row in df.iterrows():
            pdd_val = str(row[col_pdd] if col_pdd and pd.notna(row[col_pdd]) else '').strip()
            rota_val = str(row[col_rota] if col_rota and pd.notna(row[col_rota]) else '').strip()
            status_v = str(row[col_status_v] if col_status_v and pd.notna(row[col_status_v]) else 'Em Trânsito: 在途').strip()
            
            # FILTRO OBRIGATÓRIO: Mantém APENAS os carros permitidos (SP BRE, SN RAO, F IBG-SP, EXT -MG)
            if not _is_allowed_volumetria_car(pdd_val, rota_val, status_v):
                continue

            id_tr = str(row[col_id] if col_id and pd.notna(row[col_id]) else '').strip()
            if not id_tr or id_tr.upper().startswith('PREVISTO') or id_tr.upper().startswith('TOTAL'):
                continue
            
            # Pedido Sistema
            ped_sis = format_int_val(row[col_pedido]) if col_pedido and pd.notna(row[col_pedido]) else 0
            
            # Bipado (inicia zerado para preenchimento operacional)
            bip = format_int_val(row[col_bipado]) if col_bipado and pd.notna(row[col_bipado]) else 0

            # Previsão de Chegada (preenchida automaticamente da planilha)
            prev_chegada = format_time_val(row[col_prev_chegada]) if col_prev_chegada and pd.notna(row[col_prev_chegada]) else ''
            if not prev_chegada:
                for alt_col in ['Previsão de chegada', 'previsao de chegada', 'Hora de saída planejada', 'hora de saida planejada']:
                    if alt_col in row and pd.notna(row[alt_col]):
                        prev_chegada = format_time_val(row[alt_col])
                        if prev_chegada:
                            break

            # Chegada Real, Início Coleta, Fim Coleta e Status (iniciam sem preencher para preenchimento manual do operador)
            chegada = ''
            ini_col = ''
            fim_col = ''
            st = ''
            bip = 0

            obs = str(row[col_obs] if col_obs and pd.notna(row[col_obs]) else '').strip()
            if obs.lower() == 'nan':
                obs = ''

            records.append({
                "id_transporte": id_tr,
                "status_viagem": status_v,
                "pdd_saida": pdd_val,
                "pedido_sistema": ped_sis,
                "previsao_chegada": prev_chegada,
                "chegada_real": chegada,
                "inicio_coleta": ini_col,
                "fim_coleta": fim_col,
                "status": st,
                "obs": obs,
                "bipado": bip
            })

        records = _sort_volumetria_records(records)

        return {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_referencia": ref_date,
            "coletas": coletas_val,
            "backlog": backlog_val,
            "records": records
        }
    except Exception as e:
        print("Erro ao processar planilha de volumetria:", e)
        return None

def _process_volumetria_kpis(data):
    records = _sort_volumetria_records(data.get("records", []))
    
    total_previsto = sum(int(r.get("pedido_sistema") or 0) for r in records)
    total_bipados = sum(int(r.get("bipado") or 0) for r in records)
    coletas = int(data.get("coletas") or 0)
    
    total_no_piso = total_bipados + coletas
    diferenca = total_bipados - total_previsto
    eficiencia = (total_bipados / total_previsto * 100.0) if total_previsto > 0 else 100.0
    
    # Contagens por status de viagem
    status_viagem_counts = {}
    for r in records:
        sv = r.get("status_viagem", "Outro")
        sv_clean = sv.split(":")[0].strip() if ":" in sv else sv
        status_viagem_counts[sv_clean] = status_viagem_counts.get(sv_clean, 0) + 1

    # Status operacional
    status_operacional_counts = {}
    for r in records:
        st = r.get("status", "FINALIZADO").upper()
        status_operacional_counts[st] = status_operacional_counts.get(st, 0) + 1
        
    return {
        "updated_at": data.get("updated_at", datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        "data_referencia": data.get("data_referencia", datetime.now().strftime("%d/%m/%Y")),
        "kpis": {
            "previsto": total_previsto,
            "bipados": total_bipados,
            "coletas": coletas,
            "total_no_piso": total_no_piso,
            "diferenca": diferenca,
            "eficiencia": round(eficiencia, 2),
            "total_viagens": len(records),
            "viagens_finalizadas": status_operacional_counts.get("FINALIZADO", 0)
        },
        "status_viagem_dist": status_viagem_counts,
        "status_operacional_dist": status_operacional_counts,
        "records": records
    }

@app.route('/api/volumetria/data')
def get_volumetria_data():
    try:
        data = db.get_volumetria_data()
        if data and len(data.get("records", [])) > 0:
            return jsonify(data)
    except Exception as err:
        print("Erro ao carregar volumetria do banco:", err)
    data = _load_volumetria_data_internal()
    if data and len(data.get("records", [])) > 0:
        try:
            db.save_volumetria_data(data)
        except Exception:
            pass
    return jsonify(data)

@app.route('/api/volumetria/upload', methods=['POST'])
def upload_volumetria_file():
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "Nenhum arquivo enviado."}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"success": False, "error": "Nome de arquivo vazio."}), 400
        
    ext = file.filename.rsplit('.', 1)[-1].lower()
    if ext not in ['xlsx', 'xls', 'csv']:
        return jsonify({"success": False, "error": "Formato de arquivo não suportado. Envie .xlsx, .xls ou .csv"}), 400
        
    try:
        temp_path = os.path.join(os.getcwd(), f"temp_volumetria.{ext}")
        file.save(temp_path)
        
        parsed = _parse_volumetria_excel(temp_path)
        if not parsed or len(parsed.get("records", [])) == 0:
            try:
                os.replace(temp_path, VOLUMETRIA_EXCEL_FILE)
                parsed = _parse_volumetria_excel(VOLUMETRIA_EXCEL_FILE)
            except Exception:
                pass
        else:
            try:
                os.replace(temp_path, VOLUMETRIA_EXCEL_FILE)
            except Exception:
                pass
            
        if parsed and len(parsed.get("records", [])) > 0:
            # Persistência no banco SQLite (substituindo registros anteriores para manter apenas os carros filtrados)
            db.save_volumetria_data(parsed, replace_all=True)
            db.log_upload("Volumetria Diária", file.filename, len(parsed.get("records", [])))
            
            # Backup no arquivo JSON
            with open(VOLUMETRIA_JSON_FILE, "w", encoding="utf-8") as f:
                json.dump(parsed, f, ensure_ascii=False, indent=2)
                
            processed = db.get_volumetria_data()

            return jsonify({"success": True, "data": processed, "message": f"Planilha importada com sucesso! {len(parsed.get('records', []))} carros filtrados (SP BRE, SN RAO, IBG, EXT)."})
        else:
            return jsonify({"success": False, "error": "Nenhum dos carros permitidos (SP BRE, SN RAO, IBG, EXT) foi encontrado na planilha."}), 400
    except Exception as e:
        return jsonify({"success": False, "error": f"Erro ao processar o arquivo: {str(e)}"}), 500

@app.route('/api/volumetria/save', methods=['POST'])
def save_volumetria_data():
    try:
        payload = request.get_json(force=True)
        if not payload or "records" not in payload:
            return jsonify({"success": False, "error": "Dados inválidos."}), 400
            
        payload["records"] = _sort_volumetria_records(payload.get("records", []))
        payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Persistência no banco SQLite
        db.save_volumetria_data(payload)
        
        # Backup no arquivo JSON
        with open(VOLUMETRIA_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)
            
        processed = db.get_volumetria_data()
        return jsonify({"success": True, "data": processed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/volumetria/delete', methods=['POST'])
def delete_volumetria_truck():
    try:
        payload = request.get_json(force=True)
        id_transporte = str(payload.get("id_transporte") or "").strip()
        if not id_transporte:
            return jsonify({"success": False, "error": "ID de Transporte não informado."}), 400
            
        db.delete_volumetria_viagem(id_transporte)
        
        # Atualiza JSON de backup
        if os.path.exists(VOLUMETRIA_JSON_FILE):
            try:
                with open(VOLUMETRIA_JSON_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data and "records" in data:
                    data["records"] = [r for r in data["records"] if str(r.get("id_transporte") or "").strip() != id_transporte]
                    with open(VOLUMETRIA_JSON_FILE, "w", encoding="utf-8") as f:
                        json.dump(data, f, ensure_ascii=False, indent=2)
            except Exception as ex:
                print("Erro ao atualizar JSON após exclusão:", ex)
                
        processed = db.get_volumetria_data()
        return jsonify({"success": True, "data": processed, "message": f"Viagem {id_transporte} excluída com sucesso."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500







@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


# ==============================================================================
# MÓDULO DE RANKING DE PRODUTIVIDADE E HORA A HORA
# ==============================================================================
RANKING_JSON_FILE = "ranking_data.json"

def _detect_sector_from_name(name):
    n = str(name).lower()
    if any(k in n for k in ['coleta', 'chegada', 'inbound', 'receb', 'descarga']):
        return 'Coleta de Chegadas'
    elif any(k in n for k in ['lote', 'inserid', 'triagem', 'gaiola', 'sorting', 'bipagem lote']):
        return 'Inserido em Lote'
    elif any(k in n for k in ['exped', 'despacho', 'saida', 'saída', 'outbound', 'carreg']):
        return 'Expedição'
    return None

def _deduplicate_columns(df):
    """Garante que todos os nomes de colunas do DataFrame sejam únicos."""
    if df is None:
        return None
    cols = []
    count = {}
    for col in df.columns:
        c = str(col).strip()
        if c in count:
            count[c] += 1
            cols.append(f"{c}_{count[c]}")
        else:
            count[c] = 0
            cols.append(c)
    df.columns = cols
    return df

def _clean_dataframe_headers(df):
    """Detecta se o cabeçalho real está nas primeiras 10 linhas e o ajusta em memória."""
    if df is None or len(df) == 0:
        return df
    df = _deduplicate_columns(df)
    cols_str = " ".join([str(c).lower() for c in df.columns])
    if any(k in cols_str for k in ['digitaliz', 'operador', 'colaborador', 'hora', 'tempo', 'bip', 'tipo', 'qtd', 'volume', 'nome', 'user', 'pacote', 'status']):
        return df
    for idx in range(min(10, len(df))):
        row_vals = [str(x).lower() for x in df.iloc[idx].values if pd.notna(x)]
        row_str = " ".join(row_vals)
        if any(k in row_str for k in ['digitaliz', 'operador', 'colaborador', 'hora', 'tempo', 'bip', 'tipo', 'qtd', 'volume', 'nome', 'user', 'pacote', 'status']):
            df.columns = [str(c).strip() for c in df.iloc[idx]]
            df = _deduplicate_columns(df)
            return df.iloc[idx + 1:].reset_index(drop=True)
    return df

def _read_dataframe_fast(file_path, sheet_name=0):
    """Lê arquivo CSV ou Excel de forma ultra rápida com calamine e passagem única."""
    ext = file_path.rsplit('.', 1)[-1].lower()
    if ext == 'csv':
        for enc in ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']:
            for sep in [',', ';', '\t', '|']:
                try:
                    df = pd.read_csv(file_path, sep=sep, encoding=enc, low_memory=False)
                    if len(df.columns) > 1 and len(df) > 0:
                        return _clean_dataframe_headers(df)
                except Exception:
                    continue
        try:
            return _clean_dataframe_headers(pd.read_csv(file_path, low_memory=False))
        except Exception:
            return None
    else:
        # Tenta com engine calamine (ultra-rápido em C/Rust)
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='calamine')
            return _clean_dataframe_headers(df)
        except Exception:
            try:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                return _clean_dataframe_headers(df)
            except Exception:
                try:
                    df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
                    return _clean_dataframe_headers(df)
                except Exception:
                    return None

def _parse_ranking_file(file_path, sector_hint=None):
    """Processa relatórios do B.I / WMS / J&T com alta performance e suporte a arquivos massivos."""
    ext = file_path.rsplit('.', 1)[-1].lower()
    sheet_dataframes = []

    if ext == 'csv':
        df = _read_dataframe_fast(file_path)
        if df is not None and len(df) > 0:
            sheet_dataframes.append(("CSV", df))
    else:
        try:
            xl = pd.ExcelFile(file_path, engine='calamine')
            for s_name in xl.sheet_names:
                try:
                    df = pd.read_excel(xl, sheet_name=s_name)
                    df = _clean_dataframe_headers(df)
                    if df is not None and len(df) > 0:
                        sheet_dataframes.append((s_name, df))
                except Exception as e:
                    print(f"Erro ao ler aba {s_name}: {e}")
        except Exception:
            try:
                xl = pd.ExcelFile(file_path)
                for s_name in xl.sheet_names:
                    try:
                        df = pd.read_excel(xl, sheet_name=s_name)
                        df = _clean_dataframe_headers(df)
                        if df is not None and len(df) > 0:
                            sheet_dataframes.append((s_name, df))
                    except Exception as e:
                        print(f"Erro ao ler aba {s_name}: {e}")
            except Exception:
                df = _read_dataframe_fast(file_path, 0)
                if df is not None and len(df) > 0:
                    sheet_dataframes.append(("Sheet1", df))

    if not sheet_dataframes:
        print(f"Não foi possível extrair dados de {file_path}")
        return None

    operadores_map = {}
    hora_global = {str(h).zfill(2): 0 for h in range(24)}
    hora_coleta = {str(h).zfill(2): 0 for h in range(24)}
    hora_lote = {str(h).zfill(2): 0 for h in range(24)}
    hora_exp = {str(h).zfill(2): 0 for h in range(24)}
    ref_date = datetime.now().strftime("%d/%m/%Y")
    
    fname_sector = _detect_sector_from_name(os.path.basename(file_path))
    fallback_sector = sector_hint or fname_sector or None

    for s_name, df in sheet_dataframes:
        sheet_sector = _detect_sector_from_name(str(s_name)) if isinstance(s_name, str) else None
        current_fallback_sector = sheet_sector or fallback_sector or 'Coleta de Chegadas'

        col_op = None
        col_time = None
        col_tipo = None
        col_qtd = None

        for col in df.columns:
            c_clean = str(col).strip().lower()
            if any(k in c_clean for k in ['digitalizador', 'operador', 'colaborador', 'usuario', 'usuário', 'user', 'login', 'nome', 'funcionario', 'funcionário', 'responsavel', 'responsável', 'pessoa']):
                if not any(x in c_clean for x in ['no.', 'código', 'codigo', 'id_', 'id ']) and not col_op:
                    col_op = col
            elif any(k in c_clean for k in ['tempo de digitaliza', 'tempo de bipagem', 'tempo', 'horário', 'horario', 'hora', 'data/hora', 'data hora', 'data e hora', 'timestamp', 'scan time', 'criado']):
                if not col_time:
                    col_time = col
            elif any(k in c_clean for k in ['tipo de bipagem', 'tipo de digitaliza', 'tipo de operação', 'tipo de operacao', 'tipo', 'setor', 'operacao', 'operação', 'status', 'etapa', 'categoria', 'atividade', 'processo']):
                if not col_tipo:
                    col_tipo = col
            elif any(k in c_clean for k in ['quantidade de volume', 'quantidade', 'qtd', 'volume', 'volumes', 'peças', 'pecas', 'total', 'bipes', 'bipagens', 'contagem']):
                if not col_qtd:
                    col_qtd = col

        if not col_op and len(df.columns) > 0:
            col_op = df.columns[0]

        # Filtra linhas válidas
        df = df[df[col_op].notna()].copy()
        df[col_op] = df[col_op].astype(str).str.strip()
        df = df[~df[col_op].str.lower().isin(['nan', 'none', 'null', '', 'total', 'total geral', 'digitalizador', 'operador'])]
        if len(df) == 0:
            continue

        # Quantidade vetorizada
        if col_qtd and col_qtd in df.columns:
            df['qtd_calc'] = pd.to_numeric(df[col_qtd].astype(str).str.replace(',', '.'), errors='coerce').fillna(1).astype(int)
            df['qtd_calc'] = df['qtd_calc'].apply(lambda x: x if x > 0 else 1)
        else:
            df['qtd_calc'] = 1

        # Setor vetorizado
        if col_tipo and col_tipo in df.columns:
            s_types = df[col_tipo].astype(str).str.lower()
            df['sector_calc'] = current_fallback_sector
            df.loc[s_types.str.contains('coleta|chegada|inbound|receb|descarga', regex=True), 'sector_calc'] = 'Coleta de Chegadas'
            df.loc[s_types.str.contains('lote|inserid|triagem|gaiola|sorting|bipagem lote', regex=True), 'sector_calc'] = 'Inserido em Lote'
            df.loc[s_types.str.contains('exped|despacho|saida|saída|outbound|carreg', regex=True), 'sector_calc'] = 'Expedição'
        else:
            df['sector_calc'] = current_fallback_sector

        # Extração de Hora vetorizada
        if col_time and col_time in df.columns:
            time_series = df[col_time].astype(str).str.strip()
            extracted_hours = time_series.str.extract(r'(\d{1,2}):\d{2}')[0]
            df['hour_calc'] = pd.to_numeric(extracted_hours, errors='coerce').fillna(12).astype(int).apply(lambda h: f"{min(max(h, 0), 23):02d}")
            
            # Detecta data do turno se houver
            try:
                date_m = time_series.str.extract(r'(\d{2})[/.-](\d{2})[/.-](\d{4})')
                if date_m[0].notna().any():
                    first_row = date_m.dropna().iloc[0]
                    ref_date = f"{first_row[0]}/{first_row[1]}/{first_row[2]}"
                else:
                    date_iso = time_series.str.extract(r'(\d{4})[/.-](\d{2})[/.-](\d{2})')
                    if date_iso[0].notna().any():
                        first_row = date_iso.dropna().iloc[0]
                        ref_date = f"{first_row[2]}/{first_row[1]}/{first_row[0]}"
            except Exception:
                pass
        else:
            df['hour_calc'] = "12"

        # Agrupamento vetorizado por Operador e Setor
        op_sec = df.groupby([col_op, 'sector_calc'])['qtd_calc'].sum().unstack(fill_value=0)
        # Agrupamento vetorizado por Operador e Hora
        op_hour = df.groupby([col_op, 'hour_calc'])['qtd_calc'].sum().unstack(fill_value=0)

        for op_name, sec_row in op_sec.iterrows():
            c = int(sec_row.get('Coleta de Chegadas', 0))
            l = int(sec_row.get('Inserido em Lote', 0))
            e = int(sec_row.get('Expedição', 0))
            tot = c + l + e
            if tot == 0:
                continue

            if op_name not in operadores_map:
                operadores_map[op_name] = {
                    "operador": op_name,
                    "setor": current_fallback_sector,
                    "bipes_coleta": 0,
                    "bipes_lote": 0,
                    "bipes_expedicao": 0,
                    "total_bipes": 0,
                    "horas": {str(h).zfill(2): 0 for h in range(24)},
                    "primeiro_bipe": "",
                    "ultimo_bipe": "",
                    "obs": ""
                }

            cur = operadores_map[op_name]
            cur["bipes_coleta"] += c
            cur["bipes_lote"] += l
            cur["bipes_expedicao"] += e
            cur["total_bipes"] += tot

            # Atualiza horas do operador
            if op_name in op_hour.index:
                h_row = op_hour.loc[op_name]
                for h_col, val in h_row.items():
                    hk = str(h_col).zfill(2)
                    cur["horas"][hk] = cur["horas"].get(hk, 0) + int(val)

        # Atualiza totais hora a hora por setor
        sec_hour = df.groupby(['sector_calc', 'hour_calc'])['qtd_calc'].sum().unstack(fill_value=0)
        for sec_name, h_row in sec_hour.iterrows():
            for h_col, val in h_row.items():
                hk = str(h_col).zfill(2)
                v = int(val)
                if sec_name == 'Coleta de Chegadas':
                    hora_coleta[hk] = hora_coleta.get(hk, 0) + v
                elif sec_name == 'Inserido em Lote':
                    hora_lote[hk] = hora_lote.get(hk, 0) + v
                elif sec_name == 'Expedição':
                    hora_exp[hk] = hora_exp.get(hk, 0) + v
                else:
                    hora_coleta[hk] = hora_coleta.get(hk, 0) + v
                hora_global[hk] = hora_global.get(hk, 0) + v

    if not operadores_map:
        print(f"Nenhum operador encontrado em {file_path}")
        return None

    operadores_list = list(operadores_map.values())
    for op in operadores_list:
        c = op["bipes_coleta"]
        l = op["bipes_lote"]
        e = op["bipes_expedicao"]
        if c >= l and c >= e:
            op["setor"] = "Coleta de Chegadas"
        elif l >= c and l >= e:
            op["setor"] = "Inserido em Lote"
        else:
            op["setor"] = "Expedição"

        active_hours = sum(1 for v in op["horas"].values() if v > 0) or 1
        op["pph"] = round(op["total_bipes"] / active_hours, 1)

    operadores_list.sort(key=lambda x: x["total_bipes"], reverse=True)

    pico_h = max(hora_global.items(), key=lambda x: x[1], default=("12", 0))
    tot_bipes = sum(o["total_bipes"] for o in operadores_list)
    tot_coleta = sum(o["bipes_coleta"] for o in operadores_list)
    tot_lote = sum(o["bipes_lote"] for o in operadores_list)
    tot_exp = sum(o["bipes_expedicao"] for o in operadores_list)

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_referencia": ref_date,
        "sector_identified": fallback_sector or 'Geral (B.I)',
        "kpis": {
            "previsto": 28511,
            "bipado": tot_coleta,
            "coletas": 10790,
            "diferenca": 28511 - tot_coleta - 10790,
            "total_bipes": tot_bipes,
            "total_coleta": tot_coleta,
            "total_lote": tot_lote,
            "total_expedicao": tot_exp,
            "total_operadores": len(operadores_list),
            "top_operador": operadores_list[0]["operador"] if operadores_list else "-",
            "top_bipes": operadores_list[0]["total_bipes"] if operadores_list else 0,
            "media_bipes_op": round(tot_bipes / len(operadores_list), 1) if operadores_list else 0.0,
            "pico_hora": f"{pico_h[0]}:00",
            "pico_volume": pico_h[1]
        },
        "hora_a_hora": {
            "total": hora_global,
            "coleta": hora_coleta,
            "lote": hora_lote,
            "expedicao": hora_exp
        },
        "operadores": operadores_list
    }

def _merge_ranking_datasets(existing_data, new_parsed_list):
    """Funde de forma inteligente planilhas dos 3 setores (Coleta, Lote, Expedição)."""
    if not existing_data:
        existing_data = {
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "data_referencia": datetime.now().strftime("%d/%m/%Y"),
            "kpis": {"previsto": 28511, "total_bipes": 0, "total_coleta": 0, "total_lote": 0, "total_expedicao": 0},
            "hora_a_hora": {
                "total": {str(h).zfill(2): 0 for h in range(24)},
                "coleta": {str(h).zfill(2): 0 for h in range(24)},
                "lote": {str(h).zfill(2): 0 for h in range(24)},
                "expedicao": {str(h).zfill(2): 0 for h in range(24)}
            },
            "operadores": []
        }

    # Mapas de operadores existentes
    op_dict = {o["operador"]: dict(o) for o in existing_data.get("operadores", [])}
    hora_coleta = dict(existing_data.get("hora_a_hora", {}).get("coleta", {str(h).zfill(2): 0 for h in range(24)}))
    hora_lote = dict(existing_data.get("hora_a_hora", {}).get("lote", {str(h).zfill(2): 0 for h in range(24)}))
    hora_exp = dict(existing_data.get("hora_a_hora", {}).get("expedicao", {str(h).zfill(2): 0 for h in range(24)}))
    ref_date = existing_data.get("data_referencia") or datetime.now().strftime("%d/%m/%Y")
    previsto = existing_data.get("kpis", {}).get("previsto") or 28511

    for parsed in new_parsed_list:
        if not parsed:
            continue
        if parsed.get("data_referencia"):
            ref_date = parsed.get("data_referencia")

        sec = parsed.get("sector_identified")
        p_horas = parsed.get("hora_a_hora", {})

        # Atualiza a curva horária do setor correspondente
        if sec == 'Coleta de Chegadas':
            hora_coleta = dict(p_horas.get("coleta") or hora_coleta)
        elif sec == 'Inserido em Lote':
            hora_lote = dict(p_horas.get("lote") or hora_lote)
        elif sec == 'Expedição':
            hora_exp = dict(p_horas.get("expedicao") or hora_exp)
        else:
            for h in range(24):
                hk = str(h).zfill(2)
                if p_horas.get("coleta", {}).get(hk, 0) > 0:
                    hora_coleta[hk] = p_horas["coleta"][hk]
                if p_horas.get("lote", {}).get(hk, 0) > 0:
                    hora_lote[hk] = p_horas["lote"][hk]
                if p_horas.get("expedicao", {}).get(hk, 0) > 0:
                    hora_exp[hk] = p_horas["expedicao"][hk]

        # Atualiza ou insere operadores
        for op in parsed.get("operadores", []):
            name = op["operador"]
            if name not in op_dict:
                op_dict[name] = {
                    "operador": name,
                    "setor": op.get("setor", sec or "Coleta de Chegadas"),
                    "bipes_coleta": op.get("bipes_coleta", 0),
                    "bipes_lote": op.get("bipes_lote", 0),
                    "bipes_expedicao": op.get("bipes_expedicao", 0),
                    "total_bipes": op.get("total_bipes", 0),
                    "horas": op.get("horas", {str(h).zfill(2): 0 for h in range(24)}),
                    "primeiro_bipe": op.get("primeiro_bipe", ""),
                    "ultimo_bipe": op.get("ultimo_bipe", ""),
                    "pph": op.get("pph", 0.0),
                    "obs": op.get("obs", "")
                }
            else:
                target = op_dict[name]
                if sec == 'Coleta de Chegadas':
                    target["bipes_coleta"] = op.get("bipes_coleta", 0)
                elif sec == 'Inserido em Lote':
                    target["bipes_lote"] = op.get("bipes_lote", 0)
                elif sec == 'Expedição':
                    target["bipes_expedicao"] = op.get("bipes_expedicao", 0)
                else:
                    target["bipes_coleta"] = max(target.get("bipes_coleta", 0), op.get("bipes_coleta", 0))
                    target["bipes_lote"] = max(target.get("bipes_lote", 0), op.get("bipes_lote", 0))
                    target["bipes_expedicao"] = max(target.get("bipes_expedicao", 0), op.get("bipes_expedicao", 0))

                target["total_bipes"] = target["bipes_coleta"] + target["bipes_lote"] + target["bipes_expedicao"]
                
                # Setor predominante
                c = target["bipes_coleta"]
                l = target["bipes_lote"]
                e = target["bipes_expedicao"]
                if c >= l and c >= e:
                    target["setor"] = "Coleta de Chegadas"
                elif l >= c and l >= e:
                    target["setor"] = "Inserido em Lote"
                else:
                    target["setor"] = "Expedição"

                # Horas
                op_horas = op.get("horas", {})
                for h in range(24):
                    hk = str(h).zfill(2)
                    if op_horas.get(hk, 0) > 0:
                        target["horas"][hk] = max(target["horas"].get(hk, 0), op_horas[hk])

                if op.get("primeiro_bipe"):
                    if not target["primeiro_bipe"] or op["primeiro_bipe"] < target["primeiro_bipe"]:
                        target["primeiro_bipe"] = op["primeiro_bipe"]
                if op.get("ultimo_bipe"):
                    if not target["ultimo_bipe"] or op["ultimo_bipe"] > target["ultimo_bipe"]:
                        target["ultimo_bipe"] = op["ultimo_bipe"]

                act_h = sum(1 for v in target["horas"].values() if v > 0) or 1
                target["pph"] = round(target["total_bipes"] / act_h, 1)

    # Recompõe totais hora a hora global
    hora_total = {str(h).zfill(2): (hora_coleta.get(str(h).zfill(2), 0) + hora_lote.get(str(h).zfill(2), 0) + hora_exp.get(str(h).zfill(2), 0)) for h in range(24)}
    
    operadores_final = list(op_dict.values())
    operadores_final.sort(key=lambda x: x["total_bipes"], reverse=True)

    tot_coleta = sum(o["bipes_coleta"] for o in operadores_final)
    tot_lote = sum(o["bipes_lote"] for o in operadores_final)
    tot_exp = sum(o["bipes_expedicao"] for o in operadores_final)
    tot_bipes = tot_coleta + tot_lote + tot_exp

    pico_h = max(hora_total.items(), key=lambda x: x[1], default=("12", 0))

    coletas = existing_data.get("kpis", {}).get("coletas") if (existing_data.get("kpis", {}).get("coletas") is not None) else 10790
    bipado = tot_coleta
    diferenca = previsto - bipado - coletas

    return {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_referencia": ref_date,
        "kpis": {
            "previsto": previsto,
            "bipado": bipado,
            "coletas": coletas,
            "diferenca": diferenca,
            "total_bipes": tot_bipes,
            "total_coleta": tot_coleta,
            "total_lote": tot_lote,
            "total_expedicao": tot_exp,
            "total_operadores": len(operadores_final),
            "top_operador": operadores_final[0]["operador"] if operadores_final else "-",
            "top_bipes": operadores_final[0]["total_bipes"] if operadores_final else 0,
            "media_bipes_op": round(tot_bipes / len(operadores_final), 1) if operadores_final else 0.0,
            "pico_hora": f"{pico_h[0]}:00",
            "pico_volume": pico_h[1]
        },
        "hora_a_hora": {
            "total": hora_total,
            "coleta": hora_coleta,
            "lote": hora_lote,
            "expedicao": hora_exp
        },
        "operadores": operadores_final
    }

def _load_ranking_data_internal(force_reset=False):
    """Carrega dados do arquivo JSON local ou cria/reseta um modelo padrão caso não existam ou estejam expirados."""
    horas_padrao = {str(h).zfill(2): 0 for h in range(24)}
    empty_template = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_referencia": datetime.now().strftime("%d/%m/%Y"),
        "kpis": {
            "previsto": 28511,
            "bipado": 0,
            "total_bipes": 0,
            "total_coleta": 0,
            "total_lote": 0,
            "total_expedicao": 0,
            "total_operadores": 0,
            "top_operador": "-",
            "top_bipes": 0,
            "media_bipes_op": 0.0,
            "pico_hora": "--:--",
            "pico_volume": 0
        },
        "hora_a_hora": {
            "total": horas_padrao,
            "coleta": horas_padrao,
            "lote": horas_padrao,
            "expedicao": horas_padrao
        },
        "operadores": []
    }

    if force_reset:
        return empty_template

    if os.path.exists(RANKING_JSON_FILE):
        try:
            with open(RANKING_JSON_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                up_at = data.get("updated_at")
                if up_at and db.is_ranking_data_expired(up_at):
                    print(f"[RANKING] Dados do turno anterior expiraram ({up_at}). Resetando ranking_data.json para novo turno.")
                    with open(RANKING_JSON_FILE, "w", encoding="utf-8") as fw:
                        json.dump(empty_template, fw, ensure_ascii=False, indent=2)
                    return empty_template
                return data
        except Exception as e:
            print("Erro ao ler ranking_data.json:", e)

    return empty_template

@app.route('/api/ranking/data')
def get_ranking_data():
    vol_coletas = 10790
    vol_previsto = 27262
    try:
        vol_data = db.get_volumetria_data()
        if not vol_data or not vol_data.get("records"):
            vol_data = _load_volumetria_data_internal()
        if vol_data:
            vol_coletas = int(vol_data.get("coletas") if vol_data.get("coletas") is not None else (vol_data.get("kpis", {}).get("coletas") or 10790))
            v_kpis = vol_data.get("kpis", {})
            if v_kpis.get("previsto") is not None and int(v_kpis.get("previsto")) > 0:
                vol_previsto = int(v_kpis.get("previsto"))
            elif vol_data.get("records"):
                vol_previsto = sum(int(r.get("pedido_sistema") or 0) for r in vol_data.get("records", []))
    except Exception as e:
        print("Erro ao obter volumetria para ranking:", e)

    try:
        data = db.get_ranking_data(check_expiration=True)
        if data and len(data.get("operadores", [])) > 0:
            if "kpis" in data:
                data["kpis"]["coletas"] = vol_coletas
                data["kpis"]["previsto"] = vol_previsto
            return jsonify(data)
    except Exception as err:
        print("Erro ao carregar ranking do banco:", err)
    data = _load_ranking_data_internal()
    if data and "kpis" in data:
        data["kpis"]["coletas"] = vol_coletas
        data["kpis"]["previsto"] = vol_previsto
    return jsonify(data)

@app.route('/api/ranking/clear', methods=['POST'])
def clear_ranking():
    try:
        db.clear_ranking_data()
        empty_data = _load_ranking_data_internal(force_reset=True)
        with open(RANKING_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(empty_data, f, ensure_ascii=False, indent=2)
        return jsonify({
            "success": True,
            "data": empty_data,
            "message": "Dados do ranking limpos com sucesso. Pronto para iniciar novo turno (16h00 às 07h00)."
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/ranking/upload', methods=['POST'])
def upload_ranking_file():
    # Coleta arquivos enviados (suporta 'files', 'file' ou múltiplos inputs)
    uploaded_files = request.files.getlist('files')
    if not uploaded_files:
        if 'file' in request.files:
            uploaded_files = [request.files['file']]
            
    if not uploaded_files or len(uploaded_files) == 0:
        return jsonify({"success": False, "error": "Nenhum arquivo enviado."}), 400

    sector_param = request.form.get('sector')
    sector_hint = None
    if sector_param:
        if 'coleta' in sector_param.lower() or 'chegada' in sector_param.lower():
            sector_hint = 'Coleta de Chegadas'
        elif 'lote' in sector_param.lower() or 'inserid' in sector_param.lower() or 'triagem' in sector_param.lower():
            sector_hint = 'Inserido em Lote'
        elif 'exped' in sector_param.lower() or 'despacho' in sector_param.lower():
            sector_hint = 'Expedição'

    try:
        parsed_list = []
        for file in uploaded_files:
            if not file or file.filename == '':
                continue
            ext = file.filename.rsplit('.', 1)[-1].lower()
            if ext not in ['xlsx', 'xls', 'csv']:
                continue

            temp_path = os.path.join(os.getcwd(), f"temp_ranking_{len(parsed_list)}_{file.filename}")
            file.save(temp_path)

            parsed = _parse_ranking_file(temp_path, sector_hint=sector_hint)
            if parsed and len(parsed.get("operadores", [])) > 0:
                parsed_list.append(parsed)
                db.log_upload("Ranking & Produtividade", file.filename, len(parsed.get("operadores", [])))

            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

        if not parsed_list:
            return jsonify({"success": False, "error": "Não foi possível extrair dados válidos dos arquivos enviados (.xlsx, .xls ou .csv). Verifique se o arquivo contém as colunas da bipagem/digitalização."}), 200

        # Carrega base existente (se for do turno anterior expirado, já vem zerado e limpo)
        existing_data = db.get_ranking_data(check_expiration=True) or _load_ranking_data_internal()
        # Se os dados existentes eram de outro turno expirado, garante replace completo
        merged_data = _merge_ranking_datasets(existing_data, parsed_list)

        db.save_ranking_data(merged_data, replace_all=True)

        with open(RANKING_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(merged_data, f, ensure_ascii=False, indent=2)

        processed = db.get_ranking_data(check_expiration=False)
        return jsonify({
            "success": True,
            "data": processed,
            "message": f"Planilhas importadas com sucesso! {len(parsed_list)} arquivo(s) processado(s) para o turno atual."
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "error": f"Erro ao processar arquivo: {str(e)}"}), 200

@app.errorhandler(500)
def handle_500(e):
    return jsonify({"success": False, "error": f"Erro interno do servidor: {str(e)}"}), 200

@app.errorhandler(400)
def handle_400(e):
    return jsonify({"success": False, "error": f"Requisição inválida: {str(e)}"}), 200

@app.route('/api/ranking/save', methods=['POST'])
def save_ranking_data():
    try:
        payload = request.get_json(force=True)
        if not payload or "operadores" not in payload:
            return jsonify({"success": False, "error": "Dados inválidos."}), 400

        payload["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        db.save_ranking_data(payload)

        with open(RANKING_JSON_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        processed = db.get_ranking_data(check_expiration=False)
        return jsonify({"success": True, "data": processed})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# ROTAS DO MÓDULO CONTROLE DE PDAs
# ==============================================================================
@app.route('/pda')
def pda_redirect():
    return redirect('/pda/', code=302)

@app.route('/pda/')
def pda_index():
    pda_dir = os.path.join(app.root_path, 'controle-pda')
    return send_from_directory(pda_dir, 'index.html')

@app.route('/pda/<path:filename>')
def pda_static(filename):
    pda_dir = os.path.join(app.root_path, 'controle-pda')
    return send_from_directory(pda_dir, filename)

@app.route('/controle-pda/<path:filename>')
def controle_pda_files(filename):
    pda_dir = os.path.join(app.root_path, 'controle-pda')
    return send_from_directory(pda_dir, filename)

@app.route('/app.js')
@app.route('/static/app.js')
def root_app_js():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.js'),
        os.path.join(app.root_path, 'app.js'),
        os.path.join(app.root_path, 'static', 'app.js'),
        'app.js'
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, 'r', encoding='utf-8') as f:
                    content = f.read()
                resp = Response(content, mimetype='application/javascript')
                resp.headers['Content-Type'] = 'application/javascript; charset=utf-8'
                return resp
            except Exception:
                pass
    return send_from_directory(app.root_path, 'app.js', mimetype='application/javascript')

@app.route('/style.css')
@app.route('/styles.css')
@app.route('/static/style.css')
@app.route('/static/styles.css')
def root_style_css():
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), 'style.css'),
        os.path.join(app.root_path, 'style.css'),
        os.path.join(app.root_path, 'static', 'style.css'),
        'style.css'
    ]
    for c in candidates:
        if os.path.exists(c):
            try:
                with open(c, 'r', encoding='utf-8') as f:
                    content = f.read()
                resp = Response(content, mimetype='text/css')
                resp.headers['Content-Type'] = 'text/css; charset=utf-8'
                return resp
            except Exception:
                pass
    return send_from_directory(app.root_path, 'style.css', mimetype='text/css')

# ==============================================================================
# APIS DO CONTROLE DE PDAs E REPORT DE INÍCIO (PERSISTÊNCIA 100% NO BANCO)
# ==============================================================================

@app.route('/api/pda/data', methods=['GET', 'OPTIONS'])
def api_pda_get_data():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        data = db.get_pda_data()
        return jsonify({"success": True, "data": data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pda/save', methods=['POST', 'OPTIONS'])
@app.route('/api/pda/sync', methods=['POST', 'OPTIONS'])
def api_pda_save_data():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"success": False, "error": "Payload vazio"}), 400
        saved_data = db.save_pda_data(payload)
        return jsonify({"success": True, "data": saved_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pda/registro', methods=['POST', 'DELETE', 'OPTIONS'])
def api_pda_registro():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        if request.method == 'DELETE':
            reg_id = request.args.get('id') or (request.get_json(silent=True) or {}).get('id')
            if not reg_id:
                return jsonify({"success": False, "error": "ID é obrigatório"}), 400
            db.delete_pda_registro(str(reg_id).strip())
            return jsonify({"success": True, "message": f"Registro {reg_id} excluído com sucesso", "data": db.get_pda_data()})
        
        payload = request.get_json(force=True)
        if not payload:
            return jsonify({"success": False, "error": "Payload vazio"}), 400
        saved = db.save_pda_registro(payload)
        return jsonify({"success": True, "registro": saved, "data": db.get_pda_data()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pda/frota', methods=['POST', 'OPTIONS'])
def api_pda_frota():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        payload = request.get_json(force=True)
        codigo = payload.get("codigo")
        status = payload.get("status", "Disponível")
        obs = payload.get("obs", "OK")
        if not codigo:
            return jsonify({"success": False, "error": "Código do PDA obrigatório"}), 400
        db.save_pda_frota_item(codigo, status, obs)
        return jsonify({"success": True, "data": db.get_pda_data()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pda/report_inicio', methods=['GET', 'POST', 'OPTIONS'])
def api_pda_report_inicio():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        if request.method == 'POST':
            payload = request.get_json(force=True)
            saved = db.save_pda_report_inicio(payload)
            return jsonify({"success": True, "report": saved})
        else:
            rep = db.get_pda_report_inicio()
            return jsonify({"success": True, "report": rep})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route('/api/pda/reset', methods=['POST', 'OPTIONS'])
def api_pda_reset():
    if request.method == 'OPTIONS':
        return jsonify({"success": True}), 200
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tb_pda_registros;")
            cursor.execute("DELETE FROM tb_pda_frota;")
            cursor.execute("DELETE FROM tb_pda_autorizados;")
            conn.commit()
        db.seed_pda_initial_data()
        return jsonify({"success": True, "data": db.get_pda_data()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Bloco principal para execucao direta do script python
if __name__ == '__main__':
    # Garante a criacao da pasta de templates html se ela nao existir no diretorio
    os.makedirs('templates', exist_ok=True)
    
    # Inicia o servidor local do Flask na porta 5000 aceitando conexoes externas (0.0.0.0)
    app.run(debug=True, host='0.0.0.0', port=5000)

