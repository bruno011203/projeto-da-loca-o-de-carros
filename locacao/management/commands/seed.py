"""Carga de dados de exemplo: python manage.py seed [--reset]"""

from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from locacao import operacoes
from locacao.enums import CategoriaCNH, NivelCombustivel, PerfilUsuario, StatusVeiculo
from locacao.models import Categoria, Cliente, Funcionario, Locacao, Reserva, Veiculo

SENHA_PADRAO = "locadora123"

CATEGORIAS = [
    ("Econômico", "120.00", "500.00", "300.00", "Compactos 1.0, ideais para a cidade."),
    ("Intermediário", "170.00", "800.00", "350.00", "Sedãs e hatches 1.0 turbo."),
    ("SUV", "260.00", "1500.00", "450.00", "Utilitários esportivos."),
    ("Executivo", "340.00", "2000.00", "500.00", "Sedãs médios e grandes."),
]

VEICULOS = [
    ("ABC1D23", "9BWZZZ377VT004251", "Fiat", "Mobi", 2023, "Branco", 32100, "Econômico"),
    ("BRA2E19", "9BGKS48U0KG123456", "Renault", "Kwid", 2024, "Prata", 8300, "Econômico"),
    ("RIO3F45", "93HGK5850KZ200111", "Hyundai", "HB20", 2023, "Vermelho", 21400, "Econômico"),
    ("SPX4G67", "9BGEA48A0LG300222", "Chevrolet", "Onix Plus", 2024, "Preto", 12050, "Intermediário"),
    ("MGA5H89", "9BWDB45U0LT400333", "Volkswagen", "Virtus", 2023, "Cinza", 27800, "Intermediário"),
    ("XYZ9876", "1C4NJCBA0LD500444", "Jeep", "Compass", 2022, "Preto", 41000, "SUV"),
    ("QWE4R56", "9BRBZ3BE0M0600555", "Toyota", "Corolla Cross", 2024, "Branco", 5100, "SUV"),
    ("JKL6M12", "93YRBB000LJ700666", "Hyundai", "Creta", 2023, "Azul", 18200, "SUV"),
    ("EXE7N34", "9BR53ZEC0N8800777", "Toyota", "Corolla", 2024, "Prata", 9900, "Executivo"),
    ("VIP8P56", "WBA5R1C50LF900888", "BMW", "320i", 2023, "Preto", 15300, "Executivo"),
]

CLIENTES = [
    ("Ana Souza", "52998224725", date(1990, 5, 12), "01234567890", CategoriaCNH.B, 900, "ana@exemplo.com"),
    ("Carlos Lima", "11144477735", date(1985, 9, 3), "09876543210", CategoriaCNH.B, 500, "carlos@exemplo.com"),
    ("Mariana Rocha", "39053344705", date(1998, 1, 20), "11223344556", CategoriaCNH.D, 700, "mariana@exemplo.com"),
    ("João Pedro Alves", "15350946056", date(2006, 3, 15), "22334455667", CategoriaCNH.B, 1500, "joao@exemplo.com"),
    ("Beatriz Nunes", "71428793860", date(1979, 11, 30), "33445566778", CategoriaCNH.A, 800, "bia@exemplo.com"),
]


