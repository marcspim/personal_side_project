import streamlit as st
from datetime import datetime, date, timedelta
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import sqlite3
from pathlib import Path
import hashlib
import time
import re
from datetime import datetime as dt, timedelta
import io

# ---------- Config
DB_PATH = Path("versao2_mim.db")
AREAS_DEFAULT = [
    "Coding",
    "Inglês",
    "Educação",
    "Saúde Mental",
    "Saúde Física",
    "Finanças",
    "Social",
    "Produtividade",
    "Criatividade",
    "Casa", 
    "Lazer",
]

BASE_XP = 100
XP_EXP = 1.45

st.set_page_config(page_title='Versão 2.0 de Mim', layout='wide')

# ------------------ Compatibilidade: rerun seguro ------------------
def safe_rerun():
    """
    Força a reexecução do script (rerun) usando o método mais robusto (query_params ou experimental_rerun).
    """
    try:
        if hasattr(st, "query_params"):
            st.query_params["_rerun_ts"] = str(int(time.time()))
            return
    except Exception:
        pass

    try:
        st.experimental_rerun()
        return
    except Exception:
        pass
        
    try:
        params = dict(st.query_params)
        params["_rerun_ts"] = str(int(time.time()))
        st.experimental_set_query_params(**params) if hasattr(st, "experimental_set_query_params") else st.experimental_set_query_params(**params)
        return
    except Exception:
        pass

    return

# ---------- Helpers: XP / Level conversions
def xp_for_level(level: int) -> int:
    if level <= 1:
        return 0
    return int(BASE_XP * (level ** XP_EXP))

def level_from_xp(xp: int) -> int:
    if xp <= 0:
        return 1
    lvl = 1
    while xp_for_level(lvl + 1) <= xp:
        lvl += 1
        if lvl > 1000:
            break
    return lvl

def xp_progress_in_level(xp: int):
    level = level_from_xp(xp)
    xp_curr_level = xp - xp_for_level(level)
    xp_next_level = xp_for_level(level + 1) - xp_for_level(level)
    pct = xp_curr_level / xp_next_level if xp_next_level > 0 else 0
    return level, xp_curr_level, xp_next_level, pct

# ---------- Database init
def init_db(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5) 
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY,
            date TEXT NOT NULL,
            area TEXT NOT NULL,
            xp INTEGER NOT NULL,
            note TEXT,
            type TEXT,
            user TEXT
        )
        """
    )
    conn.commit()
    conn.close()

def init_db_extra(path: Path = DB_PATH):
    """
    Inicializa/garante tabelas auxiliares (quests, perks, metas).
    Implementado com context manager para evitar 'closed database' e com tratamento de erro.
    """
    try:
        with sqlite3.connect(path, timeout=5) as conn:
            c = conn.cursor()

            # --- Quests
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS quests (
                    id INTEGER PRIMARY KEY,
                    title TEXT NOT NULL,
                    area TEXT NOT NULL,
                    xp_reward INTEGER NOT NULL,
                    cadence TEXT,
                    last_done TEXT,
                    streak INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    user TEXT
                )
                """
            )

            # --- Perks (schema com colunas novas já previstas)
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS perks (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    area TEXT,
                    unlock_level INTEGER NOT NULL,
                    effect TEXT,
                    duration_days INTEGER DEFAULT 0,
                    multiplier REAL DEFAULT 1.0,
                    start_date TEXT,
                    active INTEGER DEFAULT 0,
                    user TEXT
                )
                """
            )

            # --- Metas (opcional)
            c.execute(
                """
                CREATE TABLE IF NOT EXISTS metas (
                    id INTEGER PRIMARY KEY,
                    area TEXT NOT NULL,
                    weekly_target INTEGER NOT NULL,
                    note TEXT,
                    daily_suggestion INTEGER DEFAULT 0,
                    active INTEGER DEFAULT 1,
                    user TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT
                )
                """
            )

            # commit implícito ao sair do `with` (mas chamar explicitamente não faz mal)
            conn.commit()

    except Exception as e:
        # Log simples para debug — você pode trocar por st.error / logging
        print(f"ERRO init_db_extra(): {e}")
        # relança para que o erro apareça se você prefere falhar fast
        raise

def migrate_perks_table(path: Path = DB_PATH):
    """
    Garante que a tabela perks tenha as colunas necessárias (adiciona com ALTER TABLE se faltarem).
    Executar no startup para compatibilidade com DBs antigos.
    """
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    # Descobre colunas existentes
    c.execute("PRAGMA table_info(perks)")
    cols = [r[1] for r in c.fetchall()]
    # Map of desired columns with SQL to add
    adds = []
    if 'duration_days' not in cols:
        adds.append("ALTER TABLE perks ADD COLUMN duration_days INTEGER DEFAULT 0")
    if 'multiplier' not in cols:
        adds.append("ALTER TABLE perks ADD COLUMN multiplier REAL DEFAULT 1.0")
    if 'start_date' not in cols:
        adds.append("ALTER TABLE perks ADD COLUMN start_date TEXT")
    if 'active' not in cols:
        adds.append("ALTER TABLE perks ADD COLUMN active INTEGER DEFAULT 0")
    for a in adds:
        try:
            c.execute(a)
        except Exception:
            # ignore if already exists or incompatible (best-effort)
            pass
    conn.commit()
    conn.close()

# run migration at startup
migrate_perks_table()

def migrate_meta_table(path: Path = DB_PATH):
    """
    Garante que exista a tabela 'metas' e cria se não existir.
    Executar no startup para compatibilidade com DBs antigos.
    """
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    # cria tabela se não existir
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS metas (
            id INTEGER PRIMARY KEY,
            area TEXT NOT NULL,
            weekly_target INTEGER NOT NULL,
            note TEXT,
            daily_suggestion INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1,
            user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT
        )
        """
    )
    conn.commit()
    conn.close()

# execute migration no startup
migrate_meta_table()

def migrate_events_table(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    # Verifica se coluna meta_id já existe
    c.execute("PRAGMA table_info(events)")
    cols = [r[1] for r in c.fetchall()]
    if 'meta_id' not in cols:
        c.execute("ALTER TABLE events ADD COLUMN meta_id INTEGER")
    conn.commit()
    conn.close()

# chame no startup
migrate_events_table()

def init_users(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            display_name TEXT,
            password_hash TEXT NOT NULL,
            role TEXT,
            profession TEXT,
            bio TEXT,
            gender TEXT,
            birth_year INTEGER,
            height_cm REAL,
            weight_kg REAL,
            body_fat_pct REAL
        )
        """
    )
    conn.commit()
    conn.close()

# Tabela para configurações persistentes do usuário
def init_config_db(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS user_config (
            id INTEGER PRIMARY KEY,
            user TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT,
            UNIQUE(user, key)
        )
        """
    )
    conn.commit()
    conn.close()


# initialize DB and extras
init_db()
init_db_extra()
init_users()
init_config_db()
migrate_events_table()
migrate_meta_table()

# ---------- CONFIG HELPERS: Configuração persistente
def get_user_config(user: str, key: str, default=None) -> str:
    conn = sqlite3.connect(DB_PATH) 
    c = conn.cursor()
    c.execute("SELECT value FROM user_config WHERE user=? AND key=?", (user, key))
    row = c.fetchone()
    conn.close()
    if row:
        return row[0]
    return str(default) if default is not None else None

def set_user_config(user: str, key: str, value):
    value_str = str(value)
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute(
        "INSERT OR REPLACE INTO user_config (user, key, value) VALUES (?, ?, ?)",
        (user, key, value_str)
    )
    conn.commit()
    conn.close()

# ---------- Password hashing
def hash_pw(pw: str) -> str:
    return hashlib.sha256(pw.encode('utf-8')).hexdigest()

# ---------- Robust default users insertion
def create_default_users():
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("PRAGMA table_info(users)")
    cols_info = c.fetchall()
    cols = [r[1] for r in cols_info]

    defaults = [
        {
            "username": "marcel.pimenta",
            "display_name": "Marcel Pimenta",
            "password_hash": hash_pw("msp824655"),
            "role": "user",
            "profession": "Geólogo, Mestre em Ciência do Solo, Geocientista analista de integração de dados júnior, estudando Ciência de Dados",
            "bio": "Pretende até o fim do ano encerrar o curso de Ciência de Dados e até o fim do 1º semestre de 2026 ser promovido a nível pleno e/ou se tornar membro logístico na área de projetos.",
            "gender": "Homem",
            "birth_year": 1996,
            "height_cm": 171.0,
            "weight_kg": 86.0,
            "body_fat_pct": 19.0,
        },
        {
            "username": "larissa.souza",
            "display_name": "Larissa Souza",
            "password_hash": hash_pw("kmzc911011"),
            "role": "user",
            "profession": "Veterinária, Mestra em Ciências Veterinárias, pleiteando doutorado e/ou aprovação em concurso público",
            "bio": "Pretende ingressar no doutorado no 1º semestre de 2026 e/ou ser aprovada em concurso público.",
            "gender": "Mulher",
            "birth_year": 1996,
            "height_cm": 158.0,
            "weight_kg": 63.0,
            "body_fat_pct": 23.5,
        },
    ]

    for user_dict in defaults:
        insert_cols = [col for col in ["username","display_name","password_hash","role","profession","bio","gender","birth_year","height_cm","weight_kg","body_fat_pct"] if col in cols]
        placeholders = ",".join(["?"] * len(insert_cols))
        insert_cols_sql = ",".join(insert_cols)
        values = [user_dict.get(col, None) for col in insert_cols]
        try:
            c.execute(f"INSERT INTO users ({insert_cols_sql}) VALUES ({placeholders})", tuple(values))
        except sqlite3.IntegrityError:
            continue
        except Exception as e:
            print("Erro inserindo usuário default:", e)
            continue

    conn.commit()
    conn.close()

create_default_users()

# ---------- Basic CRUD helpers (user-aware)
def add_event(event_date: date, area: str, xp: int, note: str = "", type_: str = "manual", user: str = None, meta_id: int = None):
    eff_xp = apply_perks_to_xp(area, user, xp)
    note_final = note or ""
    if eff_xp != xp:
        note_final = f"{note_final} [Bônus aplicado: original {xp} -> {eff_xp} XP]" if note_final else f"[Bônus aplicado: original {xp} -> {eff_xp} XP]"
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (date, area, xp, note, type, user, meta_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (event_date.isoformat(), area, int(eff_xp), note_final, type_, user, int(meta_id) if meta_id is not None else None),
    )
    conn.commit()
    conn.close()

