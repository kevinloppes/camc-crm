"""Testes automatizados: python -m unittest discover -s tests -v"""
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from camc import banco, exemplo, seguranca, servicos  # noqa: E402
from camc.servicos import ClienteDuplicado, ErroValidacao, ServicoCRM  # noqa: E402

SENHA = exemplo.SENHA_DEMO


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pasta = Path(self.tmp.name)
        self.con = banco.conectar(self.pasta / "teste.db")
        banco.inicializar(self.con)
        exemplo.popular(self.con, iteracoes=1000)
        banco.PASTA_BACKUPS = self.pasta / "backups"

    def tearDown(self):
        self.con.close()
        self.tmp.cleanup()

    def como(self, login):
        sessao = seguranca.autenticar(self.con, login, SENHA)
        return ServicoCRM(self.con, sessao)

    def dados_cliente(self, **extra):
        d = {"nome": "Fernanda Lopes", "tipo": "PF", "documento": "87748248800",
             "telefone": "(12) 98888-7777", "email": "fernanda@email.example", "cidade": "Jacareí",
             "canal_preferido": "WhatsApp", "segmento": "Consumidor de mel"}
        d.update(extra)
        return d


class TestValidadores(unittest.TestCase):
    def test_cpf(self):
        self.assertTrue(servicos.validar_cpf("529.982.247-25"))
        self.assertFalse(servicos.validar_cpf("529.982.247-24"))
        self.assertFalse(servicos.validar_cpf("111.111.111-11"))

    def test_cnpj(self):
        self.assertTrue(servicos.validar_cnpj("11.222.333/0001-81"))
        self.assertFalse(servicos.validar_cnpj("11.222.333/0001-80"))

    def test_sla(self):
        agora = datetime.now()
        t = {"criado_em": (agora - timedelta(hours=50)).isoformat(sep=" "), "prioridade": "media", "resolvido_em": None}
        self.assertEqual(servicos.calcular_sla(t)[0], "atrasado")
        t["criado_em"] = (agora - timedelta(hours=10)).isoformat(sep=" ")
        self.assertEqual(servicos.calcular_sla(t)[0], "ok")
        t["criado_em"] = (agora - timedelta(hours=46)).isoformat(sep=" ")
        self.assertEqual(servicos.calcular_sla(t)[0], "alerta")


