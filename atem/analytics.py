"""Cálculos de KPIs, rankings, séries temporais e alertas."""
from __future__ import annotations

import pandas as pd

from .agrupamento import cid_pai, grupo_procedimento, nome_cid_pai
from .models import STATUS_DESISTENTE, TIPO_CONSULTA, TIPO_PROCEDIMENTO, Dataset


def filtrar_periodo(ds: Dataset, inicio=None, fim=None) -> pd.DataFrame:
    a = ds.atividades
    if a.empty:
        return a
    if inicio is not None:
        a = a[a["data"] >= pd.Timestamp(inicio)]
    if fim is not None:
        a = a[a["data"] < pd.Timestamp(fim) + pd.Timedelta(days=1)]
    return a


def kpis(ds: Dataset, inicio=None, fim=None) -> dict:
    a = filtrar_periodo(ds, inicio, fim)
    total = len(a)
    cons = int((a["tipo"] == TIPO_CONSULTA).sum())
    return {
        "total": total, "consultas": cons, "procedimentos": total - cons,
        "procedimentos_distintos": int(a["procedimento_nome"].fillna(a["procedimento"]).map(grupo_procedimento).nunique()) if total else 0,
        "dias_ativos": int(a["data"].dt.normalize().nunique()) if total else 0,
        "ultima_atividade": a["data"].max() if total else pd.NaT,
        "dificuldade_media": float(a["dificuldade"].mean()) if a["dificuldade"].notna().any() else None,
    }


def ranking(ds: Dataset, inicio=None, fim=None, por: str | None = None) -> pd.DataFrame:
    """Ranking de especialistas ativos (desistentes ficam de fora). `por` ('especialidade'/'mentor')
    gera a posição dentro de cada grupo."""
    esp = ds.ativos[["especialista_id", "nome", "especialidade", "mentor"]].copy()
    a = filtrar_periodo(ds, inicio, fim)
    cont = a.groupby("especialista_id").agg(
        atendimentos=("tipo", "size"),
        consultas=("tipo", lambda s: int((s == TIPO_CONSULTA).sum())),
        procedimentos=("tipo", lambda s: int((s == TIPO_PROCEDIMENTO).sum())),
    )
    r = esp.merge(cont, on="especialista_id", how="left")
    for c in ("atendimentos", "consultas", "procedimentos"):
        r[c] = r[c].fillna(0).astype(int)
    chave = r.groupby(por) if por else r
    r["posicao"] = (chave["atendimentos"].rank(method="min", ascending=False)).astype(int)
    sort = ([por] if por else []) + ["posicao", "nome"]
    return r.sort_values(sort).reset_index(drop=True)


def evolucao(ds: Dataset, freq: str = "M", inicio=None, fim=None, por_tipo: bool = True) -> pd.DataFrame:
    """Atendimentos por período ('M' mensal, 'W' semanal)."""
    a = filtrar_periodo(ds, inicio, fim).dropna(subset=["data"])
    if a.empty:
        return pd.DataFrame(columns=["periodo", "tipo", "atendimentos"])
    a = a.assign(periodo=a["data"].dt.to_period(freq).dt.start_time)
    cols = ["periodo", "tipo"] if por_tipo else ["periodo"]
    return a.groupby(cols).size().reset_index(name="atendimentos")


def top_procedimentos(ds: Dataset, n: int = 10, inicio=None, fim=None) -> pd.DataFrame:
    a = filtrar_periodo(ds, inicio, fim)
    a = a.assign(nome=a["procedimento_nome"].fillna(a["procedimento"]).map(grupo_procedimento))
    g = a.groupby("nome").agg(quantidade=("nome", "size"),
                              tipo=("tipo", lambda s: s.mode().iloc[0] if s.notna().any() else "Procedimento"))
    return g.sort_values("quantidade", ascending=False).head(n).reset_index()


