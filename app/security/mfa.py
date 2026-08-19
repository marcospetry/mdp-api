from cryptography.fernet import Fernet, InvalidToken
import pyotp

from app.config import settings


def _fernet() -> Fernet:
    if not settings.mfa_encryption_key:
        raise RuntimeError("MFA_ENCRYPTION_KEY não configurada")
    return Fernet(settings.mfa_encryption_key.encode())


def generate_secret() -> str:
    return pyotp.random_base32()


def encrypt_secret(secret: str) -> str:
    return _fernet().encrypt(secret.encode()).decode()


def decrypt_secret(secret_enc: str) -> str:
    try:
        return _fernet().decrypt(secret_enc.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError("Não foi possível descriptografar o segredo MFA") from exc


def verify_totp(secret: str, codigo: str) -> bool:
    return pyotp.TOTP(secret).verify(codigo, valid_window=1)


def provisioning_uri(secret: str, email: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=email, issuer_name=settings.mfa_issuer)
