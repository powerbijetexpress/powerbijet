# -*- coding: utf-8 -*-
"""
db.py - Gerenciador do Banco de Dados Relacional Híbrido (PostgreSQL na Nuvem / SQLite Local)
Oferece persistência estruturada permanente (Render, Supabase, Neon ou Local),
consultas SQL indexadas, versionamento de fechamentos e migração automática de planilhas.
"""

import os
import sqlite3
import json
import time
from datetime import datetime, timedelta, date
try:
    import openpyxl
except ImportError:
    openpyxl = None

DEFAULT_RENDER_PG_URL = "postgresql://dc_bauru_db_user:opbS3AWCwu8U6VYSwQueJ1qHudNZJ1nD@dpg-dap3co6k1f9s739amlk0-a/dc_bauru_db"

# Detecta se está em ambiente de nuvem (Render) ou se uma URL explícita foi definida
_IS_CLOUD_ENV = bool(os.environ.get("RENDER") or os.environ.get("RENDER_SERVICE_ID"))

DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or os.environ.get("RENDER_DATABASE_URL")
if not DATABASE_URL and _IS_CLOUD_ENV:
    DATABASE_URL = DEFAULT_RENDER_PG_URL

if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

IS_POSTGRES = bool(DATABASE_URL)
_last_pg_error_time = 0

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logistica_bi.db")

class UniversalCursor:
    def __init__(self, cursor, is_postgres=False):
        self._cur = cursor
        self.is_postgres = is_postgres

    def execute(self, sql, params=None):
        cleaned_sql = sql
        if self.is_postgres:
            # Compatibilidade de tipos SQLite -> PostgreSQL
            cleaned_sql = cleaned_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "SERIAL PRIMARY KEY")
            cleaned_sql = cleaned_sql.replace("INTEGER PRIMARY KEY AUTO_INCREMENT", "SERIAL PRIMARY KEY")
            # Substitui marcadores posicionais '?' por '%s' para o driver psycopg2
            cleaned_sql = cleaned_sql.replace("?", "%s")
            
        if params is not None:
            return self._cur.execute(cleaned_sql, params)
        else:
            return self._cur.execute(cleaned_sql)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def rowcount(self):
        return self._cur.rowcount

class UniversalConnection:
    def __init__(self, conn, is_postgres=False):
        self._conn = conn
        self.is_postgres = is_postgres

    def cursor(self):
        return UniversalCursor(self._conn.cursor(), self.is_postgres)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self._conn.rollback()
        else:
            self._conn.commit()
        self._conn.close()

def get_connection():
    """Retorna uma conexão Universal pronta para PostgreSQL na nuvem ou SQLite local."""
    global _last_pg_error_time
    import time
    if IS_POSTGRES and DATABASE_URL and (time.time() - _last_pg_error_time > 300):
        try:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor, connect_timeout=2)
            conn.autocommit = True
            return UniversalConnection(conn, is_postgres=True)
        except Exception:
            _last_pg_error_time = time.time()
            # Fallback silencioso para SQLite local quando rodando fora da nuvem Render
            pass
            
    conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return UniversalConnection(conn, is_postgres=False)