def update_event(event_id: int, event_date: date, area: str, xp: int, note: str, user: str):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute(
        "UPDATE events SET date=?, area=?, xp=?, note=? WHERE id=? AND user=?",
        (event_date.isoformat(), area, xp, note, event_id, user),
    )
    conn.commit()
    conn.close()

def load_events(user: str = None) -> pd.DataFrame:
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query("SELECT * FROM events WHERE user=? ORDER BY date ASC", conn, params=(user,), parse_dates=["date"])
    else:
        df = pd.read_sql_query("SELECT * FROM events ORDER BY date ASC", conn, parse_dates=["date"])
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["id", "date", "area", "xp", "note", "type", "user"])
    df['date'] = pd.to_datetime(df['date']).dt.date
    return df

# Função de atualização para Quests
def update_quest(quest_id: int, title: str, area: str, xp_reward: int, cadence: str, streak: int, user: str):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    # Assume que o usuário só pode atualizar quests que criou (user=?) ou quests genéricas (user IS NULL),
    # mas o teste de `user=?` é mais seguro para evitar que Marcel edite uma quest de Larissa
    # que porventura ela tenha criado sem o escopo de usuário (se houvesse esse bug).
    c.execute(
        "UPDATE quests SET title=?, area=?, xp_reward=?, cadence=?, streak=? WHERE id=? AND (user=? OR user IS NULL)",
        (title, area, xp_reward, cadence, streak, quest_id, user),
    )
    conn.commit()
    conn.close()

# ---------- Analytics & badges
def aggregate_xp_by_area(df: pd.DataFrame):
    if df.empty:
        return pd.Series(dtype=float).reindex(AREAS_DEFAULT).fillna(0)
    s = df.groupby('area')['xp'].sum().reindex(AREAS_DEFAULT).fillna(0)
    return s

def xp_over_time(df: pd.DataFrame, freq: str = 'W') -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=['date', 'xp'])
    tmp = df.copy()
    tmp['date'] = pd.to_datetime(tmp['date'])
    res = tmp.set_index('date')['xp'].resample(freq).sum().reset_index()
    res['date'] = res['date'].dt.date
    return res

def compute_badges(df: pd.DataFrame):
    badges = []
    if df.empty:
        return badges
    total_xp = df['xp'].sum()
    if total_xp > 5000:
        badges.append(('Veteran', '+5000 XP'))
    if total_xp > 1000:
        badges.append(('Committed', '>1000 XP'))
    recent = df[pd.to_datetime(df['date']) >= (pd.Timestamp(date.today()) - pd.Timedelta(days=7))]
    if not recent.empty and recent['xp'].sum() > 200:
        badges.append(('Weekly Hero', '>200 XP last 7d'))
    weekly = xp_over_time(df, freq='W')
    if weekly.shape[0] >= 8 and (weekly['xp'] > 0).tail(8).sum() >= 6:
        badges.append(('Consistent', 'Active 6/8 weeks'))
    return badges

# ---------- Quests & Perks (user-scoped)
def add_quest(title: str, area: str, xp_reward: int, cadence: str = 'daily', user: str = None):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("INSERT INTO quests (title, area, xp_reward, cadence, user) VALUES (?, ?, ?, ?, ?)", (title, area, xp_reward, cadence, user))
    conn.commit()
    conn.close()

def load_quests(user: str = None):
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query("SELECT * FROM quests WHERE active=1 AND (user=? OR user IS NULL)", conn, params=(user,), parse_dates=["last_done"])
    else:
        df = pd.read_sql_query("SELECT * FROM quests WHERE active=1", conn, parse_dates=["last_done"])
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["id","title","area","xp_reward","cadence","last_done","streak","active","user"])
    return df

def complete_quest(quest_id: int, user: str = None):
    conn = sqlite3.connect(DB_PATH, timeout=5) 
    c = conn.cursor()
    if user:
        c.execute("SELECT id, title, area, xp_reward, last_done, streak FROM quests WHERE id=? AND (user=? OR user IS NULL)", (quest_id, user))
    else:
        c.execute("SELECT id, title, area, xp_reward, last_done, streak FROM quests WHERE id=?", (quest_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return False
    qid, title, area, xp_reward, last_done, streak = row
    today_iso = date.today().isoformat()
    new_streak = 1
    if last_done:
        try:
            last = datetime.fromisoformat(last_done).date()
            if (date.today() - last).days == 1:
                new_streak = streak + 1
        except Exception:
            new_streak = 1
    
    c.execute("UPDATE quests SET last_done=?, streak=? WHERE id=?", (today_iso, new_streak, qid))
    conn.commit()
    conn.close()
    
    add_event(date.today(), area, xp_reward, note=f"Quest: {title}", type_='quest', user=user)
    return True

def add_perk(name: str, area: str = None, unlock_level: int = 0, effect: str = "", user: str = None,
             duration_days: int = 0, multiplier: float = 1.0, active: int = 0):
    """
    Insere uma perk. Garante que os campos duration_days e multiplier sejam salvos.
    Use apenas para inserir novas linhas.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    # garante colunas existem (migração defensiva)
    c.execute("PRAGMA table_info(perks)")
    cols = [r[1] for r in c.fetchall()]
    if 'multiplier' not in cols:
        c.execute("ALTER TABLE perks ADD COLUMN multiplier REAL DEFAULT 1.0")
    if 'duration_days' not in cols:
        c.execute("ALTER TABLE perks ADD COLUMN duration_days INTEGER DEFAULT 0")
    # Insere explicitamente todas as colunas
    c.execute(
        """INSERT INTO perks (name, area, unlock_level, effect, user, duration_days, multiplier, start_date, active)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, area, int(unlock_level), effect, user, int(duration_days), float(multiplier), None, int(active))
    )
    conn.commit()
    conn.close()

def seed_default_perks():
    """
    Insere/atualiza perks padrões declaradas no código. Faz upsert:
    - Se já existir perk com mesmo name+area+user -> atualiza multiplier/duration_days/effect (mantendo start_date/active).
    - Caso contrário -> insere nova.
    """
    defaults = [
        {'name': 'Focus Booster', 'area': 'Produtividade', 'unlock_level': 3, 'effect': '10% XP bonus para tarefas de produtividade', 'user': None, 'duration_days': 3, 'multiplier': 1.10},
        {'name': 'Deep Work', 'area': 'Coding', 'unlock_level': 5, 'effect': 'XP x1.2 em Coding por 7 dias', 'user': 'marcel.pimenta', 'duration_days': 7, 'multiplier': 1.20},
        {'name': 'Deep Work', 'area': 'Educação/Inglês/Produtividade', 'unlock_level': 5, 'effect': 'XP x1.2 em Educação, Inglês e Produtividade por 7 dias', 'user': 'larissa.souza', 'duration_days': 7, 'multiplier': 1.20},
    ]
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    for p in defaults:
        # procura por match exato name+area+user (user pode ser NULL)
        if p['user'] is None:
            c.execute("SELECT id FROM perks WHERE name=? AND area=? AND user IS NULL", (p['name'], p['area']))
        else:
            c.execute("SELECT id FROM perks WHERE name=? AND area=? AND user=?", (p['name'], p['area'], p['user']))
        res = c.fetchone()
        if res:
            pid = res[0]
            # atualiza multiplicador, duration e effect se diferente (não altera start_date/active)
            c.execute(
                "UPDATE perks SET unlock_level=?, effect=?, duration_days=?, multiplier=? WHERE id=?",
                (int(p['unlock_level']), p['effect'], int(p['duration_days']), float(p['multiplier']), int(pid))
            )
        else:
            # insere
            c.execute(
                "INSERT INTO perks (name, area, unlock_level, effect, user, duration_days, multiplier, start_date, active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (p['name'], p['area'], int(p['unlock_level']), p['effect'], p['user'], int(p['duration_days']), float(p['multiplier']), None, 0)
            )
    conn.commit()
    conn.close()

seed_default_perks()

