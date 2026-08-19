"""Cria o primeiro superadmin MDP de forma interativa, sem senha em arquivo/Git."""
from getpass import getpass
from pathlib import Path
import sys

# Permite executar diretamente: python scripts\\bootstrap_superadmin.py
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.auth import Perfil, Usuario, UsuarioEmpresa
from app.models.empresa import Empresa
from app.security.password import hash_password


def main():
    db: Session = SessionLocal()
    try:
        email = input("E-mail do superadmin: ").strip().lower()
        nome = input("Nome: ").strip()
        senha = getpass("Senha inicial: ")
        confirmar = getpass("Confirme a senha: ")
        if senha != confirmar:
            raise SystemExit("As senhas não conferem.")
        if db.query(Usuario).filter(Usuario.email == email).first():
            raise SystemExit("Já existe usuário com esse e-mail.")
        empresa = db.query(Empresa).filter(Empresa.slug == "mdp", Empresa.ativo.is_(True)).first()
        perfil = db.query(Perfil).filter(Perfil.codigo == "ADMIN", Perfil.ativo.is_(True)).first()
        if not empresa or not perfil:
            raise SystemExit("Empresa MDP ou perfil ADMIN não encontrado.")
        usuario = Usuario(
            nome=nome,
            email=email,
            password_hash=hash_password(senha),
            is_superadmin=True,
            ativo=True,
        )
        db.add(usuario)
        db.flush()
        db.add(
            UsuarioEmpresa(
                usuario_id=usuario.id,
                empresa_id=empresa.id,
                perfil_id=perfil.id,
                ativo=True,
            )
        )
        db.commit()
        print(f"Superadmin criado: {usuario.email}")
        print("No primeiro login, o MFA será obrigatório e deverá ser configurado.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
