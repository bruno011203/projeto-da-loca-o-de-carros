"""Testes unitários das fórmulas de cálculo (base da pirâmide)."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.test import SimpleTestCase

from locacao import services
from locacao.enums import NivelCombustivel as N

RETIRADA = datetime(2026, 10, 10, 9, 0)
PREVISTA = datetime(2026, 10, 13, 9, 0)


class DiariasContratadasTests(SimpleTestCase):
    def test_periodo_exato(self):
        self.assertEqual(services.diarias_contratadas(RETIRADA, PREVISTA), 3)

    def test_fracao_de_24h_conta_diaria_cheia(self):
        self.assertEqual(services.diarias_contratadas(RETIRADA, PREVISTA + timedelta(minutes=1)), 4)

    def test_minimo_de_uma_diaria(self):
        self.assertEqual(services.diarias_contratadas(RETIRADA, RETIRADA + timedelta(hours=2)), 1)


class DiariasDeAtrasoTests(SimpleTestCase):
    def test_dentro_da_tolerancia_nao_gera_atraso(self):
        self.assertEqual(services.diarias_de_atraso(PREVISTA, PREVISTA + timedelta(minutes=60)), 0)

    def test_um_minuto_apos_tolerancia_gera_uma_diaria(self):
        self.assertEqual(services.diarias_de_atraso(PREVISTA, PREVISTA + timedelta(minutes=61)), 1)

    def test_devolucao_antecipada_nao_gera_atraso(self):
        self.assertEqual(services.diarias_de_atraso(PREVISTA, PREVISTA - timedelta(days=1)), 0)

    def test_varios_blocos_de_atraso(self):
        # 2 dias e 2 horas de atraso − 1 h de tolerância = 2 dias e 1 h → 3 diárias
        self.assertEqual(services.diarias_de_atraso(PREVISTA, PREVISTA + timedelta(days=2, hours=2)), 3)


class ValoresTests(SimpleTestCase):
    def test_valor_previsto(self):
        self.assertEqual(services.valor_previsto(3, Decimal("120.00")), Decimal("360.00"))

    def test_multa_e_cinquenta_por_cento_mais_cara(self):
        self.assertEqual(services.valor_multa(2, Decimal("120.00")), Decimal("360.00"))

    def test_taxa_combustivel(self):
        self.assertEqual(services.taxa_combustivel(N.CHEIO, N.METADE, Decimal("300")), Decimal("150.00"))

    def test_combustivel_devolvido_mais_cheio_nao_gera_credito(self):
        self.assertEqual(services.taxa_combustivel(N.METADE, N.CHEIO, Decimal("300")), Decimal("0.00"))

    def test_arredondamento_half_up(self):
        # 1 quarto de R$ 100,10 = 25,025 → 25,03 (HALF_UP), e não 25,02 (arredondamento bancário)
        self.assertEqual(services.taxa_combustivel(N.UM_QUARTO, N.VAZIO, Decimal("100.10")), Decimal("25.03"))

    def test_multa_de_cancelamento(self):
        self.assertEqual(services.multa_cancelamento(Decimal("360.00")), Decimal("72.00"))


class ExemploNumericoDoDocumentoTests(SimpleTestCase):
    """Exemplo do documento 'Modelo e regras': Econômico, R$ 120/dia, tanque R$ 300."""

    def test_extrato_completo(self):
        extrato = services.apurar_devolucao(
            retirada=RETIRADA, devolucao_prevista=PREVISTA,
            devolucao_real=datetime(2026, 10, 13, 14, 0), valor_diaria=Decimal("120.00"),
            nivel_saida=N.CHEIO, nivel_retorno=N.METADE, valor_tanque=Decimal("300.00"))
        self.assertEqual(extrato, {
            "diarias": 3,
            "valor_previsto": Decimal("360.00"),
            "diarias_atraso": 1,
            "multa": Decimal("180.00"),
            "taxa_combustivel": Decimal("150.00"),
            "total": Decimal("690.00"),
        })
