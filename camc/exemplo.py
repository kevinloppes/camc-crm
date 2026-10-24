"""Dados de exemplo (fictícios) para demonstrar o sistema na primeira execução."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta

from . import seguranca

SENHA_DEMO = "camc-demo-2026"

USUARIOS = [
    ("atendente", "Ana Souza", "atendente"),
    ("gestor", "Roberto Lima", "gestor"),
    ("logistica", "Bia Ramos", "logistica"),
    ("producao", "Carlos Pereira", "producao"),
    ("auditor", "Marcos Teixeira", "auditor"),
    ("admin", "Admin de TI", "admin_ti"),
]


def popular(con: sqlite3.Connection, iteracoes: int = seguranca.ITERACOES) -> None:
    agora = datetime.now().replace(microsecond=0)

    def atras(horas: float) -> str:
        return (agora - timedelta(hours=horas)).isoformat(sep=" ")

    def dia(dias_atras: int) -> str:
        return (agora - timedelta(days=dias_atras)).strftime("%Y-%m-%d")

    # usuários
    for login, nome, perfil in USUARIOS:
        h, sal, it = seguranca.hash_senha(SENHA_DEMO, iteracoes=iteracoes)
        con.execute("INSERT INTO usuarios (login, nome, perfil, senha_hash, salt, iteracoes) VALUES (?,?,?,?,?,?)",
                    (login, nome, perfil, h, sal, it))

    # produtos
    con.executemany("INSERT INTO produtos (id, nome, curto, preco) VALUES (?,?,?,?)", [
        (1, "Mel puro 500 g", "o mel", 38.00),
        (2, "Chia a granel 1 kg", "a chia", 29.90),
        (3, "Barra Mel & Chia (caixa com 12)", "a Barra Mel & Chia", 64.00),
    ])

    # clientes (dados fictícios)
    clientes = [
        (1, "Marina Alves", "PF", "52998224725", "(12) 99100-0001", "marina.alves@email.example", "Santa Branca", "WhatsApp", "Consumidor da barra", 60),
        (2, "Restaurante Raízes", "PJ", "11222333000181", "(12) 3100-0002", "compras@raizes.example", "Jacareí", "E-mail", "Comprador de chia a granel", 90),
        (3, "Paulo Nogueira", "PF", "11144477735", "(12) 99100-0003", "paulo.n@email.example", "Guararema", "Telefone", "Consumidor de mel", 120),
        (4, "Empório Boa Colheita", "PJ", "11444777000161", "(11) 4100-0004", "contato@boacolheita.example", "Mogi das Cruzes", "E-mail", "Revendedor", 200),
        (5, "Camila Duarte", "PF", "39053344705", "(12) 99100-0005", "camila.d@email.example", "São José dos Campos", "Aplicativo", "Consumidor da barra", 15),
        (6, "Helena Prado", "PF", "12345678909", "(12) 99100-0006", "helena.prado@email.example", "Santa Branca", "WhatsApp", "Consumidor de mel", 5),
    ]
    for c in clientes:
        quando = atras(24 * c[9])
        con.execute("INSERT INTO clientes (id, nome, tipo, documento, telefone, email, cidade, canal_preferido, segmento, consentimento_em, criado_em)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?,?)", (*c[:9], quando, quando))
    con.execute("INSERT INTO anotacoes (cliente_id, autor, texto, criado_em) VALUES (2, 'Ana Souza', ?, ?)",
                ("Compra chia todo mês; prefere nota fiscal por e-mail.", atras(24 * 20)))

    # lotes e etapas
    lotes = [
        ("LC-0826-T1", "Chia – talhão 1", "chia", 0), ("LM-0826-A1", "Mel – apiário 1", "mel", 1),
        ("LC-0926-T3", "Chia – talhão 3", "chia", 1), ("LM-0926-A1", "Mel puro – apiário 1", "mel", 1),
        ("LM-0926-A2", "Mel – apiário 2", "mel", 0), ("LB-0926-B", "Barra Mel & Chia", "barra", 1),
        ("LB-1026-A", "Barra Mel & Chia", "barra", 1),
    ]
    con.executemany("INSERT INTO lotes (codigo, nome, tipo, venda) VALUES (?,?,?,?)", lotes)
    con.executemany("INSERT INTO lote_insumos (lote, insumo) VALUES (?,?)", [
        ("LB-0926-B", "LC-0826-T1"), ("LB-0926-B", "LM-0826-A1"),
        ("LB-1026-A", "LC-0926-T3"), ("LB-1026-A", "LM-0926-A2"),
    ])
    etapas = [  # lote, ordem, tipo, titulo, subtitulo, data, responsavel, medidas, entrada, saida
        ("LC-0826-T1", 1, "chia", "Plantio e manejo", "Talhão 1", dia(190), "Campo", "Umidade do solo 22%", None, None),
        ("LC-0826-T1", 2, "chia", "Colheita da chia", "Talhão 1", dia(56), "Campo e Qualidade", "Pureza 98,2%", None, None),
        ("LM-0826-A1", 1, "mel", "Extração do mel", "Apiário 1", dia(54), "Apicultura", "Umidade 17,5%", None, None),
        ("LM-0826-A1", 2, "mel", "Filtragem e envase", "Laboratório", dia(53), "Laboratório", "", 118, 116.1),
        ("LC-0926-T3", 1, "chia", "Plantio e manejo", "Talhão 3", dia(150), "Campo", "Adubação orgânica registrada", None, None),
        ("LC-0926-T3", 2, "chia", "Colheita da chia", "Talhão 3", dia(33), "Campo e Qualidade", "Pureza 98,7%", None, None),
        ("LC-0926-T3", 3, "fabrica", "Beneficiamento", "Secagem, limpeza e seleção", dia(31), "Indústria", "", 1240, 1201.6),
        ("LM-0926-A1", 1, "mel", "Extração do mel", "Apiário 1", dia(35), "Apicultura", "Umidade 17,9%", None, None),
        ("LM-0926-A1", 2, "mel", "Filtragem e envase", "Frascos de 500 g", dia(34), "Laboratório", "", 96, 94.2),
        ("LM-0926-A2", 1, "mel", "Manejo do apiário", "Apiário 2", dia(41), "Apicultura", "Colmeias revisadas", None, None),
        ("LM-0926-A2", 2, "mel", "Extração do mel", "Laboratório", dia(29), "Apicultura", "Umidade 17,8%", None, None),
        ("LM-0926-A2", 3, "fabrica", "Beneficiamento", "Filtragem", dia(28), "Laboratório", "", 142, 139.4),
        ("LB-0926-B", 1, "fabrica", "Produção da barra", "Fábrica", dia(38), "Indústria", "Linha semiautomatizada, 1.800 un.", 1000, 928),
        ("LB-0926-B", 2, "fabrica", "Controle de qualidade", "Inspeção do lote", dia(38), "Qualidade", "Conferência por amostragem", None, None),
        ("LB-1026-A", 1, "fabrica", "Produção da barra", "Fábrica", dia(15), "Indústria", "Linha semiautomatizada, 2.400 un.", 1350, 1296),
        ("LB-1026-A", 2, "fabrica", "Controle de qualidade", "Inspeção do lote", dia(15), "Qualidade", "Balanço de massa conforme", None, None),
    ]
    con.executemany("INSERT INTO lote_etapas (lote, ordem, tipo, titulo, subtitulo, data, responsavel, medidas, entrada_kg, saida_kg)"
                    " VALUES (?,?,?,?,?,?,?,?,?,?)", etapas)

    # pedidos (id, cliente, criado há (h), status, postado há, entregue há, rastreio, itens)
    pedidos = [
        (1035, 3, 24 * 45, "entregue", None, 24 * 40, "TM201101", [(1, 1, "LM-0826-A1")]),
        (1036, 4, 24 * 9, "entregue", None, 24 * 6, "TM203377", [(3, 10, "LB-0926-B")]),
        (1037, 5, 24 * 12, "entregue", None, 24 * 9, "TM203120", [(3, 1, "LB-0926-B")]),
        (1038, 2, 24 * 10, "entregue", None, 24 * 8, "TM203201", [(2, 10, "LC-0926-T3")]),
        (1039, 6, 24 * 4, "postado", 24 * 3.5, None, "TM204990", [(1, 1, "LM-0926-A1")]),
        (1040, 1, 24 * 7, "entregue", None, 24 * 4.5, "TM203999", [(1, 1, "LM-0926-A1")]),
        (1041, 1, 72, "entregue", None, 30, "TM204815", [(3, 1, "LB-1026-A")]),
        (1042, 3, 50, "entregue", None, 20, "TM204833", [(1, 2, "LM-0926-A1")]),
        (1043, 5, 30, "em_rota", 10, None, "TM205001", [(3, 2, "LB-1026-A")]),
    ]
    precos = {1: 38.00, 2: 29.90, 3: 64.00}
    for pid, cid, criado, status, postado, entregue, rastreio, itens in pedidos:
        con.execute("INSERT INTO pedidos (id, cliente_id, criado_em, status, transportadora, rastreio, postado_em, entregue_em)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (pid, cid, atras(criado), status, "TransMel Log", rastreio,
                     atras(postado) if postado else None, atras(entregue) if entregue else None))
        for prod, qtd, lote in itens:
            con.execute("INSERT INTO pedido_itens (pedido_id, produto_id, quantidade, lote, preco_unitario) VALUES (?,?,?,?,?)",
                        (pid, prod, qtd, lote, precos[prod]))

    # avaliações
    feedbacks = [
        (1035, 3, "LM-0826-A1", 4, "Sabor", "Mel delicioso.", 24 * 38),
        (1036, 4, "LB-0926-B", 2, "Textura", "Barras mais duras que da última vez, algumas quebraram na caixa.", 20),
        (1037, 5, "LB-0926-B", 5, "Sabor,Doçura", "Perfeita!", 24 * 8),
        (1038, 2, "LC-0926-T3", 5, "Entrega", "Chia limpa e entrega no prazo.", 24 * 7),
        (1040, 1, "LM-0926-A1", 3, "Embalagem", "Mel ótimo, mas a tampa vazou na caixa.", 24 * 4),
    ]
    for pid, cid, lote, nota, etq, com, h in feedbacks:
        con.execute("INSERT INTO feedbacks (pedido_id, cliente_id, lote, nota, etiquetas, comentario, criado_em) VALUES (?,?,?,?,?,?,?)",
                    (pid, cid, lote, nota, etq, com, atras(h)))

    # tickets: id, cliente, canal, categoria, prioridade, status, assunto, pedido, lote, resp, criado há, 1ª resposta há, resolvido há, eventos
    tickets = [
        (231, 4, "Aplicativo", "Qualidade", "alta", "analise", "Avaliação 2: barras duras e quebradas", 1036, "LB-0926-B", "Carlos", 20, 19, None, [
            (20, "sistema", "Sistema", "Ticket aberto automaticamente pela avaliação do cliente."),
            (20, "cliente", "Empório Boa Colheita", "Barras mais duras que da última vez, algumas quebraram na caixa."),
            (19, "status", "Roberto Lima", "Status: Novo → Em análise"),
            (19, "nota", "Carlos Pereira", "Conferir o balanço de massa do lote LB-0926-B: houve perda acima da tolerância na produção.")]),
        (232, 6, "WhatsApp", "Rastreio", "media", "aguardando_transportadora", "Pedido ainda não chegou", 1039, "LM-0926-A1", "Bia", 60, 59, None, [
            (60, "sistema", "Sistema", "Ticket aberto via WhatsApp."),
            (60, "cliente", "Helena Prado", "Oi! Já faz 4 dias e meu pedido não chegou."),
            (59, "resposta", "Bia Ramos", "Olá, Helena! Já pedi a posição à transportadora e retorno ainda hoje."),
            (58, "status", "Bia Ramos", "Status: Em análise → Aguardando transportadora")]),
        (233, 1, "WhatsApp", "Dúvida", "baixa", "novo", "A barra contém glúten?", None, None, "", 3, None, None, [
            (3, "sistema", "Sistema", "Ticket aberto via WhatsApp."),
            (3, "cliente", "Marina Alves", "A barra de mel e chia contém glúten?")]),
        (234, 2, "E-mail", "Pedido", "media", "resolucao", "Orçamento para 50 kg de chia", None, None, "Ana", 30, 29, None, [
            (30, "sistema", "Sistema", "Ticket aberto via E-mail."),
            (30, "cliente", "Restaurante Raízes", "Gostaríamos de um orçamento para 50 kg de chia a granel."),
            (29, "resposta", "Ana Souza", "Recebido! Estou conferindo o estoque do lote atual e envio o orçamento."),
            (28, "status", "Ana Souza", "Status: Em análise → Em resolução")]),
        (235, 3, "Telefone", "Sugestão", "baixa", "resolvido", "Sugestão de frasco de 250 g", None, None, "Ana", 100, 98, 70, [
            (100, "sistema", "Sistema", "Ticket aberto via Telefone."),
            (98, "resposta", "Ana Souza", "Obrigada pela sugestão! Levei para a equipe de produção."),
            (70, "status", "Ana Souza", "Status: Em análise → Resolvido")]),
        (236, 1, "WhatsApp", "Reclamação", "media", "aguardando_cliente", "Tampa do frasco vazou", 1040, "LM-0926-A1", "Ana", 30, 29, None, [
            (30, "sistema", "Sistema", "Ticket aberto via WhatsApp."),
            (30, "cliente", "Marina Alves", "A tampa do frasco de mel vazou durante o transporte."),
            (29, "resposta", "Ana Souza", "Sentimos muito! Pode enviar uma foto da embalagem para registrarmos o lote?"),
            (29, "status", "Ana Souza", "Status: Em análise → Aguardando cliente")]),
        (237, 4, "E-mail", "Dúvida", "baixa", "encerrado", "Tabela de preços de revenda", None, None, "Ana", 24 * 9, 24 * 9 - 2, 24 * 8, [
            (24 * 9, "sistema", "Sistema", "Ticket aberto via E-mail."),
            (24 * 9 - 2, "resposta", "Ana Souza", "Enviei a tabela de revenda atualizada por e-mail."),
            (24 * 8, "status", "Ana Souza", "Status: Resolvido → Encerrado")]),
        (238, 6, "Instagram", "Sugestão", "baixa", "novo", "Potes de vidro para o mel?", None, None, "", 5, None, None, [
            (5, "sistema", "Sistema", "Mensagem direta do Instagram transformada em ticket."),
            (5, "cliente", "Helena Prado", "Vocês vendem o mel em potes de vidro?")]),
    ]
    for tid, cid, canal, cat, pri, st, ass, pid, lote, resp, criado, resposta, resolvido, eventos in tickets:
        con.execute("INSERT INTO tickets (id, protocolo, cliente_id, canal, categoria, prioridade, status, assunto, pedido_id, lote,"
                    " responsavel, criado_em, primeira_resposta_em, resolvido_em) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (tid, f"CAMC-{tid:04d}", cid, canal, cat, pri, st, ass, pid, lote, resp, atras(criado),
                     atras(resposta) if resposta else None, atras(resolvido) if resolvido else None))
        for h, tipo, autor, texto in eventos:
            con.execute("INSERT INTO ticket_eventos (ticket_id, tipo, autor, texto, criado_em) VALUES (?,?,?,?,?)",
                        (tid, tipo, autor, texto, atras(h)))

    # contatos fora de ticket
    con.executemany("INSERT INTO interacoes (cliente_id, canal, texto, criado_em) VALUES (?,?,?,?)", [
        (1, "WhatsApp", "Pedido P-1041 entregue. Cliente confirmou: chegou tudo certo.", atras(29)),
        (3, "Telefone", "Ligação de 6 min: perguntou sobre a validade do mel.", atras(48)),
        (2, "E-mail", "Enviada nota fiscal do pedido P-1038.", atras(24 * 10)),
        (5, "Aplicativo", "Cadastro feito pelo aplicativo.", atras(24 * 15)),
        (4, "Telefone", "Ligação de 11 min: combinou nova reposição de barras.", atras(24 * 12)),
    ])

    # trilha de auditoria inicial
    for horas, quem, acao, detalhe in [
        (24 * 12, "Sistema", "Implantação", "Banco de dados inicializado e cadeia de auditoria criada."),
        (24 * 12, "Roberto Lima (Gestor)", "Perfis de acesso", "Seis perfis configurados: Atendente, Gestor, Logística, Produção, Auditor e Administrador de TI."),
        (24 * 5, "Ana Souza (Atendente)", "Cliente cadastrado", "Helena Prado cadastrada com consentimento LGPD."),
        (60, "Ana Souza (Atendente)", "Ticket aberto", "CAMC-0232 aberto via WhatsApp."),
        (58, "Bia Ramos (Logística)", "Status alterado", "CAMC-0232: Em análise → Aguardando transportadora."),
        (20, "Cliente (aplicativo)", "Avaliação registrada", "P-1036, nota 2, lote LB-0926-B."),
        (20, "Sistema", "Ticket aberto", "CAMC-0231 aberto automaticamente (nota baixa)."),
        (19, "Roberto Lima (Gestor)", "Status alterado", "CAMC-0231: Novo → Em análise."),
        (3, "Ana Souza (Atendente)", "Ticket aberto", "CAMC-0233 aberto via WhatsApp."),
    ]:
        seguranca.registrar_auditoria(con, quem, acao, detalhe, quando=atras(horas))
    con.commit()
