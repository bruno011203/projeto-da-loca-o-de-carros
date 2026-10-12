import re

from django.core.exceptions import ValidationError


def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf) -> bool:
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        if (soma * 10) % 11 % 10 != int(cpf[tamanho]):
            return False
    return True


def validar_cpf(valor):
    if not cpf_valido(valor):
        raise ValidationError("CPF inválido.")
