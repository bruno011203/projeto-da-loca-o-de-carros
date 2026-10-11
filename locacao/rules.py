"""Validações das regras de negócio (RN01 a RN19).

Funções puras: recebem datas, números e enums e lançam RegraNegocioError
com o código da regra violada. As operações que tocam o banco ficam em
operacoes.py e reutilizam estas funções.
"""

from datetime import timedelta

from .enums import CategoriaCNH, StatusLocacao, StatusReserva
from .services import diarias_contratadas

IDADE_MINIMA = 21                    # RN01
CATEGORIAS_CNH_PERMITIDAS = {CategoriaCNH.B, CategoriaCNH.C, CategoriaCNH.D, CategoriaCNH.E}  # RN02
MIN_DIARIAS, MAX_DIARIAS = 1, 30     # RN08
PRAZO_CANCELAMENTO_LIVRE = timedelta(hours=24)  # RN11
PRAZO_EXPIRACAO_RESERVA = timedelta(hours=4)    # RN12


class RegraNegocioError(Exception):
    def __init__(self, codigo, mensagem):
        self.codigo = codigo
        super().__init__(f"{codigo}: {mensagem}")


# --------------------------------------------------------------------------- disponibilidade

def ha_sobreposicao(nova_retirada, nova_devolucao, periodos_existentes) -> bool:
    """RN06: existe conflito se novaRetirada < devolucaoExistente e novaDevolucao > retiradaExistente.

    Períodos que apenas se encostam (um termina exatamente quando o outro começa)
    não são considerados sobrepostos.
    """
    return any(nova_retirada < fim and nova_devolucao > inicio for inicio, fim in periodos_existentes)


# --------------------------------------------------------------------------- cliente

def idade_na_data(data_nascimento, data) -> int:
    anos = data.year - data_nascimento.year
    if (data.month, data.day) < (data_nascimento.month, data_nascimento.day):
        anos -= 1
    return anos


def validar_idade(data_nascimento, data_retirada):
    """RN01: 21 anos ou mais na data da retirada."""
    if idade_na_data(data_nascimento, data_retirada) < IDADE_MINIMA:
        raise RegraNegocioError("RN01", f"o cliente deve ter {IDADE_MINIMA} anos ou mais na data da retirada.")


def validar_cnh(categoria, validade, devolucao_prevista):
    """RN02: CNH categoria B ou superior e válida até a devolução prevista."""
    if categoria not in CATEGORIAS_CNH_PERMITIDAS:
        raise RegraNegocioError("RN02", "a CNH deve ser categoria B ou superior.")
    if validade < devolucao_prevista:
        raise RegraNegocioError("RN02", "a CNH precisa estar válida até a data de devolução prevista.")


def validar_cliente_ativo(ativo):
    """RN03: cliente inativo não pode reservar."""
    if not ativo:
        raise RegraNegocioError("RN03", "cliente inativo não pode reservar.")


def validar_sem_atraso(possui_locacao_atrasada):
    """RN04: cliente com locação ATRASADA não pode abrir nova reserva."""
    if possui_locacao_atrasada:
        raise RegraNegocioError("RN04", "o cliente possui locação em atraso.")


def validar_cliente(*, ativo, data_nascimento, cnh_categoria, cnh_validade,
                    retirada, devolucao_prevista, possui_locacao_atrasada):
    validar_cliente_ativo(ativo)
    validar_sem_atraso(possui_locacao_atrasada)
    validar_idade(data_nascimento, retirada.date() if hasattr(retirada, "date") else retirada)
    validar_cnh(cnh_categoria, cnh_validade,
                devolucao_prevista.date() if hasattr(devolucao_prevista, "date") else devolucao_prevista)


# --------------------------------------------------------------------------- reserva

def validar_periodo(retirada, devolucao_prevista, agora):
    """RN09, RN10 e RN08."""
    if retirada < agora:
        raise RegraNegocioError("RN09", "a retirada prevista deve ser igual ou posterior ao momento da reserva.")
    if devolucao_prevista <= retirada:
        raise RegraNegocioError("RN10", "a devolução prevista deve ser posterior à retirada prevista.")
    diarias = diarias_contratadas(retirada, devolucao_prevista)
    if not MIN_DIARIAS <= diarias <= MAX_DIARIAS:
        raise RegraNegocioError("RN08", f"o período deve ter de {MIN_DIARIAS} a {MAX_DIARIAS} diárias.")
    return diarias


def cancelamento_com_multa(retirada_prevista, agora) -> bool:
    """RN11: cancelamento livre até 24 h antes da retirada; depois, há multa."""
    return retirada_prevista - agora < PRAZO_CANCELAMENTO_LIVRE


def reserva_expirada(status, retirada_prevista, agora) -> bool:
    """RN12: reserva ATIVA não retirada até 4 h após a hora prevista expira."""
    return status == StatusReserva.ATIVA and agora > retirada_prevista + PRAZO_EXPIRACAO_RESERVA


# --------------------------------------------------------------------------- retirada e devolução

def validar_reserva_convertivel(status):
    """RN13: só reserva ATIVA vira locação."""
    if status != StatusReserva.ATIVA:
        raise RegraNegocioError("RN13", "só uma reserva com status ATIVA pode ser convertida em locação.")


def validar_dados_saida(km_saida, combustivel_saida, km_atual_veiculo):
    """RN14: retirada exige km e combustível de saída."""
    if km_saida is None or not combustivel_saida:
        raise RegraNegocioError("RN14", "informe a quilometragem e o nível de combustível de saída.")
    if km_saida < km_atual_veiculo:
        raise RegraNegocioError("RN14", "a quilometragem de saída não pode ser menor que a atual do veículo.")


def validar_km_retorno(km_saida, km_retorno):
    """RN16: km de retorno maior ou igual ao de saída."""
    if km_retorno is None or km_retorno < km_saida:
        raise RegraNegocioError("RN16", "a quilometragem de retorno deve ser maior ou igual à de saída.")


def status_locacao_efetivo(status, devolucao_prevista, agora,
                           tolerancia=timedelta(minutes=60)):
    """ATRASADA é avaliada de forma preguiçosa: EM_ANDAMENTO além da tolerância (RN17)."""
    if status == StatusLocacao.EM_ANDAMENTO and agora > devolucao_prevista + tolerancia:
        return StatusLocacao.ATRASADA
    return status
