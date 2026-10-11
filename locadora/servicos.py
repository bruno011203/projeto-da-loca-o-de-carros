"""Regras de negócio da locadora.

As funções recebem uma conexão sqlite3 e lançam RegraNegocioError quando
alguma regra é violada; as rotas só traduzem isso em mensagens para o usuário.
"""

import re
from datetime import date

MULTA_ATRASO = 0.20  # acréscimo de 20% sobre a diária em cada dia de atraso
CATEGORIAS = ["Econômico", "Intermediário", "SUV", "Executivo", "Utilitário"]
STATUS_VEICULO = {"disponivel": "Disponível", "locado": "Locado", "manutencao": "Em manutenção"}
STATUS_LOCACAO = {"ativa": "Ativa", "finalizada": "Finalizada", "cancelada": "Cancelada"}


class RegraNegocioError(Exception):
    pass


# --------------------------------------------------------------------------- validações

def somente_digitos(valor):
    return re.sub(r"\D", "", valor or "")


def cpf_valido(cpf):
    cpf = somente_digitos(cpf)
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        digito = (soma * 10) % 11 % 10
        if digito != int(cpf[tamanho]):
            return False
    return True


def formatar_cpf(cpf):
    c = somente_digitos(cpf)
    return f"{c[:3]}.{c[3:6]}.{c[6:9]}-{c[9:]}" if len(c) == 11 else cpf


def normalizar_placa(placa):
    return re.sub(r"[^A-Z0-9]", "", (placa or "").upper())


def placa_valida(placa):
    # Padrão antigo (ABC1234) ou Mercosul (ABC1D23)
    return bool(re.fullmatch(r"[A-Z]{3}\d[A-Z0-9]\d{2}", normalizar_placa(placa)))


def para_data(valor):
    if isinstance(valor, date):
        return valor
    try:
        return date.fromisoformat(valor)
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Data inválida: {valor!r}.")


def para_numero(valor, campo, tipo=float):
    try:
        return tipo(str(valor).replace(",", "."))
    except (TypeError, ValueError):
        raise RegraNegocioError(f"Valor inválido para {campo}.")


def _obrigatorios(dados, campos):
    faltando = [nome for chave, nome in campos.items() if not str(dados.get(chave) or "").strip()]
    if faltando:
        raise RegraNegocioError("Preencha os campos obrigatórios: " + ", ".join(faltando) + ".")


# --------------------------------------------------------------------------- clientes

def salvar_cliente(db, dados, cliente_id=None):
    _obrigatorios(dados, {"nome": "Nome", "cpf": "CPF", "cnh": "CNH", "validade_cnh": "Validade da CNH"})
    if not cpf_valido(dados["cpf"]):
        raise RegraNegocioError("CPF inválido.")
    cpf = somente_digitos(dados["cpf"])
    para_data(dados["validade_cnh"])

    existente = db.execute("SELECT id FROM clientes WHERE cpf = ?", (cpf,)).fetchone()
    if existente and existente["id"] != cliente_id:
        raise RegraNegocioError("Já existe um cliente cadastrado com este CPF.")

    valores = (
        dados["nome"].strip(), cpf, dados["cnh"].strip(), dados["validade_cnh"],
        (dados.get("telefone") or "").strip(), (dados.get("email") or "").strip(),
        (dados.get("endereco") or "").strip(),
    )
    if cliente_id is None:
        cur = db.execute(
            "INSERT INTO clientes (nome, cpf, cnh, validade_cnh, telefone, email, endereco)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)", valores)
        cliente_id = cur.lastrowid
    else:
        db.execute(
            "UPDATE clientes SET nome=?, cpf=?, cnh=?, validade_cnh=?, telefone=?, email=?, endereco=?"
            " WHERE id=?", valores + (cliente_id,))
    db.commit()
    return cliente_id


def excluir_cliente(db, cliente_id):
    if db.execute("SELECT 1 FROM locacoes WHERE cliente_id = ?", (cliente_id,)).fetchone():
        raise RegraNegocioError("Não é possível excluir um cliente com histórico de locações.")
    db.execute("DELETE FROM clientes WHERE id = ?", (cliente_id,))
    db.commit()


# --------------------------------------------------------------------------- veículos

