from io import BytesIO
from pathlib import Path
from tempfile import gettempdir

import pandas as pd
import pytest
import requests

from atem.auth import Usuario, dados_visiveis
from atem.datasource import RedcapFilesSource, criar_fonte


@pytest.fixture
def uploads():
    attendance = BytesIO()
    with pd.ExcelWriter(attendance, engine="openpyxl") as writer:
        for sheet, name in [("Onco 1", "Ana Teste"), ("Anest 1", "Beto Teste")]:
            pd.DataFrame([
                ["Especialista", name, None, None],
                ["Email", f"{sheet.lower().replace(' ', '')}@example.org", None, None],
                ["Atividades", None, None, None],
                ["CID", "Procedimento", "Procedimento (nome)", "Data"],
                ["C50", "0301010072", "Consulta", "01/06/2026"],
            ]).to_excel(writer, sheet_name=sheet, header=False, index=False)
    course = BytesIO()
    with pd.ExcelWriter(course, engine="openpyxl") as writer:
        pd.DataFrame([
            ["2026.1 - Curso de Teste", None, None, None, None],
            [None, None, None, None, "Módulo: Base"],
            ["Nome", "CPF", "Endereço de e-mail", "Acesso ao curso", "Atividade 1"],
            ["ANA TESTE", "000", "onco1@example.org", "1 dia", "Concluído"],
        ]).to_excel(writer, sheet_name="L1 - 01.06", header=False, index=False)
    return attendance.getvalue(), course.getvalue()


class Reply:
    def __init__(self, value=None, content=b"", status=200):
        self.value, self.content, self.status_code = value, content, status
        self.headers = {}

    def json(self):
        return self.value


def source(uploads, records=None):
    calls = []
    records = records if records is not None else [
        {"record_id": "1", "atendimento_especialistas": "atendimentos.xlsx",
         "curso_especialistas": "curso_onco.xlsx"}
    ]

    def post(url, data, **kwargs):
        calls.append(data.copy())
        if data["content"] == "metadata":
            return Reply([
                {"field_name": "record_id", "field_type": "text", "form_name": "upload_docs"},
                *[{"field_name": f, "field_type": "file", "form_name": "upload_docs"}
                  for f in ("atendimento_especialistas", "curso_especialistas")],
            ])
        if data["content"] == "record":
            return Reply(records)
        return Reply(content=uploads[0 if data["field"] == "atendimento_especialistas" else 1])

    return RedcapFilesSource("https://redcap.example.org/api/", "test-only", post=post), calls


def test_download_todas_abas_curso_e_autorizacao(uploads):
    src, calls = source(uploads)
    before = set(Path(gettempdir()).glob("atem_redcap_*"))
    ds = src.load()
    assert set(ds.especialistas.especialista_id) == {"onco-1", "anest-1"}
    assert len(ds.atividades) == 2
    assert ds.curso_alunos.iloc[0].especialista_id == "onco-1"
    assert ds.curso_alunos.iloc[0].percentual == 100
    visible = dados_visiveis(Usuario("onco1@example.org", "Ana", "especialista", "onco-1"), ds)
    assert set(visible.atividades.especialista_id) == {"onco-1"}
    assert set(visible.curso_alunos.especialista_id) == {"onco-1"}
    assert set(Path(gettempdir()).glob("atem_redcap_*")) == before
    assert calls[-1]["action"] == "export"


def test_ultimo_id_numerico_sem_duplicar_historico(uploads):
    src, calls = source(uploads, [
        {"record_id": str(i), "atendimento_especialistas": "a.xlsx",
         "curso_especialistas": "curso_onco.xlsx"} for i in [10, 2, 1]
    ])
    ds = src.load()
    assert len(ds.atividades) == 2
    assert [c["record"] for c in calls if c["content"] == "file"] == ["10", "10"]
    src.load()
    assert len([c for c in calls if c["content"] == "record"]) == 2  # sem cache oculto


def test_curso_por_especialidade_e_contexto_repetido(uploads):
    src, calls = source(uploads, [
        {"record_id": "1", "atendimento_especialistas": "a.xlsx", "curso_especialistas": "curso_onco.xlsx"},
        {"record_id": "2", "atendimento_especialistas": "", "curso_especialistas": "curso_anest.xlsx",
         "redcap_event_name": "mes_arm_1", "redcap_repeat_instrument": "upload_docs",
         "redcap_repeat_instance": "2"},
    ])
    ds = src.load()
    assert set(ds.curso_alunos.curso) == {"Oncologia", "Anestesiologia"}
    assert calls[-1]["event"] == "mes_arm_1"
    assert calls[-1]["repeat_instance"] == "2"
    assert "mes" not in ds.especialistas.columns


@pytest.mark.parametrize("records,match", [
    ([], "Nenhuma planilha"),
    ([{"record_id": "1", "atendimento_especialistas": "a.xlsx", "curso_especialistas": ""}], "curso_especialistas"),
    ([{"record_id": "jan", "atendimento_especialistas": "a.xlsx"}], "numéricos"),
])
def test_upload_incompleto_ou_id_invalido(uploads, records, match):
    src, _ = source(uploads, records)
    with pytest.raises(RuntimeError, match=match):
        src.load()


