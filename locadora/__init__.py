import os

from flask import Flask, render_template

from . import db, rotas, servicos


def create_app(config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.update(
        SECRET_KEY=os.environ.get("SECRET_KEY", "troque-esta-chave-em-producao"),
        DATABASE=os.path.join(app.instance_path, "locadora.sqlite3"),
    )
    if config:
        app.config.update(config)
    os.makedirs(app.instance_path, exist_ok=True)

    db.init_app(app)
    app.register_blueprint(rotas.bp)
    app.register_error_handler(404, lambda _e: (render_template("404.html"), 404))

    @app.template_filter("moeda")
    def moeda(valor):
        texto = f"{valor or 0:,.2f}"
        return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")

    @app.template_filter("data_br")
    def data_br(valor):
        if not valor:
            return "—"
        ano, mes, dia = str(valor)[:10].split("-")
        return f"{dia}/{mes}/{ano}"

    app.jinja_env.filters["cpf"] = servicos.formatar_cpf
    app.jinja_env.globals.update(
        STATUS_VEICULO=servicos.STATUS_VEICULO,
        STATUS_LOCACAO=servicos.STATUS_LOCACAO,
        CATEGORIAS=servicos.CATEGORIAS,
    )
    return app