def salvar_veiculo(db, dados, veiculo_id=None):
    _obrigatorios(dados, {"placa": "Placa", "marca": "Marca", "modelo": "Modelo", "ano": "Ano",
                          "categoria": "Categoria", "valor_diaria": "Valor da diária"})
    if not placa_valida(dados["placa"]):
        raise RegraNegocioError("Placa inválida. Use o formato ABC1234 ou ABC1D23.")
    placa = normalizar_placa(dados["placa"])
    ano = para_numero(dados["ano"], "ano", int)
    if not 1950 <= ano <= date.today().year + 1:
        raise RegraNegocioError("Ano do veículo fora do intervalo permitido.")
    diaria = para_numero(dados["valor_diaria"], "valor da diária")
    if diaria <= 0:
        raise RegraNegocioError("O valor da diária deve ser maior que zero.")
    km = para_numero(dados.get("km_atual") or 0, "quilometragem", int)
    if km < 0:
        raise RegraNegocioError("A quilometragem não pode ser negativa.")
    if dados["categoria"] not in CATEGORIAS:
        raise RegraNegocioError("Categoria inválida.")

    existente = db.execute("SELECT id FROM veiculos WHERE placa = ?", (placa,)).fetchone()
    if existente and existente["id"] != veiculo_id:
        raise RegraNegocioError("Já existe um veículo cadastrado com esta placa.")

    valores = (placa, dados["marca"].strip(), dados["modelo"].strip(), ano,
               (dados.get("cor") or "").strip(), dados["categoria"], diaria, km)
    if veiculo_id is None:
        cur = db.execute(
            "INSERT INTO veiculos (placa, marca, modelo, ano, cor, categoria, valor_diaria, km_atual)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?)", valores)
        veiculo_id = cur.lastrowid
    else:
        atual = db.execute("SELECT km_atual FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()
        if atual and km < atual["km_atual"]:
            raise RegraNegocioError("A quilometragem não pode ser reduzida.")
        db.execute(
            "UPDATE veiculos SET placa=?, marca=?, modelo=?, ano=?, cor=?, categoria=?,"
            " valor_diaria=?, km_atual=? WHERE id=?", valores + (veiculo_id,))
    db.commit()
    return veiculo_id


def alterar_status_veiculo(db, veiculo_id, novo_status):
    if novo_status not in ("disponivel", "manutencao"):
        raise RegraNegocioError("Status inválido.")
    veiculo = db.execute("SELECT status FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()
    if veiculo is None:
        raise RegraNegocioError("Veículo não encontrado.")
    if veiculo["status"] == "locado":
        raise RegraNegocioError("Veículo locado: registre a devolução antes de alterar o status.")
    db.execute("UPDATE veiculos SET status = ? WHERE id = ?", (novo_status, veiculo_id))
    db.commit()


def excluir_veiculo(db, veiculo_id):
    if db.execute("SELECT 1 FROM locacoes WHERE veiculo_id = ?", (veiculo_id,)).fetchone():
        raise RegraNegocioError("Não é possível excluir um veículo com histórico de locações.")
    db.execute("DELETE FROM veiculos WHERE id = ?", (veiculo_id,))
    db.commit()


# --------------------------------------------------------------------------- locações

def calcular_diarias(inicio, fim):
    """Número de diárias cobradas entre duas datas (mínimo de uma)."""
    return max(1, (para_data(fim) - para_data(inicio)).days)


def calcular_fechamento(valor_diaria, data_retirada, data_prevista, data_devolucao):
    """Retorna (diárias, multa, total) para a devolução de uma locação.

    Cada dia usado é cobrado pela diária; os dias além da data prevista
    recebem ainda o acréscimo de MULTA_ATRASO sobre a diária.
    """
    diarias = calcular_diarias(data_retirada, data_devolucao)
    atraso = max(0, (para_data(data_devolucao) - para_data(data_prevista)).days)
    multa = round(atraso * valor_diaria * MULTA_ATRASO, 2)
    total = round(diarias * valor_diaria + multa, 2)
    return diarias, multa, total


def abrir_locacao(db, cliente_id, veiculo_id, data_retirada, data_prevista, observacoes=""):
    retirada, prevista = para_data(data_retirada), para_data(data_prevista)
    if prevista <= retirada:
        raise RegraNegocioError("A devolução prevista deve ser posterior à retirada.")

    cliente = db.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
    if cliente is None:
        raise RegraNegocioError("Cliente não encontrado.")
    if para_data(cliente["validade_cnh"]) < prevista:
        raise RegraNegocioError("A CNH do cliente vence antes do fim da locação.")
    if db.execute(
        "SELECT 1 FROM locacoes WHERE cliente_id = ? AND status = 'ativa' AND data_prevista < ?",
        (cliente_id, date.today().isoformat()),
    ).fetchone():
        raise RegraNegocioError("O cliente possui locação em atraso e não pode fazer nova locação.")

    veiculo = db.execute("SELECT * FROM veiculos WHERE id = ?", (veiculo_id,)).fetchone()
    if veiculo is None:
        raise RegraNegocioError("Veículo não encontrado.")
    if veiculo["status"] != "disponivel":
        raise RegraNegocioError("O veículo selecionado não está disponível.")

    valor_previsto = round(calcular_diarias(retirada, prevista) * veiculo["valor_diaria"], 2)
    cur = db.execute(
        "INSERT INTO locacoes (cliente_id, veiculo_id, data_retirada, data_prevista, km_retirada,"
        " valor_diaria, valor_previsto, observacoes) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (cliente_id, veiculo_id, retirada.isoformat(), prevista.isoformat(), veiculo["km_atual"],
         veiculo["valor_diaria"], valor_previsto, (observacoes or "").strip()))
    db.execute("UPDATE veiculos SET status = 'locado' WHERE id = ?", (veiculo_id,))
    db.commit()
    return cur.lastrowid


def _locacao_ativa(db, locacao_id):
    locacao = db.execute("SELECT * FROM locacoes WHERE id = ?", (locacao_id,)).fetchone()
    if locacao is None:
        raise RegraNegocioError("Locação não encontrada.")
    if locacao["status"] != "ativa":
        raise RegraNegocioError("Esta locação não está ativa.")
    return locacao


def devolver_veiculo(db, locacao_id, data_devolucao, km_devolucao):
    locacao = _locacao_ativa(db, locacao_id)
    devolucao = para_data(data_devolucao)
    if devolucao < para_data(locacao["data_retirada"]):
        raise RegraNegocioError("A data de devolução não pode ser anterior à retirada.")
    km = para_numero(km_devolucao, "quilometragem", int)
    if km < locacao["km_retirada"]:
        raise RegraNegocioError("A quilometragem de devolução é menor que a de retirada.")

    _, multa, total = calcular_fechamento(
        locacao["valor_diaria"], locacao["data_retirada"], locacao["data_prevista"], devolucao)
    db.execute(
        "UPDATE locacoes SET data_devolucao=?, km_devolucao=?, multa=?, valor_total=?,"
        " status='finalizada' WHERE id=?",
        (devolucao.isoformat(), km, multa, total, locacao_id))
    db.execute("UPDATE veiculos SET status='disponivel', km_atual=? WHERE id=?",
               (km, locacao["veiculo_id"]))
    db.commit()
    return total


def cancelar_locacao(db, locacao_id):
    locacao = _locacao_ativa(db, locacao_id)
    db.execute("UPDATE locacoes SET status='cancelada', valor_total=0 WHERE id=?", (locacao_id,))
    db.execute("UPDATE veiculos SET status='disponivel' WHERE id=?", (locacao["veiculo_id"],))
    db.commit()


# --------------------------------------------------------------------------- relatórios

def resumo_painel(db, hoje=None):
    hoje = (hoje or date.today()).isoformat()
    mes = hoje[:7]

    def escalar(sql, *params):
        return db.execute(sql, params).fetchone()[0]

    return {
        "clientes": escalar("SELECT COUNT(*) FROM clientes"),
        "veiculos": escalar("SELECT COUNT(*) FROM veiculos"),
        "disponiveis": escalar("SELECT COUNT(*) FROM veiculos WHERE status='disponivel'"),
        "locados": escalar("SELECT COUNT(*) FROM veiculos WHERE status='locado'"),
        "manutencao": escalar("SELECT COUNT(*) FROM veiculos WHERE status='manutencao'"),
        "ativas": escalar("SELECT COUNT(*) FROM locacoes WHERE status='ativa'"),
        "atrasadas": escalar(
            "SELECT COUNT(*) FROM locacoes WHERE status='ativa' AND data_prevista < ?", hoje),
        "faturamento_mes": escalar(
            "SELECT COALESCE(SUM(valor_total), 0) FROM locacoes"
            " WHERE status='finalizada' AND substr(data_devolucao, 1, 7) = ?", mes),
    }
