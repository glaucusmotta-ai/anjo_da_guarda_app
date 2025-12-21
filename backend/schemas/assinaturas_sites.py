from pydantic import BaseModel, EmailStr
from typing import Optional


class AssinaturaSiteIn(BaseModel):
    # Dados do cliente
    nome: Optional[str] = None
    telefone: Optional[str] = None  # WhatsApp do usuário
    user_email: EmailStr

    # Dados da assinatura / cobrança
    plano: str
    valor_mensal_centavos: int
    desconto_centavos: Optional[int] = 0
    vendedor_email: Optional[EmailStr] = None
