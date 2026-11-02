"""Painel Projeto Mais Especialistas (ATEM/PROADI-SUS, HAOC) — Streamlit."""
from __future__ import annotations

import html
import math
import os

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from atem import analytics as an
from atem import curso as cs
from atem.agrupamento import ESTADOS, centros_estados, contornos_estados
from atem.auth import autenticar, carregar_usuarios, dados_visiveis
from atem.datasource import criar_fonte
from atem.supabase_auth import AuthError, SessionExpired, criar_auth

st.set_page_config(page_title="Mais Especialistas", page_icon="🩺", layout="wide")


def cfg(chave: str, padrao: str | None = None) -> str | None:
    try:
        if chave in st.secrets:
            return str(st.secrets[chave])
    except FileNotFoundError:
        pass
    return os.environ.get(chave, padrao)


@st.cache_resource
def _fonte():
    return criar_fonte(cfg)


@st.cache_data(ttl=60, show_spinner="Carregando dados...")
def carregar_dados():
    """Dados da fonte (Excel/REDCap) + hora da consulta; o cache curto mantém o painel quase em tempo real."""
    return _fonte().load(), pd.Timestamp.now()


@st.cache_data(ttl=30)
def _usuarios():
    return carregar_usuarios(cfg("ATEM_USERS_FILE", "data/usuarios.json"),
                            cfg("ATEM_USERS_JSON", None))


@st.cache_resource
def _auth():
    return criar_auth(cfg)


# -------------------------------------------------------------------- login
CSS_LOGIN = """<style>
[data-testid="stSidebar"], [data-testid="stHeader"] {display: none;}
.stApp {background: radial-gradient(1100px 600px at 15% -10%, rgba(20,163,179,.35), transparent 60%),
  radial-gradient(900px 500px at 100% 0%, rgba(31,58,95,.55), transparent 60%), #0B1220;}
.block-container {max-width: 460px; padding-top: 7vh;}
.marca {text-align: center; margin-bottom: 22px;}
.marca .logo {width: 72px; height: 72px; border-radius: 22px; margin: 0 auto 16px; display: flex;
  align-items: center; justify-content: center; font-size: 2.1rem;
  background: linear-gradient(135deg, #14A3B3, #1F3A5F); box-shadow: 0 10px 30px rgba(20,163,179,.4);}
.marca h1 {font-size: 2.1rem; margin: 0; padding: 0; font-weight: 800; letter-spacing: -.02em;
  background: linear-gradient(90deg, #7FE3EE, #14A3B3 60%, #9B8CE0); -webkit-background-clip: text;
  background-clip: text; -webkit-text-fill-color: transparent;}
.marca p {color: #9FB3C8; margin: 8px 0 0; font-size: .9rem;}
[data-testid="stForm"] {background: rgba(255,255,255,.05); border: 1px solid rgba(255,255,255,.12);
  border-radius: 20px; padding: 26px 24px; backdrop-filter: blur(8px);}
.stApp label, .stApp p {color: #E6EDF5;}
[data-baseweb="input"], [data-baseweb="base-input"] {background-color: rgba(255,255,255,.07) !important;
  border-radius: 10px !important; border: 1px solid rgba(255,255,255,.18) !important;}
[data-baseweb="input"] input {color: #fff !important; -webkit-text-fill-color: #fff;}
.rodape-login {text-align: center; color: #6F829A; font-size: .78rem; margin-top: 18px;}
</style>"""


def tela_login(supabase: bool = False) -> None:
    st.markdown("\n".join(l for l in CSS_LOGIN.splitlines() if l.strip()), unsafe_allow_html=True)
    st.markdown('<div class="marca"><div class="logo">🩺</div><h1>Mais Especialistas</h1>'
                '<p>Projeto Mais Especialistas · ATEM / PROADI-SUS · HAOC</p></div>', unsafe_allow_html=True)
    if "aviso_logout" in st.session_state:
        st.warning(st.session_state.pop("aviso_logout"))
    if supabase:
        tela_login_supabase()
        return
    try:
        usuarios = _usuarios()
    except ValueError:
        st.error("A configuração de contas está inválida. Peça à administração para revisar ATEM_USERS_JSON.")
        return
    if not usuarios:
        st.error("Nenhum usuário cadastrado. Rode `python scripts/gerar_usuarios.py` (veja o README).")
        return
    with st.form("login"):
        email = st.text_input("E-mail", placeholder="seu@email.com")
        senha = st.text_input("Senha", type="password", placeholder="••••••••")
        if st.form_submit_button("Entrar", type="primary", use_container_width=True):
            u = autenticar(usuarios, email, senha)
            if u:
                st.session_state["usuario"] = u
                st.rerun()
            st.error("E-mail ou senha inválidos.")
    st.markdown('<div class="rodape-login">Acesso restrito a especialistas e supervisores do projeto.</div>',
                unsafe_allow_html=True)


def tela_login_supabase() -> None:
    try:
        auth = _auth()
    except AuthError as exc:
        st.error(str(exc))
        return
    with st.form("login_supabase", clear_on_submit=True):
        email = st.text_input("E-mail", placeholder="seu@email.com")
        password = st.text_input("Senha", type="password")
        if st.form_submit_button("Entrar", type="primary", use_container_width=True):
            try:
                session = auth.sign_in(email, password)
            except AuthError as exc:
                st.error(str(exc))
            else:
                st.session_state["auth_session"] = session
                st.session_state["usuario"] = session.usuario
                st.rerun()
    with st.expander("Esqueci minha senha"):
        st.caption("Solicite um código por e-mail. Depois informe o código e a nova senha abaixo.")
        with st.form("solicitar_codigo", clear_on_submit=True):
            email_reset = st.text_input("E-mail da conta")
            if st.form_submit_button("Enviar código"):
                try:
                    auth.request_password_reset(email_reset)
                except AuthError as exc:
                    st.error(str(exc))
                else:
                    st.success("Se houver uma conta elegível, você receberá as instruções por e-mail.")
        with st.form("redefinir_senha", clear_on_submit=True):
            email_verify = st.text_input("E-mail cadastrado")
            code = st.text_input("Código recebido por e-mail")
            new_password = st.text_input("Nova senha", type="password", help="Pelo menos 12 caracteres.")
            confirmation = st.text_input("Confirme a nova senha", type="password")
            if st.form_submit_button("Salvar nova senha"):
                if new_password != confirmation:
                    st.error("As senhas não coincidem.")
                else:
                    try:
                        auth.reset_password(email_verify, code, new_password)
                    except AuthError as exc:
                        st.error(str(exc))
                    else:
                        st.success("Senha alterada. Entre com a nova senha.")
    st.caption("Acesso por convite da coordenação. Não há cadastro público.")


# ------------------------------------------------------------------ helpers
def seletor_periodo(ds, chave: str = "periodo"):
    """Período opcional: começa vazio (= todo o histórico); só filtra se o usuário escolher início e fim."""
    datas = ds.atividades["data"].dropna()
    if datas.empty:
        return None, None
    mn, mx = datas.min().date(), datas.max().date()
    sel = st.date_input("Período (opcional)", value=(), min_value=mn, max_value=mx, key=chave,
                        format="DD/MM/YYYY", help="Deixe vazio para ver o total. Para filtrar, escolha a data inicial e a final.")
    if isinstance(sel, (tuple, list)) and len(sel) == 2:
        return pd.Timestamp(sel[0]), pd.Timestamp(sel[1])
    return None, None


ROTULOS = {
    "posicao": "Posição", "nome": "Nome", "especialidade": "Especialidade", "mentor": "Mentor(a)",
    "atendimentos": "Atendimentos", "especialistas": "Especialistas", "procedimentos": "Procedimentos",
    "consultas": "Consultas", "media_por_especialista": "Média por especialista",
    "atendimentos_recentes": "Atendimentos recentes", "ultima_atividade": "Última atividade",
    "dias_sem_atividade": "Dias sem atividade",
}


def tabela(df: pd.DataFrame, cols: list[str] | None = None, **kw) -> None:
    """Tabela com títulos legíveis e vazios em texto (nunca 'None'/'NaT')."""
    d = df[[c for c in cols if c in df.columns]] if cols else df.copy()
    d = d.copy()
    for c in d.columns:
        if pd.api.types.is_datetime64_any_dtype(d[c]):
            d[c] = d[c].dt.strftime("%d/%m/%Y").fillna("Sem atividades")
        elif c == "dias_sem_atividade":
            d[c] = d[c].map(lambda v: "Sem atividades" if pd.isna(v) else f"{int(v)} dia(s)")
    d = d.fillna("—").rename(columns=ROTULOS)
    st.dataframe(d, hide_index=True, use_container_width=True, **kw)


