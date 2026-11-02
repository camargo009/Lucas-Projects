"""Autenticação (bcrypt) e autorização: especialista nunca acessa dados de outro."""
from __future__ import annotations

import csv
import json
import secrets
import string
from dataclasses import dataclass
from pathlib import Path

import bcrypt
import pandas as pd

from .analytics import ranking
from .models import Dataset

PERFIL_ESPECIALISTA = "especialista"
PERFIL_SUPERVISOR = "supervisor"

# Hash falso usado para igualar o tempo de resposta quando o e-mail não existe.
_HASH_FALSO = bcrypt.hashpw(b"x", bcrypt.gensalt())


@dataclass(frozen=True)
class Usuario:
    email: str
    nome: str
    perfil: str
    especialista_id: str | None = None

    @property
    def eh_supervisor(self) -> bool:
        return self.perfil == PERFIL_SUPERVISOR


def hash_senha(senha: str) -> str:
    return bcrypt.hashpw(senha.encode(), bcrypt.gensalt()).decode()


def gerar_senha(n: int = 10) -> str:
    alfabeto = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(n))


def carregar_usuarios(caminho: str | Path, usuarios_json: str | None = None) -> dict[str, dict]:
    """Os secrets têm prioridade; na nuvem não é necessário publicar arquivos de usuários."""
    if usuarios_json is not None:
        try:
            usuarios = json.loads(usuarios_json)
        except (ValueError, TypeError):
            raise ValueError("ATEM_USERS_JSON deve conter um objeto JSON de contas válido.") from None
        if not isinstance(usuarios, dict):
            raise ValueError("ATEM_USERS_JSON deve conter um objeto JSON de contas válido.")
        for email, reg in usuarios.items():
            if (not isinstance(email, str) or email != email.strip().lower() or "@" not in email
                    or not isinstance(reg, dict) or not isinstance(reg.get("nome"), str)
                    or reg.get("perfil") not in {PERFIL_ESPECIALISTA, PERFIL_SUPERVISOR}
                    or not isinstance(reg.get("hash"), str)
                    or (reg["perfil"] == PERFIL_ESPECIALISTA
                        and not isinstance(reg.get("especialista_id"), str))):
                raise ValueError("ATEM_USERS_JSON contém uma conta com campos inválidos.")
            try:
                bcrypt.checkpw(b"validation", reg["hash"].encode())
            except ValueError:
                raise ValueError("ATEM_USERS_JSON contém um hash bcrypt inválido.") from None
        return usuarios
    p = Path(caminho)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def autenticar(usuarios: dict[str, dict], email: str, senha: str) -> Usuario | None:
    email = (email or "").strip().lower()
    reg = usuarios.get(email)
    alvo = reg["hash"].encode() if reg else _HASH_FALSO
    ok = bcrypt.checkpw((senha or "").encode(), alvo)
    if not reg or not ok:
        return None
    return Usuario(email, reg["nome"], reg["perfil"], reg.get("especialista_id"))


def gerar_usuarios(ds: Dataset, supervisores: list[dict], admins: list[dict] | None = None,
                   existentes: dict[str, dict] | None = None) -> tuple[dict[str, dict], list[dict]]:
    """Cria usuários que ainda não existem. Retorna (usuarios, senhas_iniciais_geradas).

    supervisores/admins: [{"nome":..., "email":...}]. Especialistas vêm dos e-mails do Excel.
    """
    usuarios = dict(existentes or {})
    novas: list[dict] = []

    def add(email: str, nome: str, perfil: str, eid: str | None) -> None:
        email = email.strip().lower()
        if not email or email in usuarios:
            return
        senha = gerar_senha()
        usuarios[email] = {"nome": nome, "perfil": perfil, "especialista_id": eid, "hash": hash_senha(senha)}
        novas.append({"email": email, "nome": nome, "perfil": perfil, "senha": senha})

    for _, e in ds.especialistas.iterrows():
        if e["email"]:
            add(e["email"], e["nome"], PERFIL_ESPECIALISTA, e["especialista_id"])
    for s in [*supervisores, *(admins or [])]:
        add(s["email"], s["nome"], PERFIL_SUPERVISOR, None)
    return usuarios, novas


def carregar_supervisores_csv(caminho: str | Path) -> list[dict]:
    with open(caminho, encoding="utf-8-sig", newline="") as f:
        return [{"nome": r["nome"], "email": r["email"]} for r in csv.DictReader(f)]


# ---------------------------------------------------------------- autorização
def dados_visiveis(usuario: Usuario, ds: Dataset) -> Dataset:
    """Único ponto de acesso a dados para a interface: especialista só recebe os próprios."""
    if usuario.eh_supervisor:
        return ds
    if not usuario.especialista_id:
        return Dataset().only("__nenhum__")
    return ds.only(usuario.especialista_id)


def posicao_no_ranking(usuario: Usuario, ds: Dataset, inicio=None, fim=None) -> tuple[int, int] | None:
    """(posição, total) do especialista; não expõe dados de terceiros."""
    if usuario.eh_supervisor or not usuario.especialista_id:
        return None
    r = ranking(ds, inicio, fim)
    linha = r[r["especialista_id"] == usuario.especialista_id]
    if linha.empty:
        return None
    return int(linha.iloc[0]["posicao"]), len(r)
