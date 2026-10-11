from dataclasses import dataclass
from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models

from .enums import (
    CategoriaCNH, NivelCombustivel, PerfilUsuario, StatusLocacao, StatusReserva, StatusVeiculo,
)
from .validators import validar_cpf

DINHEIRO = {"max_digits": 10, "decimal_places": 2, "validators": [MinValueValidator(0)]}


@dataclass(frozen=True)
class CNH:
    """Objeto de valor embutido no Cliente (não é tabela própria)."""
    numero: str
    categoria: str
    validade: date


class Cliente(models.Model):
    nome = models.CharField(max_length=120)
    cpf = models.CharField("CPF", max_length=11, unique=True, validators=[validar_cpf],
                           help_text="Somente números.")
    email = models.EmailField("e-mail", blank=True)
    telefone = models.CharField(max_length=20, blank=True)
    data_nascimento = models.DateField("data de nascimento")
    endereco = models.CharField("endereço", max_length=200, blank=True)
    ativo = models.BooleanField(default=True)
    # CNH embutida (composição)
    cnh_numero = models.CharField("número da CNH", max_length=11,
                                  validators=[RegexValidator(r"^\d{9,11}$", "Informe de 9 a 11 dígitos.")])
    cnh_categoria = models.CharField("categoria da CNH", max_length=2, choices=CategoriaCNH.choices)
    cnh_validade = models.DateField("validade da CNH")

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return f"{self.nome} ({self.cpf_formatado})"

    @property
    def cnh(self) -> CNH:
        return CNH(self.cnh_numero, self.cnh_categoria, self.cnh_validade)

    @property
    def cpf_formatado(self):
        c = self.cpf
        return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else c


class Categoria(models.Model):
    nome = models.CharField(max_length=40, unique=True)
    valor_diaria = models.DecimalField("valor da diária", **DINHEIRO)
    valor_caucao = models.DecimalField("valor da caução", **DINHEIRO)
    valor_tanque_cheio = models.DecimalField("valor do tanque cheio", **DINHEIRO)
    descricao = models.CharField("descrição", max_length=200, blank=True)

    class Meta:
        ordering = ["valor_diaria"]

    def __str__(self):
        return self.nome


class Veiculo(models.Model):
    placa = models.CharField(max_length=7, unique=True, validators=[
        RegexValidator(r"^[A-Z]{3}\d[A-Z0-9]\d{2}$", "Use o formato ABC1234 ou ABC1D23.")])
    chassi = models.CharField(max_length=17, unique=True, validators=[
        RegexValidator(r"^[A-HJ-NPR-Z0-9]{17}$", "O chassi tem 17 caracteres (sem I, O e Q).")])
    marca = models.CharField(max_length=40)
    modelo = models.CharField(max_length=60)
    ano_fabricacao = models.PositiveIntegerField("ano de fabricação",
                                                 validators=[MinValueValidator(1990)])
    cor = models.CharField(max_length=30, blank=True)
    km_atual = models.PositiveIntegerField("km atual", default=0)
    status = models.CharField(max_length=12, choices=StatusVeiculo.choices,
                              default=StatusVeiculo.DISPONIVEL)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name="veiculos")

    class Meta:
        ordering = ["marca", "modelo"]
        verbose_name = "veículo"

    def __str__(self):
        return f"{self.marca} {self.modelo} ({self.placa})"

    def clean(self):
        self.placa = (self.placa or "").upper().replace("-", "")
        self.chassi = (self.chassi or "").upper()
        if self.ano_fabricacao and self.ano_fabricacao > date.today().year + 1:
            raise ValidationError({"ano_fabricacao": "Ano de fabricação inválido."})


class Funcionario(models.Model):
    """Quem opera o sistema. Login e senha vêm do User do Django (substitui senhaHash)."""
    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                   related_name="funcionario")
    nome = models.CharField(max_length=120)
    matricula = models.CharField("matrícula", max_length=20, unique=True)
    perfil = models.CharField(max_length=10, choices=PerfilUsuario.choices,
                              default=PerfilUsuario.ATENDENTE)

    class Meta:
        ordering = ["nome"]
        verbose_name = "funcionário"

    def __str__(self):
        return f"{self.nome} ({self.matricula})"

    @property
    def login(self):
        return self.usuario.username


class Reserva(models.Model):
    codigo = models.CharField("código", max_length=20, unique=True, editable=False)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="reservas")
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name="reservas")
    retirada_prevista = models.DateTimeField("retirada prevista")
    devolucao_prevista = models.DateTimeField("devolução prevista")
    valor_estimado = models.DecimalField("valor estimado", **DINHEIRO)
    status = models.CharField(max_length=10, choices=StatusReserva.choices,
                              default=StatusReserva.ATIVA)
    valor_multa_cancelamento = models.DecimalField("multa de cancelamento", default=0, **DINHEIRO)
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-retirada_prevista"]

    def __str__(self):
        return self.codigo


class Locacao(models.Model):
    reserva = models.OneToOneField(Reserva, on_delete=models.PROTECT, null=True, blank=True,
                                   related_name="locacao")
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="locacoes")
    veiculo = models.ForeignKey(Veiculo, on_delete=models.PROTECT, related_name="locacoes")
    atendente = models.ForeignKey(Funcionario, on_delete=models.PROTECT, related_name="locacoes")
    data_retirada = models.DateTimeField("data de retirada")
    devolucao_prevista = models.DateTimeField("devolução prevista")
    devolucao_real = models.DateTimeField("devolução real", null=True, blank=True)
    km_saida = models.PositiveIntegerField("km de saída")
    km_retorno = models.PositiveIntegerField("km de retorno", null=True, blank=True)
    combustivel_saida = models.CharField("combustível na saída", max_length=12,
                                         choices=NivelCombustivel.choices)
    combustivel_retorno = models.CharField("combustível no retorno", max_length=12,
                                           choices=NivelCombustivel.choices, blank=True)
    valor_diaria_aplicado = models.DecimalField("diária aplicada", **DINHEIRO)
    valor_caucao = models.DecimalField("caução", **DINHEIRO)
    valor_multa = models.DecimalField("multa por atraso", default=0, **DINHEIRO)
    valor_combustivel = models.DecimalField("taxa de combustível", default=0, **DINHEIRO)
    valor_total = models.DecimalField("valor total", null=True, blank=True, **DINHEIRO)
    avaria = models.BooleanField(default=False)
    descricao_avaria = models.CharField("descrição da avaria", max_length=300, blank=True)
    status = models.CharField(max_length=12, choices=StatusLocacao.choices,
                              default=StatusLocacao.EM_ANDAMENTO)

    class Meta:
        ordering = ["-data_retirada"]
        verbose_name = "locação"
        verbose_name_plural = "locações"

    def __str__(self):
        return f"Locação #{self.pk} — {self.cliente.nome}"

    @property
    def em_aberto(self):
        return self.status in (StatusLocacao.EM_ANDAMENTO, StatusLocacao.ATRASADA)

    def save(self, *args, **kwargs):
        # RN19: locação FINALIZADA é imutável.
        if self.pk:
            status_gravado = Locacao.objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if status_gravado == StatusLocacao.FINALIZADA:
                raise ValidationError("RN19: locação finalizada não pode ser alterada.")
        super().save(*args, **kwargs)
