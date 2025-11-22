import smtplib, ssl
FROM="glaucusmotta@gmail.com"
PWD ="xzhetcmouwjxzsof"  # senha de app
TO  =["glaucusmotta@gmail.com","glaucusmotta@hotmail.com","giovannasilvamotta@hotmail.com","glaucumottafilho2012@gmail.com"]

msg = f"From: {FROM}\r\nTo: {', '.join(TO)}\r\nSubject: Teste SMTP direto (Anjo da Guarda)\r\n\r\nSe você recebeu este e-mail, o SMTP está OK.\r\n"
ctx = ssl.create_default_context()
with smtplib.SMTP("smtp.gmail.com", 587, timeout=25) as s:
    s.ehlo(); s.starttls(context=ctx); s.ehlo()
    s.login(FROM, PWD)
    s.sendmail(FROM, TO, msg.encode("utf-8"))
print("SMTP OK")
