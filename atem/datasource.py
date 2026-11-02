"""Camada de dados abstrata: ExcelSource (local) e RedcapSource (API Export Records)."""
from __future__ import annotations

import json
import os
import time
from email.message import Message
from abc import ABC, abstractmethod
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from urllib.parse import urlparse

import pandas as pd

from .curso import COLS_LINHAS, carregar_cursos, ler_planilha_curso, montar_curso, nome_do_curso
from .models import (
    COLS_ATIVIDADES, COLS_ESPECIALISTAS, COLS_MENTORIAS, STATUS_ATIVO,
    STATUS_DESISTENTE, Dataset,
)
from .parser import mes_numero, norm, parse_data, parse_numero, parse_workbook, slug, _tipo, NOMES_MESES


class DataSource(ABC):
    @abstractmethod
    def load(self) -> Dataset:
        """Carrega os dados atuais da fonte."""


class ExcelSource(DataSource):
    def __init__(self, path: str | Path, curso_paths: list[str | Path] | None = None):
        self.path = Path(path)
        self.curso_paths = list(curso_paths) if curso_paths is not None else sorted(self.path.parent.glob("curso_*.xlsx"))

    def load(self) -> Dataset:
        if not self.path.exists():
            raise FileNotFoundError(f"Arquivo Excel não encontrado: {self.path}")
        ds = parse_workbook(self.path)
        ds.curso_alunos, ds.curso_atividades, ds.curso_evolucao = carregar_cursos(self.curso_paths, ds.especialistas)
        return ds


# Nomes padrão dos campos no REDCap; sobrescreva com REDCAP_FIELD_MAP (JSON {padrão: nome_real}).
CAMPOS_REDCAP_PADRAO = {
    "nome": "nome", "telefone": "telefone", "email": "email", "especialidade": "especialidade",
    "mentor": "mentor", "local_atuacao": "local_atuacao", "uf": "uf", "semana_imersao": "semana_imersao",
    "status": "status", "cid": "cid", "cid_texto": "cid_texto", "procedimento": "procedimento",
    "procedimento_nome": "procedimento_nome", "dificuldade": "dificuldade",
    "dificuldade_texto": "dificuldade_texto", "data": "data", "mentoria_mes": "mentoria_mes",
    "mentoria_propostas": "mentoria_propostas", "mentoria_participacao": "mentoria_participacao",
}


def records_to_dataset(records: list[dict], campos: dict[str, str] | None = None) -> Dataset:
    """Converte registros planos do REDCap (um por atividade/mentoria, agrupados por e-mail)."""
    c = {**CAMPOS_REDCAP_PADRAO, **(campos or {})}

    def g(r: dict, k: str) -> Any:
        v = r.get(c[k])
        return None if v is None or str(v).strip() == "" else v

    esps: dict[str, dict] = {}
    atvs, ments = [], []
    for r in records:
        email = (g(r, "email") or "").strip().lower()
        nome = g(r, "nome")
        chave = email or (slug(nome) if nome else "")
        if not chave:
            continue
        eid = slug(chave)
        if eid not in esps:
            status = str(g(r, "status") or "")
            esps[eid] = {
                "especialista_id": eid, "nome": nome or chave, "telefone": g(r, "telefone"),
                "email": email or None, "especialidade": g(r, "especialidade"),
                "mentor": g(r, "mentor"), "local_atuacao": g(r, "local_atuacao"), "uf": g(r, "uf"),
                "semana_imersao": g(r, "semana_imersao"),
                "status": STATUS_DESISTENTE if "desist" in norm(status) else STATUS_ATIVO,
                "aba": None,
            }
        data = parse_data(g(r, "data"))
        if not pd.isna(data) or g(r, "cid") or g(r, "procedimento"):
            cod, nm = g(r, "procedimento"), g(r, "procedimento_nome")
            cod = str(cod).strip() if cod else None
            atvs.append({
                "especialista_id": eid, "cid": (str(g(r, "cid")).upper() if g(r, "cid") else None),
                "cid_texto": g(r, "cid_texto"), "procedimento": cod, "procedimento_nome": nm,
                "dificuldade": parse_numero(g(r, "dificuldade")),
                "dificuldade_texto": g(r, "dificuldade_texto"), "data": data, "tipo": _tipo(cod, nm),
            })
        num = mes_numero(g(r, "mentoria_mes"))
        if num:
            prop, part = parse_numero(g(r, "mentoria_propostas")), parse_numero(g(r, "mentoria_participacao"))
            ments.append({
                "especialista_id": eid, "mes_num": num, "mes": NOMES_MESES[num - 1],
                "propostas": prop, "participacao": part,
                "percentual": (part or 0) / prop * 100 if prop else None,
            })
    atv = pd.DataFrame(atvs, columns=COLS_ATIVIDADES)
    atv["data"] = pd.to_datetime(atv["data"], errors="coerce")
    esp_df = pd.DataFrame(list(esps.values()), columns=COLS_ESPECIALISTAS)
    alunos, curso_atv, evo = montar_curso(records_to_curso(records, campos), esp_df)
    return Dataset(esp_df, atv, pd.DataFrame(ments, columns=COLS_MENTORIAS), alunos, curso_atv, evo)


