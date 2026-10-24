"""Segurança e auditoria (Passo 2 do Projeto Integrado).

- senhas com PBKDF2-HMAC-SHA256 e sal individual;
- perfis de acesso (RBAC) com permissões mínimas;
- bloqueio temporário após tentativas de login malsucedidas;
- trilha de auditoria com encadeamento de hashes (SHA-256);
- backup com verificação de integridade e teste de restauração.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import shutil
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from . import banco

ITERACOES = 200_000
MAX_TENTATIVAS = 5
BLOQUEIO_MINUTOS = 5
ZERO = "0" * 64


class ErroAutenticacao(Exception):
    """Login ou senha inválidos, conta bloqueada ou desativada."""


class PermissaoNegada(Exception):
    """O perfil do usuário não tem permissão para a ação."""


# ---------------------------------------------------------------- perfis (RBAC)
PERFIS = {
    "atendente": {
        "nome": "Atendente",
        "permissoes": {
            "painel.ver", "clientes.ver", "clientes.editar", "clientes.anotar",
            "tickets.ver", "tickets.criar", "tickets.editar", "rastreio.ver",
            "feedback.simular",
        },
    },
    "gestor": {
        "nome": "Gestor",
        "permissoes": {
            "painel.ver", "clientes.ver", "clientes.anotar", "clientes.anonimizar",
            "tickets.ver", "tickets.criar", "tickets.editar", "rastreio.ver",
            "auditoria.ver", "auditoria.verificar", "feedback.simular",
        },
    },
    "logistica": {
        "nome": "Logística",
        "permissoes": {
            "painel.ver", "clientes.ver", "tickets.ver", "tickets.editar_rastreio",
            "rastreio.ver",
        },
    },
    "producao": {
        "nome": "Produção",
        "permissoes": {"painel.ver", "rastreio.ver", "lotes.registrar"},
    },
    "auditor": {
        "nome": "Auditor",
        "permissoes": {
            "painel.ver", "clientes.ver", "tickets.ver", "rastreio.ver",
            "auditoria.ver", "auditoria.verificar",
        },
    },
    "admin_ti": {
        "nome": "Administrador de TI",
        "permissoes": {"auditoria.ver", "backup.executar", "backup.testar", "usuarios.gerir"},
    },
}


def tem_permissao(perfil: str, permissao: str) -> bool:
    return permissao in PERFIS.get(perfil, {}).get("permissoes", set())


@dataclass(frozen=True)
class Sessao:
    usuario_id: int
    login: str
    nome: str
    perfil: str

    @property
    def perfil_nome(self) -> str:
        return PERFIS[self.perfil]["nome"]

    @property
    def rotulo(self) -> str:
        return f"{self.nome} ({self.perfil_nome})"

    def pode(self, permissao: str) -> bool:
        return tem_permissao(self.perfil, permissao)


# ---------------------------------------------------------------------- senhas
def hash_senha(senha: str, sal: str | None = None, iteracoes: int = ITERACOES):
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), iteracoes)
    return h.hex(), sal, iteracoes


def verificar_senha(senha: str, hash_hex: str, sal: str, iteracoes: int) -> bool:
    calculado, _, _ = hash_senha(senha, sal, iteracoes)
    return hmac.compare_digest(calculado, hash_hex)


def validar_forca_senha(senha: str) -> str | None:
    """Retorna a mensagem de erro ou None se a senha atender à política."""
    if len(senha) < 12:
        return "A senha deve ter pelo menos 12 caracteres."
    if not any(c.isalpha() for c in senha) or not any(c.isdigit() for c in senha):
        return "A senha deve combinar letras e números."
    return None


# ------------------------------------------------------------------- auditoria
def _texto_registro(n, quando, usuario, acao, detalhe, anterior) -> str:
    return "|".join([str(n), quando, usuario, acao, detalhe, anterior])


def registrar_auditoria(con: sqlite3.Connection, usuario: str, acao: str, detalhe: str,
                        quando: str | None = None) -> int:
    """Acrescenta um registro à cadeia. Quem chama é responsável pelo commit."""
    ultimo = con.execute("SELECT n, hash FROM auditoria ORDER BY n DESC LIMIT 1").fetchone()
    n = (ultimo["n"] + 1) if ultimo else 1
    anterior = ultimo["hash"] if ultimo else ZERO
    quando = quando or banco.agora()
    h = hashlib.sha256(_texto_registro(n, quando, usuario, acao, detalhe, anterior).encode("utf-8")).hexdigest()
    con.execute(
        "INSERT INTO auditoria (n, quando, usuario, acao, detalhe, hash_anterior, hash) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (n, quando, usuario, acao, detalhe, anterior, h),
    )
    return n


def verificar_cadeia(con: sqlite3.Connection):
    """Recalcula toda a cadeia. Retorna (íntegra, primeira_quebra, total)."""
    anterior = ZERO
    total = 0
    for r in con.execute("SELECT * FROM auditoria ORDER BY n"):
        total += 1
        esperado = hashlib.sha256(
            _texto_registro(r["n"], r["quando"], r["usuario"], r["acao"], r["detalhe"], r["hash_anterior"]).encode("utf-8")
        ).hexdigest()
        if r["hash_anterior"] != anterior or esperado != r["hash"]:
            return False, r["n"], total
        anterior = r["hash"]
    return True, None, total


def simular_adulteracao(con: sqlite3.Connection) -> int:
    """DEMONSTRAÇÃO: altera um registro antigo por fora das regras do sistema,
    como faria alguém com acesso direto ao arquivo do banco."""
    if con.execute("SELECT 1 FROM config WHERE chave = 'demo_adulteracao'").fetchone():
        raise ValueError("Já existe uma adulteração simulada. Desfaça-a antes.")
    r = con.execute("SELECT n, detalhe FROM auditoria ORDER BY n LIMIT 1 OFFSET 2").fetchone()
    if r is None:
        raise ValueError("Ainda não há registros suficientes para a demonstração.")
    con.execute("DROP TRIGGER IF EXISTS auditoria_sem_update")
    con.execute("UPDATE auditoria SET detalhe = detalhe || ' (valor alterado fora do sistema)' WHERE n = ?", (r["n"],))
    con.execute(banco.GATILHO_SEM_UPDATE)
    con.execute("INSERT INTO config (chave, valor) VALUES ('demo_adulteracao', ?)",
                (json.dumps({"n": r["n"], "detalhe": r["detalhe"]}),))
    con.commit()
    return r["n"]


def desfazer_adulteracao(con: sqlite3.Connection) -> bool:
    c = con.execute("SELECT valor FROM config WHERE chave = 'demo_adulteracao'").fetchone()
    if not c:
        return False
    info = json.loads(c["valor"])
    con.execute("DROP TRIGGER IF EXISTS auditoria_sem_update")
    con.execute("UPDATE auditoria SET detalhe = ? WHERE n = ?", (info["detalhe"], info["n"]))
    con.execute(banco.GATILHO_SEM_UPDATE)
    con.execute("DELETE FROM config WHERE chave = 'demo_adulteracao'")
    con.commit()
    return True


def adulteracao_ativa(con: sqlite3.Connection) -> bool:
    return con.execute("SELECT 1 FROM config WHERE chave = 'demo_adulteracao'").fetchone() is not None


# ----------------------------------------------------------------------- login
def autenticar(con: sqlite3.Connection, login: str, senha: str) -> Sessao:
    generica = "Login ou senha incorretos."
    u = con.execute("SELECT * FROM usuarios WHERE login = ?", (login.strip().lower(),)).fetchone()
    if u is None:
        registrar_auditoria(con, "Anônimo", "Falha de login", "Tentativa com login inexistente.")
        con.commit()
        raise ErroAutenticacao(generica)
    agora = datetime.now()
    if u["bloqueado_ate"] and datetime.fromisoformat(u["bloqueado_ate"]) > agora:
        raise ErroAutenticacao("Conta bloqueada temporariamente por excesso de tentativas. Tente novamente em alguns minutos.")
    if not u["ativo"]:
        registrar_auditoria(con, u["nome"], "Falha de login", "Usuário desativado tentou entrar.")
        con.commit()
        raise ErroAutenticacao("Usuário desativado. Fale com o administrador de TI.")
    if not verificar_senha(senha, u["senha_hash"], u["salt"], u["iteracoes"]):
        tentativas = u["tentativas"] + 1
        bloqueio = None
        detalhe = f"Senha incorreta ({tentativas} de {MAX_TENTATIVAS})."
        if tentativas >= MAX_TENTATIVAS:
            bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).replace(microsecond=0).isoformat(sep=" ")
            tentativas = 0
            detalhe = f"Conta bloqueada por {BLOQUEIO_MINUTOS} minutos após {MAX_TENTATIVAS} tentativas."
        con.execute("UPDATE usuarios SET tentativas = ?, bloqueado_ate = ? WHERE id = ?", (tentativas, bloqueio, u["id"]))
        registrar_auditoria(con, u["nome"], "Falha de login", detalhe)
        con.commit()
        raise ErroAutenticacao(generica)
    con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL WHERE id = ?", (u["id"],))
    registrar_auditoria(con, u["nome"], "Login", f"Sessão iniciada como {PERFIS[u['perfil']]['nome']}.")
    con.commit()
    return Sessao(u["id"], u["login"], u["nome"], u["perfil"])


# ---------------------------------------------------------------------- backup
def sha256_arquivo(caminho: Path) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(1024 * 1024), b""):
            h.update(bloco)
    return h.hexdigest()


def criar_backup(con: sqlite3.Connection, pasta: Path, manter: int = 30) -> Path:
    """Copia consistente do banco (API de backup do SQLite) + arquivo de hash."""
    pasta = Path(pasta)
    pasta.mkdir(parents=True, exist_ok=True)
    base = f"camc_{datetime.now():%Y%m%d_%H%M%S}"
    destino = pasta / f"{base}.db"
    i = 2
    while destino.exists():
        destino = pasta / f"{base}_{i}.db"
        i += 1
    copia = sqlite3.connect(str(destino))
    try:
        con.backup(copia)
    finally:
        copia.close()
    (pasta / f"{destino.name}.sha256").write_text(f"{sha256_arquivo(destino)}  {destino.name}\n", encoding="utf-8")
    aplicar_retencao(pasta, manter)
    return destino


def aplicar_retencao(pasta: Path, manter: int) -> list[str]:
    """Mantém apenas os N backups mais recentes."""
    arquivos = sorted(Path(pasta).glob("camc_*.db"))
    removidos = []
    for antigo in arquivos[:-manter] if manter > 0 else []:
        antigo.unlink(missing_ok=True)
        Path(str(antigo) + ".sha256").unlink(missing_ok=True)
        removidos.append(antigo.name)
    return removidos


def listar_backups(pasta: Path) -> list[dict]:
    itens = []
    for p in sorted(Path(pasta).glob("camc_*.db"), reverse=True):
        st = p.stat()
        itens.append({"arquivo": p.name, "caminho": p, "tamanho": st.st_size,
                      "criado_em": datetime.fromtimestamp(st.st_mtime).replace(microsecond=0).isoformat(sep=" ")})
    return itens


def testar_backup(caminho: Path) -> dict:
    """Teste de restauração: confere o hash, abre uma cópia temporária, roda a
    verificação de integridade do SQLite e recalcula a cadeia de auditoria."""
    caminho = Path(caminho)
    rel = {"arquivo": caminho.name, "hash_confere": False, "integridade_sqlite": False,
           "cadeia_integra": False, "registros_auditoria": 0, "clientes": 0, "tickets": 0, "erro": ""}
    try:
        selo = Path(str(caminho) + ".sha256")
        if selo.exists():
            esperado = selo.read_text(encoding="utf-8").split()[0]
            rel["hash_confere"] = esperado == sha256_arquivo(caminho)
        with tempfile.TemporaryDirectory() as tmp:
            copia = Path(tmp) / "restaurado.db"
            shutil.copy2(caminho, copia)
            con = sqlite3.connect(str(copia))
            con.row_factory = sqlite3.Row
            try:
                rel["integridade_sqlite"] = con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                ok, _, total = verificar_cadeia(con)
                rel["cadeia_integra"], rel["registros_auditoria"] = ok, total
                rel["clientes"] = con.execute("SELECT COUNT(*) FROM clientes").fetchone()[0]
                rel["tickets"] = con.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
            finally:
                con.close()
    except Exception as exc:  # backup corrompido ou ilegível
        rel["erro"] = str(exc)
    rel["aprovado"] = rel["hash_confere"] and rel["integridade_sqlite"] and rel["cadeia_integra"] and not rel["erro"]
    return rel
