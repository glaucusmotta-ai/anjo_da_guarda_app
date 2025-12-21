"""
services/comissao.py

Funções de cálculo de COMISSÃO do vendedor nas assinaturas.
Toda regra de comissão fica concentrada aqui.
"""

from typing import Optional


def calcular_comissao_centavos(
    valor_base_centavos: int,
    percentual_comissao: float = 5.0,
    tem_comissao: bool = True,
) -> int:
    """
    Calcula a comissão do vendedor em centavos.

    Parâmetros:
      - valor_base_centavos: base de cálculo (normalmente valor_mensal - desconto)
      - percentual_comissao: ex.: 5.0 = 5%
      - tem_comissao: se False, retorna 0 sempre.

    Regras:
      - Se tem_comissao == False -> 0
      - Se valor_base_centavos <= 0 -> 0
      - Se percentual_comissao <= 0 -> 0
      - Senão: round(valor_base_centavos * (percentual_comissao / 100))
      - Nunca negativo.
    """

    if not tem_comissao:
        return 0

    if valor_base_centavos <= 0:
        return 0

    if percentual_comissao <= 0:
        return 0

    comissao = int(round(valor_base_centavos * (percentual_comissao / 100.0)))
    if comissao < 0:
        comissao = 0

    return comissao


if __name__ == "__main__":
    # Testes rápidos de exemplo (opcional)
    base = 2290  # R$ 22,90
    print("Sem comissão:", calcular_comissao_centavos(base, tem_comissao=False))
    print("Comissão 5%:", calcular_comissao_centavos(base, percentual_comissao=5.0, tem_comissao=True))