# Campos do curso no REDCap (um registro por aluno × atividade × fotografia); sobrescreva via REDCAP_FIELD_MAP.
CAMPOS_CURSO_PADRAO = {
    "curso_nome": "curso_nome", "curso_email": "curso_email", "curso_curso": "curso_curso",
    "curso_modulo": "curso_modulo", "curso_atividade": "curso_atividade",
    "curso_concluido": "curso_concluido", "curso_acesso": "curso_acesso",
    "curso_data": "curso_data", "curso_rotulo": "curso_rotulo",
}


def records_to_curso(records: list[dict], campos: dict[str, str] | None = None) -> pd.DataFrame:
    """Converte registros do REDCap em linhas aluno × atividade × fotografia do curso."""
    c = {**CAMPOS_CURSO_PADRAO, **(campos or {})}
    linhas = []
    for r in records:
        nome, atividade = str(r.get(c["curso_nome"]) or "").strip(), str(r.get(c["curso_atividade"]) or "").strip()
        data = parse_data(r.get(c["curso_data"]))
        if not nome or not atividade or pd.isna(data):
            continue
        email = str(r.get(c["curso_email"]) or "").strip().lower() or None
        linhas.append({
            "nome": nome, "email": email, "curso": str(r.get(c["curso_curso"]) or "Curso").strip(),
            "data": data, "rotulo": str(r.get(c["curso_rotulo"]) or data.strftime("%d/%m")),
            "acesso": str(r.get(c["curso_acesso"]) or ""), "modulo": str(r.get(c["curso_modulo"]) or "Geral"),
            "ordem": len(linhas), "atividade": atividade,
            "concluido": norm(r.get(c["curso_concluido"])) in {"concluido", "sim", "yes", "true", "1", "checked"},
        })
    return pd.DataFrame(linhas, columns=COLS_LINHAS)


class RedcapSource(DataSource):
    """Lê via API 'Export Records'. O token vem de variável de ambiente/secrets, nunca do código."""

    def __init__(self, url: str | None = None, token: str | None = None, ttl: int = 60,
                 campos: dict[str, str] | None = None,
                 post: Callable[..., Any] | None = None):
        self.url = url or os.environ.get("REDCAP_URL", "")
        self.token = token or os.environ.get("REDCAP_TOKEN", "")
        if not self.url or not self.token:
            raise RuntimeError("Defina REDCAP_URL e REDCAP_TOKEN (variáveis de ambiente ou secrets).")
        if campos is None and os.environ.get("REDCAP_FIELD_MAP"):
            campos = json.loads(os.environ["REDCAP_FIELD_MAP"])
        self.campos = campos
        self.ttl = ttl
        self._post = post
        self._cache: tuple[float, Dataset] | None = None

    def _export(self) -> list[dict]:
        import requests

        post = self._post or requests.post
        resp = post(self.url, data={
            "token": self.token, "content": "record", "format": "json", "type": "flat",
            "rawOrLabel": "label", "returnFormat": "json",
        }, timeout=60)
        resp.raise_for_status()
        return resp.json()

    def load(self) -> Dataset:
        agora = time.monotonic()
        if self._cache and agora - self._cache[0] < self.ttl:
            return self._cache[1]
        ds = records_to_dataset(self._export(), self.campos)
        self._cache = (agora, ds)
        return ds