def activate_perk(perk_id: int, user: str = None):
    """Ativa a perk (grava start_date = agora e active=1)."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    now_iso = datetime.now().isoformat()
    # garante que a linha corresponde ao usuário ou seja global
    c.execute("UPDATE perks SET start_date=?, active=1 WHERE id=? AND (user=? OR user IS NULL)", (now_iso, perk_id, user))
    conn.commit()
    conn.close()

def deactivate_perk(perk_id: int, user: str = None):
    """Desativa a perk (active=0)."""
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("UPDATE perks SET active=0, start_date=NULL WHERE id=? AND (user=? OR user IS NULL)", (perk_id, user))
    conn.commit()
    conn.close()

def get_active_perks(user: str = None):
    """
    Retorna DataFrame com perks cujo active=1 e que ainda estão dentro do período duration_days (se duration_days>0).
    Aceita perks globais (user IS NULL) e perks do usuário.
    """
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query("SELECT * FROM perks WHERE (user=? OR user IS NULL) AND active=1", conn, params=(user,), parse_dates=["start_date"])
    else:
        df = pd.read_sql_query("SELECT * FROM perks WHERE active=1", conn, parse_dates=["start_date"])
    conn.close()
    if df.empty:
        return pd.DataFrame()
    # Filtra por duração: se duration_days>0 e start_date definida, verifica se ainda está ativa
    def still_active(row):
        try:
            dur = int(row.get('duration_days') or 0)
            if dur <= 0:
                return True
            sd = row.get('start_date')
            if not sd:
                # Se active=1 mas sem start_date, considera ativa (mas warn)
                return True
            sd_date = pd.to_datetime(sd).date() if isinstance(sd, str) else pd.to_datetime(sd).date()
            # ainda ativa se dias passados < dur
            return (date.today() - sd_date).days < dur
        except Exception:
            return True
    df['is_active_now'] = df.apply(still_active, axis=1)
    df = df[df['is_active_now']]
    return df

def apply_perks_to_xp(area: str, user: str, xp: int) -> int:
    """
    Aplica perks ativas que influenciem a area.
    Estratégia:
      - considera perks ativas do user e globais (get_active_perks)
      - faz comparação por *contains* (case-insensitive) para cobrir 'Produtividade' e 'Produtividade/Outros'
      - aplica o maior multiplicador encontrado (evita stacking indesejado)
    """
    df = get_active_perks(user=user)
    if df.empty:
        return xp
    candidates = []
    a_norm = (area or "").strip().lower()
    for _, r in df.iterrows():
        r_area = str(r.get('area') or "").strip().lower()
        # se r_area vazio => aplica a todas as áreas
        if not r_area:
            candidates.append(r)
            continue
        # se r_area lista separada por '/', verificar contains em qualquer segmento
        parts = [p.strip() for p in r_area.split('/')]
        for p in parts:
            if p and (p == a_norm or p in a_norm or a_norm in p):
                candidates.append(r)
                break
    if not candidates:
        return xp
    # pega maior multiplicador
    best = max(candidates, key=lambda rr: float(rr.get('multiplier') or 1.0))
    mult = float(best.get('multiplier') or 1.0)
    new_xp = int(round(xp * mult))
    return new_xp

def perk_time_remaining(row) -> str:
    """
    Retorna string com tempo restante, em dias/hours, para um perk com start_date/duration_days.
    """
    try:
        sd = row.get('start_date')
        dur = int(row.get('duration_days', 0) or 0)
        if dur <= 0:
            return "Ilimitado"
        if not sd:
            return f"{dur} dias (não ativada)"
        sd_date = pd.to_datetime(sd).to_pydatetime()
        end_dt = sd_date + timedelta(days=dur)
        rem = end_dt - datetime.now()
        if rem.total_seconds() <= 0:
            return "Expirada"
        days = rem.days
        hours = rem.seconds // 3600
        if days > 0:
            return f"{days}d {hours}h"
        else:
            return f"{hours}h"
    except Exception:
        return "Desconhecido"

def load_perks(user: str = None):
    conn = sqlite3.connect(DB_PATH)
    if user:
        # Carrega perks genéricos (user IS NULL) e específicos do usuário
        df = pd.read_sql_query("SELECT * FROM perks WHERE user=? OR user IS NULL", conn, params=(user,))
    else:
        df = pd.read_sql_query("SELECT * FROM perks", conn)
    conn.close()
    if df.empty:
        return pd.DataFrame(columns=["id","name","area","unlock_level","effect","user"])
        
    # Remove perks genéricos se houver uma versão específica do usuário
    # Isso garante que a Larissa veja a versão dela de 'Deep Work', e não uma versão 'user IS NULL'
    specific_names = df[df['user'] == user]['name'].tolist()
    if specific_names:
        df = df[~((df['user'].isna()) & (df['name'].isin(specific_names)))]

    return df

conn_check = sqlite3.connect(DB_PATH)
df_perks_all = pd.read_sql_query("SELECT * FROM perks", conn_check)
conn_check.close()

# Verifica se os perks específicos já existem no DB
marcel_perk_exists = any(
    (p['name'] == 'Deep Work' and p['user'] == 'marcel.pimenta') for _, p in df_perks_all.iterrows()
)
larissa_perk_exists = any(
    (p['name'] == 'Deep Work' and p['user'] == 'larissa.souza') for _, p in df_perks_all.iterrows()
)

# Se qualquer um dos perks específicos estiver faltando, recria todos de forma limpa
if not marcel_perk_exists or not larissa_perk_exists:
    # 1. Limpa perks Deep Work (incluindo o genérico, se houve) e o Focus Booster genérico para evitar duplicatas
    conn_del = sqlite3.connect(DB_PATH, timeout=5)
    c_del = conn_del.cursor()
    c_del.execute("DELETE FROM perks WHERE name='Focus Booster'")
    c_del.execute("DELETE FROM perks WHERE name='Deep Work'")
    conn_del.commit()
    conn_del.close()

    # 2. Insere a versão Focus Booster genérica (útil para ambos e baseada em uma área comum)
    # Level 3 perks agora têm critério temporal de 3 dias por padrão com multiplier 1.10
    add_perk(
        'Focus Booster',
        'Produtividade',
        3,
        '10% XP bonus para tarefas de produtividade',
        user=None,
        duration_days=3,
        multiplier=1.10,
        active=0
    )

    # 3. Insere a versão Deep Work EXCLUSIVA para Marcel (Coding) - duration 7 dias
    add_perk(
        'Deep Work',
        'Coding',
        5,
        'XP x1.2 em Coding por 7 dias',
        user='marcel.pimenta',
        duration_days=7,
        multiplier=1.20,
        active=0
    )

    # 4. Insere a versão Deep Work EXCLUSIVA para Larissa (Educação, Inglês, Produtividade) - duration 7 dias
    add_perk(
        'Deep Work',
        'Educação/Inglês/Produtividade',
        5,
        'XP x1.2 em Educação, Inglês e Produtividade por 7 dias',
        user='larissa.souza',
        duration_days=7,
        multiplier=1.20,
        active=0
    )

def set_meta(area: str, weekly_target: int, note: str = "", daily_suggestion: int = 0, user: str = None, meta_id: int = None):
    """
    Cria ou atualiza uma meta. Ao criar, grava created_at.
    """
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    now_iso = datetime.now().isoformat()
    if meta_id:
        c.execute(
            "UPDATE metas SET area=?, weekly_target=?, note=?, daily_suggestion=?, updated_at=? , user=?, active=1 WHERE id=?",
            (area, int(weekly_target), note, int(daily_suggestion), now_iso, user, int(meta_id))
        )
    else:
        c.execute(
            "INSERT INTO metas (area, weekly_target, note, daily_suggestion, active, user, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (area, int(weekly_target), note, int(daily_suggestion), 1, user, now_iso, now_iso)
        )
    conn.commit()
    conn.close()

def get_meta(meta_id: int, user: str = None):
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query("SELECT * FROM metas WHERE id=? AND (user=? OR user IS NULL)", conn, params=(meta_id, user))
    else:
        df = pd.read_sql_query("SELECT * FROM metas WHERE id=?", conn, params=(meta_id,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def get_metas_for_user(user: str = None):
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query("SELECT * FROM metas WHERE (user=? OR user IS NULL) ORDER BY id DESC", conn, params=(user,))
    else:
        df = pd.read_sql_query("SELECT * FROM metas ORDER BY id DESC", conn)
    conn.close()
    return df

def week_start_end_for_date(d: date):
    """
    Retorna (start_date, end_date) da semana corrente em que d está, com start = Monday.
    end_date é inclusive (domingo).
    """
    start = d - timedelta(days=d.weekday())  # Monday
    end = start + timedelta(days=6)
    return start, end

def compute_week_progress_for_meta(meta_row: dict) -> dict:
    """
    Para metas específicas: soma apenas eventos com events.meta_id == meta.id,
    entre created_at e created_at+6 dias (ou até hoje).
    """
    meta_id = int(meta_row['id'])
    weekly_target = int(meta_row['weekly_target'])
    created_at_str = meta_row.get('created_at') or meta_row.get('created') or None
    today = date.today()

    if created_at_str:
        try:
            start = pd.to_datetime(created_at_str).date()
        except Exception:
            start = today
    else:
        start = today

    end = start + timedelta(days=6)
    effective_end = min(end, today)

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT SUM(xp) FROM events WHERE meta_id=? AND (user=? OR user IS NULL) AND date BETWEEN ? AND ?",
        (meta_id, meta_row.get('user'), start.isoformat(), effective_end.isoformat())
    )
    row = c.fetchone()
    accumulated = int(row[0] or 0)
    conn.close()

    percent = (accumulated / weekly_target) * 100 if weekly_target > 0 else 0.0
    return {
        'accumulated_xp': accumulated,
        'weekly_target': weekly_target,
        'percent': round(percent, 1),
        'start_date': start,
        'end_date': end
    }

def create_or_update_daily_quest_from_meta(meta_row: dict):
    """
    Se meta_row.daily_suggestion > 0, cria ou atualiza uma quest diária com title 'Meta: <area> - diária' e xp_reward = daily_suggestion.
    Retorna quest_id.
    """
    ds = int(meta_row.get('daily_suggestion') or 0)
    if ds <= 0:
        return None
    title = f"Meta diária: {meta_row['area']}"
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    # procura quest existente com mesmo título e user
    c.execute("SELECT id FROM quests WHERE title=? AND (user=? OR user IS NULL)", (title, meta_row.get('user')))
    res = c.fetchone()
    now_iso = datetime.now().isoformat()
    if res:
        qid = res[0]
        c.execute("UPDATE quests SET xp_reward=?, cadence='daily', last_done=NULL, active=1 WHERE id=?", (ds, qid))
    else:
        c.execute("INSERT INTO quests (title, area, xp_reward, cadence, last_done, streak, active, user) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                  (title, meta_row['area'], ds, 'daily', None, 0, 1, meta_row.get('user')))
        qid = c.lastrowid
    conn.commit()
    conn.close()
    return qid

# Callback para iniciar edição — executa antes da rerun final
def start_meta_edit(area, note, weekly, daily, meta_id):
    """
    Callback executado quando o usuário clica em 'Editar'.
    Define valores iniciais em st.session_state para que os widgets exibam os valores no próximo rerun.
    Observação: não chama st.experimental_rerun() para compatibilidade com versões de Streamlit.
    """
    st.session_state["meta_area_input"] = area
    st.session_state["meta_note_input"] = note or ""
    st.session_state["meta_weekly_input"] = int(weekly)
    st.session_state["meta_daily_input"] = int(daily or 0)
    st.session_state["editing_meta_id"] = int(meta_id)
    # NÃO chamar st.experimental_rerun() (nem st.experimental_rerun em try/except).
    # O callback on_click é executado no momento apropriado do ciclo de rerun
    # e, assim que o Streamlit rerun ocorrer, os widgets usarão os valores acima.
    return

def compute_area_xp_totals(user: str = None):
    """
    Retorna dict {area: total_xp} somando todos eventos dessa área.
    Por padrão inclui todos os eventos (incluindo os vinculados a metas).
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user:
        c.execute("SELECT area, SUM(xp) FROM events WHERE (user=? OR user IS NULL) GROUP BY area", (user,))
    else:
        c.execute("SELECT area, SUM(xp) FROM events GROUP BY area")
    rows = c.fetchall()
    conn.close()
    return {r[0]: int(r[1] or 0) for r in rows}

def level_from_xp(xp: int) -> int:
    """
    Função de exemplo: converte XP acumulado para level.
    Ajuste conforme sua tabela de XP->level real.
    Ex.: level n exige 100 * n XP acumulado cumulativo (exponha se tiver sua própria).
    """
    if xp < 100:
        return 1
    # exemplo simples: cada 200 xp = +1 level a partir de 1
    lvl = 1
    threshold = 100
    while xp >= threshold:
        xp -= threshold
        lvl += 1
        threshold = int(threshold * 1.5)  # opcional: incremento crescente
    return lvl

# ---------- Auth helpers
def get_user_by_username(username: str):
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query("SELECT * FROM users WHERE username=?", conn, params=(username,))
    conn.close()
    if df.empty:
        return None
    return df.iloc[0].to_dict()

def check_login(username: str, password: str) -> bool:
    user = get_user_by_username(username)
    if not user:
        return False
    return user['password_hash'] == hash_pw(password)

