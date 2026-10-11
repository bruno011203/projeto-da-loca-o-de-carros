"""Popula o banco com dados de exemplo: python seed.py"""
from datetime import date, timedelta

from locadora import create_app
from locadora.db import get_db
from locadora.servicos import abrir_locacao, devolver_veiculo, salvar_cliente, salvar_veiculo

hoje = date.today()
d = lambda dias: (hoje + timedelta(days=dias)).isoformat()

app = create_app()
with app.app_context():
    db = get_db()
    if db.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]:
        raise SystemExit("O banco já possui dados; nada foi alterado.")

    clientes = [
        salvar_cliente(db, {"nome": "Ana Souza", "cpf": "529.982.247-25", "cnh": "01234567890",
                            "validade_cnh": d(900), "telefone": "(11) 98888-1111", "email": "ana@exemplo.com"}),
        salvar_cliente(db, {"nome": "Carlos Lima", "cpf": "111.444.777-35", "cnh": "09876543210",
                            "validade_cnh": d(400), "telefone": "(21) 97777-2222"}),
        salvar_cliente(db, {"nome": "Mariana Rocha", "cpf": "390.533.447-05", "cnh": "11223344556",
                            "validade_cnh": d(700), "email": "mariana@exemplo.com"}),
    ]
    veiculos = [
        salvar_veiculo(db, {"placa": "ABC1D23", "marca": "Fiat", "modelo": "Mobi", "ano": 2023, "cor": "Branco",
                            "categoria": "Econômico", "valor_diaria": "119.90", "km_atual": 15200}),
        salvar_veiculo(db, {"placa": "BRA2E19", "marca": "Chevrolet", "modelo": "Onix", "ano": 2024, "cor": "Prata",
                            "categoria": "Intermediário", "valor_diaria": "159.90", "km_atual": 8300}),
        salvar_veiculo(db, {"placa": "XYZ9876", "marca": "Jeep", "modelo": "Compass", "ano": 2022, "cor": "Preto",
                            "categoria": "SUV", "valor_diaria": "289.00", "km_atual": 41000}),
        salvar_veiculo(db, {"placa": "QWE4R56", "marca": "Toyota", "modelo": "Corolla", "ano": 2024, "cor": "Cinza",
                            "categoria": "Executivo", "valor_diaria": "329.00", "km_atual": 5100}),
        salvar_veiculo(db, {"placa": "FOR1A22", "marca": "Fiat", "modelo": "Strada", "ano": 2023, "cor": "Vermelho",
                            "categoria": "Utilitário", "valor_diaria": "199.00", "km_atual": 22000}),
    ]
    finalizada = abrir_locacao(db, clientes[0], veiculos[3], d(-10), d(-6))
    devolver_veiculo(db, finalizada, d(-5), 5900)
    abrir_locacao(db, clientes[0], veiculos[0], d(-2), d(3))
    abrir_locacao(db, clientes[1], veiculos[2], d(-6), d(-1))  # em atraso
    db.execute("UPDATE veiculos SET status = 'manutencao' WHERE id = ?", (veiculos[4],))
    db.commit()
    print("Dados de exemplo criados.")