class TestSeguranca(Base):
    def test_senha_hash_e_politica(self):
        h, sal, it = seguranca.hash_senha("minha-senha-forte-1")
        self.assertTrue(seguranca.verificar_senha("minha-senha-forte-1", h, sal, it))
        self.assertFalse(seguranca.verificar_senha("outra", h, sal, it))
        self.assertIsNotNone(seguranca.validar_forca_senha("curta1"))
        self.assertIsNotNone(seguranca.validar_forca_senha("somenteletrasaqui"))
        self.assertIsNone(seguranca.validar_forca_senha("senha-forte-2026"))

    def test_login_e_bloqueio(self):
        with self.assertRaises(seguranca.ErroAutenticacao):
            seguranca.autenticar(self.con, "atendente", "errada")
        for _ in range(seguranca.MAX_TENTATIVAS):
            with self.assertRaises(seguranca.ErroAutenticacao):
                seguranca.autenticar(self.con, "gestor", "errada")
        with self.assertRaises(seguranca.ErroAutenticacao) as ctx:
            seguranca.autenticar(self.con, "gestor", SENHA)
        self.assertIn("bloqueada", str(ctx.exception))

    def test_perfis(self):
        self.assertTrue(seguranca.tem_permissao("gestor", "auditoria.verificar"))
        self.assertFalse(seguranca.tem_permissao("atendente", "auditoria.ver"))
        self.assertFalse(seguranca.tem_permissao("admin_ti", "clientes.ver"))  # TI não vê dados de negócio

    def test_cadeia_de_auditoria_detecta_adulteracao(self):
        ok, quebra, total = seguranca.verificar_cadeia(self.con)
        self.assertTrue(ok)
        self.assertGreater(total, 5)
        seguranca.simular_adulteracao(self.con)
        ok, quebra, _ = seguranca.verificar_cadeia(self.con)
        self.assertFalse(ok)
        self.assertEqual(quebra, 3)
        self.assertTrue(seguranca.desfazer_adulteracao(self.con))
        self.assertTrue(seguranca.verificar_cadeia(self.con)[0])

    def test_banco_recusa_update_e_delete_na_auditoria(self):
        import sqlite3
        with self.assertRaises(sqlite3.DatabaseError):
            self.con.execute("UPDATE auditoria SET detalhe = 'x' WHERE n = 1")
        with self.assertRaises(sqlite3.DatabaseError):
            self.con.execute("DELETE FROM auditoria WHERE n = 1")

    def test_backup_e_teste_de_restauracao(self):
        admin = self.como("admin")
        caminho = admin.criar_backup()
        self.assertTrue(caminho.exists())
        rel = admin.testar_backup(caminho)
        self.assertTrue(rel["aprovado"], rel)
        self.assertGreater(rel["clientes"], 0)
        # corrompe o backup: o teste precisa reprovar
        with open(caminho, "ab") as f:
            f.write(b"lixo")
        self.assertFalse(admin.testar_backup(caminho)["aprovado"])

    def test_retencao_de_backups(self):
        for _ in range(4):
            seguranca.criar_backup(self.con, banco.PASTA_BACKUPS, manter=2)
        self.assertEqual(len(list(banco.PASTA_BACKUPS.glob("camc_*.db"))), 2)


class TestClientes(Base):
    def test_cadastro_com_consentimento_e_auditoria(self):
        s = self.como("atendente")
        with self.assertRaises(ErroValidacao):
            s.criar_cliente(self.dados_cliente(), consentimento=False)
        cid = s.criar_cliente(self.dados_cliente(), consentimento=True)
        c = s.obter_cliente(cid)
        self.assertEqual(c["documento"], "87748248800")
        self.assertIsNotNone(c["consentimento_em"])
        ultimo = self.con.execute("SELECT * FROM auditoria ORDER BY n DESC LIMIT 1").fetchone()
        self.assertEqual(ultimo["acao"], "Cliente cadastrado")
        self.assertTrue(seguranca.verificar_cadeia(self.con)[0])

    def test_validacoes(self):
        s = self.como("atendente")
        with self.assertRaises(ErroValidacao):
            s.criar_cliente(self.dados_cliente(documento="123.456.789-00"), True)
        with self.assertRaises(ErroValidacao):
            s.criar_cliente(self.dados_cliente(telefone="", email=""), True)
        with self.assertRaises(ErroValidacao):
            s.criar_cliente(self.dados_cliente(email="sem-arroba"), True)

    def test_duplicidade_por_documento_telefone_e_email(self):
        s = self.como("atendente")
        with self.assertRaises(ClienteDuplicado) as ctx:
            s.criar_cliente(self.dados_cliente(documento="529.982.247-25"), True)
        self.assertEqual(ctx.exception.existente["nome"], "Marina Alves")
        with self.assertRaises(ClienteDuplicado):
            s.criar_cliente(self.dados_cliente(telefone="12 99100 0003"), True)
        with self.assertRaises(ClienteDuplicado):
            s.criar_cliente(self.dados_cliente(email="PAULO.N@email.example"), True)

    def test_permissoes_de_clientes(self):
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("gestor").criar_cliente(self.dados_cliente(), True)
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("producao").listar_clientes()
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("atendente").anonimizar_cliente(1)

    def test_anonimizacao_lgpd(self):
        g = self.como("gestor")
        g.anonimizar_cliente(2)
        c = g.obter_cliente(2)
        self.assertEqual((c["documento"], c["telefone"], c["email"]), ("", "", ""))
        self.assertEqual(c["anonimizado"], 1)
        self.assertEqual(len(g.anotacoes(2)), 0)
        self.assertGreater(len(g.pedidos_do_cliente(2)), 0)  # histórico permanece
        with self.assertRaises(ErroValidacao):
            self.como("atendente").editar_cliente(2, self.dados_cliente())

    def test_linha_do_tempo_unifica_canais(self):
        tl = self.como("atendente").linha_do_tempo(1)
        origens = {e["origem"] for e in tl}
        self.assertTrue({"WhatsApp", "Pedido", "Entrega", "Ticket", "Avaliação"} <= origens)
        self.assertEqual([e["quando"] for e in tl], sorted([e["quando"] for e in tl], reverse=True))


