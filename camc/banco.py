"""Camada de dados da CAMC: conexão com o SQLite e criação do esquema.

O banco é um único arquivo (dados/camc.db), o que facilita o backup descrito
no plano de segurança. Defina a variável de ambiente CAMC_DADOS para usar outra
pasta.
"""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_DADOS = Path(os.environ.get("CAMC_DADOS", RAIZ / "dados"))
PASTA_BACKUPS = PASTA_DADOS / "backups"


def caminho_banco() -> Path:
    return PASTA_DADOS / "camc.db"


def agora() -> str:
    """Data e hora local no formato AAAA-MM-DD HH:MM:SS."""
    return datetime.now().replace(microsecond=0).isoformat(sep=" ")


def restringir_permissoes(caminho: Path, eh_diretorio: bool = False) -> None:
    """Restringe permissões de arquivos/diretórios em sistemas POSIX (0700/0600)."""
    if os.name != "posix":
        return
    try:
        os.chmod(caminho, 0o700 if eh_diretorio else 0o600)
    except OSError:
        pass


def normalizar_email(texto: str) -> str:
    """Normaliza e-mails para detecção de unicidade (lowercase, remoção de +tag e pontos no Gmail)."""
    email = (texto or "").strip().lower()
    if "@" not in email:
        return ""
    local, dominio = email.rsplit("@", 1)
    if not local or not dominio:
        return ""
    local = local.split("+", 1)[0]
    if dominio == "googlemail.com":
        dominio = "gmail.com"
    if dominio == "gmail.com":
        local = local.replace(".", "")
    if not local:
        return ""
    return f"{local}@{dominio}"


def conectar(caminho=None) -> sqlite3.Connection:
    """Abre uma conexão (criando a pasta e o arquivo, se necessário)."""
    destino = Path(caminho) if caminho else caminho_banco()
    destino.parent.mkdir(parents=True, exist_ok=True)
    restringir_permissoes(destino.parent, eh_diretorio=True)
    con = sqlite3.connect(str(destino))
    restringir_permissoes(destino, eh_diretorio=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.execute("PRAGMA secure_delete = ON")
    return con


# Gatilhos que tornam a tabela de auditoria "somente acréscimo": o próprio banco
# recusa UPDATE e DELETE. A cadeia de hashes protege contra quem editar o
# arquivo por fora do sistema.
GATILHO_SEM_UPDATE = (
    "CREATE TRIGGER IF NOT EXISTS auditoria_sem_update BEFORE UPDATE ON auditoria "
    "BEGIN SELECT RAISE(ABORT, 'Registros de auditoria não podem ser alterados.'); END"
)
GATILHO_SEM_DELETE = (
    "CREATE TRIGGER IF NOT EXISTS auditoria_sem_delete BEFORE DELETE ON auditoria "
    "BEGIN SELECT RAISE(ABORT, 'Registros de auditoria não podem ser excluídos.'); END"
)

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    login         TEXT NOT NULL UNIQUE,
    nome          TEXT NOT NULL,
    perfil        TEXT NOT NULL,
    senha_hash    TEXT NOT NULL,
    salt          TEXT NOT NULL,
    iteracoes     INTEGER NOT NULL,
    ativo         INTEGER NOT NULL DEFAULT 1,
    tentativas    INTEGER NOT NULL DEFAULT 0,
    bloqueado_ate TEXT,
    token_versao  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS sessoes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id   INTEGER NOT NULL REFERENCES usuarios(id),
    token_hash   TEXT NOT NULL UNIQUE,
    refresh_hash TEXT NOT NULL UNIQUE,
    criada_em    TEXT NOT NULL,
    expira_em    TEXT NOT NULL,
    revogada_em  TEXT
);

CREATE TABLE IF NOT EXISTS login_rate_limit (
    chave         TEXT PRIMARY KEY,
    tentativas    INTEGER NOT NULL DEFAULT 0,
    janela_inicio TEXT NOT NULL,
    bloqueado_ate TEXT
);

