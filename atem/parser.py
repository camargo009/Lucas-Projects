"""Parser robusto das abas do Excel de acompanhamento (uma aba por especialista)."""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from openpyxl import load_workbook

from .models import (
    COLS_ATIVIDADES, COLS_ESPECIALISTAS, COLS_MENTORIAS, STATUS_ATIVO,
    STATUS_DESISTENTE, TIPO_CONSULTA, TIPO_PROCEDIMENTO, Dataset,
)

MESES = ["janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
         "agosto", "setembro", "outubro", "novembro", "dezembro"]
NOMES_MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho",
               "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
ESPECIALIDADE_POR_PREFIXO = {"onco": "Oncologia", "anest": "Anestesiologia"}


def norm(v: Any) -> str:
    """Texto minúsculo, sem acentos, sem pontuação de borda e com espaços colapsados."""
    if v is None:
        return ""
    s = unicodedata.normalize("NFKD", str(v))
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r"[()\[\]:]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def vazio(v: Any) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v)) or str(v).strip() == ""


def texto(v: Any) -> str | None:
    return None if vazio(v) else re.sub(r"\s+", " ", str(v)).strip()


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", norm(s)).strip("-")


def parse_numero(v: Any) -> float | None:
    if vazio(v):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace("%", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def parse_data(v: Any) -> pd.Timestamp:
    if vazio(v):
        return pd.NaT
    if isinstance(v, (datetime, date)):
        return pd.Timestamp(v)
    if isinstance(v, (int, float)):
        return pd.Timestamp("1899-12-30") + pd.Timedelta(days=float(v)) if 20000 < v < 80000 else pd.NaT
    return pd.to_datetime(str(v).strip(), dayfirst=True, errors="coerce")


def mes_numero(v: Any) -> int | None:
    """Mês a partir de nome (tolera erros de digitação como 'Novemrbo') ou data."""
    if isinstance(v, (datetime, date)):
        return v.month
    s = norm(v)
    if len(s) < 3:
        return None
    for i, m in enumerate(MESES, 1):
        if s[:3] == m[:3]:
            return i
    return None


# ---------------------------------------------------------------- metadados
_ROTULOS = [
    ("nome", "especialista"), ("telefone", "telefone"), ("email", "email"),
    ("email", "e mail"), ("especialidade", "especialidade"), ("mentor", "mentor"),
    ("local", "local de atuacao"), ("imersao", "semana de imersao"),
]


def _rotulo(cell: Any) -> str | None:
    s = norm(cell)
    if not s:
        return None
    for chave, rot in _ROTULOS:
        if s == rot:
            return chave
    if s.startswith(("visita presencial", "voo ")):
        return "outro"
    return None


def _linhas(ws) -> list[tuple]:
    return [tuple(r) for r in ws.iter_rows(values_only=True)]


def _parse_meta(rows: list[tuple], limite: int) -> dict[str, str | None]:
    meta: dict[str, str | None] = {}
    for row in rows[:limite]:
        for j, cell in enumerate(row):
            chave = _rotulo(cell)
            if not chave or chave == "outro":
                continue
            valores = [c for c in row[j + 1:] if not vazio(c)]
            # O valor é a primeira célula não vazia à direita, desde que não seja outro rótulo.
            if valores and _rotulo(valores[0]) is None:
                if chave not in meta:
                    meta[chave] = texto(valores[0])
                if chave == "local" and len(valores) > 1:
                    meta.setdefault("uf", texto(valores[1]))
            else:
                meta.setdefault(chave, None)
    return meta


# ---------------------------------------------------------------- mentorias
_METRICAS = {"propostas": "propostas", "participacao": "participacao", "percentual": "percentual"}


def _parse_mentorias(rows: list[tuple], ini: int, fim: int, eid: str) -> list[dict]:
    """Aceita meses nas linhas (colunas = métricas) ou meses nas colunas (linhas = métricas)."""
    regiao = rows[ini:fim]
    saida: dict[int, dict] = {}

    def reg(num: int, label: Any, metrica: str, valor: Any) -> None:
        d = saida.setdefault(num, {"especialista_id": eid, "mes_num": num,
                                   "mes": NOMES_MESES[num - 1], "propostas": None,
                                   "participacao": None, "percentual": None})
        valor = parse_numero(valor)
        if valor is not None:
            d[metrica] = valor

    cab = next((r for r in regiao if sum(norm(c) in _METRICAS for c in r) >= 2), None)
    if cab is not None:  # meses nas linhas
        cols = {_METRICAS[norm(c)]: j for j, c in enumerate(cab) if norm(c) in _METRICAS}
        for r in regiao[regiao.index(cab) + 1:]:
            rot = next((c for c in r[: min(cols.values()) + 1] if not vazio(c) and norm(c) not in _METRICAS), None)
            num = mes_numero(rot)
            if num is None:
                continue
            for metrica, j in cols.items():
                reg(num, rot, metrica, r[j] if j < len(r) else None)
    else:  # meses nas colunas
        header = None
        for r in regiao:
            primeiro = next((c for c in r if not vazio(c)), None)
            if primeiro is not None and norm(primeiro) in _METRICAS:
                if header is None:
                    continue
                for j, c in enumerate(r):
                    num = header.get(j)
                    if num and not vazio(c) and norm(c) not in _METRICAS:
                        reg(num, None, _METRICAS[norm(primeiro)], c)
            else:
                meses = {j: mes_numero(c) for j, c in enumerate(r) if mes_numero(c)}
                if len(meses) >= 2:
                    header = meses
    out = []
    for d in saida.values():
        if d["percentual"] is None and d["propostas"]:
            d["percentual"] = (d["participacao"] or 0) / d["propostas"] * 100
        elif d["percentual"] is not None and d["percentual"] <= 1:
            d["percentual"] *= 100
        if any(d[k] is not None for k in ("propostas", "participacao", "percentual")):
            out.append(d)
    return sorted(out, key=lambda d: d["mes_num"])


# --------------------------------------------------------------- atividades
_CAMPOS = {"cid": "cid", "cid texto": "cid_texto", "procedimento": "procedimento",
           "procedimento nome": "procedimento_nome", "dificuldade": "dificuldade",
           "dificuldade texto": "dificuldade_texto", "data": "data"}
_COD_NOME = re.compile(r"^\s*(\d{6,10})\s*[-–]\s*(.+?)\s*$")


def _achar_cabecalho(rows: list[tuple]) -> int | None:
    for i, r in enumerate(rows):
        ns = {norm(c) for c in r}
        if "cid" in ns and "data" in ns and "procedimento" in ns:
            return i
    return None


def _colunas(header: tuple) -> dict[str, int]:
    cols: dict[str, int] = {}
    for j, c in enumerate(header):
        campo = _CAMPOS.get(norm(c))
        if campo and campo not in cols:
            cols[campo] = j
    return cols


def _melhor_deslocamento(dados: list[tuple], col_data: int) -> int:
    """Se o cabeçalho estiver desalinhado dos dados, escolhe o deslocamento que gera datas válidas."""
    melhor, melhor_n = 0, -1
    for d in (0, 1, -1, 2, -2):
        j = col_data + d
        n = sum(1 for r in dados if 0 <= j < len(r) and not pd.isna(parse_data(r[j])))
        if n > melhor_n:
            melhor, melhor_n = d, n
    return melhor


def _cod_proc(v: Any) -> str | None:
    if vazio(v):
        return None
    if isinstance(v, (int, float)):
        return str(int(v)).zfill(10)
    return str(v).strip()


def _tipo(codigo: str | None, nome: str | None) -> str:
    if (nome and "consulta" in norm(nome)) or (codigo and codigo.startswith("0301")):
        return TIPO_CONSULTA
    return TIPO_PROCEDIMENTO


def _parse_atividades(rows: list[tuple], eid: str) -> list[dict]:
    h = _achar_cabecalho(rows)
    if h is None:
        return []
    cols = _colunas(rows[h])
    if "data" not in cols:
        return []
    dados = rows[h + 1:]
    desl = _melhor_deslocamento(dados, cols["data"])
    cols = {k: v + desl for k, v in cols.items()}

    def cel(r: tuple, campo: str) -> Any:
        j = cols.get(campo)
        return r[j] if j is not None and 0 <= j < len(r) else None

    out = []
    for r in dados:
        data = parse_data(cel(r, "data"))
        cid, proc_raw = texto(cel(r, "cid")), cel(r, "procedimento")
        if pd.isna(data) and cid is None and vazio(proc_raw):
            continue
        codigo, nome = _cod_proc(proc_raw), texto(cel(r, "procedimento_nome"))
        if codigo:
            m = _COD_NOME.match(codigo)
            if m:
                codigo, nome = m.group(1), nome or m.group(2)
            elif not re.fullmatch(r"\d{6,10}", codigo):
                codigo, nome = None, nome or texto(proc_raw)  # ex.: "Consulta ambulatorial"
        dif = parse_numero(cel(r, "dificuldade"))
        out.append({
            "especialista_id": eid, "cid": cid.upper() if cid else None,
            "cid_texto": texto(cel(r, "cid_texto")), "procedimento": codigo,
            "procedimento_nome": nome, "dificuldade": dif,
            "dificuldade_texto": texto(cel(r, "dificuldade_texto")), "data": data,
            "tipo": _tipo(codigo, nome),
        })
    return out


# -------------------------------------------------------------------- aba
def parse_aba(nome_aba: str, rows: list[tuple]) -> tuple[dict, list[dict], list[dict]] | None:
    """Retorna (especialista, atividades, mentorias) ou None se a aba não tiver estrutura reconhecível."""
    marcadores = [i for i, r in enumerate(rows) if any(norm(c) in ("mentorias", "atividades") for c in r)]
    cab = _achar_cabecalho(rows)
    limite = min([*marcadores, *( [cab] if cab is not None else [] ), len(rows)])
    meta = _parse_meta(rows, limite)
    if not meta.get("nome") and cab is None:
        return None
    eid = slug(nome_aba)
    prefixo = norm(nome_aba).split(" ")[0]
    desistente = prefixo.startswith("desist") or "desist" in norm(meta.get("imersao"))
    ment_ini = next((i for i, r in enumerate(rows) if any(norm(c) == "mentorias" for c in r)), None)
    ment_fim = next((i for i in range(ment_ini or 0, len(rows))
                     if any(norm(c) == "atividades" for c in rows[i])), cab if cab is not None else len(rows))
    esp = {
        "especialista_id": eid, "nome": meta.get("nome") or nome_aba,
        "telefone": meta.get("telefone"), "email": (meta.get("email") or "").lower() or None,
        "especialidade": meta.get("especialidade"), "mentor": meta.get("mentor"),
        "local_atuacao": meta.get("local"), "uf": meta.get("uf"),
        "semana_imersao": meta.get("imersao"),
        "status": STATUS_DESISTENTE if desistente else STATUS_ATIVO, "aba": nome_aba,
    }
    if not esp["especialidade"]:
        esp["especialidade"] = next((v for k, v in ESPECIALIDADE_POR_PREFIXO.items() if prefixo.startswith(k)), None)
    ment = _parse_mentorias(rows, ment_ini, ment_fim, eid) if ment_ini is not None else []
    return esp, _parse_atividades(rows, eid), ment


def parse_workbook(path: str | Path) -> Dataset:
    if Path(path).suffix.lower() == ".ods":
        esps, atvs, ments = [], [], []
        for nome, df in pd.read_excel(path, sheet_name=None, header=None, engine="odf").items():
            rows = df.astype(object).where(df.notna(), None).values.tolist()
            res = parse_aba(nome, rows)
            if res is not None:
                e, a, m = res
                esps.append(e)
                atvs.extend(a)
                ments.extend(m)
        atv_df = pd.DataFrame(atvs, columns=COLS_ATIVIDADES)
        atv_df["data"] = pd.to_datetime(atv_df["data"], errors="coerce")
        return Dataset(pd.DataFrame(esps, columns=COLS_ESPECIALISTAS),
                       atv_df, pd.DataFrame(ments, columns=COLS_MENTORIAS))
    wb = load_workbook(path, data_only=True, read_only=False)
    esps, atvs, ments = [], [], []
    for ws in wb.worksheets:
        try:
            res = parse_aba(ws.title, _linhas(ws))
        except Exception:  # uma aba problemática não deve derrubar o painel
            res = None
        if res is None:
            continue
        e, a, m = res
        esps.append(e)
        atvs += a
        ments += m
    wb.close()
    esp_df = pd.DataFrame(esps, columns=COLS_ESPECIALISTAS)
    atv_df = pd.DataFrame(atvs, columns=COLS_ATIVIDADES)
    atv_df["data"] = pd.to_datetime(atv_df["data"], errors="coerce")
    return Dataset(esp_df, atv_df, pd.DataFrame(ments, columns=COLS_MENTORIAS))
