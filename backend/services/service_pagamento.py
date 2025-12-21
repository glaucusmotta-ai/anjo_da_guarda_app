# backend/services/service_pagamento.py

import os
import re
import logging

try:
    import mercadopago  # type: ignore
except ImportError:  # pragma: no cover
    mercadopago = None

logger = logging.getLogger("anjo_da_guarda")

MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")

# Host do backend (túneis, webhooks etc.)
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://anjo-track.3g-brasil.com")

# Página pública de instalação/checkout do Anjo da Guarda (site 3G Brasil)
SITE_DOWNLOAD_URL = os.getenv(
    "ANJO_DOWNLOAD_URL",
    "https://www.3g-brasil.com/anjo-da-guarda",
)


def _resolver_valor_centavos(plano: str, valor_centavos: int | None) -> int:
    """
    Se vier um valor explícito, usa ele.
    Caso contrário, tenta extrair o valor a partir do texto do plano
    (ex.: 'Mensal individual — BRL 22,90' -> 2290).
    Se não conseguir, usa 22,90 como padrão.
    """
    if isinstance(valor_centavos, (int, float)) and valor_centavos > 0:
        return int(valor_centavos)

    m = re.search(r"BRL\s*([0-9]+),([0-9]{2})", plano)
    if m:
        reais = int(m.group(1))
        centavos = int(m.group(2))
        return reais * 100 + centavos

    logger.warning(
        "Não foi possível extrair valor do plano '%s'; usando 22,90 como padrão.",
        plano,
    )
    return 2290  # 22,90


def gerar_checkout_url(
    assinatura_id: int,
    plano: str,
    valor_centavos: int | None,
    email: str,
) -> str:
    """
    Gera uma URL de checkout para a assinatura.

    - Se Mercado Pago estiver configurado (SDK instalado + ACCESS_TOKEN no ambiente),
      cria uma preferência e devolve o 'init_point' (link grandão de pagamento).

    - Se ainda não estiver configurado, devolve o link padrão SITE_DOWNLOAD_URL
      (página pública do Anjo da Guarda no site 3G Brasil).
    """
    valor_final = _resolver_valor_centavos(plano, valor_centavos)

    if mercadopago is None or not MERCADO_PAGO_ACCESS_TOKEN:
        logger.warning("Mercado Pago não configurado; usando link padrão de instalação.")
        return SITE_DOWNLOAD_URL

    sdk = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

    preference_data = {
        "items": [
            {
                "title": f"Assinatura Anjo da Guarda - {plano}",
                "quantity": 1,
                "currency_id": "BRL",
                "unit_price": valor_final / 100.0,  # em reais
            }
        ],
        "payer": {
            "email": email,
        },
        # Podemos usar o ID da assinatura pra localizar depois no webhook
        "external_reference": str(assinatura_id),
        # Após o pagamento, usuário cai na página pública do Anjo da Guarda
        "back_urls": {
            "success": SITE_DOWNLOAD_URL,
            "pending": SITE_DOWNLOAD_URL,
            "failure": SITE_DOWNLOAD_URL,
        },
        "auto_return": "approved",
    }

    result = sdk.preference().create(preference_data)
    resp = result.get("response", {}) if isinstance(result, dict) else {}

    init_point = resp.get("init_point") or resp.get("sandbox_init_point")

    if not init_point:
        logger.error("Não foi possível obter init_point do Mercado Pago; usando link padrão.")
        return SITE_DOWNLOAD_URL

    return init_point
