"""Regras de negócio da CAMC.

Passo 1 (projeto de software): clientes, histórico, tickets, canais e status.
Passo 2 (segurança): permissões por perfil e trilha de auditoria em toda ação.
Passo 4 (usabilidade): registro da avaliação do cliente, com ticket automático
para notas baixas.
Rastreabilidade: cadeia "da colmeia/planta à mesa" por lote, com balanço de massa.
"""
from __future__ import annotations

import os
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from . import banco, seguranca
from .seguranca import PermissaoNegada, Sessao

CANAIS = ["WhatsApp", "E-mail", "Telefone", "Aplicativo", "Instagram"]
CATEGORIAS = ["Reclamação", "Sugestão", "Dúvida", "Pedido", "Rastreio", "Qualidade"]
PRIORIDADES = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
PRAZO_HORAS = {"alta": 24, "media": 48, "baixa": 72}
STATUS = {
    "novo": "Novo",
    "analise": "Em análise",
    "aguardando_cliente": "Aguardando cliente",
    "aguardando_transportadora": "Aguardando transportadora",
    "resolucao": "Em resolução",
    "resolvido": "Resolvido",
    "encerrado": "Encerrado",
}
TRANSICOES = {
    "novo": ["analise"],
    "analise": ["aguardando_cliente", "aguardando_transportadora", "resolucao", "resolvido"],
    "aguardando_cliente": ["analise", "resolucao", "resolvido"],
    "aguardando_transportadora": ["analise", "resolucao", "resolvido"],
    "resolucao": ["aguardando_cliente", "resolvido"],
    "resolvido": ["encerrado"],
    "encerrado": [],
}
SEGMENTOS = ["Consumidor de mel", "Consumidor da barra", "Comprador de chia a granel", "Revendedor"]
ETIQUETAS = ["Sabor", "Textura", "Doçura", "Embalagem", "Entrega"]
RESPONSAVEIS = ["Ana", "Carlos", "Bia"]
TIPOS_ETAPA = {"chia": "Campo (chia)", "mel": "Apiário (mel)", "fabrica": "Indústria"}
TOLERANCIA_PERDA_PCT = 5.0
ESTADOS_PEDIDO = {"separacao": "Em separação", "postado": "Postado", "em_rota": "Em rota", "entregue": "Entregue"}


class ErroValidacao(Exception):
    """Dado inválido ou regra de negócio violada (mensagem pronta para o usuário)."""


class ClienteDuplicado(ErroValidacao):
    def __init__(self, existente):
        super().__init__(f"Este cliente já existe: {existente['nome']}.")
        self.existente = existente


# ------------------------------------------------------------------ utilidades
def somente_digitos(texto) -> str:
    return re.sub(r"\D", "", texto or "")


def validar_cpf(texto) -> bool:
    d = somente_digitos(texto)
    if len(d) != 11 or d == d[0] * 11:
        return False
    for t in (9, 10):
        soma = sum(int(d[i]) * (t + 1 - i) for i in range(t))
        if (soma * 10) % 11 % 10 != int(d[t]):
            return False
    return True


