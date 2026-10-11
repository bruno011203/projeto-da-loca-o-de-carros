from datetime import timedelta

from django import forms
from django.utils import timezone

from .enums import NivelCombustivel, StatusVeiculo
from .models import Categoria, Cliente, Veiculo
from .validators import somente_digitos

FORMATO_DATA_HORA = "%Y-%m-%dT%H:%M"


class DataHoraInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format=FORMATO_DATA_HORA, **kwargs)


class DataInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


def campo_data_hora(label, **kwargs):
    return forms.DateTimeField(label=label, widget=DataHoraInput(),
                               input_formats=[FORMATO_DATA_HORA], **kwargs)


class BootstrapMixin:
    """Aplica as classes do Bootstrap 5 em todos os campos."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for campo in self.fields.values():
            widget = campo.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs.setdefault("class", "form-select")
            else:
                widget.attrs.setdefault("class", "form-control")


# --------------------------------------------------------------------------- UC01 e UC02

class ClienteForm(BootstrapMixin, forms.ModelForm):
    cpf = forms.CharField(label="CPF", max_length=14, help_text="Com ou sem pontuação.")

    class Meta:
        model = Cliente
        fields = ["nome", "cpf", "data_nascimento", "email", "telefone", "endereco",
                  "cnh_numero", "cnh_categoria", "cnh_validade", "ativo"]
        widgets = {"data_nascimento": DataInput(), "cnh_validade": DataInput()}

    def clean_cpf(self):
        return somente_digitos(self.cleaned_data["cpf"])


class VeiculoForm(BootstrapMixin, forms.ModelForm):
    class Meta:
        model = Veiculo
        fields = ["placa", "chassi", "marca", "modelo", "ano_fabricacao", "cor", "categoria",
                  "km_atual", "status"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.status == StatusVeiculo.LOCADO:
            # O status de um veículo locado só muda pela devolução (RN18).
            self.fields["status"].disabled = True
        else:
            self.fields["status"].choices = [c for c in StatusVeiculo.choices if c[0] != StatusVeiculo.LOCADO]

    def clean_placa(self):
        return self.cleaned_data["placa"].upper().replace("-", "").strip()

    def clean_chassi(self):
        return self.cleaned_data["chassi"].upper().strip()

    def clean_km_atual(self):
        km = self.cleaned_data["km_atual"]
        if self.instance.pk and km < self.instance.km_atual:
            raise forms.ValidationError("A quilometragem não pode ser reduzida.")
        return km


# --------------------------------------------------------------------------- UC03

class BuscaDisponibilidadeForm(BootstrapMixin, forms.Form):
    retirada = campo_data_hora("Retirada")
    devolucao = campo_data_hora("Devolução")
    categoria = forms.ModelChoiceField(Categoria.objects.all(), required=False,
                                       empty_label="Todas as categorias")

    def clean(self):
        dados = super().clean()
        if dados.get("retirada") and dados.get("devolucao") and dados["devolucao"] <= dados["retirada"]:
            raise forms.ValidationError("RN10: a devolução deve ser posterior à retirada.")
        return dados


class ReservaForm(BootstrapMixin, forms.Form):
    cliente = forms.ModelChoiceField(Cliente.objects.filter(ativo=True), label="Cliente")


# --------------------------------------------------------------------------- UC04

class RetiradaForm(BootstrapMixin, forms.Form):
    km_saida = forms.IntegerField(label="Km de saída", min_value=0)
    combustivel_saida = forms.ChoiceField(label="Combustível na saída", choices=NivelCombustivel.choices,
                                          initial=NivelCombustivel.CHEIO)


class LocacaoBalcaoForm(RetiradaForm):
    cliente = forms.ModelChoiceField(Cliente.objects.filter(ativo=True), label="Cliente")
    veiculo = forms.ModelChoiceField(Veiculo.objects.none(), label="Veículo")
    devolucao_prevista = campo_data_hora("Devolução prevista")

    field_order = ["cliente", "veiculo", "devolucao_prevista", "km_saida", "combustivel_saida"]

    def __init__(self, *args, veiculos=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["veiculo"].queryset = veiculos if veiculos is not None else Veiculo.objects.filter(
            status=StatusVeiculo.DISPONIVEL)


# --------------------------------------------------------------------------- UC05

class DevolucaoForm(BootstrapMixin, forms.Form):
    devolucao_real = campo_data_hora("Data e hora da devolução")
    km_retorno = forms.IntegerField(label="Km de retorno", min_value=0)
    combustivel_retorno = forms.ChoiceField(label="Combustível no retorno", choices=NivelCombustivel.choices)
    avaria = forms.BooleanField(label="Houve avaria", required=False)
    descricao_avaria = forms.CharField(label="Descrição da avaria", required=False,
                                       widget=forms.Textarea(attrs={"rows": 2}))

    def clean_devolucao_real(self):
        valor = self.cleaned_data["devolucao_real"]
        if valor > timezone.now() + timedelta(minutes=1):
            raise forms.ValidationError("A devolução não pode estar no futuro.")
        return valor

    def clean(self):
        dados = super().clean()
        if dados.get("avaria") and not dados.get("descricao_avaria"):
            self.add_error("descricao_avaria", "Descreva a avaria.")
        return dados
