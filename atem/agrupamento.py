"""Agrupamentos: procedimentos da mesma família, CIDs pelo código-pai e localização (UF/região)."""
from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

import pandas as pd

# ------------------------------------------------------------ procedimentos
_RUIDO = [
    r"\([^)]*\)",                                   # (PRÉVIA), (ADJUVANTE), (PRÉ-OPERATÓRIA)...
    r"\bEM\s+EST[ÁA]DIO\s+[IVX]+\b", r"\bEST[ÁA]DIO\s+[IVX]+\b",
    r"[-–]?\s*\d+\s*[ªA°º]?\s*LINHA\b", r"\bAVAN[ÇC]ADO\b",
    r"\bHER-?2\s+POSITIVO\b", r"[_\s]*x00\w+_[-–\s]*",
]


def grupo_procedimento(nome) -> str:
    """Nome-base do procedimento, sem estádio/linha/fase (ex.: quimioterapia de mama estádio II e III → uma só)."""
    if nome is None or (isinstance(nome, float) and pd.isna(nome)) or not str(nome).strip():
        return "(não informado)"
    s = str(nome).upper()
    for p in _RUIDO:
        s = re.sub(p, " ", s)
    s = re.sub(r"\bPOLIQUIMIOTERAPIA\b", "QUIMIOTERAPIA", s)
    s = re.sub(r"\b(QUIMIOTERAPIA|HORMONIOTERAPIA|RADIOTERAPIA)\s+(DO|DA|DE)\b", r"\1 DE", s)
    s = re.sub(r"\bDE\s+(O|A)\b", "DE", s)
    s = re.sub(r"[-–/]\s*$", "", re.sub(r"\s+", " ", s).strip()).strip()
    return s[:1] + s[1:].lower() if s else "(não informado)"


# --------------------------------------------------------------------- CIDs
CID_PAI = {
    "C50": "Neoplasia maligna da mama", "C61": "Neoplasia maligna da próstata",
    "C53": "Neoplasia maligna do colo do útero", "C54": "Neoplasia maligna do corpo do útero",
    "C56": "Neoplasia maligna do ovário", "C51": "Neoplasia maligna da vulva", "C52": "Neoplasia maligna da vagina",
    "C18": "Neoplasia maligna do cólon", "C19": "Neoplasia maligna da junção retossigmoide",
    "C20": "Neoplasia maligna do reto", "C21": "Neoplasia maligna do ânus", "C22": "Neoplasia maligna do fígado",
    "C25": "Neoplasia maligna do pâncreas", "C15": "Neoplasia maligna do esôfago",
    "C16": "Neoplasia maligna do estômago", "C34": "Neoplasia maligna dos brônquios e pulmões",
    "C32": "Neoplasia maligna da laringe", "C10": "Neoplasia maligna da orofaringe",
    "C64": "Neoplasia maligna do rim", "C67": "Neoplasia maligna da bexiga", "C60": "Neoplasia maligna do pênis",
    "C62": "Neoplasia maligna do testículo", "C73": "Neoplasia maligna da tireoide",
    "C71": "Neoplasia maligna do encéfalo", "C44": "Outras neoplasias malignas da pele",
    "C49": "Neoplasia maligna de tecido conjuntivo e moles", "C76": "Neoplasia maligna de outras localizações",
    "C81": "Doença de Hodgkin", "C85": "Linfoma não-Hodgkin", "C90": "Mieloma múltiplo", "C91": "Leucemia linfoide",
    "D24": "Neoplasia benigna da mama", "D25": "Leiomioma do útero",
    "K80": "Colelitíase", "K35": "Apendicite aguda", "K40": "Hérnia inguinal", "K42": "Hérnia umbilical",
    "K92": "Outras doenças do aparelho digestivo", "I84": "Hemorroidas", "N40": "Hiperplasia da próstata",
    "R10": "Dor abdominal e pélvica", "Z00": "Exame geral e investigação", "Z30": "Contracepção",
    "Z12": "Rastreamento de neoplasias", "Z51": "Outros cuidados médicos",
}
_PAI = re.compile(r"^\s*([A-Za-z]\d{2})")


def cid_pai(cid) -> str | None:
    m = _PAI.match(str(cid)) if cid is not None and not (isinstance(cid, float) and pd.isna(cid)) else None
    return m.group(1).upper() if m else None


