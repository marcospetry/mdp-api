import os
import smtplib
from email.message import EmailMessage


SMTP_HOST = os.getenv("SMTP_HOST")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
CONTATO_DESTINO = os.getenv(
    "CONTATO_DESTINO",
    "marcosdpetry@gmail.com",
)


def enviar_email_novo_contato(contato):
    if not all([
        SMTP_HOST,
        SMTP_USER,
        SMTP_PASSWORD,
        SMTP_FROM,
        CONTATO_DESTINO,
    ]):
        print("SMTP não configurado. E-mail não enviado.")
        return

    mensagem = EmailMessage()

    mensagem["Subject"] = f"Novo contato pelo site MDP - {contato.nome}"
    mensagem["From"] = SMTP_FROM
    mensagem["To"] = CONTATO_DESTINO
    mensagem["Reply-To"] = contato.email

    corpo = f"""
Novo contato recebido pelo site MDP Consultoria.

Nome:
{contato.nome}

E-mail:
{contato.email}

Telefone:
{contato.telefone}

Empresa:
{contato.empresa_contato or "-"}

Mensagem:
{contato.mensagem}

Origem:
{contato.origem}

ID do contato:
{contato.id}
"""

    mensagem.set_content(corpo)

    try:
        with smtplib.SMTP(
            SMTP_HOST,
            SMTP_PORT,
            timeout=20,
        ) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.ehlo()

            servidor.login(
                SMTP_USER,
                SMTP_PASSWORD,
            )

            servidor.send_message(mensagem)

        print(
            f"E-mail enviado para {CONTATO_DESTINO}"
        )

    except Exception as erro:
        print(
            f"Erro ao enviar e-mail do contato {contato.id}: {erro}"
        )