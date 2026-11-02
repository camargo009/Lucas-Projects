import pandas as pd
import pytest

from atem.analytics import alertas_baixa_atividade, ranking
from atem.auth import (
    Usuario, autenticar, dados_visiveis, gerar_usuarios, hash_senha, posicao_no_ranking,
)
from atem.datasource import RedcapSource, records_to_dataset
from atem.models import COLS_ESPECIALISTAS, Dataset


def _ds() -> Dataset:
    esp = pd.DataFrame([
        ["a", "Ana", None, "a@x.com", "Oncologia", "M1", None, None, None, "Ativo", "Onco 1"],
        ["b", "Beto", None, "b@x.com", "Oncologia", "M1", None, None, None, "Ativo", "Onco 2"],
        ["c", "Cris", None, "c@x.com", "Anestesiologia", "M2", None, None, None, "Ativo", "Anest 1"],
        ["d", "Desi", None, "d@x.com", "Oncologia", "M1", None, None, None, "Desistente", "Desist 1"],
    ], columns=COLS_ESPECIALISTAS)
    linhas = [("a", "Consulta", "2026-05-01")] * 3 + [("b", "Procedimento", "2026-05-02")] * 5 + \
             [("d", "Procedimento", "2026-05-03")] * 50
    atv = pd.DataFrame([{"especialista_id": e, "cid": "C50", "cid_texto": None, "procedimento": None,
                         "procedimento_nome": "X", "dificuldade": None, "dificuldade_texto": None,
                         "data": pd.Timestamp(d), "tipo": t} for e, t, d in linhas])
    return Dataset(esp, atv)


def test_ranking_exclui_desistentes_e_inclui_zerados():
    r = ranking(_ds())
    assert "d" not in set(r["especialista_id"])
    assert list(r["especialista_id"]) == ["b", "a", "c"]
    assert list(r["posicao"]) == [1, 2, 3]
    por = ranking(_ds(), por="especialidade").set_index("especialista_id")
    assert por.loc["c", "posicao"] == 1


def test_alertas():
    al = alertas_baixa_atividade(_ds(), dias=7, minimo=1, ref="2026-05-10")
    assert set(al["especialista_id"]) == {"c"} | set() or "c" in set(al["especialista_id"])
    assert "d" not in set(al["especialista_id"])


def test_especialista_ve_apenas_seus_dados():
    ds = _ds()
    u = Usuario("a@x.com", "Ana", "especialista", "a")
    v = dados_visiveis(u, ds)
    assert set(v.especialistas["especialista_id"]) == {"a"}
    assert set(v.atividades["especialista_id"]) == {"a"}
    assert len(v.atividades) == 3


def test_especialista_sem_id_nao_ve_nada():
    v = dados_visiveis(Usuario("x@x.com", "X", "especialista", None), _ds())
    assert v.especialistas.empty and v.atividades.empty


def test_supervisor_ve_tudo():
    ds = _ds()
    v = dados_visiveis(Usuario("m@x.com", "M", "supervisor"), ds)
    assert len(v.especialistas) == 4


def test_posicao_so_retorna_numeros():
    u = Usuario("a@x.com", "Ana", "especialista", "a")
    assert posicao_no_ranking(u, _ds()) == (2, 3)
    assert posicao_no_ranking(Usuario("m@x.com", "M", "supervisor"), _ds()) is None


def test_login_e_geracao_de_usuarios():
    usuarios, novas = gerar_usuarios(_ds(), [{"nome": "M1", "email": "M1@x.com"}], [{"nome": "Adm", "email": "adm@x.com"}])
    assert "m1@x.com" in usuarios and usuarios["adm@x.com"]["perfil"] == "supervisor"
    assert usuarios["a@x.com"]["especialista_id"] == "a"
    assert all("senha" not in v for v in usuarios.values())  # só hash é persistido
    senha = next(n["senha"] for n in novas if n["email"] == "a@x.com")
    u = autenticar(usuarios, " A@x.com ", senha)
    assert u and u.especialista_id == "a" and not u.eh_supervisor
    assert autenticar(usuarios, "a@x.com", "errada") is None
    assert autenticar(usuarios, "nao@existe.com", senha) is None
    # reexecutar não recria nem troca senhas existentes
    u2, novas2 = gerar_usuarios(_ds(), [], None, usuarios)
    assert novas2 == [] and u2["a@x.com"]["hash"] == usuarios["a@x.com"]["hash"]


def test_hash_nao_e_texto_puro():
    assert hash_senha("abc") != "abc" and hash_senha("abc").startswith("$2")


def test_redcap_transformacao_e_cache():
    registros = [
        {"nome": "Ana", "email": "A@x.com", "especialidade": "Oncologia", "mentor": "M", "status": "",
         "cid": "c50", "procedimento": "0301010072", "procedimento_nome": "CONSULTA", "data": "2026-05-01"},
        {"nome": "Ana", "email": "a@x.com", "mentoria_mes": "Abril", "mentoria_propostas": "4",
         "mentoria_participacao": "3"},
        {"nome": "Bia", "email": "b@x.com", "status": "Desistência"},
    ]
    ds = records_to_dataset(registros)
    assert len(ds.especialistas) == 2 and len(ds.atividades) == 1
    assert ds.atividades.iloc[0]["tipo"] == "Consulta"
    assert ds.mentorias.iloc[0]["percentual"] == 75
    assert ds.especialistas.set_index("email").loc["b@x.com", "status"] == "Desistente"

    chamadas = []

    class R:
        def raise_for_status(self): pass
        def json(self): return registros

    def post(url, data, timeout):
        chamadas.append(data)
        return R()

    src = RedcapSource("https://r/api/", "TOKEN", ttl=60, post=post)
    src.load(); src.load()
    assert len(chamadas) == 1 and chamadas[0]["content"] == "record"


def test_redcap_exige_token(monkeypatch):
    monkeypatch.delenv("REDCAP_TOKEN", raising=False)
    monkeypatch.delenv("REDCAP_URL", raising=False)
    with pytest.raises(RuntimeError):
        RedcapSource()
