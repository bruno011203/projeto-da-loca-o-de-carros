from django.contrib import admin

from .models import Categoria, Cliente, Funcionario, Locacao, Reserva, Veiculo


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nome", "valor_diaria", "valor_caucao", "valor_tanque_cheio")
    search_fields = ("nome",)


@admin.register(Veiculo)
class VeiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "marca", "modelo", "ano_fabricacao", "categoria", "km_atual", "status")
    list_filter = ("status", "categoria", "marca")
    search_fields = ("placa", "chassi", "marca", "modelo")


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nome", "cpf", "telefone", "cnh_categoria", "cnh_validade", "ativo")
    list_filter = ("ativo", "cnh_categoria")
    search_fields = ("nome", "cpf", "email", "cnh_numero")
    fieldsets = (
        (None, {"fields": ("nome", "cpf", "data_nascimento", "email", "telefone", "endereco", "ativo")}),
        ("CNH", {"fields": ("cnh_numero", "cnh_categoria", "cnh_validade")}),
    )


@admin.register(Funcionario)
class FuncionarioAdmin(admin.ModelAdmin):
    list_display = ("nome", "matricula", "perfil", "usuario")
    list_filter = ("perfil",)
    search_fields = ("nome", "matricula", "usuario__username")


class SomenteLeituraAdmin(admin.ModelAdmin):
    """Reservas e locações mudam de estado só pelas telas do sistema (regras RN06–RN19)."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Reserva)
class ReservaAdmin(SomenteLeituraAdmin):
    list_display = ("codigo", "cliente", "veiculo", "retirada_prevista", "devolucao_prevista",
                    "valor_estimado", "status")
    list_filter = ("status",)
    search_fields = ("codigo", "cliente__nome", "veiculo__placa")


@admin.register(Locacao)
class LocacaoAdmin(SomenteLeituraAdmin):
    list_display = ("id", "cliente", "veiculo", "data_retirada", "devolucao_prevista", "devolucao_real",
                    "valor_total", "status")
    list_filter = ("status",)
    search_fields = ("cliente__nome", "veiculo__placa")
