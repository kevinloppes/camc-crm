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
import os
import secrets
import shutil
import sqlite3
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from . import banco

ITERACOES = 200_000
MAX_TENTATIVAS = 5
MAX_TENTATIVAS_GLOBAIS = 25
BLOQUEIO_MINUTOS = 5
SESSAO_HORAS = 8
ZERO = "0" * 64
ERRO_LOGIN_GENERICO = "Login ou senha incorretos."
HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefixo}"
_SALT_DUMMY = "00112233445566778899aabbccddeeff"

# Hashes SHA-1 (maiúsculo) de senhas vazadas/padrão bloqueadas mesmo em operação offline
SENHAS_VAZADAS_LOCAIS_SHA1 = frozenset({
    hashlib.sha1(s.encode("utf-8")).hexdigest().upper()
    for s in (
        "camc-demo-2026",
        "password1234",
        "password12345",
        "Password1234!",
        "123456789012",
        "qwerty123456",
        "admin1234567",
        "Admin@123456",
        "letmein12345",
        "welcome12345",
        "abc123456789",
        "senha1234567",
        "Senha@123456",
        "mudar1234567",
    )
})


class ErroAutenticacao(Exception):
    """Login ou senha inválidos, conta bloqueada ou desativada."""


class PermissaoNegada(Exception):
    """O perfil do usuário não tem permissão para a ação."""


class SessaoInvalida(PermissaoNegada, ErroAutenticacao):
    """Sessão expirada, inexistente ou revogada no servidor."""


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
            "auditoria.ver", "auditoria.verificar", "auditoria.simular", "feedback.simular",
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
    token: str = field(default="", repr=False)
    refresh_token: str = field(default="", repr=False)
    token_versao: int = 1

    @property
    def perfil_nome(self) -> str:
        return PERFIS[self.perfil]["nome"]

    @property
    def rotulo(self) -> str:
        return f"{self.nome} ({self.perfil_nome})"

    def pode(self, permissao: str) -> bool:
        return tem_permissao(self.perfil, permissao)


# --------------------------------------------------------------------- sessões
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _criar_sessao_db(con: sqlite3.Connection, usuario_id: int, login: str, nome: str,
                     perfil: str, token_versao: int) -> Sessao:
    token = secrets.token_urlsafe(32)
    refresh = secrets.token_urlsafe(32)
    criada = datetime.now().replace(microsecond=0)
    expira = criada + timedelta(hours=SESSAO_HORAS)
    con.execute(
        "INSERT INTO sessoes (usuario_id, token_hash, refresh_hash, criada_em, expira_em) VALUES (?, ?, ?, ?, ?)",
        (usuario_id, hash_token(token), hash_token(refresh), criada.isoformat(sep=" "), expira.isoformat(sep=" ")),
    )
    return Sessao(usuario_id, login, nome, perfil, token=token, refresh_token=refresh, token_versao=token_versao)


def obter_perfil_sessao_ativa(con: sqlite3.Connection, sessao: Sessao | None) -> str | None:
    """Valida a sessão no banco e retorna o perfil autoritativo do usuário (ou None se inválida/revogada)."""
    if sessao is None or not sessao.token:
        return None
    r = con.execute(
        "SELECT u.perfil, u.ativo, u.token_versao, s.expira_em, s.revogada_em "
        "FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.token_hash = ? AND s.usuario_id = ?",
        (hash_token(sessao.token), sessao.usuario_id),
    ).fetchone()
    if r is None or r["revogada_em"] is not None or not r["ativo"]:
        return None
    if r["token_versao"] != sessao.token_versao:
        return None
    if datetime.fromisoformat(r["expira_em"]) <= datetime.now():
        return None
    return r["perfil"]


def sessao_valida(con: sqlite3.Connection, sessao: Sessao | None) -> bool:
    return obter_perfil_sessao_ativa(con, sessao) is not None


def revogar_sessao(con: sqlite3.Connection, sessao: Sessao | None) -> bool:
    """Invalida uma sessão específica (logout)."""
    if sessao is None or not sessao.token:
        return False
    cur = con.execute(
        "UPDATE sessoes SET revogada_em = ? WHERE token_hash = ? AND revogada_em IS NULL",
        (banco.agora(), hash_token(sessao.token)),
    )
    con.commit()
    return cur.rowcount > 0


