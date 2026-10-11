CREATE TABLE IF NOT EXISTS clientes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nome        TEXT    NOT NULL,
    cpf         TEXT    NOT NULL UNIQUE,
    cnh         TEXT    NOT NULL,
    validade_cnh TEXT   NOT NULL,
    telefone    TEXT,
    email       TEXT,
    endereco    TEXT,
    criado_em   TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS veiculos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    placa         TEXT    NOT NULL UNIQUE,
    marca         TEXT    NOT NULL,
    modelo        TEXT    NOT NULL,
    ano           INTEGER NOT NULL,
    cor           TEXT,
    categoria     TEXT    NOT NULL,
    valor_diaria  REAL    NOT NULL CHECK (valor_diaria > 0),
    km_atual      INTEGER NOT NULL DEFAULT 0 CHECK (km_atual >= 0),
    status        TEXT    NOT NULL DEFAULT 'disponivel'
                  CHECK (status IN ('disponivel', 'locado', 'manutencao')),
    criado_em     TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS locacoes (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id          INTEGER NOT NULL REFERENCES clientes(id),
    veiculo_id          INTEGER NOT NULL REFERENCES veiculos(id),
    data_retirada       TEXT    NOT NULL,
    data_prevista       TEXT    NOT NULL,
    data_devolucao      TEXT,
    km_retirada         INTEGER NOT NULL,
    km_devolucao        INTEGER,
    valor_diaria        REAL    NOT NULL,
    valor_previsto      REAL    NOT NULL,
    multa               REAL    NOT NULL DEFAULT 0,
    valor_total         REAL,
    status              TEXT    NOT NULL DEFAULT 'ativa'
                        CHECK (status IN ('ativa', 'finalizada', 'cancelada')),
    observacoes         TEXT,
    criado_em           TEXT    NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_locacoes_status ON locacoes(status);
CREATE INDEX IF NOT EXISTS idx_locacoes_cliente ON locacoes(cliente_id);
CREATE INDEX IF NOT EXISTS idx_locacoes_veiculo ON locacoes(veiculo_id);
