from decimal import Decimal

from django import template

register = template.Library()

CORES_STATUS = {
    "DISPONIVEL": "success", "LOCADO": "primary", "MANUTENCAO": "warning", "INATIVO": "secondary",
    "ATIVA": "primary", "CONVERTIDA": "success", "CANCELADA": "secondary", "EXPIRADA": "dark",
    "EM_ANDAMENTO": "primary", "FINALIZADA": "success", "ATRASADA": "danger",
}


@register.filter
def moeda(valor):
    texto = f"{Decimal(str(valor or 0)):,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def milhar(valor):
    return f"{valor or 0:,}".replace(",", ".")


@register.inclusion_tag("locacao/_status.html")
def status(obj):
    return {"cor": CORES_STATUS.get(obj.status, "secondary"), "texto": obj.get_status_display()}
