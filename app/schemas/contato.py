from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, model_validator


class ContatoCreate(BaseModel):
    nome: str
    email: EmailStr
    telefone: str | None = None
    empresa_contato: str | None = None
    mensagem: str

    tipo_solicitacao: Literal[
        "CONTATO",
        "DIAGNOSTICO",
    ] = "CONTATO"

    cnpj: str | None = None
    cidade: str | None = None
    uf: str | None = None
    site_instagram: str | None = None
    segmento: str | None = None

    objetivos: list[str] = Field(
        default_factory=list
    )

    consentimento_dados: bool
    consentimento_versao: str = "LGPD_SITE_V1"

    @model_validator(mode="after")
    def validar_dados(self):
        if not self.consentimento_dados:
            raise ValueError(
                "É necessário autorizar o tratamento dos dados."
            )

        if self.tipo_solicitacao == "DIAGNOSTICO":
            campos_obrigatorios = {
                "empresa_contato": self.empresa_contato,
                "cnpj": self.cnpj,
                "cidade": self.cidade,
                "uf": self.uf,
                "segmento": self.segmento,
            }

            faltando = [
                nome
                for nome, valor in campos_obrigatorios.items()
                if not valor or not valor.strip()
            ]

            if faltando:
                raise ValueError(
                    "Para solicitar o diagnóstico, informe: "
                    + ", ".join(faltando)
                )

            if not self.objetivos:
                raise ValueError(
                    "Selecione pelo menos um objetivo."
                )

        if self.uf:
            self.uf = self.uf.strip().upper()

            if len(self.uf) != 2:
                raise ValueError(
                    "UF deve possuir 2 caracteres."
                )

        return self


class ContatoResponse(BaseModel):
    id: UUID
    empresa_id: UUID

    nome: str
    email: EmailStr
    telefone: str | None
    empresa_contato: str | None
    mensagem: str

    origem: str
    status: str

    tipo_solicitacao: str
    cnpj: str | None
    cidade: str | None
    uf: str | None
    site_instagram: str | None
    segmento: str | None
    objetivos: list[str] | None

    consentimento_dados: bool
    consentimento_em: datetime | None
    consentimento_versao: str | None

    created_at: datetime

    model_config = {
        "from_attributes": True
    }
