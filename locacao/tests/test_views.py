"""Testes de integração: operações com banco e fluxo completo pela interface."""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from locacao import operacoes
from locacao.enums import CategoriaCNH, NivelCombustivel, StatusLocacao, StatusReserva, StatusVeiculo
from locacao.forms import FORMATO_DATA_HORA
from locacao.models import Categoria, Cliente, Funcionario, Locacao, Reserva, Veiculo
from locacao.rules import RegraNegocioError

H = timedelta(hours=1)
DIA = timedelta(days=1)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.categoria = Categoria.objects.create(nome="Econômico", valor_diaria=Decimal("120.00"),
                                                 valor_caucao=Decimal("500.00"),
                                                 valor_tanque_cheio=Decimal("300.00"))
        cls.usuario = User.objects.create_user("atendente", password="senha-teste")
        cls.atendente = Funcionario.objects.create(usuario=cls.usuario, nome="Rafael", matricula="F1")

    def setUp(self):
        self.agora = timezone.now().replace(second=0, microsecond=0)
        self.cliente = self.novo_cliente()
        self.veiculo = self.novo_veiculo("ABC1D23")

    def novo_cliente(self, cpf="52998224725", **extra):
        dados = dict(nome="Ana Souza", cpf=cpf, data_nascimento=date(1990, 5, 12), cnh_numero="01234567890",
                     cnh_categoria=CategoriaCNH.B, cnh_validade=date.today() + 365 * DIA)
        dados.update(extra)
        return Cliente.objects.create(**dados)

    def novo_veiculo(self, placa, chassi=None):
        return Veiculo.objects.create(placa=placa, chassi=chassi or f"9BWZZZ377VT{placa[-6:]}", marca="Fiat",
                                      modelo="Mobi", ano_fabricacao=2023, km_atual=32100, categoria=self.categoria)

    def reservar(self, inicio_h=2, fim_h=74, cliente=None, veiculo=None):
        return operacoes.criar_reserva(cliente or self.cliente, veiculo or self.veiculo,
                                       self.agora + inicio_h * H, self.agora + fim_h * H, agora=self.agora)

    def assertRegra(self, codigo, funcao, *args, **kwargs):
        with self.assertRaises(RegraNegocioError) as ctx:
            funcao(*args, **kwargs)
        self.assertEqual(ctx.exception.codigo, codigo)


class DisponibilidadeTests(Base):
    def test_rn06_reserva_sobreposta_e_recusada(self):
        self.reservar(2, 74)
        outro = self.novo_cliente(cpf="11144477735")
        self.assertRegra("RN06", self.reservar, 50, 100, cliente=outro)

    def test_reserva_em_sequencia_e_aceita(self):
        self.reservar(2, 74)
        self.reservar(74, 98, cliente=self.novo_cliente(cpf="11144477735"))

    def test_rn05_rn07_busca_ignora_manutencao_inativo_e_reservados(self):
        manutencao = self.novo_veiculo("MAN1A11")
        manutencao.status = StatusVeiculo.MANUTENCAO
        manutencao.save()
        inativo = self.novo_veiculo("INA1A11")
        inativo.status = StatusVeiculo.INATIVO
        inativo.save()
        livre = self.novo_veiculo("LIV1A11")
        self.reservar(2, 74)
        disponiveis = operacoes.veiculos_disponiveis(self.agora + 10 * H, self.agora + 20 * H)
        self.assertEqual(list(disponiveis), [livre])

    def test_rn05_veiculo_em_manutencao_nao_pode_ser_reservado(self):
        self.veiculo.status = StatusVeiculo.MANUTENCAO
        self.veiculo.save()
        self.assertRegra("RN05", self.reservar)