class Command(BaseCommand):
    help = "Cria categorias, veículos, clientes, funcionários, reservas e locações de exemplo."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Apaga os dados antes de recriar.")

    @transaction.atomic
    def handle(self, *args, reset=False, **opts):
        if reset:
            for modelo in (Locacao, Reserva, Veiculo, Categoria, Cliente, Funcionario):
                modelo.objects.all().delete()
            User.objects.filter(username__in=["gerente", "atendente"]).delete()
        if Categoria.objects.exists():
            self.stdout.write(self.style.WARNING("O banco já possui dados. Use --reset para recriar."))
            return

        gerente = self._funcionario("gerente", "Gabriela Martins", "F0001", PerfilUsuario.GERENTE, staff=True)
        atendente = self._funcionario("atendente", "Rafael Costa", "F0002", PerfilUsuario.ATENDENTE)

        categorias = {}
        for nome, diaria, caucao, tanque, descricao in CATEGORIAS:
            categorias[nome] = Categoria.objects.create(
                nome=nome, valor_diaria=Decimal(diaria), valor_caucao=Decimal(caucao),
                valor_tanque_cheio=Decimal(tanque), descricao=descricao)
        veiculos = {}
        for placa, chassi, marca, modelo, ano, cor, km, categoria in VEICULOS:
            veiculos[placa] = Veiculo.objects.create(
                placa=placa, chassi=chassi, marca=marca, modelo=modelo, ano_fabricacao=ano,
                cor=cor, km_atual=km, categoria=categorias[categoria])
        hoje = date.today()
        clientes = [
            Cliente.objects.create(nome=nome, cpf=cpf, data_nascimento=nasc, cnh_numero=cnh,
                                   cnh_categoria=cat, cnh_validade=hoje + timedelta(days=dias), email=email,
                                   telefone="(11) 9" + cpf[:4] + "-" + cpf[4:8], endereco="São Paulo - SP")
            for nome, cpf, nasc, cnh, cat, dias, email in CLIENTES
        ]

        agora = timezone.now().replace(second=0, microsecond=0)
        hora = timedelta(hours=1)
        dia = timedelta(days=1)

        # Locação finalizada há alguns dias (com atraso e combustível)
        passado = agora - 6 * dia
        reserva = operacoes.criar_reserva(clientes[0], veiculos["ABC1D23"], passado + hora, passado + 3 * dia + hora,
                                          agora=passado)
        loc = operacoes.registrar_retirada(atendente=atendente, reserva=reserva, km_saida=32100,
                                           combustivel_saida=NivelCombustivel.CHEIO, agora=passado + hora)
        operacoes.registrar_devolucao(loc, km_retorno=32740, combustivel_retorno=NivelCombustivel.METADE,
                                      devolucao_real=passado + 3 * dia + 6 * hora, agora=agora)

        # Locação em andamento (devolução daqui a 2 dias)
        operacoes.registrar_retirada(atendente=atendente, cliente=clientes[1], veiculo=veiculos["SPX4G67"],
                                     devolucao_prevista=agora + 2 * dia, km_saida=12050,
                                     combustivel_saida=NivelCombustivel.CHEIO, agora=agora - dia)

        # Locação atrasada (devolução prevista para ontem)
        operacoes.registrar_retirada(atendente=gerente, cliente=clientes[2], veiculo=veiculos["XYZ9876"],
                                     devolucao_prevista=agora - dia, km_saida=41000,
                                     combustivel_saida=NivelCombustivel.TRES_QUARTOS, agora=agora - 4 * dia)

        # Reservas futuras
        operacoes.criar_reserva(clientes[0], veiculos["QWE4R56"], agora + 3 * hora, agora + 2 * dia + 3 * hora,
                                agora=agora)
        operacoes.criar_reserva(clientes[1], veiculos["EXE7N34"], agora + 5 * dia, agora + 8 * dia, agora=agora)

        # Um veículo em manutenção
        Veiculo.objects.filter(placa="VIP8P56").update(status=StatusVeiculo.MANUTENCAO)
        operacoes.atualizar_status_temporais(agora)

        self.stdout.write(self.style.SUCCESS(
            f"Dados criados. Logins: gerente / {SENHA_PADRAO} (acessa o admin) e atendente / {SENHA_PADRAO}."))

    def _funcionario(self, login, nome, matricula, perfil, staff=False):
        primeiro, *resto = nome.split()
        usuario = User.objects.create_user(login, password=SENHA_PADRAO, first_name=primeiro,
                                           last_name=" ".join(resto), is_staff=staff, is_superuser=staff)
        return Funcionario.objects.create(usuario=usuario, nome=nome, matricula=matricula, perfil=perfil)