def revogar_todas_sessoes_usuario(con: sqlite3.Connection, usuario_id: int) -> int:
    """Invalida imediatamente todos os tokens e refresh tokens ativos do usuário.
    Quem chama é responsável pelo commit (para executar atomicamente na mesma transação)."""
    con.execute("UPDATE usuarios SET token_versao = token_versao + 1 WHERE id = ?", (usuario_id,))
    cur = con.execute(
        "UPDATE sessoes SET revogada_em = ? WHERE usuario_id = ? AND revogada_em IS NULL",
        (banco.agora(), usuario_id),
    )
    return cur.rowcount


def renovar_sessao(con: sqlite3.Connection, refresh_token: str) -> Sessao:
    """Rotaciona o par de tokens usando um refresh token válido e não revogado."""
    if not refresh_token:
        raise SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
    r = con.execute(
        "SELECT s.id AS sessao_id, s.expira_em, s.revogada_em, u.id, u.login, u.nome, u.perfil, u.ativo, u.token_versao "
        "FROM sessoes s JOIN usuarios u ON u.id = s.usuario_id "
        "WHERE s.refresh_hash = ?",
        (hash_token(refresh_token),),
    ).fetchone()
    if r is None or r["revogada_em"] is not None or not r["ativo"]:
        raise SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
    if datetime.fromisoformat(r["expira_em"]) <= datetime.now():
        raise SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
    with con:
        con.execute("UPDATE sessoes SET revogada_em = ? WHERE id = ?", (banco.agora(), r["sessao_id"]))
        nova = _criar_sessao_db(con, r["id"], r["login"], r["nome"], r["perfil"], r["token_versao"])
    return nova


# ---------------------------------------------------------------------- senhas
def hash_senha(senha: str, sal: str | None = None, iteracoes: int = ITERACOES):
    sal = sal or secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), bytes.fromhex(sal), iteracoes)
    return h.hex(), sal, iteracoes


def verificar_senha(senha: str, hash_hex: str, sal: str, iteracoes: int) -> bool:
    calculado, _, _ = hash_senha(senha, sal, iteracoes)
    return hmac.compare_digest(calculado, hash_hex)


