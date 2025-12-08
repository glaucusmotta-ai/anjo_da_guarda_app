import os
import smtplib
from email.message import EmailMessage
from pathlib import Path


def _load_env_from_file() -> None:
    """
    Carrega variáveis do .env para o os.environ
    para funcionar mesmo quando rodar via:
      python -m services.service_email_assinatura
    """
    # pasta raiz do projeto: C:\dev\anjo_da_guarda_app
    root_dir = Path(__file__).resolve().parents[2]

    # Preferência: primeiro backend/.env, depois .env na raiz (se existir)
    candidates = [
        root_dir / "backend" / ".env",
        root_dir / ".env",
    ]

    for path in candidates:
        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip()
                        if k and k not in os.environ:
                            os.environ[k] = v
                print(f"[ASSINATURAS] .env carregado de {path}")
            except Exception as e:
                print(f"[ASSINATURAS] Erro ao ler {path}: {e}")
            break


# Carrega o .env logo na importação
_load_env_from_file()


def enviar_email_boas_vindas_assinatura(destinatario: str, plano: str) -> None:
    """
    Envia o e-mail de boas-vindas para uma nova assinatura criada pelo site.
    Usa as variáveis SMTP_ já configuradas no .env.
    """

    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "465"))
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASS")
    from_addr = os.getenv("SMTP_FROM")
    from_name = os.getenv("SMTP_FROM_NAME", "3G Brasil / Assinaturas Anjo da Guarda")

    if not all([host, port, user, password, from_addr]):
        print(
            "[ASSINATURAS] SMTP não configurado (HOST/PORT/USER/PASS/FROM). "
            "E-mail de boas-vindas NÃO será enviado."
        )
        return

    # Link de download do app (pode ser Play Store ou uma página sua com instruções)
    link_download = os.getenv(
        "ANJO_DOWNLOAD_URL",
        "https://www.3g-brasil.com/anjo-da-guarda",
    )

    # URL da imagem do QR Code (você depois sobe essa imagem no seu site)
    url_qrcode = os.getenv(
        "ANJO_QRCODE_URL",
        "https://www.3g-brasil.com/assets/qrcode-anjo-android.png",
    )

    assunto = f"Bem-vindo ao Anjo da Guarda — plano {plano}"

    # Versão texto simples (fallback sem HTML)
    corpo_texto = f"""
Olá,

Obrigado por contratar o Anjo da Guarda no plano {plano}.

1. Instale o app (Android)
Baixe o app pelo link:
{link_download}

Ou, se preferir, abra o link do QR Code (caso seu leitor use a imagem):
{url_qrcode}

2. Ative o canal oficial de WhatsApp
- Salve o número +55 11 9617-4582 nos seus contatos (Anjo da Guarda / 3G Brasil);
- Envie uma mensagem com "Oi" para esse número via WhatsApp.

Esse "Oi" é importante para liberar o canal de comunicação para:
- Mensagem de boas-vindas;
- Alertas de segurança disparados pelo app;
- Comunicações relacionadas à sua proteção.

3. Suporte
Qualquer dúvida sobre assinatura, cobrança ou uso do app, fale com a gente:
comercial@3g-brasil.com

Forte abraço,
Equipe 3G Brasil / Anjo da Guarda
""".strip()

    # Versão HTML com link + QR Code
    corpo_html = f"""
<html>
  <body style="font-family: system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color:#111; line-height:1.6;">
    <p>Olá,</p>

    <p>
      Obrigado por contratar o <strong>Anjo da Guarda</strong> no plano
      <strong>{plano}</strong>.
    </p>

    <h3>1. Instale o app (Android)</h3>
    <p>Clique no link abaixo para instalar o aplicativo no seu celular Android:</p>
    <p>
      <a href="{link_download}" target="_blank" style="color:#2563eb;">
        {link_download}
      </a>
    </p>

    <p>Se preferir, aponte a câmera do seu celular para o QR Code abaixo:</p>
    <p>
      <img
        src="{url_qrcode}"
        alt="QR Code para baixar o app Anjo da Guarda"
        style="max-width:220px; height:auto; border:0;"
      />
    </p>

    <h3>2. Ative o canal oficial de WhatsApp</h3>
    <p>
      Salve em seus contatos o número
      <strong>+55 11 9617-4582</strong>
      (Anjo da Guarda / 3G Brasil).
    </p>
    <p>
      Depois envie uma mensagem com <strong>"Oi"</strong> para esse número via WhatsApp.
      Esse passo é necessário para liberar:
    </p>
    <ul>
      <li>Mensagem de boas-vindas;</li>
      <li>Alertas de segurança disparados pelo app;</li>
      <li>Comunicações importantes sobre sua proteção.</li>
    </ul>

    <h3>3. Suporte</h3>
    <p>
      Qualquer dúvida sobre assinatura, cobrança ou uso do aplicativo, fale com a gente pelo e-mail:
      <a href="mailto:comercial@3g-brasil.com">comercial@3g-brasil.com</a>.
    </p>

    <p>
      Forte abraço,<br/>
      <strong>Equipe 3G Brasil / Anjo da Guarda</strong>
    </p>
  </body>
</html>
""".strip()

    msg = EmailMessage()
    msg["Subject"] = assunto
    msg["From"] = f"{from_name} <{from_addr}>"
    msg["To"] = destinatario
    msg.set_content(corpo_texto)
    msg.add_alternative(corpo_html, subtype="html")

    with smtplib.SMTP(host, port) as smtp:
        smtp.starttls()
        smtp.login(user, password)
        smtp.send_message(msg)


    print(f"[ASSINATURAS] E-mail de boas-vindas enviado para {destinatario}")


if __name__ == "__main__":
    # Teste rápido manual (Opcional):
    # Ajuste aqui um e-mail seu para ver se chega.
    teste_email = "comercial@3g-brasil.com"
    enviar_email_boas_vindas_assinatura(
        teste_email,
        "Mensal individual — BRL 22,90",
    )
