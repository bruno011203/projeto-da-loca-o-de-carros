from datetime import date, timedelta

from flask import Blueprint, abort, flash, redirect, render_template, request, url_for

from .db import get_db
from .servicos import (
    RegraNegocioError, abrir_locacao, alterar_status_veiculo, calcular_fechamento,
    cancelar_locacao, devolver_veiculo, excluir_cliente, excluir_veiculo, resumo_painel,
    salvar_cliente, salvar_veiculo,
)

bp = Blueprint("locadora", __name__)

LOCACOES_SQL = """
    SELECT l.*, c.nome AS cliente_nome, c.cpf AS cliente_cpf,
           v.placa, v.marca, v.modelo
      FROM locacoes l
      JOIN clientes c ON c.id = l.cliente_id
      JOIN veiculos v ON v.id = l.veiculo_id
"""


def _buscar(sql, *params):
    registro = get_db().execute(sql, params).fetchone()
    if registro is None:
        abort(404)
    return registro


# --------------------------------------------------------------------------- painel

@bp.route("/")
def painel():
    db = get_db()
    hoje = date.today().isoformat()
    atrasadas = db.execute(
        LOCACOES_SQL + " WHERE l.status='ativa' AND l.data_prevista < ? ORDER BY l.data_prevista",
        (hoje,)).fetchall()
    proximas = db.execute(
        LOCACOES_SQL + " WHERE l.status='ativa' AND l.data_prevista BETWEEN ? AND ?"
        " ORDER BY l.data_prevista",
        (hoje, (date.today() + timedelta(days=3)).isoformat())).fetchall()
    return render_template("painel.html", resumo=resumo_painel(db), atrasadas=atrasadas,
                           proximas=proximas, hoje=hoje)


# --------------------------------------------------------------------------- clientes

@bp.route("/clientes")
def clientes():
    busca = request.args.get("q", "").strip()
    sql, params = "SELECT * FROM clientes", ()
    if busca:
        sql += " WHERE nome LIKE ? OR cpf LIKE ?"
        params = (f"%{busca}%", f"%{''.join(filter(str.isdigit, busca)) or busca}%")
    lista = get_db().execute(sql + " ORDER BY nome", params).fetchall()
    return render_template("clientes/lista.html", clientes=lista, busca=busca)


@bp.route("/clientes/novo", methods=["GET", "POST"])
@bp.route("/clientes/<int:cliente_id>/editar", methods=["GET", "POST"])
def cliente_form(cliente_id=None):
    cliente = _buscar("SELECT * FROM clientes WHERE id = ?", cliente_id) if cliente_id else None
    if request.method == "POST":
        try:
            salvar_cliente(get_db(), request.form, cliente_id)
        except RegraNegocioError as erro:
            flash(str(erro), "erro")
            return render_template("clientes/form.html", cliente=dict(request.form, id=cliente_id)), 400
        flash("Cliente salvo com sucesso.", "sucesso")
        return redirect(url_for("locadora.clientes"))
    return render_template("clientes/form.html", cliente=cliente or {})


@bp.route("/clientes/<int:cliente_id>")
def cliente_detalhe(cliente_id):
    cliente = _buscar("SELECT * FROM clientes WHERE id = ?", cliente_id)
    historico = get_db().execute(
        LOCACOES_SQL + " WHERE l.cliente_id = ? ORDER BY l.data_retirada DESC", (cliente_id,)
    ).fetchall()
    return render_template("clientes/detalhe.html", cliente=cliente, historico=historico,
                           hoje=date.today().isoformat())


@bp.post("/clientes/<int:cliente_id>/excluir")
def cliente_excluir(cliente_id):
    try:
        excluir_cliente(get_db(), cliente_id)
        flash("Cliente excluído.", "sucesso")
    except RegraNegocioError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("locadora.clientes"))


# --------------------------------------------------------------------------- veículos

@bp.route("/veiculos")
def veiculos():
    status = request.args.get("status", "")
    sql, params = "SELECT * FROM veiculos", ()
    if status:
        sql, params = sql + " WHERE status = ?", (status,)
    lista = get_db().execute(sql + " ORDER BY marca, modelo", params).fetchall()
    return render_template("veiculos/lista.html", veiculos=lista, status=status)


@bp.route("/veiculos/novo", methods=["GET", "POST"])
@bp.route("/veiculos/<int:veiculo_id>/editar", methods=["GET", "POST"])
def veiculo_form(veiculo_id=None):
    veiculo = _buscar("SELECT * FROM veiculos WHERE id = ?", veiculo_id) if veiculo_id else None
    if request.method == "POST":
        try:
            salvar_veiculo(get_db(), request.form, veiculo_id)
        except RegraNegocioError as erro:
            flash(str(erro), "erro")
            return render_template("veiculos/form.html", veiculo=dict(request.form, id=veiculo_id)), 400
        flash("Veículo salvo com sucesso.", "sucesso")
        return redirect(url_for("locadora.veiculos"))
    return render_template("veiculos/form.html", veiculo=veiculo or {})


