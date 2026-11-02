"""Gera data/usuarios.json (hashes bcrypt) e data/senhas_iniciais.csv (senhas em texto, só dos novos).

Uso:
  python scripts/gerar_usuarios.py [--excel data/acompanhamento.xlsx] [--supervisores data/supervisores.csv]
                                   [--admin email@dominio:Nome]

supervisores.csv: colunas nome,email (mentores). Usuários existentes não são alterados.
"""
import argparse
import csv
import sys
import os
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from atem.auth import carregar_supervisores_csv, carregar_usuarios, gerar_usuarios  # noqa: E402
from atem.datasource import ExcelSource, criar_fonte  # noqa: E402
import json  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", default="data/acompanhamento.xlsx")
    ap.add_argument("--redcap", action="store_true", help="Lê a fonte REDCap configurada nos secrets locais.")
    ap.add_argument("--somente-ativos", action="store_true", help="Não cria contas para desistentes.")
    ap.add_argument("--supervisores", default="data/supervisores.csv")
    ap.add_argument("--admin", action="append", default=[], help="email:Nome (repetível)")
    ap.add_argument("--usuarios", default="data/usuarios.json")
    ap.add_argument("--saida-senhas", default="data/senhas_iniciais.csv")
    a = ap.parse_args()

    if a.redcap:
        secrets_path = Path(".streamlit/secrets.toml")
        config = tomllib.loads(secrets_path.read_text(encoding="utf-8")) if secrets_path.exists() else {}
        def get(key, default=None):
            return config.get(key, os.environ.get(key, default))
        if get("DATA_SOURCE") not in {"redcap", "redcap_files"}:
            ap.error("--redcap exige DATA_SOURCE=redcap ou redcap_files.")
        ds = criar_fonte(get).load()
    else:
        ds = ExcelSource(a.excel).load()
    if a.somente_ativos:
        ds = ds.filtrar(ds.ativos["especialista_id"])
    sup = carregar_supervisores_csv(a.supervisores) if Path(a.supervisores).exists() else []
    if not sup:
        print(f"Aviso: {a.supervisores} não encontrado; mentores precisam de e-mail para ter acesso.")
    print("Mentores na base:", ", ".join(sorted(ds.especialistas["mentor"].dropna().unique())))
    admins = []
    for item in a.admin:
        email, _, nome = item.partition(":")
        admins.append({"email": email, "nome": nome or email})

    usuarios, novas = gerar_usuarios(ds, sup, admins, carregar_usuarios(a.usuarios))
    Path(a.usuarios).parent.mkdir(parents=True, exist_ok=True)
    Path(a.usuarios).write_text(json.dumps(usuarios, ensure_ascii=False, indent=2), encoding="utf-8")
    if novas:
        Path(a.saida_senhas).parent.mkdir(parents=True, exist_ok=True)
        with open(a.saida_senhas, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["email", "nome", "perfil", "senha"])
            w.writeheader()
            w.writerows(novas)
    print(f"{len(novas)} usuário(s) novo(s); total {len(usuarios)}. Senhas iniciais em {a.saida_senhas}")


if __name__ == "__main__":
    main()
