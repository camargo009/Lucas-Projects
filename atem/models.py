"""Modelo de dados comum a todas as fontes (Excel, REDCap)."""
from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

STATUS_ATIVO = "Ativo"
STATUS_DESISTENTE = "Desistente"

COLS_ESPECIALISTAS = [
    "especialista_id", "nome", "telefone", "email", "especialidade", "mentor",
    "local_atuacao", "uf", "semana_imersao", "status", "aba",
]
COLS_ATIVIDADES = [
    "especialista_id", "cid", "cid_texto", "procedimento", "procedimento_nome",
    "dificuldade", "dificuldade_texto", "data", "tipo",
]
COLS_MENTORIAS = ["especialista_id", "mes_num", "mes", "propostas", "participacao", "percentual"]
COLS_CURSO_ALUNOS = [
    "especialista_id", "nome", "email", "curso", "ultimo_acesso_dias", "nunca_acessou",
    "concluidas", "total", "percentual", "situacao",
]
COLS_CURSO_ATIVIDADES = [
    "especialista_id", "nome", "curso", "modulo", "ordem", "atividade", "concluido",
]
COLS_CURSO_EVOLUCAO = [
    "especialista_id", "nome", "curso", "rotulo", "data", "concluidas", "total", "percentual",
]

TIPO_CONSULTA = "Consulta"
TIPO_PROCEDIMENTO = "Procedimento"


@dataclass
class Dataset:
    especialistas: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_ESPECIALISTAS))
    atividades: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_ATIVIDADES))
    mentorias: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_MENTORIAS))
    curso_alunos: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_CURSO_ALUNOS))
    curso_atividades: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_CURSO_ATIVIDADES))
    curso_evolucao: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=COLS_CURSO_EVOLUCAO))

    def only(self, especialista_id: str) -> "Dataset":
        """Subconjunto contendo exclusivamente um especialista."""
        def f(df: pd.DataFrame) -> pd.DataFrame:
            return df[df["especialista_id"] == especialista_id].copy()

        return Dataset(f(self.especialistas), f(self.atividades), f(self.mentorias),
                       f(self.curso_alunos), f(self.curso_atividades), f(self.curso_evolucao))

    def filtrar(self, ids) -> "Dataset":
        """Subconjunto com apenas os especialistas indicados (alunos do curso sem vínculo ficam de fora)."""
        ids = set(ids)

        def f(df: pd.DataFrame) -> pd.DataFrame:
            return df[df["especialista_id"].isin(ids)].copy()

        return Dataset(f(self.especialistas), f(self.atividades), f(self.mentorias),
                       f(self.curso_alunos), f(self.curso_atividades), f(self.curso_evolucao))

    @property
    def ativos(self) -> pd.DataFrame:
        return self.especialistas[self.especialistas["status"] != STATUS_DESISTENTE]
