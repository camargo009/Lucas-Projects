"""Acompanhamento do curso (EAD): leitura das planilhas de monitoramento e agregações.

Cada aba da planilha é uma fotografia do curso numa data (ex.: "L11 - 26.10"). A aba mais recente
define a situação atual; o conjunto das abas forma a evolução. Dados pessoais irrelevantes para o
painel (CPF, telefone, mensagens de encaminhamento) são descartados na leitura.
"""
from __future__ import annotations

import difflib
import re
from pathlib import Path

import numpy as np
import pandas as pd

from .models import COLS_CURSO_ALUNOS, COLS_CURSO_ATIVIDADES, COLS_CURSO_EVOLUCAO
from .parser import norm

COLS_LINHAS = ["nome", "email", "curso", "data", "rotulo", "acesso", "modulo", "ordem", "atividade", "concluido"]

SITUACAO_CONCLUIDO = "Concluído"
SITUACAO_ANDAMENTO = "Em andamento"
SITUACAO_SEM_PROGRESSO = "Sem progresso"
SITUACAO_NUNCA = "Nunca acessou"

_MINUSCULAS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o", "para", "com", "ao"}
_SIGLAS = {"sus", "bls", "rpa", "pbm", "ead", "uti", "ii", "iii"}


def _titulo(s: str) -> str:
    """'MANEJO DE VIA AÉREA' -> 'Manejo de via aérea' (texto já misto é mantido)."""
    s = re.sub(r"^\s*m[oó]dulo\s*:\s*", "", str(s).strip(), flags=re.I)
    if s != s.upper():
        return s
    palavras = []
    for i, p in enumerate(s.lower().split()):
        base = re.sub(r"\W", "", p)
        if base in _SIGLAS:
            palavras.append(p.upper())
        elif i > 0 and base in _MINUSCULAS:
            palavras.append(p)
        else:
            palavras.append(p.capitalize() if i == 0 else p)
    return " ".join(palavras)


def nome_do_curso(caminho: str | Path) -> str:
    n = norm(Path(caminho).stem)
    if "anest" in n:
        return "Anestesiologia"
    if "onco" in n:
        return "Oncologia"
    return Path(caminho).stem.strip()


def parse_acesso(txt) -> tuple[float, bool]:
    """'4 dias 10 horas' -> (4.42, False); 'Nunca' -> (nan, True); vazio -> (nan, False)."""
    n = norm(txt)
    if not n:
        return np.nan, False
    if n.startswith("nunca"):
        return np.nan, True
    dias = re.search(r"(\d+)\s*dia", n)
    horas = re.search(r"(\d+)\s*hora", n)
    if not dias and not horas:
        return np.nan, False
    return (int(dias.group(1)) if dias else 0) + (int(horas.group(1)) if horas else 0) / 24, False


def _concluido(v) -> bool:
    return norm(v) in {"concluido", "sim", "true", "1", "completo"}


def _data_da_aba(nome_aba: str, ano: int) -> pd.Timestamp:
    m = re.search(r"(\d{1,2})\.(\d{1,2})\s*$", nome_aba.strip())
    if not m:
        return pd.NaT
    try:
        return pd.Timestamp(year=ano, month=int(m.group(2)), day=int(m.group(1)))
    except ValueError:
        return pd.NaT


def _rotulo_da_aba(nome_aba: str) -> str:
    m = re.match(r"\s*(L\s*\d+)", nome_aba, flags=re.I)
    return re.sub(r"\s+", "", m.group(1)).upper() if m else nome_aba.strip()


def _achar_cabecalho(df: pd.DataFrame) -> int | None:
    for i in range(min(len(df), 12)):
        vals = {norm(v) for v in df.iloc[i].tolist()}
        if "nome" in vals and "acesso ao curso" in vals:
            return i
    return None


