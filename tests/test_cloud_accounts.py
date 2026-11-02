import json

import pytest

from atem.auth import autenticar, carregar_usuarios, hash_senha


def test_secrets_prevalecem_sem_publicar_arquivo(tmp_path):
    path = tmp_path / "usuarios.json"
    path.write_text('{"local": {}}', encoding="utf-8")
    contas = {"ana@example.org": {"nome": "Ana", "perfil": "especialista",
                                "especialista_id": "onco-1", "hash": hash_senha("test-only")}}
    usuarios = carregar_usuarios(path, json.dumps(contas))
    assert "local" not in usuarios
    assert autenticar(usuarios, "ana@example.org", "test-only").especialista_id == "onco-1"
    assert autenticar(usuarios, "ana@example.org", "wrong") is None


@pytest.mark.parametrize("value", ['invalid', '[]', '{"a@example.org":{}}',
                                 '{"a@example.org":{"nome":"A","perfil":"supervisor","hash":"plain"}}'])
def test_secrets_invalidos_nao_usam_contas_locais(tmp_path, value):
    with pytest.raises(ValueError, match="ATEM_USERS_JSON"):
        carregar_usuarios(tmp_path / "usuarios.json", value)


def test_secrets_vazios_nao_ativam_acesso_local(tmp_path):
    assert carregar_usuarios(tmp_path / "usuarios.json", "{}") == {}