def legenda_periodo(ini, fim) -> str:
    return "total geral" if ini is None else f"de {ini:%d/%m/%Y} a {fim:%d/%m/%Y}"


PALETA = ["#14A3B3", "#F4A259", "#7BC9A6", "#E0626B", "#9B8CE0"]
CSS = """
<style>
.block-container {padding-top: 2rem;}
.banner {background: linear-gradient(120deg, #0E7C86 0%, #1F3A5F 100%); color: #fff;
  border-radius: 16px; padding: 22px 28px; margin-bottom: 18px;}
.banner h1 {font-size: 1.7rem; margin: 0 0 6px 0; padding: 0; color: #fff;}
.banner .chip {display: inline-block; background: rgba(255,255,255,.18); border-radius: 999px;
  padding: 3px 12px; margin: 4px 6px 0 0; font-size: .82rem;}
.kcard {border-radius: 14px; padding: 16px 18px; border: 1px solid rgba(128,128,128,.25);
  background: rgba(128,128,128,.08); border-left: 6px solid var(--c);}
.kcard.hero {padding: 26px 30px;}
.kcard.hero .vl {font-size: 3.6rem;}
.kcard.hero .lb {font-size: .95rem;}
.idgrid {display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 18px; margin-bottom: 8px;}
.idgrid .vl {word-break: break-word;}
.linha-controle {min-height: 2.9rem; margin-bottom: 9px; display: flex; align-items: center; font-size: .85rem; opacity: .85;}
.secao {display: flex; align-items: center; gap: 10px; margin: 0 0 14px 0;}
.secao span {font-size: 1.1rem; font-weight: 700;}
.secao .ponto {width: 8px; height: 22px; border-radius: 6px; background: linear-gradient(180deg, #14A3B3, #9B8CE0);}
[data-testid="stVerticalBlockBorderWrapper"] {border: 1px solid rgba(128,128,128,.18) !important;
  border-radius: 18px !important; background: rgba(128,128,128,.06); box-shadow: 0 6px 22px rgba(0,0,0,.10);
  padding: 6px 8px;}
[data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {box-shadow: none;
  background: rgba(128,128,128,.05);}
.kcard {border: 0; border-radius: 16px; background: linear-gradient(145deg, rgba(20,163,179,.14), rgba(128,128,128,.06));
  box-shadow: inset 0 0 0 1px rgba(128,128,128,.16);}
.kcard.hero {background: linear-gradient(135deg, #0E7C86 0%, #1F3A5F 100%); box-shadow: 0 10px 28px rgba(14,124,134,.30);}
.kcard.hero, .kcard.hero * {color: #fff !important;}
.kcard.hero .vl {font-size: 3.4rem;}
.barra {height: 10px; border-radius: 999px; background: rgba(128,128,128,.25); overflow: hidden; margin-top: 10px;}
.barra > div {height: 100%; border-radius: 999px; background: linear-gradient(90deg, #14A3B3, #7BC9A6);}
.sit {display: inline-block; padding: 3px 12px; border-radius: 999px; font-size: .8rem; font-weight: 600;
  background: rgba(20,163,179,.18); color: #14A3B3;}
.atv {display: flex; gap: 10px; align-items: flex-start; padding: 7px 4px; font-size: .92rem;}
.atv .ok {color: #1E9E6A;} .atv .pend {color: #9AA5B1;}
[data-baseweb="tag"] {background-color: rgba(20,163,179,.20) !important; border-radius: 999px !important;
  border: 1px solid rgba(20,163,179,.45);}
[data-baseweb="tag"] span, [data-baseweb="tag"] svg {color: #BFEFF4 !important; fill: #BFEFF4 !important;
  -webkit-text-fill-color: #BFEFF4 !important;}
@media (max-width: 768px) {
  .block-container {padding: 1rem .8rem 3rem !important;}
  .banner {padding: 16px 18px;} .banner h1 {font-size: 1.3rem;}
  .kcard.hero {padding: 18px 20px;} .kcard.hero .vl {font-size: 2.6rem;}
  .kcard .vl {font-size: 1.6rem;}
  .idgrid {grid-template-columns: 1fr 1fr; gap: 10px;}
  .destaque {flex-wrap: wrap; padding: 14px 16px; gap: 12px;} .destaque .dn {font-size: 1.2rem;}
  .destaque .pill {margin-left: 0;}
  [data-testid="stHorizontalBlock"] {flex-wrap: wrap !important; gap: .6rem !important;}
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {min-width: 100% !important; flex: 1 1 100% !important;}
  [data-testid="stVerticalBlockBorderWrapper"] {padding: 2px 2px;}
  [data-baseweb="tab-list"] {overflow-x: auto;}
}
.destaque {display: flex; align-items: center; gap: 18px; padding: 20px 24px; margin-bottom: 14px;
  border-radius: 16px; border: 2px solid #14A3B3; background: rgba(20,163,179,.10);
  box-shadow: 0 4px 18px rgba(20,163,179,.18);}
.destaque .avatar {width: 64px; height: 64px; border-radius: 50%; background: linear-gradient(135deg,#14A3B3,#1F3A5F);
  color: #fff; display: flex; align-items: center; justify-content: center; font-size: 1.5rem; font-weight: 700;}
.destaque .dn {font-size: 1.5rem; font-weight: 700; line-height: 1.2;}
.destaque .ds {opacity: .8;}
.destaque .pill {margin-left: auto; background: #1E9E6A; color: #fff; border-radius: 999px; padding: 4px 14px;
  font-weight: 600; font-size: .85rem;}
.destaque .pill.off {background: #E0626B;}
.kcard .ic {font-size: 1.3rem;}
.kcard .lb {font-size: .8rem; opacity: .75; text-transform: uppercase; letter-spacing: .04em;}
.kcard .vl {font-size: 2rem; font-weight: 700; line-height: 1.15;}
.kcard .sb {font-size: .8rem; opacity: .7;}
</style>
"""


TEMAS = {
    "escuro": {"bg": "#0E1117", "side": "#161B22", "fg": "#FAFAFA", "plotly": "plotly_dark",
               "tag_bg": "rgba(20,163,179,.22)", "tag_fg": "#BFEFF4"},
    "claro": {"bg": "#FFFFFF", "side": "#F3F5F8", "fg": "#1B1F24", "plotly": "plotly_white",
              "tag_bg": "#E0F4F6", "tag_fg": "#0E6F78"},
}


def tema() -> dict:
    return TEMAS["escuro" if st.session_state.get("escuro", True) else "claro"]


