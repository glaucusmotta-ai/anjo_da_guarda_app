# backend/services/service_email.py

import os
import ssl
import smtplib
import logging
from email.message import EmailMessage
from typing import List, Optional

from pydantic import BaseModel

logger = logging.getLogger("anjo_da_guarda")


class SosEmailRequest(BaseModel):
    nome: str = "nome"
    lat: Optional[float] = None
    lon: Optional[float] = None
    tracking_url: Optional[str] = None  # link rastreável (ex.: https://anjo-track.3g-brasil.com/t/xxxxx)
    emails: Optional[List[str]] = None
    origem: Optional[str] = None  # "audio", "pin", etc. (só para log)


def build_alert_text_email(
    nome: str,
    tracking_url: Optional[str],
    lat: Optional[float],
    lon: Optional[float],
) -> str:
    """
    Mesmo padrão conceitual do texto de alerta:
    ALERTA + situação + localização (com ou sem mapa).

    Prioridade:
    1) Se vier tracking_url (link rastreável do Anjo da Guarda), usa ele.
    2) Senão, se vier lat/lon, usa link do Google Maps.
    3) Senão, informa "Localização: não informada".
    """
    # 1) Preferência: link rastreável do Anjo da Guarda
    if tracking_url:
        link = tracking_url.strip()
        return (
            f"🚨 ALERTA de {nome}\n"
            f"Situação: sos pessoal\n"
            f"Localização (mapa): {link}\n\n"
            f"Se não puder ajudar, encaminhe às autoridades."
        ).strip()

    # 2) Fallback: lat/lon -> Google Maps
    if lat is not None and lon is not None:
        link = f"https://maps.google.com/?q={lat},{lon}"
        return (
            f"🚨 ALERTA de {nome}\n"
            f"Situação: sos pessoal\n"
            f"Localização (mapa): {link}\n\n"
            f"Se não puder ajudar, encaminhe às autoridades."
        ).strip()

    # 3) Sem localização
    return (
        f"🚨 ALERTA de {nome}\n"
        f"Situação: sos pessoal\n"
        f"Localização: não informada\n\n"
        f"Se não puder ajudar, encaminhe às autoridades."
    ).strip()



def send_sos_email_via_smtp(req: SosEmailRequest) -> bool:
    """
    Envia o e-mail SOS usando SMTP (Zoho, por exemplo).
    Agora lê diretamente o arquivo .env (SMTP_* e EMAIL_SMTP_*),
    sem depender de os.getenv().
    """
    # Caminho do .env na raiz do projeto
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env_path = os.path.join(base_dir, ".env")

    # Carrega o .env como dicionário
    try:
        from dotenv import dotenv_values  # já está instalado no projeto
        env = dotenv_values(env_path)
    except Exception:
        env = {}

    # Helper pra buscar com fallback em várias chaves
    def env_get(*keys, default: str = "") -> str:
        for k in keys:
            v = env.get(k)
            if v is not None and str(v).strip() != "":
                return str(v).strip()
        return default

    # Lê SMTP_* com fallback para EMAIL_SMTP_* (legado)
    smtp_host = env_get("SMTP_HOST", "EMAIL_SMTP_HOST")
    smtp_port_str = env_get("SMTP_PORT", "EMAIL_SMTP_PORT", default="587")
    try:
        smtp_port = int(smtp_port_str)
    except ValueError:
        smtp_port = 587

    smtp_user = env_get("SMTP_USER", "EMAIL_USERNAME")
    smtp_pass = env_get("SMTP_PASS", "EMAIL_PASSWORD")
    smtp_from = env_get("SMTP_FROM", "EMAIL_FROM", default=smtp_user)

    email_enabled_str = env_get("EMAIL_ENABLED", default="true").lower()
    email_enabled = email_enabled_str in ("1", "true", "yes", "on")

    if not email_enabled:
        logger.warning("EMAIL_ENABLED=false no .env, pulando envio de e-mail SOS.")
        return False

    if not (smtp_host and smtp_user and smtp_pass and smtp_from):
        logger.error(
            "SMTP não configurado (verifique SMTP_HOST/EMAIL_SMTP_HOST, "
            "SMTP_USER/EMAIL_USERNAME, SMTP_PASS/EMAIL_PASSWORD, SMTP_FROM/EMAIL_FROM)"
        )
        return False

    # Resolve destinatários
    to_list: List[str] = []

    # 1) se o app mandou lista de e-mails no JSON, usa ela
    if req.emails:
        to_list.extend([e.strip() for e in req.emails if e and e.strip()])

    # 2) se não vier nada, usa fallback do backend (lista fixa)
    if not to_list:
        default_to = env_get("SOS_EMAIL_TO", "EMAIL_TO_LIST", default="")
        to_list = [e.strip() for e in default_to.split(",") if e.strip()]

    if not to_list:
        logger.error("Nenhum destinatário de e-mail configurado para SOS.")
        return False

    nome = (req.nome or "nome").strip() or "nome"
    body = build_alert_text_email(nome, req.tracking_url, req.lat, req.lon)
    subject = f"SOS - ALERTA de {nome}"

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = ", ".join(to_list)
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            # Sempre STARTTLS (Zoho aceita na 587)
            server.starttls(context=context)
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)

        logger.info(
            "E-mail SOS enviado para %s (origem=%s)",
            to_list,
            req.origem or "desconhecida",
        )
        return True
    except Exception as e:
        logger.exception("Erro ao enviar e-mail SOS: %s", e)
        return False
