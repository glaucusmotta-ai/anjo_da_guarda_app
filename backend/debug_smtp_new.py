import os
from anjo_web_main import logger  # já existe no projeto

print("=== DEBUG SMTP_* (novo formato) ===")
print("SMTP_HOST      =", os.getenv("SMTP_HOST", ""))
print("SMTP_PORT      =", os.getenv("SMTP_PORT", ""))
print("SMTP_USER      =", os.getenv("SMTP_USER", ""))
print("SMTP_PASS vazio?", not bool(os.getenv("SMTP_PASS", "").strip()))
print("SMTP_FROM      =", os.getenv("SMTP_FROM", ""))
print("SMTP_FROM_NAME =", os.getenv("SMTP_FROM_NAME", ""))
print("EMAIL_ENABLED  =", os.getenv("EMAIL_ENABLED", ""))
print("SOS_EMAIL_TO   =", os.getenv("SOS_EMAIL_TO", ""))


# só pra garantir que o .env está sendo carregado
from anjo_web_main import CFG
print("\n=== CFG resumido ===")
print("CFG.email_enabled =", getattr(CFG, "email_enabled", None))
print("CFG.smtp_host     =", getattr(CFG, "smtp_host", None))
print("CFG.smtp_user     =", getattr(CFG, "smtp_user", None))
print("CFG.smtp_from     =", getattr(CFG, "smtp_from", None))