def css_tema() -> str:
    t = tema()
    claro_extra = "" if st.session_state.get("escuro", True) else """
[data-baseweb="input"], [data-baseweb="input"] > div, [data-baseweb="base-input"], [data-baseweb="select"] > div,
[data-baseweb="select"] > div > div, [data-baseweb="textarea"], [data-testid="stNumberInput"] button,
[data-testid="stDateInput"] > div > div {background-color: #FFFFFF !important; color: #1B1F24 !important;}
[data-testid="stNumberInput"] button svg, [data-testid="stDateInput"] svg {fill: #1B1F24 !important;}
[data-baseweb="input"] input::placeholder {color: #6B7280 !important; -webkit-text-fill-color: #6B7280;}
[data-testid="stMultiSelect"] [role="group"], [data-testid="stSelectbox"] [role="group"], [data-testid="stNumberInput"] [role="group"],
[data-testid="stSelectbox"] [data-rac], [data-testid="stNumberInput"] input {background-color: #FFFFFF !important; border: 1px solid rgba(128,128,128,.45) !important;}
[data-testid="stMultiSelect"] input, [data-testid="stSelectbox"] input, [data-testid="stSelectbox"] [data-rac],
[data-testid="stMultiSelect"] [role="group"] *:not([data-baseweb="tag"]) {color: #1B1F24 !important; -webkit-text-fill-color: #1B1F24;}
[data-testid="stMultiSelect"] button, [data-testid="stSelectbox"] button, [data-testid="stNumberInput"] button {background-color: #FFFFFF !important; color: #1B1F24 !important;}
[data-testid="stMultiSelect"] button svg, [data-testid="stSelectbox"] button svg, [data-testid="stNumberInput"] button svg {fill: #1B1F24 !important; color: #1B1F24 !important;}
[data-testid="stDateInputCalendar"] {background-color: #FFFFFF !important; border: 1px solid rgba(128,128,128,.35); border-radius: 8px;}
[data-testid="stDateInputCalendar"] *:not([aria-selected="true"]) {color: #1B1F24 !important; -webkit-text-fill-color: #1B1F24;}
[data-testid="stDateInputCalendar"] [role="gridcell"], [data-testid="stDateInputCalendar"] [role="gridcell"] * {background-color: #F1F5F9 !important;}
[data-testid="stDateInputCalendar"] [aria-selected="true"], [data-testid="stDateInputCalendar"] [aria-selected="true"] * {background-color: #14A3B3 !important; color: #FFFFFF !important;}
[data-testid="stDateInputCalendar"] svg {fill: #1B1F24 !important;}
[data-testid$="Dropdown"], [data-testid$="Dropdown"] [role="listbox"] {background-color: #FFFFFF !important; border: 1px solid rgba(128,128,128,.35); border-radius: 8px;}
[data-testid$="Dropdown"] *, [role="listbox"] * {color: #1B1F24 !important; -webkit-text-fill-color: #1B1F24;}
[role="option"]:hover, [role="option"][data-focused="true"], [role="option"][aria-selected="true"] {background-color: #E6F4F6 !important;}
[data-testid="stCheckbox"] label:has(input[role="switch"]:not(:checked)) > div:first-of-type {background-color: #CBD5E1 !important;}
[data-baseweb="popover"], [data-baseweb="popover"] > div, [data-baseweb="popover"] ul, [data-baseweb="popover"] li,
[data-baseweb="menu"], [data-baseweb="popover"] div[role="listbox"] {background-color: #FFFFFF !important; color: #1B1F24 !important;}
[data-baseweb="popover"] li:hover, [data-baseweb="popover"] li[aria-selected="true"] {background-color: #E6F4F6 !important;}
[data-baseweb="popover"] *:not(svg):not(path) {color: #1B1F24 !important; -webkit-text-fill-color: #1B1F24;}
[data-baseweb="calendar"] *, [data-baseweb="datepicker"] * {background-color: #FFFFFF !important; color: #1B1F24 !important;}
[data-testid="stDataFrame"] {filter: invert(1) hue-rotate(180deg);}
[data-testid="stAlert"] * {color: #1B1F24 !important;}
"""
    css = f"""<style>
.stApp, [data-testid="stHeader"] {{background-color: {t['bg']};}}
[data-testid="stSidebar"], [data-testid="stSidebar"] > div:first-child {{background-color: {t['side']};}}
.stApp, .stApp p, .stApp label, .stApp span, .stApp h1, .stApp h2, .stApp h3, .stApp li,
[data-testid="stMetricValue"], [data-testid="stMetricLabel"], [data-testid="stCaptionContainer"] {{color: {t['fg']};}}
.banner, .banner h1, .banner .chip, .destaque .avatar, .destaque .pill {{color: #fff !important;}}
[data-testid="stSidebar"], [data-testid="stSidebar"] *:not(svg):not(path) {{color: {t['fg']};}}
[data-testid="stSidebar"] button {{background-color: {t['bg']}; border: 1px solid rgba(128,128,128,.45);}}
[data-testid="stSidebar"] button * {{color: {t['fg']};}}
[data-testid="stSidebar"] svg {{fill: {t['fg']};}}
[data-baseweb="tab"], [data-testid="stTab"] {{color: {t['fg']};}}
[role="tablist"] {{gap: 8px; padding: 6px; border-radius: 16px; background: rgba(20,163,179,.10);
  border: 1px solid rgba(20,163,179,.35); overflow-x: auto;}}
[data-testid="stTab"] {{height: auto; padding: 10px 18px; border-radius: 12px; cursor: pointer;
  font-weight: 600; background: transparent; transition: all .15s; white-space: nowrap;}}
[data-testid="stTab"] p {{font-size: 1rem; font-weight: 600;}}
[data-testid="stTab"]:hover {{background: rgba(20,163,179,.22);}}
[data-testid="stTab"][aria-selected="true"] {{background: linear-gradient(135deg,#14A3B3,#1F6F8B) !important;
  box-shadow: 0 4px 12px rgba(20,163,179,.4);}}
[data-testid="stTab"][aria-selected="true"], [data-testid="stTab"][aria-selected="true"] * {{color: #fff !important;}}
[data-testid="stTabs"] [role="tablist"] ~ div[class*="highlight"],
[data-baseweb="tab-highlight"], [data-baseweb="tab-border"] {{display: none;}}
[data-baseweb="popover"] li, [data-baseweb="popover"] div[role="listbox"] {{background-color: {t['bg']}; color: {t['fg']};}}
[data-baseweb="tag"] {{background-color: {t['tag_bg']} !important;}}
[data-baseweb="tag"] span, [data-baseweb="tag"] svg {{color: {t['tag_fg']} !important; fill: {t['tag_fg']} !important;
  -webkit-text-fill-color: {t['tag_fg']} !important;}}
[data-baseweb="input"], [data-baseweb="base-input"], [data-baseweb="select"] > div {{
  background-color: {t['bg']} !important; border: 1px solid rgba(128,128,128,.45) !important;}}
[data-baseweb="input"] input, [data-baseweb="base-input"] input, [data-baseweb="select"] input,
[data-baseweb="select"] div, [data-baseweb="select"] span {{color: {t['fg']} !important; -webkit-text-fill-color: {t['fg']};}}
[data-testid="stSidebar"] [data-baseweb="tag"] span, [data-testid="stSidebar"] [data-baseweb="tag"] svg {{
  color: {t['tag_fg']} !important; fill: {t['tag_fg']} !important; -webkit-text-fill-color: {t['tag_fg']} !important;}}
[data-baseweb="calendar"], [data-baseweb="calendar"] * {{background-color: {t['bg']}; color: {t['fg']};}}
[data-baseweb="tag"] {{border-radius: 999px !important; padding: 2px 4px 2px 12px !important; font-weight: 600;
  border: 1px solid rgba(20,163,179,.45) !important; align-items: center;}}
[data-baseweb="tag"] *, [data-testid="stMultiSelect"] [data-baseweb="tag"] button {{background: transparent !important;
  background-color: transparent !important; border: 0 !important; box-shadow: none !important;}}
[data-baseweb="tag"] [role="presentation"], [data-baseweb="tag"] button {{width: 20px !important; height: 20px !important;
  min-width: 20px !important; margin-left: 4px !important; padding: 0 !important; border-radius: 50% !important;
  display: inline-flex !important; align-items: center; justify-content: center; cursor: pointer;
  transition: background-color .15s;}}
[data-baseweb="tag"] [role="presentation"]:hover, [data-baseweb="tag"] button:hover {{
  background-color: rgba(20,163,179,.35) !important;}}
[data-baseweb="tag"] svg {{width: 12px !important; height: 12px !important;}}
[data-testid="stMultiSelect"] [data-tag] {{border-radius: 999px !important; padding: 2px 6px 2px 12px !important;
  align-items: center; gap: 4px;}}
[data-testid="stMultiSelect"] [data-tag] button {{background: transparent !important; background-color: transparent !important;
  border: 0 !important; box-shadow: none !important; width: 20px !important; height: 20px !important; min-width: 20px !important;
  padding: 0 !important; border-radius: 50% !important; display: inline-flex !important; align-items: center;
  justify-content: center; cursor: pointer; transition: background-color .15s;}}
[data-testid="stMultiSelect"] [data-tag] button:hover {{background-color: rgba(255,255,255,.28) !important;}}
[data-testid="stMultiSelect"] [role="group"] [data-tag] button svg, [data-testid="stMultiSelect"] [role="group"] [data-tag] button svg path {{
  width: 9px !important; height: 9px !important; color: #FFFFFF !important; fill: none !important; stroke: #FFFFFF !important;}}
[data-testid="stMultiSelect"] [role="group"] [data-tag] span {{color: #FFFFFF !important; -webkit-text-fill-color: #FFFFFF !important;}}
{claro_extra}
</style>"""
    # linhas em branco encerram o bloco HTML do markdown e quebrariam o CSS
    return "\n".join(l for l in css.splitlines() if l.strip())


