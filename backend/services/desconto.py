"""
services/desconto.py

Funções de cálculo de DESCONTO das assinaturas.
A ideia é centralizar toda regra de desconto aqui.
"""

from typing import Optional


def calcular_desconto_centavos(
    valor_mensal_centavos: int,
    percentual: Optional[float] = None,
    valor_fixo_centavos: Optional[int] = None,
) -> int:
    """
    Calcula o desconto em centavos.

    Regras:
      - Se valor_fixo_centavos for informado e > 0, usa ele.
      - Senão, se percentual for informado e > 0, calcula:
            desconto = round(valor_mensal_centavos * (percentual / 100))
      - Se nada for informado, desconto = 0.
      - Nunca deixa o desconto ficar negativo.
      - Nunca deixa o desconto ser maior que o valor_mensal_centavos.
    """

    if valor_mensal_centavos <= 0:
        return 0

    desconto = 0

    # 1) Se veio valor fixo, ele manda
    if valor_fixo_centavos is not None and valor_fixo_centavos > 0:
        desconto = int(valor_fixo_centavos)
    # 2) Senão, se veio percentual, calcula por percentual
    elif percentual is not None and percentual > 0:
        desconto = int(round(valor_mensal_centavos * (percentual / 100.0)))
    else:
        desconto = 0

    # Proteções
    if desconto < 0:
        desconto = 0
    if desconto > valor_mensal_centavos:
        desconto = valor_mensal_centavos

    return desconto


if __name__ == "__main__":
    # Testes rápidos de exemplo (opcional)
    v = 2290  # R$ 22,90
    print("Sem desconto:", calcular_desconto_centavos(v))
    print("Desconto 10%:", calcular_desconto_centavos(v, percentual=10.0))
    print("Desconto fixo R$ 2,90:", calcular_desconto_centavos(v, valor_fixo_centavos=290))