class RedcapFilesSource(DataSource):
    """Exporta anexos do formulário de uploads; arquivos temporários são removidos após a leitura."""

    def __init__(self, url: str, token: str, form: str = "upload_docs",
                 attendance_field: str = "atendimento_especialistas",
                 course_field: str = "curso_especialistas",
                 post: Callable[..., Any] | None = None,
                 course_fields: dict[str, str] | None = None):
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("REDCAP_URL deve ser uma URL HTTPS válida, sem credenciais.")
        if not token:
            raise ValueError("Defina REDCAP_TOKEN nos secrets ou no ambiente.")
        self.url, self.token = url, token
        self.form, self.attendance_field, self.course_field = form, attendance_field, course_field
        self.course_fields = course_fields
        self._post = post

    def _request(self, content: str, **params):
        import requests

        try:
            response = (self._post or requests.post)(
                self.url, data={"token": self.token, "content": content,
                                "returnFormat": "json", **params},
                timeout=60, allow_redirects=False)
        except requests.RequestException:
            raise RuntimeError("Não foi possível conectar ao REDCap. Verifique a rede e a URL da API.") from None
        if response.status_code != 200:
            operation = {"metadata": "metadados", "record": "registros", "file": "arquivos"}.get(content, "dados")
            media_type = response.headers.get("Content-Type", "").lower()
            response_format = ("HTML" if "text/html" in media_type else
                               "JSON" if "json" in media_type else "outro")
            raise RuntimeError(f"O REDCap recusou a consulta (HTTP {response.status_code}). "
                               f"Operação: exportar {operation}; formato da resposta: {response_format}. "
                               "Verifique a URL, o token e as permissões de exportação. "
                               "Se o mesmo acesso funciona localmente, peça à TI para verificar "
                               "restrições de rede ou firewall para a hospedagem.")
        return response

    def _json(self, content: str, **params) -> list[dict]:
        response = self._request(content, format="json", **params)
        try:
            result = response.json()
        except ValueError:
            raise RuntimeError("Resposta inválida do REDCap: era esperado JSON.") from None
        if not isinstance(result, list) or not all(isinstance(row, dict) for row in result):
            raise RuntimeError("O REDCap não retornou os registros esperados. "
                               "Verifique as permissões da API.")
        return result

    def _download(self, row: dict, record_field: str, field: str, folder: Path) -> Path:
        params = {"action": "export", "record": str(row[record_field]), "field": field}
        if row.get("redcap_event_name"):
            params["event"] = row["redcap_event_name"]
        if row.get("redcap_repeat_instance"):
            params["repeat_instance"] = str(row["redcap_repeat_instance"])
        response = self._request("file", **params)
        disposition = Message()
        disposition["Content-Disposition"] = response.headers.get("Content-Disposition", "")
        filename = disposition.get_filename() or str(row[field])
        filename = filename.replace("\\", "/").rsplit("/", 1)[-1]
        if Path(filename).suffix.lower() not in {".xlsx", ".xlsm", ".ods"}:
            raise RuntimeError(f"O campo {field} deve conter uma planilha XLSX, XLSM ou ODS.")
        if not response.content.startswith(b"PK"):
            raise RuntimeError(f"O REDCap não retornou uma planilha válida para o campo {field}. "
                               "Verifique a permissão de exportação de arquivos.")
        folder.mkdir()
        path = folder / filename
        path.write_bytes(response.content)
        return path

    def load(self) -> Dataset:
        metadata = self._json("metadata")
        if not metadata or not metadata[0].get("field_name"):
            raise RuntimeError("O projeto REDCap não possui um identificador de registro válido.")
        record_field = metadata[0]["field_name"]
        fields = {m["field_name"]: m for m in metadata}
        course_fields = self.course_fields or {self.course_field: None}
        for field in (self.attendance_field, *course_fields):
            if field not in fields or fields[field].get("field_type") != "file" or fields[field].get("form_name") != self.form:
                raise RuntimeError(f"O campo de upload {field} não foi encontrado no formulário {self.form}.")
        records = self._json("record", type="flat", rawOrLabel="raw", **{"forms[0]": self.form})
        records = [r for r in records if r.get("redcap_repeat_instrument", "") in ("", self.form)]
        if any(not str(r.get(record_field, "")).isdigit() for r in records):
            raise RuntimeError("Os IDs do formulário de uploads devem ser numéricos e crescentes.")
        records.sort(key=lambda r: (int(r[record_field]), int(r.get("redcap_repeat_instance") or 0)))
        attendance = [r for r in records if r.get(self.attendance_field)]
        if not attendance:
            raise RuntimeError(f"Nenhuma planilha disponível em {self.attendance_field}.")
        latest_courses = {}
        for field, course in course_fields.items():
            uploads = [r for r in records if r.get(field)]
            if not uploads:
                raise RuntimeError(f"Nenhuma planilha disponível em {field}.")
            for row in uploads:
                latest_courses[course or nome_do_curso(str(row[field]))] = (field, row)
        # Cada acompanhamento é uma fotografia completa, não um lote a somar.
        with TemporaryDirectory(prefix="atem_redcap_") as tmp:
            root = Path(tmp)
            path = self._download(attendance[-1], record_field, self.attendance_field, root / "atendimentos")
            ds = parse_workbook(path)
            if ds.especialistas.empty:
                raise RuntimeError("A planilha de atendimentos não contém abas de especialistas reconhecidas.")
            # Mantém o arquivo mais recente de cada curso, inclusive em uploads repetidos.
            parts = []
            for i, (course, (field, row)) in enumerate(latest_courses.items()):
                path = self._download(row, record_field, field, root / f"curso_{i}")
                lines = ler_planilha_curso(path, curso=course)
                if lines.empty:
                    raise RuntimeError(f"A planilha em {field} não contém dados de monitoramento reconhecidos.")
                parts.append(lines)
            ds.curso_alunos, ds.curso_atividades, ds.curso_evolucao = montar_curso(
                pd.concat(parts, ignore_index=True), ds.especialistas)
            return ds


