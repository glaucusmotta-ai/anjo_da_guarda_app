# -*- coding: utf-8 -*-
"""
service_clientes.py

Serviços de "cliente" para o Anjo da Guarda:
- normalização de telefone (formato E.164 "bruto" com DDI 55)
- lookup de usuário por e-mail
- criação/garantia de contatos (sms/whatsapp) para um usuário
- função de alto nível para vincular telefone a um usuário (por e-mail)

Obs:
- NÃO cria usuário novo (não mexe em senha nem fluxo de auth).
- Só trabalha com users já existentes na tabela `users`.
"""

import os
import re
import sqlite3
import logging
from datetime import datetime
from typing import Optional, Dict, Any, Iterable, List

# ---------------------------------------------------------
# Logs
# ---------------------------------------------------------
logger = logging.getLogger("anjo_da_guarda.clientes")

# ---------------------------------------------------------
# DB helpers
# ---------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# volta duas pastas: services -> backend -> (raiz do projeto) -> data
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def db() -> sqlite3.Connection:
    """
    Abre conexão com o mesmo anjo.db usado pelo anjo_web_main.
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.utcnow().isoformat()


# ---------------------------------------------------------
# Normalização de telefone
# ---------------------------------------------------------
def normalize_phone_e164(phone_raw: Optional[str]) -> Optional[str]:
    """
    Normaliza telefone para um formato "E.164 simplificado" numérico,
    sempre com DDI 55 (Brasil), sem o sinal de +.

    Exemplos:
      "11 97415-2712"      -> "5511974152712"
      "+55 (11) 97415-2712"-> "5511974152712"
      "97415-2712"         -> "55974152712"  (sem DDD fica difícil, mas ainda guarda dígitos)

    Retorna None se não houver dígitos suficientes.
    """
    if not phone_raw:
        return None

    digits = re.sub(r"\D", "", phone_raw)
    if not digits:
        return None

    # Já começa com 55 -> assume que já está com DDI
    if digits.startswith("55"):
        # mínimo razoável: 55 + 2(DDD) + 8/9 (número) => 12/13 dígitos
        if len(digits) < 12:
            logger.warning("[CLIENTES] telefone possivelmente incompleto: %r -> %r", phone_raw, digits)
        return digits

    # Não começa com 55: se tiver pelo menos 10 dígitos, prefixa 55
    if len(digits) >= 10:
        normalized = "55" + digits
        return normalized

    # Muito curto, não dá pra confiar
    logger.warning("[CLIENTES] telefone muito curto, ignorando: %r -> %r", phone_raw, digits)
    return None


# ---------------------------------------------------------
# Users / Contacts helpers
# ---------------------------------------------------------
def get_user_by_email(email: Optional[str]) -> Optional[sqlite3.Row]:
    """
    Busca um usuário na tabela `users` pelo e-mail (case insensitive).
    Retorna a linha inteira ou None.
    """
    if not email:
        return None

    email_clean = email.strip().lower()
    if not email_clean:
        return None

    with db() as con:
        row = con.execute(
            "SELECT id, email, email_verified, created_at FROM users WHERE email=?",
            (email_clean,),
        ).fetchone()
    return row


def get_contacts_for_user(user_id: int) -> List[sqlite3.Row]:
    """
    Retorna todos os contatos (pending/active) de um user_id.
    """
    with db() as con:
        rows = con.execute(
            """
            SELECT id, type, value, is_primary, status, created_at
            FROM contacts
            WHERE user_id=? AND status IN ('pending', 'active')
            ORDER BY type, id
            """,
            (user_id,),
        ).fetchall()
    return list(rows)


def ensure_contacts_for_phone(
    user_id: int,
    phone_normalized: str,
    types: Iterable[str] = ("sms", "whatsapp"),
) -> Dict[str, Any]:
    """
    Garante que existam contatos para o `user_id` com o valor `phone_normalized`
    para os tipos informados (ex.: sms, whatsapp).

    - Se já existir contato com esse valor + tipo, apenas reutiliza.
    - Se não existir, insere uma nova linha em contacts:
        status='pending'
        is_primary=1 se não houver nenhum contato daquele tipo ainda.

    Retorna um resumo:
      {
        "created": ["sms", "whatsapp"],
        "reused": ["sms"],
      }
    """
    types = list(types) or []
    if not types:
        return {"created": [], "reused": []}

    created: List[str] = []
    reused: List[str] = []

    with db() as con:
        # Contatos já existentes com esse mesmo valor
        existing_rows = con.execute(
            """
            SELECT id, type, value, is_primary, status
            FROM contacts
            WHERE user_id=? AND value=?
            """,
            (user_id, phone_normalized),
        ).fetchall()
        existing_by_type = {r["type"]: r for r in existing_rows}

        for ctype in types:
            ctype = (ctype or "").strip().lower()
            if not ctype:
                continue

            # Já existe contato deste tipo com este número -> reaproveita
            if ctype in existing_by_type:
                reused.append(ctype)
                continue

            # Verifica se já existem contatos desse tipo (qualquer número)
            row_type = con.execute(
                "SELECT id FROM contacts WHERE user_id=? AND type=?",
                (user_id, ctype),
            ).fetchone()
            is_primary = 1 if row_type is None else 0

            con.execute(
                """
                INSERT INTO contacts (user_id, type, value, is_primary, status, created_at)
                VALUES (?,?,?,?,?,?)
                """,
                (
                    user_id,
                    ctype,
                    phone_normalized,
                    is_primary,
                    "pending",
                    _now(),
                ),
            )
            created.append(ctype)

    return {"created": created, "reused": reused}


# ---------------------------------------------------------
# Função de alto nível: vincular telefone ao cliente
# ---------------------------------------------------------
def link_phone_to_user(
    email: Optional[str],
    phone_raw: Optional[str],
    types: Iterable[str] = ("sms", "whatsapp"),
) -> Dict[str, Any]:
    """
    Vincula um telefone (phone_raw) a um usuário existente (via e-mail),
    garantindo entradas em `contacts` para os tipos desejados.

    NÃO cria usuário novo.
    Pensado para ser usado em fluxos como:
      - venda no site (assinatura) que informa e-mail + telefone
      - depois queremos amarrar esse telefone ao cliente no banco.

    Retorno (exemplo):
      {
        "ok": True,
        "reason": "LINKED",
        "email": "cliente@exemplo.com",
        "user_id": 123,
        "phone_raw": "+55 11 97415-2712",
        "phone_normalized": "5511974152712",
        "created": ["sms"],
        "reused": ["whatsapp"]
      }
    """
    email_clean = (email or "").strip().lower()
    phone_normalized = normalize_phone_e164(phone_raw)

    if not email_clean or not phone_normalized:
        return {
            "ok": False,
            "reason": "MISSING_EMAIL_OR_PHONE",
            "email": email_clean,
            "phone_raw": phone_raw,
            "phone_normalized": phone_normalized,
        }

    user_row = get_user_by_email(email_clean)
    if not user_row:
        return {
            "ok": False,
            "reason": "USER_NOT_FOUND",
            "email": email_clean,
            "phone_raw": phone_raw,
            "phone_normalized": phone_normalized,
        }

    user_id = int(user_row["id"])
    summary = ensure_contacts_for_phone(
        user_id=user_id,
        phone_normalized=phone_normalized,
        types=types,
    )

    result: Dict[str, Any] = {
        "ok": True,
        "reason": "LINKED",
        "email": email_clean,
        "user_id": user_id,
        "phone_raw": phone_raw,
        "phone_normalized": phone_normalized,
    }
    result.update(summary)
    return result
