from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from atem.auth import Usuario
from atem.models import Dataset


@pytest.mark.parametrize("fail", [False, True])
def test_carregamento_remove_popup_apos_sucesso_ou_erro(monkeypatch, fail):
    class Source:
        def load(self):
            if fail:
                raise RuntimeError("Falha de consulta de teste")
            return Dataset()

    st.cache_resource.clear()
    st.cache_data.clear()
    monkeypatch.setattr("atem.datasource.criar_fonte", lambda get: Source())
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120)
    at.secrets["AUTH_PROVIDER"] = "local"
    at.session_state["usuario"] = Usuario("test@example.org", "Teste <perfil>", "especialista", "onco-1")
    at.run()
    assert not at.exception
    lateral = "\n".join(m.value for m in at.sidebar.markdown)
    assert 'class="sidebar-brand"' in lateral
    assert "Teste &lt;perfil&gt;" in lateral
    assert "Especialista · HAOC" in lateral
    assert not any('class="atem-carregamento"' in m.value for m in at.markdown)
    if fail:
        assert any("Falha de consulta de teste" in e.value for e in at.error)
    else:
        assert not at.error
        assert any("Não encontramos seus dados" in w.value for w in at.warning)
    st.cache_resource.clear()
    st.cache_data.clear()


def test_cache_armazena_tabelas_sem_serializar_classe_da_fonte(monkeypatch):
    class DatasetRecarregado(Dataset):
        def __reduce_ex__(self, protocol):
            raise TypeError("Classe da fonte não pode ser serializada")

    calls = []

    class Source:
        def load(self):
            calls.append(True)
            return DatasetRecarregado()

    st.cache_resource.clear()
    st.cache_data.clear()
    monkeypatch.setattr("atem.datasource.criar_fonte", lambda get: Source())
    at = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py", default_timeout=120)
    at.secrets["AUTH_PROVIDER"] = "local"
    at.session_state["usuario"] = Usuario("test@example.org", "Teste", "especialista", "onco-1")
    try:
        for _ in range(2):
            at.run()
            assert not at.exception
            assert not at.error
            assert any("Não encontramos seus dados" in w.value for w in at.warning)
        assert len(calls) == 1
    finally:
        st.cache_resource.clear()
        st.cache_data.clear()