def _ler_aba(df: pd.DataFrame, nome_aba: str, curso: str) -> pd.DataFrame:
    h = _achar_cabecalho(df)
    if h is None:
        return pd.DataFrame(columns=COLS_LINHAS)
    cab = [norm(v) for v in df.iloc[h].tolist()]
    c_nome, c_acesso = cab.index("nome"), cab.index("acesso ao curso")
    c_email = next((j for j, v in enumerate(cab) if "mail" in v), None)
    fim = next((j for j, v in enumerate(cab) if v.startswith("quantas atividades")), len(cab))
    colunas = [j for j in range(c_acesso + 1, fim) if cab[j]]

    # módulos: células "Módulo: ..." nas linhas acima do cabeçalho, válidas até o próximo módulo
    modulo_por_col: dict[int, str] = {}
    atual = "Geral"
    linha_mod = next((k for k in range(max(0, h - 3), h)
                      if any(norm(v).startswith("modulo") for v in df.iloc[k].tolist())), None)
    for j in range(len(cab)):
        if linha_mod is not None:
            v = df.iat[linha_mod, j]
            if isinstance(v, str) and norm(v).startswith("modulo"):
                atual = _titulo(v)
        modulo_por_col[j] = atual

    titulo = " ".join(str(v) for k in range(h) for v in df.iloc[k].tolist() if isinstance(v, str))
    ano = int(m.group(0)) if (m := re.search(r"20\d\d", titulo)) else pd.Timestamp.today().year
    data, rotulo = _data_da_aba(nome_aba, ano), _rotulo_da_aba(nome_aba)

    linhas = []
    for i in range(h + 1, len(df)):
        nome = df.iat[i, c_nome]
        if not isinstance(nome, str) or not nome.strip():
            break
        email = df.iat[i, c_email] if c_email is not None else None
        email = str(email).strip().lower() if isinstance(email, str) else None
        acesso = str(df.iat[i, c_acesso]).strip()
        for ordem, j in enumerate(colunas):
            linhas.append({
                "nome": nome.strip(), "email": email, "curso": curso, "data": data, "rotulo": rotulo,
                "acesso": acesso, "modulo": modulo_por_col[j], "ordem": ordem,
                "atividade": re.sub(r"\s+", " ", str(df.iat[h, j])).strip(),
                "concluido": _concluido(df.iat[i, j]),
            })
    return pd.DataFrame(linhas, columns=COLS_LINHAS)


def ler_planilha_curso(caminho: str | Path, curso: str | None = None) -> pd.DataFrame:
    """Lê todas as abas de monitoramento e devolve linhas aluno × atividade × fotografia."""
    caminho = Path(caminho)
    curso = curso or nome_do_curso(caminho)
    partes = []
    for aba, df in pd.read_excel(caminho, sheet_name=None, header=None).items():
        if norm(aba) == "base":
            continue
        p = _ler_aba(df, aba, curso)
        if not p.empty and p["data"].notna().all():
            partes.append(p)
    if not partes:
        return pd.DataFrame(columns=COLS_LINHAS)
    return pd.concat(partes, ignore_index=True)


# ------------------------------------------------------------------ montagem
def _vincular(linhas: pd.DataFrame, especialistas: pd.DataFrame) -> dict[tuple[str, str], str | None]:
    """Associa cada aluno do curso a um especialista (e-mail, depois nome, depois nome aproximado)."""
    por_email = {str(e).strip().lower(): i for i, e in zip(especialistas["especialista_id"], especialistas["email"])
                 if isinstance(e, str) and e.strip()}
    por_nome = {norm(n): i for i, n in zip(especialistas["especialista_id"], especialistas["nome"])}
    mapa: dict[tuple[str, str], str | None] = {}
    for (nome, email), _ in linhas.groupby(["nome", "email"], dropna=False):
        n = norm(nome)
        eid = por_nome.get(n) or (por_email.get(email) if isinstance(email, str) else None)
        if eid is None and por_nome:
            prox = difflib.get_close_matches(n, list(por_nome), n=1, cutoff=0.88)
            eid = por_nome[prox[0]] if prox else None
        mapa[(nome, email if isinstance(email, str) else "")] = eid
    return mapa


def _situacao(nunca: bool, concl: int, total: int) -> str:
    if nunca:
        return SITUACAO_NUNCA
    if total and concl >= total:
        return SITUACAO_CONCLUIDO
    return SITUACAO_ANDAMENTO if concl > 0 else SITUACAO_SEM_PROGRESSO


