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
    conn = sqlite3.connect(path, timeout=5)
    c = conn.cursor()
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
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS perks (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            area TEXT,
            unlock_level INTEGER NOT NULL,
            effect TEXT,
            user TEXT
        )
        """
    )
    conn.commit()
    conn.close()

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
def add_event(event_date: date, area: str, xp: int, note: str = "", type_: str = "manual", user: str = None):
    conn = sqlite3.connect(DB_PATH, timeout=5) 
    c = conn.cursor()
    c.execute(
        "INSERT INTO events (date, area, xp, note, type, user) VALUES (?, ?, ?, ?, ?, ?)",
        (event_date.isoformat(), area, xp, note, type_, user),
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

def add_perk(name: str, area: str, unlock_level: int, effect: str, user: str = None):
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    c.execute("INSERT INTO perks (name, area, unlock_level, effect, user) VALUES (?, ?, ?, ?, ?)", (name, area, unlock_level, effect, user))
    conn.commit()
    conn.close()

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
    add_perk(
        'Focus Booster', 
        'Produtividade', 
        3, 
        '10% XP bonus para tarefas de produtividade', 
        user=None
    )

    # 3. Insere a versão Deep Work EXCLUSIVA para Marcel (Coding)
    add_perk(
        'Deep Work', 
        'Coding', 
        5, 
        'XP x1.2 em Coding por 7 dias', 
        user='marcel.pimenta'
    )

    # 4. Insere a versão Deep Work EXCLUSIVA para Larissa (Educação, Inglês, Produtividade)
    add_perk(
        'Deep Work', 
        'Educação/Inglês/Produtividade', # Áreas listadas no campo Area para exibição
        5, 
        'XP x1.2 em Educação, Inglês e Produtividade por 7 dias', 
        user='larissa.souza'
    )

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
        submitted = st.form_submit_button('Registrar XP', key=f'ev_submit_{current_user}')
        if submitted:
            add_event(ev_date, ev_area, int(ev_xp), ev_note, user=current_user)
            st.success(f'Registrado: {ev_xp} XP em {ev_area} em {ev_date} (usuário: {current_user})')
            safe_rerun()

with col2:
    st.subheader('Snapshot Rápido')
    df = load_events(user=current_user)
    total_xp = int(df['xp'].sum()) if not df.empty else 0
    lvl, xp_curr, xp_next, pct = xp_progress_in_level(total_xp)
    st.metric('Nível atual', f"{lvl}")
    st.progress(pct)
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
with st.expander('Configurar metas (por área)'):
    for a in areas: 
        default_w = int(get_user_config(current_user, f'goal_weekly_{a}', 100))
        default_m = int(get_user_config(current_user, f'goal_monthly_{a}', 400))
        
        w_key = f'goal_w_{current_user}_{a}'
        m_key = f'goal_m_{current_user}_{a}'
        
        st.markdown(f"**{a}**")
        w = st.number_input(
            'Meta semanal XP',
            min_value=0, 
            value=default_w, 
            key=w_key,
            on_change=lambda area=a: set_user_config(current_user, f'goal_weekly_{area}', st.session_state[w_key])
        )
        m = st.number_input(
            'Meta mensal XP', 
            min_value=0, 
            value=default_m, 
            key=m_key,
            on_change=lambda area=a: set_user_config(current_user, f'goal_monthly_{area}', st.session_state[m_key])
        )
        goals[a] = {'weekly': w, 'monthly': m}
        st.markdown('---')

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
        st.write(f"**{a}** — Semana: {w_xp}/{goals[a]['weekly']} | Mês: {m_xp}/{goals[a]['monthly']}")
        st.progress(min(w_xp / max(1, goals[a]['weekly']), 1.0))

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
    # ... (código do formulário 'Criar nova quest' existente)
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

# Penalidades simples (user-scoped)
st.markdown('---')
st.header('Penalidades por quebra de hábito (configurar)')

with st.expander('Configurar penalidades'):
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
        'XP a subtrair por falta', 
        min_value=0, 
        value=default_penalty_amount, 
        key=penalty_amount_key,
        on_change=lambda: set_user_config(current_user, 'penalty_amount', st.session_state[penalty_amount_key])
    )

if penalize and not quests_df.empty:
    today = date.today()
    conn = sqlite3.connect(DB_PATH, timeout=5)
    c = conn.cursor()
    for _, q in quests_df.iterrows():
        if q['cadence'] == 'daily' and q['last_done']:
            try:
                last = datetime.fromisoformat(q['last_done']).date()
                if (today - last).days > 1:
                    new_streak = max(0, int(q['streak']) - ((today - last).days - 1))
                    c.execute('UPDATE quests SET streak=? WHERE id=?', (new_streak, int(q['id'])))
                    add_event(today, q['area'], -int(penalty_amount), note=f'Penalty: missed {q["title"]}', type_='penalty', user=current_user)
            except Exception:
                continue
    conn.commit()
    conn.close()

# Perks display (user-scoped)
st.markdown('---')
st.header('Perks desbloqueáveis')
perks_df = load_perks(user=current_user)
area_xp = aggregate_xp_by_area(df)
area_levels = {a: level_from_xp(int(area_xp.get(a, 0))) for a in AREAS_DEFAULT}
for _, p in perks_df.iterrows():
    unlocked = False
    area = p['area']
    if not area or pd.isna(area):
        # Desbloqueio baseado no XP total
        unlocked = level_from_xp(int(df['xp'].sum() if not df.empty else 0)) >= int(p['unlock_level'])
    else:
        # Desbloqueio baseado em área específica (usa a primeira área listada como requisito)
        req_area = area.split('/')[0] 
        unlocked = area_levels.get(req_area, 1) >= int(p['unlock_level'])
        
    if unlocked:
        st.success(f"**{p['name']}** (desbloqueado) — {p['effect']}")
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