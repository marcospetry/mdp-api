"""Gera os valores secretos do Omni/Instagram. Roda LOCALMENTE, sem rede e sem banco.

Copie cada valor direto para o Dokploy (mdp-api > Environment). NUNCA cole estes valores no chat, no Git ou em e-mail.
"""
import secrets

from cryptography.fernet import Fernet

print("OMNI_CONNECTION_ENCRYPTION_KEY=" + Fernet.generate_key().decode())
print("INSTAGRAM_WEBHOOK_VERIFY_TOKEN=" + secrets.token_urlsafe(32))
print()
print("Guarde a chave de criptografia num gerenciador de senhas: sem ela, os tokens ja gravados nao podem ser lidos.")