def montar_curso(linhas: pd.DataFrame, especialistas: pd.DataFrame
                 ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Linhas aluno × atividade × fotografia -> (alunos, atividades, evolução)."""
    if linhas.empty:
        return (pd.DataFrame(columns=COLS_CURSO_ALUNOS), pd.DataFrame(columns=COLS_CURSO_ATIVIDADES),
                pd.DataFrame(columns=COLS_CURSO_EVOLUCAO))
    l = linhas.copy()
    l["data"] = pd.to_datetime(l["data"])
    mapa = _vincular(l, especialistas)
    l["especialista_id"] = [mapa.get((n, e if isinstance(e, str) else "")) for n, e in zip(l["nome"], l["email"])]
    l["_chave"] = l["nome"].map(norm)

    evo = (l.groupby(["curso", "_chave", "rotulo", "data"], dropna=False)
           .agg(especialista_id=("especialista_id", "first"), nome=("nome", "first"),
                concluidas=("concluido", "sum"), total=("concluido", "size")).reset_index())
    evo["percentual"] = evo["concluidas"] / evo["total"] * 100
    evo = evo.sort_values(["curso", "data", "nome"])[COLS_CURSO_EVOLUCAO]

    ultima = l.groupby("curso")["data"].transform("max")
    atual = l[l["data"] == ultima]
    atividades = atual.assign(concluido=atual["concluido"].astype(bool))[COLS_CURSO_ATIVIDADES]

    alunos = []
    for (curso, _), g in atual.groupby(["curso", "_chave"], sort=False):
        dias, nunca = parse_acesso(g["acesso"].iloc[0])
        concl, total = int(g["concluido"].sum()), len(g)
        alunos.append({
            "especialista_id": g["especialista_id"].iloc[0], "nome": g["nome"].iloc[0], "email": g["email"].iloc[0],
            "curso": curso, "ultimo_acesso_dias": dias, "nunca_acessou": nunca, "concluidas": concl,
            "total": total, "percentual": concl / total * 100 if total else 0.0,
            "situacao": _situacao(nunca, concl, total),
        })
    return pd.DataFrame(alunos, columns=COLS_CURSO_ALUNOS), atividades.reset_index(drop=True), evo.reset_index(drop=True)


def carregar_cursos(caminhos: list[str | Path], especialistas: pd.DataFrame
                    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    partes = [ler_planilha_curso(c) for c in caminhos if Path(c).exists()]
    partes = [p for p in partes if not p.empty]
    if not partes:
        return montar_curso(pd.DataFrame(columns=COLS_LINHAS), especialistas)
    return montar_curso(pd.concat(partes, ignore_index=True), especialistas)


# --------------------------------------------------------------- agregações
def kpis_curso(alunos: pd.DataFrame) -> dict:
    if alunos.empty:
        return {"alunos": 0, "progresso_medio": 0.0, "concluiram": 0, "nunca": 0, "em_andamento": 0}
    return {
        "alunos": len(alunos),
        "progresso_medio": float(alunos["percentual"].mean()),
        "concluiram": int((alunos["situacao"] == SITUACAO_CONCLUIDO).sum()),
        "nunca": int((alunos["situacao"] == SITUACAO_NUNCA).sum()),
        "em_andamento": int((alunos["situacao"] == SITUACAO_ANDAMENTO).sum()),
    }


def progresso_por_modulo(atividades: pd.DataFrame) -> pd.DataFrame:
    cols = ["curso", "modulo", "concluidas", "total", "percentual"]
    if atividades.empty:
        return pd.DataFrame(columns=cols)
    g = (atividades.groupby(["curso", "modulo"], sort=False)
         .agg(concluidas=("concluido", "sum"), total=("concluido", "size"), ordem=("ordem", "min")).reset_index())
    g["percentual"] = g["concluidas"] / g["total"] * 100
    return g.sort_values(["curso", "ordem"])[cols].reset_index(drop=True)


def taxa_por_atividade(atividades: pd.DataFrame) -> pd.DataFrame:
    cols = ["curso", "modulo", "atividade", "concluidas", "total", "percentual"]
    if atividades.empty:
        return pd.DataFrame(columns=cols)
    g = (atividades.groupby(["curso", "modulo", "ordem", "atividade"], sort=False)
         .agg(concluidas=("concluido", "sum"), total=("concluido", "size")).reset_index())
    g["percentual"] = g["concluidas"] / g["total"] * 100
    return g.sort_values(["curso", "ordem"])[cols].reset_index(drop=True)


def evolucao_media(evolucao: pd.DataFrame) -> pd.DataFrame:
    cols = ["curso", "rotulo", "data", "percentual", "alunos"]
    if evolucao.empty:
        return pd.DataFrame(columns=cols)
    g = (evolucao.groupby(["curso", "rotulo", "data"])
         .agg(percentual=("percentual", "mean"), alunos=("nome", "nunique")).reset_index())
    return g.sort_values(["curso", "data"])[cols].reset_index(drop=True)


def precisam_atencao(alunos: pd.DataFrame, dias: int = 30) -> pd.DataFrame:
    """Alunos que nunca acessaram, ou sem acesso há mais de `dias`, e ainda não concluíram."""
    if alunos.empty:
        return alunos.copy()
    sem = alunos["nunca_acessou"] | (alunos["ultimo_acesso_dias"] > dias)
    r = alunos[sem & (alunos["situacao"] != SITUACAO_CONCLUIDO)]
    return r.sort_values(["nunca_acessou", "ultimo_acesso_dias"], ascending=[False, False]).reset_index(drop=True)
