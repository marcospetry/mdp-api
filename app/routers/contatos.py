from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.contato import Contato
from app.schemas.contato import ContatoCreate, ContatoResponse


router = APIRouter(
    prefix="/api/contatos",
    tags=["Contatos"],
)

MDP_EMPRESA_ID = UUID("4ac04902-ee2b-4b18-b99a-b5b3bbefaa40")


@router.post(
    "",
    response_model=ContatoResponse,
    status_code=status.HTTP_201_CREATED,
)
def criar_contato(
    dados: ContatoCreate,
    db: Session = Depends(get_db),
):
    contato = Contato(
        empresa_id=MDP_EMPRESA_ID,
        nome=dados.nome,
        email=str(dados.email),
        telefone=dados.telefone,
        empresa_contato=dados.empresa_contato,
        mensagem=dados.mensagem,
        origem="site",
        status="novo",
    )

    db.add(contato)
    db.commit()
    db.refresh(contato)

    return contato
