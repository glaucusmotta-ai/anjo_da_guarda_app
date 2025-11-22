# backend/main.py
import re
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from services.zenvia import (
    send_whatsapp_template,
    send_sms_zenvia,
    format_local_aproximado,
)

app = FastAPI()

from fastapi import Request
from fastapi.responses import JSONResponse

@app.get("/ping")
def ping():
    return {"ok": True}

@app.post("/api/zenvia/status")
async def zenvia_status(req: Request):
    payload = await req.json()
    print("ZENVIA STATUS:", payload)  # vai aparecer no terminal
    return {"ok": True}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # dev only
    allow_methods=["*"],
    allow_headers=["*"],
)

class SosIn(BaseModel):
    nome: str = Field(..., min_length=1)
    lat: float
    lon: float
    # lista obrigatória (>=1 item)
    destinatarios: list[str] = Field(..., min_items=1)

    @field_validator("destinatarios")
    @classmethod
    def _valida_destinatarios(cls, v: list[str]) -> list[str]:
        pat = re.compile(r"^\d{10,15}$")
        for num in v:
            if not pat.match(num):
                raise ValueError("Cada destinatário deve estar em E.164 (sem +), 10–15 dígitos.")
        return v

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/api/sos")
def disparar_sos(body: SosIn):
    loc_param = format_local_aproximado(body.lat, body.lon)  # "q=lat,lon"
    resultados = []

    for numero in body.destinatarios:
        wa = send_whatsapp_template(
            to=numero,
            nome=body.nome,
            local_aproximado=loc_param,
        )
        item = {"to": numero, "whatsapp": wa}

        if not wa.get("ok"):
            # fallback SMS com link completo
            url = f"https://maps.google.com/?{loc_param}"
            sms_msg = (
                f"🚨 ALERTA de {body.nome}\n"
                f"Situação: sos pessoal\n"
                f"Localização (mapa): {url}\n"
                f"Se não puder ajudar, encaminhe às autoridades."
            )
            sms = send_sms_zenvia(numero, sms_msg)
            item["sms"] = sms

        resultados.append(item)

    if all(not r["whatsapp"].get("ok") for r in resultados):
        raise HTTPException(status_code=502, detail=resultados)

    return {"sent": resultados}