# ---------- Auth sidebar (robusta) ----------
def render_auth_sidebar():
    """
    Renderiza o painel de autenticação na sidebar.
    """
    if 'user' not in st.session_state:
        st.session_state['user'] = None

    cur_user = st.session_state.get("user", None)

    st.sidebar.header("Login")
    if cur_user is None:
        username_in = st.sidebar.text_input("Usuário", key="login_username")
        password_in = st.sidebar.text_input("Senha", type="password", key="login_password")
        
        if st.sidebar.button("Entrar", key="login_button_main"):
            if check_login(username_in, password_in):
                u = get_user_by_username(username_in)
                st.session_state["user"] = username_in
                st.session_state["display_name"] = u.get("display_name", username_in)
                
                st.session_state['auth_toggle_ts'] = str(int(time.time()))
                safe_rerun()
            else:
                st.sidebar.error("Usuário ou senha inválidos")
        
        st.sidebar.info("Faça login para acessar seu dashboard pessoal.")
        
    else:
        u = get_user_by_username(cur_user)
        disp = u.get("display_name") if u else cur_user
        st.sidebar.markdown(f"**Conectado:** {disp}")
        
        st.sidebar.write(f"**Profissão:** {u.get('profession','-')}")
        st.sidebar.write(f"**Objetivos:** {u.get('bio','-')}")
        st.sidebar.write(f"**Gênero:** {u.get('gender','-')}")
        st.sidebar.write(f"**Ano de nascimento:** {u.get('birth_year','-')}")
        
        if st.sidebar.button("Sair", key="logout_button_main"):
            for k in ["user", "display_name"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.session_state['auth_toggle_ts'] = str(int(time.time()))
            
            safe_rerun()

# Render auth sidebar
render_auth_sidebar()

# If not logged in, show minimal main page and stop
if st.session_state.get("user") is None:
    st.title("Versão 2.0 de Mim — Faça login para continuar")
    st.write("Por favor, use a barra lateral para entrar com seu usuário. Dê dois cliques em 'Entrar' ou 'Sair' para atualizar a seção de Login da sidebar.")
    st.stop()

# ---------- Sidebar main actions (user-scoped) ----------
def sidebar_main():
    st.sidebar.header('Config & Ações')
    cur_user = st.session_state.get('user')

    # Filtra a lista de áreas: remove "Coding" se não for Marcel
    available_areas = AREAS_DEFAULT.copy()
    if cur_user != "marcel.pimenta" and "Coding" in available_areas:
        available_areas.remove("Coding")

    areas_local = st.sidebar.multiselect(
        'Áreas (personalize)',
        options=available_areas,
        default=available_areas,
        key=f"areas_{cur_user}"
    )

    if st.sidebar.button('Limpar meus dados (CUIDADO)', key=f"btn_clear_{cur_user}"):
        conn = sqlite3.connect(DB_PATH, timeout=5)
        c = conn.cursor()
        c.execute('DELETE FROM events WHERE user=?', (cur_user,))
        c.execute('DELETE FROM quests WHERE user=?', (cur_user,))
        c.execute('DELETE FROM perks WHERE user=?', (cur_user,))
        c.execute('DELETE FROM user_config WHERE user=?', (cur_user,))
        conn.commit()
        conn.close()
        safe_rerun()

    st.sidebar.markdown('---')
    st.sidebar.subheader('Exportar / Importar (meus dados)')
    df_events_local = load_events(user=cur_user)
    st.sidebar.download_button('Exportar events.csv', df_events_local.to_csv(index=False).encode('utf-8'),
                               file_name=f'events_export_{cur_user}.csv', key=f"dl_events_{cur_user}")
    upload_local = st.sidebar.file_uploader('Importar CSV de events', type=['csv'], key=f"upload_events_{cur_user}")
    if upload_local is not None:
        df_in = pd.read_csv(upload_local)
        for _, row in df_in.iterrows():
            try:
                add_event(datetime.fromisoformat(str(row['date'])).date(),
                          row['area'], int(row['xp']), str(row.get('note', '')), str(row.get('type', 'import')), user=cur_user)
            except Exception as e:
                st.error(f'Erro importando linha: {e}')
        st.success('Import concluído')
        safe_rerun()
    return areas_local

areas = sidebar_main()

# ---------- Main dashboard (user is logged in) ----------
st.title("Versão 2.0 de Mim — HUD de Vida (gamificado)")
st.markdown("Acompanhe seu progresso como se fosse um personagem de jogo: níveis, XP, metas e badges.")

current_user = st.session_state.get('user')

# Define a lista de áreas para o seletor de registro de eventos
available_areas_for_main = AREAS_DEFAULT.copy()
if current_user != "marcel.pimenta" and "Coding" in available_areas_for_main:
    available_areas_for_main.remove("Coding")


# Register XP event form
st.header('Registrar atividades / ganhar XP')
col1, col2, col3 = st.columns([3, 2, 2])
with col1:
    with st.form(f'add_event_form_{current_user}'):
        ev_date = st.date_input('Data', value=date.today(), key=f'ev_date_{current_user}')
        ev_area = st.selectbox('Área', options=available_areas_for_main, key=f'ev_area_{current_user}')
        ev_xp = st.number_input('XP ganho', min_value=0, value=20, key=f'ev_xp_{current_user}')
        ev_note = st.text_area('Nota (opcional)', key=f'ev_note_{current_user}')

        # --- select de metas do usuário (opcional)
        metas_for_user = get_metas_for_user(user=current_user)
        meta_options = [None]
        meta_map = {None: None}
        if metas_for_user is not None and not metas_for_user.empty:
            for _, mm in metas_for_user.iterrows():
                mrow = mm.to_dict()
                label = f"{mrow['area']} — {mrow['weekly_target']} XP (id {mrow['id']})"
                meta_options.append(label)
                meta_map[label] = int(mrow['id'])

        selected_meta_label = st.selectbox("Atribuir esta atividade a uma meta (opcional)", options=meta_options, index=0, key=f'ev_meta_sel_{current_user}')
        assign_to_meta = False
        selected_meta_id = None
        if selected_meta_label and meta_map.get(selected_meta_label):
            # confirma com checkbox (redundante, mas evita cliques acidentais)
            assign_to_meta = st.checkbox("Confirmar: registrar esta atividade para a meta selecionada", key=f'confirm_meta_assign_{current_user}')
            if assign_to_meta:
                selected_meta_id = meta_map[selected_meta_label]

        submitted = st.form_submit_button('Registrar XP', key=f'ev_submit_{current_user}')
        if submitted:
            # se assign_to_meta e selected_meta_id foram escolhidos, grava com meta_id
            try:
                add_event(ev_date, ev_area, int(ev_xp), ev_note, user=current_user, meta_id=selected_meta_id)
                if selected_meta_id:
                    st.success(f'Registrado: {ev_xp} XP em {ev_area} vinculado à meta id {selected_meta_id}')
                else:
                    st.success(f'Registrado: {ev_xp} XP em {ev_area} (sem meta)')
                safe_rerun()
            except Exception as e:
                st.error(f"Erro ao registrar evento: {e}")

with col2:
    st.subheader('Snapshot Rápido')
    df = load_events(user=current_user)
    total_xp = int(df['xp'].sum()) if not df.empty else 0
    lvl, xp_curr, xp_next, pct = xp_progress_in_level(total_xp)

    # métrica de nível
    st.metric('Nível atual', f"{lvl}")

    # --- garante que o valor passado ao st.progress esteja entre 0 e 1 ---
    try:
        safe_pct = float(pct)
    except Exception:
        safe_pct = 0.0

    safe_pct = max(0.0, min(safe_pct, 1.0))  # clamp [0, 1]
    st.progress(safe_pct)
    # ---------------------------------------------------------------------------

    st.write(f"XP total: {total_xp} ( {xp_curr}/{xp_next} para nível {lvl+1} )")

with col3:
    st.subheader('Badges')
    badges = compute_badges(df)
    if not badges:
        st.write('Nenhum badge ainda. Registre atividades para ganhar badges!')
    else:
        for b, desc in badges:
            st.success(f"**{b}** — {desc}")

# KPIs & charts
st.header('Visão geral & evolução')
df = load_events(user=current_user)
col_a, col_b = st.columns([2, 3])
with col_a:
    st.subheader('Distribuição de XP por área')
    s = aggregate_xp_by_area(df)
    if s.empty or s.sum() == 0:
        st.info("Sem dados para exibir no gráfico de barras.")
    else:
        df_bar = pd.DataFrame({"area": list(s.index), "xp": list(s.values)})
        fig_bar = px.bar(df_bar, x="area", y="xp", labels={"area": "Área", "xp": "XP"}, title="XP por área")
        st.plotly_chart(fig_bar, use_container_width=True)

with col_b:
    st.subheader('Radar: equilíbrio entre áreas (XP relativo)')
    if df.empty:
        st.write('Sem dados — registre atividades para ver o radar')
    else:
        rvals = s.values
        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(r=list(rvals) + [rvals[0]], theta=list(s.index) + [s.index[0]], fill='toself', name='XP'))
        fig.update_layout(polar=dict(radialaxis=dict(visible=True)), showlegend=False, title_text='Radar de áreas')
        st.plotly_chart(fig, use_container_width=True)

st.markdown('---')
st.subheader('XP ao longo do tempo')
if df.empty:
    st.info('Sem dados históricos — registre atividades ou importe events.csv')
else:
    freq = st.selectbox('Resolução', options=['D', 'W', 'M'], index=1, key=f'freq_{current_user}')
    res = xp_over_time(df, freq=freq)
    fig_line = px.line(res, x='date', y='xp', title='XP por período')
    st.plotly_chart(fig_line, use_container_width=True)

# Goals (user-scoped)
st.header('Metas & tarefas')
goals = {}

# evita chaves com 'None' no nome caso current_user seja None
user_keyname = current_user or "guest"