def grafico(fig, **kw) -> None:
    t = tema()
    fig.update_layout(template=t["plotly"], paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color=t["fg"], size=13, family="Inter, Segoe UI, sans-serif"), colorway=PALETA,
                      title=None, legend=dict(orientation="h", y=-0.18, x=0, title_text=""),
                      hoverlabel=dict(font_size=13, bgcolor=t["bg"], bordercolor="#14A3B3"))
    fig.update_xaxes(gridcolor="rgba(128,128,128,.14)", showline=False, zeroline=False)
    fig.update_yaxes(gridcolor="rgba(128,128,128,.14)", showline=False, zeroline=False)
    if not fig.layout.height:
        fig.update_layout(height=360, margin=dict(l=0, r=10, t=10, b=10))
    cfg_plotly = {"displayModeBar": False}
    cfg_plotly.update(kw.get("config", {}))
    st.plotly_chart(fig, theme=None, use_container_width=True, config=cfg_plotly)


def cabecalho(titulo: str, partes: list[str]) -> None:
    chips = "".join(f'<span class="chip">{p}</span>' for p in partes if p)
    st.markdown(f'<div class="banner"><h1>{titulo}</h1>{chips}</div>', unsafe_allow_html=True)


def cartoes(k: dict, destaque: bool = False) -> None:
    itens = [("🩺", "Atendimentos", k["total"], "no período", "#14A3B3"),
             ("🛠️", "Procedimentos", k["procedimentos_distintos"], "tipos distintos realizados", "#7BC9A6"),
             ("📅", "Dias com atividade", k["dias_ativos"], "dias distintos", "#9B8CE0")]
    if destaque:
        ic, lb, vl, sb, cor = itens.pop(0)
        st.markdown(f'<div class="kcard hero" style="--c:{cor}"><div class="ic">{ic}</div>'
                    f'<div class="lb">Total de {lb.lower()}</div><div class="vl">{vl}</div>'
                    f'<div class="sb">{sb}</div></div>', unsafe_allow_html=True)
        st.write("")
    for col, (ic, lb, vl, sb, cor) in zip(st.columns(len(itens), gap="medium"), itens):
        col.markdown(f'<div class="kcard" style="--c:{cor}"><div class="ic">{ic}</div>'
                     f'<div class="lb">{lb}</div><div class="vl">{vl}</div><div class="sb">{sb}</div></div>',
                     unsafe_allow_html=True)
    st.write("")


def grafico_evolucao(ds, ini, fim, chave: str) -> None:
    freq = st.radio("Agrupar por", ["Mês", "Semana"], horizontal=True, key=f"freq_{chave}")
    e = an.evolucao(ds, "M" if freq == "Mês" else "W", ini, fim, por_tipo=False)
    if e.empty:
        st.info("Sem atividades no período.")
        return
    fig = px.area(e, x="periodo", y="atendimentos", line_shape="linear", markers=True,
                  labels={"periodo": "", "atendimentos": "Atendimentos"})
    fig.update_traces(line=dict(color="#14A3B3", width=3), marker=dict(size=7, color="#14A3B3"),
                      fillcolor="rgba(20,163,179,.22)")
    fig.update_yaxes(rangemode="tozero")
    grafico(fig)


def secao(titulo: str, icone: str = "") -> None:
    st.markdown(f'<div class="secao"><div class="ponto"></div><span>{icone} {html.escape(titulo)}</span></div>',
                unsafe_allow_html=True)


def _abrevia(s: str, n: int = 42) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


_ALTURA = 420
_ESCALA = ["#BFEFF4", "#14A3B3", "#1F3A5F"]


def _padrao_barras(fig) -> None:
    """Mesmo enquadramento (altura, margens, eixos) para os rankings em barras."""
    fig.update_layout(height=_ALTURA, margin=dict(l=0, r=50, t=10, b=10), bargap=0.35)
    fig.update_xaxes(title=None, showgrid=True, zeroline=False, showticklabels=False)
    fig.update_yaxes(title=None, automargin=True, tickfont=dict(size=12), showgrid=False)
    fig.update_traces(marker_cornerradius=8)


def top_procedimentos_grafico(df: pd.DataFrame) -> None:
    secao("Top procedimentos", "🛠️")
    if df.empty:
        st.info("Sem dados.")
        return
    d = df.copy()
    d["pct"] = d["quantidade"] / d["quantidade"].sum() * 100
    d["rotulo"] = d["nome"].map(lambda s: _abrevia(s, 34))
    d["texto"] = d.apply(lambda r: f"{r['quantidade']} · {r['pct']:.0f}%", axis=1)
    fig = px.bar(d.iloc[::-1], x="quantidade", y="rotulo", orientation="h", text="texto",
                 color="quantidade", color_continuous_scale=_ESCALA,
                 custom_data=["nome", "pct"], labels={"rotulo": "", "quantidade": "Qtd.", "pct": "% do top"})
    fig.update_traces(textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{customdata[0]}</b><br>Quantidade: %{x}<br>%{customdata[1]:.1f}% do top<extra></extra>")
    fig.update_layout(coloraxis_showscale=False)
    _padrao_barras(fig)
    grafico(fig)


def top_cids_grafico(df: pd.DataFrame, chave: str) -> None:
    secao("Top CIDs", "🧬")
    if df.empty:
        st.info("Sem dados.")
        return
    d = df.copy()
    d["pct"] = d["quantidade"] / d["quantidade"].sum() * 100
    d["rotulo"] = d.apply(lambda r: f"{r['cid']} — {_abrevia(r['descricao'], 24)}" if r["descricao"] else r["cid"],
                          axis=1)
    modo = st.radio("Visual", ["Barras", "Mapa de blocos"], horizontal=True, key=f"cidmodo_{chave}",
                    label_visibility="collapsed")
    if modo == "Barras":
        d["texto"] = d.apply(lambda r: f"{r['quantidade']} · {r['pct']:.0f}%", axis=1)
        fig = px.bar(d.iloc[::-1], x="quantidade", y="rotulo", orientation="h", text="texto",
                     color="quantidade", color_continuous_scale=_ESCALA,
                     custom_data=["descricao", "cid", "subcodigos"], labels={"rotulo": "", "quantidade": "Qtd."})
        fig.update_traces(textposition="outside", cliponaxis=False,
                          hovertemplate="<b>%{customdata[1]}</b> — %{customdata[0]}<br>Quantidade: %{x}"
                                        "<br>Subcódigos agrupados: %{customdata[2]}<extra></extra>")
        fig.update_layout(coloraxis_showscale=False)
        _padrao_barras(fig)
    else:
        fig = px.treemap(d, path=["rotulo"], values="quantidade", color="quantidade", color_continuous_scale=_ESCALA)
        fig.update_traces(textinfo="label+value", root_color="rgba(0,0,0,0)", marker_cornerradius=8)
        fig.update_layout(coloraxis_showscale=False, margin=dict(l=0, r=0, t=10, b=10), height=_ALTURA)
    grafico(fig)


def rosca(df: pd.DataFrame, nomes: str, valores: str, cores: dict | None = None):
    fig = px.pie(df, names=nomes, values=valores, hole=0.68, color=nomes, color_discrete_map=cores or {})
    fig.update_traces(textinfo="percent", marker=dict(line=dict(color="rgba(0,0,0,0)", width=3)), sort=False)
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10))
    return fig


def painel_identificacao(e) -> None:
    def v(x):
        return html.escape(str(x)) if pd.notna(x) and str(x).strip() else "—"
    local = v(e["local_atuacao"])
    if pd.notna(e.get("uf")) and str(e.get("uf")).strip() and local != "—":
        local += f" / {html.escape(str(e['uf']))}"
    partes = [p for p in str(e["nome"]).split() if p]
    iniciais = html.escape((partes[0][0] + (partes[-1][0] if len(partes) > 1 else "")).upper()) if partes else "?"
    desist = e.get("status") == "Desistente"
    pill = "Desistente" if desist else "Ativo"
    st.markdown(
        f'<div class="destaque"><div class="avatar">{iniciais}</div>'
        f'<div><div class="dn">{v(e["nome"])}</div>'
        f'<div class="ds">{v(e["especialidade"])} · Mentor(a): {v(e["mentor"])}</div></div>'
        f'<div class="pill {"off" if desist else ""}">{pill}</div></div>', unsafe_allow_html=True)
    campos = [("📞", "Telefone", v(e["telefone"])), ("✉️", "E-mail", v(e["email"])),
              ("🩺", "Especialidade", v(e["especialidade"])), ("🎓", "Mentor(a)", v(e["mentor"])),
              ("📍", "Local de atuação", local)]
    itens = "".join(f'<div class="kcard" style="--c:#14A3B3"><div class="ic">{ic}</div>'
                    f'<div class="lb">{lb}</div><div class="vl" style="font-size:1.05rem">{vl}</div></div>'
                    for ic, lb, vl in campos)
    st.markdown(f'<div class="idgrid">{itens}</div>', unsafe_allow_html=True)
    st.write("")