def lista_procedimentos(ds: Dataset, inicio=None, fim=None) -> pd.DataFrame:
    """Todos os procedimentos do período (código, nome, tipo, quantidade), agrupados por código."""
    a = filtrar_periodo(ds, inicio, fim)
    cols = ["codigo", "procedimento", "tipo", "dificuldade", "quantidade"]
    if a.empty:
        return pd.DataFrame(columns=cols)
    nome = a["procedimento_nome"].fillna(a["procedimento"]).map(grupo_procedimento)
    a = a.assign(_nome=nome, _chave=nome.str.lower())
    g = a.groupby("_chave").agg(
        codigo=("procedimento", lambda s: ", ".join(sorted(s.dropna().astype(str).unique())[:3]) + ("…" if s.nunique() > 3 else "")),
        procedimento=("_nome", lambda s: s.mode().iloc[0]),
        tipo=("tipo", lambda s: s.mode().iloc[0] if s.notna().any() else "Procedimento"),
        dificuldade=("dificuldade_texto", lambda s: s.dropna().mode().iloc[0] if s.notna().any() else "—"),
        quantidade=("_nome", "size"))
    return g.sort_values(["quantidade", "procedimento"], ascending=[False, True]).reset_index(drop=True)[cols]


def top_cids(ds: Dataset, n: int = 10, inicio=None, fim=None) -> pd.DataFrame:
    a = filtrar_periodo(ds, inicio, fim).dropna(subset=["cid"])
    a = a.assign(cid_cod=a["cid"].map(cid_pai)).dropna(subset=["cid_cod"])
    g = a.groupby("cid_cod").agg(quantidade=("cid", "size"), subcodigos=("cid", "nunique"))
    g["descricao"] = [nome_cid_pai(c, a.loc[a["cid_cod"] == c, "cid_texto"]) for c in g.index]
    g.index.name = "cid"
    return g.sort_values("quantidade", ascending=False).head(n).reset_index()


def resumo_grupo(ds: Dataset, por: str, inicio=None, fim=None) -> pd.DataFrame:
    """Comparativo por especialidade/mentor: total, média por especialista."""
    r = ranking(ds, inicio, fim)
    g = r.groupby(por).agg(especialistas=("especialista_id", "size"), atendimentos=("atendimentos", "sum"),
                           consultas=("consultas", "sum"), procedimentos=("procedimentos", "sum"))
    g["media_por_especialista"] = (g["atendimentos"] / g["especialistas"]).round(1)
    return g.reset_index()


def mentorias_resumo(ds: Dataset) -> pd.DataFrame:
    return ds.mentorias.sort_values(["especialista_id", "mes_num"]) if not ds.mentorias.empty else ds.mentorias


def alertas_baixa_atividade(ds: Dataset, dias: int = 14, minimo: int = 1, ref=None) -> pd.DataFrame:
    """Ativos com menos de `minimo` atendimentos nos últimos `dias` (relativos a `ref`,
    por padrão a data do último registro da base)."""
    a = ds.atividades.dropna(subset=["data"])
    ref = pd.Timestamp(ref) if ref is not None else (a["data"].max() if not a.empty else pd.Timestamp.today())
    ini = ref.normalize() - pd.Timedelta(days=dias - 1)
    esp = ds.ativos[["especialista_id", "nome", "especialidade", "mentor"]].copy()
    rec = a[a["data"] >= ini].groupby("especialista_id").size().rename("atendimentos_recentes")
    ult = a.groupby("especialista_id")["data"].max().rename("ultima_atividade")
    r = esp.merge(rec, on="especialista_id", how="left").merge(ult, on="especialista_id", how="left")
    r["atendimentos_recentes"] = r["atendimentos_recentes"].fillna(0).astype(int)
    r["dias_sem_atividade"] = (ref.normalize() - r["ultima_atividade"].dt.normalize()).dt.days
    return r[r["atendimentos_recentes"] < minimo].sort_values(
        "dias_sem_atividade", ascending=False, na_position="first").reset_index(drop=True)


def desistentes(ds: Dataset) -> pd.DataFrame:
    return ds.especialistas[ds.especialistas["status"] == STATUS_DESISTENTE][
        ["nome", "especialidade", "mentor", "local_atuacao"]]


def localizacao_especialistas(ds: Dataset, inicio=None, fim=None) -> pd.DataFrame:
    """Especialistas ativos com UF, região, atendimentos no período e posição no ranking."""
    from .agrupamento import ESTADOS, regiao_da_uf, uf_do_especialista
    r = ranking(ds, inicio, fim)
    loc = ds.ativos[["especialista_id", "local_atuacao", "uf"]]
    r = r.merge(loc, on="especialista_id", how="left")
    r["sigla"] = [uf_do_especialista(u, l) for u, l in zip(r["uf"], r["local_atuacao"])]
    r["estado"] = r["sigla"].map(lambda s: ESTADOS[s][0] if s in ESTADOS else "Não informado")
    r["regiao"] = r["sigla"].map(regiao_da_uf)
    return r
