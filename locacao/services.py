"""Regras de cálculo da locadora.

Funções puras: recebem números e datas e devolvem números. Não acessam o
banco, por isso os testes rodam em milissegundos (base da pirâmide de testes).
Todo valor monetário é Decimal com duas casas e arredondamento HALF_UP.
"""

import math
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from .enums import QUARTOS_COMBUSTIVEL

DIA = timedelta(hours=24)
TOLERANCIA_ATRASO_MIN = 60          # RN17
FATOR_MULTA_ATRASO = Decimal("1.5")  # diária de atraso sai 50% mais cara
PERCENTUAL_MULTA_CANCELAMENTO = Decimal("0.20")  # RN11
CENTAVO = Decimal("0.01")


def dinheiro(valor) -> Decimal:
    return Decimal(str(valor)).quantize(CENTAVO, rounding=ROUND_HALF_UP)


def _blocos_de_24h(intervalo: timedelta) -> int:
    """Quantidade de blocos de 24 h iniciados no intervalo (fração conta inteira)."""
    return math.ceil(intervalo.total_seconds() / DIA.total_seconds())


def diarias_contratadas(retirada, devolucao_prevista) -> int:
    """D = ⌈(devolucaoPrevista − retirada) / 24h⌉, mínimo de 1 diária."""
    return max(1, _blocos_de_24h(devolucao_prevista - retirada))


def valor_previsto(diarias: int, valor_diaria) -> Decimal:
    """Vprevisto = D × valorDiariaAplicado."""
    return dinheiro(Decimal(diarias) * Decimal(str(valor_diaria)))


def diarias_de_atraso(devolucao_prevista, devolucao_real, tolerancia_min=TOLERANCIA_ATRASO_MIN) -> int:
    """Datraso = max(0, ⌈(devolucaoReal − devolucaoPrevista − tolerância) / 24h⌉)."""
    excedente = devolucao_real - devolucao_prevista - timedelta(minutes=tolerancia_min)
    return max(0, _blocos_de_24h(excedente))


def valor_multa(diarias_atraso: int, valor_diaria) -> Decimal:
    """M = Datraso × valorDiariaAplicado × 1,5."""
    return dinheiro(Decimal(diarias_atraso) * Decimal(str(valor_diaria)) * FATOR_MULTA_ATRASO)


def taxa_combustivel(nivel_saida, nivel_retorno, valor_tanque) -> Decimal:
    """C = max(0, qsaída − qretorno) × valorTanqueCheio / 4."""
    quartos = max(0, QUARTOS_COMBUSTIVEL[nivel_saida] - QUARTOS_COMBUSTIVEL[nivel_retorno])
    return dinheiro(Decimal(quartos) * Decimal(str(valor_tanque)) / 4)


def valor_total(previsto, multa, combustivel) -> Decimal:
    """Vtotal = Vprevisto + M + C (a caução é tratada à parte)."""
    return dinheiro(Decimal(str(previsto)) + Decimal(str(multa)) + Decimal(str(combustivel)))


def multa_cancelamento(valor_estimado) -> Decimal:
    """RN11: 20% sobre o valor estimado quando o cancelamento é tardio."""
    return dinheiro(Decimal(str(valor_estimado)) * PERCENTUAL_MULTA_CANCELAMENTO)


def apurar_devolucao(*, retirada, devolucao_prevista, devolucao_real, valor_diaria,
                     nivel_saida, nivel_retorno, valor_tanque):
    """Extrato completo da devolução, usando as cinco fórmulas."""
    diarias = diarias_contratadas(retirada, devolucao_prevista)
    previsto = valor_previsto(diarias, valor_diaria)
    atraso = diarias_de_atraso(devolucao_prevista, devolucao_real)
    multa = valor_multa(atraso, valor_diaria)
    combustivel = taxa_combustivel(nivel_saida, nivel_retorno, valor_tanque)
    return {
        "diarias": diarias,
        "valor_previsto": previsto,
        "diarias_atraso": atraso,
        "multa": multa,
        "taxa_combustivel": combustivel,
        "total": valor_total(previsto, multa, combustivel),
    }
