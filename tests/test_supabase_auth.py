import time
from dataclasses import replace
from pathlib import Path

import pytest
import requests

from atem.auth import Usuario
from atem.supabase_auth import AuthError, AuthSession, SessionExpired, SupabaseAuth


class Reply:
    def __init__(self, value=None, status=200):
        self.value, self.status_code = value, status
        self.content = b"json" if value is not None else b""

    def json(self):
        return self.value


class API:
    def __init__(self):
        self.calls = []
        self.identity = {"id": "user-1", "email": "ana@example.org",
                         "user_metadata": {"perfil": "supervisor"}}
        self.profiles = [{"id": "user-1", "nome": "Ana", "perfil": "especialista",
                          "especialista_id": "onco-1", "ativo": True}]

    def __call__(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        if url.endswith("/token") or url.endswith("/verify"):
            return Reply({"access_token": "access-private", "refresh_token": "refresh-private", "expires_in": 3600})
        if url.endswith("/atem_perfis"):
            return Reply(self.profiles)
        if url.endswith("/user"):
            return Reply(self.identity)
        return Reply(status=204)


@pytest.fixture
def api():
    return API()


def client(api):
    return SupabaseAuth("https://example.supabase.co", "sb_publishable_test", request=api)


def test_login_identidade_verificada_e_perfil_nao_vem_de_metadata(api):
    session = client(api).sign_in(" ANA@example.org ", "test-password")
    assert session.usuario == Usuario("ana@example.org", "Ana", "especialista", "onco-1")
    assert not session.usuario.eh_supervisor
    assert session.expires_at > time.time()
    assert "private" not in repr(session)
    assert api.calls[0][2]["params"] == {"grant_type": "password"}
    assert api.calls[-1][2]["headers"]["Authorization"] == "Bearer access-private"
    assert api.calls[-1][2]["params"]["id"] == "eq.user-1"
    assert all(c[2]["allow_redirects"] is False for c in api.calls)


@pytest.mark.parametrize("profiles", [
    [], [{"id": "user-1", "nome": "Ana", "perfil": "supervisor", "ativo": False}],
    [{"id": "user-1", "nome": "Ana", "perfil": "especialista", "ativo": True}],
    [{"id": "user-2", "nome": "Outra", "perfil": "supervisor", "ativo": True}],
    [{"id": "user-1", "nome": "Ana", "perfil": "inventado", "ativo": True}],
])
def test_contas_sem_permissao_nao_entram(api, profiles):
    api.profiles = profiles
    with pytest.raises(SessionExpired):
        client(api).sign_in("ana@example.org", "test-password")


def test_revalida_permissao_a_cada_interacao_e_revoga_acesso(api):
    auth = client(api)
    session = auth.sign_in("ana@example.org", "test-password")
    api.profiles[0].update(perfil="supervisor", especialista_id=None)
    assert auth.validate(session).usuario.eh_supervisor
    api.profiles = []
    with pytest.raises(SessionExpired):
        auth.validate(session)


def test_refresh_rotaciona_sessao_sem_trocar_usuario(api):
    auth = client(api)
    session = replace(auth.sign_in("ana@example.org", "test-password"), expires_at=0)
    renewed = auth.validate(session)
    assert renewed.expires_at > time.time()
    assert any(c[2].get("params") == {"grant_type": "refresh_token"} for c in api.calls)
    api.identity["id"] = "other-user"
    api.profiles[0]["id"] = "other-user"
    with pytest.raises(SessionExpired):
        auth.validate(session)


def test_sessao_invalida_nao_autoriza():
    with pytest.raises(SessionExpired):
        client(API()).validate(Usuario("ana@example.org", "Ana", "supervisor"))


def test_logout_usa_sessao_local(api):
    auth = client(api)
    auth.sign_out(auth.sign_in("ana@example.org", "test-password"))
    assert api.calls[-1][1].endswith("/logout")
    assert api.calls[-1][2]["params"] == {"scope": "local"}


def test_recuperacao_verifica_codigo_antes_de_alterar_senha(api):
    auth = client(api)
    auth.request_password_reset(" ANA@example.org ")
    assert api.calls[0][2]["json"] == {"email": "ana@example.org"}
    auth.reset_password("ana@example.org", "123456", "a-new-password-123")
    paths = [(method, url.rsplit("/", 1)[-1]) for method, url, _ in api.calls]
    assert paths == [("POST", "recover"), ("POST", "verify"), ("GET", "user"), ("PUT", "user")]
    assert api.calls[1][2]["json"]["type"] == "recovery"
    assert not any(url.endswith("/atem_perfis") for _, url, _ in api.calls)


def test_recuperacao_rejeita_senha_curta_e_email_diferente(api):
    auth = client(api)
    with pytest.raises(AuthError, match="12"):
        auth.reset_password("ana@example.org", "123456", "short")
    with pytest.raises(AuthError, match="corresponde"):
        auth.reset_password("other@example.org", "123456", "a-new-password-123")
    assert not any(method == "PUT" for method, _, _ in api.calls)


@pytest.mark.parametrize("status", [400, 401, 403, 429, 500])
def test_erros_remotos_nao_expoem_tokens_ou_corpo(status):
    auth = client(lambda *a, **k: Reply({"error": "private-token"}, status))
    with pytest.raises(AuthError) as exc:
        auth.sign_in("ana@example.org", "secret-password")
    assert "private-token" not in str(exc.value)
    assert "secret-password" not in str(exc.value)


def test_schema_ausente_e_rede_indisponivel(api):
    def request(method, url, **kwargs):
        if url.endswith("/atem_perfis"):
            return Reply({"code": "PGRST205"}, 404)
        return api(method, url, **kwargs)

    with pytest.raises(AuthError, match="configurado"):
        client(request).sign_in("ana@example.org", "test-password")

    def offline(*a, **k):
        raise requests.ConnectionError("private-token")

    with pytest.raises(AuthError, match="conectar") as exc:
        client(offline).sign_in("ana@example.org", "test-password")
    assert "private-token" not in str(exc.value)


def test_configuracao_exige_https_e_chave_publicavel():
    with pytest.raises(AuthError):
        SupabaseAuth("http://example.org", "key")
    with pytest.raises(AuthError):
        SupabaseAuth("https://example.org", "sb_secret_private")


def test_tela_supabase_nao_aceita_usuario_local_como_sessao(monkeypatch, api):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    st.cache_resource.clear()
    monkeypatch.setattr("atem.supabase_auth.criar_auth", lambda get: client(api))
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120)
    at.secrets["AUTH_PROVIDER"] = "supabase"
    at.session_state["usuario"] = Usuario("test@example.org", "Teste", "supervisor")
    at.run()
    assert not at.exception
    assert any(t.label == "Senha" for t in at.text_input)
    assert not any(b.label == "Atualizar dados" for b in at.button)
    assert any(e.label == "Esqueci minha senha" for e in at.expander)
    st.cache_resource.clear()


