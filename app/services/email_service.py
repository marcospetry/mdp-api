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


def smtp_configurado():
    return all(
        [
            SMTP_HOST,
            SMTP_USER,
            SMTP_PASSWORD,
            SMTP_FROM,
        ]
    )


def enviar_mensagem(mensagem: EmailMessage, destinatario_log: str):
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

        print(f"E-mail enviado para {destinatario_log}")

    except Exception as erro:
        print(
            f"Erro ao enviar e-mail para "
            f"{destinatario_log}: {erro}"
        )


def formatar_objetivos(objetivos):
    if not objetivos:
        return "-"

    return "\n".join(
        f"- {objetivo}"
        for objetivo in objetivos
    )


def enviar_email_novo_contato(contato):
    if not smtp_configurado() or not CONTATO_DESTINO:
        print(
            "SMTP ou CONTATO_DESTINO não configurado. "
            "E-mail interno não enviado."
        )
        return

    mensagem = EmailMessage()

    if contato.tipo_solicitacao == "DIAGNOSTICO":
        empresa = contato.empresa_contato or contato.nome

        mensagem["Subject"] = (
            f"Nova solicitação de Diagnóstico MDP - {empresa}"
        )
    else:
        mensagem["Subject"] = (
            f"Novo contato pelo site MDP - {contato.nome}"
        )

    mensagem["From"] = SMTP_FROM
    mensagem["To"] = CONTATO_DESTINO
    mensagem["Reply-To"] = contato.email

    if contato.tipo_solicitacao == "DIAGNOSTICO":
        corpo = f"""
Nova solicitação de Diagnóstico Inicial recebida pelo site MDP Consultoria.

DADOS DO SOLICITANTE

Nome:
{contato.nome}

E-mail:
{contato.email}

Telefone:
{contato.telefone or "-"}

Empresa:
{contato.empresa_contato or "-"}

CNPJ:
{contato.cnpj or "-"}

Cidade:
{contato.cidade or "-"}

UF:
{contato.uf or "-"}

Site / Instagram:
{contato.site_instagram or "-"}

Segmento:
{contato.segmento or "-"}


OBJETIVOS INFORMADOS

{formatar_objetivos(contato.objetivos)}


MENSAGEM / PRINCIPAL NECESSIDADE

{contato.mensagem}


CONTROLE

Tipo de solicitação:
{contato.tipo_solicitacao}

Origem:
{contato.origem}

Consentimento LGPD:
{"Sim" if contato.consentimento_dados else "Não"}

Versão do consentimento:
{contato.consentimento_versao or "-"}

Data do consentimento:
{contato.consentimento_em or "-"}

ID do contato:
{contato.id}
"""
    else:
        corpo = f"""
Novo contato recebido pelo site MDP Consultoria.

Nome:
{contato.nome}

E-mail:
{contato.email}

Telefone:
{contato.telefone or "-"}

Empresa:
{contato.empresa_contato or "-"}

Mensagem:
{contato.mensagem}

Tipo de solicitação:
{contato.tipo_solicitacao}

Origem:
{contato.origem}

Consentimento LGPD:
{"Sim" if contato.consentimento_dados else "Não"}

Versão do consentimento:
{contato.consentimento_versao or "-"}

ID do contato:
{contato.id}
"""

    mensagem.set_content(corpo)

    enviar_mensagem(
        mensagem,
        CONTATO_DESTINO,
    )


def enviar_email_confirmacao_contato(contato):
    if not smtp_configurado():
        print(
            "SMTP não configurado. "
            "E-mail de confirmação não enviado."
        )
        return

    if not contato.email:
        print(
            f"Contato {contato.id} não possui e-mail. "
            "Confirmação não enviada."
        )
        return

    mensagem = EmailMessage()

    mensagem["From"] = SMTP_FROM
    mensagem["To"] = contato.email

    if contato.tipo_solicitacao == "DIAGNOSTICO":

        mensagem["Subject"] = (
            "Recebemos sua solicitação de Diagnóstico - "
            "MDP Consultoria"
        )

        objetivos = formatar_objetivos(
            contato.objetivos
        )

        corpo = f"""
Olá, {contato.nome}.

Recebemos sua solicitação de Diagnóstico Inicial Gratuito da MDP Consultoria.

Empresa:
{contato.empresa_contato or "-"}

Objetivos informados:

{objetivos}

Agora faremos uma rápida validação das informações da empresa.

Após essa etapa, enviaremos seu acesso individual para responder ao diagnóstico.

Você não precisa enviar uma nova solicitação.

Se precisar complementar alguma informação, basta responder a este e-mail.

Obrigado pelo contato.

MDP Consultoria
Seu negócio 24h no mundo digital.
"""

    else:

        mensagem["Subject"] = (
            "Recebemos seu contato - MDP Consultoria"
        )

        corpo = f"""
Olá, {contato.nome}.

Recebemos sua mensagem pelo site da MDP Consultoria.

Empresa:
{contato.empresa_contato or "-"}

Sua mensagem:

{contato.mensagem}

Em breve entraremos em contato pelos dados informados.

Se precisar complementar alguma informação, basta responder a este e-mail.

Obrigado pelo contato.

MDP Consultoria
Seu negócio 24h no mundo digital.
"""

    mensagem.set_content(corpo)

    enviar_mensagem(
        mensagem,
        contato.email,
    )