def tabela_procedimentos(ds_x, ini, fim) -> None:
    secao("Procedimentos realizados", "📋")
    lp = an.lista_procedimentos(ds_x, ini, fim)
    if lp.empty:
        st.info("Sem procedimentos no período.")
        return
    st.caption(f"{len(lp)} procedimentos distintos · {int(lp['quantidade'].sum())} realizações ({legenda_periodo(ini, fim)}).")
    st.dataframe(lp.rename(columns={"codigo": "Código", "procedimento": "Procedimento", "tipo": "Tipo",
                                    "dificuldade": "Dificuldade", "quantidade": "Quantidade"}),
                 hide_index=True, use_container_width=True,
                 column_config={"Quantidade": st.column_config.ProgressColumn(
                     "Quantidade", format="%d", min_value=0, max_value=int(lp["quantidade"].max()))})


def visao_individual(ds_e, ini, fim, chave: str, destaque: bool = False) -> None:
    """Painel de um único especialista (ds_e já contém só ele)."""
    cartoes(an.kpis(ds_e, ini, fim), destaque)
    with st.container(border=True):
        secao("Evolução", "📈")
        grafico_evolucao(ds_e, ini, fim, chave)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        top_procedimentos_grafico(an.top_procedimentos(ds_e, 10, ini, fim))
    with c2, st.container(border=True):
        top_cids_grafico(an.top_cids(ds_e, 10, ini, fim), chave)
    with st.container(border=True):
        tabela_procedimentos(ds_e, ini, fim)
    a = an.filtrar_periodo(ds_e, ini, fim)
    if a["dificuldade_texto"].notna().any():
        with st.container(border=True):
            secao("Dificuldade dos casos", "🎯")
            d = a["dificuldade_texto"].dropna().str.lower().value_counts().reset_index()
            d.columns = ["dificuldade", "quantidade"]
            grafico(rosca(d, "dificuldade", "quantidade"))
    with st.container(border=True):
        secao("Mentorias", "🎓")
        m = an.mentorias_resumo(ds_e)
        if m.empty:
            st.info("Ainda não há mentorias registradas.")
        else:
            fig = px.bar(m, x="mes", y="percentual", labels={"percentual": "% participação", "mes": ""})
            fig.update_traces(marker_cornerradius=8, marker_color="#9B8CE0")
            fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=10))
            grafico(fig)
            st.dataframe(m[["mes", "propostas", "participacao", "percentual"]], hide_index=True,
                         use_container_width=True)


# ------------------------------------------------------------------- curso
def _cor_situacao(s: str) -> str:
    return {cs.SITUACAO_CONCLUIDO: "#1E9E6A", cs.SITUACAO_ANDAMENTO: "#14A3B3",
            cs.SITUACAO_SEM_PROGRESSO: "#F4A259", cs.SITUACAO_NUNCA: "#E0626B"}.get(s, "#9AA5B1")


CORES_SITUACAO = {s: _cor_situacao(s) for s in (cs.SITUACAO_CONCLUIDO, cs.SITUACAO_ANDAMENTO,
                                                 cs.SITUACAO_SEM_PROGRESSO, cs.SITUACAO_NUNCA)}


def _acesso_txt(r) -> str:
    if r["nunca_acessou"]:
        return "Nunca acessou"
    d = r["ultimo_acesso_dias"]
    if pd.isna(d):
        return "—"
    return "Hoje" if d < 1 else f"há {int(d)} dia(s)"


def barras_modulo(pm: pd.DataFrame, altura: int = 300):
    d = pm.copy()
    d["rotulo"] = d["modulo"].map(lambda s: _abrevia(s, 36))
    fig = px.bar(d.iloc[::-1], x="percentual", y="rotulo", orientation="h", text=d.iloc[::-1]["percentual"].map(lambda v: f"{v:.0f}%"),
                 custom_data=["modulo"], labels={"rotulo": "", "percentual": "% concluído"}, range_x=[0, 100])
    fig.update_traces(marker_color="#14A3B3", textposition="outside", cliponaxis=False,
                      hovertemplate="<b>%{customdata[0]}</b><br>Concluído: %{x:.0f}%<extra></extra>")
    _padrao_barras(fig)
    fig.update_layout(height=altura)
    return fig


def curso_individual(ds_e) -> None:
    """Progresso no curso (EAD) de um único especialista (ds_e já contém só ele)."""
    if ds_e.curso_alunos.empty:
        st.info("Ainda não encontramos seu progresso no curso. Se você já iniciou, fale com a coordenação.")
        return
    for _, r in ds_e.curso_alunos.iterrows():
        atv = ds_e.curso_atividades[ds_e.curso_atividades["curso"] == r["curso"]]
        evo = ds_e.curso_evolucao[ds_e.curso_evolucao["curso"] == r["curso"]].sort_values("data")
        cor = _cor_situacao(r["situacao"])
        st.markdown(
            f'<div class="kcard hero"><div class="ic">🎓</div><div class="lb">Curso de {html.escape(r["curso"])}</div>'
            f'<div class="vl">{r["percentual"]:.0f}%</div><div class="sb">{int(r["concluidas"])} de {int(r["total"])} '
            f'atividades concluídas</div><div class="barra"><div style="width:{r["percentual"]:.0f}%"></div></div></div>',
            unsafe_allow_html=True)
        st.write("")
        c1, c2 = st.columns(2, gap="medium")
        c1.markdown(f'<div class="kcard" style="--c:{cor}"><div class="ic">📌</div><div class="lb">Situação</div>'
                    f'<div class="vl" style="font-size:1.4rem;color:{cor}">{html.escape(r["situacao"])}</div></div>',
                    unsafe_allow_html=True)
        c2.markdown(f'<div class="kcard" style="--c:#9B8CE0"><div class="ic">🕒</div><div class="lb">Último acesso</div>'
                    f'<div class="vl" style="font-size:1.4rem">{_acesso_txt(r)}</div></div>', unsafe_allow_html=True)
        st.write("")
        a, b = st.columns(2, gap="medium")
        with a, st.container(border=True):
            secao("Progresso por módulo", "📚")
            grafico(barras_modulo(cs.progresso_por_modulo(atv)))
        with b, st.container(border=True):
            secao("Minha evolução no curso", "📈")
            if len(evo) < 2:
                st.info("A evolução aparece conforme novas atualizações forem registradas.")
            else:
                fig = px.area(evo, x="data", y="percentual", line_shape="linear", markers=True,
                              labels={"data": "", "percentual": "% concluído"}, range_y=[0, 105])
                fig.update_traces(line=dict(color="#14A3B3", width=3), fillcolor="rgba(20,163,179,.22)")
                fig.update_layout(height=320, margin=dict(l=0, r=16, t=16, b=10))
                fig.update_yaxes(tickvals=[0, 25, 50, 75, 100], ticksuffix="%", automargin=True)
                fig.update_xaxes(automargin=True, tickformat="%d/%m", nticks=8)
                grafico(fig)
        with st.container(border=True):
            secao("Atividades", "✅")
            for modulo, g in atv.sort_values("ordem").groupby("modulo", sort=False):
                with st.expander(f"{modulo} — {int(g['concluido'].sum())}/{len(g)}"):
                    st.markdown("".join(
                        f'<div class="atv"><span class="{"ok" if x.concluido else "pend"}">'
                        f'{"●" if x.concluido else "○"}</span><span>{html.escape(x.atividade)}</span></div>'
                        for x in g.itertuples()), unsafe_allow_html=True)