class TestTickets(Base):
    def test_criacao_e_regra_de_qualidade(self):
        s = self.como("atendente")
        with self.assertRaises(ErroValidacao):
            s.criar_ticket(1, "WhatsApp", "Qualidade", "alta", "Barra estragada")
        with self.assertRaises(ErroValidacao):
            s.criar_ticket(1, "WhatsApp", "Qualidade", "alta", "Barra estragada", pedido_id=1036)  # pedido de outro cliente
        tid = s.criar_ticket(1, "WhatsApp", "Qualidade", "alta", "Barra estragada", "Veio com gosto estranho", pedido_id=1041)
        t = s.obter_ticket(tid)
        self.assertEqual(t["lote"], "LB-1026-A")
        self.assertEqual(t["status"], "novo")
        self.assertTrue(t["protocolo"].startswith("CAMC-"))

    def test_fluxo_de_status(self):
        s = self.como("atendente")
        tid = s.criar_ticket(1, "E-mail", "Dúvida", "baixa", "Prazo de validade")
        with self.assertRaises(ErroValidacao):
            s.mudar_status(tid, "resolvido")  # novo não pula etapas
        s.mudar_status(tid, "analise")
        s.responder(tid, "A validade é de 12 meses.")
        t = s.obter_ticket(tid)
        self.assertIsNotNone(t["primeira_resposta_em"])
        s.mudar_status(tid, "resolvido")
        self.assertIsNotNone(s.obter_ticket(tid)["resolvido_em"])
        s.mudar_status(tid, "encerrado")
        s.reabrir_ticket(tid)
        t = s.obter_ticket(tid)
        self.assertEqual((t["status"], t["resolvido_em"]), ("analise", None))

    def test_perfis_de_edicao(self):
        logistica = self.como("logistica")
        logistica.mudar_status(232, "analise")  # ticket de Rastreio: pode
        with self.assertRaises(seguranca.PermissaoNegada):
            logistica.mudar_status(236, "analise")  # reclamação: não pode
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("auditor").nota_interna(231, "teste")
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("auditor").criar_ticket(1, "E-mail", "Dúvida", "baixa", "x")
        self.assertEqual(len(self.como("auditor").listar_tickets()), 8)

    def test_filtros(self):
        s = self.como("atendente")
        self.assertEqual(len(s.listar_tickets(busca="glúten")), 1)
        self.assertEqual(len(s.listar_tickets(categoria="Rastreio")), 1)
        self.assertEqual(len(s.listar_tickets(ocultar_encerrados=True)), 7)