class ReservaTests(Base):
    def test_valor_estimado(self):
        self.assertEqual(self.reservar(2, 74).valor_estimado, Decimal("360.00"))

    def test_rn01_cliente_menor_de_21(self):
        jovem = self.novo_cliente(cpf="11144477735", data_nascimento=date.today() - 20 * 365 * DIA)
        self.assertRegra("RN01", self.reservar, cliente=jovem)

    def test_rn02_cnh_categoria_a(self):
        moto = self.novo_cliente(cpf="11144477735", cnh_categoria=CategoriaCNH.A)
        self.assertRegra("RN02", self.reservar, cliente=moto)

    def test_rn03_cliente_inativo(self):
        self.cliente.ativo = False
        self.cliente.save()
        self.assertRegra("RN03", self.reservar)

    def test_rn04_cliente_com_locacao_atrasada(self):
        operacoes.registrar_retirada(atendente=self.atendente, cliente=self.cliente, veiculo=self.veiculo,
                                     devolucao_prevista=self.agora - DIA, km_saida=32100,
                                     combustivel_saida=NivelCombustivel.CHEIO, agora=self.agora - 3 * DIA)
        operacoes.atualizar_status_temporais(self.agora)
        self.assertRegra("RN04", self.reservar, veiculo=self.novo_veiculo("OUT1A11"))

    def test_rn08_mais_de_30_dias(self):
        self.assertRegra("RN08", self.reservar, 2, 2 + 31 * 24)

    def test_rn11_cancelamento_livre_e_com_multa(self):
        livre = self.reservar(48, 120)
        self.assertEqual(operacoes.cancelar_reserva(livre, agora=self.agora), Decimal("0.00"))
        tardia = self.reservar(10, 82)
        self.assertEqual(operacoes.cancelar_reserva(tardia, agora=self.agora), Decimal("72.00"))
        tardia.refresh_from_db()
        self.assertEqual(tardia.status, StatusReserva.CANCELADA)

    def test_rn12_reserva_expira_e_libera_veiculo(self):
        reserva = self.reservar(2, 74)
        operacoes.atualizar_status_temporais(self.agora + 6 * H + timedelta(seconds=1))
        reserva.refresh_from_db()
        self.assertEqual(reserva.status, StatusReserva.EXPIRADA)
        self.assertIn(self.veiculo, operacoes.veiculos_disponiveis(self.agora + 10 * H, self.agora + 20 * H))


class RetiradaDevolucaoTests(Base):
    def retirar(self, reserva, agora=None):
        return operacoes.registrar_retirada(atendente=self.atendente, reserva=reserva, km_saida=32100,
                                            combustivel_saida=NivelCombustivel.CHEIO,
                                            agora=agora or self.agora + 2 * H)

    def test_rn15_retirada_muda_estados_e_registra_caucao(self):
        reserva = self.reservar()
        locacao = self.retirar(reserva)
        reserva.refresh_from_db()
        self.veiculo.refresh_from_db()
        self.assertEqual(reserva.status, StatusReserva.CONVERTIDA)
        self.assertEqual(self.veiculo.status, StatusVeiculo.LOCADO)
        self.assertEqual(locacao.valor_caucao, Decimal("500.00"))
        self.assertEqual(locacao.valor_diaria_aplicado, Decimal("120.00"))

    def test_rn13_reserva_convertida_nao_pode_ser_retirada_de_novo(self):
        reserva = self.reservar()
        self.retirar(reserva)
        self.assertRegra("RN13", self.retirar, reserva)

    def test_snapshot_de_preco(self):
        locacao = self.retirar(self.reservar())
        self.categoria.valor_diaria = Decimal("999.00")
        self.categoria.save()
        locacao.refresh_from_db()
        self.assertEqual(locacao.valor_diaria_aplicado, Decimal("120.00"))

    def test_exemplo_do_documento_e_rn18_sem_avaria(self):
        locacao = self.retirar(self.reservar())
        devolucao_real = locacao.devolucao_prevista + 5 * H
        extrato = operacoes.registrar_devolucao(
            locacao, km_retorno=32740, combustivel_retorno=NivelCombustivel.METADE,
            devolucao_real=devolucao_real, agora=devolucao_real)
        self.assertEqual(extrato["total"], Decimal("690.00"))
        locacao.refresh_from_db()
        self.veiculo.refresh_from_db()
        self.assertEqual(locacao.status, StatusLocacao.FINALIZADA)
        self.assertEqual(self.veiculo.status, StatusVeiculo.DISPONIVEL)
        self.assertEqual(self.veiculo.km_atual, 32740)

    def test_rn18_avaria_manda_para_manutencao(self):
        locacao = self.retirar(self.reservar())
        operacoes.registrar_devolucao(locacao, km_retorno=32200, combustivel_retorno=NivelCombustivel.CHEIO,
                                      avaria=True, descricao_avaria="Para-choque amassado",
                                      agora=self.agora + 10 * H)
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.status, StatusVeiculo.MANUTENCAO)

    def test_rn16_km_de_retorno_menor(self):
        locacao = self.retirar(self.reservar())
        self.assertRegra("RN16", operacoes.registrar_devolucao, locacao, km_retorno=32000,
                         combustivel_retorno=NivelCombustivel.CHEIO, agora=self.agora + 10 * H)

    def test_rn19_locacao_finalizada_e_imutavel(self):
        locacao = self.retirar(self.reservar())
        operacoes.registrar_devolucao(locacao, km_retorno=32200, combustivel_retorno=NivelCombustivel.CHEIO,
                                      agora=self.agora + 10 * H)
        self.assertRegra("RN19", operacoes.registrar_devolucao, locacao, km_retorno=32300,
                         combustivel_retorno=NivelCombustivel.CHEIO, agora=self.agora + 11 * H)
        locacao.refresh_from_db()
        locacao.valor_total = Decimal("1.00")
        with self.assertRaises(ValidationError):
            locacao.save()

    def test_locacao_de_balcao_sem_reserva(self):
        locacao = operacoes.registrar_retirada(
            atendente=self.atendente, cliente=self.cliente, veiculo=self.veiculo,
            devolucao_prevista=self.agora + 2 * DIA, km_saida=32100,
            combustivel_saida=NivelCombustivel.CHEIO, agora=self.agora)
        self.assertIsNone(locacao.reserva)

    def test_balcao_respeita_reserva_existente(self):
        self.reservar(24, 72)
        self.assertRegra("RN06", operacoes.registrar_retirada, atendente=self.atendente, cliente=self.cliente,
                         veiculo=self.veiculo, devolucao_prevista=self.agora + 48 * H, km_saida=32100,
                         combustivel_saida=NivelCombustivel.CHEIO, agora=self.agora)

    def test_atrasada_por_tempo(self):
        locacao = self.retirar(self.reservar())
        operacoes.atualizar_status_temporais(locacao.devolucao_prevista + 61 * timedelta(minutes=1))
        locacao.refresh_from_db()
        self.assertEqual(locacao.status, StatusLocacao.ATRASADA)