with st.expander('Configurar metas (por área)'):
    for a in areas:
        # lê defaults do user_config (se existir), senão usa valores padrão
        default_w = int(get_user_config(current_user, f'goal_weekly_{a}', 100))
        default_m = int(get_user_config(current_user, f'goal_monthly_{a}', 400))
        default_note = get_user_config(current_user, f'goal_note_{a}', "")
        default_daily = int(get_user_config(current_user, f'goal_daily_{a}', 0) or 0)

        # keys para sessão — usa user_keyname (non-None)
        w_key = f'goal_w_{user_keyname}_{a}'
        m_key = f'goal_m_{user_keyname}_{a}'
        note_key = f'goal_note_{user_keyname}_{a}'
        daily_key = f'goal_daily_{user_keyname}_{a}'

        st.markdown(f"### {a}")
        col1, col2 = st.columns([2,1])

        with col1:
            # number_input cria a chave em session_state quando o Streamlit estiver com ScriptRunContext
            w = st.number_input(
                'Meta semanal XP',
                min_value=0,
                value=default_w,
                key=w_key,
                on_change=(lambda area=a, key=w_key: set_user_config(current_user, f'goal_weekly_{area}', st.session_state[key]))
            )
            # descrição livre da meta (ex: "Estudar 7 dias na semana - 50xp diários")
            note = st.text_input(
                'Descrição detalhada da meta (opcional)',
                value=default_note,
                key=note_key,
                help="Ex: 'Estudar 7 dias na semana - 50xp diários'",
                on_change=(lambda area=a, key=note_key: set_user_config(current_user, f'goal_note_{area}', st.session_state[key]))
            )

        with col2:
            m = st.number_input(
                'Meta mensal XP',
                min_value=0,
                value=default_m,
                key=m_key,
                on_change=(lambda area=a, key=m_key: set_user_config(current_user, f'goal_monthly_{area}', st.session_state[key]))
            )
            daily = st.number_input(
                'Sugestão diária (XP) — opcional',
                min_value=0,
                value=default_daily,
                key=daily_key,
                on_change=(lambda area=a, key=daily_key: set_user_config(current_user, f'goal_daily_{area}', st.session_state[key]))
            )

        # Segurança ao ler st.session_state: use get() com fallback para evitar KeyError
        w_val = int(st.session_state.get(w_key, default_w))
        m_val = int(st.session_state.get(m_key, default_m))
        note_val = st.session_state.get(note_key, default_note) or ""
        daily_val = int(st.session_state.get(daily_key, default_daily) or 0)

        # guarda no dicionário local usado depois
        goals[a] = {'weekly': w_val, 'monthly': m_val, 'note': note_val, 'daily': daily_val}
        st.markdown('---')

# === Metas (UI) ===
st.header("Metas semanais")

# Carrega metas do usuário (se a função existir)
try:
    metas_df = get_metas_for_user(user=current_user)
except Exception:
    metas_df = pd.DataFrame()

with st.expander("Criar ou editar meta"):
    st.write("Defina uma meta semanal por área, descreva-a e (opcional) indique um objetivo diário.")
    col1, col2 = st.columns([2,1])
    with col1:
        meta_area = st.text_input("Área da meta (ex: Educação, Produtividade, Inglês)", key="meta_area_input")
        meta_note = st.text_area("Descrição / detalhamento (ex: Estudar 7 dias na semana - 50xp diários)", key="meta_note_input")
    with col2:
        meta_weekly = st.number_input("Meta semanal (XP total)", min_value=1, step=1, value=350, key="meta_weekly_input")
        meta_daily = st.number_input("Sugestão diária (XP) — opcional", min_value=0, step=1, value=50, key="meta_daily_input")
        if st.button("Salvar meta"):
            try:
                editing_id = st.session_state.get("editing_meta_id")
                if editing_id:
                    # Atualiza meta existente
                    set_meta(meta_area.strip(), int(meta_weekly), meta_note.strip(), int(meta_daily), user=current_user,
                             meta_id=int(editing_id))
                    # limpa flag de edição
                    del st.session_state["editing_meta_id"]
                    st.success("Meta atualizada.")
                else:
                    # Cria nova meta
                    set_meta(meta_area.strip(), int(meta_weekly), meta_note.strip(), int(meta_daily), user=current_user)
                    st.success("Meta criada.")
                # Mantém user_config sincronizado
                set_user_config(current_user, f'goal_weekly_{meta_area}', int(meta_weekly))
                set_user_config(current_user, f'goal_monthly_{meta_area}',
                                int(get_user_config(current_user, f'goal_monthly_{meta_area}', int(meta_weekly * 4))))
                set_user_config(current_user, f'goal_note_{meta_area}', meta_note.strip())
                set_user_config(current_user, f'goal_daily_{meta_area}', int(meta_daily))
                safe_rerun()
            except Exception as e:
                st.error(f"Erro ao salvar meta: {e}")

st.markdown("---")
st.subheader("Minhas metas")
if metas_df is None or metas_df.empty:
    st.info("Nenhuma meta cadastrada.")
else:
    for _, m in metas_df.iterrows():
        mdict = m.to_dict()
        st.markdown(f"**{mdict['area']}** — Meta semanal: **{mdict['weekly_target']} XP**")
        if mdict.get('note'):
            st.write(mdict['note'])
        # progresso
        prog = compute_week_progress_for_meta(mdict)
        # st.progress agora espera valor entre 0 e 1
        try:
            pct_meta = float(prog.get('percent', 0.0))
        except Exception:
            pct_meta = 0.0

        pct_meta_norm = max(0.0, min(pct_meta / 100.0, 1.0))
        st.progress(pct_meta_norm)
        st.write(f"Acumulado esta semana: **{prog['accumulated_xp']} XP** de {prog['weekly_target']} ({prog['percent']}%) — período {prog['start_date'].isoformat()} → {prog['end_date'].isoformat()}")
        # --- BOTÃO: registrar XP diretamente para esta meta (opcional)
        # Só aparece se meta tem sugestão diária ou se você quer registrar manualmente
        try:
            if int(mdict.get('daily_suggestion', 0)) > 0:
                if st.button(f"Registrar +{int(mdict['daily_suggestion'])} XP para meta '{mdict['area']}'", key=f"reg_meta_{mdict['id']}"):
                    add_event(date.today(), mdict['area'], int(mdict['daily_suggestion']),
                              note=f"Registro direto para meta {mdict['id']}", user=current_user, meta_id=int(mdict['id']))
                    st.success("Registrado para a meta.")
                    safe_rerun()
        except Exception:
            # fallback: se daily_suggestion não for int/estiver ausente, mostra um botão genérico
            if st.button(f"Registrar XP para meta '{mdict['area']}'", key=f"reg_meta_fallback_{mdict['id']}"):
                add_event(date.today(), mdict['area'], 0, note=f"Registro direto para meta {mdict['id']}", user=current_user, meta_id=int(mdict['id']))
                st.success("Registrado para a meta.")
                safe_rerun()
        # opção de transformar daily_suggestion em quest diária
        if int(mdict.get('daily_suggestion', 0)) > 0:
            if st.button(f"Criar/Atualizar quest diária ({mdict['daily_suggestion']} XP)", key=f"create_daily_{mdict['id']}"):
                qid = create_or_update_daily_quest_from_meta(mdict)
                if qid:
                    st.success(f"Quest diária criada/atualizada (id {qid}).")
                    safe_rerun()
                else:
                    st.error("Não foi possível criar/atualizar a quest.")
        # editar / excluir
        cols = st.columns([1, 1])  # Editar e Excluir
        with cols[0]:
            st.button(
                "Editar",
                key=f"edit_meta_{mdict['id']}",
                on_click=start_meta_edit,
                args=(
                    mdict['area'],
                    mdict.get('note') or "",
                    int(mdict['weekly_target']),
                    int(mdict.get('daily_suggestion') or 0),
                    int(mdict['id'])
                )
            )

        with cols[1]:
            if st.button("Excluir", key=f"del_meta_{mdict['id']}"):
                area_to_clear = mdict['area']
                meta_id_to_delete = int(mdict['id'])
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=5)
                    c = conn.cursor()
                    # 1) Deleta a meta da tabela metas
                    c.execute("DELETE FROM metas WHERE id=?", (meta_id_to_delete,))
                    conn.commit()

                    # 2) Remove quests diárias geradas pela meta (se houver)
                    try:
                        # procura quests cujo title comece com 'Meta diária: <area>'
                        pattern = f"Meta diária: {area_to_clear}%"
                        c.execute("DELETE FROM quests WHERE title LIKE ? AND (user=? OR user IS NULL)",
                                  (pattern, current_user))
                        conn.commit()
                    except Exception:
                        # se falhar aqui, não bloqueia; log no console
                        print(f"Aviso: falha ao tentar remover quests diárias para area={area_to_clear}")

                    conn.close()

                    # 3) Limpa user_config relacionado para evitar que a meta "continue aparecendo"
                    #    — remove descrição, sugestão diária e reseta metas semanais/mensais para defaults
                    try:
                        set_user_config(current_user, f'goal_note_{area_to_clear}', "")
                        set_user_config(current_user, f'goal_daily_{area_to_clear}', 0)
                        # opcional: resetar metas para valores padrão (ajuste se preferir outros defaults)
                        set_user_config(current_user, f'goal_weekly_{area_to_clear}', 100)
                        set_user_config(current_user, f'goal_monthly_{area_to_clear}', 400)
                    except Exception:
                        print(f"Aviso: falha ao limpar user_config para area={area_to_clear}")

                    st.success("Meta excluída com sucesso — entradas relacionadas também foram limpas.")
                    safe_rerun()
                except Exception as e:
                    st.error(f"Erro ao excluir meta: {e}")
                    try:
                        conn.close()
                    except Exception:
                        pass

st.subheader('Progresso nas metas')
if df.empty:
    st.write('Sem dados — registre atividades')
else:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = date(today.year, today.month, 1)
    df_pd = df.copy()
    df_pd['date'] = pd.to_datetime(df_pd['date']).dt.date
    week_df = df_pd[df_pd['date'] >= week_start]
    month_df = df_pd[df_pd['date'] >= month_start]

    for a in areas:
        w_xp = int(week_df[week_df['area'] == a]['xp'].sum())
        m_xp = int(month_df[month_df['area'] == a]['xp'].sum())

        # usa os valores atualizados em 'goals'
        weekly_target = int(goals.get(a, {}).get('weekly', int(get_user_config(current_user, f'goal_weekly_{a}', 100))))
        monthly_target = int(goals.get(a, {}).get('monthly', int(get_user_config(current_user, f'goal_monthly_{a}', 400))))
        note = goals.get(a, {}).get('note') or get_user_config(current_user, f'goal_note_{a}', "")
        daily_suggestion = int(goals.get(a, {}).get('daily', get_user_config(current_user, f'goal_daily_{a}', 0) or 0))

        st.markdown(f"### **{a}**")
        if note:
            st.write(f"*{note}*")
        st.write(f"Semana: **{w_xp}** / {weekly_target} XP  —  Mês: **{m_xp}** / {monthly_target} XP")
        # barra de progresso (protege divisão por zero)
        if weekly_target > 0:
            # calcula progresso seguro em [0.0, 1.0]
            wt = max(1, int(weekly_target))  # evita divisão por 0
            raw_val = float(w_xp) / float(wt)  # pode ser negativo se w_xp < 0
            if raw_val < 0:
                st.warning(f"XP semanal negativo: {w_xp} (meta {wt}).")
            progress_val = max(0.0, min(raw_val, 1.0))  # força intervalo [0.0, 1.0]
            st.progress(progress_val)
            pct = round((w_xp / weekly_target) * 100, 1)
            st.write(f"{pct}% da meta semanal")
        else:
            st.info("Meta semanal não definida")

        # Sugestão diária e botão para criar/atualizar quest diária
        if daily_suggestion and daily_suggestion > 0:
            cols = st.columns([2,1])
            with cols[0]:
                st.write(f"Sugestão diária: **{daily_suggestion} XP**")
            with cols[1]:
                if st.button(f"Criar/Atualizar quest diária ({daily_suggestion} XP) — {a}", key=f"create_daily_cfg_{a}"):
                    # monta meta_row compatível com create_or_update_daily_quest_from_meta
                    meta_row = {
                        'area': a,
                        'weekly_target': weekly_target,
                        'note': note,
                        'daily_suggestion': daily_suggestion,
                        'user': current_user
                    }
                    try:
                        qid = create_or_update_daily_quest_from_meta(meta_row)
                        if qid:
                            st.success(f"Quest diária criada/atualizada (id {qid}).")
                            safe_rerun()
                        else:
                            st.error("Não foi possível criar/atualizar a quest.")
                    except Exception as e:
                        st.error(f"Erro ao criar/atualizar quest diária: {e}")

        st.markdown('---')

