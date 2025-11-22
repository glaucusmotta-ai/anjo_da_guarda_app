from anjo_web_main import send_email, CFG
print("EMAIL_ENABLED =", CFG.email_enabled)
print("EMAIL_FROM    =", CFG.email_from)
print("EMAIL_TO_LIST =", CFG.email_to_legacy)
res = send_email("Teste direto (backend)", "Corpo de teste.\nSe chegou, SMTP via app está ok.", None)
print("RESULT        =", res)