class InterfaceTests(Base):
    def setUp(self):
        super().setUp()
        self.client.login(username="atendente", password="senha-teste")

    def test_login_obrigatorio(self):
        self.client.logout()
        resposta = self.client.get(reverse("locacao:painel"))
        self.assertRedirects(resposta, reverse("login") + "?next=/")

    def test_paginas_carregam(self):
        for nome in ["painel", "veiculos", "veiculo_novo", "clientes", "cliente_novo", "disponibilidade",
                     "reservas", "locacoes", "locacao_balcao"]:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(f"locacao:{nome}")).status_code, 200)

    def test_cadastro_de_cliente_valida_cpf(self):
        resposta = self.client.post(reverse("locacao:cliente_novo"), {
            "nome": "Teste", "cpf": "123.456.789-00", "data_nascimento": "1990-01-01",
            "cnh_numero": "12345678901", "cnh_categoria": "B", "cnh_validade": "2030-01-01", "ativo": "on"})
        self.assertContains(resposta, "CPF inválido")

    def test_ciclo_completo_pela_interface(self):
        inicio = timezone.localtime(self.agora + 2 * H)
        fim = inicio + 3 * DIA
        params = {"retirada": inicio.strftime(FORMATO_DATA_HORA), "devolucao": fim.strftime(FORMATO_DATA_HORA)}

        # UC03: busca e reserva
        busca = self.client.get(reverse("locacao:disponibilidade"), params)
        self.assertContains(busca, "ABC1D23")
        self.assertContains(busca, "R$ 360,00")
        resposta = self.client.post(reverse("locacao:reserva_nova"),
                                    {**params, "veiculo": self.veiculo.pk, "cliente": self.cliente.pk})
        reserva = Reserva.objects.get()
        self.assertRedirects(resposta, reverse("locacao:reserva_detalhe", args=[reserva.pk]))

        # RN06 pela interface: segunda reserva sobreposta recusada
        outro = self.novo_cliente(cpf="11144477735", nome="Carlos")
        resposta = self.client.post(reverse("locacao:reserva_nova"),
                                    {**params, "veiculo": self.veiculo.pk, "cliente": outro.pk}, follow=True)
        self.assertContains(resposta, "RN06")
        self.assertEqual(Reserva.objects.count(), 1)

        # UC04: retirada
        resposta = self.client.post(reverse("locacao:retirada", args=[reserva.pk]),
                                    {"km_saida": 32100, "combustivel_saida": "CHEIO"})
        locacao = Locacao.objects.get()
        self.assertRedirects(resposta, reverse("locacao:locacao_detalhe", args=[locacao.pk]))

        # UC05: devolução 5 h depois do previsto, com meio tanque → R$ 690,00
        Locacao.objects.filter(pk=locacao.pk).update(
            data_retirada=self.agora - 3 * DIA - 5 * H, devolucao_prevista=self.agora - 5 * H)
        dados = {"devolucao_real": timezone.localtime(self.agora).strftime(FORMATO_DATA_HORA),
                 "km_retorno": 32740, "combustivel_retorno": "METADE"}
        previa = self.client.post(reverse("locacao:devolucao", args=[locacao.pk]), {**dados, "calcular": ""})
        self.assertContains(previa, "R$ 690,00")
        self.client.post(reverse("locacao:devolucao", args=[locacao.pk]), {**dados, "confirmar": ""})
        locacao.refresh_from_db()
        self.assertEqual(locacao.status, StatusLocacao.FINALIZADA)
        self.assertEqual(locacao.valor_total, Decimal("690.00"))
        self.assertEqual(locacao.atendente, self.atendente)
