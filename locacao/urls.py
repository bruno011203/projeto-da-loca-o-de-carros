from django.urls import path

from . import views

app_name = "locacao"

urlpatterns = [
    path("", views.painel, name="painel"),
    # UC01 — Manter veículo
    path("veiculos/", views.veiculos, name="veiculos"),
    path("veiculos/novo/", views.veiculo_form, name="veiculo_novo"),
    path("veiculos/<int:pk>/editar/", views.veiculo_form, name="veiculo_editar"),
    # UC02 — Manter cliente
    path("clientes/", views.clientes, name="clientes"),
    path("clientes/novo/", views.cliente_form, name="cliente_novo"),
    path("clientes/<int:pk>/", views.cliente_detalhe, name="cliente_detalhe"),
    path("clientes/<int:pk>/editar/", views.cliente_form, name="cliente_editar"),
    # UC03 — Consultar disponibilidade e reservar
    path("disponibilidade/", views.disponibilidade, name="disponibilidade"),
    path("reservas/", views.reservas, name="reservas"),
    path("reservas/nova/", views.reserva_nova, name="reserva_nova"),
    path("reservas/<int:pk>/", views.reserva_detalhe, name="reserva_detalhe"),
    path("reservas/<int:pk>/cancelar/", views.reserva_cancelar, name="reserva_cancelar"),
    # UC04 — Registrar retirada
    path("reservas/<int:pk>/retirada/", views.retirada, name="retirada"),
    path("locacoes/balcao/", views.locacao_balcao, name="locacao_balcao"),
    # UC05 — Registrar devolução e apurar valores
    path("locacoes/", views.locacoes, name="locacoes"),
    path("locacoes/<int:pk>/", views.locacao_detalhe, name="locacao_detalhe"),
    path("locacoes/<int:pk>/devolucao/", views.devolucao, name="devolucao"),
]