def verificar_senha_vazada(senha: str, timeout: float = 3.0, modo: str | None = None) -> bool:
    """Verifica se a senha consta em vazamentos conhecidos via lista local e API HIBP (k-anonymity).

    Apenas os 5 primeiros caracteres hexadecimais do hash SHA-1 são enviados à API Pwned Passwords
    com cabeçalho Add-Padding: true.
    Modos via CAMC_HIBP_MODO: 'best_effort' (padrão), 'estrito' (falha fechado se offline) ou 'offline'.
    """
    sha1_hex = hashlib.sha1(senha.encode("utf-8")).hexdigest().upper()
    if sha1_hex in SENHAS_VAZADAS_LOCAIS_SHA1:
        return True
    modo_efetivo = (modo or os.environ.get("CAMC_HIBP_MODO", "best_effort")).strip().lower()
    if modo_efetivo == "offline":
        return False
    prefixo, sufixo = sha1_hex[:5], sha1_hex[5:]
    req = urllib.request.Request(
        HIBP_RANGE_URL.format(prefixo=prefixo),
        headers={"User-Agent": "CAMC-CRM-AppSec/1.0", "Add-Padding": "true"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = resp.read().decode("utf-8", errors="ignore")
    except (urllib.error.URLError, TimeoutError, OSError):
        if modo_efetivo == "estrito":
            raise RuntimeError("Não foi possível verificar a senha contra bases de senhas vazadas.")
        return False
    for linha in corpo.splitlines():
        partes = linha.strip().split(":")
        if len(partes) != 2:
            continue
        cand_sufixo, contagem = partes[0].upper(), partes[1].strip()
        if hmac.compare_digest(cand_sufixo, sufixo):
            try:
                return int(contagem) > 0
            except ValueError:
                return True
    return False


def validar_forca_senha(senha: str, login: str = "", verificar_vazamento: bool = True) -> str | None:
    """Retorna a mensagem de erro ou None se a senha atender à política e não estiver vazada."""
    if len(senha) < 12:
        return "A senha deve ter pelo menos 12 caracteres."
    if len(senha) > 128:
        return "A senha deve ter no máximo 128 caracteres."
    if not any(c.isalpha() for c in senha) or not any(c.isdigit() for c in senha):
        return "A senha deve combinar letras e números."
    classes = sum([
        any(c.isupper() for c in senha),
        any(c.islower() for c in senha),
        any(c.isdigit() for c in senha),
        any(not c.isalnum() for c in senha),
    ])
    if classes < 3:
        return "A senha deve combinar ao menos 3 tipos: maiúsculas, minúsculas, números e símbolos."
    if len(set(senha)) < 5:
        return "A senha possui pouca variedade de caracteres."
    if login and login.strip().lower() in senha.lower():
        return "A senha não pode conter o próprio login."
    if verificar_vazamento:
        try:
            if verificar_senha_vazada(senha):
                return "Esta senha consta em bases de senhas vazadas. Escolha outra senha."
        except RuntimeError as exc:
            return str(exc)
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
def _iteracoes_referencia(con: sqlite3.Connection) -> int:
    r = con.execute("SELECT MAX(iteracoes) FROM usuarios").fetchone()
    return int(r[0]) if (r and r[0]) else ITERACOES


def _consumir_tempo_pbkdf2(senha: str, iteracoes: int) -> None:
    """Equaliza o tempo de resposta em falhas para evitar enumeração por temporização."""
    hash_senha(senha or "", _SALT_DUMMY, iteracoes=iteracoes)


def _esta_limitado(con: sqlite3.Connection, chave: str, agora: datetime) -> bool:
    r = con.execute("SELECT bloqueado_ate FROM login_rate_limit WHERE chave = ?", (chave,)).fetchone()
    return bool(r and r["bloqueado_ate"] and datetime.fromisoformat(r["bloqueado_ate"]) > agora)


def _registrar_falha_rate_limit(con: sqlite3.Connection, chave: str, agora: datetime, limite: int) -> bool:
    r = con.execute("SELECT tentativas, janela_inicio FROM login_rate_limit WHERE chave = ?", (chave,)).fetchone()
    agora_iso = agora.replace(microsecond=0).isoformat(sep=" ")
    if r is None or (agora - datetime.fromisoformat(r["janela_inicio"])) > timedelta(minutes=BLOQUEIO_MINUTOS):
        tentativas = 1
        janela_inicio = agora_iso
    else:
        tentativas = r["tentativas"] + 1
        janela_inicio = r["janela_inicio"]
    bloqueio = None
    bloqueou = False
    if tentativas >= limite:
        bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).replace(microsecond=0).isoformat(sep=" ")
        tentativas = 0
        janela_inicio = agora_iso
        bloqueou = True
    con.execute(
        "INSERT INTO login_rate_limit (chave, tentativas, janela_inicio, bloqueado_ate) VALUES (?, ?, ?, ?) "
        "ON CONFLICT(chave) DO UPDATE SET tentativas = excluded.tentativas, "
        "janela_inicio = excluded.janela_inicio, bloqueado_ate = excluded.bloqueado_ate",
        (chave, tentativas, janela_inicio, bloqueio),
    )
    return bloqueou


def limpar_rate_limit_login(con: sqlite3.Connection, login: str) -> None:
    con.execute("DELETE FROM login_rate_limit WHERE chave = ?", (f"login:{(login or '').strip().lower()}",))


def autenticar(con: sqlite3.Connection, login: str, senha: str) -> Sessao:
    login_norm = (login or "").strip().lower()
    chave_login = f"login:{login_norm}"
    agora = datetime.now()
    it_ref = _iteracoes_referencia(con)
    if _esta_limitado(con, "global", agora) or _esta_limitado(con, chave_login, agora):
        _consumir_tempo_pbkdf2(senha, it_ref)
        registrar_auditoria(con, "Anônimo", "Falha de login", "Tentativa bloqueada por limite de taxa.")
        con.commit()
        raise ErroAutenticacao(ERRO_LOGIN_GENERICO)
    u = con.execute("SELECT * FROM usuarios WHERE login = ?", (login_norm,)).fetchone()
    if u is None:
        _consumir_tempo_pbkdf2(senha, it_ref)
        _registrar_falha_rate_limit(con, chave_login, agora, MAX_TENTATIVAS)
        _registrar_falha_rate_limit(con, "global", agora, MAX_TENTATIVAS_GLOBAIS)
        registrar_auditoria(con, "Anônimo", "Falha de login", "Tentativa com credenciais inválidas.")
        con.commit()
        raise ErroAutenticacao(ERRO_LOGIN_GENERICO)
    if u["bloqueado_ate"] and datetime.fromisoformat(u["bloqueado_ate"]) > agora:
        _consumir_tempo_pbkdf2(senha, u["iteracoes"])
        _registrar_falha_rate_limit(con, "global", agora, MAX_TENTATIVAS_GLOBAIS)
        registrar_auditoria(con, u["nome"], "Falha de login", "Tentativa em conta temporariamente bloqueada.")
        con.commit()
        raise ErroAutenticacao(ERRO_LOGIN_GENERICO)
    if not u["ativo"]:
        _consumir_tempo_pbkdf2(senha, u["iteracoes"])
        _registrar_falha_rate_limit(con, chave_login, agora, MAX_TENTATIVAS)
        _registrar_falha_rate_limit(con, "global", agora, MAX_TENTATIVAS_GLOBAIS)
        registrar_auditoria(con, u["nome"], "Falha de login", "Usuário desativado tentou entrar.")
        con.commit()
        raise ErroAutenticacao(ERRO_LOGIN_GENERICO)
    if not verificar_senha(senha, u["senha_hash"], u["salt"], u["iteracoes"]):
        tentativas = u["tentativas"] + 1
        bloqueio = None
        detalhe = f"Senha incorreta ({tentativas} de {MAX_TENTATIVAS})."
        if tentativas >= MAX_TENTATIVAS:
            bloqueio = (agora + timedelta(minutes=BLOQUEIO_MINUTOS)).replace(microsecond=0).isoformat(sep=" ")
            tentativas = 0
            detalhe = f"Conta bloqueada por {BLOQUEIO_MINUTOS} minutos após {MAX_TENTATIVAS} tentativas."
        con.execute("UPDATE usuarios SET tentativas = ?, bloqueado_ate = ? WHERE id = ?", (tentativas, bloqueio, u["id"]))
        _registrar_falha_rate_limit(con, chave_login, agora, MAX_TENTATIVAS)
        _registrar_falha_rate_limit(con, "global", agora, MAX_TENTATIVAS_GLOBAIS)
        registrar_auditoria(con, u["nome"], "Falha de login", detalhe)
        con.commit()
        raise ErroAutenticacao(ERRO_LOGIN_GENERICO)
    con.execute("UPDATE usuarios SET tentativas = 0, bloqueado_ate = NULL WHERE id = ?", (u["id"],))
    limpar_rate_limit_login(con, login_norm)
    sessao = _criar_sessao_db(con, u["id"], u["login"], u["nome"], u["perfil"], u["token_versao"])
    registrar_auditoria(con, u["nome"], "Login", f"Sessão iniciada como {PERFIS[u['perfil']]['nome']}.")
    con.commit()
    return sessao


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
    banco.restringir_permissoes(pasta, eh_diretorio=True)
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
    banco.restringir_permissoes(destino, eh_diretorio=False)
    selo = pasta / f"{destino.name}.sha256"
    selo.write_text(f"{sha256_arquivo(destino)}  {destino.name}\n", encoding="utf-8")
    banco.restringir_permissoes(selo, eh_diretorio=False)
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
            partes = selo.read_text(encoding="utf-8").split()
            esperado = partes[0] if partes else ""
            rel["hash_confere"] = bool(esperado) and hmac.compare_digest(esperado, sha256_arquivo(caminho))
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
    except Exception:  # backup corrompido ou ilegível (sem vazar detalhes internos/paths)
        rel["erro"] = "Arquivo de backup inválido, corrompido ou ilegível."
    rel["aprovado"] = rel["hash_confere"] and rel["integridade_sqlite"] and rel["cadeia_integra"] and not rel["erro"]
    return rel
