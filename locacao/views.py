from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import operacoes, rules, services
from .enums import PerfilUsuario, StatusLocacao, StatusReserva, StatusVeiculo
from .forms import (
    FORMATO_DATA_HORA, BuscaDisponibilidadeForm, ClienteForm, DevolucaoForm, LocacaoBalcaoForm,
    ReservaForm, RetiradaForm, VeiculoForm,
)
from .models import Cliente, Funcionario, Locacao, Reserva, Veiculo
from .rules import RegraNegocioError


def funcionario_do_usuario(user):
    """Funcionário vinculado ao usuário logado (criado na primeira vez para superusuários)."""
    funcionario = getattr(user, "funcionario", None)
    if funcionario is None:
        funcionario = Funcionario.objects.create(
            usuario=user, nome=user.get_full_name() or user.username, matricula=f"U{user.pk:04d}",
            perfil=PerfilUsuario.GERENTE if user.is_superuser else PerfilUsuario.ATENDENTE)
    return funcionario


def _local(dt):
    return timezone.localtime(dt).strftime(FORMATO_DATA_HORA)


# --------------------------------------------------------------------------- painel

@login_required
def painel(request):
    agora = timezone.now()
    operacoes.atualizar_status_temporais(agora)
    hoje = timezone.localdate()
    veiculos = Veiculo.objects.aggregate(
        total=Count("id"),
        livres=Count("id", filter=Q(status=StatusVeiculo.DISPONIVEL)),
        locados=Count("id", filter=Q(status=StatusVeiculo.LOCADO)),
        manutencao=Count("id", filter=Q(status=StatusVeiculo.MANUTENCAO)),
    )
    contexto = {
        "veiculos": veiculos,
        "em_andamento": Locacao.objects.filter(status=StatusLocacao.EM_ANDAMENTO).count(),
        "atrasadas": Locacao.objects.filter(status=StatusLocacao.ATRASADA).select_related("cliente", "veiculo"),
        "retiradas_hoje": Reserva.objects.filter(status=StatusReserva.ATIVA, retirada_prevista__date=hoje)
                                         .select_related("cliente", "veiculo"),
        "devolucoes_hoje": Locacao.objects.filter(status=StatusLocacao.EM_ANDAMENTO,
                                                  devolucao_prevista__date=hoje)
                                          .select_related("cliente", "veiculo"),
        "faturado_hoje": Locacao.objects.filter(status=StatusLocacao.FINALIZADA, devolucao_real__date=hoje)
                                        .aggregate(total=Sum("valor_total"))["total"] or 0,
    }
    return render(request, "locacao/painel.html", contexto)


# --------------------------------------------------------------------------- UC01 — veículos

@login_required
def veiculos(request):
    qs = Veiculo.objects.select_related("categoria")
    status = request.GET.get("status", "")
    busca = request.GET.get("q", "").strip()
    if status:
        qs = qs.filter(status=status)
    if busca:
        qs = qs.filter(Q(placa__icontains=busca) | Q(modelo__icontains=busca) | Q(marca__icontains=busca))
    return render(request, "locacao/veiculos.html", {
        "veiculos": qs, "status": status, "busca": busca, "status_opcoes": StatusVeiculo.choices})


@login_required
def veiculo_form(request, pk=None):
    veiculo = get_object_or_404(Veiculo, pk=pk) if pk else None
    form = VeiculoForm(request.POST or None, instance=veiculo)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Veículo salvo com sucesso.")
        return redirect("locacao:veiculos")
    return render(request, "locacao/form.html", {
        "form": form, "titulo": "Editar veículo" if veiculo else "Novo veículo",
        "voltar": "locacao:veiculos"})


# --------------------------------------------------------------------------- UC02 — clientes

@login_required
def clientes(request):
    qs = Cliente.objects.all()
    busca = request.GET.get("q", "").strip()
    if busca:
        digitos = "".join(filter(str.isdigit, busca))
        filtro = Q(nome__icontains=busca)
        if digitos:
            filtro |= Q(cpf__contains=digitos)
        qs = qs.filter(filtro)
    return render(request, "locacao/clientes.html", {"clientes": qs, "busca": busca})


@login_required
def cliente_form(request, pk=None):
    cliente = get_object_or_404(Cliente, pk=pk) if pk else None
    form = ClienteForm(request.POST or None, instance=cliente)
    if request.method == "POST" and form.is_valid():
        cliente = form.save()
        messages.success(request, "Cliente salvo com sucesso.")
        return redirect("locacao:cliente_detalhe", pk=cliente.pk)
    return render(request, "locacao/form.html", {
        "form": form, "titulo": "Editar cliente" if cliente else "Novo cliente",
        "voltar": "locacao:clientes"})


