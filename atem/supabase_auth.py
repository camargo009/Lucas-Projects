"""Autenticação Supabase sem chave administrativa ou estado compartilhado entre usuários."""
from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Any, Callable
from urllib.parse import urlparse

import requests

from .auth import PERFIL_ESPECIALISTA, PERFIL_SUPERVISOR, Usuario


class AuthError(RuntimeError):
    """Falha de autenticação ou configuração, com mensagem segura para a interface."""


class SessionExpired(AuthError):
    """A sessão não é mais válida e deve ser removida."""


@dataclass(frozen=True)
class AuthSession:
    user_id: str
    access_token: str = field(repr=False)
    refresh_token: str = field(repr=False)
    expires_at: float
    usuario: Usuario


class SupabaseAuth:
    def __init__(self, url: str, key: str, request: Callable[..., Any] | None = None):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment or not key):
            raise AuthError("Configure SUPABASE_URL e SUPABASE_PUBLISHABLE_KEY nos secrets.")
        if key.startswith("sb_secret_"):
            raise AuthError("Use a chave publicável do Supabase, não uma chave secreta.")
        self.url, self.key = url.rstrip("/"), key
        self._request = request or requests.request

    def _call(self, method: str, path: str, *, token: str | None = None,
              payload: dict | None = None, params: dict | None = None):
        headers = {"apikey": self.key}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            response = self._request(method, self.url + path, headers=headers,
                                     json=payload, params=params, timeout=30, allow_redirects=False)
        except requests.RequestException:
            raise AuthError("Não foi possível conectar ao serviço de login. Tente novamente.") from None
        if response.status_code == 429:
            raise AuthError("Muitas tentativas. Aguarde alguns minutos antes de tentar novamente.")
        if response.status_code in (401, 403) and token:
            raise SessionExpired("Sua sessão expirou ou o acesso foi revogado. Entre novamente.")
        if response.status_code == 404 and path.startswith("/rest/"):
            raise AuthError("O cadastro de permissões ainda não foi configurado no Supabase.")
        if not 200 <= response.status_code < 300:
            if response.status_code in (400, 401, 403, 422):
                raise AuthError("Não foi possível validar o acesso. Confira os dados e a confirmação do e-mail.")
            raise AuthError("O serviço de login está indisponível. Tente novamente mais tarde.")
        if response.status_code == 204 or not response.content:
            return {}
        try:
            return response.json()
        except ValueError:
            raise AuthError("O serviço de login retornou uma resposta inválida.") from None

    def _identity(self, token: str) -> dict:
        identity = self._call("GET", "/auth/v1/user", token=token)
        if not isinstance(identity, dict) or not identity.get("id") or not identity.get("email"):
            raise SessionExpired("Sessão inválida. Entre novamente.")
        return identity

    def _profile(self, token: str, identity: dict) -> Usuario:
        rows = self._call("GET", "/rest/v1/atem_perfis", token=token, params={
            "select": "id,nome,perfil,especialista_id,ativo", "id": f"eq.{identity['id']}", "limit": "1",
        })
        if not isinstance(rows, list) or not rows:
            raise SessionExpired("Sua conta ainda não tem acesso autorizado. Fale com a coordenação.")
        p = rows[0]
        if (not isinstance(p, dict) or p.get("id") != identity["id"] or p.get("ativo") is not True
                or p.get("perfil") not in {PERFIL_ESPECIALISTA, PERFIL_SUPERVISOR}
                or not isinstance(p.get("nome"), str) or not p["nome"].strip()
                or (p["perfil"] == PERFIL_ESPECIALISTA
                    and (not isinstance(p.get("especialista_id"), str) or not p["especialista_id"].strip()))):
            raise SessionExpired("Seu perfil está inativo ou incompleto. Fale com a coordenação.")
        return Usuario(identity["email"].strip().lower(), p["nome"], p["perfil"], p.get("especialista_id"))

    def _session(self, data: dict) -> AuthSession:
        if (not isinstance(data, dict) or not isinstance(data.get("access_token"), str)
                or not data["access_token"] or not isinstance(data.get("refresh_token"), str)
                or not data["refresh_token"] or not isinstance(data.get("expires_in"), (int, float))
                or data["expires_in"] <= 0):
            raise AuthError("O serviço de login não retornou uma sessão válida.")
        identity = self._identity(data["access_token"])
        usuario = self._profile(data["access_token"], identity)
        return AuthSession(identity["id"], data["access_token"], data["refresh_token"],
                           time.time() + data["expires_in"], usuario)

    def sign_in(self, email: str, password: str) -> AuthSession:
        if not email.strip() or not password:
            raise AuthError("Preencha o e-mail e a senha.")
        return self._session(self._call("POST", "/auth/v1/token",
                                       params={"grant_type": "password"},
                                       payload={"email": email.strip().lower(), "password": password}))

    def validate(self, session: AuthSession) -> AuthSession:
        if not isinstance(session, AuthSession):
            raise SessionExpired("Entre novamente para continuar.")
        if session.expires_at <= time.time() + 60:
            refreshed = self._session(self._call("POST", "/auth/v1/token",
                                                params={"grant_type": "refresh_token"},
                                                payload={"refresh_token": session.refresh_token}))
            if refreshed.user_id != session.user_id:
                raise SessionExpired("Sessão inválida. Entre novamente.")
            return refreshed
        identity = self._identity(session.access_token)
        if identity["id"] != session.user_id:
            raise SessionExpired("Sessão inválida. Entre novamente.")
        return replace(session, usuario=self._profile(session.access_token, identity))

    def sign_out(self, session: AuthSession) -> None:
        self._call("POST", "/auth/v1/logout", token=session.access_token, params={"scope": "local"})

    def request_password_reset(self, email: str) -> None:
        if not email.strip() or "@" not in email:
            raise AuthError("Informe um e-mail válido.")
        self._call("POST", "/auth/v1/recover", payload={"email": email.strip().lower()})

    def reset_password(self, email: str, code: str, password: str) -> None:
        if len(password) < 12:
            raise AuthError("Use uma senha com pelo menos 12 caracteres.")
        if not email.strip() or not code.strip():
            raise AuthError("Informe o e-mail e o código recebido.")
        data = self._call("POST", "/auth/v1/verify",
                          payload={"email": email.strip().lower(), "token": code.strip(), "type": "recovery"})
        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"]:
            raise AuthError("Código inválido ou expirado. Solicite outro código.")
        token = data["access_token"]
        identity = self._identity(token)
        if identity["email"].strip().lower() != email.strip().lower():
            raise AuthError("O código não corresponde ao e-mail informado.")
        self._call("PUT", "/auth/v1/user", token=token, payload={"password": password})


def criar_auth(get: Callable[[str, str | None], str | None]) -> SupabaseAuth:
    return SupabaseAuth(get("SUPABASE_URL", "") or "", get("SUPABASE_PUBLISHABLE_KEY", "") or "")