def test_erro_exportacao_nao_parece_sucesso(uploads):
    src, _ = source((b'{"error":"File export denied"}', uploads[1]))
    with pytest.raises(RuntimeError, match="planilha válida"):
        src.load()


def test_download_invalido_limpa_temporarios(uploads):
    src, _ = source((uploads[0], b"denied"))
    before = set(Path(gettempdir()).glob("atem_redcap_*"))
    with pytest.raises(RuntimeError, match="planilha válida"):
        src.load()
    assert set(Path(gettempdir()).glob("atem_redcap_*")) == before


def test_erros_http_e_rede_sem_expor_token():
    src = RedcapFilesSource("https://redcap.example.org/api/", "test-secret",
                            post=lambda *a, **k: Reply(status=403))
    with pytest.raises(RuntimeError, match="HTTP 403") as exc:
        src.load()
    assert "test-secret" not in str(exc.value)

    def offline(*a, **k):
        raise requests.ConnectionError("test-secret")

    src._post = offline
    with pytest.raises(RuntimeError, match="conectar") as exc:
        src.load()
    assert "test-secret" not in str(exc.value)


def test_factory_e_https():
    config = {"DATA_SOURCE": "redcap_files", "REDCAP_URL": "https://redcap.example.org/api/",
              "REDCAP_TOKEN": "test-only"}
    assert isinstance(criar_fonte(lambda k, d=None: config.get(k, d)), RedcapFilesSource)
    with pytest.raises(ValueError, match="HTTPS"):
        RedcapFilesSource("http://redcap.example.org/api/", "test-only")


@pytest.mark.parametrize("media_type,label", [("text/html", "HTML"), ("application/json", "JSON"), ("", "outro")])
def test_diagnostico_recusa_sem_corpo_ou_token(media_type, label):
    reply = Reply(content=b"private response with secret", status=403)
    reply.headers["Content-Type"] = media_type
    src = RedcapFilesSource("https://redcap.example.org/api/", "private-token",
                            post=lambda *a, **k: reply)
    with pytest.raises(RuntimeError) as exc:
        src.load()
    message = str(exc.value)
    assert "exportar metadados" in message
    assert f"resposta: {label}" in message
    assert "private" not in message and "secret" not in message


@pytest.mark.parametrize("missing", [False, True])
def test_campos_separados_todas_abas_e_isolamento(uploads, missing):
    fields = {"curso_especialistas_onco": "Oncologia",
              "curso_especialistas_anestesio": "Anestesiologia"}
    calls = []
    anest = BytesIO()
    with pd.ExcelWriter(anest, engine="openpyxl") as writer:
        for date in ["01.06", "08.06"]:
            pd.DataFrame([
                ["2026.1 - Curso de Teste", None, None, None, None],
                [None, None, None, None, "Módulo: Base"],
                ["Nome", "CPF", "Endereço de e-mail", "Acesso ao curso", "Atividade 1"],
                ["BETO TESTE", "000", "anest1@example.org", "1 dia", "Concluído"],
            ]).to_excel(writer, sheet_name=f"L1 - {date}", header=False, index=False)

    def post(url, data, **kwargs):
        calls.append(data.copy())
        if data["content"] == "metadata":
            return Reply([
                {"field_name": "record_id", "field_type": "text", "form_name": "upload_docs"},
                *[{"field_name": f, "field_type": "file", "form_name": "upload_docs"}
                  for f in ["atendimento_especialistas", *fields]],
            ])
        if data["content"] == "record":
            return Reply([
                {"record_id": str(i), "atendimento_especialistas": "a.xlsx",
                 "curso_especialistas_onco": "monitoramento.xlsx",
                 "curso_especialistas_anestesio": "" if missing or i == 10 else "monitoramento.xlsx"}
                for i in [2, 10]
            ])
        return Reply(content=uploads[0] if data["field"] == "atendimento_especialistas"
                     else anest.getvalue() if data["field"].endswith("anestesio") else uploads[1])

    src = RedcapFilesSource("https://redcap.example.org/api/", "test-only",
                            course_fields=fields, post=post)
    if missing:
        with pytest.raises(RuntimeError, match="curso_especialistas_anestesio"):
            src.load()
        return
    ds = src.load()
    assert set(ds.curso_alunos.curso) == {"Oncologia", "Anestesiologia"}
    assert len(ds.curso_alunos) == 2
    assert len(ds.curso_evolucao) == 3
    assert [c["record"] for c in calls if c["content"] == "file"] == ["10", "10", "2"]
    for eid, course in [("onco-1", "Oncologia"), ("anest-1", "Anestesiologia")]:
        visible = dados_visiveis(Usuario("test@example.org", "Teste", "especialista", eid), ds)
        assert set(visible.curso_alunos.curso) == {course}
        assert set(visible.curso_atividades.especialista_id) == {eid}
        assert set(visible.curso_evolucao.especialista_id) == {eid}
