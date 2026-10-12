# Sistema de Gestão para Locadora de Veículos

Sistema web que controla o ciclo completo de uma locação: **reserva → retirada → devolução**,
com apuração automática de diárias, multa por atraso e taxa de combustível.

- **Stack:** Python 3.12+ · Django 5.2 LTS · SQLite · Bootstrap 5 (CDN)
- **Documentação completa:** [`docs/Documentacao_Final.docx`](docs/Documentacao_Final.docx)

## Casos de uso entregues

| Caso de uso | Regras | Onde |
|---|---|---|
| UC01 — Manter veículo | RN05, RN07 | Telas *Veículos* e Django Admin |
| UC02 — Manter cliente | RN01, RN02, RN03 | Telas *Clientes* e Django Admin |
| UC03 — Consultar disponibilidade e reservar | RN04, RN06, RN08, RN09, RN10, RN11, RN12 | *Disponibilidade* e *Reservas* |
| UC04 — Registrar retirada | RN13, RN14, RN15 | *Reservas → Retirar* e *Locação de balcão* |
| UC05 — Registrar devolução e apurar valores | RN16, RN17, RN18, RN19 | *Locações → Devolver* |

## Pré-requisitos

- Python 3.12 ou superior
- Navegador atualizado (Chrome, Edge, Firefox ou Safari) com acesso à internet para carregar o Bootstrap por CDN

## Instalação e execução

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt

python manage.py migrate
python manage.py seed                # dados de exemplo (use --reset para recriar)
python manage.py runserver
```

Acesse <http://127.0.0.1:8000> e entre com um dos usuários criados pelo `seed`:

| Login | Senha | Perfil |
|---|---|---|
| `gerente` | `locadora123` | Gerente — também acessa o admin em `/admin` |
| `atendente` | `locadora123` | Atendente |

## Testes

```bash
python manage.py test
```

São 64 testes: fórmulas de cálculo (`test_services.py`), regras de negócio puras
(`test_rules.py`) e integração com banco e interface (`test_views.py`), incluindo o
exemplo numérico do documento de regras (total de R$ 690,00).

## Estrutura

```
config/                 configurações do projeto Django (pt-br, America/Sao_Paulo, USE_TZ)
locacao/
  enums.py              StatusVeiculo, StatusReserva, StatusLocacao, CategoriaCNH, NivelCombustivel, PerfilUsuario
  models.py             as 7 entidades (Cliente+CNH, Categoria, Veiculo, Reserva, Locacao, Funcionario)
  services.py           as 5 fórmulas de cálculo — funções puras, Decimal HALF_UP
  rules.py              validações RN01–RN19 — funções puras
  operacoes.py          casos de uso UC03–UC05 (transações com o banco)
  forms.py · views.py · urls.py · admin.py
  management/commands/seed.py
  templates/locacao/    telas em Bootstrap 5
  tests/                test_services.py · test_rules.py · test_views.py
docs/
  diagramas/            fontes Mermaid (.mmd) e imagens (.png)
  prototipos/           baixa fidelidade (wireframes) e alta fidelidade (capturas)
  Documentacao_Final.docx
```

## Fluxo de trabalho

GitHub Flow com `main` (entregue), `develop` (integração) e `feature/<caso-de-uso>`.
Commits no padrão Conventional Commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`).
