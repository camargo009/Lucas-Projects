import pandas as pd
import pytest

from atem import curso as cs
from atem.auth import Usuario, dados_visiveis
from atem.datasource import ExcelSource, records_to_curso
from atem.models import Dataset, COLS_ESPECIALISTAS, COLS_ATIVIDADES, COLS_MENTORIAS


def _aba(extra_ativ: bool) -> pd.DataFrame:
    n = 4 if extra_ativ else 3
    linhas = [
        ["2026.1 - Curso de Teste"] + [None] * (n + 2),
        [None, None, None, None, "Módulo: Base"] + [None] * (n - 1),
        ["Nome", "CPF", "Endereço de e-mail", "Acesso ao curso"] + [f"Ativ {i}" for i in range(1, n + 1)],
        ["ANA MARIA SOUZA", "000", "ana@x.com", "2 dias 3 horas"] + ["Concluído"] * n,
        ["JOAO PEDRO LIMA", "111", "joao@x.com", "Nunca"] + ["Não concluído"] * n,
        ["FULANO SEM VINCULO", "222", "fulano@x.com", "\t10 dias 0 horas"] + ["Concluído"] + ["Não concluído"] * (n - 1),
        [None] * (n + 4),
        ["ENCAMINHAMENTOS", None, None, None] + [None] * n,
    ]
    return pd.DataFrame(linhas)


@pytest.fixture
def xlsx_curso(tmp_path):
    caminho = tmp_path / "curso_onco.xlsx"
    with pd.ExcelWriter(caminho) as w:
        _aba(False).to_excel(w, sheet_name="L1 - 01.06", header=False, index=False)
        _aba(True).to_excel(w, sheet_name="L2 - 08.06", header=False, index=False)
        pd.DataFrame([["Nome", "CPF"], ["ANA", "999"]]).to_excel(w, sheet_name="BASE", header=False, index=False)
    return caminho


@pytest.fixture
def especialistas():
    return pd.DataFrame([
        {"especialista_id": "onco-1", "nome": "Ana Maria Souza", "email": "ana@x.com", "status": "Ativo"},
        {"especialista_id": "onco-2", "nome": "Joao Pedro Lima", "email": "outro@x.com", "status": "Ativo"},
    ]).reindex(columns=COLS_ESPECIALISTAS)


def test_parse_acesso():
    assert cs.parse_acesso("Nunca")[1] is True
    dias, nunca = cs.parse_acesso("\t2 dias 12 horas")
    assert nunca is False and dias == pytest.approx(2.5)


def test_parser_ignora_base_e_dados_pessoais(xlsx_curso):
    linhas = cs.ler_planilha_curso(xlsx_curso)
    assert set(linhas["rotulo"]) == {"L1", "L2"}
    assert "cpf" not in [c.lower() for c in linhas.columns]
    assert linhas["curso"].iloc[0] == "Oncologia"


def test_vinculo_por_email_nome_e_sem_vinculo(xlsx_curso, especialistas):
    alunos, atv, evo = cs.carregar_cursos([xlsx_curso], especialistas)
    por_nome = alunos.set_index("nome")["especialista_id"]
    assert por_nome["ANA MARIA SOUZA"] == "onco-1"
    assert por_nome["JOAO PEDRO LIMA"] == "onco-2"        # vínculo pelo nome
    assert pd.isna(por_nome["FULANO SEM VINCULO"])
    ana = alunos[alunos["nome"] == "ANA MARIA SOUZA"].iloc[0]
    assert ana["concluidas"] == 4 and ana["total"] == 4 and ana["situacao"] == cs.SITUACAO_CONCLUIDO
    assert alunos[alunos["nome"] == "JOAO PEDRO LIMA"].iloc[0]["situacao"] == cs.SITUACAO_NUNCA
    assert evo["rotulo"].nunique() == 2


def test_especialista_nao_ve_curso_de_outro(xlsx_curso, especialistas):
    alunos, atv, evo = cs.carregar_cursos([xlsx_curso], especialistas)
    ds = Dataset(especialistas, pd.DataFrame(columns=COLS_ATIVIDADES), pd.DataFrame(columns=COLS_MENTORIAS),
                 alunos, atv, evo)
    vis = dados_visiveis(Usuario("ana@x.com", "Ana", "especialista", "onco-1"), ds)
    assert set(vis.curso_alunos["especialista_id"]) == {"onco-1"}
    assert set(vis.curso_atividades["especialista_id"]) == {"onco-1"}
    assert set(vis.curso_evolucao["especialista_id"]) == {"onco-1"}
    sup = dados_visiveis(Usuario("m@x", "Mentor", "supervisor"), ds)
    assert len(sup.curso_alunos) == 3


def test_redcap_registros_do_curso():
    registros = [
        {"curso_nome": "ANA", "curso_atividade": "A1", "curso_concluido": "Concluído", "curso_data": "2026-06-01",
         "curso_curso": "Oncologia", "curso_modulo": "M1", "curso_acesso": "1 dia 2 horas"},
        {"curso_nome": "", "curso_atividade": "A2", "curso_data": "2026-06-01"},
    ]
    df = records_to_curso(registros)
    assert len(df) == 1 and bool(df["concluido"].iloc[0]) is True


def test_excel_source_sem_cursos(tmp_path):
    with pytest.raises(FileNotFoundError):
        ExcelSource(tmp_path / "nao_existe.xlsx").load()
