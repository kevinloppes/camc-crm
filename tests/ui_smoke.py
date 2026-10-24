"""Teste de fumaça da interface (precisa de um display; no Linux use: xvfb-run -a python tests/ui_smoke.py).

Percorre as telas com cada perfil, simula o fluxo de avaliação em 3 cliques e
falha se qualquer callback do Tkinter levantar exceção. Se a variável de
ambiente CAMC_CAPTURAS apontar para uma pasta, salva imagens das telas.
"""
import os
import subprocess
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
os.environ["CAMC_DADOS"] = tempfile.mkdtemp()

from tkinter import messagebox  # noqa: E402

from camc import banco, exemplo, interface, seguranca  # noqa: E402

CAPTURAS = os.environ.get("CAMC_CAPTURAS")
erros, avisos = [], []
for nome in ("showwarning", "showinfo", "showerror"):
    setattr(messagebox, nome, lambda t, m, **kw: avisos.append((t, m)))
messagebox.askyesno = lambda t, m, **kw: True


def fechar_janelas(w):
    for f in list(w.winfo_children()):
        if isinstance(f, interface.JanelaCadeia):
            f.destroy()
        else:
            fechar_janelas(f)


def captura(app, nome, janela=None):
    """Salva uma imagem da janela (requer ImageMagick: comando 'import')."""
    app.root.update_idletasks()
    app.root.update()
    if CAPTURAS:
        Path(CAPTURAS).mkdir(parents=True, exist_ok=True)
        alvo = (janela or app.root).winfo_toplevel()
        area = f"{alvo.winfo_width()}x{alvo.winfo_height()}+{alvo.winfo_rootx()}+{alvo.winfo_rooty()}"
        subprocess.run(["import", "-window", "root", "-crop", area, "+repage", str(Path(CAPTURAS) / f"{nome}.png")], check=False)


def entrar(app, login):
    if not isinstance(app.atual, interface.TelaLogin):
        app.atual.sair()
    app.root.update()
    app.atual.login.set(login)
    app.atual.senha.set(exemplo.SENHA_DEMO)
    app.atual.entrar()
    app.root.update()
    return app.atual


def aba(app, chave):
    app.atual.nb.select(app.atual.abas[chave])
    app.root.update()
    return app.atual.abas[chave]