def init_db():
    """Cria a estrutura de tabelas e índices se ainda não existirem."""
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Tabela de Volumetria Diária - Viagens
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_volumetria_viagens (
                id_transporte TEXT PRIMARY KEY,
                data_ref TEXT NOT NULL,
                pdd_saida TEXT,
                status_viagem TEXT,
                pedido_sistema INTEGER DEFAULT 0,
                previsao_chegada TEXT DEFAULT '',
                chegada_real TEXT,
                inicio_coleta TEXT,
                fim_coleta TEXT,
                status TEXT DEFAULT 'FINALIZADO',
                obs TEXT DEFAULT '',
                bipado INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vol_data_ref ON tb_volumetria_viagens(data_ref);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vol_pdd ON tb_volumetria_viagens(pdd_saida);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vol_status_viagem ON tb_volumetria_viagens(status_viagem);")

        # Migração automática: Adiciona coluna previsao_chegada se já existir a tabela sem ela
        try:
            cursor.execute("SELECT previsao_chegada FROM tb_volumetria_viagens LIMIT 1;")
        except Exception:
            try:
                cursor.execute("ALTER TABLE tb_volumetria_viagens ADD COLUMN previsao_chegada TEXT DEFAULT '';")
                conn.commit()
            except Exception:
                pass

        # 2. Tabela de Volumetria Diária - KPIs do Piso
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_volumetria_kpis (
                data_ref TEXT PRIMARY KEY,
                previsto INTEGER DEFAULT 0,
                bipados INTEGER DEFAULT 0,
                coletas INTEGER DEFAULT 0,
                total_no_piso INTEGER DEFAULT 0,
                diferenca INTEGER DEFAULT 0,
                eficiencia REAL DEFAULT 100.0,
                total_viagens INTEGER DEFAULT 0,
                viagens_finalizadas INTEGER DEFAULT 0,
                updated_at TEXT
            );
        """)

        # 3. Tabela de Carregamento de Veículos (Volumetria Diária)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_volumetria_carregamento (
                id TEXT PRIMARY KEY,
                veiculo TEXT NOT NULL,
                inicio TEXT DEFAULT '',
                termino TEXT DEFAULT '',
                tempo_total TEXT DEFAULT '',
                volume TEXT DEFAULT '',
                status TEXT DEFAULT 'PENDENTE',
                obs TEXT DEFAULT '',
                ordem INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_vol_carr_ordem ON tb_volumetria_carregamento(ordem);")

        # Migração: garante que a coluna 'volume' exista caso a tabela já tenha sido criada anteriormente
        cursor.execute("PRAGMA table_info(tb_volumetria_carregamento);")
        carr_cols = [c[1] for c in cursor.fetchall()]
        if 'volume' not in carr_cols:
            try:
                cursor.execute("ALTER TABLE tb_volumetria_carregamento ADD COLUMN volume TEXT DEFAULT '';")
            except Exception:
                pass

        # Remove tabelas legadas garantindo que apenas Volumetria Diária e Controle de PDAs fiquem no banco
        for tbl in ['tb_fechamento_turno', 'tb_recebimento', 'tb_sem_movimentacao',
                    'tb_expedido_nao_chegou', 'tb_historico_uploads',
                    'tb_ranking_operadores', 'tb_ranking_resumo']:
            cursor.execute(f"DROP TABLE IF EXISTS {tbl};")

        # 10. Tabela de Frota de PDAs (40 Coletores)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_pda_frota (
                codigo TEXT PRIMARY KEY,
                status TEXT DEFAULT 'Disponível',
                obs TEXT DEFAULT 'OK',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_frota_status ON tb_pda_frota(status);")

        # 11. Tabela de Responsáveis Autorizados por Turno
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_pda_autorizados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                turno TEXT NOT NULL,
                nome TEXT NOT NULL,
                UNIQUE(turno, nome)
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_aut_turno ON tb_pda_autorizados(turno);")

        # 12. Tabela de Registros de Retirada e Devolução de PDAs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_pda_registros (
                id TEXT PRIMARY KEY,
                pda TEXT NOT NULL,
                turno TEXT NOT NULL,
                responsavel TEXT NOT NULL,
                setor TEXT NOT NULL,
                data_retirada TEXT NOT NULL,
                data_devolucao TEXT,
                status TEXT NOT NULL,
                obs_retirada TEXT,
                obs_devolucao TEXT,
                estado_devolucao TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_reg_pda ON tb_pda_registros(pda);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_reg_status ON tb_pda_registros(status);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_reg_turno ON tb_pda_registros(turno);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_pda_reg_retirada ON tb_pda_registros(data_retirada);")

        # 13. Tabela de Report de Início da Operação
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_pda_report_inicio (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_ref TEXT NOT NULL,
                backlog_inicial TEXT DEFAULT '692',
                volume_previsto TEXT DEFAULT '65.129',
                inicio_operacao TEXT DEFAULT '15:11',
                clts_presentes_18h TEXT DEFAULT '32',
                absenteismo_18h TEXT DEFAULT '4',
                clts_presentes_23h TEXT DEFAULT '— 60',
                absenteismo_23h TEXT DEFAULT '— 4',
                diaristas_solicitados_15h TEXT DEFAULT '20',
                diaristas_presentes_15h TEXT DEFAULT '18',
                diaristas_solicitados_20h TEXT DEFAULT '—',
                diaristas_presentes_20h TEXT DEFAULT '—',
                phd_previsto TEXT DEFAULT '—',
                obs_falta_injustificada TEXT DEFAULT '—',
                obs_atestados TEXT DEFAULT '-',
                obs_pontos_atencao TEXT DEFAULT 'N/A',
                raw_text TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 14. Tabela de Report Grot
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tb_report_grot (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_ref TEXT NOT NULL,
                json_data TEXT NOT NULL,
                raw_text TEXT DEFAULT '',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

# ==========================================================
# OPERAÇÕES DE VOLUMETRIA DIÁRIA
# ==========================================================

def _normalize_date_iso(d_str):
    if not d_str:
        return datetime.now().strftime("%Y-%m-%d")
    s = str(d_str).strip()
    if "/" in s:
        parts = s.split("/")
        if len(parts) == 3 and len(parts[2]) == 4:
            return f"{parts[2]}-{parts[1].zfill(2)}-{parts[0].zfill(2)}"
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    return datetime.now().strftime("%Y-%m-%d")

def _format_date_br(d_str):
    if not d_str:
        return datetime.now().strftime("%d/%m/%Y")
    s = str(d_str).strip()
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        parts = s[:10].split("-")
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    if "/" in s:
        return s
    return datetime.now().strftime("%d/%m/%Y")

def _safe_int(val, default=0):
    if val is None:
        return default
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    s = str(val).strip()
    if not s or s in ['nan', 'none', 'null', '-', '--']:
        return default
    s_clean = s.replace('R$', '').replace(' ', '')
    if '.' in s_clean and ',' in s_clean:
        s_clean = s_clean.split(',')[0].replace('.', '')
    elif '.' in s_clean:
        parts = s_clean.split('.')
        if len(parts) == 2 and len(parts[1]) == 3:
            s_clean = parts[0] + parts[1]
        else:
            s_clean = s_clean.replace('.', '')
    elif ',' in s_clean:
        parts = s_clean.split(',')
        if len(parts) == 2 and len(parts[1]) == 3:
            s_clean = parts[0] + parts[1]
        else:
            s_clean = s_clean.split(',')[0]
    try:
        return int(float(s_clean))
    except Exception:
        import re
        digits = re.sub(r'\D', '', s)
        return int(digits) if digits else default

def save_volumetria_data(data_dict, replace_all=False):
    """Salva viagens e KPIs de Volumetria Diária no banco de dados."""
    if not data_dict:
        return False
        
    raw_date = data_dict.get("data_referencia") or datetime.now().strftime("%Y-%m-%d")
    data_ref = _normalize_date_iso(raw_date)
    updated_at = data_dict.get("updated_at") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    records = data_dict.get("records") or []
    kpis = data_dict.get("kpis") or {}
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Se replace_all for True (ao importar nova planilha), remove viagens e KPIs anteriores para garantir limpeza total
        if replace_all:
            cursor.execute("DELETE FROM tb_volumetria_viagens;")
            cursor.execute("DELETE FROM tb_volumetria_kpis;")
        elif records:
            # Sincroniza exclusões removendo do banco IDs que não estão mais na lista enviada
            valid_ids = [str(r.get("id_transporte") or "").strip() for r in records if str(r.get("id_transporte") or "").strip()]
            if valid_ids:
                placeholders = ','.join('?' for _ in valid_ids)
                cursor.execute(f"DELETE FROM tb_volumetria_viagens WHERE id_transporte NOT IN ({placeholders});", valid_ids)
        
        # Upsert Viagens
        for r in records:
            id_transporte = str(r.get("id_transporte") or "").strip()
            if not id_transporte:
                continue
                
            cursor.execute("""
                INSERT INTO tb_volumetria_viagens (
                    id_transporte, data_ref, pdd_saida, status_viagem,
                    pedido_sistema, previsao_chegada, chegada_real, inicio_coleta, fim_coleta,
                    status, obs, bipado, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(id_transporte) DO UPDATE SET
                    data_ref = excluded.data_ref,
                    pdd_saida = excluded.pdd_saida,
                    status_viagem = excluded.status_viagem,
                    pedido_sistema = excluded.pedido_sistema,
                    previsao_chegada = excluded.previsao_chegada,
                    chegada_real = excluded.chegada_real,
                    inicio_coleta = excluded.inicio_coleta,
                    fim_coleta = excluded.fim_coleta,
                    status = excluded.status,
                    obs = excluded.obs,
                    bipado = excluded.bipado,
                    updated_at = CURRENT_TIMESTAMP;
            """, (
                id_transporte,
                data_ref,
                r.get("pdd_saida") or "",
                r.get("status_viagem") or "",
                _safe_int(r.get("pedido_sistema")),
                r.get("previsao_chegada") or "",
                r.get("chegada_real") or "",
                r.get("inicio_coleta") or "",
                r.get("fim_coleta") or "",
                r.get("status") if r.get("status") is not None else "",
                r.get("obs") or "",
                _safe_int(r.get("bipado"))
            ))
            
        # Upsert KPIs
        sum_prev = sum(_safe_int(r.get("pedido_sistema")) for r in records)
        previsto = _safe_int(kpis.get("previsto")) if (kpis.get("previsto") is not None and _safe_int(kpis.get("previsto")) > 0) else sum_prev
        bipados = sum(_safe_int(r.get("bipado")) for r in records)
        
        if data_dict.get("coletas") is not None:
            coletas = _safe_int(data_dict.get("coletas"))
        elif kpis.get("coletas") is not None:
            coletas = _safe_int(kpis.get("coletas"))
        else:
            coletas = 10790
            
        total_piso = bipados + coletas
        diferenca = bipados - previsto
        eficiencia = round((bipados / previsto * 100), 2) if previsto > 0 else 100.0
        total_viagens = len(records)
        viagens_finalizadas = sum(1 for r in records if "FINALIZADO" in str(r.get("status", "")).upper())
        
        cursor.execute("""
            INSERT INTO tb_volumetria_kpis (
                data_ref, previsto, bipados, coletas, total_no_piso, diferenca,
                eficiencia, total_viagens, viagens_finalizadas, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(data_ref) DO UPDATE SET
                previsto = excluded.previsto,
                bipados = excluded.bipados,
                coletas = excluded.coletas,
                total_no_piso = excluded.total_no_piso,
                diferenca = excluded.diferenca,
                eficiencia = excluded.eficiencia,
                total_viagens = excluded.total_viagens,
                viagens_finalizadas = excluded.viagens_finalizadas,
                updated_at = excluded.updated_at;
        """, (
            data_ref, previsto, bipados, coletas, total_piso, diferenca,
            eficiencia, total_viagens, viagens_finalizadas, updated_at
        ))
        
        # Salva dados de carregamento de veículos se fornecidos compartilhando o mesmo cursor/transação
        if "carregamento" in data_dict and data_dict["carregamento"] is not None:
            save_volumetria_carregamento(data_dict["carregamento"], cursor=cursor)

        conn.commit()
    return True

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

def get_volumetria_data(data_ref=None):
    """Obtém os dados consolidados de Volumetria Diária do banco.
    Retorna SEMPRE o estado atual persistido das viagens e KPIs, sem nunca expirar ou resetar por horário.
    """
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Busca todas as viagens ativas salvas
        cursor.execute("SELECT * FROM tb_volumetria_viagens ORDER BY id_transporte;")
        records_rows = cursor.fetchall()
        
        # 2. Busca os KPIs mais recentes salvos
        cursor.execute("SELECT * FROM tb_volumetria_kpis ORDER BY updated_at DESC LIMIT 1;")
        kpi_row = cursor.fetchone()
        
        if not records_rows and not kpi_row:
            return None
            
        data_ref_val = None
        if kpi_row and "data_ref" in kpi_row.keys():
            data_ref_val = kpi_row["data_ref"]
        elif records_rows and len(records_rows) > 0 and "data_ref" in records_rows[0].keys():
            data_ref_val = records_rows[0]["data_ref"]
            
        if not data_ref_val:
            data_ref_val = datetime.now().strftime("%Y-%m-%d")
            
        records = []
        status_viagem_dist = {}
        status_operacional_dist = {}
        
        for r in records_rows:
            rec = {
                "id_transporte": r["id_transporte"],
                "pdd_saida": r["pdd_saida"],
                "status_viagem": r["status_viagem"],
                "pedido_sistema": r["pedido_sistema"],
                "previsao_chegada": (r["previsao_chegada"] if "previsao_chegada" in r.keys() else "") or "",
                "chegada_real": r["chegada_real"] or "",
                "inicio_coleta": r["inicio_coleta"] or "",
                "fim_coleta": r["fim_coleta"] or "",
                "status": r["status"] or "",
                "obs": r["obs"] or "",
                "bipado": r["bipado"]
            }
            records.append(rec)
            
            # Agrupamento para gráficos
            sv = r["status_viagem"] or "Outro"
            if "conclu" in sv.lower():
                sv_key = "Concluído"
            elif "trânsito" in sv.lower() or "transito" in sv.lower():
                sv_key = "Em Trânsito"
            elif "programa" in sv.lower():
                sv_key = "Programado"
            else:
                sv_key = sv
            status_viagem_dist[sv_key] = status_viagem_dist.get(sv_key, 0) + 1
            
            st_op = (r["status"] or "EM BRANCO").strip().upper()
            status_operacional_dist[st_op] = status_operacional_dist.get(st_op, 0) + 1
            
        if kpi_row:
            kpis = {
                "previsto": kpi_row["previsto"],
                "bipados": kpi_row["bipados"],
                "coletas": kpi_row["coletas"],
                "total_no_piso": kpi_row["total_no_piso"],
                "diferenca": kpi_row["diferenca"],
                "eficiencia": kpi_row["eficiencia"],
                "total_viagens": kpi_row["total_viagens"],
                "viagens_finalizadas": kpi_row["viagens_finalizadas"]
            }
            updated_at = kpi_row["updated_at"]
        else:
            prev = sum(r["pedido_sistema"] for r in records)
            bip = sum(r["bipado"] for r in records)
            kpis = {
                "previsto": prev,
                "bipados": bip,
                "coletas": 10790,
                "total_no_piso": bip + 10790,
                "diferenca": bip - prev,
                "eficiencia": round((bip / prev * 100), 2) if prev > 0 else 100.0,
                "total_viagens": len(records),
                "viagens_finalizadas": sum(1 for r in records if "FINALIZADO" in str(r.get("status", "")).upper())
            }
            updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
        records = _sort_volumetria_records(records)

        # Busca registros de carregamento de veículos (com veículos padrão SN RAO, SP BRE, DC PPB-SP)
        try:
            carregamento_list = get_volumetria_carregamento()
        except Exception as e:
            carregamento_list = []

        return {
            "data_referencia": _format_date_br(data_ref_val),
            "updated_at": updated_at,
            "kpis": kpis,
            "coletas": _safe_int(kpis.get("coletas"), 10790),
            "records": records,
            "carregamento": carregamento_list,
            "status_viagem_dist": status_viagem_dist,
            "status_operacional_dist": status_operacional_dist
        }

def get_volumetria_carregamento():
    """Obtém a lista de veículos em monitoramento de carregamento."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tb_volumetria_carregamento ORDER BY ordem ASC, rowid ASC;")
        rows = cursor.fetchall()
        if not rows:
            # Insere os 3 veículos padrão solicitados pelo usuário se ainda não existirem
            default_vehicles = [
                {"id": "carr-1", "veiculo": "SN RAO", "ordem": 1},
                {"id": "carr-2", "veiculo": "SP BRE", "ordem": 2},
                {"id": "carr-3", "veiculo": "DC PPB-SP", "ordem": 3}
            ]
            for v in default_vehicles:
                cursor.execute("""
                    INSERT OR IGNORE INTO tb_volumetria_carregamento (id, veiculo, inicio, termino, tempo_total, status, obs, ordem)
                    VALUES (?, ?, '', '', '', 'PENDENTE', '', ?)
                """, (v["id"], v["veiculo"], v["ordem"]))
            conn.commit()
            cursor.execute("SELECT * FROM tb_volumetria_carregamento ORDER BY ordem ASC, rowid ASC;")
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

def save_volumetria_carregamento(records, cursor=None):
    """Salva a lista completa de veículos do painel de carregamento."""
    if records is None:
        return False
        
    def _do_save(cur):
        cur.execute("DELETE FROM tb_volumetria_carregamento;")
        for idx, r in enumerate(records):
            c_id = str(r.get("id") or f"carr_{idx+1}_{int(time.time()*1000)}").strip()
            veiculo = str(r.get("veiculo") or "").strip()
            inicio = str(r.get("inicio") or "").strip()
            termino = str(r.get("termino") or "").strip()
            tempo_total = str(r.get("tempo_total") or "").strip()
            volume = str(r.get("volume") or "").strip()
            status = str(r.get("status") or "PENDENTE").strip()
            obs = str(r.get("obs") or "").strip()
            ordem = int(r.get("ordem") if r.get("ordem") is not None else idx + 1)
            
            cur.execute("""
                INSERT INTO tb_volumetria_carregamento (
                    id, veiculo, inicio, termino, tempo_total, volume, status, obs, ordem, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP);
            """, (c_id, veiculo, inicio, termino, tempo_total, volume, status, obs, ordem))

    if cursor is not None:
        _do_save(cursor)
        return True

    with get_connection() as conn:
        cur = conn.cursor()
        _do_save(cur)
        conn.commit()
        return True

def delete_volumetria_carregamento_item(item_id):
    """Remove um veículo específico do painel de carregamento."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tb_volumetria_carregamento WHERE id = ?;", (item_id,))
        conn.commit()
        return cursor.rowcount > 0

def update_volumetria_obs(id_transporte, obs):
    """Atualiza a observação de uma viagem diretamente no banco de dados."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tb_volumetria_viagens
            SET obs = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id_transporte = ?;
        """, (obs, id_transporte))
        conn.commit()
        return cursor.rowcount > 0

def delete_volumetria_viagem(id_transporte):
    """Exclui uma viagem de volumetria pelo ID de Transporte."""
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tb_volumetria_viagens WHERE id_transporte = ?;", (id_transporte,))
        conn.commit()
        return cursor.rowcount > 0

# ==========================================================
# OPERAÇÕES DE RANKING E PRODUTIVIDADE HORA A HORA
# ==========================================================

def is_ranking_data_expired(updated_at_str, now_dt=None):
    """
    Verifica se os dados de ranking expiraram com base no turno operacional (16h00 às 07h00).
    - Dados gerados durante o turno (entre 16:00 de D e 06:59 de D+1) pertencem ao turno D e expiram em D+1 às 07:00:00.
    - Dados gerados entre 07:00 de D e 15:59 de D pertencem à preparação do turno D e expiram em D+1 às 07:00:00.
    - Se now_dt >= expire_dt, os dados são considerados expirados e devem ser apagados.
    """
    if not updated_at_str:
        return True
    if now_dt is None:
        now_dt = datetime.now()
        
    try:
        updated_at_clean = str(updated_at_str).strip()
        if len(updated_at_clean) == 10:
            up_dt = datetime.strptime(updated_at_clean, "%Y-%m-%d")
        else:
            up_dt = datetime.strptime(updated_at_clean[:19], "%Y-%m-%d %H:%M:%S")
    except Exception:
        return True

    if up_dt.hour < 7:
        # Gerado de madrugada antes das 07h (parte final do turno iniciado às 16h da véspera)
        expire_dt = datetime(up_dt.year, up_dt.month, up_dt.day, 7, 0, 0)
    else:
        # Gerado a partir das 07h ou 16h (pertence ao turno que encerra às 07h do dia seguinte)
        next_day = up_dt.date() + timedelta(days=1)
        expire_dt = datetime(next_day.year, next_day.month, next_day.day, 7, 0, 0)
        
    return now_dt >= expire_dt

RANKING_JSON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ranking_data.json")

def _get_empty_ranking_template():
    horas_padrao = {str(h).zfill(2): 0 for h in range(24)}
    return {
        "data_referencia": datetime.now().strftime("%d/%m/%Y"),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
            "total": horas_padrao.copy(),
            "coleta": horas_padrao.copy(),
            "lote": horas_padrao.copy(),
            "expedicao": horas_padrao.copy()
        },
        "operadores": []
    }

def clear_ranking_data():
    """Limpa todos os dados de ranking gravados no arquivo JSON (sem usar banco)."""
    empty = _get_empty_ranking_template()
    try:
        with open(RANKING_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(empty, f, ensure_ascii=False, indent=2)
    except Exception:
        pass
    return True

def save_ranking_data(data_dict, replace_all=False):
    """Salva os dados do Ranking exclusivamente no arquivo JSON (sem gravar no banco de dados)."""
    try:
        with open(RANKING_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_ranking_data(data_ref=None, check_expiration=True):
    """Retorna os dados consolidados de Ranking lendo exclusivamente do arquivo JSON."""
    empty_result = _get_empty_ranking_template()
    if not os.path.exists(RANKING_JSON_PATH):
        return empty_result
    try:
        with open(RANKING_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            up_at = data.get("updated_at")
            if check_expiration and up_at and is_ranking_data_expired(up_at):
                clear_ranking_data()
                return empty_result
            return data
    except Exception:
        return empty_result

# ==========================================================
# OPERAÇÕES DO CONTROLE DE PDAs E REPORT DE INÍCIO DA OPERAÇÃO
# ==========================================================

DEFAULT_PDA_AUTORIZADOS = {
    '08h': ['GIOVANNY', 'JOAO MENDES'],
    '14h': ['Vinicius Nascimento'],
    '15h': ['PABLO', 'CRISTIANE', 'ISABELLA', 'ANGELA', 'BRUNO', 'GABRIEL', 'JULIANA', 'VITORIA', 'LUAN'],
    '23h': ['Matheus Nascimento', 'Kaue pedrozo', 'Amanda', 'Gabriel oliveira', 'William', 'João Pedro']
}

DEFAULT_PDA_SETORES = [
    'Expedição',
    'Lacre',
    'Esteira',
    'Recebimento',
    'Avaria',
    'Erro de triagem',
    'Criação de lote',
    'DROP'
]

def format_pda_report_inicio_text(d):
    data_val = d.get("data_ref", "*06/10/2026*")
    if not str(data_val).startswith("*") and not str(data_val).endswith("*"):
        data_val = f"*{data_val}*"
        
    return f"""📊 REPORT DE INÍCIO DA OPERAÇÃO

📅 Data: {data_val}

📦 Backlog Inicial: {d.get('backlog_inicial', '692')}
📦 Volume previsto: {d.get('volume_previsto', '53.903')}
🕒 Início da operação: {d.get('inicio_operacao', '15:11')}
👥 CLTs presentes 18hrs: {d.get('clts_presentes_18h', '32')}
❌ Absenteísmo 18hrs: {d.get('absenteismo_18h', '4')}
👥 CLTs presentes 22hrs: {d.get('clts_presentes_22h', d.get('clts_presentes_23h', '—'))}
❌ Absenteísmo 22hrs: {d.get('absenteismo_22h', d.get('absenteismo_23h', '—'))}
👷 Diaristas solicitados (15:00): {d.get('diaristas_solicitados_15h', '20')}
✅ Diaristas presentes (15:00): {d.get('diaristas_presentes_15h', '18')}
👷 Diaristas solicitados (20:00): {d.get('diaristas_solicitados_20h', '10')}
✅ Diaristas presentes (20:00): {d.get('diaristas_presentes_20h', '—')}
📈 PHD previsto: {d.get('phd_previsto', '—')}


📝 Observações:

- Falta injustificada: {d.get('obs_falta_injustificada', '4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA')}

- Atestados: {d.get('obs_atestados', 'N/A')}

- Pontos de atenção: {d.get('obs_pontos_atencao', 'N/A')}"""

def get_default_pda_report_inicio():
    d = {
        "data_ref": "*06/10/2026*",
        "backlog_inicial": "692",
        "volume_previsto": "53.903",
        "inicio_operacao": "15:11",
        "clts_presentes_18h": "32",
        "absenteismo_18h": "4",
        "clts_presentes_22h": "—",
        "absenteismo_22h": "—",
        "clts_presentes_23h": "—",
        "absenteismo_23h": "—",
        "diaristas_solicitados_15h": "20",
        "diaristas_presentes_15h": "18",
        "diaristas_solicitados_20h": "10",
        "diaristas_presentes_20h": "—",
        "phd_previsto": "—",
        "obs_falta_injustificada": "4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA",
        "obs_atestados": "N/A",
        "obs_pontos_atencao": "N/A"
    }
    d["raw_text"] = format_pda_report_inicio_text(d)
    return d

def normalize_pda_codigo(cod):
    """Padroniza o código do PDA estritamente no formato PDA-XX (PDA-00 a PDA-50)."""
    if not cod:
        return ""
    s = str(cod).strip().upper()
    digits = "".join(filter(str.isdigit, s))
    if digits != "":
        val = int(digits)
        return f"PDA-{val:02d}"
    return s

def normalize_pda_status(st):
    """Normaliza o status do PDA para garantir compatibilidade e evitar divergências de acentuação."""
    if not st:
        return "Disponível"
    s = str(st).strip().lower()
    if "devol" in s or "entreg" in s:
        return "Devolvido"
    if "uso" in s or "ocupad" in s or "retirad" in s:
        return "Em Uso"
    if "avar" in s or "manut" in s or "quebr" in s or "defe" in s:
        return "Avaria"
    if "disp" in s or "livr" in s or "ok" in s:
        return "Disponível"
    return "Disponível"

def _backup_pda_json(data):
    """Grava cópias de backup do estado em JSON dentro da pasta do projeto para máxima resiliência e segurança."""
    try:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        paths = [
            os.path.join(base_dir, "pda_data.json"),
            os.path.join(base_dir, "controle-pda", "pda_data.json")
        ]
        payload = {
            "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            **data
        }
        for p in paths:
            try:
                os.makedirs(os.path.dirname(p), exist_ok=True)
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(payload, f, ensure_ascii=False, indent=2)
            except Exception:
                pass
    except Exception:
        pass

def get_pda_report_inicio():
    """Retorna o último Report de Início da Operação gravado no banco."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tb_pda_report_inicio ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row:
            rep = {
                "id": row["id"],
                "data_ref": row["data_ref"],
                "backlog_inicial": row["backlog_inicial"],
                "volume_previsto": row["volume_previsto"],
                "inicio_operacao": row["inicio_operacao"],
                "clts_presentes_18h": row["clts_presentes_18h"],
                "absenteismo_18h": row["absenteismo_18h"],
                "clts_presentes_23h": row["clts_presentes_23h"],
                "absenteismo_23h": row["absenteismo_23h"],
                "diaristas_solicitados_15h": row["diaristas_solicitados_15h"],
                "diaristas_presentes_15h": row["diaristas_presentes_15h"],
                "diaristas_solicitados_20h": row["diaristas_solicitados_20h"],
                "diaristas_presentes_20h": row["diaristas_presentes_20h"],
                "phd_previsto": row["phd_previsto"],
                "obs_falta_injustificada": row["obs_falta_injustificada"],
                "obs_atestados": row["obs_atestados"],
                "obs_pontos_atencao": row["obs_pontos_atencao"],
                "raw_text": row["raw_text"] or format_pda_report_inicio_text(row)
            }
            return rep
        else:
            return get_default_pda_report_inicio()

def save_pda_report_inicio(report_dict):
    """Salva ou atualiza os dados do Report de Início da Operação no banco."""
    if not report_dict:
        report_dict = get_default_pda_report_inicio()
    init_db()
    data_ref = report_dict.get("data_ref", "*06/10/2026*")
    backlog_ini = str(report_dict.get("backlog_inicial", "692"))
    vol_prev = str(report_dict.get("volume_previsto", "53.903"))
    ini_op = str(report_dict.get("inicio_operacao", "15:11"))
    clt_18 = str(report_dict.get("clts_presentes_18h", "32"))
    abs_18 = str(report_dict.get("absenteismo_18h", "4"))
    clt_23 = str(report_dict.get("clts_presentes_22h", report_dict.get("clts_presentes_23h", "—")))
    abs_23 = str(report_dict.get("absenteismo_22h", report_dict.get("absenteismo_23h", "—")))
    dia_sol_15 = str(report_dict.get("diaristas_solicitados_15h", "20"))
    dia_pres_15 = str(report_dict.get("diaristas_presentes_15h", "18"))
    dia_sol_20 = str(report_dict.get("diaristas_solicitados_20h", "10"))
    dia_pres_20 = str(report_dict.get("diaristas_presentes_20h", "—"))
    phd = str(report_dict.get("phd_previsto", "—"))
    obs_falta = str(report_dict.get("obs_falta_injustificada", "4 — GIOVANA TEIXEIRA GRILLO DAMADA DAVI CARLOS DE PINHO BATISTA LISLAINE CHAVES DE CAMILO LUIS CARLOS PERES DA SILVA"))
    obs_atest = str(report_dict.get("obs_atestados", "N/A"))
    obs_aten = str(report_dict.get("obs_pontos_atencao", "N/A"))
    raw_text = report_dict.get("raw_text") or format_pda_report_inicio_text(report_dict)

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tb_pda_report_inicio ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row:
            rep_id = row["id"]
            cursor.execute("""
                UPDATE tb_pda_report_inicio SET
                    data_ref = ?, backlog_inicial = ?, volume_previsto = ?, inicio_operacao = ?,
                    clts_presentes_18h = ?, absenteismo_18h = ?, clts_presentes_23h = ?, absenteismo_23h = ?,
                    diaristas_solicitados_15h = ?, diaristas_presentes_15h = ?,
                    diaristas_solicitados_20h = ?, diaristas_presentes_20h = ?,
                    phd_previsto = ?, obs_falta_injustificada = ?, obs_atestados = ?, obs_pontos_atencao = ?,
                    raw_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (data_ref, backlog_ini, vol_prev, ini_op, clt_18, abs_18, clt_23, abs_23,
                  dia_sol_15, dia_pres_15, dia_sol_20, dia_pres_20, phd, obs_falta, obs_atest, obs_aten, raw_text, rep_id))
        else:
            cursor.execute("""
                INSERT INTO tb_pda_report_inicio (
                    data_ref, backlog_inicial, volume_previsto, inicio_operacao,
                    clts_presentes_18h, absenteismo_18h, clts_presentes_23h, absenteismo_23h,
                    diaristas_solicitados_15h, diaristas_presentes_15h,
                    diaristas_solicitados_20h, diaristas_presentes_20h,
                    phd_previsto, obs_falta_injustificada, obs_atestados, obs_pontos_atencao,
                    raw_text
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (data_ref, backlog_ini, vol_prev, ini_op, clt_18, abs_18, clt_23, abs_23,
                  dia_sol_15, dia_pres_15, dia_sol_20, dia_pres_20, phd, obs_falta, obs_atest, obs_aten, raw_text))
        conn.commit()

    return get_pda_report_inicio()

def get_pda_data():
    """Retorna todo o estado do Controle de PDAs persistido no banco, garantindo integridade dos 51 PDAs (PDA-00 a PDA-50)."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Frota
        cursor.execute("SELECT codigo, status, obs FROM tb_pda_frota;")
        frota_rows = cursor.fetchall()
        
        if len(frota_rows) == 0:
            seed_pda_initial_data(force=True)
            cursor.execute("SELECT codigo, status, obs FROM tb_pda_frota;")
            frota_rows = cursor.fetchall()

        frota_map = {}
        for r in frota_rows:
            cod = normalize_pda_codigo(r["codigo"])
            if cod:
                st = normalize_pda_status(r["status"])
                if cod not in frota_map or st in ("Em Uso", "Avaria"):
                    frota_map[cod] = {
                        "codigo": cod,
                        "status": st,
                        "obs": r["obs"] or "OK"
                    }

        # Garante exatamente de PDA-00 a PDA-50
        for i in range(0, 51):
            cod = f"PDA-{i:02d}"
            if cod not in frota_map:
                frota_map[cod] = {
                    "codigo": cod,
                    "status": "Disponível",
                    "obs": "OK"
                }

        frota = list(frota_map.values())
        frota.sort(key=lambda p: int("".join(filter(str.isdigit, p["codigo"])) or 0))
            
        # 2. Autorizados
        cursor.execute("SELECT turno, nome FROM tb_pda_autorizados ORDER BY turno, id;")
        aut_rows = cursor.fetchall()
        autorizados = {"08h": [], "14h": [], "15h": [], "23h": []}
        for r in aut_rows:
            t = r["turno"]
            if t not in autorizados:
                autorizados[t] = []
            if r["nome"] not in autorizados[t]:
                autorizados[t].append(r["nome"])
                
        # 3. Registros
        cursor.execute("""
            SELECT id, pda, turno, responsavel, setor, data_retirada, data_devolucao, status, obs_retirada, obs_devolucao, estado_devolucao
            FROM tb_pda_registros
            ORDER BY data_retirada DESC;
        """)
        reg_rows = cursor.fetchall()
        registros = []
        for r in reg_rows:
            registros.append({
                "id": r["id"],
                "pda": normalize_pda_codigo(r["pda"]),
                "turno": r["turno"],
                "responsavel": r["responsavel"],
                "setor": r["setor"],
                "dataRetirada": r["data_retirada"],
                "dataDevolucao": r["data_devolucao"],
                "status": normalize_pda_status(r["status"]),
                "obsRetirada": r["obs_retirada"],
                "obsDevolucao": r["obs_devolucao"],
                "estadoDevolucao": r["estado_devolucao"]
            })
            
        # 4. Report de Início
        cursor.execute("SELECT * FROM tb_pda_report_inicio ORDER BY id DESC LIMIT 1;")
        rep_row = cursor.fetchone()
        report_inicio = None
        if rep_row:
            report_inicio = {
                "id": rep_row["id"],
                "data_ref": rep_row["data_ref"],
                "backlog_inicial": rep_row["backlog_inicial"],
                "volume_previsto": rep_row["volume_previsto"],
                "inicio_operacao": rep_row["inicio_operacao"],
                "clts_presentes_18h": rep_row["clts_presentes_18h"],
                "absenteismo_18h": rep_row["absenteismo_18h"],
                "clts_presentes_23h": rep_row["clts_presentes_23h"],
                "absenteismo_23h": rep_row["absenteismo_23h"],
                "diaristas_solicitados_15h": rep_row["diaristas_solicitados_15h"],
                "diaristas_presentes_15h": rep_row["diaristas_presentes_15h"],
                "diaristas_solicitados_20h": rep_row["diaristas_solicitados_20h"],
                "diaristas_presentes_20h": rep_row["diaristas_presentes_20h"],
                "phd_previsto": rep_row["phd_previsto"],
                "obs_falta_injustificada": rep_row["obs_falta_injustificada"],
                "obs_atestados": rep_row["obs_atestados"],
                "obs_pontos_atencao": rep_row["obs_pontos_atencao"],
                "raw_text": rep_row["raw_text"] or format_pda_report_inicio_text(rep_row)
            }
        else:
            report_inicio = get_default_pda_report_inicio()

        return {
            "frota": frota,
            "autorizados": autorizados,
            "registros": registros,
            "report_inicio": report_inicio
        }

def save_pda_data(payload):
    """Salva estado completo ou sincronização no banco de dados com persistência 100% estruturada."""
    if not payload:
        return get_pda_data()
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # Frota
        if "frota" in payload and isinstance(payload["frota"], list):
            for item in payload["frota"]:
                cod = normalize_pda_codigo(item.get("codigo", ""))
                st = normalize_pda_status(item.get("status", "Disponível"))
                obs = item.get("obs", "OK")
                if cod:
                    cursor.execute("""
                        INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                        ON CONFLICT(codigo) DO UPDATE SET
                            status = excluded.status,
                            obs = excluded.obs,
                            updated_at = CURRENT_TIMESTAMP;
                    """, (cod, st, obs))
                    
        # Autorizados
        if "autorizados" in payload and isinstance(payload["autorizados"], dict):
            cursor.execute("DELETE FROM tb_pda_autorizados;")
            for turno, nomes in payload["autorizados"].items():
                if isinstance(nomes, list):
                    for nome in nomes:
                        n = str(nome).strip()
                        if n:
                            try:
                                cursor.execute("INSERT INTO tb_pda_autorizados (turno, nome) VALUES (?, ?);", (str(turno).strip(), n))
                            except Exception:
                                pass
                                
        # Registros
        if "registros" in payload and isinstance(payload["registros"], list):
            for reg in payload["registros"]:
                reg_id = str(reg.get("id", "")).strip()
                pda = normalize_pda_codigo(reg.get("pda", ""))
                if not reg_id or not pda:
                    continue
                turno = reg.get("turno", "15h")
                resp = reg.get("responsavel", "")
                setor = reg.get("setor", "Expedição")
                data_ret = reg.get("dataRetirada") or datetime.now().isoformat()
                data_dev = reg.get("dataDevolucao")
                st = normalize_pda_status(reg.get("status", "Em Uso"))
                obs_ret = reg.get("obsRetirada")
                obs_dev = reg.get("obsDevolucao")
                est_dev = reg.get("estadoDevolucao")
                
                cursor.execute("""
                    INSERT INTO tb_pda_registros (id, pda, turno, responsavel, setor, data_retirada, data_devolucao, status, obs_retirada, obs_devolucao, estado_devolucao, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(id) DO UPDATE SET
                        pda = excluded.pda,
                        turno = excluded.turno,
                        responsavel = excluded.responsavel,
                        setor = excluded.setor,
                        data_retirada = excluded.data_retirada,
                        data_devolucao = excluded.data_devolucao,
                        status = excluded.status,
                        obs_retirada = excluded.obs_retirada,
                        obs_devolucao = excluded.obs_devolucao,
                        estado_devolucao = excluded.estado_devolucao,
                        updated_at = CURRENT_TIMESTAMP;
                """, (reg_id, pda, turno, resp, setor, data_ret, data_dev, st, obs_ret, obs_dev, est_dev))

        conn.commit()

    # Report de Início (fora do bloco de conexão para evitar lock)
    if "report_inicio" in payload and isinstance(payload["report_inicio"], dict):
        save_pda_report_inicio(payload["report_inicio"])

    data = get_pda_data()
    _backup_pda_json(data)
    return data

def save_pda_registro(reg_dict):
    """Salva/atualiza uma retirada ou devolução e sincroniza a frota."""
    if not reg_dict:
        return None
    init_db()
    reg_id = str(reg_dict.get("id") or f"REG-{int(datetime.now().timestamp() * 1000)}").strip()
    pda = normalize_pda_codigo(reg_dict.get("pda", ""))
    turno = reg_dict.get("turno", "15h")
    resp = reg_dict.get("responsavel", "")
    setor = reg_dict.get("setor", "Expedição")
    data_ret = reg_dict.get("dataRetirada") or datetime.now().isoformat()
    data_dev = reg_dict.get("dataDevolucao")
    st = normalize_pda_status(reg_dict.get("status", "Em Uso"))
    obs_ret = reg_dict.get("obsRetirada")
    obs_dev = reg_dict.get("obsDevolucao")
    est_dev = reg_dict.get("estadoDevolucao")

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tb_pda_registros (id, pda, turno, responsavel, setor, data_retirada, data_devolucao, status, obs_retirada, obs_devolucao, estado_devolucao, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                pda = excluded.pda,
                turno = excluded.turno,
                responsavel = excluded.responsavel,
                setor = excluded.setor,
                data_retirada = excluded.data_retirada,
                data_devolucao = excluded.data_devolucao,
                status = excluded.status,
                obs_retirada = excluded.obs_retirada,
                obs_devolucao = excluded.obs_devolucao,
                estado_devolucao = excluded.estado_devolucao,
                updated_at = CURRENT_TIMESTAMP;
        """, (reg_id, pda, turno, resp, setor, data_ret, data_dev, st, obs_ret, obs_dev, est_dev))

        if st == 'Em Uso':
            cursor.execute("""
                INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                VALUES (?, 'Em Uso', 'Em Uso', CURRENT_TIMESTAMP)
                ON CONFLICT(codigo) DO UPDATE SET status = 'Em Uso', updated_at = CURRENT_TIMESTAMP;
            """, (pda,))
        elif st == 'Avaria':
            cursor.execute("""
                INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                VALUES (?, 'Avaria', ?, CURRENT_TIMESTAMP)
                ON CONFLICT(codigo) DO UPDATE SET status = 'Avaria', obs = excluded.obs, updated_at = CURRENT_TIMESTAMP;
            """, (pda, obs_dev or "Danificado na devolução"))
        elif st == 'Devolvido' or st == 'Disponível':
            cursor.execute("SELECT COUNT(*) as cnt FROM tb_pda_registros WHERE pda = ? AND status = 'Em Uso' AND id != ?;", (pda, reg_id))
            row = cursor.fetchone()
            if not row or row["cnt"] == 0:
                cursor.execute("""
                    INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                    VALUES (?, 'Disponível', 'OK', CURRENT_TIMESTAMP)
                    ON CONFLICT(codigo) DO UPDATE SET status = 'Disponível', obs = 'OK', updated_at = CURRENT_TIMESTAMP;
                """, (pda,))
        conn.commit()

    data = get_pda_data()
    _backup_pda_json(data)
    return reg_dict

def delete_pda_registro(reg_id):
    """Exclui um registro do histórico e atualiza a frota se necessário."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT pda, status FROM tb_pda_registros WHERE id = ?;", (reg_id,))
        row = cursor.fetchone()
        pda = normalize_pda_codigo(row["pda"]) if row else None
        
        cursor.execute("DELETE FROM tb_pda_registros WHERE id = ?;", (reg_id,))
        
        if pda:
            cursor.execute("SELECT COUNT(*) as cnt FROM tb_pda_registros WHERE pda = ? AND status = 'Em Uso';", (pda,))
            c_row = cursor.fetchone()
            if not c_row or c_row["cnt"] == 0:
                cursor.execute("UPDATE tb_pda_frota SET status = 'Disponível', obs = 'OK', updated_at = CURRENT_TIMESTAMP WHERE codigo = ? AND status = 'Em Uso';", (pda,))
        conn.commit()

    data = get_pda_data()
    _backup_pda_json(data)
    return True

def save_pda_frota_item(codigo, status="Disponível", obs="OK"):
    """Cadastra ou altera o status de um PDA específico."""
    init_db()
    cod = normalize_pda_codigo(codigo)
    st = normalize_pda_status(status)
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(codigo) DO UPDATE SET status = excluded.status, obs = excluded.obs, updated_at = CURRENT_TIMESTAMP;
        """, (cod, st, obs))
        conn.commit()
    data = get_pda_data()
    _backup_pda_json(data)
    return True

def delete_pda_frota_item(codigo):
    """Exclui um PDA específico da frota e cancela pendências ativas dele."""
    init_db()
    cod = normalize_pda_codigo(codigo)
    if not cod:
        return False
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tb_pda_frota WHERE codigo = ?;", (cod,))
        cursor.execute("DELETE FROM tb_pda_registros WHERE pda = ? AND (data_devolucao IS NULL OR status = 'Em Uso');", (cod,))
        conn.commit()
    data = get_pda_data()
    _backup_pda_json(data)
    return True

def seed_pda_initial_data(force=False):
    """Inicializa os PDAs apenas se a tabela tb_pda_frota estiver vazia (ou force=True)."""
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS total FROM tb_pda_frota;")
        total = cursor.fetchone()["total"]
        if total > 0 and not force:
            return
        
        # 1. Limpa registros duplicados / códigos com 3 dígitos (ex: PDA-037 -> PDA-37)
        cursor.execute("SELECT codigo, status, obs FROM tb_pda_frota;")
        current_rows = cursor.fetchall()
        for r in current_rows:
            old_cod = r["codigo"]
            new_cod = normalize_pda_codigo(old_cod)
            if new_cod and new_cod != old_cod:
                cursor.execute("DELETE FROM tb_pda_frota WHERE codigo = ?;", (old_cod,))
                cursor.execute("""
                    INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(codigo) DO UPDATE SET status = excluded.status, obs = excluded.obs, updated_at = CURRENT_TIMESTAMP;
                """, (new_cod, r["status"], r["obs"]))
                cursor.execute("UPDATE tb_pda_registros SET pda = ? WHERE pda = ?;", (new_cod, old_cod))

        # 2. Garante todos os 51 PDAs de PDA-00 a PDA-50
        for i in range(0, 51):
            cod = f"PDA-{i:02d}"
            cursor.execute("""
                INSERT INTO tb_pda_frota (codigo, status, obs, updated_at)
                VALUES (?, 'Disponível', 'OK', CURRENT_TIMESTAMP)
                ON CONFLICT(codigo) DO NOTHING;
            """, (cod,))
            
        # 3. Autorizados
        cursor.execute("SELECT COUNT(*) as count FROM tb_pda_autorizados;")
        aut_count = cursor.fetchone()["count"]
        if aut_count == 0:
            for t, nomes in DEFAULT_PDA_AUTORIZADOS.items():
                for n in nomes:
                    try:
                        cursor.execute("INSERT INTO tb_pda_autorizados (turno, nome) VALUES (?, ?);", (t, n))
                    except Exception:
                        pass
        conn.commit()
    
    rep = get_pda_report_inicio()
    if not rep:
        save_pda_report_inicio(get_default_pda_report_inicio())
    
    data = get_pda_data()
    _backup_pda_json(data)
    return True

# ==========================================================
# GESTÃO REPORT GROT (DC BAURU)
# ==========================================================

def format_grot_whatsapp_text(d):
    data_val = d.get('data_ref', '12/11/2026')
    jt = d.get('hc_jt', {})
    jt_tot = jt.get('Total', {})
    tsi = d.get('diaristas_tsi', {})
    smn = d.get('smn', {})
    smn_tot = smn.get('Total', {})
    mnc = d.get('mao_na_caixa', {})
    phd = d.get('phd', {})
    vol = d.get('volumetria', {})
    pont = d.get('pontualidade', {})
    sm = d.get('sem_mov', {})
    carr = d.get('carregamentos', [])

    text = f"""*📊 REPORT GROT - DC BAURU*
📅 Data: *{data_val}*

*1. PRESENTEÍSMO & EFETIVO*
👥 J&T Operadores Presentes: *{jt_tot.get('presentes', 0)} / {jt_tot.get('operador', 0)}* (Abs: {str(round(jt_tot.get('pct_abs', 0), 1)).replace('.', ',')}% - {jt_tot.get('faltas', 0)} Faltas | {jt_tot.get('atestados', 0)} Atestados)
   • T1: {jt.get('T1', {}).get('presentes', 0)}/{jt.get('T1', {}).get('operador', 0)} (Abs: {str(round(jt.get('T1', {}).get('pct_abs', 0), 1)).replace('.', ',')}%)
   • T2: {jt.get('T2', {}).get('presentes', 0)}/{jt.get('T2', {}).get('operador', 0)} (Abs: {str(round(jt.get('T2', {}).get('pct_abs', 0), 1)).replace('.', ',')}%)
   • T3: {jt.get('T3', {}).get('presentes', 0)}/{jt.get('T3', {}).get('operador', 0)} (Abs: {str(round(jt.get('T3', {}).get('pct_abs', 0), 1)).replace('.', ',')}%)
👷 Diaristas TSI: *{tsi.get('Total', 0)}* (T1: {tsi.get('T1', 0)} | T2: {tsi.get('T2', 0)} | T3: {tsi.get('T3', 0)})
🤝 Terceiros SMN: *{smn_tot.get('operador', 0)} Operadores* | Abs: {smn_tot.get('abs', 0)} ({str(round(smn_tot.get('pct_abs', 0), 1)).replace('.', ',')}%)
📦 *Total Mão na Caixa (Operação):* *{mnc.get('operacao', 0)}* | Geral (+Assist): *{mnc.get('geral', 0)}*

*2. PRODUTIVIDADE & VOLUME*
📥 Volume Total Geral: *{vol.get('volume_total_geral', 0):,}* pacotes
   • Coletas: {vol.get('coletas', 0):,}
   • Recebido: {vol.get('recebido', 0):,}
⚡ PHD Operação: *{str(phd.get('operacao', 0)).replace('.', ',')}* peças/HC
⚡ PHD Geral: *{str(phd.get('geral', 0)).replace('.', ',')}* peças/HC

*3. PONTUALIDADE (HUB -> PDD)*
⏱️ SP BRE: *{str(round(pont.get('bre', 0), 1)).replace('.', ',')}%*
⏱️ SN RAO: *{str(round(pont.get('rao', 0), 1)).replace('.', ',')}%*

*4. GESTÃO DE BACKLOG & SEM MOV*
🔄 Sem Movimentação: *{sm.get('hoje', 0)}* pacotes (Ontem: {sm.get('ontem', 0)} | Var: {sm.get('variacao', 0):+d})
⚠️ Expedido Não Chegou: *{sm.get('exp_nao_chegou_qtd', 0)}* pacotes ({str(round(sm.get('exp_nao_chegou_pct', 0), 1)).replace('.', ',')}% do Sem Mov)""".replace(',', '.')

    motivos = sm.get('aging_motivos', [])
    if motivos:
        text += "\n📋 Principais Motivos de Aging:"
        for m in motivos:
            if m.get('motivo') and m.get('qtd') and 'Total Geral' not in m.get('motivo'):
                text += f"\n   • {m['motivo']}: {m['qtd']}"

    if carr:
        text += "\n\n*5. CARREGAMENTOS*"
        for c in carr:
            ini = c.get('inicio') or '--:--'
            fim = c.get('fim') or '--:--'
            v_val = c.get('volume') or ''
            v_str = f" | Vol: {v_val}" if v_val else ""
            text += f"\n   • *{c.get('veiculo')}*: Início {ini} ➔ Término {fim}{v_str}"

    return text

def parse_report_grot_excel(filepath='Report Grot.xlsx'):
    if not os.path.isabs(filepath):
        filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filepath)
    if not os.path.exists(filepath):
        return None
        
    wb = openpyxl.load_workbook(filepath, data_only=True)
    ws = wb['Planilha1'] if 'Planilha1' in wb.sheetnames else wb.active
    
    def val(r, c):
        v = ws.cell(r, c).value
        return v if v is not None else ''

    # Data
    raw_date = val(3, 2)
    if isinstance(raw_date, (datetime, date)):
        date_str = raw_date.strftime('%d/%m/%Y')
    elif str(raw_date).strip():
        date_str = str(raw_date)[:10]
    else:
        date_str = datetime.now().strftime('%d/%m/%Y')

    # HC J&T
    jt = {}
    for r, turno in [(5, 'T1'), (6, 'T2'), (7, 'T3')]:
        jt[turno] = {
            'operador': int(val(r, 2) or 0),
            'assistente': int(val(r, 3) or 0),
            'lider': int(val(r, 4) or 0),
            'presentes': int(val(r, 6) or 0),
            'faltas': int(val(r, 7) or 0),
            'atestados': int(val(r, 8) or 0),
            'abs_turno': int(val(r, 9) or 0),
            'pct_abs': round(float(val(r, 10) or 0) * 100, 1)
        }
    jt['Total'] = {
        'operador': int(val(8, 2) or sum(jt[t]['operador'] for t in ['T1','T2','T3'])),
        'assistente': int(val(8, 3) or sum(jt[t]['assistente'] for t in ['T1','T2','T3'])),
        'lider': int(val(8, 4) or sum(jt[t]['lider'] for t in ['T1','T2','T3'])),
        'presentes': int(val(8, 6) or sum(jt[t]['presentes'] for t in ['T1','T2','T3'])),
        'faltas': int(val(8, 7) or sum(jt[t]['faltas'] for t in ['T1','T2','T3'])),
        'atestados': int(val(8, 8) or sum(jt[t]['atestados'] for t in ['T1','T2','T3'])),
        'abs_turno': int(val(8, 9) or sum(jt[t]['abs_turno'] for t in ['T1','T2','T3'])),
        'pct_abs': round(float(val(8, 10) or 0) * 100, 1)
    }

    # Diaristas TSI
    diaristas = {
        'T1': int(val(11, 2) or 0),
        'T2': int(val(12, 2) or 0),
        'T3': int(val(13, 2) or 0),
        'Total': int(val(14, 2) or 0)
    }

    # SMN
    smn = {}
    for r, turno in [(11, 'T2'), (12, 'T3')]:
        smn[turno] = {
            'operador': int(val(r, 5) or 0),
            'lideranca': int(val(r, 6) or 0),
            'abs': int(val(r, 7) or 0),
            'obs': str(val(r, 8) or '').strip(),
            'pct_abs': round(float(val(r, 10) or 0) * 100, 1)
        }
    smn['Total'] = {
        'operador': int(val(13, 5) or sum(smn[t]['operador'] for t in ['T2','T3'])),
        'lideranca': int(val(13, 6) or sum(smn[t]['lideranca'] for t in ['T2','T3'])),
        'abs': int(val(13, 7) or sum(smn[t]['abs'] for t in ['T2','T3'])),
        'pct_abs': round(float(val(13, 10) or 0) * 100, 1)
    }

    # Total - Mão na Caixa & PHD
    mao_na_caixa = {
        'operacao': int(val(17, 2) or 0),
        'geral': int(val(18, 2) or 0)
    }
    phd = {
        'operacao': round(float(val(17, 4) or 0), 1),
        'geral': round(float(val(18, 4) or 0), 1)
    }

    # Volumetria
    volumetria = {
        'coletas': int(val(5, 13) or 0),
        'recebido': int(val(6, 13) or 0),
        'ppb': int(val(7, 13) or 0),
        'fast_pass': int(val(8, 13) or 0),
        'ppb_processado': int(val(9, 13) or 0),
        'volume_dc_bau': int(val(4, 13) or 0),
        'volume_total_geral': int(val(10, 13) or 0)
    }

    # Pontualidade
    pontualidade = {
        'bre': round(float(val(15, 14) or 0) * 100, 1),
        'rao': round(float(val(16, 14) or 0) * 100, 1)
    }

    # Sem Movimentação
    sem_mov = {
        'ontem': int(val(18, 8) or 0),
        'hoje': int(val(19, 8) or 0),
        'variacao': int(val(20, 8) or 0),
        'exp_nao_chegou_qtd': int(val(21, 8) or 0),
        'exp_nao_chegou_pct': round(float(val(21, 9) or 0) * 100, 1),
        'aging_motivos': []
    }
    for r in range(26, 33):
        motivo = str(val(r, 7) or '').strip()
        qtd = val(r, 8)
        if qtd != '' and qtd is not None:
            if 'Total Geral' in motivo:
                continue
            if not motivo and r == 26:
                motivo = 'Sem Motivo / Outros'
            clean_motivo = motivo.split(' 外')[0].split(' 有')[0].split(' 错')[0].split(' 客')[0].split(' 无')[0].strip()
            clean_motivo = clean_motivo.replace('.', ' ')
            sem_mov['aging_motivos'].append({'motivo': clean_motivo, 'qtd': int(qtd)})

    # Carregamentos
    carregamentos = []
    for r in [20, 21, 22]:
        veic = str(val(r, 12) or '').strip()
        if veic:
            carregamentos.append({
                'veiculo': veic,
                'inicio': str(val(r, 13) or '').strip(),
                'fim': str(val(r, 14) or '').strip(),
                'volume': val(r, 15) or ''
            })

    result = {
        'data_ref': date_str,
        'hc_jt': jt,
        'diaristas_tsi': diaristas,
        'smn': smn,
        'mao_na_caixa': mao_na_caixa,
        'phd': phd,
        'volumetria': volumetria,
        'pontualidade': pontualidade,
        'sem_mov': sem_mov,
        'carregamentos': carregamentos
    }
    result['raw_text'] = format_grot_whatsapp_text(result)
    return result

def save_report_grot_data(data_dict, raw_text=""):
    init_db()
    if not data_dict:
        return False
    data_ref = str(data_dict.get("data_ref") or datetime.now().strftime("%d/%m/%Y")).strip()
    if not raw_text:
        raw_text = format_grot_whatsapp_text(data_dict)
    data_dict["raw_text"] = raw_text
    
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM tb_report_grot ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        json_str = json.dumps(data_dict, ensure_ascii=False)
        if row:
            cursor.execute("""
                UPDATE tb_report_grot
                SET data_ref = ?, json_data = ?, raw_text = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?;
            """, (data_ref, json_str, raw_text, row["id"]))
        else:
            cursor.execute("""
                INSERT INTO tb_report_grot (data_ref, json_data, raw_text)
                VALUES (?, ?, ?);
            """, (data_ref, json_str, raw_text))
        conn.commit()
    return True

def get_report_grot_data():
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tb_report_grot ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        if row and row["json_data"]:
            try:
                data = json.loads(row["json_data"])
                if row["raw_text"]:
                    data["raw_text"] = row["raw_text"]
                return data
            except Exception:
                pass
                
    # Se ainda não estiver salvo no banco, tenta parsear o arquivo Report Grot.xlsx na pasta
    excel_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Report Grot.xlsx")
    if os.path.exists(excel_path):
        parsed = parse_report_grot_excel(excel_path)
        if parsed:
            save_report_grot_data(parsed)
            return parsed
    return None

# ==========================================================
# OPERAÇÕES DE LOG E AUDITORIA DE UPLOADS
# ==========================================================

def log_upload(modulo, nome_arquivo, total_registros=0, status="SUCESSO"):
    """Mantido para compatibilidade com chamadas existentes sem gravar no banco."""
    pass

# ==========================================================
# MIGRAÇÃO INICIAL (SEED) A PARTIR DE ARQUIVOS EXISTENTES
# ==========================================================

def seed_initial_data():
    """Migra automaticamente os dados das planilhas locais para o SQLite se as tabelas estiverem vazias."""
    init_db()
    
    with get_connection() as conn:
        cursor = conn.cursor()
        
        # 1. Seed Volumetria
        cursor.execute("SELECT COUNT(*) as count FROM tb_volumetria_viagens;")
        if cursor.fetchone()["count"] == 0:
            json_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "volumetria_data.json")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    save_volumetria_data(data)
                    log_upload("Volumetria Diária", "volumetria_data.json", len(data.get("records", [])), "MIGRAÇÃO_INICIAL")
                    print("--> [DB] Volumetria Diária migrada com sucesso para o banco SQLite.")
                except Exception as e:
                    print(f"--> [DB] Erro ao migrar volumetria_data.json: {e}")

    # 2. Seed Controle de PDAs e Report de Início (fora do bloco de conexão)
    try:
        seed_pda_initial_data()
    except Exception as e:
        print(f"--> [DB] Erro no seed do Controle de PDAs: {e}")

# Executa inicialização automática ao carregar o módulo
try:
    init_db()
    seed_initial_data()
except Exception as e:
    print(f"[DB] Aviso na inicialização do banco: {e}")

