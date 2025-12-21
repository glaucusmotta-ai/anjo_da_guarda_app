import os
import sqlite3
from datetime import datetime, timedelta
from typing import Any

# BASE_DIR = pasta "services"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = C:\dev\anjo_da_guarda_app\data
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def _utc_now_iso() -> str:
    """Retorna o horário UTC atual em ISO8601 (segundos) com sufixo 'Z'."""
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def registrar_assinatura_site(
    user_email: str,
    plano: str,
    valor_mensal_centavos: int,
    origem: str = "site",
    billing_provider: str = "manual",
    external_id: str | None = None,
    status: str = "ativa",
    desconto_centavos: int = 0,
    vendedor_email: str | None = None,
    percentual_comissao: float = 0.05,
) -> int:
    """
    Registra uma nova assinatura na tabela `assinaturas`.

    - `desconto_centavos` entra no cálculo da comissão (base = valor - desconto).
    - Se não houver `vendedor_email`, a comissão fica 0.
    """

    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)

    try:
        conn.execute("PRAGMA foreign_keys = ON;")

        agora = _utc_now_iso()
        prox_cobranca = (
            datetime.utcnow() + timedelta(days=30)
        ).isoformat(timespec="seconds") + "Z"

        # normaliza desconto (nunca negativo)
        desconto_centavos = max(int(desconto_centavos or 0), 0)

        # base para comissão = bruto - desconto
        valor_liquido_para_comissao = max(
            int(valor_mensal_centavos) - desconto_centavos, 0
        )

        if vendedor_email:
            comissao_centavos = int(
                round(valor_liquido_para_comissao * float(percentual_comissao))
            )
        else:
            comissao_centavos = 0

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO assinaturas (
                user_email,
                plano,
                valor_mensal_centavos,
                status,
                origem,
                billing_provider,
                external_id,
                data_inicio_utc,
                data_prox_cobranca_utc,
                data_cancelamento_utc,
                created_at_utc,
                updated_at_utc,
                desconto_centavos,
                vendedor_email,
                comissao_centavos
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, ?)
            """,
            (
                user_email,
                plano,
                valor_mensal_centavos,
                status,
                origem,
                billing_provider,
                external_id,
                agora,
                prox_cobranca,
                agora,
                agora,
                desconto_centavos,
                vendedor_email,
                comissao_centavos,
            ),
        )

        conn.commit()
        return int(cur.lastrowid)

    finally:
        conn.close()


def listar_assinaturas_debug(limit: int = 100) -> list[dict[str, Any]]:
    """
    Retorna as últimas assinaturas para debug interno (/api/assinaturas/debug).

    Já inclui desconto, vendedor e comissão.
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                user_email,
                plano,
                valor_mensal_centavos,
                desconto_centavos,
                vendedor_email,
                comissao_centavos,
                status,
                origem,
                billing_provider,
                external_id,
                data_inicio_utc,
                data_prox_cobranca_utc,
                data_cancelamento_utc,
                created_at_utc,
                updated_at_utc
            FROM assinaturas
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]

    finally:
        conn.close()


def listar_comissoes_por_vendedor(
    vendedor_email: str, limit: int = 500
) -> dict[str, Any]:
    """
    Retorna um resumo de comissões para UM vendedor específico.

    - itens: lista de assinaturas dele
    - totais: somatórios em centavos (bruto, desconto, líquido, comissão)
    """
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                user_email,
                plano,
                valor_mensal_centavos,
                desconto_centavos,
                comissao_centavos,
                status,
                origem,
                billing_provider,
                data_inicio_utc,
                data_prox_cobranca_utc,
                created_at_utc,
                updated_at_utc
            FROM assinaturas
            WHERE vendedor_email = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (vendedor_email, limit),
        )
        rows = cur.fetchall()
        itens = [dict(r) for r in rows]

        total_bruto = 0
        total_desc = 0
        total_liq = 0
        total_comissao = 0

        for r in itens:
            bruto = int(r.get("valor_mensal_centavos") or 0)
            desc = int(r.get("desconto_centavos") or 0)
            com = int(r.get("comissao_centavos") or 0)
            liq = max(bruto - desc, 0)

            total_bruto += bruto
            total_desc += desc
            total_liq += liq
            total_comissao += com

        return {
            "vendedor_email": vendedor_email,
            "totais": {
                "valor_bruto_centavos": total_bruto,
                "desconto_centavos": total_desc,
                "valor_liquido_centavos": total_liq,
                "comissao_centavos": total_comissao,
            },
            "itens": itens,
        }
    finally:
        conn.close()


if __name__ == "__main__":
    # Teste rápido manual (opcional)
    novo_id = registrar_assinatura_site(
        user_email="teste_comissao@example.com",
        plano="Mensal individual — BRL 22,90",
        valor_mensal_centavos=2290,
        # simula venda COM vendedor e desconto
        desconto_centavos=290,  # R$ 2,90 de desconto
        vendedor_email="vendedor1@3g-brasil.com",
        percentual_comissao=0.05,
    )
    print("Assinatura de teste criada com id =", novo_id)