@login_required
def cliente_detalhe(request, pk):
    operacoes.atualizar_status_temporais()
    cliente = get_object_or_404(Cliente, pk=pk)
    idade = rules.idade_na_data(cliente.data_nascimento, timezone.localdate())
    return render(request, "locacao/cliente_detalhe.html", {
        "cliente": cliente, "idade": idade,
        "reservas": cliente.reservas.select_related("veiculo"),
        "locacoes": cliente.locacoes.select_related("veiculo"),
    })


# --------------------------------------------------------------------------- UC03 — disponibilidade e reserva

@login_required
def disponibilidade(request):
    operacoes.atualizar_status_temporais()
    resultados = None
    if "retirada" in request.GET:
        form = BuscaDisponibilidadeForm(request.GET)
        if form.is_valid():
            dados = form.cleaned_data
            diarias = services.diarias_contratadas(dados["retirada"], dados["devolucao"])
            resultados = [
                (v, services.valor_previsto(diarias, v.categoria.valor_diaria))
                for v in operacoes.veiculos_disponiveis(dados["retirada"], dados["devolucao"], dados["categoria"])
            ]
            return render(request, "locacao/disponibilidade.html", {
                "form": form, "resultados": resultados, "diarias": diarias,
                "retirada": _local(dados["retirada"]), "devolucao": _local(dados["devolucao"])})
    else:
        inicio = timezone.localtime().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        form = BuscaDisponibilidadeForm(initial={"retirada": inicio, "devolucao": inicio + timedelta(days=1)})
    return render(request, "locacao/disponibilidade.html", {"form": form, "resultados": resultados})


def _ler_data_hora(texto):
    try:
        return timezone.make_aware(datetime.strptime(texto or "", FORMATO_DATA_HORA))
    except ValueError:
        return None


@login_required
def reserva_nova(request):
    dados = request.POST if request.method == "POST" else request.GET
    veiculo = Veiculo.objects.select_related("categoria").filter(pk=dados.get("veiculo") or 0).first()
    retirada, devolucao = _ler_data_hora(dados.get("retirada")), _ler_data_hora(dados.get("devolucao"))
    if veiculo is None or retirada is None or devolucao is None or devolucao <= retirada:
        return redirect("locacao:disponibilidade")

    diarias = services.diarias_contratadas(retirada, devolucao)
    resumo = {"retirada": retirada, "devolucao": devolucao, "diarias": diarias,
              "valor": services.valor_previsto(diarias, veiculo.categoria.valor_diaria)}
    form = ReservaForm(request.POST or None)
    resumo.update(retirada_txt=_local(retirada), devolucao_txt=_local(devolucao))
    if request.method == "POST" and form.is_valid():
        try:
            reserva = operacoes.criar_reserva(form.cleaned_data["cliente"], veiculo, retirada, devolucao)
        except RegraNegocioError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Reserva {reserva.codigo} confirmada.")
            return redirect("locacao:reserva_detalhe", pk=reserva.pk)
    return render(request, "locacao/reserva_nova.html", {"form": form, "veiculo": veiculo, "resumo": resumo})


@login_required
def reservas(request):
    operacoes.atualizar_status_temporais()
    qs = Reserva.objects.select_related("cliente", "veiculo")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "locacao/reservas.html", {
        "reservas": qs, "status": status, "status_opcoes": StatusReserva.choices})


@login_required
def reserva_detalhe(request, pk):
    operacoes.atualizar_status_temporais()
    reserva = get_object_or_404(Reserva.objects.select_related("cliente", "veiculo__categoria"), pk=pk)
    agora = timezone.now()
    multa = None
    if reserva.status == StatusReserva.ATIVA and rules.cancelamento_com_multa(reserva.retirada_prevista, agora):
        multa = services.multa_cancelamento(reserva.valor_estimado)
    return render(request, "locacao/reserva_detalhe.html", {
        "reserva": reserva, "multa_cancelamento": multa,
        "locacao": getattr(reserva, "locacao", None) if reserva.status == StatusReserva.CONVERTIDA else None})


@login_required
@require_POST
def reserva_cancelar(request, pk):
    reserva = get_object_or_404(Reserva, pk=pk)
    try:
        multa = operacoes.cancelar_reserva(reserva)
    except RegraNegocioError as erro:
        messages.error(request, str(erro))
    else:
        texto = f" Multa de cancelamento: R$ {multa}".replace(".", ",") if multa else " Sem multa."
        messages.success(request, f"Reserva {reserva.codigo} cancelada.{texto}")
    return redirect("locacao:reserva_detalhe", pk=pk)