def curso_geral(alunos: pd.DataFrame, atv: pd.DataFrame, evo: pd.DataFrame) -> None:
    """Visão do curso para supervisores."""
    if alunos.empty:
        st.info("Nenhum aluno do curso para os filtros selecionados.")
        return
    cursos = sorted(alunos["curso"].unique())
    escolha = st.radio("Curso", ["Todos"] + cursos, horizontal=True, key="curso_sel")
    if escolha != "Todos":
        alunos, atv, evo = (x[x["curso"] == escolha] for x in (alunos, atv, evo))
    k = cs.kpis_curso(alunos)
    itens = [("🎓", "Alunos", k["alunos"], "matriculados", "#14A3B3"),
             ("📊", "Progresso médio", f'{k["progresso_medio"]:.0f}%', "das atividades", "#7BC9A6"),
             ("🏁", "Concluíram", k["concluiram"], "100% das atividades", "#9B8CE0"),
             ("⚠️", "Nunca acessaram", k["nunca"], "sem acesso ao curso", "#E0626B")]
    for col, (ic, lb, vl, sb, cor) in zip(st.columns(4, gap="medium"), itens):
        col.markdown(f'<div class="kcard" style="--c:{cor}"><div class="ic">{ic}</div><div class="lb">{lb}</div>'
                     f'<div class="vl">{vl}</div><div class="sb">{sb}</div></div>', unsafe_allow_html=True)
    st.write("")
    a, b = st.columns([1, 2], gap="medium")
    with a, st.container(border=True):
        secao("Situação dos alunos", "🧭")
        s = alunos["situacao"].value_counts().reset_index()
        s.columns = ["situacao", "alunos"]
        grafico(rosca(s, "situacao", "alunos", CORES_SITUACAO))
    with b, st.container(border=True):
        secao("Progresso por aluno", "🏅")
        r = alunos.sort_values("percentual").assign(rotulo=lambda d: d["nome"].map(lambda x: _abrevia(_primeiro_ultimo(x), 26)))
        fig = px.bar(r, x="percentual", y="rotulo", orientation="h", color="curso", range_x=[0, 100],
                     custom_data=["nome", "curso"], labels={"rotulo": "", "percentual": "% concluído", "curso": "Curso"})
        fig.update_traces(hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>Concluído: %{x:.0f}%<extra></extra>")
        _padrao_barras(fig)
        fig.update_xaxes(showticklabels=True)
        fig.update_layout(height=max(320, 26 * len(r) + 60))
        grafico(fig)
    c, d = st.columns(2, gap="medium")
    with c, st.container(border=True):
        secao("Progresso médio por módulo", "📚")
        pm = cs.progresso_por_modulo(atv)
        pm = pm.groupby("modulo", sort=False, as_index=False)["percentual"].mean() if not pm.empty else pm
        if not pm.empty:
            grafico(barras_modulo(pm, 340))
    with d, st.container(border=True):
        secao("Evolução do progresso médio", "📈")
        em = cs.evolucao_media(evo)
        if em.empty:
            st.info("Sem histórico.")
        else:
            fig = px.line(em, x="data", y="percentual", color="curso", line_shape="linear", markers=True,
                          labels={"data": "", "percentual": "% médio concluído", "curso": "Curso"}, range_y=[0, 105])
            fig.update_traces(line=dict(width=3))
            fig.update_layout(height=340, margin=dict(l=0, r=10, t=10, b=10))
            grafico(fig)
    with st.container(border=True):
        secao("Atividades com menor conclusão", "🔻")
        ta = cs.taxa_por_atividade(atv).sort_values("percentual").head(10)
        if ta.empty:
            st.info("Sem atividades.")
        else:
            st.dataframe(ta.rename(columns={"curso": "Curso", "modulo": "Módulo", "atividade": "Atividade",
                                            "percentual": "% de conclusão"}),
                         hide_index=True, use_container_width=True,
                         column_config={"% de conclusão": st.column_config.ProgressColumn(
                             "% de conclusão", format="%.0f%%", min_value=0, max_value=100)})
    with st.container(border=True):
        secao("Precisam de atenção", "🚨")
        dias = st.slider("Sem acessar há mais de (dias)", 7, 90, 30, format="%d dias", key="curso_dias")
        pa = cs.precisam_atencao(alunos, dias)
        if pa.empty:
            st.success("Nenhum aluno precisa de atenção.")
        else:
            pa = pa.assign(acesso=pa.apply(_acesso_txt, axis=1))
            st.dataframe(pa[["nome", "curso", "situacao", "percentual", "acesso"]].rename(columns={
                "nome": "Aluno", "curso": "Curso", "situacao": "Situação", "percentual": "% concluído",
                "acesso": "Último acesso"}), hide_index=True, use_container_width=True,
                column_config={"% concluído": st.column_config.ProgressColumn("% concluído", format="%.0f%%", min_value=0, max_value=100)})


def _primeiro_ultimo(nome: str) -> str:
    p = str(nome).split()
    return f"{p[0]} {p[-1]}".title() if len(p) > 1 else str(nome).title()


# ------------------------------------------------------------------- mapa
_ZOOM_MAPA = {  # (lon mín/máx, lat mín/máx)
    "Brasil inteiro": ((-74.5, -28), (-34.5, 7.5)),
    "Norte": ((-74.5, -43), (-14, 7.5)),
    "Nordeste": ((-49, -33), (-19, -0.5)),
    "Centro-Oeste": ((-62, -44), (-25, -6)),
    "Sudeste": ((-54, -37), (-26, -13)),
    "Sul": ((-58, -46), (-34.5, -21.5)),
}


def _mapa_brasil(loc: pd.DataFrame, metrica: str, rotulo: str, zona: str = "Brasil inteiro") -> go.Figure:
    t = tema()
    est = loc[loc["sigla"].notna()]
    por_uf = est.groupby("sigla").agg(especialistas=("nome", "size"), atendimentos=("atendimentos", "sum")).reset_index()
    por_uf["media"] = (por_uf["atendimentos"] / por_uf["especialistas"]).round(1)
    base = pd.DataFrame({"sigla": list(ESTADOS)}).merge(por_uf, on="sigla", how="left").fillna(0)
    base["estado"] = base["sigla"].map(lambda s: ESTADOS[s][0])
    base["regiao"] = base["sigla"].map(lambda s: ESTADOS[s][1])
    zmax = max(float(base[metrica].max()), 1.0)
    escala = [[0, "#BFEFF4"], [0.5, "#14A3B3"], [1, "#1F3A5F"]]
    contornos = contornos_estados()
    fig = go.Figure()
    for r in base.itertuples():
        xs, ys = contornos[r.sigla]
        com_dados = r.especialistas > 0
        cor = px.colors.sample_colorscale(escala, [getattr(r, metrica) / zmax])[0] if com_dados else "rgba(124,135,150,.28)"
        fig.add_trace(go.Scatter(
            x=xs, y=ys, mode="lines", fill="toself", fillcolor=cor, line=dict(color=t["bg"], width=1.2),
            hoveron="fills", name=r.estado, showlegend=False,
            text=f"<b>{r.estado}</b> · {r.regiao}<br>Especialistas: {r.especialistas:.0f}<br>Atendimentos: {r.atendimentos:.0f}"
                 f"<br>Média por especialista: {r.media:.1f}",
            hoverinfo="text"))
    fig.add_trace(go.Scatter(  # série invisível só para exibir a barra de cores
        x=[None], y=[None], mode="markers", hoverinfo="skip", showlegend=False,
        marker=dict(colorscale=escala, cmin=0, cmax=zmax, color=[0], showscale=True,
                    colorbar=dict(title=dict(text=rotulo, side="top"), orientation="h", thickness=10, len=0.7,
                                  x=0.5, xanchor="center", y=-0.02, yanchor="top",
                                  tickfont=dict(color=t["fg"])))))
    # um marcador por médico, espalhado ao redor do centro do estado
    centros = centros_estados()
    xs, ys, nomes, textos, tam = [], [], [], [], []
    for sg, grp in est.groupby("sigla"):
        lat0, lon0 = centros[sg]
        n = len(grp)
        for i, (_, r) in enumerate(grp.reset_index(drop=True).iterrows()):
            ang = 2 * math.pi * i / max(n, 1)
            raio = 0 if n == 1 else 0.9 + 0.12 * n
            ys.append(lat0 + raio * math.sin(ang))
            xs.append(lon0 + raio * math.cos(ang))
            nomes.append(r["nome"])
            textos.append(f"{r['especialidade']} · {r['atendimentos']} atend.<br>{r['estado']} · {r['regiao']}"
                          f"<br>{r['local_atuacao'] if pd.notna(r['local_atuacao']) else ''}")
            tam.append(11 + min(int(r["atendimentos"]), 400) / 400 * 14)
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="markers", text=nomes, customdata=textos,
                                marker=dict(size=tam, color="#FFB020", line=dict(color="#FFFFFF", width=1.5), opacity=.95),
                                hovertemplate="<b>%{text}</b><br>%{customdata}<extra></extra>", name="Médicos"))
    # rótulos: sigla em todos os estados; nome completo nos estados com médicos
    lx, ly, lt, lc = [], [], [], []
    for r in base.itertuples():
        la, lo = centros[r.sigla]
        if r.especialistas > 0:
            dy, dx = {"RJ": (-2.6, 3.6), "ES": (-1.5, 4.5), "RR": (3.8, 0)}.get(r.sigla, (3.3, 0))
            lx.append(lo + dx)
            ly.append(la + dy)
            lt.append(f"<b>{r.estado}</b>")
            lc.append(t["fg"])
        else:
            dx = 3.2 if r.sigla in {"RN", "PB", "PE", "AL", "SE", "ES"} else 0
            lx.append(lo + dx)
            ly.append(la)
            lt.append(r.sigla)
            lc.append(t["fg"])
    fig.add_trace(go.Scatter(x=lx, y=ly, mode="text", text=lt, textfont=dict(size=11, color=lc),
                             textposition="middle center", hoverinfo="skip", showlegend=False))
    xr, yr = _ZOOM_MAPA.get(zona, _ZOOM_MAPA["Brasil inteiro"])
    fig.update_xaxes(visible=False, range=list(xr), showgrid=False, zeroline=False, constrain="domain")
    fig.update_yaxes(visible=False, range=list(yr), showgrid=False, zeroline=False, scaleanchor="x", scaleratio=1.04,
                     constrain="domain")
    fig.update_layout(dragmode="pan")
    fig.update_layout(height=760 if zona == "Brasil inteiro" else 640, margin=dict(l=0, r=0, t=24, b=50), showlegend=False)
    return fig


