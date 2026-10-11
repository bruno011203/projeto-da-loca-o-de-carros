from datetime import date, timedelta

import pytest

from locadora import create_app
from locadora.db import get_db
from locadora.servicos import (
    RegraNegocioError, abrir_locacao, calcular_fechamento, cancelar_locacao, cpf_valido,
    devolver_veiculo, excluir_cliente, placa_valida, resumo_painel, salvar_cliente, salvar_veiculo,
)

HOJE = date.today()


def dia(n):
    return (HOJE + timedelta(days=n)).isoformat()


CLIENTE = {"nome": "Ana Souza", "cpf": "529.982.247-25", "cnh": "123", "validade_cnh": dia(365)}
VEICULO = {"placa": "abc-1d23", "marca": "Fiat", "modelo": "Mobi", "ano": 2023,
           "categoria": "Econômico", "valor_diaria": "100", "km_atual": 1000}


@pytest.fixture
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "teste.sqlite3")})


@pytest.fixture
def db(app):
    with app.app_context():
        yield get_db()


@pytest.fixture
def ids(db):
    return salvar_cliente(db, CLIENTE), salvar_veiculo(db, VEICULO)


def status_veiculo(db, veiculo_id):
    return db.execute("SELECT status FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()[0]


# --------------------------------------------------------------------------- validações

def test_cpf_valido():
    assert cpf_valido("529.982.247-25")
    assert not cpf_valido("529.982.247-24")
    assert not cpf_valido("111.111.111-11")


def test_placa_valida():
    assert placa_valida("ABC1234") and placa_valida("abc-1d23")
    assert not placa_valida("AB12345")


def test_cpf_duplicado(db, ids):
    with pytest.raises(RegraNegocioError, match="CPF"):
        salvar_cliente(db, CLIENTE)


def test_placa_duplicada_e_normalizada(db, ids):
    with pytest.raises(RegraNegocioError, match="placa"):
        salvar_veiculo(db, dict(VEICULO, placa="ABC1D23"))


# --------------------------------------------------------------------------- cálculos

def test_fechamento_no_prazo():
    assert calcular_fechamento(100, "2026-01-01", "2026-01-05", "2026-01-05") == (4, 0, 400)


def test_fechamento_devolucao_no_mesmo_dia_cobra_uma_diaria():
    assert calcular_fechamento(100, "2026-01-01", "2026-01-05", "2026-01-01") == (1, 0, 100)


def test_fechamento_com_atraso():
    # 6 diárias + 2 dias de atraso com 20% de multa sobre a diária
    assert calcular_fechamento(100, "2026-01-01", "2026-01-05", "2026-01-07") == (6, 40, 640)


# --------------------------------------------------------------------------- locações

def test_fluxo_completo_de_locacao(db, ids):
    cliente_id, veiculo_id = ids
    locacao_id = abrir_locacao(db, cliente_id, veiculo_id, dia(0), dia(3))
    assert status_veiculo(db, veiculo_id) == "locado"

    with pytest.raises(RegraNegocioError, match="disponível"):
        abrir_locacao(db, cliente_id, veiculo_id, dia(0), dia(2))

    total = devolver_veiculo(db, locacao_id, dia(3), 1350)
    assert total == 300
    veiculo = db.execute("SELECT * FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()
    assert veiculo["status"] == "disponivel" and veiculo["km_atual"] == 1350


def test_devolucao_com_km_menor_e_rejeitada(db, ids):
    locacao_id = abrir_locacao(db, *ids, dia(0), dia(3))
    with pytest.raises(RegraNegocioError, match="quilometragem"):
        devolver_veiculo(db, locacao_id, dia(3), 999)


def test_datas_invalidas(db, ids):
    with pytest.raises(RegraNegocioError, match="posterior"):
        abrir_locacao(db, *ids, dia(3), dia(3))


def test_cnh_vencida_impede_locacao(db, ids):
    cliente_id, veiculo_id = ids
    salvar_cliente(db, dict(CLIENTE, validade_cnh=dia(1)), cliente_id)
    with pytest.raises(RegraNegocioError, match="CNH"):
        abrir_locacao(db, cliente_id, veiculo_id, dia(0), dia(5))


def test_cliente_em_atraso_nao_pode_locar(db, ids):
    cliente_id, veiculo_id = ids
    abrir_locacao(db, cliente_id, veiculo_id, dia(-5), dia(-1))
    outro = salvar_veiculo(db, dict(VEICULO, placa="XYZ9876"))
    with pytest.raises(RegraNegocioError, match="atraso"):
        abrir_locacao(db, cliente_id, outro, dia(0), dia(2))


def test_veiculo_em_manutencao_nao_pode_ser_locado(app, db, ids):
    cliente_id, veiculo_id = ids
    app.test_client().post(f"/veiculos/{veiculo_id}/status", data={"status": "manutencao"})
    with pytest.raises(RegraNegocioError, match="disponível"):
        abrir_locacao(db, cliente_id, veiculo_id, dia(0), dia(2))


def test_cancelamento_libera_veiculo(db, ids):
    locacao_id = abrir_locacao(db, *ids, dia(0), dia(3))
    cancelar_locacao(db, locacao_id)
    assert status_veiculo(db, ids[1]) == "disponivel"
    with pytest.raises(RegraNegocioError, match="ativa"):
        devolver_veiculo(db, locacao_id, dia(3), 1100)


def test_nao_exclui_cliente_com_historico(db, ids):
    abrir_locacao(db, *ids, dia(0), dia(3))
    with pytest.raises(RegraNegocioError, match="histórico"):
        excluir_cliente(db, ids[0])


def test_resumo_painel(db, ids):
    locacao_id = abrir_locacao(db, *ids, dia(-4), dia(-2))
    assert resumo_painel(db)["atrasadas"] == 1
    devolver_veiculo(db, locacao_id, dia(0), 1100)
    resumo = resumo_painel(db)
    assert resumo["atrasadas"] == 0 and resumo["faturamento_mes"] == 440


# --------------------------------------------------------------------------- interface web

@pytest.mark.parametrize("url", ["/", "/clientes", "/veiculos", "/locacoes", "/locacoes/nova",
                                 "/clientes/novo", "/veiculos/novo"])
def test_paginas_carregam(app, url):
    assert app.test_client().get(url).status_code == 200


def test_fluxo_pela_interface(app):
    cliente = app.test_client()
    assert cliente.post("/clientes/novo", data=CLIENTE).status_code == 302
    assert cliente.post("/veiculos/novo", data=VEICULO).status_code == 302
    resposta = cliente.post("/locacoes/nova", data={
        "cliente_id": 1, "veiculo_id": 1, "data_retirada": dia(0), "data_prevista": dia(2)})
    assert resposta.status_code == 302
    assert "Ana Souza" in cliente.get("/locacoes/1").get_data(as_text=True)
    previa = cliente.get(f"/locacoes/1/devolucao?data_devolucao={dia(2)}&km_devolucao=1200")
    assert "R$ 200,00" in previa.get_data(as_text=True)
    resposta = cliente.post("/locacoes/1/devolucao",
                            data={"data_devolucao": dia(2), "km_devolucao": 1200},
                            follow_redirects=True)
    assert "Finalizada" in resposta.get_data(as_text=True)


def test_formulario_invalido_mostra_erro(app):
    resposta = app.test_client().post("/clientes/novo", data=dict(CLIENTE, cpf="123"))
    assert resposta.status_code == 400
    assert "CPF inválido" in resposta.get_data(as_text=True)


def test_registro_inexistente_retorna_404(app):
    assert app.test_client().get("/clientes/999").status_code == 404
