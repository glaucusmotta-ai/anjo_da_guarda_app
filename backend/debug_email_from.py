import os
from anjo_web_main import send_email, CFG
print("EMAIL_FROM       =", CFG.email_from)
print("EMAIL_FROM_NAME  =", os.getenv("EMAIL_FROM_NAME"))
print("EMAIL_USERNAME   =", CFG.smtp_user if hasattr(CFG,"smtp_user") else "n/a")
print("EMAIL_TO_LIST    =", CFG.email_to_legacy)
print(">>> Disparando teste via send_email()...")
res = send_email("Teste remetente com nome", "Corpo de teste.", None)
print("RESULT           =", res)