def criar_fonte(get: Callable[[str, str | None], str | None]) -> DataSource:
    """Escolhe a fonte via configuração (DATA_SOURCE=excel|redcap|redcap_files)."""
    tipo = (get("DATA_SOURCE", "excel") or "excel").lower()
    if tipo == "redcap_files":
        course_fields_json = get("REDCAP_COURSE_FIELDS", None)
        course_fields = json.loads(course_fields_json) if course_fields_json else None
        if course_fields is not None and (
            not isinstance(course_fields, dict) or not course_fields
            or not all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
                       for k, v in course_fields.items())
            or len(set(course_fields.values())) != len(course_fields)
        ):
            raise ValueError("REDCAP_COURSE_FIELDS deve mapear campos de upload para nomes únicos de cursos.")
        return RedcapFilesSource(
            get("REDCAP_URL", "") or "", get("REDCAP_TOKEN", "") or "",
            form=get("REDCAP_UPLOAD_FORM", "upload_docs") or "upload_docs",
            attendance_field=get("REDCAP_ATTENDANCE_FIELD", "atendimento_especialistas") or "atendimento_especialistas",
            course_field=get("REDCAP_COURSE_FIELD", "curso_especialistas") or "curso_especialistas",
            course_fields=course_fields)
    if tipo == "redcap":
        return RedcapSource(get("REDCAP_URL", None), get("REDCAP_TOKEN", None),
                            ttl=int(get("REDCAP_CACHE_TTL", "60") or 60))
    caminho = get("EXCEL_PATH", "data/acompanhamento.xlsx") or "data/acompanhamento.xlsx"
    cursos = [p.strip() for p in (get("CURSO_PATHS", None) or "").split(",") if p.strip()] or None
    return ExcelSource(caminho, cursos)