# Detailed events table
st.markdown('---')
st.subheader('Registro detalhado de eventos')
df = load_events(user=current_user)
if df.empty:
    st.write('Nenhum evento registrado')
else:
    st.dataframe(df.sort_values('date', ascending=False))

    # --- Funcionalidade de EDIÇÃO ---
    with st.expander('Editar Eventos (por ID) / Modificar dados'):
        event_ids = df['id'].unique().tolist()
        edit_id = st.selectbox('ID do evento para editar', options=[None] + event_ids, index=0, format_func=lambda x: "Selecione um ID" if x is None else str(x), key=f'edit_id_{current_user}')

        if edit_id is not None:
            current_event = df[df['id'] == edit_id].iloc[0]
            
            col_edit_1, col_edit_2, col_edit_3 = st.columns(3)
            
            with col_edit_1:
                edit_date = st.date_input('Nova Data', value=current_event['date'], key=f'edit_date_{current_user}')
            
            with col_edit_2:
                current_area = current_event['area']
                all_areas = sorted(list(set(AREAS_DEFAULT + df['area'].unique().tolist())))
                try:
                    current_area_index = all_areas.index(current_area)
                except ValueError:
                    all_areas.insert(0, current_area)
                    current_area_index = 0
                    
                edit_area = st.selectbox('Nova Área', options=all_areas, index=current_area_index, key=f'edit_area_{current_user}')
            
            with col_edit_3:
                current_xp = int(current_event['xp'])
                edit_xp = st.number_input('Novo XP', min_value=0, value=current_xp, key=f'edit_xp_{current_user}')

            edit_note = st.text_area('Nova Nota', value=current_event['note'], key=f'edit_note_{current_user}')

            if st.button('Salvar Alterações', key=f'edit_btn_{current_user}'):
                try:
                    update_event(
                        event_id=int(edit_id),
                        event_date=edit_date,
                        area=edit_area,
                        xp=int(edit_xp),
                        note=edit_note,
                        user=current_user
                    )
                    st.success(f'Evento #{edit_id} atualizado com sucesso!')
                    safe_rerun()
                except sqlite3.OperationalError:
                    st.error("Erro: O banco de dados está bloqueado. Por favor, tente novamente.")


    st.markdown('---')
    
    # --- Funcionalidade de EXCLUSÃO ---
    if st.checkbox('Habilitar exclusão de eventos', key=f'enable_del_{current_user}'):
        del_ids = df['id'].unique().tolist()
        del_id = st.selectbox('ID do evento para deletar', options=[None] + del_ids, index=0, format_func=lambda x: "Selecione um ID" if x is None else str(x), key=f'del_id_{current_user}')
        
        if del_id is not None and st.button('Deletar evento', key=f'del_btn_{current_user}'):
            try:
                conn = sqlite3.connect(DB_PATH, timeout=5)
                c = conn.cursor()
                c.execute('DELETE FROM events WHERE id=? AND user=?', (int(del_id), current_user))
                conn.commit()
                conn.close()
                st.success(f'Evento #{del_id} deletado com sucesso!')
                safe_rerun()
            except sqlite3.OperationalError:
                st.error("Erro: O banco de dados está bloqueado. Por favor, tente novamente.")

# Quests & streaks (user-scoped)
st.markdown('---')
st.header('Quests & Streaks')
with st.expander('Criar nova quest'):
    q_title = st.text_input('Título da quest', key=f'q_title_{current_user}')
    q_area = st.selectbox('Área', options=areas, key=f'q_area_{current_user}') 
    q_xp = st.number_input('XP recompensa', min_value=0, value=50, key=f'q_xp_{current_user}')
    q_cadence = st.selectbox('Cadência', options=['daily','weekly','once'], index=0, key=f'q_cad_{current_user}')
    if st.button('Adicionar quest', key=f'addq_{current_user}') and q_title:
        add_quest(q_title, q_area, int(q_xp), cadence=q_cadence, user=current_user)
        st.success('Quest adicionada')
        safe_rerun()
        
# Formulário de Edição de Quests
with st.expander('Editar Quests (por ID) / Modificar dados'):
    quests_df_full = load_quests(user=current_user) # Recarrega todas as quests (ativas e inativas se necessário para edicao)
    if quests_df_full.empty:
        st.info("Nenhuma quest disponível para edição.")
    else:
        quest_ids = quests_df_full['id'].unique().tolist()
        edit_quest_id = st.selectbox(
            'ID da quest para editar', 
            options=[None] + quest_ids, 
            index=0, 
            format_func=lambda x: "Selecione um ID" if x is None else str(x), 
            key=f'edit_quest_id_{current_user}'
        )

        if edit_quest_id is not None:
            current_quest = quests_df_full[quests_df_full['id'] == edit_quest_id].iloc[0]
            
            with st.form(f'edit_quest_form_{current_user}'):
                
                # Campos de edição
                edit_q_title = st.text_input('Novo Título', value=current_quest['title'], key=f'edit_q_title_{current_user}')
                
                # Para a Área
                current_q_area = current_quest['area']
                all_areas_q = sorted(list(set(AREAS_DEFAULT + quests_df_full['area'].unique().tolist())))
                try:
                    current_q_area_index = all_areas_q.index(current_q_area)
                except ValueError:
                    all_areas_q.insert(0, current_q_area)
                    current_q_area_index = 0
                edit_q_area = st.selectbox('Nova Área', options=all_areas_q, index=current_q_area_index, key=f'edit_q_area_{current_user}')
                
                edit_q_xp = st.number_input('Novo XP Recompensa', min_value=0, value=int(current_quest['xp_reward']), key=f'edit_q_xp_{current_user}')
                
                # Para a Cadência
                current_q_cadence = current_quest['cadence']
                cadence_options = ['daily', 'weekly', 'once']
                current_q_cadence_index = cadence_options.index(current_q_cadence) if current_q_cadence in cadence_options else 0
                edit_q_cadence = st.selectbox('Nova Cadência', options=cadence_options, index=current_q_cadence_index, key=f'edit_q_cadence_{current_user}')
                
                edit_q_streak = st.number_input('Novo Streak', min_value=0, value=int(current_quest['streak']), key=f'edit_q_streak_{current_user}')
                
                edit_submitted = st.form_submit_button('Salvar Alterações da Quest', key=f'edit_quest_btn_{current_user}')
                
                if edit_submitted:
                    try:
                        update_quest(
                            quest_id=int(edit_quest_id),
                            title=edit_q_title,
                            area=edit_q_area,
                            xp_reward=int(edit_q_xp),
                            cadence=edit_q_cadence,
                            streak=int(edit_q_streak),
                            user=current_user
                        )
                        st.success(f'Quest #{edit_quest_id} atualizada com sucesso!')
                        safe_rerun()
                    except sqlite3.OperationalError:
                        st.error("Erro: O banco de dados está bloqueado. Por favor, tente novamente.")


quests_df = load_quests(user=current_user) # Carrega APENAS as quests ativas para exibição
if quests_df.empty:
    st.write('Nenhuma quest ativa.')
else:
    for _, r in quests_df.iterrows():
        qid = int(r["id"])
        qtitle = r["title"]
        qarea = r["area"]
        qxp = int(r["xp_reward"])
        qcadence = r["cadence"]
        qlast = r["last_done"] if r["last_done"] else "Nunca"
        qstreak = r["streak"]

        col1, col2, col3 = st.columns([3,1,1])
        with col1:
            st.write(f"**{qtitle}** — {qarea} — {qxp} XP — {qcadence}")
            st.write(f"Último: {qlast} | Streak: {qstreak}")
        with col2:
            btn_label = f"Completar #{qid}"
            btn_key = f"comp_{current_user}_{qid}"
            if st.button(btn_label, key=btn_key):
                try:
                    ok = complete_quest(qid, user=current_user)
                    if ok:
                        st.success("Quest marcada como completa e XP concedido")
                        st.components.v1.html("<script>try{new Audio().play();}catch(e){}</script>", height=0)
                        safe_rerun()
                except sqlite3.OperationalError:
                    st.error("Erro: O banco de dados está bloqueado. Por favor, tente novamente.")
        with col3:
            dis_label = f"Desativar #{qid}"
            dis_key = f"dis_{current_user}_{qid}"
            if st.button(dis_label, key=dis_key):
                try:
                    conn = sqlite3.connect(DB_PATH, timeout=5)
                    c = conn.cursor()
                    c.execute('UPDATE quests SET active=0 WHERE id=? AND (user=? OR user IS NULL)', (qid, current_user))
                    conn.commit()
                    conn.close()
                    safe_rerun()
                except sqlite3.OperationalError:
                    st.error("Erro: O banco de dados está bloqueado. Por favor, tente novamente.")