class TestFeedbackERastreio(Base):
    def test_nota_baixa_abre_ticket_automatico(self):
        s = self.como("atendente")
        fid, tid = s.registrar_feedback(1041, 1, ["Textura"], "Muito dura", cliques=3, segundos=8)
        self.assertIsNotNone(tid)
        t = s.obter_ticket(tid)
        self.assertEqual((t["categoria"], t["prioridade"], t["lote"], t["canal"]), ("Qualidade", "alta", "LB-1026-A", "Aplicativo"))
        s.solicitar_contato(tid)
        self.assertIn("Pediu contato", s.eventos_ticket(tid)[-1]["texto"])

    def test_nota_alta_nao_abre_ticket_e_pedido_so_avalia_uma_vez(self):
        s = self.como("atendente")
        _, tid = s.registrar_feedback(1042, 5, ["Sabor"], "Ótimo")
        self.assertIsNone(tid)
        with self.assertRaises(ErroValidacao):
            s.registrar_feedback(1042, 4)
        with self.assertRaises(ErroValidacao):
            s.registrar_feedback(1043, 5)  # ainda em rota
        with self.assertRaises(ErroValidacao):
            s.registrar_feedback(1041, 6)

    def test_simular_entrega_libera_avaliacao(self):
        s = self.como("atendente")
        antes = len(s.pedidos_aguardando_avaliacao())
        self.assertEqual(s.simular_entrega(), 1043)
        self.assertEqual(len(s.pedidos_aguardando_avaliacao()), antes + 1)

    def test_cadeia_do_lote_e_balanco_de_massa(self):
        s = self.como("gestor")
        nos = s.cadeia_do_lote("LB-0926-B")
        alertas = [n["alerta"] for n in nos if n["alerta"]]
        self.assertEqual(len(alertas), 1)
        self.assertIn("Perda acima", alertas[0])
        self.assertEqual(nos[0]["lote"], "LC-0826-T1")  # insumos vêm primeiro
        cadeia = s.cadeia_do_pedido(1041)
        self.assertEqual([n["tipo"] for n in cadeia[-3:]], ["pedido", "entrega", "feedback"])
        self.assertTrue(cadeia[-1]["pendente"])

    def test_registrar_etapa_exige_perfil_e_calcula_alerta(self):
        with self.assertRaises(seguranca.PermissaoNegada):
            self.como("atendente").registrar_etapa("LB-1026-A", "fabrica", "Embalagem", "", "", 100, 99, "")
        p = self.como("producao")
        self.assertEqual(p.registrar_etapa("LB-1026-A", "fabrica", "Embalagem", "Fábrica", "Indústria", 100, 99, ""), "")
        self.assertIn("Perda acima", p.registrar_etapa("LB-1026-A", "fabrica", "Selagem", "Fábrica", "Indústria", 100, 80, ""))
        self.assertIn("Saída maior", p.registrar_etapa("LB-1026-A", "fabrica", "Pesagem", "Fábrica", "Indústria", 100, 120, ""))
        with self.assertRaises(ErroValidacao):
            p.registrar_etapa("LB-1026-A", "fabrica", "Sem saída", "", "", 100, None, "")

    def test_indicadores(self):
        i = self.como("auditor").indicadores()
        self.assertEqual(i["abertos"], 6)
        self.assertGreaterEqual(i["atrasados"], 1)
        self.assertAlmostEqual(i["satisfacao"], 3.8)
        self.assertEqual(dict(i["reclamacoes_por_lote"]).get("LB-0926-B"), 1)


class TestAdmin(Base):
    def test_usuarios_e_senha(self):
        admin = self.como("admin")
        self.assertEqual(len(admin.listar_usuarios()), 6)
        with self.assertRaises(ErroValidacao):
            admin.alternar_usuario(admin.sessao.usuario_id)
        uid = self.con.execute("SELECT id FROM usuarios WHERE login='atendente'").fetchone()["id"]
        self.assertFalse(admin.alternar_usuario(uid))
        with self.assertRaises(seguranca.ErroAutenticacao):
            seguranca.autenticar(self.con, "atendente", SENHA)
        a = self.como("gestor")
        with self.assertRaises(ErroValidacao):
            a.alterar_minha_senha(SENHA, "curta")
        a.alterar_minha_senha(SENHA, "nova-senha-2026!")
        seguranca.autenticar(self.con, "gestor", "nova-senha-2026!")


if __name__ == "__main__":
    unittest.main()