def main():
    con = banco.conectar()
    banco.inicializar(con)
    exemplo.popular(con, iteracoes=1000)
    app = interface.Aplicacao(con)
    app.root.report_callback_exception = lambda *a: erros.append(a)
    app.root.update()
    captura(app, "01_login")

    # login com senha errada
    app.atual.login.set("gestor")
    app.atual.senha.set("errada")
    app.atual.entrar()
    assert "incorretos" in app.atual.erro.get()
    captura(app, "02_login_erro")

    # ---- atendente
    principal = entrar(app, "atendente")
    assert set(principal.abas) == {"painel", "tickets", "clientes", "rastreio"}, principal.abas
    captura(app, "03_painel")
    t = aba(app, "tickets")
    t.tree.selection_set("231")
    app.root.update()
    captura(app, "04_tickets")
    t._mudar("resolvido") if False else None
    t.tree.selection_set("233")
    app.root.update()
    t._mudar("analise")
    assert principal.srv.obter_ticket(233)["status"] == "analise"
    t.resposta.insert("1.0", "Olá, Marina! A barra não contém glúten.")
    t._responder()
    assert principal.srv.obter_ticket(233)["primeira_resposta_em"]
    t.v_busca.set("glúten")
    app.root.update()
    assert len(t.tree.get_children()) == 1
    t.v_busca.set("")
    c = aba(app, "clientes")
    c.selecionar(1)
    app.root.update()
    captura(app, "05_clientes")
    c.nb.select(1)
    app.root.update()
    captura(app, "06_clientes_historico")
    c.nb.select(2)
    c.compras.selection_set("1041")
    c._rastreio()
    app.root.update()
    captura(app, "07_rastreio_pedido")
    fechar_janelas(app.root)
    # novo cliente: duplicidade e cadastro válido
    dlg = interface.DialogoCliente(c, principal.srv)
    dlg.v["nome"].set("Fernanda Lopes"); dlg.v["documento"].set("877.482.488-00"); dlg.v["telefone"].set("(12) 98888-7777")
    dlg.salvar()
    assert dlg.erro.get().startswith("Registre o consentimento"), dlg.erro.get()
    captura(app, "08_dialogo_cliente")
    dlg.consentimento.set(True)
    dlg.salvar()
    app.root.update()
    assert any(x["nome"] == "Fernanda Lopes" for x in principal.srv.listar_clientes())
    # novo ticket
    dt = interface.DialogoTicket(t, principal.srv, ao_criar=lambda tid: principal.atualizar_tudo())
    dt.var_ass.set("Prazo de validade do mel")
    dt.texto.insert("1.0", "Qual a validade?")
    captura(app, "09_dialogo_ticket")
    dt.salvar()
    app.root.update()
    assert principal.srv.listar_tickets(busca="validade do mel")

    # ---- app do cliente: caminho pela notificação, nota baixa
    principal.abrir_app_cliente()
    j = principal.janela_cliente
    app.root.update()
    j.geometry("+60+30")
    captura(app, "10_app_notificacao", j)
    j.geometry("+60+30")
    j.lift()
    j.toque_notificacao()
    captura(app, "11_app_avaliar", j)
    j.toque_estrela(2)
    j.alternar_etiqueta("Textura")
    j.campo.insert("1.0", "Barra muito dura.")
    app.root.update()
    captura(app, "12_app_nota_baixa", j)
    j.enviar()
    app.root.update()
    assert j.resultado["cliques"] == 3 and j.ticket_id, (j.resultado, j.ticket_id)
    captura(app, "13_app_obrigado", j)
    j.falar_com_a_gente()
    assert j.contato
    # caminho pelo cartão: nota alta, 2 cliques
    j.caminho.set("cartao")
    j._simular_entrega()
    j._trocar_caminho()
    captura(app, "14_app_cartao", j)
    j.toque_estrela(5)
    j.enviar()
    assert j.resultado["cliques"] == 2 and not j.ticket_id
    j.destroy()

    # ---- logística só edita Rastreio
    principal = entrar(app, "logistica")
    t = aba(app, "tickets")
    t.tree.selection_set("236")
    app.root.update()
    assert "disabled" in t.btn_enviar.state()
    t.tree.selection_set("232")
    app.root.update()
    assert "disabled" not in t.btn_enviar.state()

    # ---- produção registra etapa com alerta
    principal = entrar(app, "producao")
    assert set(principal.abas) == {"painel", "rastreio"}
    r = aba(app, "rastreio")
    app.root.update()
    captura(app, "15_rastreio")
    de = interface.DialogoEtapa(r, principal.srv, "LB-1026-A", ao_salvar=lambda l: principal.atualizar_tudo())
    de.v["titulo"].set("Embalagem"); de.v["entrada"].set("1296"); de.v["saida"].set("1100")
    de.salvar()
    assert any("Perda acima" in a[1] for a in avisos), avisos

    # ---- gestor: auditoria e adulteração
    principal = entrar(app, "gestor")
    au = aba(app, "auditoria")
    assert "íntegra" in au.banner.cget("text")
    captura(app, "16_auditoria")
    au._simular()
    app.root.update()
    assert "Quebra detectada" in au.banner.cget("text")
    captura(app, "17_auditoria_quebra")
    au._desfazer()
    assert "íntegra" in au.banner.cget("text")
    cl = aba(app, "clientes")
    cl.selecionar(2)
    cl._anonimizar()
    assert principal.srv.obter_cliente(2)["anonimizado"] == 1

    # ---- admin de TI
    principal = entrar(app, "admin")
    assert set(principal.abas) == {"auditoria", "admin"}, principal.abas
    ad = aba(app, "admin")
    ad._criar()
    app.root.update()
    ad.tree_bk.selection_set(ad.tree_bk.get_children()[0])
    ad._testar()
    app.root.update()
    assert "APROVADO" in ad.lbl_teste.cget("text"), ad.lbl_teste.cget("text")
    captura(app, "18_admin")

    # ---- auditor consulta
    principal = entrar(app, "auditor")
    au = aba(app, "auditoria")
    captura(app, "19_auditor")

    ok, quebra, total = seguranca.verificar_cadeia(con)
    assert ok, quebra
    app.root.destroy()
    if erros:
        import traceback
        for e in erros:
            traceback.print_exception(*e)
        raise SystemExit(f"{len(erros)} erro(s) em callbacks do Tkinter")
    print(f"Interface OK. Auditoria íntegra com {total} registros.")


if __name__ == "__main__":
    main()