def migrate_penalties_table(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS penalties (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            area TEXT NOT NULL,
            amount INTEGER NOT NULL,
            user TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

migrate_penalties_table()

def migrate_penalty_applications_table(path: Path = DB_PATH):
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS penalty_applications (
            id INTEGER PRIMARY KEY,
            penalty_id INTEGER,
            penalty_name TEXT,
            user TEXT,
            area TEXT,
            amount INTEGER,
            note TEXT,
            applied_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(penalty_id) REFERENCES penalties(id)
        )
    """)
    conn.commit()
    conn.close()

migrate_penalty_applications_table()

# ---------- Funções utilitárias ----------
def add_penalty(name: str, area: str, amount: int, user: str = None):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("INSERT INTO penalties (name, area, amount, user) VALUES (?, ?, ?, ?)",
              (name, area, int(amount), user))
    conn.commit()
    conn.close()

def load_penalties(user: str = None):
    conn = sqlite3.connect(DB_PATH)
    if user:
        df = pd.read_sql_query(
            "SELECT * FROM penalties WHERE (user=? OR user IS NULL) ORDER BY id DESC",
            conn, params=(user,))
    else:
        df = pd.read_sql_query("SELECT * FROM penalties ORDER BY id DESC", conn)
    conn.close()

    if df.empty:
        return pd.DataFrame(columns=["id","name","area","amount","user","created_at"])

    # remove duplicatas globais se existir versão do usuário com mesmo nome
    specific = df[df["user"] == user]["name"].tolist()
    if specific:
        df = df[~((df["user"].isna()) & (df["name"].isin(specific)))]

    return df

def _penalty_last_applied_key(user: str, penalty_id: int):
    return f"penalty_last_applied_{user}_{penalty_id}"

def can_apply_penalty(user: str, penalty_id: int, block_days: int = 1):
    key = _penalty_last_applied_key(user, penalty_id)
    last = get_user_config(user, key, None)

    if last is None or last == "None":
        return True, ""

    try:
        last_date = date.fromisoformat(str(last))
        if (date.today() - last_date).days >= block_days:
            return True, ""
        else:
            next_allowed = last_date + timedelta(days=block_days)
            return False, (
                f"Você só poderá aplicar novamente em {next_allowed.isoformat()}."
            )
    except Exception:
        return True, ""

# ---------- Auditoria ----------
def record_penalty_application(penalty_id: int, penalty_name: str,
                               user: str, area: str, amount: int, note: str = ""):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("""
        INSERT INTO penalty_applications
        (penalty_id, penalty_name, user, area, amount, note, applied_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (penalty_id, penalty_name, user, area, amount, note,
          datetime.now().isoformat()))
    conn.commit()
    conn.close()

# ---------- Aplicação da penalidade ----------
def apply_penalty(penalty_row: dict, user: str, block_days: int = 1):
    try:
        pid = int(penalty_row["id"])
        name = penalty_row["name"]
        area = penalty_row["area"]
        amount = int(penalty_row["amount"])

        allowed, msg = can_apply_penalty(user, pid, block_days)
        if not allowed:
            return False, msg

        # evento negativo
        add_event(date.today(), area, -abs(amount),
                  note=f"Penalidade: {name}", type_="penalty", user=user)

        # auditoria
        record_penalty_application(pid, name, user, area,
                                   -abs(amount),
                                   note=f"Aplicado por {user}")

        # bloquear por 1 dia
        set_user_config(
            user,
            _penalty_last_applied_key(user, pid),
            date.today().isoformat()
        )

        return True, f"Penalidade '{name}' aplicada: -{amount} XP."
    except Exception as e:
        return False, f"Erro ao aplicar penalidade: {e}"

# ------------------ Penalidades (com criação, aplicação e histórico) ------------------

st.markdown('---')
st.header('Penalidades por quebra de hábito')

# 1) Painel: penalidade automática (missed daily) — conserva o comportamento existente
with st.expander('Configurar penalidades automáticas'):
    st.markdown("### Penalidade Diária (Missed Daily Quest)")
    default_penalize_str = get_user_config(current_user, 'penalty_active', 'False')
    default_penalize = default_penalize_str.lower() == 'true'
    default_penalty_amount = int(get_user_config(current_user, 'penalty_amount', 10))

    penalize_key = f'penalize_{current_user}'
    penalty_amount_key = f'penalty_{current_user}'

    penalize = st.checkbox(
        'Ativar penalidades automáticas (missed daily => -XP)',
        value=default_penalize,
        key=penalize_key,
        on_change=lambda: set_user_config(current_user, 'penalty_active', st.session_state[penalize_key])
    )

    penalty_amount = st.number_input(
        'XP a subtrair por falta (diária)',
        min_value=0,
        value=default_penalty_amount,
        key=penalty_amount_key,
        on_change=lambda: set_user_config(current_user, 'penalty_amount', st.session_state[penalty_amount_key])
    )

    # Penalidades por metas semanais/mensais não atingidas
    st.markdown("### Penalidades por Metas Não Atingidas (Semanal/Mensal)")

    # Semanal
    default_penalize_weekly_str = get_user_config(current_user, 'penalty_weekly_active', 'False')
    default_penalize_weekly = default_penalize_weekly_str.lower() == 'true'
    # Valor base para a penalidade semanal
    default_penalty_weekly_amount = int(get_user_config(current_user, 'penalty_weekly_amount', 50)) 

    penalize_weekly_key = f'penalize_weekly_{current_user}'
    penalty_weekly_amount_key = f'penalty_weekly_amount_{current_user}'

    penalize_weekly = st.checkbox(
        'Ativar penalidades por **meta semanal** não atingida',
        value=default_penalize_weekly,
        key=penalize_weekly_key,
        on_change=lambda: set_user_config(current_user, 'penalty_weekly_active', st.session_state[penalize_weekly_key])
    )

    penalty_weekly_amount = st.number_input(
        'XP a subtrair por meta semanal não atingida (base)',
        min_value=0,
        value=default_penalty_weekly_amount,
        key=penalty_weekly_amount_key,
        on_change=lambda: set_user_config(current_user, 'penalty_weekly_amount', st.session_state[penalty_weekly_amount_key])
    )

    # Mensal
    default_penalize_monthly_str = get_user_config(current_user, 'penalty_monthly_active', 'False')
    default_penalize_monthly = default_penalize_monthly_str.lower() == 'true'
    # Valor base para a penalidade mensal
    default_penalty_monthly_amount = int(get_user_config(current_user, 'penalty_monthly_amount', 100)) 

    penalize_monthly_key = f'penalize_monthly_{current_user}'
    penalty_monthly_amount_key = f'penalty_monthly_amount_{current_user}'

    penalize_monthly = st.checkbox(
        'Ativar penalidades por **meta mensal** não atingida',
        value=default_penalize_monthly,
        key=penalize_monthly_key,
        on_change=lambda: set_user_config(current_user, 'penalty_monthly_active', st.session_state[penalize_monthly_key])
    )

    penalty_monthly_amount = st.number_input(
        'XP a subtrair por meta mensal não atingida (base)',
        min_value=0,
        value=default_penalty_monthly_amount,
        key=penalty_monthly_amount_key,
        on_change=lambda: set_user_config(current_user, 'penalty_monthly_amount', st.session_state[penalty_monthly_amount_key])
    )

# Executa a penalidade automática (missed daily)
if penalize and 'quests_df' in globals() and not quests_df.empty:
    today = date.today()
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    for _, q in quests_df.iterrows():
        if q['cadence'] == 'daily':
            try:
                last_done = q['last_done']
                if last_done:
                    last = datetime.fromisoformat(last_done).date()
                    if (today - last).days > 1:
                        new_streak = max(0, int(q['streak']) - ((today - last).days - 1))
                        c.execute('UPDATE quests SET streak=? WHERE id=?', (new_streak, int(q['id'])))
                        # grava evento negativo
                        add_event(today, q['area'], -int(penalty_amount),
                                  note=f'Penalty automática: missed {q["title"]}', type_='penalty', user=current_user)
            except Exception:
                continue
    conn.commit()
    conn.close()

# Lógica de penalidade por metas não atingidas (Semanal/Mensal)
def check_and_apply_goal_penalties(user: str):
    """
    Verifica se as metas semanais e mensais do período anterior foram atingidas
    e aplica a penalidade, se ativada.
    """
    today = date.today()
    
    # --- 1. Penalidade Semanal ---
    if get_user_config(user, 'penalty_weekly_active', 'False').lower() == 'true':
        penalty_amount = int(get_user_config(user, 'penalty_weekly_amount', 50))
        # Verifica se estamos em uma nova semana (segunda-feira) e se a verificação da semana anterior já ocorreu
        last_weekly_check_str = get_user_config(user, 'last_weekly_penalty_check', '2000-01-01')
        last_weekly_check = date.fromisoformat(last_weekly_check_str)
        
        # O período a ser verificado é a semana anterior
        # Começo da semana anterior (segunda)
        prev_week_start = today - timedelta(days=today.weekday() + 7) 
        # Fim da semana anterior (domingo)
        prev_week_end = prev_week_start + timedelta(days=6)

        # Só verifica se hoje for uma nova semana (Monday == 0) e a verificação não foi feita nesta semana
        # Ou se a última checagem foi antes do início da semana anterior.
        if today.weekday() == 0 and last_weekly_check < today: # Verifica apenas na segunda-feira

            df_prev_week = load_events(user=user)
            if not df_prev_week.empty:
                df_prev_week['date'] = pd.to_datetime(df_prev_week['date']).dt.date
                df_prev_week = df_prev_week[(df_prev_week['date'] >= prev_week_start) & (df_prev_week['date'] <= prev_week_end)]
            
            # Checa Metas configuradas via expansor "Configurar metas (por área)"
            goals_config = {}
            for area in AREAS_DEFAULT:
                weekly_target = int(get_user_config(user, f'goal_weekly_{area}', 0))
                if weekly_target > 0:
                    goals_config[area] = weekly_target
            
            # Agrega XP por área na semana anterior
            xp_by_area_prev_week = df_prev_week.groupby('area')['xp'].sum() if not df_prev_week.empty else pd.Series(dtype=float)
            
            for area, target in goals_config.items():
                xp_achieved = int(xp_by_area_prev_week.get(area, 0))
                if xp_achieved < target:
                    # Aplica a penalidade!
                    note = f"Penalty Semanal: Meta {area} ({target} XP) não atingida na semana de {prev_week_start.isoformat()} - {prev_week_end.isoformat()}. XP alcançado: {xp_achieved}"
                    add_event(today, area, -abs(penalty_amount), note=note, type_='penalty_weekly_fail', user=user)
                    st.toast(f"🚨 Penalidade de -{penalty_amount} XP em {area} por falha na meta semanal.", icon="❌")
            
            # Marca a verificação como feita
            set_user_config(user, 'last_weekly_penalty_check', today.isoformat())

    # --- 2. Penalidade Mensal ---
    if get_user_config(user, 'penalty_monthly_active', 'False').lower() == 'true':
        penalty_amount = int(get_user_config(user, 'penalty_monthly_amount', 100))
        # Verifica se estamos em um novo mês (primeiro dia)
        last_monthly_check_str = get_user_config(user, 'last_monthly_penalty_check', '2000-01-01')
        last_monthly_check = date.fromisoformat(last_monthly_check_str)
        
        # O período a ser verificado é o mês anterior
        first_of_month = date(today.year, today.month, 1)
        prev_month_end = first_of_month - timedelta(days=1)
        prev_month_start = date(prev_month_end.year, prev_month_end.month, 1)

        # Só verifica se hoje for o primeiro do mês e a verificação não foi feita neste mês
        if today.day == 1 and last_monthly_check < today:

            df_prev_month = load_events(user=user)
            if not df_prev_month.empty:
                df_prev_month['date'] = pd.to_datetime(df_prev_month['date']).dt.date
                df_prev_month = df_prev_month[(df_prev_month['date'] >= prev_month_start) & (df_prev_month['date'] <= prev_month_end)]
            
            # Checa Metas configuradas via expansor "Configurar metas (por área)"
            goals_config = {}
            for area in AREAS_DEFAULT:
                monthly_target = int(get_user_config(user, f'goal_monthly_{area}', 0))
                if monthly_target > 0:
                    goals_config[area] = monthly_target
            
            # Agrega XP por área no mês anterior
            xp_by_area_prev_month = df_prev_month.groupby('area')['xp'].sum() if not df_prev_month.empty else pd.Series(dtype=float)
            
            for area, target in goals_config.items():
                xp_achieved = int(xp_by_area_prev_month.get(area, 0))
                if xp_achieved < target:
                    # Aplica a penalidade!
                    note = f"Penalty Mensal: Meta {area} ({target} XP) não atingida no mês de {prev_month_start.isoformat()} - {prev_month_end.isoformat()}. XP alcançado: {xp_achieved}"
                    add_event(today, area, -abs(penalty_amount), note=note, type_='penalty_monthly_fail', user=user)
                    st.toast(f"🚨 Penalidade de -{penalty_amount} XP em {area} por falha na meta mensal.", icon="❌")
            
            # Marca a verificação como feita
            set_user_config(user, 'last_monthly_penalty_check', today.isoformat())

# Executa a checagem de metas no início da página
check_and_apply_goal_penalties(current_user)

st.markdown('---')

# 2) Painel: criar penalidade customizada (user-scoped)
with st.expander('Criar nova penalidade (personalizada)'):
    p_name = st.text_input('Nome da penalidade (ex: Falta - Casa)', key=f'pen_name_{current_user}')
    p_area = st.selectbox('Área afetada', options=available_areas_for_main, index=max(0, available_areas_for_main.index('Casa') if 'Casa' in available_areas_for_main else 0), key=f'pen_area_{current_user}')
    p_amount = st.number_input('XP a subtrair por aplicação', min_value=0, value=10, key=f'pen_amount_{current_user}')
    if st.button('Salvar penalidade', key=f'save_pen_{current_user}') and p_name:
        try:
            add_penalty(p_name.strip(), p_area.strip(), int(p_amount), user=current_user)
            st.success('Penalidade criada.')
            safe_rerun()
        except Exception as e:
            st.error(f'Erro ao criar penalidade: {e}')

# 3) Lista de penalidades e UI de aplicar
st.subheader('Penalidades disponíveis (globais + minhas)')
pens_df = load_penalties(user=current_user)

if pens_df is None or pens_df.empty:
    st.info('Nenhuma penalidade cadastrada. Crie uma no painel acima.')
else:
    for _, prow in pens_df.iterrows():
        p = prow.to_dict()
        cols = st.columns([3,1,1])
        with cols[0]:
            st.write(f"**{p['name']}** — Área: {p['area']} — XP: {p['amount']}")
            if p.get('user'):
                st.caption(f"Personal — owner: {p['user']}")
            else:
                st.caption("Global")
        with cols[1]:
            # verifica bloqueio (1 dia) por aplicação
            allowed, msg = can_apply_penalty(current_user, int(p['id']), block_days=1)
            apply_key = f"apply_pen_{current_user}_{int(p['id'])}"
            if allowed:
                if st.button(f"Aplicar {p['name']}", key=apply_key):
                    ok, message = apply_penalty(p, user=current_user, block_days=1)
                    if ok:
                        st.success(message)
                        safe_rerun()
                    else:
                        st.error(message)
            else:
                st.button("Aplicar (bloqueado)", key=apply_key + "_blocked")
                st.warning(msg)
        with cols[2]:
            # permitir exclusão apenas para penalidades do próprio usuário
            if p.get('user') == current_user:
                if st.button("Excluir", key=f"del_pen_{current_user}_{int(p['id'])}"):
                    try:
                        conn = sqlite3.connect(DB_PATH, timeout=5)
                        c = conn.cursor()
                        c.execute("DELETE FROM penalties WHERE id=? AND user=?", (int(p['id']), current_user))
                        conn.commit()
                        conn.close()
                        st.success("Penalidade excluída.")
                        safe_rerun()
                    except Exception as e:
                        st.error(f"Erro ao excluir: {e}")
            else:
                st.write("")

st.markdown('---')

# 4) Histórico de aplicações (auditoria) — mantém a UI que você já tem
st.subheader('Histórico de aplicações de penalidades (auditoria)')

all_pens_df = load_penalties(user=None)  # carrega todas (globais + pessoais)
penalty_options = ["(Todos)"] + [f"{int(r['id'])} - {r['name']}" for _, r in all_pens_df.iterrows()]

colf1, colf2, colf3 = st.columns([3,2,2])
with colf1:
    chosen_penalty = st.selectbox("Filtrar por penalidade", options=penalty_options, index=0)
with colf2:
    date_from = st.date_input("De", value=(date.today() - timedelta(days=30)))
with colf3:
    date_to = st.date_input("Até", value=date.today())

user_filter = st.text_input("Filtrar por usuário (ex: seu usuário) - vazio para todos", value="")

if st.button("Carregar histórico"):
    q = "SELECT * FROM penalty_applications WHERE DATE(applied_at) BETWEEN ? AND ?"
    params = [date_from.isoformat(), date_to.isoformat()]
    if chosen_penalty and chosen_penalty != "(Todos)":
        pid = int(chosen_penalty.split(" - ")[0])
        q += " AND penalty_id = ?"
        params.append(pid)
    if user_filter.strip():
        q += " AND user LIKE ?"
        params.append(f"%{user_filter.strip()}%")

    conn = sqlite3.connect(DB_PATH)
    df_hist = pd.read_sql_query(q + " ORDER BY applied_at DESC", conn, params=params)
    conn.close()

    if df_hist.empty:
        st.info("Nenhum registro encontrado para os filtros selecionados.")
    else:
        df_hist['applied_at'] = pd.to_datetime(df_hist['applied_at'])
        st.write(f"Mostrando {len(df_hist)} registros")
        st.dataframe(df_hist)
        csv_buf = io.StringIO()
        df_hist.to_csv(csv_buf, index=False)
        csv_bytes = csv_buf.getvalue().encode('utf-8')
        st.download_button("Exportar CSV do histórico", data=csv_bytes, file_name="penalty_applications_history.csv", mime="text/csv")

st.caption("A aplicação de penalidades cria eventos negativos (tipo 'penalty') e grava auditoria em penalty_applications.")

# --- PAINEL: Níveis por área (mostra XP e Level por área)
area_totals = compute_area_xp_totals(user=current_user)
area_levels = {a: level_from_xp(area_totals.get(a, 0)) for a in AREAS_DEFAULT}

st.markdown('---')
st.subheader("Níveis por área")
for a in AREAS_DEFAULT:
    st.write(f"**{a}** — XP: {area_totals.get(a, 0)} → Lv {area_levels.get(a, 1)}")

# Perks display (user-scoped) com contadores regressivos para perks temporais
st.markdown('---')
st.header('Perks desbloqueáveis')
perks_df = load_perks(user=current_user)
area_xp = aggregate_xp_by_area(df)
area_levels = {a: level_from_xp(int(area_xp.get(a, 0))) for a in AREAS_DEFAULT}

for _, p in perks_df.iterrows():
    unlocked = False
    area = p['area']
    if not area or pd.isna(area):
        unlocked = level_from_xp(int(df['xp'].sum() if not df.empty else 0)) >= int(p['unlock_level'])
    else:
        req_area = area.split('/')[0]
        unlocked = area_levels.get(req_area, 1) >= int(p['unlock_level'])

    # Informações de tempo/multiplicador
    dur = int(p.get('duration_days') or 0)
    mult = float(p.get('multiplier') or 1.0)
    start = p.get('start_date')
    is_active_flag = int(p.get('active') or 0)

    if unlocked:
        col1, col2 = st.columns([4,1])
        with col1:
            st.success(f"**{p['name']}** — {p['effect']}")
            st.write(
                f"Áreas: {p.get('area') or 'Todas'} | Requisito Lv {p['unlock_level']} | Multiplier: x{float(p.get('multiplier') or 1.0):.2f}")
            if dur > 0:
                if is_active_flag:
                    remaining = perk_time_remaining(p)
                    st.info(f"Ativa — tempo restante: {remaining}")
                else:
                    st.info(f"Duração: {dur} dias (quando ativada)")
        with col2:
            # Botão de ativar/desativar (ativa só para perks desbloqueadas)
            act_key = f"activate_perk_{current_user}_{int(p['id'])}"
            deact_key = f"deactivate_perk_{current_user}_{int(p['id'])}"
            if is_active_flag:
                if st.button("Desativar", key=deact_key):
                    try:
                        deactivate_perk(int(p['id']), user=current_user)
                        st.success("Perk desativada")
                        safe_rerun()
                    except sqlite3.OperationalError:
                        st.error("Erro ao desativar perk: DB bloqueado")
            else:
                if st.button("Ativar", key=act_key):
                    try:
                        activate_perk(int(p['id']), user=current_user)
                        st.success("Perk ativada — será aplicada nas próximas atividades registradas")
                        safe_rerun()
                    except sqlite3.OperationalError:
                        st.error("Erro ao ativar perk: DB bloqueado")
    else:
        st.write(f"**{p['name']}** — (Requisito: {area} Lv {p['unlock_level']}) — {p['effect']}")

# Level up detection (user-scoped)
prev_level = st.session_state.get(f'prev_level_{current_user}', None)
current_total_xp = int(df['xp'].sum()) if not df.empty else 0
current_level = level_from_xp(current_total_xp)
if prev_level is None:
    st.session_state[f'prev_level_{current_user}'] = current_level
elif current_level > prev_level:
    st.balloons()
    st.success(f'Parabéns — você alcançou o nível {current_level}!')
    st.session_state[f'prev_level_{current_user}'] = current_level

st.caption("Dica: O arquivo de banco de dados é 'versao2_mim.db' (local). Use 'Exportar events.csv' para backup.")