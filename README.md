# Sistema de Gestão para Locadora de Automóveis

Aplicação web em **Python + Flask + SQLite** para gerenciar clientes, frota e locações.

## Funcionalidades

- **Painel**: veículos disponíveis/locados/em manutenção, locações ativas e em atraso,
  faturamento do mês e devoluções previstas para os próximos dias.
- **Clientes**: cadastro com validação de CPF (dígitos verificadores), CNH e validade,
  busca por nome/CPF e histórico de locações.
- **Veículos**: cadastro com placa no padrão antigo ou Mercosul, categoria, diária e
  quilometragem; filtro por status; envio para manutenção e liberação.
- **Locações**: abertura, devolução (com prévia do valor) e cancelamento.

## Regras de negócio

| Regra | Onde |
|---|---|
| Só é possível locar veículos com status *Disponível* | `abrir_locacao` |
| A CNH do cliente precisa ser válida até o fim da locação | `abrir_locacao` |
| Cliente com locação em atraso não pode fazer nova locação | `abrir_locacao` |
| A devolução prevista deve ser depois da retirada | `abrir_locacao` |
| O valor da diária é congelado no momento da locação | `abrir_locacao` |
| Cobrança mínima de 1 diária | `calcular_diarias` |
| Cada dia de atraso gera multa de 20% sobre a diária (além da diária) | `calcular_fechamento` |
| Km de devolução não pode ser menor que o de retirada; atualiza o km do veículo | `devolver_veiculo` |
| Clientes e veículos com histórico de locações não podem ser excluídos | `excluir_cliente` / `excluir_veiculo` |
| CPF e placa são únicos | `salvar_cliente` / `salvar_veiculo` |

Todas as regras ficam em `locadora/servicos.py`; os valores (multa, categorias) são
constantes no topo do arquivo e podem ser ajustados.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python seed.py                   # opcional: cria dados de exemplo
python app.py                    # abre em http://127.0.0.1:5000
```

O banco SQLite é criado automaticamente em `instance/locadora.sqlite3`.

## Testes

```bash
pytest
```

## Estrutura

```
app.py                 ponto de entrada
seed.py                dados de exemplo
locadora/
  __init__.py          criação da aplicação e filtros de template (moeda, data)
  db.py                conexão com SQLite
  schema.sql           tabelas: clientes, veiculos, locacoes
  servicos.py          regras de negócio
  rotas.py             páginas e formulários
  templates/           HTML (Jinja2)
  static/style.css     estilos
tests/                 testes automatizados (pytest)
```