@bp.post("/veiculos/<int:veiculo_id>/status")
def veiculo_status(veiculo_id):
    try:
        alterar_status_veiculo(get_db(), veiculo_id, request.form.get("status"))
        flash("Status do veículo atualizado.", "sucesso")
    except RegraNegocioError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("locadora.veiculos"))


@bp.post("/veiculos/<int:veiculo_id>/excluir")
def veiculo_excluir(veiculo_id):
    try:
        excluir_veiculo(get_db(), veiculo_id)
        flash("Veículo excluído.", "sucesso")
    except RegraNegocioError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("locadora.veiculos"))


# --------------------------------------------------------------------------- locações

@bp.route("/locacoes")
def locacoes():
    status = request.args.get("status", "")
    sql, params = LOCACOES_SQL, ()
    if status:
        sql, params = sql + " WHERE l.status = ?", (status,)
    lista = get_db().execute(sql + " ORDER BY l.data_retirada DESC, l.id DESC", params).fetchall()
    return render_template("locacoes/lista.html", locacoes=lista, status=status,
                           hoje=date.today().isoformat())


@bp.route("/locacoes/nova", methods=["GET", "POST"])
def locacao_nova():
    db = get_db()
    form = request.form if request.method == "POST" else {
        "data_retirada": date.today().isoformat(),
        "data_prevista": (date.today() + timedelta(days=1)).isoformat(),
        "veiculo_id": request.args.get("veiculo_id", ""),
        "cliente_id": request.args.get("cliente_id", ""),
    }
    if request.method == "POST":
        try:
            locacao_id = abrir_locacao(
                db, form.get("cliente_id", type=int), form.get("veiculo_id", type=int),
                form.get("data_retirada"), form.get("data_prevista"), form.get("observacoes"))
            flash("Locação registrada com sucesso.", "sucesso")
            return redirect(url_for("locadora.locacao_detalhe", locacao_id=locacao_id))
        except RegraNegocioError as erro:
            flash(str(erro), "erro")
    clientes_ = db.execute("SELECT id, nome, cpf FROM clientes ORDER BY nome").fetchall()
    veiculos_ = db.execute(
        "SELECT * FROM veiculos WHERE status='disponivel' ORDER BY marca, modelo").fetchall()
    status_http = 400 if request.method == "POST" else 200
    return render_template("locacoes/form.html", form=form, clientes=clientes_,
                           veiculos=veiculos_), status_http


@bp.route("/locacoes/<int:locacao_id>")
def locacao_detalhe(locacao_id):
    locacao = _buscar(LOCACOES_SQL + " WHERE l.id = ?", locacao_id)
    return render_template("locacoes/detalhe.html", locacao=locacao,
                           hoje=date.today().isoformat())


@bp.route("/locacoes/<int:locacao_id>/devolucao", methods=["GET", "POST"])
def locacao_devolucao(locacao_id):
    locacao = _buscar(LOCACOES_SQL + " WHERE l.id = ?", locacao_id)
    if locacao["status"] != "ativa":
        flash("Esta locação não está ativa.", "erro")
        return redirect(url_for("locadora.locacao_detalhe", locacao_id=locacao_id))

    data_devolucao = request.values.get("data_devolucao") or date.today().isoformat()
    km_devolucao = request.values.get("km_devolucao") or locacao["km_retirada"]
    if request.method == "POST":
        try:
            total = devolver_veiculo(get_db(), locacao_id, data_devolucao, km_devolucao)
            flash(f"Devolução registrada. Valor total: R$ {total:.2f}".replace(".", ","), "sucesso")
            return redirect(url_for("locadora.locacao_detalhe", locacao_id=locacao_id))
        except RegraNegocioError as erro:
            flash(str(erro), "erro")

    try:
        diarias, multa, total = calcular_fechamento(
            locacao["valor_diaria"], locacao["data_retirada"], locacao["data_prevista"],
            data_devolucao)
    except RegraNegocioError:
        diarias, multa, total = 0, 0, 0
    return render_template("locacoes/devolucao.html", locacao=locacao,
                           data_devolucao=data_devolucao, km_devolucao=km_devolucao,
                           diarias=diarias, multa=multa, total=total)


@bp.post("/locacoes/<int:locacao_id>/cancelar")
def locacao_cancelar(locacao_id):
    try:
        cancelar_locacao(get_db(), locacao_id)
        flash("Locação cancelada.", "sucesso")
    except RegraNegocioError as erro:
        flash(str(erro), "erro")
    return redirect(url_for("locadora.locacao_detalhe", locacao_id=locacao_id))