CREATE TABLE IF NOT EXISTS clientes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    nome              TEXT NOT NULL,
    tipo              TEXT NOT NULL CHECK (tipo IN ('PF', 'PJ')),
    documento         TEXT NOT NULL DEFAULT '',
    telefone          TEXT NOT NULL DEFAULT '',
    email             TEXT NOT NULL DEFAULT '',
    email_normalizado TEXT NOT NULL DEFAULT '',
    cidade            TEXT NOT NULL DEFAULT '',
    canal_preferido   TEXT NOT NULL,
    segmento          TEXT NOT NULL,
    consentimento_em  TEXT,
    anonimizado       INTEGER NOT NULL DEFAULT 0,
    criado_em         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS anotacoes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    autor      TEXT NOT NULL,
    texto      TEXT NOT NULL,
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS interacoes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    canal      TEXT NOT NULL,
    texto      TEXT NOT NULL,
    criado_em  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS produtos (
    id    INTEGER PRIMARY KEY,
    nome  TEXT NOT NULL,
    curto TEXT NOT NULL,
    preco REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS lotes (
    codigo TEXT PRIMARY KEY,
    nome   TEXT NOT NULL,
    tipo   TEXT NOT NULL,
    venda  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS lote_insumos (
    lote   TEXT NOT NULL REFERENCES lotes(codigo),
    insumo TEXT NOT NULL REFERENCES lotes(codigo),
    PRIMARY KEY (lote, insumo)
);

CREATE TABLE IF NOT EXISTS lote_etapas (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lote        TEXT NOT NULL REFERENCES lotes(codigo),
    ordem       INTEGER NOT NULL,
    tipo        TEXT NOT NULL,
    titulo      TEXT NOT NULL,
    subtitulo   TEXT NOT NULL DEFAULT '',
    data        TEXT NOT NULL,
    responsavel TEXT NOT NULL DEFAULT '',
    medidas     TEXT NOT NULL DEFAULT '',
    entrada_kg  REAL,
    saida_kg    REAL
);

CREATE TABLE IF NOT EXISTS pedidos (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id    INTEGER NOT NULL REFERENCES clientes(id),
    criado_em     TEXT NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('separacao', 'postado', 'em_rota', 'entregue')),
    transportadora TEXT NOT NULL DEFAULT '',
    rastreio      TEXT NOT NULL DEFAULT '',
    postado_em    TEXT,
    entregue_em   TEXT
);

CREATE TABLE IF NOT EXISTS pedido_itens (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id      INTEGER NOT NULL REFERENCES pedidos(id),
    produto_id     INTEGER NOT NULL REFERENCES produtos(id),
    quantidade     INTEGER NOT NULL CHECK (quantidade > 0),
    lote           TEXT NOT NULL REFERENCES lotes(codigo),
    preco_unitario REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS tickets (
    id                   INTEGER PRIMARY KEY,
    protocolo            TEXT NOT NULL UNIQUE,
    cliente_id           INTEGER NOT NULL REFERENCES clientes(id),
    canal                TEXT NOT NULL,
    categoria            TEXT NOT NULL,
    prioridade           TEXT NOT NULL,
    status               TEXT NOT NULL,
    assunto              TEXT NOT NULL,
    pedido_id            INTEGER REFERENCES pedidos(id),
    lote                 TEXT REFERENCES lotes(codigo),
    responsavel          TEXT NOT NULL DEFAULT '',
    criado_em            TEXT NOT NULL,
    primeira_resposta_em TEXT,
    resolvido_em         TEXT,
    escalonado           INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ticket_eventos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id INTEGER NOT NULL REFERENCES tickets(id),
    tipo      TEXT NOT NULL,
    autor     TEXT NOT NULL,
    texto     TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedbacks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    pedido_id  INTEGER NOT NULL UNIQUE REFERENCES pedidos(id),
    cliente_id INTEGER NOT NULL REFERENCES clientes(id),
    lote       TEXT,
    nota       INTEGER NOT NULL CHECK (nota BETWEEN 1 AND 5),
    etiquetas  TEXT NOT NULL DEFAULT '',
    comentario TEXT NOT NULL DEFAULT '',
    criado_em  TEXT NOT NULL,
    cliques    INTEGER,
    segundos   INTEGER
);

CREATE TABLE IF NOT EXISTS auditoria (
    n             INTEGER PRIMARY KEY AUTOINCREMENT,
    quando        TEXT NOT NULL,
    usuario       TEXT NOT NULL,
    acao          TEXT NOT NULL,
    detalhe       TEXT NOT NULL,
    hash_anterior TEXT NOT NULL,
    hash          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS config (
    chave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);
"""


def inicializar(con: sqlite3.Connection) -> None:
    """Cria as tabelas, índices de unicidade e gatilhos de proteção, se ainda não existirem."""
    con.executescript(ESQUEMA)
    # Migrações seguras para bancos já existentes
    cols_usuarios = {r["name"] for r in con.execute("PRAGMA table_info(usuarios)")}
    if "token_versao" not in cols_usuarios:
        con.execute("ALTER TABLE usuarios ADD COLUMN token_versao INTEGER NOT NULL DEFAULT 1")
    cols_clientes = {r["name"] for r in con.execute("PRAGMA table_info(clientes)")}
    if "email_normalizado" not in cols_clientes:
        con.execute("ALTER TABLE clientes ADD COLUMN email_normalizado TEXT NOT NULL DEFAULT ''")
    for c in con.execute("SELECT id, email FROM clientes WHERE anonimizado = 0 AND email != '' AND email_normalizado = ''").fetchall():
        con.execute("UPDATE clientes SET email_normalizado = ? WHERE id = ?", (normalizar_email(c["email"]), c["id"]))
    con.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_email_norm "
        "ON clientes(email_normalizado) WHERE anonimizado = 0 AND email_normalizado != ''"
    )
    con.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_documento "
        "ON clientes(documento) WHERE anonimizado = 0 AND documento != ''"
    )
    con.execute(
        "CREATE INDEX IF NOT EXISTS idx_sessoes_usuario_ativa "
        "ON sessoes(usuario_id) WHERE revogada_em IS NULL"
    )
    con.execute(GATILHO_SEM_UPDATE)
    con.execute(GATILHO_SEM_DELETE)
    con.commit()


def banco_vazio(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0] == 0