def aba_mapa(ds, ini, fim) -> None:
    loc = an.localizacao_especialistas(ds, ini, fim)
    if loc.empty:
        st.info("Sem especialistas para os filtros.")
        return
    sem = loc[loc["sigla"].isna()]
    com = loc[loc["sigla"].notna()]
    k1, k2, k3, k4 = st.columns(4, gap="small")
    k1.metric("Estados atendidos", com["sigla"].nunique())
    k2.metric("Regiões", com["regiao"].nunique())
    k3.metric("Médicos localizados", len(com))
    k4.metric("Sem local informado", len(sem))
    with st.container(border=True):
        secao("Mapa do Brasil — onde estão os especialistas", "🗺️")
        modo = st.radio("Colorir estados por", ["Atendimentos", "Nº de especialistas", "Média por especialista"],
                        horizontal=True, key="mapa_metrica")
        metrica, rot = {"Atendimentos": ("atendimentos", "Atendimentos"),
                        "Nº de especialistas": ("especialistas", "Especialistas"),
                        "Média por especialista": ("media", "Média")}[modo]
        grafico(_mapa_brasil(loc, metrica, rot, "Brasil inteiro"),
                config={"scrollZoom": True, "displayModeBar": True, "displaylogo": False,
                        "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]})
        st.caption("Cada ponto laranja é um médico (maior = mais atendimentos). Passe o mouse para ver detalhes. "
                   "Use a roda do mouse (ou pinça no celular) para aproximar, arraste para mover e o ícone da casa para voltar.")
    por_reg = com.groupby("regiao").agg(especialistas=("nome", "size"), atendimentos=("atendimentos", "sum")).reset_index()
    por_reg["media"] = (por_reg["atendimentos"] / por_reg["especialistas"]).round(1)
    c1, c2 = st.columns(2, gap="medium")
    with c1, st.container(border=True):
        secao("Atendimentos por região", "🧭")
        fig = px.bar(por_reg.sort_values("atendimentos"), x="atendimentos", y="regiao", orientation="h", text="atendimentos",
                     color="atendimentos", color_continuous_scale=_ESCALA, custom_data=["especialistas", "media"],
                     labels={"regiao": "", "atendimentos": "Atendimentos"})
        fig.update_traces(textposition="outside", cliponaxis=False,
                          hovertemplate="<b>%{y}</b><br>Atendimentos: %{x}<br>Especialistas: %{customdata[0]}"
                                        "<br>Média: %{customdata[1]}<extra></extra>")
        fig.update_layout(coloraxis_showscale=False)
        _padrao_barras(fig)
        grafico(fig)
    with c2, st.container(border=True):
        secao("Mapa de calor: região × especialidade", "🔥")
        hm = com.pivot_table(index="regiao", columns="especialidade", values="atendimentos", aggfunc="sum", fill_value=0)
        fig = px.imshow(hm, text_auto=True, aspect="auto", color_continuous_scale=_ESCALA,
                        labels=dict(x="", y="", color="Atendimentos"))
        fig.update_layout(height=_ALTURA, margin=dict(l=0, r=0, t=10, b=10), coloraxis_showscale=False)
        grafico(fig)
    with st.container(border=True):
        secao("Estados e médicos alocados", "📍")
        est = com.groupby(["regiao", "estado"]).agg(
            especialistas=("nome", "size"), atendimentos=("atendimentos", "sum"),
            medicos=("nome", lambda s: ", ".join(s))).reset_index().sort_values("atendimentos", ascending=False)
        est["media"] = (est["atendimentos"] / est["especialistas"]).round(1)
        tabela(est.rename(columns={"regiao": "Região", "estado": "Estado", "especialistas": "Especialistas",
                                   "atendimentos": "Atendimentos", "media": "Média", "medicos": "Médicos"}))
        if not sem.empty:
            st.caption("Sem local informado: " + ", ".join(sem["nome"]))


# ------------------------------------------------------------ especialista
def pagina_especialista(u, ds_total) -> None:
    ds = dados_visiveis(u, ds_total)  # apenas os dados do próprio usuário
    if ds.especialistas.empty:
        st.warning("Não encontramos seus dados. Fale com a coordenação.")
        return
    e = ds.especialistas.iloc[0]
    cabecalho(f"Olá, {e['nome']}", [e["especialidade"], f"Mentor(a): {e['mentor']}", e["local_atuacao"]])
    if e["status"] == "Desistente":
        st.info("Seu status no projeto: desistência registrada.")
    aba_painel, aba_curso = st.tabs(["📊 Meu painel", "🎓 Meu curso"])
    with aba_painel:
        with st.container(border=True):
            secao("Meu perfil", "🪪")
            painel_identificacao(e)
        with st.container(border=True):
            secao("Filtro", "🗓️")
            ini, fim = seletor_periodo(ds, "periodo_esp")
        secao("Meu desempenho", "📊")
        visao_individual(ds, ini, fim, "esp", destaque=True)
    with aba_curso:
        curso_individual(ds)


# -------------------------------------------------------------- supervisor
def pagina_supervisor(u, ds_total) -> None:
    ds = dados_visiveis(u, ds_total)
    cabecalho("Visão geral do projeto", ["Projeto Mais Especialistas", "ATEM / PROADI-SUS", "HAOC"])
    with st.container(border=True):
        secao("Filtros", "🎛️")
        f1, f2, f3 = st.columns(3, gap="medium")
        with f1:
            ini, fim = seletor_periodo(ds, "periodo_sup")
        esp_sel = f2.multiselect("Especialidade", sorted(ds.ativos["especialidade"].dropna().unique()),
                                 placeholder="Todas")
        men_sel = f3.multiselect("Mentor", sorted(ds.ativos["mentor"].dropna().unique()), placeholder="Todos")
        st.caption(f"Exibindo: **{legenda_periodo(ini, fim)}**"
                   + (f" · {', '.join(esp_sel)}" if esp_sel else "") + (f" · mentor(es): {', '.join(men_sel)}" if men_sel else ""))
    esp = ds.ativos      # desistentes ficam fora de KPIs e rankings
    if esp_sel:
        esp = esp[esp["especialidade"].isin(esp_sel)]
    if men_sel:
        esp = esp[esp["mentor"].isin(men_sel)]
    ds_total = ds
    ds = ds_total.filtrar(esp["especialista_id"])
    if not (esp_sel or men_sel):  # sem filtro, inclui alunos do curso ainda sem vínculo
        sem_vinculo = ds_total.curso_alunos["especialista_id"].isna()
        ds.curso_alunos = ds_total.curso_alunos[sem_vinculo | ds_total.curso_alunos["especialista_id"].isin(esp["especialista_id"])]
        ds.curso_atividades = ds_total.curso_atividades[ds_total.curso_atividades["nome"].isin(ds.curso_alunos["nome"])]
        ds.curso_evolucao = ds_total.curso_evolucao[ds_total.curso_evolucao["nome"].isin(ds.curso_alunos["nome"])]

    abas = st.tabs(["📊 Visão geral", "🗺️ Mapa", "🏆 Ranking", "⚖️ Comparativos", "🚨 Alertas", "🎓 Curso", "👤 Desempenho individual"])
    t = [None, abas[0]] + list(abas[2:])
    ativos = ds.especialistas
    with t[1]:
        k = an.kpis(ds, ini, fim)
        cartoes(k)
        st.caption(f"Especialistas ativos considerados: **{len(ds.ativos)}**")
        with st.container(border=True):
            secao("Evolução", "📈")
            grafico_evolucao(ds, ini, fim, "geral")
        c1, c2 = st.columns(2, gap="medium")
        with c1, st.container(border=True):
            top_procedimentos_grafico(an.top_procedimentos(ds, 10, ini, fim))
        with c2, st.container(border=True):
            top_cids_grafico(an.top_cids(ds, 10, ini, fim), "geral")
        with st.container(border=True):
            tabela_procedimentos(ds, ini, fim)
    with abas[1]:
        aba_mapa(ds, ini, fim)
    with t[2]:
        with st.container(border=True):
            secao("Ranking", "🏆")
            modo = st.radio("Ranking", ["Total", "Por especialidade", "Por mentor"], horizontal=True,
                            label_visibility="collapsed")
            por = {"Total": None, "Por especialidade": "especialidade", "Por mentor": "mentor"}[modo]
            r = an.ranking(ds, ini, fim, por)
            if r.empty:
                st.info("Sem especialistas para os filtros.")
            else:
                if por is None:
                    fig = px.bar(r, x="atendimentos", y="nome", color="especialidade", orientation="h",
                                 custom_data=["mentor", "especialidade"], labels={"nome": "", "atendimentos": "Atendimentos", "especialidade": ""})
                    fig.update_traces(hovertemplate="<b>%{y}</b><br>%{customdata[1]} · Mentor(a): %{customdata[0]}<br>Atendimentos: %{x}<extra></extra>")
                    fig.update_yaxes(autorange="reversed")
                    _padrao_barras(fig)
                    fig.update_xaxes(showticklabels=True)
                    fig.update_layout(height=max(360, 26 * len(r) + 60))
                    grafico(fig)
                cols = ["posicao", "nome", "especialidade", "mentor", "atendimentos"]
                tabela(r, cols)
    with t[3]:
        for por, tit in (("especialidade", "Por especialidade"), ("mentor", "Por mentor")):
            g = an.resumo_grupo(ds, por, ini, fim)
            with st.container(border=True):
                secao(tit, "📊")
                if not g.empty:
                    fig = px.bar(g, x=por, y="media_por_especialista",
                                 labels={"media_por_especialista": "Média por especialista", por: ""})
                    fig.update_traces(marker_color="#14A3B3", marker_cornerradius=8)
                    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=10), bargap=0.4)
                    grafico(fig)
                    tabela(g.drop(columns=["consultas"], errors="ignore"))
        ev = an.evolucao(ds, "M", ini, fim, por_tipo=False)
        if not ev.empty:
            m = ds.atividades.merge(ds.ativos[["especialista_id", "especialidade"]], on="especialista_id")
            m = m.dropna(subset=["data"])
            if ini is not None:
                m = m[(m["data"] >= ini) & (m["data"] <= fim)]
            m["periodo"] = m["data"].dt.to_period("M").dt.start_time
            g = m.groupby(["periodo", "especialidade"]).size().reset_index(name="atendimentos")
            with st.container(border=True):
                secao("Evolução mensal por especialidade", "📈")
                fig = px.line(g, x="periodo", y="atendimentos", color="especialidade", markers=True, line_shape="linear",
                              labels={"periodo": "", "atendimentos": "Atendimentos", "especialidade": ""})
                fig.update_traces(line=dict(width=3))
                grafico(fig)
    with t[4]:
        with st.container(border=True):
            secao("Alertas de baixa atividade", "🚨")
            st.caption("Veja quem atendeu pouco recentemente. Ajuste os dois controles abaixo.")
            c1, c2 = st.columns(2, gap="large")
            dias = c1.slider("Período analisado", 7, 90, 14, step=1, format="%d dias",
                             help="Quantos dias olhar para trás, a partir da data mais recente registrada nos dados.")
            minimo = c2.slider("Mínimo de atendimentos", 1, 50, 1, step=1, format="%d",
                               help="Quem tiver menos atendimentos que isso no período aparece na lista.")
            n_min = int(minimo)
            st.info(f"Mostrando especialistas com menos de {n_min} {'atendimento' if n_min == 1 else 'atendimentos'} "
                    f"nos últimos {int(dias)} dias.")
            al = an.alertas_baixa_atividade(ds, int(dias), int(minimo))
            if al.empty:
                st.success("Nenhum especialista com baixa atividade.")
            else:
                st.warning(f"{len(al)} especialista(s) abaixo do mínimo.")
                tabela(al, ["nome", "especialidade", "mentor", "atendimentos_recentes", "ultima_atividade",
                            "dias_sem_atividade"])
    with t[5]:
        st.caption("O progresso no curso não depende do filtro de período; ele reflete a atualização mais recente.")
        curso_geral(ds.curso_alunos, ds.curso_atividades, ds.curso_evolucao)
    with t[6]:
        if ativos.empty:
            st.info("Nenhum especialista.")
        else:
            with st.container(border=True):
                secao("Identificação do especialista", "🪪")
                nome = st.selectbox("Escolha o especialista", ativos["nome"].tolist(), key="sel_esp")
                eid = ativos.loc[ativos["nome"] == nome, "especialista_id"].iloc[0]
                painel_identificacao(ativos[ativos["especialista_id"] == eid].iloc[0])
            secao(f"Desempenho — {nome}", "📊")
            ds_e = ds.only(eid)
            visao_individual(ds_e, ini, fim, "sup")
            if not ds_e.curso_alunos.empty:
                secao("Curso", "🎓")
                curso_individual(ds_e)