# --------------------------------------------------------------------------- UC04 — retirada

@login_required
def retirada(request, pk):
    operacoes.atualizar_status_temporais()
    reserva = get_object_or_404(Reserva.objects.select_related("cliente", "veiculo__categoria"), pk=pk)
    if reserva.status != StatusReserva.ATIVA:
        messages.error(request, "RN13: só uma reserva com status ATIVA pode ser convertida em locação.")
        return redirect("locacao:reserva_detalhe", pk=pk)
    form = RetiradaForm(request.POST or None, initial={"km_saida": reserva.veiculo.km_atual})
    if request.method == "POST" and form.is_valid():
        try:
            locacao = operacoes.registrar_retirada(
                atendente=funcionario_do_usuario(request.user), reserva=reserva, **form.cleaned_data)
        except RegraNegocioError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Retirada registrada. Locação #{locacao.pk} em andamento.")
            return redirect("locacao:locacao_detalhe", pk=locacao.pk)
    return render(request, "locacao/retirada.html", {"form": form, "reserva": reserva})


@login_required
def locacao_balcao(request):
    """Locação sem reserva prévia (a associação Reserva–Locação é 0..1)."""
    operacoes.atualizar_status_temporais()
    agora = timezone.now()
    form = LocacaoBalcaoForm(request.POST or None, initial={"devolucao_prevista": timezone.localtime(agora) + timedelta(days=1)})
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        try:
            locacao = operacoes.registrar_retirada(
                atendente=funcionario_do_usuario(request.user), cliente=dados["cliente"],
                veiculo=dados["veiculo"], devolucao_prevista=dados["devolucao_prevista"],
                km_saida=dados["km_saida"], combustivel_saida=dados["combustivel_saida"])
        except RegraNegocioError as erro:
            messages.error(request, str(erro))
        else:
            messages.success(request, f"Locação #{locacao.pk} aberta no balcão.")
            return redirect("locacao:locacao_detalhe", pk=locacao.pk)
    return render(request, "locacao/form.html", {
        "form": form, "titulo": "Locação de balcão (sem reserva)", "voltar": "locacao:locacoes",
        "botao": "Registrar retirada"})


# --------------------------------------------------------------------------- UC05 — devolução

@login_required
def locacoes(request):
    operacoes.atualizar_status_temporais()
    qs = Locacao.objects.select_related("cliente", "veiculo", "atendente")
    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(status=status)
    return render(request, "locacao/locacoes.html", {
        "locacoes": qs, "status": status, "status_opcoes": StatusLocacao.choices})


@login_required
def locacao_detalhe(request, pk):
    operacoes.atualizar_status_temporais()
    locacao = get_object_or_404(
        Locacao.objects.select_related("cliente", "veiculo__categoria", "atendente", "reserva"), pk=pk)
    return render(request, "locacao/locacao_detalhe.html", {"locacao": locacao})


@login_required
def devolucao(request, pk):
    operacoes.atualizar_status_temporais()
    locacao = get_object_or_404(Locacao.objects.select_related("cliente", "veiculo__categoria"), pk=pk)
    if not locacao.em_aberto:
        messages.error(request, "RN19: esta locação já foi finalizada.")
        return redirect("locacao:locacao_detalhe", pk=pk)

    inicial = {"devolucao_real": timezone.localtime().replace(second=0, microsecond=0),
               "km_retorno": locacao.km_saida, "combustivel_retorno": locacao.combustivel_saida}
    form = DevolucaoForm(request.POST or None, initial=inicial)
    extrato = None
    if request.method == "POST" and form.is_valid():
        dados = form.cleaned_data
        if "confirmar" in request.POST:
            try:
                operacoes.registrar_devolucao(locacao, **dados)
            except RegraNegocioError as erro:
                messages.error(request, str(erro))
            else:
                messages.success(request, "Devolução registrada e locação finalizada.")
                return redirect("locacao:locacao_detalhe", pk=pk)
        try:
            rules.validar_km_retorno(locacao.km_saida, dados["km_retorno"])
        except RegraNegocioError as erro:
            form.add_error("km_retorno", str(erro))
        else:
            extrato = operacoes.apurar(locacao, dados["combustivel_retorno"], dados["devolucao_real"])
            extrato["avaria"] = dados["avaria"]
    return render(request, "locacao/devolucao.html", {"form": form, "locacao": locacao, "extrato": extrato})
