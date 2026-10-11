"""Operações do sistema (casos de uso UC03, UC04 e UC05).

Diferente de services.py e rules.py, este módulo acessa o banco: busca os
dados, chama as regras puras e grava o resultado dentro de uma transação.
"""

import secrets
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from . import rules, services
from .enums import StatusLocacao, StatusReserva, StatusVeiculo
from .models import Locacao, Reserva, Veiculo
from .rules import RegraNegocioError

EM_ABERTO = (StatusLocacao.EM_ANDAMENTO, StatusLocacao.ATRASADA)


# --------------------------------------------------------------------------- status disparados por tempo

def atualizar_status_temporais(agora=None):
    """Avaliação preguiçosa dos estados que dependem do relógio.

    RN12: reserva ATIVA sem retirada 4 h após o horário previsto vira EXPIRADA.
    RN17: locação EM_ANDAMENTO além da tolerância de 60 min vira ATRASADA.
    Chamada no início das telas e operações que dependem desses estados.
    """
    agora = agora or timezone.now()
    Reserva.objects.filter(
        status=StatusReserva.ATIVA,
        retirada_prevista__lt=agora - rules.PRAZO_EXPIRACAO_RESERVA,
    ).update(status=StatusReserva.EXPIRADA)
    Locacao.objects.filter(
        status=StatusLocacao.EM_ANDAMENTO,
        devolucao_prevista__lt=agora - timedelta(minutes=services.TOLERANCIA_ATRASO_MIN),
    ).update(status=StatusLocacao.ATRASADA)


# --------------------------------------------------------------------------- disponibilidade

def reservas_conflitantes(inicio, fim):
    """Reservas ATIVA cujo período se sobrepõe a [inicio, fim) — RN06."""
    return Reserva.objects.filter(status=StatusReserva.ATIVA,
                                  retirada_prevista__lt=fim, devolucao_prevista__gt=inicio)


def veiculos_disponiveis(inicio, fim, categoria=None):
    """RN05, RN06, RN07: só DISPONIVEL e sem reserva ATIVA sobreposta ao período."""
    qs = (Veiculo.objects.select_related("categoria")
          .filter(status=StatusVeiculo.DISPONIVEL)
          .exclude(pk__in=reservas_conflitantes(inicio, fim).values("veiculo_id")))
    if categoria:
        qs = qs.filter(categoria=categoria)
    return qs.order_by("categoria__valor_diaria", "marca", "modelo")


def _periodos_ocupados(veiculo, ignorar_reserva=None):
    reservas = veiculo.reservas.filter(status=StatusReserva.ATIVA)
    if ignorar_reserva:
        reservas = reservas.exclude(pk=ignorar_reserva.pk)
    periodos = list(reservas.values_list("retirada_prevista", "devolucao_prevista"))
    periodos += list(veiculo.locacoes.filter(status__in=EM_ABERTO)
                     .values_list("data_retirada", "devolucao_prevista"))
    return periodos


def _validar_veiculo(veiculo, inicio, fim, ignorar_reserva=None):
    if veiculo.status != StatusVeiculo.DISPONIVEL:
        raise RegraNegocioError("RN05", "só é ofertado veículo com status DISPONÍVEL.")
    if rules.ha_sobreposicao(inicio, fim, _periodos_ocupados(veiculo, ignorar_reserva)):
        raise RegraNegocioError("RN06", "o veículo já possui reserva ou locação nesse período.")


def _validar_cliente(cliente, retirada, devolucao_prevista):
    rules.validar_cliente(
        ativo=cliente.ativo,
        data_nascimento=cliente.data_nascimento,
        cnh_categoria=cliente.cnh_categoria,
        cnh_validade=cliente.cnh_validade,
        retirada=timezone.localtime(retirada),
        devolucao_prevista=timezone.localtime(devolucao_prevista),
        possui_locacao_atrasada=cliente.locacoes.filter(status=StatusLocacao.ATRASADA).exists(),
    )


def _bloquear_veiculo(veiculo):
    """Relê o veículo com lock de linha para evitar duas reservas simultâneas."""
    return Veiculo.objects.select_for_update().select_related("categoria").get(pk=veiculo.pk)


# --------------------------------------------------------------------------- UC03 — reservar

def gerar_codigo_reserva(agora):
    while True:
        codigo = f"RES-{agora:%Y}-{secrets.token_hex(3).upper()}"
        if not Reserva.objects.filter(codigo=codigo).exists():
            return codigo


@transaction.atomic
def criar_reserva(cliente, veiculo, retirada_prevista, devolucao_prevista, agora=None):
    agora = agora or timezone.now()
    atualizar_status_temporais(agora)
    veiculo = _bloquear_veiculo(veiculo)
    diarias = rules.validar_periodo(retirada_prevista, devolucao_prevista, agora)
    _validar_cliente(cliente, retirada_prevista, devolucao_prevista)
    _validar_veiculo(veiculo, retirada_prevista, devolucao_prevista)
    return Reserva.objects.create(
        codigo=gerar_codigo_reserva(agora),
        cliente=cliente,
        veiculo=veiculo,
        retirada_prevista=retirada_prevista,
        devolucao_prevista=devolucao_prevista,
        valor_estimado=services.valor_previsto(diarias, veiculo.categoria.valor_diaria),
    )


