from typing import Dict, Any
from datetime import datetime
import secrets

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse


def _valid_coords(lat, lon) -> bool:
    """
    Valida latitude/longitude básicos.
    """
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (TypeError, ValueError):
        return False
    return -90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0


def live_track_start_handler(
    payload: Dict[str, Any],
    request: Request,
    LIVE_TRACK_SESSIONS,
    _now,
    salvar_ponto_trilha,
    logger,
    tracking_base_url: str | None,
):
    nome = (str(payload.get("nome") or "").strip() or "contato")
    phone = (str(payload.get("phone") or "").strip() or "")
    lat = payload.get("lat")
    lon = payload.get("lon")

    if lat is None or lon is None:
        return JSONResponse(
            status_code=400, content={"ok": False, "reason": "LAT_LON_REQUIRED"}
        )

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return JSONResponse(
            status_code=400, content={"ok": False, "reason": "INVALID_COORDS"}
        )

    now = _now()
    session_id = secrets.token_urlsafe(10)
    LIVE_TRACK_SESSIONS[session_id] = {
        "nome": nome,
        "phone": phone,
        "lat": lat_f,
        "lon": lon_f,
        "created_at": now,
        "updated_at": now,
        "active": True,
        "track": [{"lat": lat_f, "lon": lon_f, "ts": now}],
    }

    # salva primeiro ponto
    try:
        salvar_ponto_trilha(session_id, lat_f, lon_f, now)
    except Exception as e:
        logger.error("[TRACK] erro ao salvar ponto inicial da trilha: %s", e)

    if tracking_base_url:
        base = tracking_base_url.rstrip("/")
    else:
        base = str(request.base_url).rstrip("/")

    tracking_url = f"{base}/t/{session_id}"

    return {
        "ok": True,
        "session_id": session_id,
        "tracking_url": tracking_url,
    }


def live_track_update_handler(
    payload: Dict[str, Any],
    LIVE_TRACK_SESSIONS,
    _now,
    salvar_ponto_trilha,
    logger,
):
    session_id = (str(payload.get("session_id") or payload.get("id") or "")).strip()
    if not session_id or session_id not in LIVE_TRACK_SESSIONS:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "reason": "SESSION_NOT_FOUND"},
        )

    session = LIVE_TRACK_SESSIONS[session_id]
    if not session.get("active", True):
        return JSONResponse(
            status_code=410,
            content={"ok": False, "reason": "SESSION_INACTIVE"},
        )

    lat = payload.get("lat")
    lon = payload.get("lon")
    if lat is None or lon is None:
        return JSONResponse(
            status_code=400, content={"ok": False, "reason": "LAT_LON_REQUIRED"}
        )

    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except Exception:
        return JSONResponse(
            status_code=400, content={"ok": False, "reason": "INVALID_COORDS"}
        )

    now = _now()
    session["lat"] = lat_f
    session["lon"] = lon_f
    session["updated_at"] = now

    track = session.get("track")
    if not isinstance(track, list):
        track = []
    track.append({"lat": lat_f, "lon": lon_f, "ts": now})
    if len(track) > 500:
        track.pop(0)
    session["track"] = track

    # persiste no banco
    try:
        salvar_ponto_trilha(session_id, lat_f, lon_f, now)
    except Exception as e:
        logger.error("[TRACK] erro ao salvar ponto da trilha no banco: %s", e)

    logger.info(
        "[TRACK UPDATE] id=%s ts=%s lat=%.7f lon=%.7f n_points=%d",
        session_id,
        now,
        lat_f,
        lon_f,
        len(track),
    )

    return {
        "ok": True,
        "session_id": session_id,
        "updated_at": now,
    }


def live_track_last_handler(session_id: str, LIVE_TRACK_SESSIONS):
    data = LIVE_TRACK_SESSIONS.get(session_id)
    if not data:
        return JSONResponse(
            status_code=404, content={"ok": False, "reason": "SESSION_NOT_FOUND"}
        )

    out = {"ok": True, "session_id": session_id}
    out.update(
        {
            "nome": data.get("nome"),
            "phone": data.get("phone"),
            "lat": data.get("lat"),
            "lon": data.get("lon"),
            "updated_at": data.get("updated_at"),
            "active": bool(data.get("active", True)),
        }
    )
    return out