def validar_cnpj(texto) -> bool:
    d = somente_digitos(texto)
    if len(d) != 14 or d == d[0] * 14:
        return False

    def digito(tamanho):
        pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] if tamanho == 12 else [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
        resto = sum(int(d[i]) * pesos[i] for i in range(tamanho)) % 11
        return 0 if resto < 2 else 11 - resto

    return digito(12) == int(d[12]) and digito(13) == int(d[13])


def validar_email(texto) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", texto or ""))


normalizar_email = banco.normalizar_email


def formatar_documento(texto) -> str:
    d = somente_digitos(texto)
    if len(d) == 11:
        return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"
    if len(d) == 14:
        return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"
    return texto or ""


def formatar_data(iso) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y")


def formatar_data_hora(iso) -> str:
    if not iso:
        return ""
    return datetime.fromisoformat(iso).strftime("%d/%m %H:%M")


def formatar_duracao(delta: timedelta) -> str:
    minutos = max(int(delta.total_seconds() // 60), 1)
    if minutos < 60:
        return f"{minutos} min"
    horas = minutos // 60
    if horas < 48:
        return f"{horas} h"
    return f"{horas // 24} dias"


def numero_br(valor: float, casas: int = 1) -> str:
    """Número no padrão brasileiro (vírgula decimal), sem zeros inúteis."""
    texto = f"{valor:.{casas}f}".rstrip("0").rstrip(".") if casas else f"{valor:.0f}"
    return texto.replace(".", ",")


def moeda(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def calcular_sla(ticket, agora: datetime | None = None):
    """Retorna (situação, texto). Situação: 'ok', 'alerta' (vence em < 4 h) ou 'atrasado'."""
    agora = agora or datetime.now()
    prazo = datetime.fromisoformat(ticket["criado_em"]) + timedelta(hours=PRAZO_HORAS[ticket["prioridade"]])
    if ticket["resolvido_em"]:
        no_prazo = datetime.fromisoformat(ticket["resolvido_em"]) <= prazo
        return ("ok", "Dentro do prazo") if no_prazo else ("atrasado", "Resolvido fora do prazo")
    restante = prazo - agora
    if restante.total_seconds() < 0:
        return "atrasado", "Vencido há " + formatar_duracao(-restante)
    return ("alerta" if restante < timedelta(hours=4) else "ok"), "Vence em " + formatar_duracao(restante)


# --------------------------------------------------------------------- serviço
class ServicoCRM:
    """Operações do sistema. Cada método confere a permissão do perfil e grava
    a ação na trilha de auditoria."""

    def __init__(self, con: sqlite3.Connection, sessao: Sessao | None = None):
        self.con = con
        self.sessao = sessao

    # ---- infraestrutura
    def _quem(self) -> str:
        return self.sessao.rotulo if self.sessao else "Sistema"

    def _autor(self) -> str:
        return self.sessao.nome if self.sessao else "Sistema"

    def _perfil_ativo(self) -> str | None:
        if self.sessao is None:
            return None
        return seguranca.obter_perfil_sessao_ativa(self.con, self.sessao)

    def _exigir_sessao(self) -> Sessao:
        if self._perfil_ativo() is None:
            raise seguranca.SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
        return self.sessao

    def pode(self, permissao: str) -> bool:
        perfil = self._perfil_ativo()
        return bool(perfil and seguranca.tem_permissao(perfil, permissao))

    def _exigir(self, permissao: str) -> None:
        perfil = self._perfil_ativo()
        if perfil is None:
            raise seguranca.SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
        if not seguranca.tem_permissao(perfil, permissao):
            raise PermissaoNegada("Seu perfil não tem permissão para esta ação.")

    def _exigir_alguma(self, *permissoes: str) -> None:
        perfil = self._perfil_ativo()
        if perfil is None:
            raise seguranca.SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
        if not any(seguranca.tem_permissao(perfil, p) for p in permissoes):
            raise PermissaoNegada("Seu perfil não tem permissão para esta ação.")

    def _auditar(self, acao: str, detalhe: str, quem: str | None = None) -> None:
        seguranca.registrar_auditoria(self.con, quem or self._quem(), acao, detalhe)

    # ---- clientes
    def listar_clientes(self, busca: str = "", segmento: str = ""):
        self._exigir("clientes.ver")
        busca = busca.strip().lower()
        digitos = somente_digitos(busca)
        saida = []
        for c in self.con.execute("SELECT * FROM clientes ORDER BY nome COLLATE NOCASE"):
            if segmento and c["segmento"] != segmento:
                continue
            if busca:
                texto = f"{c['nome']} {c['email']} {c['telefone']}".lower()
                if busca not in texto and not (digitos and digitos in somente_digitos(c["documento"] + c["telefone"])):
                    continue
            saida.append(c)
        return saida

    def _obter_cliente_interno(self, cliente_id: int):
        c = self.con.execute("SELECT * FROM clientes WHERE id = ?", (cliente_id,)).fetchone()
        if c is None:
            raise ErroValidacao("Cliente não encontrado.")
        return c

    def obter_cliente(self, cliente_id: int):
        self._exigir("clientes.ver")
        return self._obter_cliente_interno(cliente_id)

    def _normalizar_cliente(self, dados: dict, ignorar_id: int | None = None) -> dict:
        d = {k: (dados.get(k) or "").strip() for k in
             ("nome", "tipo", "documento", "telefone", "email", "cidade", "canal_preferido", "segmento")}
        if len(d["nome"]) < 3:
            raise ErroValidacao("Informe o nome do cliente (mínimo de 3 letras).")
        if d["tipo"] not in ("PF", "PJ"):
            raise ErroValidacao("Escolha o tipo de cliente: PF ou PJ.")
        d["documento"] = somente_digitos(d["documento"])
        if d["tipo"] == "PF" and not validar_cpf(d["documento"]):
            raise ErroValidacao("CPF inválido. Confira os números.")
        if d["tipo"] == "PJ" and not validar_cnpj(d["documento"]):
            raise ErroValidacao("CNPJ inválido. Confira os números.")
        if not d["telefone"] and not d["email"]:
            raise ErroValidacao("Informe ao menos um telefone ou e-mail.")
        email_norm = ""
        if d["email"]:
            if not validar_email(d["email"]):
                raise ErroValidacao("E-mail inválido.")
            email_norm = normalizar_email(d["email"])
            if not email_norm:
                raise ErroValidacao("E-mail inválido.")
        d["email_normalizado"] = email_norm
        if d["canal_preferido"] not in CANAIS:
            raise ErroValidacao("Escolha o canal preferido.")
        if d["segmento"] not in SEGMENTOS:
            raise ErroValidacao("Escolha o segmento do cliente.")
        for c in self.con.execute("SELECT * FROM clientes WHERE anonimizado = 0"):
            if c["id"] == ignorar_id:
                continue
            mesmo_tel = len(somente_digitos(d["telefone"])) >= 8 and somente_digitos(c["telefone"]) == somente_digitos(d["telefone"])
            c_email_norm = c["email_normalizado"] or normalizar_email(c["email"])
            mesmo_email = bool(email_norm) and c_email_norm == email_norm
            if c["documento"] == d["documento"] or mesmo_tel or mesmo_email:
                raise ClienteDuplicado(c)
        return d

    def criar_cliente(self, dados: dict, consentimento: bool) -> int:
        self._exigir("clientes.editar")
        if not consentimento:
            raise ErroValidacao("Registre o consentimento do cliente (LGPD) para concluir o cadastro.")
        d = self._normalizar_cliente(dados)
        try:
            with self.con:
                cur = self.con.execute(
                    "INSERT INTO clientes (nome, tipo, documento, telefone, email, email_normalizado, cidade,"
                    " canal_preferido, segmento, consentimento_em, criado_em) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    (d["nome"], d["tipo"], d["documento"], d["telefone"], d["email"], d["email_normalizado"], d["cidade"],
                     d["canal_preferido"], d["segmento"], banco.agora(), banco.agora()))
                self._auditar("Cliente cadastrado", f"{d['nome']} cadastrado com consentimento LGPD.")
        except sqlite3.IntegrityError:
            raise ErroValidacao("Não foi possível cadastrar o cliente: documento ou e-mail já utilizado.")
        return cur.lastrowid

    def editar_cliente(self, cliente_id: int, dados: dict) -> None:
        self._exigir("clientes.editar")
        atual = self._obter_cliente_interno(cliente_id)
        if atual["anonimizado"]:
            raise ErroValidacao("Cliente anonimizado não pode ser editado.")
        d = self._normalizar_cliente(dados, ignorar_id=cliente_id)
        try:
            with self.con:
                self.con.execute(
                    "UPDATE clientes SET nome=?, tipo=?, documento=?, telefone=?, email=?, email_normalizado=?,"
                    " cidade=?, canal_preferido=?, segmento=? WHERE id=?",
                    (d["nome"], d["tipo"], d["documento"], d["telefone"], d["email"], d["email_normalizado"],
                     d["cidade"], d["canal_preferido"], d["segmento"], cliente_id))
                self._auditar("Cliente editado", f"Cadastro de {d['nome']} atualizado.")
        except sqlite3.IntegrityError:
            raise ErroValidacao("Não foi possível atualizar o cliente: documento ou e-mail já utilizado.")

    def anonimizar_cliente(self, cliente_id: int) -> None:
        """Direito do titular (LGPD): remove os dados pessoais e mensagens privadas, mantendo histórico estatístico sem identificar a pessoa."""
        self._exigir("clientes.anonimizar")
        c = self._obter_cliente_interno(cliente_id)
        if c["anonimizado"]:
            raise ErroValidacao("Este cliente já foi anonimizado.")
        rotulo_anon = f"Cliente anonimizado #{cliente_id}"
        with self.con:
            self.con.execute(
                "UPDATE clientes SET nome=?, documento='', telefone='', email='', email_normalizado='',"
                " cidade='', consentimento_em=NULL, anonimizado=1 WHERE id=?",
                (rotulo_anon, cliente_id))
            self.con.execute("DELETE FROM anotacoes WHERE cliente_id = ?", (cliente_id,))
            self.con.execute("DELETE FROM interacoes WHERE cliente_id = ?", (cliente_id,))
            self.con.execute(
                "UPDATE ticket_eventos SET autor = ? WHERE tipo = 'cliente' AND ticket_id IN "
                "(SELECT id FROM tickets WHERE cliente_id = ?)",
                (rotulo_anon, cliente_id))
            self._auditar("Anonimização (LGPD)", f"Dados pessoais do cliente #{cliente_id} anonimizados.")

    def adicionar_anotacao(self, cliente_id: int, texto: str) -> None:
        self._exigir("clientes.anotar")
        if not texto.strip():
            raise ErroValidacao("Escreva a anotação antes de salvar.")
        c = self._obter_cliente_interno(cliente_id)
        if c["anonimizado"]:
            raise ErroValidacao("Cliente anonimizado não pode receber novas anotações.")
        with self.con:
            self.con.execute("INSERT INTO anotacoes (cliente_id, autor, texto, criado_em) VALUES (?,?,?,?)",
                             (cliente_id, self._autor(), texto.strip(), banco.agora()))
            self._auditar("Anotação interna", f"{c['nome']}: anotação adicionada.")

    def excluir_anotacao(self, anotacao_id: int) -> None:
        """Exclusão real (hard delete) de anotação interna."""
        self._exigir_alguma("clientes.editar", "clientes.anonimizar")
        a = self.con.execute("SELECT id, cliente_id FROM anotacoes WHERE id = ?", (anotacao_id,)).fetchone()
        if a is None:
            raise ErroValidacao("Anotação não encontrada.")
        with self.con:
            self.con.execute("DELETE FROM anotacoes WHERE id = ?", (anotacao_id,))
            self._auditar("Anotação excluída", f"Anotação #{anotacao_id} do cliente #{a['cliente_id']} excluída definitivamente.")

    def anotacoes(self, cliente_id: int):
        self._exigir("clientes.ver")
        return self.con.execute("SELECT * FROM anotacoes WHERE cliente_id = ? ORDER BY criado_em DESC", (cliente_id,)).fetchall()

    def registrar_interacao(self, cliente_id: int, canal: str, texto: str) -> None:
        """Registra uma ligação, mensagem ou e-mail no histórico do cliente."""
        self._exigir("clientes.editar")
        if canal not in CANAIS:
            raise ErroValidacao("Escolha o canal da interação.")
        if not texto.strip():
            raise ErroValidacao("Descreva a interação.")
        c = self._obter_cliente_interno(cliente_id)
        if c["anonimizado"]:
            raise ErroValidacao("Cliente anonimizado não pode receber novos contatos.")
        with self.con:
            self.con.execute("INSERT INTO interacoes (cliente_id, canal, texto, criado_em) VALUES (?,?,?,?)",
                             (cliente_id, canal, texto.strip(), banco.agora()))
            self._auditar("Interação registrada", f"{c['nome']}: contato por {canal}.")

    def linha_do_tempo(self, cliente_id: int) -> list[dict]:
        """Todas as interações do cliente (canais, compras, tickets, avaliações) em ordem cronológica inversa."""
        self._exigir("clientes.ver")
        eventos = []
        for i in self.con.execute("SELECT * FROM interacoes WHERE cliente_id = ?", (cliente_id,)):
            eventos.append({"quando": i["criado_em"], "origem": i["canal"], "texto": i["texto"]})
        for p in self.con.execute("SELECT * FROM pedidos WHERE cliente_id = ?", (cliente_id,)):
            eventos.append({"quando": p["criado_em"], "origem": "Pedido",
                            "texto": f"P-{p['id']}: {self._descricao_pedido(p['id'])} ({moeda(self._valor_pedido(p['id']))})"})
            if p["entregue_em"]:
                eventos.append({"quando": p["entregue_em"], "origem": "Entrega", "texto": f"P-{p['id']} entregue."})
        for t in self.con.execute("SELECT * FROM tickets WHERE cliente_id = ?", (cliente_id,)):
            eventos.append({"quando": t["criado_em"], "origem": "Ticket", "texto": f"{t['protocolo']} aberto via {t['canal']}: {t['assunto']}"})
            if t["resolvido_em"]:
                eventos.append({"quando": t["resolvido_em"], "origem": "Ticket", "texto": f"{t['protocolo']} resolvido."})
        for f in self.con.execute("SELECT * FROM feedbacks WHERE cliente_id = ?", (cliente_id,)):
            texto = f"Nota {f['nota']} para o pedido P-{f['pedido_id']}" + (f": {f['comentario']}" if f["comentario"] else "")
            eventos.append({"quando": f["criado_em"], "origem": "Avaliação", "texto": texto})
        return sorted(eventos, key=lambda e: e["quando"], reverse=True)

    # ---- pedidos
    def _descricao_pedido(self, pedido_id: int) -> str:
        itens = self.con.execute(
            "SELECT i.quantidade, p.nome FROM pedido_itens i JOIN produtos p ON p.id = i.produto_id WHERE i.pedido_id = ?",
            (pedido_id,)).fetchall()
        return ", ".join(f"{i['quantidade']}× {i['nome']}" for i in itens)

    def _valor_pedido(self, pedido_id: int) -> float:
        return self.con.execute("SELECT COALESCE(SUM(quantidade * preco_unitario), 0) FROM pedido_itens WHERE pedido_id = ?",
                                (pedido_id,)).fetchone()[0]

    def _lote_do_pedido(self, pedido_id: int) -> str | None:
        r = self.con.execute("SELECT lote FROM pedido_itens WHERE pedido_id = ? ORDER BY id LIMIT 1", (pedido_id,)).fetchone()
        return r["lote"] if r else None

    def descricao_pedido(self, pedido_id: int) -> str:
        self._exigir_alguma("clientes.ver", "rastreio.ver", "tickets.ver", "feedback.simular")
        return self._descricao_pedido(pedido_id)

    def valor_pedido(self, pedido_id: int) -> float:
        self._exigir_alguma("clientes.ver", "rastreio.ver", "tickets.ver", "feedback.simular")
        return self._valor_pedido(pedido_id)

    def lote_do_pedido(self, pedido_id: int) -> str | None:
        self._exigir_alguma("clientes.ver", "rastreio.ver", "tickets.ver", "feedback.simular")
        return self._lote_do_pedido(pedido_id)

    def pedidos_do_cliente(self, cliente_id: int) -> list[dict]:
        self._exigir("clientes.ver")
        saida = []
        for p in self.con.execute("SELECT * FROM pedidos WHERE cliente_id = ? ORDER BY criado_em DESC", (cliente_id,)):
            saida.append({"id": p["id"], "codigo": f"P-{p['id']}", "criado_em": p["criado_em"],
                          "itens": self._descricao_pedido(p["id"]), "valor": self._valor_pedido(p["id"]),
                          "lote": self._lote_do_pedido(p["id"]), "status": ESTADOS_PEDIDO[p["status"]]})
        return saida

    # ---- tickets
    def _pode_editar_ticket(self, ticket) -> bool:
        if self.pode("tickets.editar"):
            return True
        return self.pode("tickets.editar_rastreio") and ticket["categoria"] == "Rastreio"

    def pode_editar_ticket(self, ticket_id: int) -> bool:
        return self._pode_editar_ticket(self.obter_ticket(ticket_id))

    def _exigir_editar(self, ticket) -> None:
        if not self._pode_editar_ticket(ticket):
            raise PermissaoNegada("Seu perfil só pode consultar este ticket.")

    def obter_ticket(self, ticket_id: int):
        self._exigir("tickets.ver")
        t = self.con.execute(
            "SELECT t.*, c.nome AS cliente_nome FROM tickets t JOIN clientes c ON c.id = t.cliente_id WHERE t.id = ?",
            (ticket_id,)).fetchone()
        if t is None:
            raise ErroValidacao("Ticket não encontrado.")
        return t

    def eventos_ticket(self, ticket_id: int):
        self._exigir("tickets.ver")
        return self.con.execute("SELECT * FROM ticket_eventos WHERE ticket_id = ? ORDER BY id", (ticket_id,)).fetchall()

    def listar_tickets(self, busca: str = "", categoria: str = "", prioridade: str = "", status: str = "",
                       ocultar_encerrados: bool = False):
        self._exigir("tickets.ver")
        busca = busca.strip().lower()
        saida = []
        for t in self.con.execute(
                "SELECT t.*, c.nome AS cliente_nome FROM tickets t JOIN clientes c ON c.id = t.cliente_id ORDER BY t.criado_em DESC"):
            if categoria and t["categoria"] != categoria:
                continue
            if prioridade and t["prioridade"] != prioridade:
                continue
            if status and t["status"] != status:
                continue
            if ocultar_encerrados and t["status"] == "encerrado":
                continue
            if busca and busca not in f"{t['protocolo']} {t['assunto']} {t['cliente_nome']}".lower():
                continue
            saida.append(t)
        return saida

    def _criar_ticket_interno(self, cliente_id: int, canal: str, categoria: str, prioridade: str, assunto: str,
                              descricao: str = "", pedido_id: int | None = None, automatico: bool = False) -> int:
        if canal not in CANAIS or categoria not in CATEGORIAS or prioridade not in PRIORIDADES:
            raise ErroValidacao("Canal, categoria ou prioridade inválidos.")
        if not assunto.strip():
            raise ErroValidacao("Informe o assunto do ticket.")
        cliente = self._obter_cliente_interno(cliente_id)
        lote = None
        if pedido_id:
            p = self.con.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
            if p is None or p["cliente_id"] != cliente_id:
                raise ErroValidacao("O pedido escolhido não pertence a este cliente.")
            lote = self._lote_do_pedido(pedido_id)
        if categoria == "Qualidade" and not pedido_id:
            raise ErroValidacao("Tickets de qualidade precisam de um pedido, para ligar a reclamação ao lote.")
        agora = banco.agora()
        with self.con:
            novo_id = self.con.execute("SELECT COALESCE(MAX(id), 230) + 1 FROM tickets").fetchone()[0]
            protocolo = f"CAMC-{novo_id:04d}"
            self.con.execute(
                "INSERT INTO tickets (id, protocolo, cliente_id, canal, categoria, prioridade, status, assunto, pedido_id, lote, criado_em)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (novo_id, protocolo, cliente_id, canal, categoria, prioridade, "novo", assunto.strip(), pedido_id, lote, agora))
            origem = "Ticket aberto automaticamente pela avaliação do cliente." if automatico else f"Ticket aberto via {canal}."
            self._evento(novo_id, "sistema", "Sistema", origem)
            if descricao.strip():
                self._evento(novo_id, "cliente", cliente["nome"], descricao.strip())
            self._auditar("Ticket aberto", f"{protocolo} aberto" + (" automaticamente (nota baixa)." if automatico else f" via {canal}."),
                          "Sistema" if automatico else None)
        return novo_id

    def criar_ticket(self, cliente_id: int, canal: str, categoria: str, prioridade: str, assunto: str,
                     descricao: str = "", pedido_id: int | None = None, automatico: bool = False) -> int:
        self._exigir("tickets.criar")
        return self._criar_ticket_interno(cliente_id, canal, categoria, prioridade, assunto, descricao, pedido_id, automatico=False)

    def _evento(self, ticket_id: int, tipo: str, autor: str, texto: str) -> None:
        self.con.execute("INSERT INTO ticket_eventos (ticket_id, tipo, autor, texto, criado_em) VALUES (?,?,?,?,?)",
                         (ticket_id, tipo, autor, texto, banco.agora()))

    def proximos_status(self, ticket_id: int) -> list[str]:
        return TRANSICOES[self.obter_ticket(ticket_id)["status"]]

    def mudar_status(self, ticket_id: int, novo: str) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if novo not in TRANSICOES[t["status"]]:
            raise ErroValidacao(f"Não é possível ir de “{STATUS[t['status']]}” para “{STATUS.get(novo, novo)}”.")
        with self.con:
            if novo == "resolvido" and not t["resolvido_em"]:
                self.con.execute("UPDATE tickets SET status=?, resolvido_em=? WHERE id=?", (novo, banco.agora(), ticket_id))
            else:
                self.con.execute("UPDATE tickets SET status=? WHERE id=?", (novo, ticket_id))
            self._evento(ticket_id, "status", self._autor(), f"Status: {STATUS[t['status']]} → {STATUS[novo]}")
            self._auditar("Status alterado", f"{t['protocolo']}: {STATUS[t['status']]} → {STATUS[novo]}.")

    def reabrir_ticket(self, ticket_id: int) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if t["status"] not in ("resolvido", "encerrado"):
            raise ErroValidacao("Só é possível reabrir tickets resolvidos ou encerrados.")
        with self.con:
            self.con.execute("UPDATE tickets SET status='analise', resolvido_em=NULL WHERE id=?", (ticket_id,))
            self._evento(ticket_id, "status", self._autor(), f"Ticket reaberto. Status: {STATUS[t['status']]} → Em análise")
            self._auditar("Ticket reaberto", f"{t['protocolo']} reaberto.")

    def responder(self, ticket_id: int, texto: str) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if not texto.strip():
            raise ErroValidacao("Escreva a resposta antes de enviar.")
        with self.con:
            self._evento(ticket_id, "resposta", self._autor(), texto.strip())
            if not t["primeira_resposta_em"]:
                self.con.execute("UPDATE tickets SET primeira_resposta_em=? WHERE id=?", (banco.agora(), ticket_id))
            self._auditar("Resposta enviada", f"{t['protocolo']} respondido por {t['canal']}.")

    def nota_interna(self, ticket_id: int, texto: str) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if not texto.strip():
            raise ErroValidacao("Escreva a nota antes de salvar.")
        with self.con:
            self._evento(ticket_id, "nota", self._autor(), texto.strip())
            self._auditar("Nota interna", f"{t['protocolo']}: nota interna adicionada.")

    def atribuir(self, ticket_id: int, responsavel: str) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if responsavel and responsavel not in RESPONSAVEIS:
            raise ErroValidacao("Responsável inválido.")
        with self.con:
            self.con.execute("UPDATE tickets SET responsavel=? WHERE id=?", (responsavel, ticket_id))
            self._evento(ticket_id, "sistema", self._autor(), f"Responsável: {responsavel or 'ninguém'}.")
            self._auditar("Responsável alterado", f"{t['protocolo']} atribuído a {responsavel or 'ninguém'}.")

    def escalonar(self, ticket_id: int) -> None:
        t = self.obter_ticket(ticket_id)
        self._exigir_editar(t)
        if self._perfil_ativo() == "gestor":
            raise ErroValidacao("Tickets já estão sob responsabilidade do gestor.")
        if t["status"] in ("resolvido", "encerrado"):
            raise ErroValidacao("Não é possível escalonar tickets resolvidos ou encerrados.")
        if t["escalonado"]:
            raise ErroValidacao("Este ticket já foi escalonado.")
        with self.con:
            self.con.execute("UPDATE tickets SET escalonado=1 WHERE id=?", (ticket_id,))
            self._evento(ticket_id, "sistema", self._autor(), "Ticket escalonado ao gestor.")
            self._auditar("Ticket escalonado", f"{t['protocolo']} escalonado ao gestor.")

    # ---- rastreabilidade
    def listar_lotes(self, apenas_venda: bool = False):
        self._exigir("rastreio.ver")
        if apenas_venda:
            return self.con.execute("SELECT * FROM lotes WHERE venda = 1 ORDER BY codigo").fetchall()
        return self.con.execute("SELECT * FROM lotes ORDER BY codigo").fetchall()

    def _nos_do_lote(self, codigo: str, visitados: set) -> list[dict]:
        if codigo in visitados:
            return []
        visitados.add(codigo)
        nos = []
        for ins in self.con.execute("SELECT insumo FROM lote_insumos WHERE lote = ? ORDER BY insumo", (codigo,)):
            nos += self._nos_do_lote(ins["insumo"], visitados)
        for i, e in enumerate(self.con.execute("SELECT * FROM lote_etapas WHERE lote = ? ORDER BY ordem, id", (codigo,))):
            medidas, alerta = e["medidas"], ""
            if e["entrada_kg"] is not None and e["saida_kg"] is not None:
                entrada, saida = e["entrada_kg"], e["saida_kg"]
                perda = (entrada - saida) / entrada * 100 if entrada else 0.0
                medidas = (medidas + " · " if medidas else "") + (
                    f"entrada {numero_br(entrada)} kg, saída {numero_br(saida)} kg (perda {numero_br(perda)}%)")
                if saida > entrada:
                    alerta = "Saída maior que a entrada"
                elif perda > TOLERANCIA_PERDA_PCT:
                    alerta = f"Perda acima da tolerância de {numero_br(TOLERANCIA_PERDA_PCT)}%"
            nos.append({"tipo": e["tipo"], "titulo": e["titulo"], "subtitulo": e["subtitulo"],
                        "data": formatar_data(e["data"]), "medidas": medidas, "alerta": alerta,
                        "lote": codigo if i == 0 else "", "pendente": False})
        return nos

    def cadeia_do_lote(self, codigo: str) -> list[dict]:
        self._exigir("rastreio.ver")
        return self._nos_do_lote(codigo, set())

    def _nos_do_pedido_interno(self, pedido_id: int) -> list[dict]:
        p = self.con.execute("SELECT p.*, c.nome AS cliente_nome FROM pedidos p JOIN clientes c ON c.id = p.cliente_id WHERE p.id = ?",
                             (pedido_id,)).fetchone()
        if p is None:
            raise ErroValidacao("Pedido não encontrado.")
        f = self.con.execute("SELECT * FROM feedbacks WHERE pedido_id = ?", (pedido_id,)).fetchone()
        if p["entregue_em"]:
            data_entrega = formatar_data(p["entregue_em"])
        else:
            data_entrega = ("Postado em " + formatar_data(p["postado_em"])) if p["postado_em"] else "Em separação"
        return [
            {"tipo": "pedido", "titulo": "Pedido", "subtitulo": f"P-{p['id']} – {p['cliente_nome']}", "data": formatar_data(p["criado_em"]),
             "medidas": moeda(self._valor_pedido(pedido_id)), "alerta": "", "lote": "", "pendente": False},
            {"tipo": "entrega", "titulo": "Entrega", "subtitulo": p["transportadora"], "data": data_entrega,
             "medidas": f"Rastreio {p['rastreio']}" if p["rastreio"] else "", "alerta": "", "lote": "", "pendente": not p["entregue_em"]},
            {"tipo": "feedback", "titulo": "Avaliação", "subtitulo": f"Nota {f['nota']} de 5" if f else "Aguardando",
             "data": formatar_data(f["criado_em"]) if f else "", "medidas": f["comentario"] if f else "",
             "alerta": "", "lote": "", "pendente": f is None},
        ]

    def nos_do_pedido(self, pedido_id: int) -> list[dict]:
        self._exigir("rastreio.ver")
        return self._nos_do_pedido_interno(pedido_id)

    def cadeia_do_pedido(self, pedido_id: int) -> list[dict]:
        self._exigir("rastreio.ver")
        lote = self._lote_do_pedido(pedido_id)
        return (self._nos_do_lote(lote, set()) if lote else []) + self._nos_do_pedido_interno(pedido_id)

    def resumo_lote(self, codigo: str) -> dict:
        self._exigir("rastreio.ver")
        pedidos = self.con.execute("SELECT COUNT(DISTINCT pedido_id) FROM pedido_itens WHERE lote = ?", (codigo,)).fetchone()[0]
        fb = self.con.execute("SELECT COUNT(*), AVG(nota) FROM feedbacks WHERE lote = ?", (codigo,)).fetchone()
        tickets = self.con.execute("SELECT COUNT(*) FROM tickets WHERE lote = ?", (codigo,)).fetchone()[0]
        return {"pedidos": pedidos, "avaliacoes": fb[0], "media": fb[1], "tickets": tickets}

    def registrar_etapa(self, lote: str, tipo: str, titulo: str, subtitulo: str, responsavel: str,
                        entrada_kg, saida_kg, medidas: str, data: str | None = None) -> str:
        """Registra uma etapa no lote e aplica o balanço de massa. Retorna o alerta ('' se tudo certo)."""
        self._exigir("lotes.registrar")
        if self.con.execute("SELECT 1 FROM lotes WHERE codigo = ?", (lote,)).fetchone() is None:
            raise ErroValidacao("Lote não encontrado.")
        if tipo not in TIPOS_ETAPA:
            raise ErroValidacao("Escolha o tipo da etapa.")
        if not titulo.strip():
            raise ErroValidacao("Informe o título da etapa.")
        for nome, v in (("entrada", entrada_kg), ("saída", saida_kg)):
            if v is not None and v < 0:
                raise ErroValidacao(f"A quantidade de {nome} não pode ser negativa.")
        if (entrada_kg is None) != (saida_kg is None):
            raise ErroValidacao("Informe entrada e saída juntas para o balanço de massa.")
        data = data or datetime.now().strftime("%Y-%m-%d")
        try:
            datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            raise ErroValidacao("Data inválida. Use o formato AAAA-MM-DD.")
        alerta = ""
        if entrada_kg is not None:
            if saida_kg > entrada_kg:
                alerta = "Saída maior que a entrada"
            elif entrada_kg > 0 and (entrada_kg - saida_kg) / entrada_kg * 100 > TOLERANCIA_PERDA_PCT:
                alerta = f"Perda acima da tolerância de {TOLERANCIA_PERDA_PCT:g}%"
        with self.con:
            ordem = self.con.execute("SELECT COALESCE(MAX(ordem), 0) + 1 FROM lote_etapas WHERE lote = ?", (lote,)).fetchone()[0]
            self.con.execute(
                "INSERT INTO lote_etapas (lote, ordem, tipo, titulo, subtitulo, data, responsavel, medidas, entrada_kg, saida_kg)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (lote, ordem, tipo, titulo.strip(), subtitulo.strip(), data, responsavel.strip(), medidas.strip(), entrada_kg, saida_kg))
            self._auditar("Etapa de lote registrada", f"{lote}: {titulo.strip()}" + (f" – ALERTA: {alerta}." if alerta else "."))
        return alerta

    # ---- avaliação do cliente (app)
    def pedidos_aguardando_avaliacao(self):
        self._exigir("feedback.simular")
        return self.con.execute(
            "SELECT p.*, c.nome AS cliente_nome FROM pedidos p JOIN clientes c ON c.id = p.cliente_id "
            "WHERE p.status = 'entregue' AND NOT EXISTS (SELECT 1 FROM feedbacks f WHERE f.pedido_id = p.id) ORDER BY p.entregue_em").fetchall()

    def pedidos_em_rota(self):
        self._exigir("feedback.simular")
        return self.con.execute("SELECT * FROM pedidos WHERE status = 'em_rota' ORDER BY id").fetchall()

    def simular_entrega(self) -> int | None:
        """Demonstração: confirma a entrega do próximo pedido em rota."""
        self._exigir("feedback.simular")
        p = self.con.execute("SELECT * FROM pedidos WHERE status = 'em_rota' ORDER BY id LIMIT 1").fetchone()
        if p is None:
            return None
        with self.con:
            self.con.execute("UPDATE pedidos SET status='entregue', entregue_em=? WHERE id=?", (banco.agora(), p["id"]))
            self._auditar("Entrega confirmada", f"P-{p['id']} entregue ({p['transportadora']}) – simulação.")
        return p["id"]

    def registrar_feedback(self, pedido_id: int, nota: int, etiquetas=(), comentario: str = "",
                           cliques: int | None = None, segundos: int | None = None,
                           cliente_id: int | None = None):
        """Grava a avaliação (uma por pedido entregue). Notas 1 e 2 abrem um ticket de qualidade.
        Retorna (id_da_avaliação, id_do_ticket_ou_None)."""
        self._exigir("feedback.simular")
        if isinstance(nota, bool) or not isinstance(nota, int) or not 1 <= nota <= 5:
            raise ErroValidacao("A nota deve ser de 1 a 5.")
        p = self.con.execute("SELECT * FROM pedidos WHERE id = ?", (pedido_id,)).fetchone()
        if p is None or p["status"] != "entregue":
            raise ErroValidacao("Só é possível avaliar pedidos já entregues.")
        if cliente_id is not None and p["cliente_id"] != cliente_id:
            raise PermissaoNegada("O pedido informado não pertence a este cliente.")
        if self.con.execute("SELECT 1 FROM feedbacks WHERE pedido_id = ?", (pedido_id,)).fetchone():
            raise ErroValidacao("Este pedido já foi avaliado.")
        etiquetas = [e for e in etiquetas if e in ETIQUETAS]
        lote = self._lote_do_pedido(pedido_id)
        ticket_id = None
        with self.con:
            cur = self.con.execute(
                "INSERT INTO feedbacks (pedido_id, cliente_id, lote, nota, etiquetas, comentario, criado_em, cliques, segundos)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (pedido_id, p["cliente_id"], lote, nota, ",".join(etiquetas), comentario.strip(), banco.agora(), cliques, segundos))
            seguranca.registrar_auditoria(self.con, "Cliente (aplicativo)", "Avaliação registrada",
                                          f"P-{pedido_id}, nota {nota}, lote {lote}.")
            if nota <= 2:
                item = self.con.execute("SELECT pr.nome FROM pedido_itens i JOIN produtos pr ON pr.id = i.produto_id "
                                        "WHERE i.pedido_id = ? ORDER BY i.id LIMIT 1", (pedido_id,)).fetchone()
                produto = item["nome"] if item else f"Pedido P-{pedido_id}"
                ticket_id = self._criar_ticket_interno(
                    p["cliente_id"], "Aplicativo", "Qualidade", "alta", f"Avaliação {nota}: {produto}",
                    comentario.strip() or "Avaliação baixa sem comentário.", pedido_id, automatico=True)
        return cur.lastrowid, ticket_id

    def solicitar_contato(self, ticket_id: int, cliente_id: int | None = None) -> None:
        """O cliente pediu retorno pelo aplicativo (botão “Falar com a gente”)."""
        self._exigir("feedback.simular")
        t = self.con.execute("SELECT t.*, c.nome AS cliente_nome FROM tickets t JOIN clientes c ON c.id = t.cliente_id WHERE t.id = ?",
                             (ticket_id,)).fetchone()
        if t is None:
            raise ErroValidacao("Ticket não encontrado.")
        if t["canal"] != "Aplicativo" or t["pedido_id"] is None:
            raise PermissaoNegada("Solicitação de contato pelo aplicativo permitida apenas para tickets de avaliação.")
        if cliente_id is not None and t["cliente_id"] != cliente_id:
            raise PermissaoNegada("O ticket informado não pertence a este cliente.")
        with self.con:
            self._evento(ticket_id, "cliente", t["cliente_nome"], "Pediu contato imediato pelo aplicativo.")
            seguranca.registrar_auditoria(self.con, "Cliente (aplicativo)", "Pedido de contato", f"{t['protocolo']}: cliente pediu contato.")

    def contexto_pedido(self, pedido_id: int) -> dict:
        """Dados básicos do pedido para a tela de avaliação do aplicativo."""
        self._exigir("feedback.simular")
        p = self.con.execute("SELECT p.*, c.nome AS cliente FROM pedidos p JOIN clientes c ON c.id = p.cliente_id WHERE p.id = ?",
                             (pedido_id,)).fetchone()
        if p is None:
            raise ErroValidacao("Pedido não encontrado.")
        item = self.con.execute("SELECT pr.nome, pr.curto, i.lote FROM pedido_itens i JOIN produtos pr ON pr.id = i.produto_id "
                                "WHERE i.pedido_id = ? ORDER BY i.id LIMIT 1", (pedido_id,)).fetchone()
        if item is None:
            raise ErroValidacao("Pedido sem itens cadastrados.")
        return {"id": pedido_id, "cliente_id": p["cliente_id"], "codigo": f"P-{pedido_id}", "cliente": p["cliente"],
                "primeiro_nome": p["cliente"].split()[0], "produto": item["nome"], "curto": item["curto"], "lote": item["lote"]}

    # ---- indicadores
    def indicadores(self) -> dict:
        self._exigir("painel.ver")
        tickets = self.con.execute("SELECT * FROM tickets").fetchall()
        abertos = [t for t in tickets if t["status"] not in ("resolvido", "encerrado")]
        atrasados = [t for t in abertos if calcular_sla(t)[0] == "atrasado"]

        def media(valores):
            return sum(valores, timedelta()) / len(valores) if valores else None

        primeira = media([datetime.fromisoformat(t["primeira_resposta_em"]) - datetime.fromisoformat(t["criado_em"])
                          for t in tickets if t["primeira_resposta_em"]])
        resolucao = media([datetime.fromisoformat(t["resolvido_em"]) - datetime.fromisoformat(t["criado_em"])
                           for t in tickets if t["resolvido_em"]])
        notas = [f["nota"] for f in self.con.execute("SELECT nota FROM feedbacks")]
        reclamacoes: dict[str, int] = {}
        for t in tickets:
            if t["lote"] and t["categoria"] in ("Reclamação", "Qualidade"):
                reclamacoes[t["lote"]] = reclamacoes.get(t["lote"], 0) + 1
        return {
            "abertos": len(abertos), "atrasados": len(atrasados),
            "primeira_resposta": primeira, "resolucao": resolucao,
            "satisfacao": sum(notas) / len(notas) if notas else None, "avaliacoes": len(notas),
            "por_canal": [(c, sum(1 for t in tickets if t["canal"] == c)) for c in CANAIS],
            "por_status": [(STATUS[s], sum(1 for t in tickets if t["status"] == s)) for s in STATUS],
            "notas": [(f"{n} estrelas" if n > 1 else "1 estrela", notas.count(n)) for n in (5, 4, 3, 2, 1)],
            "reclamacoes_por_lote": sorted(reclamacoes.items(), key=lambda kv: -kv[1]),
        }

    # ---- auditoria
    def listar_auditoria(self):
        self._exigir("auditoria.ver")
        return self.con.execute("SELECT * FROM auditoria ORDER BY n DESC").fetchall()

    def verificar_auditoria(self):
        self._exigir("auditoria.verificar")
        return seguranca.verificar_cadeia(self.con)

    def simular_adulteracao(self) -> int:
        self._exigir("auditoria.simular")
        n = seguranca.simular_adulteracao(self.con)
        return n

    def desfazer_adulteracao(self) -> bool:
        self._exigir("auditoria.simular")
        return seguranca.desfazer_adulteracao(self.con)

    # ---- administração (backup e usuários)
    def criar_backup(self):
        self._exigir("backup.executar")
        caminho = seguranca.criar_backup(self.con, banco.PASTA_BACKUPS)
        with self.con:
            self._auditar("Backup criado", f"{caminho.name} gerado com arquivo de hash SHA-256.")
        return caminho

    def listar_backups(self):
        self._exigir("backup.testar")
        return seguranca.listar_backups(banco.PASTA_BACKUPS)

    def testar_backup(self, caminho):
        self._exigir("backup.testar")
        base = Path(banco.PASTA_BACKUPS).resolve()
        alvo = Path(caminho).resolve()
        try:
            dentro = os.path.commonpath([str(base), str(alvo)]) == str(base)
        except ValueError:
            dentro = False
        if not dentro or alvo == base or alvo.suffix.lower() != ".db":
            raise ErroValidacao("Caminho de backup inválido.")
        rel = seguranca.testar_backup(alvo)
        with self.con:
            self._auditar("Teste de restauração", f"{rel['arquivo']}: {'aprovado' if rel['aprovado'] else 'REPROVADO'}.")
        return rel

    def listar_usuarios(self):
        self._exigir("usuarios.gerir")
        return self.con.execute("SELECT id, login, nome, perfil, ativo FROM usuarios ORDER BY id").fetchall()

    def alternar_usuario(self, usuario_id: int) -> bool:
        self._exigir("usuarios.gerir")
        u = self.con.execute("SELECT * FROM usuarios WHERE id = ?", (usuario_id,)).fetchone()
        if u is None:
            raise ErroValidacao("Usuário não encontrado.")
        if u["id"] == self.sessao.usuario_id:
            raise ErroValidacao("Você não pode desativar o próprio usuário.")
        novo = 0 if u["ativo"] else 1
        with self.con:
            self.con.execute("UPDATE usuarios SET ativo=?, tentativas=0, bloqueado_ate=NULL WHERE id=?", (novo, usuario_id))
            seguranca.limpar_rate_limit_login(self.con, u["login"])
            if novo == 0:
                seguranca.revogar_todas_sessoes_usuario(self.con, usuario_id)
            self._auditar("Usuário " + ("ativado" if novo else "desativado"), f"{u['nome']} ({u['login']}).")
        return bool(novo)

    def alterar_minha_senha(self, atual: str, nova: str) -> None:
        sessao = self._exigir_sessao()
        u = self.con.execute("SELECT * FROM usuarios WHERE id = ?", (sessao.usuario_id,)).fetchone()
        if u is None or not u["ativo"]:
            raise seguranca.SessaoInvalida("Sessão expirada ou revogada. Faça login novamente.")
        if not seguranca.verificar_senha(atual, u["senha_hash"], u["salt"], u["iteracoes"]):
            raise ErroValidacao("A senha atual está incorreta.")
        if atual == nova:
            raise ErroValidacao("A nova senha deve ser diferente da senha atual.")
        erro = seguranca.validar_forca_senha(nova, login=u["login"])
        if erro:
            raise ErroValidacao(erro)
        h, sal, it = seguranca.hash_senha(nova)
        with self.con:
            self.con.execute("UPDATE usuarios SET senha_hash=?, salt=?, iteracoes=? WHERE id=?", (h, sal, it, u["id"]))
            seguranca.revogar_todas_sessoes_usuario(self.con, u["id"])
            self._auditar("Senha alterada", "O usuário trocou a própria senha e todas as sessões ativas foram revogadas.")