# --------------------------------------------------------------------- main
def main() -> None:
    provider = (cfg("AUTH_PROVIDER", "local") or "local").lower()
    if provider not in {"local", "supabase"}:
        st.error("AUTH_PROVIDER deve ser local ou supabase.")
        return
    if provider == "supabase":
        session = st.session_state.get("auth_session")
        if session is None:
            st.session_state.pop("usuario", None)
            tela_login(supabase=True)
            return
        try:
            session = _auth().validate(session)
        except SessionExpired as exc:
            st.session_state.pop("auth_session", None)
            st.session_state.pop("usuario", None)
            tela_login(supabase=True)
            st.error(str(exc))
            return
        except AuthError as exc:
            st.error(str(exc))
            return
        st.session_state["auth_session"] = session
        st.session_state["usuario"] = session.usuario
    u = st.session_state.get("usuario")
    if u is None:
        tela_login()
        return
    st.sidebar.write(f"👤 {u.nome}")
    px.defaults.color_discrete_sequence = PALETA
    st.sidebar.toggle("🌙 Modo escuro", value=True, key="escuro")
    st.markdown(CSS + css_tema(), unsafe_allow_html=True)
    st.sidebar.caption("Supervisor" if u.eh_supervisor else "Especialista")
    if st.sidebar.button("Sair"):
        session = st.session_state.pop("auth_session", None)
        st.session_state.pop("usuario", None)
        if provider == "supabase" and session is not None:
            try:
                _auth().sign_out(session)
            except AuthError:
                st.session_state["aviso_logout"] = "Você saiu deste painel, mas não foi possível encerrar a sessão remota."
        st.rerun()
    try:
        ds, atualizado = carregar_dados()
    except Exception as exc:
        st.error(f"Não foi possível carregar os dados: {exc}")
        return
    if st.sidebar.button("Atualizar dados"):
        _fonte.clear()
        carregar_dados.clear()
        st.rerun()
    st.sidebar.caption(f"Atualizado às {atualizado:%H:%M:%S}")
    (pagina_supervisor if u.eh_supervisor else pagina_especialista)(u, ds)


main()
