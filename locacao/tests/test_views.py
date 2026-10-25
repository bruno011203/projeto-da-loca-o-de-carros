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

    def test_todas_as_telas_exigem_login(self):
        self.client.logout()
        rotas = ["painel", "veiculos", "veiculo_novo", "clientes", "cliente_novo", "disponibilidade", "reservas",
                 "reserva_nova", "locacoes", "locacao_balcao"]
        com_id = ["veiculo_editar", "cliente_detalhe", "cliente_editar", "reserva_detalhe", "reserva_cancelar",
                  "retirada", "locacao_detalhe", "devolucao"]
        urls = [reverse(f"locacao:{n}") for n in rotas] + [reverse(f"locacao:{n}", args=[1]) for n in com_id]
        for url in urls:
            with self.subTest(url=url):
                resposta = self.client.post(url) if url.endswith("/cancelar/") else self.client.get(url)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta["Location"].startswith(reverse("login")))

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


class TelasDeOperacaoTests(Base):
    """Telas de reserva, retirada, balcão e devolução, incluindo os caminhos de erro."""

    def setUp(self):
        super().setUp()
        self.client.login(username="atendente", password="senha-teste")

    def datas(self, inicio_h, fim_h):
        return {"retirada": timezone.localtime(self.agora + inicio_h * H).strftime(FORMATO_DATA_HORA),
                "devolucao": timezone.localtime(self.agora + fim_h * H).strftime(FORMATO_DATA_HORA)}

    def test_reserva_com_parametros_invalidos_volta_para_a_busca(self):
        for params in [{}, {"veiculo": "abc", **self.datas(2, 26)}, {"veiculo": 9999, **self.datas(2, 26)},
                       {"veiculo": self.veiculo.pk, "retirada": "lixo", "devolucao": "lixo"}]:
            with self.subTest(params=params):
                self.assertRedirects(self.client.get(reverse("locacao:reserva_nova"), params),
                                     reverse("locacao:disponibilidade"))

    def test_busca_aplica_rn08_rn09_rn10(self):
        casos = {"RN08": self.datas(2, 2 + 31 * 24), "RN09": self.datas(-48, 24), "RN10": self.datas(26, 2)}
        for codigo, params in casos.items():
            with self.subTest(regra=codigo):
                self.assertContains(self.client.get(reverse("locacao:disponibilidade"), params), codigo)

    def test_reserva_exibe_erro_de_regra(self):
        jovem = self.novo_cliente(cpf="11144477735", data_nascimento=date.today() - 20 * 365 * DIA)
        resposta = self.client.post(reverse("locacao:reserva_nova"),
                                    {**self.datas(2, 26), "veiculo": self.veiculo.pk, "cliente": jovem.pk})
        self.assertContains(resposta, "RN01")
        self.assertFalse(Reserva.objects.exists())

    def test_cancelamento_pela_tela(self):
        reserva = self.reservar(48, 120)
        self.assertEqual(self.client.get(reverse("locacao:reserva_cancelar", args=[reserva.pk])).status_code, 405)
        resposta = self.client.post(reverse("locacao:reserva_cancelar", args=[reserva.pk]), follow=True)
        self.assertContains(resposta, "Sem multa")
        resposta = self.client.post(reverse("locacao:reserva_cancelar", args=[reserva.pk]), follow=True)
        self.assertContains(resposta, "RN11")

    def test_detalhe_da_reserva_avisa_multa_de_cancelamento(self):
        reserva = operacoes.criar_reserva(self.cliente, self.veiculo, timezone.now() + 2 * H,
                                          timezone.now() + 26 * H)
        self.assertContains(self.client.get(reverse("locacao:reserva_detalhe", args=[reserva.pk])), "RN11")

    def test_retirada_pela_tela_valida_km(self):
        reserva = operacoes.criar_reserva(self.cliente, self.veiculo, timezone.now() + H, timezone.now() + 26 * H)
        url = reverse("locacao:retirada", args=[reserva.pk])
        self.assertContains(self.client.get(url), "32100")
        self.assertContains(self.client.post(url, {"km_saida": 100, "combustivel_saida": "CHEIO"}), "RN14")
        self.assertRedirects(self.client.post(url, {"km_saida": 32100, "combustivel_saida": "CHEIO"}),
                             reverse("locacao:locacao_detalhe", args=[Locacao.objects.get().pk]))
        # reserva já convertida não pode ser retirada de novo (RN13)
        self.assertRedirects(self.client.get(url), reverse("locacao:reserva_detalhe", args=[reserva.pk]))

    def test_locacao_de_balcao_pela_tela(self):
        url = reverse("locacao:locacao_balcao")
        dados = {"cliente": self.cliente.pk, "veiculo": self.veiculo.pk, "km_saida": 32100,
                 "combustivel_saida": "CHEIO",
                 "devolucao_prevista": timezone.localtime(timezone.now() - DIA).strftime(FORMATO_DATA_HORA)}
        self.assertContains(self.client.post(url, dados), "RN10")
        dados["devolucao_prevista"] = timezone.localtime(timezone.now() + DIA).strftime(FORMATO_DATA_HORA)
        resposta = self.client.post(url, dados)
        locacao = Locacao.objects.get()
        self.assertRedirects(resposta, reverse("locacao:locacao_detalhe", args=[locacao.pk]))
        self.assertEqual(locacao.atendente, self.atendente)

    def test_devolucao_logo_apos_a_retirada(self):
        """Regressão: devolver no mesmo minuto da retirada dava erro RN16 por causa dos segundos."""
        url = reverse("locacao:locacao_balcao")
        self.client.post(url, {"cliente": self.cliente.pk, "veiculo": self.veiculo.pk, "km_saida": 32100,
                               "combustivel_saida": "CHEIO", "devolucao_prevista":
                               timezone.localtime(timezone.now() + DIA).strftime(FORMATO_DATA_HORA)})
        locacao = Locacao.objects.get()
        self.assertEqual(locacao.data_retirada.second, 0)
        agora_txt = timezone.localtime().strftime(FORMATO_DATA_HORA)
        self.client.post(reverse("locacao:devolucao", args=[locacao.pk]), {
            "devolucao_real": agora_txt, "km_retorno": 32150, "combustivel_retorno": "CHEIO", "confirmar": ""})
        locacao.refresh_from_db()
        self.assertEqual(locacao.status, StatusLocacao.FINALIZADA)
        self.assertEqual(locacao.valor_total, Decimal("120.00"))

    def test_devolucao_valida_data_km_e_avaria_antes_do_extrato(self):
        locacao = operacoes.registrar_retirada(
            atendente=self.atendente, cliente=self.cliente, veiculo=self.veiculo,
            devolucao_prevista=timezone.now() + DIA, km_saida=32100, combustivel_saida=NivelCombustivel.CHEIO,
            agora=timezone.now() - DIA)
        url = reverse("locacao:devolucao", args=[locacao.pk])
        agora_txt = timezone.localtime().strftime(FORMATO_DATA_HORA)
        base = {"devolucao_real": agora_txt, "km_retorno": 32200, "combustivel_retorno": "CHEIO"}
        antes = timezone.localtime(timezone.now() - 3 * DIA).strftime(FORMATO_DATA_HORA)
        futuro = timezone.localtime(timezone.now() + DIA).strftime(FORMATO_DATA_HORA)
        casos = [
            ({"devolucao_real": antes}, "RN16: a data de devolução"),
            ({"devolucao_real": futuro}, "não pode estar no futuro"),
            ({"km_retorno": 100}, "RN16: a quilometragem"),
            ({"avaria": "on"}, "Descreva a avaria"),
        ]
        for extra, mensagem in casos:
            with self.subTest(mensagem=mensagem):
                resposta = self.client.post(url, {**base, **extra, "confirmar": ""})
                self.assertContains(resposta, mensagem)
                self.assertNotContains(resposta, "Diárias contratadas")
        locacao.refresh_from_db()
        self.assertEqual(locacao.status, StatusLocacao.EM_ANDAMENTO)

    def test_devolucao_de_locacao_finalizada_redireciona(self):
        locacao = operacoes.registrar_retirada(
            atendente=self.atendente, cliente=self.cliente, veiculo=self.veiculo,
            devolucao_prevista=timezone.now() + DIA, km_saida=32100, combustivel_saida=NivelCombustivel.CHEIO,
            agora=timezone.now() - H)
        operacoes.registrar_devolucao(locacao, km_retorno=32200, combustivel_retorno=NivelCombustivel.CHEIO)
        resposta = self.client.get(reverse("locacao:devolucao", args=[locacao.pk]), follow=True)
        self.assertContains(resposta, "RN19")

    def test_detalhes_listas_e_filtros(self):
        reserva = self.reservar()
        locacao = operacoes.registrar_retirada(atendente=self.atendente, reserva=reserva, km_saida=32100,
                                               combustivel_saida=NivelCombustivel.CHEIO, agora=self.agora + 2 * H)
        urls = [reverse("locacao:locacao_detalhe", args=[locacao.pk]),
                reverse("locacao:reserva_detalhe", args=[reserva.pk]),
                reverse("locacao:cliente_detalhe", args=[self.cliente.pk]),
                reverse("locacao:veiculo_editar", args=[self.veiculo.pk]),
                reverse("locacao:cliente_editar", args=[self.cliente.pk]),
                reverse("locacao:locacoes") + "?status=EM_ANDAMENTO",
                reverse("locacao:reservas") + "?status=CONVERTIDA",
                reverse("locacao:veiculos") + "?status=LOCADO&q=abc",
                reverse("locacao:clientes") + "?q=529.982"]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        for url in ["/locacoes/9999/", "/reservas/9999/", "/clientes/9999/", "/veiculos/9999/editar/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)


class CadastrosTests(Base):
    """UC01 e UC02 pelas telas e pelo Django Admin."""

    VEICULO = {"marca": "Fiat", "modelo": "Uno", "ano_fabricacao": 2020, "cor": "Branco", "km_atual": 10,
               "status": "DISPONIVEL"}
    CLIENTE = {"nome": "Teste", "data_nascimento": "1990-01-01", "cnh_numero": "12345678901",
               "cnh_categoria": "B", "cnh_validade": "2030-01-01", "ativo": "on"}

    def setUp(self):
        super().setUp()
        self.client.login(username="atendente", password="senha-teste")

    def test_placa_com_hifen_e_minusculas_e_normalizada(self):
        """Regressão: "ABC-1D99" era recusada por ter 8 caracteres."""
        resposta = self.client.post(reverse("locacao:veiculo_novo"), {
            **self.VEICULO, "categoria": self.categoria.pk, "placa": "abc-1d99", "chassi": "9bwzzz377vt999991"})
        self.assertRedirects(resposta, reverse("locacao:veiculos"))
        self.assertTrue(Veiculo.objects.filter(placa="ABC1D99", chassi="9BWZZZ377VT999991").exists())

    def test_veiculo_invalido(self):
        casos = [({"placa": "AB12345"}, "ABC1234 ou ABC1D23"), ({"ano_fabricacao": 2099}, "Ano de fabricação"),
                 ({"placa": "ABC1D23"}, "já existe")]
        for extra, mensagem in casos:
            with self.subTest(mensagem=mensagem):
                dados = {**self.VEICULO, "categoria": self.categoria.pk, "placa": "XYZ1A23",
                         "chassi": "9BWZZZ377VT999992", **extra}
                self.assertContains(self.client.post(reverse("locacao:veiculo_novo"), dados), mensagem)

    def test_km_nao_pode_ser_reduzida_e_locado_nao_muda_status(self):
        url = reverse("locacao:veiculo_editar", args=[self.veiculo.pk])
        dados = {**self.VEICULO, "categoria": self.categoria.pk, "placa": self.veiculo.placa,
                 "chassi": self.veiculo.chassi, "km_atual": 1}
        self.assertContains(self.client.post(url, dados), "não pode ser reduzida")
        self.veiculo.status = StatusVeiculo.LOCADO
        self.veiculo.save()
        self.client.post(url, {**dados, "km_atual": 40000, "status": "DISPONIVEL"})
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.status, StatusVeiculo.LOCADO)

    def test_cliente_com_cpf_formatado_e_nascimento_futuro(self):
        url = reverse("locacao:cliente_novo")
        self.assertContains(self.client.post(url, {**self.CLIENTE, "cpf": "248.438.034-80",
                                                   "data_nascimento": "2090-01-01"}), "deve estar no passado")
        self.assertContains(self.client.post(url, {**self.CLIENTE, "cpf": "529.982.247-25"}), "já existe")
        self.client.post(url, {**self.CLIENTE, "cpf": "248.438.034-80"})
        self.assertTrue(Cliente.objects.filter(cpf="24843803480").exists())

    def test_admin_usa_as_mesmas_validacoes(self):
        User.objects.create_superuser("chefe", password="senha-teste")
        self.client.login(username="chefe", password="senha-teste")
        self.client.post("/admin/locacao/cliente/add/", {**self.CLIENTE, "cpf": "248.438.034-80"})
        self.assertTrue(Cliente.objects.filter(cpf="24843803480").exists())
        self.client.post("/admin/locacao/veiculo/add/", {
            **self.VEICULO, "categoria": self.categoria.pk, "placa": "xyz-1a23", "chassi": "9BWZZZ377VT999993"})
        self.assertTrue(Veiculo.objects.filter(placa="XYZ1A23").exists())
        # status LOCADO só pode ser definido pela retirada (RN15)
        self.client.post(f"/admin/locacao/veiculo/{self.veiculo.pk}/change/", {
            **self.VEICULO, "categoria": self.categoria.pk, "placa": self.veiculo.placa,
            "chassi": self.veiculo.chassi, "km_atual": 32100, "status": "LOCADO"})
        self.veiculo.refresh_from_db()
        self.assertEqual(self.veiculo.status, StatusVeiculo.DISPONIVEL)
        for url in ["/admin/", "/admin/locacao/locacao/", "/admin/locacao/reserva/", "/admin/auth/user/"]:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_atendente_nao_acessa_o_admin(self):
        self.assertEqual(self.client.get("/admin/").status_code, 302)


class SeedTests(TestCase):
    def test_seed_cria_dados_e_reproduz_o_exemplo_do_documento(self):
        from io import StringIO

        from django.core.management import call_command
        call_command("seed", stdout=StringIO())
        self.assertEqual(Veiculo.objects.count(), 10)
        self.assertEqual(Locacao.objects.filter(status=StatusLocacao.FINALIZADA).get().valor_total,
                         Decimal("690.00"))
        self.assertTrue(Locacao.objects.filter(status=StatusLocacao.ATRASADA).exists())
        call_command("seed", stdout=StringIO())  # segunda vez não duplica
        self.assertEqual(Veiculo.objects.count(), 10)
        call_command("seed", "--reset", stdout=StringIO())
        self.assertEqual(Veiculo.objects.count(), 10)
        self.assertTrue(self.client.login(username="gerente", password="locadora123"))
