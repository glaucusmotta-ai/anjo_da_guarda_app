
# backend/services/zenvia.py
import os
import requests
from typing import Optional, Dict, Any

API_TOKEN   = os.getenv("ZENVIA_API_TOKEN", "")
BASE_URL    = os.getenv("ZENVIA_BASE_URL", "https://api.zenvia.com/v2")
CALLBACK_URL = os.getenv("ZENVIA_CALLBACK_URL", None)

# WhatsApp
WA_FROM        = os.getenv("ZENVIA_WA_FROM") or os.getenv("ZENVIA_WHATSAPP_FROM", "")
WA_TEMPLATE_ID = os.getenv("ZENVIA_WA_TEMPLATE_ID") or os.getenv("ZENVIA_TEMPLATE_ID", "")
WA_FIELDS_MODE = (os.getenv("ZENVIA_WA_FIELDS_MODE", "maps") or "maps").lower().strip()
# valores aceitos: "maps", "search", "full"

# SMS
SMS_FROM = os.getenv("ZENVIA_SMS_FROM", "default")  # 3–11 chars ou 'default'

def _headers() -> Dict[str, str]:
    return {
        "X-API-Token": API_TOKEN,
        "Content-Type": "application/json; charset=utf-8",
        "Accept": "application/json",
    }

def _require(cond: bool, msg: str) -> Optional[Dict[str, Any]]:
    if not cond:
        return {"ok": False, "status": 0, "resp": {"error": msg}}
    return None

# ---------- Helpers ----------
def format_local_aproximado(lat: float, lon: float, mode: Optional[str] = None) -> str:
    """
    Gera o sufixo/URL de acordo com o template:
    - maps   -> '?q=lat,lon'                 (usar com 'https://www.google.com/maps/{{local_aproximado}}')
    - search -> 'search/?api=1&query=lat,lon' (idem)
    - full   -> 'https://maps.google.com/?q=lat,lon' (se o template NÃO tiver domínio na frente)
    """
    mode = (mode or WA_FIELDS_MODE).lower()
    latf = float(lat)
    lonf = float(lon)
    if mode == "search":
        return f"search/?api=1&query={latf:.6f},{lonf:.6f}"
    if mode == "full":
        return f"https://maps.google.com/?q={latf:.6f},{lonf:.6f}"
    # default: maps
    return f"?q={latf:.6f},{lonf:.6f}"

def _with_callback(body: Dict[str, Any]) -> Dict[str, Any]:
    if CALLBACK_URL:
        body["callbackUrl"] = CALLBACK_URL
    return body

# ---------- WhatsApp ----------
def send_whatsapp_template(to: str, nome: str, local_aproximado: str, numero_de_telefone: Optional[str] = None) -> dict:
    # validações mínimas
    err = _require(bool(API_TOKEN), "Missing ZENVIA_API_TOKEN")
    if err: return err
    err = _require(bool(WA_FROM), "Missing ZENVIA_WA_FROM")
    if err: return err
    err = _require(bool(WA_TEMPLATE_ID), "Missing ZENVIA_WA_TEMPLATE_ID")
    if err: return err

    url = f"{BASE_URL}/channels/whatsapp/messages"
    fields = {
        "nome": nome,
        "local_aproximado": local_aproximado,
    }
    if numero_de_telefone:
        fields["numero_de_telefone"] = numero_de_telefone  # só inclui se o template pedir

    body = _with_callback({
        "from": WA_FROM,
        "to": to,
        "contents": [{
            "type": "template",
            "templateId": WA_TEMPLATE_ID,
            "fields": fields,
        }],
    })

    try:
        r = requests.post(url, json=body, headers=_headers(), timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return {"ok": 200 <= r.status_code < 300, "status": r.status_code, "resp": data, "to": to}
    except requests.RequestException as e:
        return {"ok": False, "status": 0, "resp": {"error": str(e), "to": to, "body": body}}

def send_whatsapp_template_coords(to: str, nome: str, lat: float, lon: float, numero_de_telefone: Optional[str] = None) -> dict:
    loc = format_local_aproximado(lat, lon)
    return send_whatsapp_template(to=to, nome=nome, local_aproximado=loc, numero_de_telefone=numero_de_telefone)

# ---------- SMS ----------
def send_sms_zenvia(to: str, text: str) -> dict:
    err = _require(bool(API_TOKEN), "Missing ZENVIA_API_TOKEN")
    if err: return err

    url = f"{BASE_URL}/channels/sms/messages"
    body = _with_callback({
        "from": SMS_FROM,
        "to": to,
        "contents": [{"type": "text", "text": text}],
    })

    try:
        r = requests.post(url, json=body, headers=_headers(), timeout=20)
        try:
            data = r.json()
        except Exception:
            data = {"raw": r.text}
        return {"ok": 200 <= r.status_code < 300, "status": r.status_code, "resp": data, "to": to}
    except requests.RequestException as e:
        return {"ok": False, "status": 0, "resp": {"error": str(e), "to": to, "body": body}}
