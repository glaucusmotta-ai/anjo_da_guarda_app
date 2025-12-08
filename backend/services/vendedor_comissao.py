import os
import sqlite3
from typing import List, Dict, Any

# Mesmo esquema dos outros serviços (service_assinaturas, service_mapa etc.)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def _connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def listar_comissoes_por_vendedor(vendedor_email: str) -> List[Dict[str, Any]]:
    """
    Lista as assinaturas relacionadas a um vendedor específico,
    já trazendo valores bruto, desconto, líquido e comissão.
    """
    conn = _connect()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                id,
                user_email,
                plano,
                valor_mensal_centavos,
                COALESCE(desconto_centavos, 0) AS desconto_centavos,
                -- valor líquido = bruto - desconto
                (valor_mensal_centavos - COALESCE(desconto_centavos, 0)) AS valor_liquido_centavos,
                COALESCE(comissao_centavos, 0) AS comissao_centavos,
                vendedor_email,
                status,
                data_inicio_utc,
                created_at_utc
            FROM assinaturas
            WHERE vendedor_email = ?
            ORDER BY created_at_utc DESC, id DESC
            """,
            (vendedor_email,),
        )
        rows = cur.fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def resumir_comissoes_por_vendedor(vendedor_email: str) -> Dict[str, Any]:
    """
    Monta um resumo (totais) + lista de itens para o vendedor.
    Usado tanto no JSON quanto para gerar o CSV.
    """
    itens = listar_comissoes_por_vendedor(vendedor_email)

    total_bruto = sum(i.get("valor_mensal_centavos", 0) or 0 for i in itens)
    total_desc = sum(i.get("desconto_centavos", 0) or 0 for i in itens)
    total_liq = sum(i.get("valor_liquido_centavos", 0) or 0 for i in itens)
    total_comissao = sum(i.get("comissao_centavos", 0) or 0 for i in itens)

    return {
        "vendedor_email": vendedor_email,
        "totais": {
            "valor_bruto_centavos": total_bruto,
            "desconto_centavos": total_desc,
            "valor_liquido_centavos": total_liq,
            "comissao_centavos": total_comissao,
        },
        "items": itens,
    }


if __name__ == "__main__":
    # Teste rápido manual
    email_teste = "comercial@3g-brasil.com"
    resumo = resumir_comissoes_por_vendedor(email_teste)
    print("Resumo de comissão (teste):")
    print(resumo)
