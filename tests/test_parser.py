from datetime import datetime

import pytest
from openpyxl import Workbook

from atem.parser import parse_workbook


def _aba(wb, nome, meta, atividades, desalinhar=False, mentorias=None):
    ws = wb.create_sheet(nome)
    for i, (k, v) in enumerate(meta, 1):
        ws.cell(i, 1, k)
        ws.cell(i, 2, v)
    ws.cell(8, 1, "Visita presencial 1")
    ws.cell(8, 4, "Visita presencial 2")
    ws.cell(11, 1, "semana de imersão")
    ws.cell(11, 2, "10/08 a 14/08" if not nome.startswith("Desist") else "desistência")
    ws.cell(11, 4, "semana de imersão")
    ws.cell(14, 1, "Mentorias")
    for j, h in enumerate(["Propostas", "Participação", "Percentual"], 2):
        ws.cell(14, j, h)
    for i, m in enumerate(["Março", "Abril", "Novemrbo"], 15):
        ws.cell(i, 1, m)
    for i, (mes, p, q) in enumerate(mentorias or [], 15):
        ws.cell(i, 1, mes)
        ws.cell(i, 2, p)
        ws.cell(i, 3, q)
    ws.cell(26, 1, "Atividades")
    off = 1 if desalinhar else 0  # cabeçalho deslocado uma coluna à esquerda dos dados
    heads = ["CID", "CID (texto)", "Procedimento", "Procedimento (nome)", None, "Dificuldade",
             "Dificuldade (texto)", "Data"]
    for j, h in enumerate(heads, 1):
        if h:
            ws.cell(27, j, h)
    for i, row in enumerate(atividades, 28):
        for j, v in enumerate(row, 1 + off):
            ws.cell(i, j, v)


@pytest.fixture
def xlsx(tmp_path):
    wb = Workbook()
    wb.remove(wb.active)
    meta = [("Especialista", "Ana Teste"), ("Telefone:", "(11) 1"), ("Email:", "ANA@x.com"),
            ("Especialidade:", "Oncologia"), ("Mentor:", "Dr. M"), ("Local de atuação:", "Hosp")]
    _aba(wb, "Onco 1", meta, [
        ["C50", "Mama", 304100021.0, "Tratamento clinico", None, 3.0, "dificil", datetime(2026, 4, 11)],
        ["c61", None, "0301010072 - CONSULTA MEDICA", None, None, None, None, datetime(2026, 5, 4, 14, 0)],
        ["C16", None, "Consulta ambulatorial", None, None, None, None, "05/05/2026"],
        [None] * 8,
    ], mentorias=[("Abril", 4, 3)])
    _aba(wb, "Anest 1", [("Especialista", "Beto"), ("Email", "beto@x.com"), ("Mentor:", "Dr. N")],
         [["K80", None, "0407030034 - COLECISTECTOMIA", None, None, None, None, datetime(2026, 4, 9)]],
         desalinhar=True)
    _aba(wb, "Desistencia 1", meta[:1] + [("Email:", "d@x.com"), ("Especialidade:", "Oncologia")], [])
    p = tmp_path / "t.xlsx"
    wb.save(p)
    return p


def test_metadados_e_status(xlsx):
    ds = parse_workbook(xlsx)
    e = ds.especialistas.set_index("especialista_id")
    assert e.loc["onco-1", "nome"] == "Ana Teste"
    assert e.loc["onco-1", "email"] == "ana@x.com"
    assert e.loc["onco-1", "mentor"] == "Dr. M"
    assert e.loc["onco-1", "semana_imersao"] == "10/08 a 14/08"
    assert e.loc["desistencia-1", "status"] == "Desistente"
    assert e.loc["anest-1", "especialidade"] == "Anestesiologia"  # inferida da aba
    assert list(ds.ativos["especialista_id"]) == ["onco-1", "anest-1"]


def test_ods_preserva_todas_as_abas(xlsx, tmp_path):
    import pandas as pd

    ods = tmp_path / "acompanhamento.ods"
    with pd.ExcelWriter(ods, engine="odf") as writer:
        for name, df in pd.read_excel(xlsx, sheet_name=None, header=None).items():
            df.to_excel(writer, sheet_name=name, header=False, index=False)
    original, converted = parse_workbook(xlsx), parse_workbook(ods)
    pd.testing.assert_frame_equal(original.especialistas, converted.especialistas)
    pd.testing.assert_frame_equal(original.atividades, converted.atividades)
    pd.testing.assert_frame_equal(original.mentorias, converted.mentorias)


def test_atividades_e_tipos(xlsx):
    a = parse_workbook(xlsx).atividades
    o = a[a["especialista_id"] == "onco-1"]
    assert len(o) == 3  # linha vazia ignorada
    assert o["data"].notna().all()
    assert list(o["tipo"]) == ["Procedimento", "Consulta", "Consulta"]
    assert o.iloc[0]["procedimento"] == "0304100021"
    assert o.iloc[1]["procedimento_nome"] == "CONSULTA MEDICA"
    assert o.iloc[1]["cid"] == "C61"


def test_cabecalho_desalinhado(xlsx):
    a = parse_workbook(xlsx).atividades
    b = a[a["especialista_id"] == "anest-1"]
    assert len(b) == 1 and b.iloc[0]["data"] == datetime(2026, 4, 9)
    assert b.iloc[0]["cid"] == "K80"


def test_mentorias_e_meses_com_erro_de_digitacao(xlsx):
    m = parse_workbook(xlsx).mentorias
    assert len(m) == 1
    r = m.iloc[0]
    assert r["mes"] == "Abril" and r["propostas"] == 4 and r["percentual"] == 75


def test_aba_vazia_nao_quebra(tmp_path):
    wb = Workbook()
    wb.active.title = "Vazia"
    p = tmp_path / "v.xlsx"
    wb.save(p)
    ds = parse_workbook(p)
    assert ds.especialistas.empty and ds.atividades.empty
