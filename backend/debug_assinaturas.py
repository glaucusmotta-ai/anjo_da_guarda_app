import os
import sqlite3

# BASE_DIR = pasta "backend"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# DATA_DIR = C:\dev\anjo_da_guarda_app\data
DATA_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "data"))
DB_PATH = os.path.join(DATA_DIR, "anjo.db")


def listar_assinaturas():
    if not os.path.exists(DB_PATH):
        print(f"[ASSINATURAS] Banco não encontrado em: {DB_PATH}")
        return

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
              status,
              origem,
              billing_provider,
              data_inicio_utc,
              data_prox_cobranca_utc,
              data_cancelamento_utc,
              created_at_utc,
              updated_at_utc
            FROM assinaturas
            ORDER BY id ASC
            """
        )
        rows = cur.fetchall()

        print(f"[ASSINATURAS] DB_PATH = {DB_PATH}")
        if not rows:
            print("[ASSINATURAS] Nenhuma assinatura encontrada.")
            return

        for r in rows:
            print("-" * 70)
            print(f"id:          {r['id']}")
            print(f"email:       {r['user_email']}")
            print(f"plano:       {r['plano']}")
            print(f"valor (cent):{r['valor_mensal_centavos']}")
            print(f"status:      {r['status']}")
            print(f"origem:      {r['origem']}")
            print(f"billing:     {r['billing_provider']}")
            print(f"início:      {r['data_inicio_utc']}")
            print(f"próx cob.:   {r['data_prox_cobranca_utc']}")
            print(f"cancelado:   {r['data_cancelamento_utc']}")
            print(f"created_at:  {r['created_at_utc']}")
            print(f"updated_at:  {r['updated_at_utc']}")

    finally:
        conn.close()


if __name__ == "__main__":
    listar_assinaturas()