def live_track_track_handler(
    session_id: str,
    LIVE_TRACK_SESSIONS,
    listar_pontos_trilha,
    logger,
):
    data = LIVE_TRACK_SESSIONS.get(session_id)

    if not data:
        # tenta carregar do banco
        try:
            points = listar_pontos_trilha(session_id)
        except Exception as e:
            logger.error("[TRACK] erro ao carregar trilha do banco: %s", e)
            points = []

        if not points:
            return JSONResponse(
                status_code=404,
                content={"ok": False, "reason": "SESSION_NOT_FOUND"},
            )

        last = points[-1]
        data = {
            "nome": "contato",
            "phone": "",
            "lat": last["lat"],
            "lon": last["lon"],
            "updated_at": last["ts"],
            "active": True,
            "track": [
                {"lat": p["lat"], "lon": p["lon"], "ts": p["ts"]}
                for p in points
            ],
        }
        LIVE_TRACK_SESSIONS[session_id] = data

    track = data.get("track") or []
    safe_track = []
    for p in track:
        try:
            lat = float(p.get("lat"))
            lon = float(p.get("lon"))
            safe_track.append({"lat": lat, "lon": lon, "ts": p.get("ts")})
        except Exception:
            continue

    return {
        "ok": True,
        "session_id": session_id,
        "nome": data.get("nome"),
        "phone": data.get("phone"),
        "track": safe_track,
        "active": bool(data.get("active", True)),
    }


def live_track_stop_handler(
    payload: Dict[str, Any],
    LIVE_TRACK_SESSIONS,
    _now,
    logger,
):
    sid = (str(payload.get("session_id") or payload.get("id") or "")).strip()
    if not sid or sid not in LIVE_TRACK_SESSIONS:
        return JSONResponse(
            status_code=404,
            content={"ok": False, "reason": "SESSION_NOT_FOUND"},
        )

    session = LIVE_TRACK_SESSIONS[sid]
    now = _now()
    session["active"] = False
    session["stopped_at"] = now
    session["updated_at"] = now

    logger.info(
        "[TRACK] sessão encerrada pelo app id=%s nome=%s",
        sid,
        session.get("nome"),
    )
    return {"ok": True}


def live_track_list_handler(
    LIVE_TRACK_SESSIONS,
    tracking_base_url: str | None,
    public_base_url: str,
):
    """
    Lista todas as sessões de rastreamento em memória.
    """
    sessions_out = []

    if tracking_base_url:
        base = tracking_base_url.rstrip("/")
    else:
        base = public_base_url.rstrip("/")

    now = datetime.utcnow()

    for sid, data in LIVE_TRACK_SESSIONS.items():
        lat = data.get("lat")
        lon = data.get("lon")
        if not _valid_coords(lat, lon):
            continue

        updated_at = data.get("updated_at")

        session_flag = bool(data.get("active", True))
        active = session_flag

        if updated_at:
            try:
                dt = datetime.fromisoformat(updated_at)
                age = (now - dt).total_seconds()
                active = session_flag and (age <= 900)
            except Exception:
                active = session_flag

        try:
            lat_f = float(lat)
            lon_f = float(lon)
        except Exception:
            continue

        sessions_out.append(
            {
                "id": sid,
                "nome": data.get("nome") or "contato",
                "phone": data.get("phone") or "",
                "lat": lat_f,
                "lon": lon_f,
                "updated_at": updated_at,
                "active": active,
                "tracking_url": f"{base}/t/{sid}",
            }
        )

    return {"ok": True, "sessions": sessions_out}


def live_track_delete_handler(session_id: str, LIVE_TRACK_SESSIONS):
    """Remove uma sessão de rastreamento da memória."""
    if session_id in LIVE_TRACK_SESSIONS:
        try:
            del LIVE_TRACK_SESSIONS[session_id]
        except KeyError:
            pass
        return {"ok": True, "deleted": True}
    return JSONResponse(
        status_code=404,
        content={"ok": False, "reason": "SESSION_NOT_FOUND"},
    )


def api_live_track_points_handler(session_id: str, listar_pontos_trilha):
    points = listar_pontos_trilha(session_id)
    if not points:
        raise HTTPException(status_code=404, detail="Sessão não encontrada")
    return JSONResponse({"ok": True, "points": points})
