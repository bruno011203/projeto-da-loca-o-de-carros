from django.db import models


class StatusVeiculo(models.TextChoices):
    DISPONIVEL = "DISPONIVEL", "Disponível"
    LOCADO = "LOCADO", "Locado"
    MANUTENCAO = "MANUTENCAO", "Em manutenção"
    INATIVO = "INATIVO", "Inativo"


class StatusReserva(models.TextChoices):
    ATIVA = "ATIVA", "Ativa"
    CONVERTIDA = "CONVERTIDA", "Convertida em locação"
    CANCELADA = "CANCELADA", "Cancelada"
    EXPIRADA = "EXPIRADA", "Expirada"


class StatusLocacao(models.TextChoices):
    EM_ANDAMENTO = "EM_ANDAMENTO", "Em andamento"
    FINALIZADA = "FINALIZADA", "Finalizada"
    ATRASADA = "ATRASADA", "Atrasada"


class CategoriaCNH(models.TextChoices):
    A = "A", "A"
    B = "B", "B"
    C = "C", "C"
    D = "D", "D"
    E = "E", "E"


class NivelCombustivel(models.TextChoices):
    VAZIO = "VAZIO", "Vazio"
    UM_QUARTO = "UM_QUARTO", "1/4"
    METADE = "METADE", "1/2"
    TRES_QUARTOS = "TRES_QUARTOS", "3/4"
    CHEIO = "CHEIO", "Cheio"


# Cada nível vale um número de quartos de tanque (fórmula da taxa de combustível)
QUARTOS_COMBUSTIVEL = {
    NivelCombustivel.VAZIO: 0,
    NivelCombustivel.UM_QUARTO: 1,
    NivelCombustivel.METADE: 2,
    NivelCombustivel.TRES_QUARTOS: 3,
    NivelCombustivel.CHEIO: 4,
}


class PerfilUsuario(models.TextChoices):
    ATENDENTE = "ATENDENTE", "Atendente"
    GERENTE = "GERENTE", "Gerente"