@transaction.atomic
def cancelar_reserva(reserva, agora=None):
    """RN11: livre até 24 h antes; depois, multa de 20% do valor estimado."""
    agora = agora or timezone.now()
    atualizar_status_temporais(agora)
    reserva.refresh_from_db()
    if reserva.status != StatusReserva.ATIVA:
        raise RegraNegocioError("RN11", "só reservas ATIVA podem ser canceladas.")
    multa = (services.multa_cancelamento(reserva.valor_estimado)
             if rules.cancelamento_com_multa(reserva.retirada_prevista, agora) else services.dinheiro(0))
    reserva.status = StatusReserva.CANCELADA
    reserva.valor_multa_cancelamento = multa
    reserva.save(update_fields=["status", "valor_multa_cancelamento"])
    return multa


# --------------------------------------------------------------------------- UC04 — retirada

@transaction.atomic
def registrar_retirada(*, atendente, km_saida, combustivel_saida, reserva=None,
                       cliente=None, veiculo=None, devolucao_prevista=None, agora=None):
    """Converte uma reserva em locação ou abre uma locação de balcão (sem reserva)."""
    agora = agora or timezone.now()
    atualizar_status_temporais(agora)
    if reserva is not None:
        reserva.refresh_from_db()
        rules.validar_reserva_convertivel(reserva.status)  # RN13
        cliente, veiculo, devolucao_prevista = reserva.cliente, reserva.veiculo, reserva.devolucao_prevista
        if devolucao_prevista <= agora:
            raise RegraNegocioError("RN10", "a devolução prevista da reserva já passou.")
    else:
        if cliente is None or veiculo is None or devolucao_prevista is None:
            raise RegraNegocioError("RN13", "informe cliente, veículo e devolução prevista.")
        rules.validar_periodo(agora, devolucao_prevista, agora)

    veiculo = _bloquear_veiculo(veiculo)
    _validar_cliente(cliente, agora, devolucao_prevista)
    _validar_veiculo(veiculo, agora, devolucao_prevista, ignorar_reserva=reserva)
    rules.validar_dados_saida(km_saida, combustivel_saida, veiculo.km_atual)  # RN14

    categoria = veiculo.categoria
    locacao = Locacao.objects.create(
        reserva=reserva, cliente=cliente, veiculo=veiculo, atendente=atendente,
        data_retirada=agora, devolucao_prevista=devolucao_prevista,
        km_saida=km_saida, combustivel_saida=combustivel_saida,
        valor_diaria_aplicado=categoria.valor_diaria,  # snapshot de preço
        valor_caucao=categoria.valor_caucao,           # RN15: caução registrada
    )
    veiculo.status = StatusVeiculo.LOCADO              # RN15
    veiculo.km_atual = km_saida
    veiculo.save(update_fields=["status", "km_atual"])
    if reserva is not None:
        reserva.status = StatusReserva.CONVERTIDA      # RN15
        reserva.save(update_fields=["status"])
    return locacao


# --------------------------------------------------------------------------- UC05 — devolução

def apurar(locacao, combustivel_retorno, devolucao_real):
    return services.apurar_devolucao(
        retirada=locacao.data_retirada,
        devolucao_prevista=locacao.devolucao_prevista,
        devolucao_real=devolucao_real,
        valor_diaria=locacao.valor_diaria_aplicado,
        nivel_saida=locacao.combustivel_saida,
        nivel_retorno=combustivel_retorno,
        valor_tanque=locacao.veiculo.categoria.valor_tanque_cheio,
    )


@transaction.atomic
def registrar_devolucao(locacao, *, km_retorno, combustivel_retorno, avaria=False,
                        descricao_avaria="", devolucao_real=None, agora=None):
    agora = agora or timezone.now()
    devolucao_real = devolucao_real or agora
    locacao = Locacao.objects.select_for_update().select_related("veiculo__categoria").get(pk=locacao.pk)
    if locacao.status == StatusLocacao.FINALIZADA:
        raise RegraNegocioError("RN19", "locação finalizada não pode ser alterada.")
    if devolucao_real < locacao.data_retirada or devolucao_real > agora:
        raise RegraNegocioError("RN16", "a data de devolução deve estar entre a retirada e o momento atual.")
    rules.validar_km_retorno(locacao.km_saida, km_retorno)  # RN16

    extrato = apurar(locacao, combustivel_retorno, devolucao_real)
    locacao.devolucao_real = devolucao_real
    locacao.km_retorno = km_retorno
    locacao.combustivel_retorno = combustivel_retorno
    locacao.valor_multa = extrato["multa"]
    locacao.valor_combustivel = extrato["taxa_combustivel"]
    locacao.valor_total = extrato["total"]
    locacao.avaria = avaria
    locacao.descricao_avaria = descricao_avaria if avaria else ""
    locacao.status = StatusLocacao.FINALIZADA
    locacao.save()

    veiculo = locacao.veiculo
    veiculo.status = StatusVeiculo.MANUTENCAO if avaria else StatusVeiculo.DISPONIVEL  # RN18
    veiculo.km_atual = km_retorno
    veiculo.save(update_fields=["status", "km_atual"])
    return extrato