@pytest.mark.parametrize("role", ["especialista", "supervisor"])
def test_login_painel_e_revogacao_sem_fallback(monkeypatch, api, role):
    import streamlit as st
    from streamlit.testing.v1 import AppTest

    from atem.datasource import records_to_dataset

    st.cache_resource.clear()
    st.cache_data.clear()
    api.profiles[0]["perfil"] = role
    auth = client(api)
    monkeypatch.setattr("atem.supabase_auth.criar_auth", lambda get: auth)
    ds = records_to_dataset([
        {"nome": "Ana", "email": "ana@example.org", "especialidade": "Oncologia",
         "mentor": "Mentor", "cid": "C50", "procedimento": "0301010072", "data": "2026-06-01"},
        {"nome": "Beto", "email": "beto@example.org", "especialidade": "Anestesiologia",
         "mentor": "Outro", "cid": "K80", "procedimento": "0407030034", "data": "2026-07-01"},
        {"nome": "Beto", "email": "beto@example.org", "especialidade": "Anestesiologia",
         "mentor": "Outro", "cid": "K80", "procedimento": "0407030034", "data": "2026-08-01"},
    ])
    # O ID do acompanhamento local vem da aba, não do e-mail da fonte estruturada.
    ids = dict(zip(ds.especialistas.especialista_id, ["onco-1", "anest-1"]))
    ds.especialistas["especialista_id"] = ds.especialistas.especialista_id.map(ids)
    ds.atividades["especialista_id"] = ds.atividades.especialista_id.map(ids)

    class Source:
        def load(self):
            return ds

    monkeypatch.setattr("atem.datasource.criar_fonte", lambda get: Source())
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120)
    at.secrets["AUTH_PROVIDER"] = "supabase"
    at.run()
    next(t for t in at.text_input if t.label == "E-mail").set_value("ana@example.org")
    next(t for t in at.text_input if t.label == "Senha").set_value("test-password")
    next(b for b in at.button if b.label == "Entrar").click()
    at.run()
    assert not at.exception
    assert not at.error
    assert len(at.tabs) == (2 if role == "especialista" else 7)
    api.profiles = []
    at.run()
    assert not at.exception
    assert not at.tabs
    assert any("autorizado" in e.value for e in at.error)
    st.cache_resource.clear()
    st.cache_data.clear()
