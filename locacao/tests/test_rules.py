"""Testes unitários das regras de negócio puras (RN01–RN19)."""

from datetime import date, datetime, timedelta

from django.test import SimpleTestCase

from locacao import rules
from locacao.enums import CategoriaCNH, StatusLocacao, StatusReserva
from locacao.rules import RegraNegocioError
from locacao.validators import cpf_valido

D = datetime(2026, 10, 10, 9, 0)
H = timedelta(hours=1)
EXISTENTE = [(D, D + 72 * H)]  # 10/10 09:00 → 13/10 09:00


class SobreposicaoTests(SimpleTestCase):
    """RN06 — a regra mais importante do sistema."""

    def test_sobreposicao_total(self):
        self.assertTrue(rules.ha_sobreposicao(D - 24 * H, D + 96 * H, EXISTENTE))

    def test_novo_periodo_dentro_do_existente(self):
        self.assertTrue(rules.ha_sobreposicao(D + 24 * H, D + 48 * H, EXISTENTE))

    def test_parcial_no_inicio(self):
        self.assertTrue(rules.ha_sobreposicao(D - 24 * H, D + 1 * H, EXISTENTE))

    def test_parcial_no_fim(self):
        self.assertTrue(rules.ha_sobreposicao(D + 71 * H, D + 100 * H, EXISTENTE))

    def test_encaixe_exato_antes_nao_conflita(self):
        self.assertFalse(rules.ha_sobreposicao(D - 24 * H, D, EXISTENTE))

    def test_encaixe_exato_depois_nao_conflita(self):
        self.assertFalse(rules.ha_sobreposicao(D + 72 * H, D + 96 * H, EXISTENTE))

    def test_sem_conflito(self):
        self.assertFalse(rules.ha_sobreposicao(D + 200 * H, D + 300 * H, EXISTENTE))

    def test_sem_periodos_existentes(self):
        self.assertFalse(rules.ha_sobreposicao(D, D + H, []))


class ClienteTests(SimpleTestCase):
    def assertRegra(self, codigo, funcao, *args):
        with self.assertRaises(RegraNegocioError) as ctx:
            funcao(*args)
        self.assertEqual(ctx.exception.codigo, codigo)

    def test_rn01_idade_minima(self):
        rules.validar_idade(date(2005, 10, 10), date(2026, 10, 10))  # faz 21 no dia
        self.assertRegra("RN01", rules.validar_idade, date(2005, 10, 11), date(2026, 10, 10))

    def test_rn02_categoria_da_cnh(self):
        rules.validar_cnh(CategoriaCNH.B, date(2030, 1, 1), date(2026, 10, 13))
        rules.validar_cnh(CategoriaCNH.E, date(2030, 1, 1), date(2026, 10, 13))
        self.assertRegra("RN02", rules.validar_cnh, CategoriaCNH.A, date(2030, 1, 1), date(2026, 10, 13))

    def test_rn02_validade_ate_a_devolucao(self):
        rules.validar_cnh(CategoriaCNH.B, date(2026, 10, 13), date(2026, 10, 13))
        self.assertRegra("RN02", rules.validar_cnh, CategoriaCNH.B, date(2026, 10, 12), date(2026, 10, 13))

    def test_rn03_cliente_inativo(self):
        self.assertRegra("RN03", rules.validar_cliente_ativo, False)

    def test_rn04_cliente_com_atraso(self):
        self.assertRegra("RN04", rules.validar_sem_atraso, True)

    def test_cpf(self):
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertFalse(cpf_valido("529.982.247-24"))
        self.assertFalse(cpf_valido("111.111.111-11"))


class ReservaTests(SimpleTestCase):
    def assertRegra(self, codigo, *args):
        with self.assertRaises(RegraNegocioError) as ctx:
            rules.validar_periodo(*args)
        self.assertEqual(ctx.exception.codigo, codigo)

    def test_periodo_valido_retorna_diarias(self):
        self.assertEqual(rules.validar_periodo(D, D + 72 * H, D), 3)

    def test_rn08_maximo_de_30_diarias(self):
        self.assertEqual(rules.validar_periodo(D, D + 30 * 24 * H, D), 30)
        self.assertRegra("RN08", D, D + 30 * 24 * H + H, D)

    def test_rn09_retirada_no_passado(self):
        self.assertRegra("RN09", D - H, D + 24 * H, D)

    def test_rn10_devolucao_antes_da_retirada(self):
        self.assertRegra("RN10", D, D, D)

    def test_rn11_cancelamento(self):
        self.assertFalse(rules.cancelamento_com_multa(D + 24 * H, D))
        self.assertTrue(rules.cancelamento_com_multa(D + 23 * H, D))

    def test_rn12_expiracao(self):
        self.assertFalse(rules.reserva_expirada(StatusReserva.ATIVA, D, D + 4 * H))
        self.assertTrue(rules.reserva_expirada(StatusReserva.ATIVA, D, D + 4 * H + timedelta(seconds=1)))
        self.assertFalse(rules.reserva_expirada(StatusReserva.CONVERTIDA, D, D + 10 * H))


class RetiradaDevolucaoTests(SimpleTestCase):
    def test_rn13_so_reserva_ativa(self):
        rules.validar_reserva_convertivel(StatusReserva.ATIVA)
        for status in (StatusReserva.CANCELADA, StatusReserva.EXPIRADA, StatusReserva.CONVERTIDA):
            with self.assertRaises(RegraNegocioError):
                rules.validar_reserva_convertivel(status)

    def test_rn14_exige_km_e_combustivel(self):
        with self.assertRaises(RegraNegocioError):
            rules.validar_dados_saida(None, "CHEIO", 0)
        with self.assertRaises(RegraNegocioError):
            rules.validar_dados_saida(100, "", 0)

    def test_rn16_km_de_retorno(self):
        rules.validar_km_retorno(1000, 1000)
        with self.assertRaises(RegraNegocioError):
            rules.validar_km_retorno(1000, 999)

    def test_atrasada_por_avaliacao_preguicosa(self):
        efetivo = rules.status_locacao_efetivo
        self.assertEqual(efetivo(StatusLocacao.EM_ANDAMENTO, D, D + 60 * timedelta(minutes=1)),
                         StatusLocacao.EM_ANDAMENTO)
        self.assertEqual(efetivo(StatusLocacao.EM_ANDAMENTO, D, D + 61 * timedelta(minutes=1)),
                         StatusLocacao.ATRASADA)