def nome_cid_pai(pai: str, textos: pd.Series | None = None) -> str:
    if pai in CID_PAI:
        return CID_PAI[pai]
    if textos is not None and textos.notna().any():
        t = str(textos.dropna().mode().iloc[0]).strip()
        return t[:60]
    return ""


# ----------------------------------------------------------------- geografia
ESTADOS = {
    "AC": ("Acre", "Norte"), "AL": ("Alagoas", "Nordeste"), "AP": ("Amapá", "Norte"), "AM": ("Amazonas", "Norte"),
    "BA": ("Bahia", "Nordeste"), "CE": ("Ceará", "Nordeste"), "DF": ("Distrito Federal", "Centro-Oeste"),
    "ES": ("Espírito Santo", "Sudeste"), "GO": ("Goiás", "Centro-Oeste"), "MA": ("Maranhão", "Nordeste"),
    "MT": ("Mato Grosso", "Centro-Oeste"), "MS": ("Mato Grosso do Sul", "Centro-Oeste"),
    "MG": ("Minas Gerais", "Sudeste"), "PA": ("Pará", "Norte"), "PB": ("Paraíba", "Nordeste"),
    "PR": ("Paraná", "Sul"), "PE": ("Pernambuco", "Nordeste"), "PI": ("Piauí", "Nordeste"),
    "RJ": ("Rio de Janeiro", "Sudeste"), "RN": ("Rio Grande do Norte", "Nordeste"),
    "RS": ("Rio Grande do Sul", "Sul"), "RO": ("Rondônia", "Norte"), "RR": ("Roraima", "Norte"),
    "SC": ("Santa Catarina", "Sul"), "SP": ("São Paulo", "Sudeste"), "SE": ("Sergipe", "Nordeste"),
    "TO": ("Tocantins", "Norte"),
}


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn").lower().strip()


_POR_NOME = {_sem_acento(n): sg for sg, (n, _) in ESTADOS.items()}


def uf_do_especialista(uf, local=None) -> str | None:
    """Sigla da UF a partir da coluna UF (sigla ou nome) ou, na falta, do texto do local de atuação."""
    if uf is not None and not (isinstance(uf, float) and pd.isna(uf)):
        u = str(uf).strip()
        if u.upper() in ESTADOS:
            return u.upper()
        if _sem_acento(u) in _POR_NOME:
            return _POR_NOME[_sem_acento(u)]
    if local is not None and not (isinstance(local, float) and pd.isna(local)):
        t = _sem_acento(local)
        # nomes mais longos primeiro (ex.: "mato grosso do sul" antes de "mato grosso")
        for nome in sorted(_POR_NOME, key=len, reverse=True):
            if re.search(rf"\b{nome}\b", t):
                return _POR_NOME[nome]
        m = re.search(r"[-/,]\s*([A-Za-z]{2})\s*$", str(local).strip())
        if m and m.group(1).upper() in ESTADOS:
            return m.group(1).upper()
    return None


def regiao_da_uf(sigla: str | None) -> str:
    return ESTADOS[sigla][1] if sigla in ESTADOS else "Não informada"


@lru_cache(maxsize=1)
def geojson_brasil() -> dict:
    return json.loads((Path(__file__).parent / "assets" / "brasil_estados.geojson").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def centros_estados() -> dict[str, tuple[float, float]]:
    """Centro aproximado (lat, lon) de cada UF, para marcadores no mapa."""
    def pontos(c):
        if isinstance(c[0], (int, float)):
            yield c
        else:
            for x in c:
                yield from pontos(x)
    out = {}
    for f in geojson_brasil()["features"]:
        p = list(pontos(f["geometry"]["coordinates"]))
        lons, lats = [x[0] for x in p], [x[1] for x in p]
        out[f["properties"]["sigla"]] = ((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)
    return out


@lru_cache(maxsize=1)
def contornos_estados() -> dict[str, tuple[list, list]]:
    """Contorno de cada UF (lon, lat) com anéis separados por None, simplificado para desenho leve."""
    out = {}
    for f in geojson_brasil()["features"]:
        g = f["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        xs, ys = [], []
        for poly in polys:
            ring = poly[0]
            passo = max(1, len(ring) // 250)
            ring = ring[::passo] + [ring[-1]]
            xs += [p[0] for p in ring] + [None]
            ys += [p[1] for p in ring] + [None]
        out[f["properties"]["sigla"]] = (xs, ys)
    return out
