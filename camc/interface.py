"""Interface gráfica (Tkinter) do sistema da CAMC.

Telas: login, painel (com a cadeia "da colmeia/planta à mesa"), tickets,
clientes, rastreabilidade, auditoria, administração (backup e usuários) e a
simulação do aplicativo do cliente (avaliação em até 3 cliques).
"""
from __future__ import annotations

import os
import time
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox, ttk

from . import banco, seguranca, servicos
from .servicos import (CANAIS, CATEGORIAS, ETIQUETAS, PRIORIDADES, RESPONSAVEIS, SEGMENTOS, STATUS, TIPOS_ETAPA,
                       ClienteDuplicado, ErroValidacao, ServicoCRM)

COR = {
    "fundo": "#F2F1F7", "superficie": "#FFFFFF", "tinta": "#25222E", "tinta2": "#5E5A6E", "linha": "#DEDBEA",
    "chia": "#5A4A9C", "chia_escuro": "#473A7E", "chia_suave": "#E8E4F6",
    "mel": "#E3A21A", "mel_suave": "#FBEBC2", "mel_tinta": "#2A1F05",
    "ok": "#2F7A4B", "ok_suave": "#DCEFE2", "ruim": "#B23A3A", "ruim_suave": "#F6DCDC", "aviso": "#9A6A08",
    "lateral": "#2B2542",
}
FONTE = {}


# ---------------------------------------------------------------------- tema
def _familia(root, preferidas):
    existentes = set(tkfont.families(root))
    for f in preferidas:
        if f in existentes:
            return f
    return tkfont.nametofont("TkDefaultFont").actual("family")


def aplicar_tema(root: tk.Tk) -> None:
    sans = _familia(root, ("Segoe UI", "Helvetica Neue", "Noto Sans", "Ubuntu", "DejaVu Sans"))
    serif = _familia(root, ("Georgia", "Cambria", "Noto Serif", "DejaVu Serif"))
    mono = _familia(root, ("Consolas", "Menlo", "DejaVu Sans Mono", "Courier New"))
    FONTE.update({
        "base": tkfont.Font(root, family=sans, size=10),
        "negrito": tkfont.Font(root, family=sans, size=10, weight="bold"),
        "pequena": tkfont.Font(root, family=sans, size=9),
        "pequena_negrito": tkfont.Font(root, family=sans, size=9, weight="bold"),
        "titulo": tkfont.Font(root, family=serif, size=19),
        "subtitulo": tkfont.Font(root, family=serif, size=13),
        "kpi": tkfont.Font(root, family=serif, size=21),
        "glifo": tkfont.Font(root, family=serif, size=15),
        "mono": tkfont.Font(root, family=mono, size=9),
        "relogio": tkfont.Font(root, family=serif, size=44),
        "estrela": tkfont.Font(root, family=sans, size=22),
        "grande": tkfont.Font(root, family=sans, size=12, weight="bold"),
    })
    for nome in ("TkDefaultFont", "TkTextFont", "TkMenuFont", "TkHeadingFont"):
        tkfont.nametofont(nome).configure(family=sans, size=10)
    root.option_add("*TCombobox*Listbox.font", FONTE["base"])
    root.configure(bg=COR["fundo"])

    st = ttk.Style(root)
    st.theme_use("clam")
    st.configure(".", background=COR["fundo"], foreground=COR["tinta"], font=FONTE["base"], bordercolor=COR["linha"],
                 lightcolor=COR["fundo"], darkcolor=COR["fundo"], focuscolor=COR["mel"])
    st.configure("TFrame", background=COR["fundo"])
    st.configure("Cartao.TFrame", background=COR["superficie"])
    st.configure("TLabel", background=COR["fundo"], foreground=COR["tinta"])
    st.configure("Cartao.TLabel", background=COR["superficie"])
    st.configure("Titulo.TLabel", font=FONTE["titulo"])
    st.configure("Subtitulo.TLabel", font=FONTE["subtitulo"], background=COR["superficie"])
    st.configure("Suave.TLabel", foreground=COR["tinta2"])
    st.configure("CartaoSuave.TLabel", foreground=COR["tinta2"], background=COR["superficie"])
    st.configure("Negrito.TLabel", font=FONTE["negrito"])
    st.configure("CartaoNegrito.TLabel", font=FONTE["negrito"], background=COR["superficie"])
    st.configure("Erro.TLabel", foreground=COR["ruim"], font=FONTE["negrito"])
    st.configure("KpiNum.TLabel", font=FONTE["kpi"], background=COR["superficie"])
    st.configure("BannerOk.TLabel", background=COR["ok_suave"], foreground=COR["ok"], font=FONTE["negrito"], padding=(14, 10))
    st.configure("BannerRuim.TLabel", background=COR["ruim_suave"], foreground=COR["ruim"], font=FONTE["negrito"], padding=(14, 10))
    st.configure("TButton", padding=(12, 6), background=COR["superficie"], foreground=COR["tinta"], bordercolor=COR["linha"])
    st.map("TButton", background=[("active", COR["chia_suave"]), ("disabled", COR["fundo"])],
           foreground=[("disabled", "#9A96A8")])
    st.configure("Primario.TButton", background=COR["chia"], foreground="#FFFFFF", bordercolor=COR["chia"], font=FONTE["negrito"])
    st.map("Primario.TButton", background=[("active", COR["chia_escuro"]), ("disabled", "#B9B2D6")],
           foreground=[("disabled", "#FFFFFF")])
    st.configure("Mel.TButton", background=COR["mel"], foreground=COR["mel_tinta"], bordercolor=COR["mel"], font=FONTE["negrito"])
    st.map("Mel.TButton", background=[("active", "#F0B73A"), ("disabled", COR["mel_suave"])])
    st.configure("Perigo.TButton", foreground=COR["ruim"])
    st.configure("Pequeno.TButton", padding=(8, 3))
    st.configure("TNotebook", background=COR["fundo"], borderwidth=0, tabmargins=(0, 0, 0, 0))
    st.configure("TNotebook.Tab", padding=(18, 9), font=FONTE["negrito"], background=COR["chia_suave"], foreground=COR["tinta2"])
    st.map("TNotebook.Tab", background=[("selected", COR["superficie"])], foreground=[("selected", COR["chia"])])
    st.configure("Interno.TNotebook.Tab", padding=(14, 6))
    st.configure("Treeview", background=COR["superficie"], fieldbackground=COR["superficie"], rowheight=27,
                 bordercolor=COR["linha"], font=FONTE["base"])
    st.configure("Treeview.Heading", background=COR["chia_suave"], foreground=COR["chia"], font=FONTE["negrito"], padding=(6, 5),
                 relief="flat")
    st.map("Treeview", background=[("selected", COR["chia"])], foreground=[("selected", "#FFFFFF")])
    st.configure("TEntry", padding=5, fieldbackground=COR["superficie"])
    st.configure("TCombobox", padding=4, fieldbackground=COR["superficie"], arrowcolor=COR["chia"])
    st.map("TCombobox", fieldbackground=[("readonly", COR["superficie"])])
    st.configure("TCheckbutton", background=COR["fundo"])
    st.configure("TRadiobutton", background=COR["fundo"])
    st.configure("TPanedwindow", background=COR["fundo"])
    st.configure("TLabelframe", background=COR["superficie"], bordercolor=COR["linha"])
    st.configure("TLabelframe.Label", background=COR["superficie"], foreground=COR["tinta"], font=FONTE["negrito"])
    st.configure("Vertical.TScrollbar", background=COR["chia_suave"], troughcolor=COR["fundo"], bordercolor=COR["fundo"])
    st.configure("Horizontal.TScrollbar", background=COR["chia_suave"], troughcolor=COR["fundo"], bordercolor=COR["fundo"])


def cartao(mestre, **kw) -> tk.Frame:
    """Quadro branco com borda fina (usado como "cartão")."""
    return tk.Frame(mestre, bg=COR["superficie"], highlightthickness=1, highlightbackground=COR["linha"], **kw)


def pontos_hexagono(cx, cy, larg, alt):
    return [cx, cy - alt / 2, cx + larg / 2, cy - alt / 4, cx + larg / 2, cy + alt / 4,
            cx, cy + alt / 2, cx - larg / 2, cy + alt / 4, cx - larg / 2, cy - alt / 4]


def avisar(mestre, texto: str, titulo: str = "Atenção") -> None:
    messagebox.showwarning(titulo, texto, parent=mestre)


# ----------------------------------------------------------------- componentes
class CadeiaCanvas(ttk.Frame):
    """Linha do tempo em hexágonos: da origem no campo/apiário até a avaliação do cliente."""
    LARG = 196
    CORES = {"chia": (COR["chia"], "#FFFFFF"), "mel": (COR["mel"], COR["mel_tinta"]), "fabrica": (COR["tinta"], "#FFFFFF"),
             "pedido": (COR["tinta2"], "#FFFFFF"), "entrega": (COR["ok"], "#FFFFFF"), "feedback": (COR["mel"], COR["mel_tinta"])}
    GLIFO = {"chia": "C", "mel": "M", "fabrica": "F", "pedido": "P", "entrega": "E", "feedback": "★"}

    def __init__(self, mestre, altura: int = 250):
        super().__init__(mestre)
        self.altura = altura
        self.canvas = tk.Canvas(self, height=altura, bg=COR["superficie"], highlightthickness=0)
        self.barra = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(xscrollcommand=self.barra.set)
        self.canvas.pack(fill="both", expand=True)
        self.barra.pack(fill="x")

    def mostrar(self, nos: list) -> None:
        c = self.canvas
        c.delete("all")
        if not nos:
            c.create_text(18, 30, anchor="w", text="Nenhuma etapa registrada para este lote.", fill=COR["tinta2"], font=FONTE["base"])
        for i, no in enumerate(nos):
            x = 14 + i * self.LARG
            cor, cor_glifo = self.CORES[no["tipo"]]
            if i < len(nos) - 1:
                c.create_line(x + 56, 38, x + self.LARG - 6, 38, fill=COR["linha"], dash=(4, 3), width=2)
            pend = no.get("pendente")
            c.create_polygon(pontos_hexagono(x + 27, 38, 50, 56), fill=COR["fundo"] if pend else cor,
                             outline=COR["linha"] if pend else cor, width=2)
            c.create_text(x + 27, 38, text=self.GLIFO[no["tipo"]], font=FONTE["glifo"], fill=COR["tinta2"] if pend else cor_glifo)
            y = 74
            for texto, fonte, cor_txt in (
                    (no["titulo"], FONTE["negrito"], COR["tinta"]), (no["subtitulo"], FONTE["pequena"], COR["tinta"]),
                    (no["data"], FONTE["pequena"], COR["tinta2"]), (no["medidas"], FONTE["pequena"], COR["tinta"]),
                    (("⚠ " + no["alerta"]) if no["alerta"] else "", FONTE["pequena_negrito"], COR["ruim"]),
                    (no["lote"], FONTE["mono"], COR["chia"])):
                if not texto:
                    continue
                item = c.create_text(x, y, text=texto, anchor="nw", font=fonte, fill=cor_txt, width=self.LARG - 16)
                y = c.bbox(item)[3] + 3
        c.configure(scrollregion=(0, 0, 14 + max(len(nos), 1) * self.LARG, self.altura))
        c.xview_moveto(0)


class GraficoBarras(tk.Canvas):
    def __init__(self, mestre, cor: str):
        super().__init__(mestre, bg=COR["superficie"], highlightthickness=0, height=40)
        self.cor = cor
        self.dados: list = []
        self.bind("<Configure>", lambda e: self._desenhar())

    def definir(self, dados: list) -> None:
        self.dados = dados
        self.configure(height=max(40, 27 * len(dados) + 8))
        self._desenhar()

    def _desenhar(self) -> None:
        self.delete("all")
        if not self.dados:
            self.create_text(4, 14, anchor="w", text="Sem dados.", fill=COR["tinta2"], font=FONTE["base"])
            return
        largura = max(self.winfo_width(), 240)
        maximo = max([v for _, v in self.dados] + [1])
        x0 = min(max(FONTE["pequena"].measure(str(r)) for r, _ in self.dados) + 16, int(largura * 0.6))
        comp = max(largura - x0 - 34, 20)
        for i, (rotulo, v) in enumerate(self.dados):
            y = 16 + i * 27
            self.create_text(2, y, text=str(rotulo), anchor="w", font=FONTE["pequena"], fill=COR["tinta"])
            self.create_rectangle(x0, y - 5, x0 + comp, y + 5, fill=COR["chia_suave"], width=0)
            if v:
                self.create_rectangle(x0, y - 5, x0 + comp * v / maximo, y + 5, fill=self.cor, width=0)
            self.create_text(largura - 4, y, text=str(v), anchor="e", font=FONTE["negrito"], fill=COR["tinta"])


class AreaRolavel(ttk.Frame):
    """Área com rolagem vertical (roda do mouse incluída)."""

    def __init__(self, mestre):
        super().__init__(mestre)
        self.canvas = tk.Canvas(self, bg=COR["fundo"], highlightthickness=0)
        self.barra = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.barra.set)
        self.interno = ttk.Frame(self.canvas)
        self.janela = self.canvas.create_window((0, 0), window=self.interno, anchor="nw")
        self.interno.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.janela, width=e.width))
        self.barra.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        for w in (self.canvas, self.interno):
            w.bind("<Enter>", self._ligar_roda)
            w.bind("<Leave>", self._desligar_roda)

    def _ligar_roda(self, _e=None):
        self.canvas.bind_all("<MouseWheel>", self._roda)
        self.canvas.bind_all("<Button-4>", self._roda)
        self.canvas.bind_all("<Button-5>", self._roda)

    def _desligar_roda(self, _e=None):
        for ev in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            self.canvas.unbind_all(ev)

    def _roda(self, e):
        sobe = getattr(e, "num", 0) == 4 or getattr(e, "delta", 0) > 0
        if self.interno.winfo_height() > self.canvas.winfo_height():
            self.canvas.yview_scroll(-2 if sobe else 2, "units")


def tabela(mestre, colunas: list, altura: int = 8, selecao: str = "browse") -> ttk.Treeview:
    """Treeview com barra de rolagem. colunas: [(id, título, largura, âncora)]"""
    quadro = ttk.Frame(mestre)
    arvore = ttk.Treeview(quadro, columns=[c[0] for c in colunas], show="headings", height=altura, selectmode=selecao)
    for cid, titulo, largura, ancora in colunas:
        arvore.heading(cid, text=titulo, anchor="w")
        arvore.column(cid, width=largura, anchor=ancora, stretch=True)
    barra = ttk.Scrollbar(quadro, orient="vertical", command=arvore.yview)
    arvore.configure(yscrollcommand=barra.set)
    arvore.pack(side="left", fill="both", expand=True)
    barra.pack(side="right", fill="y")
    arvore.quadro = quadro  # type: ignore[attr-defined]
    return arvore


def kpi(mestre, rotulo: str):
    q = cartao(mestre, padx=16, pady=12)
    num = ttk.Label(q, style="KpiNum.TLabel", text="—")
    num.pack(anchor="w")
    ttk.Label(q, text=rotulo, style="CartaoSuave.TLabel", wraplength=190, justify="left").pack(anchor="w")
    return q, num


# -------------------------------------------------------------------- diálogos
class Dialogo(tk.Toplevel):
    def __init__(self, mestre, titulo: str):
        super().__init__(mestre)
        self.title(titulo)
        self.configure(bg=COR["fundo"])
        self.transient(mestre.winfo_toplevel())
        self.resizable(False, False)
        self.corpo = ttk.Frame(self, padding=20)
        self.corpo.pack(fill="both", expand=True)
        self.corpo.columnconfigure(1, weight=1)
        self.bind("<Escape>", lambda e: self.destroy())
        self.erro = tk.StringVar()

    def campo(self, linha: int, rotulo: str, widget) -> None:
        ttk.Label(self.corpo, text=rotulo, style="Negrito.TLabel").grid(row=linha, column=0, sticky="nw", padx=(0, 14), pady=6)
        widget.grid(row=linha, column=1, sticky="ew", pady=6)

    def rodape(self, linha: int, rotulo_ok: str, comando) -> None:
        ttk.Label(self.corpo, textvariable=self.erro, style="Erro.TLabel", wraplength=420, justify="left").grid(
            row=linha, column=0, columnspan=2, sticky="w", pady=(6, 0))
        botoes = ttk.Frame(self.corpo)
        botoes.grid(row=linha + 1, column=0, columnspan=2, sticky="e", pady=(14, 0))
        ttk.Button(botoes, text="Cancelar", command=self.destroy).pack(side="right", padx=(8, 0))
        ttk.Button(botoes, text=rotulo_ok, style="Primario.TButton", command=comando).pack(side="right")

    def mostrar(self) -> None:
        self.update_idletasks()
        pai = self.master.winfo_toplevel()
        x = pai.winfo_rootx() + max((pai.winfo_width() - self.winfo_reqwidth()) // 2, 0)
        y = pai.winfo_rooty() + max((pai.winfo_height() - self.winfo_reqheight()) // 3, 0)
        self.geometry(f"+{x}+{y}")
        try:
            self.wait_visibility()
            self.grab_set()
        except tk.TclError:
            pass
        self.focus_set()


class DialogoCliente(Dialogo):
    def __init__(self, mestre, srv: ServicoCRM, cliente=None, ao_salvar=None, ao_abrir_existente=None):
        super().__init__(mestre, "Editar cadastro" if cliente else "Novo cliente")
        self.srv, self.cliente, self.ao_salvar, self.ao_abrir = srv, cliente, ao_salvar, ao_abrir_existente
        self.v = {k: tk.StringVar(value=(cliente[k] if cliente else "")) for k in
                  ("nome", "tipo", "documento", "telefone", "email", "cidade", "canal_preferido", "segmento")}
        if cliente is None:
            self.v["tipo"].set("PF")
            self.v["canal_preferido"].set("WhatsApp")
            self.v["segmento"].set(SEGMENTOS[0])
        else:
            self.v["documento"].set(servicos.formatar_documento(cliente["documento"]))
        self.consentimento = tk.BooleanVar(value=False)
        self.campo(0, "Nome ou razão social", ttk.Entry(self.corpo, textvariable=self.v["nome"], width=42))
        self.campo(1, "Tipo", ttk.Combobox(self.corpo, textvariable=self.v["tipo"], values=["PF", "PJ"], state="readonly", width=8))
        self.campo(2, "CPF ou CNPJ", ttk.Entry(self.corpo, textvariable=self.v["documento"]))
        self.campo(3, "Telefone", ttk.Entry(self.corpo, textvariable=self.v["telefone"]))
        self.campo(4, "E-mail", ttk.Entry(self.corpo, textvariable=self.v["email"]))
        self.campo(5, "Cidade", ttk.Entry(self.corpo, textvariable=self.v["cidade"]))
        self.campo(6, "Canal preferido", ttk.Combobox(self.corpo, textvariable=self.v["canal_preferido"], values=CANAIS, state="readonly"))
        self.campo(7, "Segmento", ttk.Combobox(self.corpo, textvariable=self.v["segmento"], values=SEGMENTOS, state="readonly"))
        linha = 8
        if cliente is None:
            ttk.Checkbutton(self.corpo, variable=self.consentimento, text="O cliente consentiu com o uso dos dados\npara atendimento e entrega (LGPD).").grid(
                row=8, column=0, columnspan=2, sticky="w", pady=6)
            linha = 9
        self.rodape(linha, "Salvar cliente", self.salvar)
        self.mostrar()

    def salvar(self) -> None:
        dados = {k: v.get() for k, v in self.v.items()}
        try:
            if self.cliente is None:
                novo = self.srv.criar_cliente(dados, self.consentimento.get())
            else:
                self.srv.editar_cliente(self.cliente["id"], dados)
                novo = self.cliente["id"]
        except ClienteDuplicado as dup:
            if messagebox.askyesno("Cliente já cadastrado", f"{dup}\n\nDeseja abrir o cadastro existente?", parent=self):
                self.destroy()
                if self.ao_abrir:
                    self.ao_abrir(dup.existente["id"])
            return
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            self.erro.set(str(e))
            return
        self.destroy()
        if self.ao_salvar:
            self.ao_salvar(novo)


class DialogoTicket(Dialogo):
    def __init__(self, mestre, srv: ServicoCRM, ao_criar=None):
        super().__init__(mestre, "Novo ticket")
        self.srv, self.ao_criar = srv, ao_criar
        self.clientes = [c for c in srv.listar_clientes() if not c["anonimizado"]]
        self.rotulos = {f"{c['nome']} (#{c['id']})": c["id"] for c in self.clientes}
        self.var_cliente = tk.StringVar(value=next(iter(self.rotulos), ""))
        self.var_canal = tk.StringVar(value="WhatsApp")
        self.var_cat = tk.StringVar(value="Dúvida")
        self.var_pri = tk.StringVar(value="Média")
        self.var_ped = tk.StringVar(value="Nenhum")
        self.var_ass = tk.StringVar()
        cb = ttk.Combobox(self.corpo, textvariable=self.var_cliente, values=list(self.rotulos), state="readonly", width=40)
        cb.bind("<<ComboboxSelected>>", lambda e: self._atualizar_pedidos())
        self.campo(0, "Cliente", cb)
        self.campo(1, "Canal de origem", ttk.Combobox(self.corpo, textvariable=self.var_canal, values=CANAIS, state="readonly"))
        self.campo(2, "Categoria", ttk.Combobox(self.corpo, textvariable=self.var_cat, values=CATEGORIAS, state="readonly"))
        self.campo(3, "Prioridade", ttk.Combobox(self.corpo, textvariable=self.var_pri, values=list(PRIORIDADES.values()), state="readonly"))
        self.cb_ped = ttk.Combobox(self.corpo, textvariable=self.var_ped, state="readonly")
        self.campo(4, "Pedido relacionado", self.cb_ped)
        self.campo(5, "Assunto", ttk.Entry(self.corpo, textvariable=self.var_ass))
        self.texto = tk.Text(self.corpo, height=5, width=40, wrap="word", relief="solid", bd=1, font=FONTE["base"])
        self.campo(6, "Mensagem do cliente", self.texto)
        self.rodape(7, "Abrir ticket", self.salvar)
        self._atualizar_pedidos()
        self.mostrar()

    def _atualizar_pedidos(self) -> None:
        cid = self.rotulos.get(self.var_cliente.get())
        self.pedidos = {"Nenhum": None}
        if cid:
            for p in self.srv.pedidos_do_cliente(cid):
                self.pedidos[f"{p['codigo']} – {p['itens']}"] = p["id"]
        self.cb_ped.configure(values=list(self.pedidos))
        self.var_ped.set("Nenhum")

    def salvar(self) -> None:
        pri = {v: k for k, v in PRIORIDADES.items()}[self.var_pri.get()]
        try:
            tid = self.srv.criar_ticket(self.rotulos[self.var_cliente.get()], self.var_canal.get(), self.var_cat.get(), pri,
                                        self.var_ass.get(), self.texto.get("1.0", "end"), self.pedidos.get(self.var_ped.get()))
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            self.erro.set(str(e))
            return
        self.destroy()
        if self.ao_criar:
            self.ao_criar(tid)


class DialogoEtapa(Dialogo):
    def __init__(self, mestre, srv: ServicoCRM, lote_inicial: str = "", ao_salvar=None):
        super().__init__(mestre, "Registrar etapa do lote")
        self.srv, self.ao_salvar = srv, ao_salvar
        lotes = [l["codigo"] for l in srv.listar_lotes()]
        self.v = {k: tk.StringVar() for k in ("lote", "tipo", "titulo", "subtitulo", "responsavel", "entrada", "saida", "medidas", "data")}
        self.v["lote"].set(lote_inicial or (lotes[0] if lotes else ""))
        self.v["tipo"].set(list(TIPOS_ETAPA.values())[2])
        self.v["data"].set(time.strftime("%Y-%m-%d"))
        self.campo(0, "Lote", ttk.Combobox(self.corpo, textvariable=self.v["lote"], values=lotes, state="readonly"))
        self.campo(1, "Tipo", ttk.Combobox(self.corpo, textvariable=self.v["tipo"], values=list(TIPOS_ETAPA.values()), state="readonly"))
        self.campo(2, "Título da etapa", ttk.Entry(self.corpo, textvariable=self.v["titulo"], width=36))
        self.campo(3, "Local ou detalhe", ttk.Entry(self.corpo, textvariable=self.v["subtitulo"]))
        self.campo(4, "Responsável", ttk.Entry(self.corpo, textvariable=self.v["responsavel"]))
        self.campo(5, "Entrada (kg)", ttk.Entry(self.corpo, textvariable=self.v["entrada"], width=12))
        self.campo(6, "Saída (kg)", ttk.Entry(self.corpo, textvariable=self.v["saida"], width=12))
        self.campo(7, "Outras medidas", ttk.Entry(self.corpo, textvariable=self.v["medidas"]))
        self.campo(8, "Data (AAAA-MM-DD)", ttk.Entry(self.corpo, textvariable=self.v["data"], width=14))
        ttk.Label(self.corpo, text="Com entrada e saída, o sistema faz o balanço de massa e alerta perdas acima de "
                  f"{servicos.TOLERANCIA_PERDA_PCT:g}%.", style="Suave.TLabel", wraplength=420, justify="left").grid(
            row=9, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.rodape(10, "Registrar etapa", self.salvar)
        self.mostrar()

    def _numero(self, nome: str):
        texto = self.v[nome].get().strip().replace(",", ".")
        if not texto:
            return None
        try:
            return float(texto)
        except ValueError:
            raise ErroValidacao(f"Quantidade de {nome} inválida.")

    def salvar(self) -> None:
        tipo = {v: k for k, v in TIPOS_ETAPA.items()}[self.v["tipo"].get()]
        try:
            alerta = self.srv.registrar_etapa(self.v["lote"].get(), tipo, self.v["titulo"].get(), self.v["subtitulo"].get(),
                                              self.v["responsavel"].get(), self._numero("entrada"), self._numero("saida"),
                                              self.v["medidas"].get(), self.v["data"].get().strip())
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            self.erro.set(str(e))
            return
        self.destroy()
        if alerta:
            messagebox.showwarning("Balanço de massa", f"Etapa registrada, mas há um alerta:\n{alerta}.", parent=self.master)
        if self.ao_salvar:
            self.ao_salvar(self.v["lote"].get())


class DialogoSenha(Dialogo):
    def __init__(self, mestre, srv: ServicoCRM, ao_alterar=None):
        super().__init__(mestre, "Trocar minha senha")
        self.srv, self.ao_alterar = srv, ao_alterar
        self.atual, self.nova, self.conf = tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.campo(0, "Senha atual", ttk.Entry(self.corpo, textvariable=self.atual, show="•", width=30))
        self.campo(1, "Nova senha", ttk.Entry(self.corpo, textvariable=self.nova, show="•"))
        self.campo(2, "Repita a nova senha", ttk.Entry(self.corpo, textvariable=self.conf, show="•"))
        ttk.Label(self.corpo, text="Mínimo de 12 caracteres, ao menos 3 tipos (maiúsculas, minúsculas,\nnúmeros, símbolos) e não constar em bases de senhas vazadas.",
                  style="Suave.TLabel", justify="left").grid(row=3, column=0, columnspan=2, sticky="w")
        self.rodape(4, "Salvar senha", self.salvar)
        self.mostrar()

    def salvar(self) -> None:
        if self.nova.get() != self.conf.get():
            self.erro.set("A confirmação não confere com a nova senha.")
            return
        try:
            self.srv.alterar_minha_senha(self.atual.get(), self.nova.get())
        except (ErroValidacao, seguranca.PermissaoNegada, seguranca.ErroAutenticacao) as e:
            self.erro.set(str(e))
            return
        pai = self.master
        self.destroy()
        messagebox.showinfo("Senha alterada", "Sua senha foi alterada e todas as sessões ativas foram encerradas.\nFaça login novamente.", parent=pai)
        if self.ao_alterar:
            self.ao_alterar()


class DialogoInteracao(Dialogo):
    def __init__(self, mestre, srv: ServicoCRM, cliente_id: int, ao_salvar=None):
        super().__init__(mestre, "Registrar contato")
        self.srv, self.cliente_id, self.ao_salvar = srv, cliente_id, ao_salvar
        self.var_canal = tk.StringVar(value="Telefone")
        self.campo(0, "Canal", ttk.Combobox(self.corpo, textvariable=self.var_canal, values=CANAIS, state="readonly"))
        self.texto = tk.Text(self.corpo, height=5, width=44, wrap="word", relief="solid", bd=1, font=FONTE["base"])
        self.campo(1, "O que foi conversado", self.texto)
        self.rodape(2, "Salvar contato", self.salvar)
        self.mostrar()

    def salvar(self) -> None:
        try:
            self.srv.registrar_interacao(self.cliente_id, self.var_canal.get(), self.texto.get("1.0", "end"))
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            self.erro.set(str(e))
            return
        self.destroy()
        if self.ao_salvar:
            self.ao_salvar()


class JanelaCadeia(tk.Toplevel):
    def __init__(self, mestre, titulo: str, subtitulo: str, nos: list):
        super().__init__(mestre)
        self.title(titulo)
        self.configure(bg=COR["fundo"])
        self.transient(mestre.winfo_toplevel())
        self.bind("<Escape>", lambda e: self.destroy())
        corpo = ttk.Frame(self, padding=18)
        corpo.pack(fill="both", expand=True)
        ttk.Label(corpo, text=titulo, style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(corpo, text=subtitulo, style="Suave.TLabel").pack(anchor="w", pady=(2, 10))
        q = cartao(corpo, padx=10, pady=8)
        q.pack(fill="both", expand=True)
        cadeia = CadeiaCanvas(q)
        cadeia.pack(fill="both", expand=True)
        cadeia.mostrar(nos)
        ttk.Button(corpo, text="Fechar", command=self.destroy).pack(anchor="e", pady=(12, 0))
        self.geometry(f"{min(1000, max(560, 60 + CadeiaCanvas.LARG * len(nos)))}x420")


# ------------------------------------------------------------------------ abas
class Aba(ttk.Frame):
    def __init__(self, nb, app):
        super().__init__(nb, padding=(18, 16))
        self.app = app
        self.srv: ServicoCRM = app.srv

    def atualizar(self) -> None:  # pragma: no cover - implementado nas abas
        pass


def _cabecalho(mestre, titulo: str, subtitulo: str):
    topo = ttk.Frame(mestre)
    topo.pack(fill="x", pady=(0, 12))
    texto = ttk.Frame(topo)
    texto.pack(side="left", fill="x", expand=True)
    ttk.Label(texto, text=titulo, style="Titulo.TLabel").pack(anchor="w")
    ttk.Label(texto, text=subtitulo, style="Suave.TLabel", wraplength=760, justify="left").pack(anchor="w", pady=(2, 0))
    return topo


class AbaPainel(Aba):
    def __init__(self, nb, app):
        super().__init__(nb, app)
        self.area = AreaRolavel(self)
        self.area.pack(fill="both", expand=True)
        corpo = self.area.interno
        _cabecalho(corpo, "Da colmeia e da planta à mesa",
                   "Escolha um lote para ver o caminho completo, da origem no campo ou no apiário até a avaliação do cliente.")
        linha = ttk.Frame(corpo)
        linha.pack(fill="x")
        ttk.Label(linha, text="Lote", style="Negrito.TLabel").pack(side="left")
        self.var_lote = tk.StringVar()
        self.combo = ttk.Combobox(linha, textvariable=self.var_lote, state="readonly", width=44)
        self.combo.pack(side="left", padx=10)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._mostrar_lote())
        self.lbl_resumo = ttk.Label(linha, style="Suave.TLabel")
        self.lbl_resumo.pack(side="left", padx=6)
        q = cartao(corpo, padx=10, pady=8)
        q.pack(fill="x", pady=(10, 14))
        self.cadeia = CadeiaCanvas(q, altura=215)
        self.cadeia.pack(fill="x")
        faixa = ttk.Frame(corpo)
        faixa.pack(fill="x", pady=(0, 14))
        self.kpis = {}
        for i, (chave, rotulo) in enumerate((("abertos", "tickets abertos"), ("atrasados", "tickets fora do prazo"),
                                             ("primeira", "tempo médio da primeira resposta"), ("csat", "satisfação média dos clientes"))):
            q, num = kpi(faixa, rotulo)
            q.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7))
            faixa.columnconfigure(i, weight=1, uniform="k")
            self.kpis[chave] = num
        grade = ttk.Frame(corpo)
        grade.pack(fill="x")
        self.graficos = {}
        for i, (chave, titulo, cor) in enumerate((("canal", "Tickets por canal", COR["chia"]), ("status", "Tickets por status", COR["mel"]),
                                                  ("notas", "Notas dos clientes", COR["mel"]), ("lotes", "Reclamações por lote", COR["ruim"]))):
            q = cartao(grade, padx=14, pady=12)
            q.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 7, 0 if i == 3 else 7))
            grade.columnconfigure(i, weight=1, uniform="g")
            ttk.Label(q, text=titulo, style="Subtitulo.TLabel").pack(anchor="w", pady=(0, 8))
            g = GraficoBarras(q, cor)
            g.pack(fill="x")
            self.graficos[chave] = g

    def atualizar(self) -> None:
        lotes = self.srv.listar_lotes(apenas_venda=True)
        self.mapa = {f"{l['codigo']} – {l['nome']}": l["codigo"] for l in lotes}
        self.combo.configure(values=list(self.mapa))
        if self.var_lote.get() not in self.mapa:
            preferido = next((k for k in self.mapa if k.startswith("LB-1026-A")), next(iter(self.mapa), ""))
            self.var_lote.set(preferido)
        self._mostrar_lote()
        ind = self.srv.indicadores()
        self.kpis["abertos"].configure(text=str(ind["abertos"]))
        self.kpis["atrasados"].configure(text=str(ind["atrasados"]), foreground=COR["ruim"] if ind["atrasados"] else COR["tinta"])
        self.kpis["primeira"].configure(text=servicos.formatar_duracao(ind["primeira_resposta"]) if ind["primeira_resposta"] else "—")
        self.kpis["csat"].configure(text=f"{ind['satisfacao']:.1f} de 5".replace(".", ",") if ind["satisfacao"] is not None else "—")
        self.graficos["canal"].definir(ind["por_canal"])
        self.graficos["status"].definir([(r.replace("Aguardando ", "Aguard. "), v) for r, v in ind["por_status"]])
        self.graficos["notas"].definir(ind["notas"])
        self.graficos["lotes"].definir(ind["reclamacoes_por_lote"])

    def _mostrar_lote(self) -> None:
        codigo = self.mapa.get(self.var_lote.get())
        if not codigo:
            self.cadeia.mostrar([])
            self.lbl_resumo.configure(text="")
            return
        self.cadeia.mostrar(self.srv.cadeia_do_lote(codigo))
        r = self.srv.resumo_lote(codigo)
        media = f", média {r['media']:.1f}".replace(".", ",") if r["media"] is not None else ""
        self.lbl_resumo.configure(text=f"{r['pedidos']} pedido(s), {r['avaliacoes']} avaliação(ões){media}, {r['tickets']} ticket(s)")


class AbaTickets(Aba):
    COLUNAS = [("protocolo", "Protocolo", 96, "w"), ("assunto", "Assunto", 300, "w"), ("cliente", "Cliente", 170, "w"),
               ("canal", "Canal", 90, "w"), ("pri", "Prior.", 70, "w"), ("status", "Status", 180, "w"), ("prazo", "Prazo", 150, "w")]

    def __init__(self, nb, app):
        super().__init__(nb, app)
        topo = _cabecalho(self, "Tickets de atendimento",
                          "Solicitações de todos os canais em um só lugar. Selecione um ticket para responder, mudar o status e ver o lote envolvido.")
        self.btn_novo = ttk.Button(topo, text="Novo ticket", style="Primario.TButton", command=self.novo)
        self.btn_novo.pack(side="right", anchor="s")
        filtros = ttk.Frame(self)
        filtros.pack(fill="x", pady=(0, 10))
        self.v_busca, self.v_cat, self.v_pri, self.v_st = tk.StringVar(), tk.StringVar(), tk.StringVar(), tk.StringVar()
        self.v_enc = tk.BooleanVar(value=False)
        e = ttk.Entry(filtros, textvariable=self.v_busca, width=30)
        e.pack(side="left")
        ttk.Label(filtros, text="  Busca por assunto, protocolo ou cliente", style="Suave.TLabel").pack(side="left", padx=(0, 12))
        self.v_busca.trace_add("write", lambda *a: self.atualizar())
        for var, valores, vazio in ((self.v_cat, CATEGORIAS, "Todas as categorias"), (self.v_pri, list(PRIORIDADES.values()), "Todas as prioridades"),
                                    (self.v_st, list(STATUS.values()), "Todos os status")):
            cb = ttk.Combobox(filtros, textvariable=var, values=[vazio] + valores, state="readonly", width=20)
            cb.set(vazio)
            cb.pack(side="left", padx=(0, 8))
            cb.bind("<<ComboboxSelected>>", lambda ev: self.atualizar())
        ttk.Checkbutton(filtros, text="Ocultar encerrados", variable=self.v_enc, command=self.atualizar).pack(side="left", padx=8)

        painel = ttk.PanedWindow(self, orient="vertical")
        painel.pack(fill="both", expand=True)
        topo_lista = ttk.Frame(painel)
        self.tree = tabela(topo_lista, self.COLUNAS, altura=6)
        self.tree.quadro.pack(fill="both", expand=True)
        self.tree.tag_configure("atrasado", foreground=COR["ruim"])
        self.tree.tag_configure("alerta", foreground=COR["aviso"])
        self.tree.bind("<<TreeviewSelect>>", lambda e: self._mostrar())
        painel.add(topo_lista, weight=1)
        self.det = cartao(painel, padx=16, pady=12)
        painel.add(self.det, weight=3)
        self._montar_detalhe()
        self._carregando = False

    def _montar_detalhe(self) -> None:
        d = self.det
        d.columnconfigure(1, weight=1)
        d.rowconfigure(0, weight=1)
        esq = tk.Frame(d, bg=COR["superficie"])
        esq.grid(row=0, column=0, sticky="nsw", padx=(0, 22))
        dir_ = tk.Frame(d, bg=COR["superficie"])
        dir_.grid(row=0, column=1, sticky="nsew")
        # coluna da esquerda: dados, status e atalhos
        self.lbl_assunto = ttk.Label(esq, style="Subtitulo.TLabel", wraplength=400, justify="left", text="Selecione um ticket")
        self.lbl_assunto.pack(anchor="w")
        self.lbl_chips = ttk.Label(esq, style="CartaoSuave.TLabel", wraplength=400, justify="left")
        self.lbl_chips.pack(anchor="w", pady=(2, 6))
        info = tk.Frame(esq, bg=COR["superficie"])
        info.pack(fill="x")
        info.columnconfigure(1, weight=1)
        self.info = {}
        for i, rot in enumerate(("Cliente", "Responsável", "Prazo", "Aberto")):
            ttk.Label(info, text=rot, style="CartaoSuave.TLabel").grid(row=i, column=0, sticky="w", pady=2, padx=(0, 14))
        self.info["cliente"] = ttk.Label(info, style="Cartao.TLabel")
        self.info["cliente"].grid(row=0, column=1, sticky="w")
        self.v_resp = tk.StringVar()
        self.cb_resp = ttk.Combobox(info, textvariable=self.v_resp, values=["Sem responsável"] + RESPONSAVEIS, state="readonly", width=18)
        self.cb_resp.grid(row=1, column=1, sticky="w", pady=2)
        self.cb_resp.bind("<<ComboboxSelected>>", lambda e: self._atribuir())
        self.info["prazo"] = ttk.Label(info, style="Cartao.TLabel", font=FONTE["negrito"])
        self.info["prazo"].grid(row=2, column=1, sticky="w")
        self.info["aberto"] = ttk.Label(info, style="Cartao.TLabel")
        self.info["aberto"].grid(row=3, column=1, sticky="w")
        ttk.Label(esq, text="Mudar status", style="CartaoNegrito.TLabel").pack(anchor="w", pady=(10, 4))
        self.quadro_status = tk.Frame(esq, bg=COR["superficie"])
        self.quadro_status.pack(fill="x")
        self.quadro_status.columnconfigure(0, weight=1, uniform="st")
        self.quadro_status.columnconfigure(1, weight=1, uniform="st")
        extra = tk.Frame(esq, bg=COR["superficie"])
        extra.pack(fill="x", pady=(10, 0))
        self.btn_rastreio = ttk.Button(extra, text="Ver rastreio do lote", command=self._rastreio)
        self.btn_rastreio.pack(side="left")
        self.btn_cliente = ttk.Button(extra, text="Abrir cliente", command=self._abrir_cliente)
        self.btn_cliente.pack(side="left", padx=6)
        self.lbl_somente = ttk.Label(esq, style="CartaoSuave.TLabel", wraplength=400)
        self.lbl_somente.pack(anchor="w", pady=(8, 0))
        # coluna da direita: conversa e resposta
        ttk.Label(dir_, text="Histórico", style="CartaoNegrito.TLabel").pack(anchor="w", pady=(0, 4))
        botoes = tk.Frame(dir_, bg=COR["superficie"])
        botoes.pack(side="bottom", fill="x", pady=(8, 0))
        self.btn_enviar = ttk.Button(botoes, text="Enviar resposta", style="Primario.TButton", command=self._responder)
        self.btn_enviar.pack(side="left")
        self.btn_nota = ttk.Button(botoes, text="Salvar nota interna", command=self._nota)
        self.btn_nota.pack(side="left", padx=6)
        self.btn_escalar = ttk.Button(botoes, text="Escalonar ao gestor", command=self._escalar)
        self.btn_escalar.pack(side="left")
        self.resposta = tk.Text(dir_, height=3, width=10, wrap="word", relief="solid", bd=1, font=FONTE["base"])
        self.resposta.pack(side="bottom", fill="x")
        ttk.Label(dir_, text="Responder ao cliente ou registrar nota interna", style="CartaoSuave.TLabel").pack(side="bottom", anchor="w", pady=(8, 3))
        self.tl = tk.Text(dir_, height=4, width=10, wrap="word", state="disabled", relief="flat", bg=COR["fundo"], font=FONTE["base"], padx=8, pady=6)
        self.tl.pack(fill="both", expand=True)
        self.tl.tag_configure("quem", font=FONTE["pequena_negrito"], foreground=COR["tinta2"])
        self.tl.tag_configure("nota", background=COR["mel_suave"])
        self.tl.tag_configure("sistema", foreground=COR["tinta2"])
        self.tl.tag_configure("cliente", foreground=COR["ok"])

    # ---- lista
    def _filtro(self, var, vazio, mapa=None):
        v = var.get()
        if not v or v == vazio:
            return ""
        return mapa[v] if mapa else v

    def atualizar(self) -> None:
        self.btn_novo.configure(state="normal" if self.srv.pode("tickets.criar") else "disabled")
        sel = self.tree.selection()
        lembrar = sel[0] if sel else None
        pri = {v: k for k, v in PRIORIDADES.items()}
        st = {v: k for k, v in STATUS.items()}
        tickets = self.srv.listar_tickets(self.v_busca.get(), self._filtro(self.v_cat, "Todas as categorias"),
                                          self._filtro(self.v_pri, "Todas as prioridades", pri),
                                          self._filtro(self.v_st, "Todos os status", st), self.v_enc.get())
        self._carregando = True
        self.tree.delete(*self.tree.get_children())
        for t in tickets:
            situacao, texto = servicos.calcular_sla(t)
            self.tree.insert("", "end", iid=str(t["id"]), tags=(situacao,) if situacao != "ok" else (),
                             values=(t["protocolo"], t["assunto"], t["cliente_nome"], t["canal"], PRIORIDADES[t["prioridade"]],
                                     STATUS[t["status"]], texto))
        if lembrar and self.tree.exists(lembrar):
            self.tree.selection_set(lembrar)
        elif tickets:
            self.tree.selection_set(str(tickets[0]["id"]))
        self._carregando = False
        self._mostrar()

    def selecionado(self):
        sel = self.tree.selection()
        return int(sel[0]) if sel else None

    # ---- detalhe
    def _mostrar(self) -> None:
        if self._carregando:
            return
        tid = self.selecionado()
        for w in self.quadro_status.winfo_children():
            w.destroy()
        self.tl.configure(state="normal")
        self.tl.delete("1.0", "end")
        if tid is None:
            self.lbl_assunto.configure(text="Nenhum ticket encontrado")
            self.lbl_chips.configure(text="")
            for k in ("cliente", "prazo", "aberto"):
                self.info[k].configure(text="")
            self.tl.configure(state="disabled")
            for b in (self.btn_enviar, self.btn_nota, self.btn_escalar, self.btn_rastreio, self.btn_cliente):
                b.state(["disabled"])
            self.cb_resp.state(["disabled"])
            return
        t = self.srv.obter_ticket(tid)
        editavel = self.srv.pode_editar_ticket(tid)
        self.lbl_assunto.configure(text=f"{t['protocolo']}  {t['assunto']}")
        chips = [STATUS[t["status"]], "Prioridade " + PRIORIDADES[t["prioridade"]].lower(), t["categoria"], t["canal"]]
        if t["escalonado"]:
            chips.append("Escalonado ao gestor")
        self.lbl_chips.configure(text="  |  ".join(chips))
        self.info["cliente"].configure(text=t["cliente_nome"])
        self.v_resp.set(t["responsavel"] or "Sem responsável")
        situacao, texto = servicos.calcular_sla(t)
        self.info["prazo"].configure(text=texto, foreground={"ok": COR["ok"], "alerta": COR["aviso"], "atrasado": COR["ruim"]}[situacao])
        self.info["aberto"].configure(text=servicos.formatar_data_hora(t["criado_em"]))
        botoes_status = [(STATUS[s], lambda s=s: self._mudar(s)) for s in self.srv.proximos_status(tid)]
        if t["status"] in ("resolvido", "encerrado"):
            botoes_status.append(("Reabrir", self._reabrir))
        for i, (rotulo, comando) in enumerate(botoes_status):
            ttk.Button(self.quadro_status, text=rotulo, style="Pequeno.TButton", command=comando,
                       state="normal" if editavel else "disabled").grid(row=i // 2, column=i % 2, sticky="ew", padx=(0, 6), pady=2)
        if not botoes_status:
            ttk.Label(self.quadro_status, text="Sem próximas etapas.", style="CartaoSuave.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        for ev in self.srv.eventos_ticket(tid):
            etiqueta = {"nota": "nota", "sistema": "sistema", "status": "sistema", "cliente": "cliente"}.get(ev["tipo"], "")
            rotulo = {"nota": "Nota interna · ", "resposta": "Resposta · "}.get(ev["tipo"], "")
            self.tl.insert("end", f"{rotulo}{ev['autor']}, {servicos.formatar_data_hora(ev['criado_em'])}\n", ("quem",))
            self.tl.insert("end", ev["texto"] + "\n\n", (etiqueta,) if etiqueta else ())
        self.tl.configure(state="disabled")
        self.tl.see("end")
        estado = ["!disabled"] if editavel else ["disabled"]
        for b in (self.btn_enviar, self.btn_nota):
            b.state(estado)
        self.btn_escalar.state(["!disabled"] if editavel and not t["escalonado"] and self.srv.sessao.perfil != "gestor"
                               and t["status"] not in ("resolvido", "encerrado") else ["disabled"])
        self.cb_resp.state(["!disabled", "readonly"] if editavel else ["disabled"])
        self.btn_rastreio.state(["!disabled"] if t["pedido_id"] and self.srv.pode("rastreio.ver") else ["disabled"])
        self.btn_cliente.state(["!disabled"] if self.srv.pode("clientes.ver") else ["disabled"])
        self.lbl_somente.configure(text="" if editavel else f"O perfil {self.srv.sessao.perfil_nome} só pode consultar este ticket.")

    def _executar(self, funcao, *args) -> bool:
        try:
            funcao(*args)
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return False
        self.app.atualizar_tudo()
        return True

    def _mudar(self, status: str) -> None:
        self._executar(self.srv.mudar_status, self.selecionado(), status)

    def _reabrir(self) -> None:
        self._executar(self.srv.reabrir_ticket, self.selecionado())

    def _atribuir(self) -> None:
        v = self.v_resp.get()
        self._executar(self.srv.atribuir, self.selecionado(), "" if v == "Sem responsável" else v)

    def _responder(self) -> None:
        if self._executar(self.srv.responder, self.selecionado(), self.resposta.get("1.0", "end")):
            self.resposta.delete("1.0", "end")

    def _nota(self) -> None:
        if self._executar(self.srv.nota_interna, self.selecionado(), self.resposta.get("1.0", "end")):
            self.resposta.delete("1.0", "end")

    def _escalar(self) -> None:
        self._executar(self.srv.escalonar, self.selecionado())

    def _rastreio(self) -> None:
        t = self.srv.obter_ticket(self.selecionado())
        JanelaCadeia(self, f"Rastreio do pedido P-{t['pedido_id']}", f"Do lote {t['lote']} até a mesa do cliente",
                     self.srv.cadeia_do_pedido(t["pedido_id"]))

    def _abrir_cliente(self) -> None:
        t = self.srv.obter_ticket(self.selecionado())
        self.app.ir_para_cliente(t["cliente_id"])

    def novo(self) -> None:
        DialogoTicket(self, self.srv, ao_criar=lambda tid: (self.app.atualizar_tudo(), self.tree.selection_set(str(tid))))

    def selecionar(self, ticket_id: int) -> None:
        if self.tree.exists(str(ticket_id)):
            self.tree.selection_set(str(ticket_id))
            self.tree.see(str(ticket_id))


class AbaClientes(Aba):
    def __init__(self, nb, app):
        super().__init__(nb, app)
        topo = _cabecalho(self, "Clientes", "Um cadastro único por cliente, com o histórico de todos os canais e das compras.")
        self.btn_novo = ttk.Button(topo, text="Novo cliente", style="Primario.TButton", command=self.novo)
        self.btn_novo.pack(side="right", anchor="s")
        painel = ttk.PanedWindow(self, orient="horizontal")
        painel.pack(fill="both", expand=True)
        esq = ttk.Frame(painel)
        filtros = ttk.Frame(esq)
        filtros.pack(fill="x", pady=(0, 8))
        self.v_busca, self.v_seg = tk.StringVar(), tk.StringVar(value="Todos os segmentos")
        ttk.Entry(filtros, textvariable=self.v_busca).pack(fill="x")
        ttk.Label(filtros, text="Nome, CPF/CNPJ, e-mail ou telefone", style="Suave.TLabel").pack(anchor="w", pady=(2, 6))
        cb = ttk.Combobox(filtros, textvariable=self.v_seg, values=["Todos os segmentos"] + SEGMENTOS, state="readonly")
        cb.pack(fill="x")
        cb.bind("<<ComboboxSelected>>", lambda e: self.atualizar())
        self.v_busca.trace_add("write", lambda *a: self.atualizar())
        self.lista = tabela(esq, [("nome", "Cliente", 160, "w"), ("seg", "Segmento", 190, "w")], altura=16)
        self.lista.quadro.pack(fill="both", expand=True)
        self.lista.bind("<<TreeviewSelect>>", lambda e: self._mostrar())
        painel.add(esq, weight=3)
        self.dir = cartao(painel, padx=16, pady=14)
        painel.add(self.dir, weight=5)
        self._montar_detalhe()
        self._carregando = False

    def _montar_detalhe(self) -> None:
        d = self.dir
        self.lbl_nome = ttk.Label(d, style="Subtitulo.TLabel", text="Selecione um cliente")
        self.lbl_nome.pack(anchor="w")
        self.lbl_seg = ttk.Label(d, style="CartaoSuave.TLabel")
        self.lbl_seg.pack(anchor="w", pady=(0, 6))
        self.nb = ttk.Notebook(d, style="Interno.TNotebook")
        self.nb.pack(fill="both", expand=True)
        # resumo
        r = tk.Frame(self.nb, bg=COR["superficie"], padx=10, pady=10)
        self.nb.add(r, text="Resumo")
        grade = tk.Frame(r, bg=COR["superficie"])
        grade.pack(fill="x")
        self.campos = {}
        for i, (k, rot) in enumerate((("doc", "Documento"), ("tel", "Telefone"), ("email", "E-mail"), ("cidade", "Cidade"),
                                      ("canal", "Canal preferido"), ("consent", "Consentimento"))):
            ttk.Label(grade, text=rot, style="CartaoSuave.TLabel").grid(row=i, column=0, sticky="w", padx=(0, 16), pady=2)
            self.campos[k] = ttk.Label(grade, style="Cartao.TLabel")
            self.campos[k].grid(row=i, column=1, sticky="w")
        ttk.Label(r, text="Anotações internas (só a equipe vê)", style="CartaoNegrito.TLabel").pack(anchor="w", pady=(12, 4))
        self.notas = tk.Text(r, height=5, wrap="word", state="disabled", relief="flat", bg=COR["fundo"], font=FONTE["base"], padx=8, pady=6)
        self.notas.pack(fill="x")
        self.notas.tag_configure("quem", font=FONTE["pequena_negrito"], foreground=COR["tinta2"])
        self.nova_nota = tk.Text(r, height=2, wrap="word", relief="solid", bd=1, font=FONTE["base"])
        self.nova_nota.pack(fill="x", pady=(8, 0))
        linha = tk.Frame(r, bg=COR["superficie"])
        linha.pack(fill="x", pady=(8, 0))
        self.btn_nota = ttk.Button(linha, text="Salvar anotação", command=self._anotar)
        self.btn_nota.pack(side="left")
        self.btn_editar = ttk.Button(linha, text="Editar cadastro", command=self._editar)
        self.btn_editar.pack(side="left", padx=6)
        self.btn_anon = ttk.Button(linha, text="Anonimizar (LGPD)", style="Perigo.TButton", command=self._anonimizar)
        self.btn_anon.pack(side="left")
        # histórico
        h = tk.Frame(self.nb, bg=COR["superficie"], padx=10, pady=10)
        self.nb.add(h, text="Histórico")
        barra = tk.Frame(h, bg=COR["superficie"])
        barra.pack(fill="x", pady=(0, 8))
        ttk.Label(barra, text="Todos os canais, compras, tickets e avaliações em ordem cronológica.", style="CartaoSuave.TLabel").pack(side="left")
        self.btn_contato = ttk.Button(barra, text="Registrar contato", command=self._contato)
        self.btn_contato.pack(side="right")
        self.hist = tabela(h, [("quando", "Quando", 100, "w"), ("origem", "Origem", 90, "w"), ("texto", "O que aconteceu", 400, "w")], altura=10)
        self.hist.quadro.pack(fill="both", expand=True)
        # compras
        c = tk.Frame(self.nb, bg=COR["superficie"], padx=10, pady=10)
        self.nb.add(c, text="Compras")
        self.compras = tabela(c, [("pedido", "Pedido", 70, "w"), ("data", "Data", 90, "w"), ("itens", "Itens", 250, "w"),
                                  ("valor", "Valor", 90, "e"), ("lote", "Lote", 100, "w"), ("sit", "Situação", 90, "w")], altura=9)
        self.compras.quadro.pack(fill="both", expand=True)
        ttk.Button(c, text="Ver rastreio do pedido", command=self._rastreio).pack(anchor="e", pady=(8, 0))

    def atualizar(self, selecionar: int | None = None) -> None:
        self.btn_novo.configure(state="normal" if self.srv.pode("clientes.editar") else "disabled")
        seg = self.v_seg.get()
        clientes = self.srv.listar_clientes(self.v_busca.get(), "" if seg.startswith("Todos") else seg)
        sel = self.lista.selection()
        lembrar = str(selecionar) if selecionar else (sel[0] if sel else None)
        self._carregando = True
        self.lista.delete(*self.lista.get_children())
        for c in clientes:
            self.lista.insert("", "end", iid=str(c["id"]), values=(c["nome"], c["segmento"]))
        if lembrar and self.lista.exists(lembrar):
            self.lista.selection_set(lembrar)
            self.lista.see(lembrar)
        elif clientes:
            self.lista.selection_set(str(clientes[0]["id"]))
        self._carregando = False
        self._mostrar()

    def selecionado(self):
        sel = self.lista.selection()
        return int(sel[0]) if sel else None

    def selecionar(self, cliente_id: int) -> None:
        self.v_busca.set("")
        self.v_seg.set("Todos os segmentos")
        self.atualizar(selecionar=cliente_id)

    def _mostrar(self) -> None:
        if self._carregando:
            return
        cid = self.selecionado()
        self.hist.delete(*self.hist.get_children())
        self.compras.delete(*self.compras.get_children())
        self.notas.configure(state="normal")
        self.notas.delete("1.0", "end")
        if cid is None:
            self.lbl_nome.configure(text="Nenhum cliente encontrado")
            self.lbl_seg.configure(text="")
            self.notas.configure(state="disabled")
            return
        c = self.srv.obter_cliente(cid)
        self.lbl_nome.configure(text=c["nome"])
        self.lbl_seg.configure(text=c["segmento"] + ("  |  dados anonimizados" if c["anonimizado"] else ""))
        self.campos["doc"].configure(text=f"{c['tipo']}  {servicos.formatar_documento(c['documento'])}" if c["documento"] else "—")
        self.campos["tel"].configure(text=c["telefone"] or "—")
        self.campos["email"].configure(text=c["email"] or "—")
        self.campos["cidade"].configure(text=c["cidade"] or "—")
        self.campos["canal"].configure(text=c["canal_preferido"])
        self.campos["consent"].configure(text=("Registrado em " + servicos.formatar_data(c["consentimento_em"]) + " (LGPD)")
                                         if c["consentimento_em"] else "Sem consentimento registrado")
        notas = self.srv.anotacoes(cid)
        if not notas:
            self.notas.insert("end", "Nenhuma anotação.")
        for n in notas:
            self.notas.insert("end", f"{n['autor']}, {servicos.formatar_data_hora(n['criado_em'])}\n", ("quem",))
            self.notas.insert("end", n["texto"] + "\n\n")
        self.notas.configure(state="disabled")
        for e in self.srv.linha_do_tempo(cid):
            self.hist.insert("", "end", values=(servicos.formatar_data_hora(e["quando"]), e["origem"], e["texto"]))
        for p in self.srv.pedidos_do_cliente(cid):
            self.compras.insert("", "end", iid=str(p["id"]), values=(p["codigo"], servicos.formatar_data(p["criado_em"]), p["itens"],
                                                                      servicos.moeda(p["valor"]), p["lote"], p["status"]))
        livre = not c["anonimizado"]
        self.btn_editar.state(["!disabled"] if livre and self.srv.pode("clientes.editar") else ["disabled"])
        self.btn_anon.state(["!disabled"] if livre and self.srv.pode("clientes.anonimizar") else ["disabled"])
        self.btn_nota.state(["!disabled"] if livre and self.srv.pode("clientes.anotar") else ["disabled"])
        self.btn_contato.state(["!disabled"] if livre and self.srv.pode("clientes.editar") else ["disabled"])

    def novo(self) -> None:
        DialogoCliente(self, self.srv, ao_salvar=lambda cid: (self.app.atualizar_tudo(), self.selecionar(cid)),
                       ao_abrir_existente=self.selecionar)

    def _editar(self) -> None:
        c = self.srv.obter_cliente(self.selecionado())
        DialogoCliente(self, self.srv, cliente=c, ao_salvar=lambda cid: (self.app.atualizar_tudo(), self.selecionar(cid)),
                       ao_abrir_existente=self.selecionar)

    def _anotar(self) -> None:
        try:
            self.srv.adicionar_anotacao(self.selecionado(), self.nova_nota.get("1.0", "end"))
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        self.nova_nota.delete("1.0", "end")
        self.app.atualizar_tudo()

    def _anonimizar(self) -> None:
        c = self.srv.obter_cliente(self.selecionado())
        if not messagebox.askyesno("Anonimizar dados", f"Os dados pessoais de {c['nome']} serão removidos de forma definitiva.\n"
                                   "Pedidos, lotes e tickets continuam no histórico, sem identificar a pessoa.\n\nDeseja continuar?",
                                   icon="warning", parent=self):
            return
        try:
            self.srv.anonimizar_cliente(c["id"])
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        self.app.atualizar_tudo()

    def _contato(self) -> None:
        DialogoInteracao(self, self.srv, self.selecionado(), ao_salvar=self.app.atualizar_tudo)

    def _rastreio(self) -> None:
        sel = self.compras.selection()
        if not sel:
            avisar(self, "Selecione um pedido na lista.")
            return
        pid = int(sel[0])
        JanelaCadeia(self, f"Rastreio do pedido P-{pid}", f"Do lote {self.srv.lote_do_pedido(pid)} até a mesa do cliente",
                     self.srv.cadeia_do_pedido(pid))


class AbaRastreio(Aba):
    def __init__(self, nb, app):
        super().__init__(nb, app)
        topo = _cabecalho(self, "Rastreabilidade por lote",
                          "Cada lote guarda a origem, as etapas e as medidas. O balanço de massa compara entrada e saída e destaca perdas acima da tolerância.")
        self.btn_etapa = ttk.Button(topo, text="Registrar etapa", style="Primario.TButton", command=self._nova_etapa)
        self.btn_etapa.pack(side="right", anchor="s")
        linha = ttk.Frame(self)
        linha.pack(fill="x")
        ttk.Label(linha, text="Lote", style="Negrito.TLabel").pack(side="left")
        self.v_lote = tk.StringVar()
        self.combo = ttk.Combobox(linha, textvariable=self.v_lote, state="readonly", width=44)
        self.combo.pack(side="left", padx=10)
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._mostrar())
        self.lbl_resumo = ttk.Label(linha, style="Suave.TLabel")
        self.lbl_resumo.pack(side="left", padx=6)
        q = cartao(self, padx=10, pady=8)
        q.pack(fill="x", pady=(10, 14))
        self.cadeia = CadeiaCanvas(q, altura=270)
        self.cadeia.pack(fill="x")
        ttk.Label(self, text="Alertas do balanço de massa neste lote", style="Subtitulo.TLabel", background=COR["fundo"]).pack(anchor="w", pady=(0, 6))
        self.alertas = tabela(self, [("etapa", "Etapa", 220, "w"), ("lote", "Lote de origem", 120, "w"), ("alerta", "Alerta", 260, "w"),
                                     ("medidas", "Medidas", 380, "w")], altura=5)
        self.alertas.quadro.pack(fill="both", expand=True)
        self.alertas.tag_configure("alerta", foreground=COR["ruim"])

    def atualizar(self) -> None:
        self.btn_etapa.configure(state="normal" if self.srv.pode("lotes.registrar") else "disabled")
        lotes = self.srv.listar_lotes()
        self.mapa = {f"{l['codigo']} – {l['nome']}": l["codigo"] for l in lotes}
        self.combo.configure(values=list(self.mapa))
        if self.v_lote.get() not in self.mapa:
            self.v_lote.set(next((k for k in self.mapa if k.startswith("LB-0926-B")), next(iter(self.mapa), "")))
        self._mostrar()

    def _mostrar(self) -> None:
        codigo = self.mapa.get(self.v_lote.get())
        self.alertas.delete(*self.alertas.get_children())
        if not codigo:
            self.cadeia.mostrar([])
            return
        nos = self.srv.cadeia_do_lote(codigo)
        self.cadeia.mostrar(nos)
        origem = ""
        for n in nos:
            origem = n["lote"] or origem
            if n["alerta"]:
                self.alertas.insert("", "end", values=(n["titulo"], origem, n["alerta"], n["medidas"]), tags=("alerta",))
        if not self.alertas.get_children():
            self.alertas.insert("", "end", values=("Nenhum alerta", "", "Todas as etapas com balanço de massa dentro da tolerância.", ""))
        r = self.srv.resumo_lote(codigo)
        self.lbl_resumo.configure(text=f"{r['pedidos']} pedido(s), {r['avaliacoes']} avaliação(ões), {r['tickets']} ticket(s)")

    def _nova_etapa(self) -> None:
        DialogoEtapa(self, self.srv, self.mapa.get(self.v_lote.get(), ""), ao_salvar=lambda lote: self.app.atualizar_tudo())


class AbaAuditoria(Aba):
    def __init__(self, nb, app):
        super().__init__(nb, app)
        _cabecalho(self, "Auditoria",
                   "Cada ação gera um registro com autor, data e hora. Cada registro guarda a impressão digital (SHA-256) do anterior: "
                   "alterar o passado quebra a cadeia.")
        self.banner = ttk.Label(self, style="BannerOk.TLabel", anchor="w")
        self.banner.pack(fill="x")
        barra = ttk.Frame(self)
        barra.pack(fill="x", pady=10)
        self.btn_verificar = ttk.Button(barra, text="Verificar integridade", style="Primario.TButton", command=self._verificar)
        self.btn_verificar.pack(side="left")
        self.btn_simular = ttk.Button(barra, text="Simular adulteração (demonstração)", command=self._simular)
        self.btn_simular.pack(side="left", padx=8)
        self.btn_desfazer = ttk.Button(barra, text="Desfazer adulteração", command=self._desfazer)
        self.btn_desfazer.pack(side="left")
        self.tree = tabela(self, [("n", "Nº", 44, "e"), ("quando", "Quando", 100, "w"), ("quem", "Quem", 190, "w"), ("acao", "Ação", 170, "w"),
                                  ("detalhe", "Detalhe", 440, "w"), ("hash", "Impressão digital", 150, "w")], altura=14)
        self.tree.quadro.pack(fill="both", expand=True)
        self.tree.tag_configure("quebra", foreground=COR["ruim"], background=COR["ruim_suave"])

    def atualizar(self) -> None:
        pode_verif = self.srv.pode("auditoria.verificar")
        pode_sim = self.srv.pode("auditoria.simular")
        adulterado = seguranca.adulteracao_ativa(self.srv.con)
        self.btn_verificar.state(["!disabled"] if pode_verif else ["disabled"])
        self.btn_simular.state(["!disabled"] if pode_sim and not adulterado else ["disabled"])
        self.btn_desfazer.state(["!disabled"] if pode_sim and adulterado else ["disabled"])
        quebra = None
        if pode_verif:
            ok, quebra, total = self.srv.verificar_auditoria()
            if ok:
                self.banner.configure(style="BannerOk.TLabel", text=f"Cadeia íntegra: {total} registros verificados.")
            else:
                self.banner.configure(style="BannerRuim.TLabel", text=f"Quebra detectada a partir do registro nº {quebra}. "
                                      "Os dados foram alterados depois de gravados.")
        else:
            self.banner.configure(style="BannerOk.TLabel", text="Seu perfil pode consultar os registros, mas não verificar a cadeia.")
        self.tree.delete(*self.tree.get_children())
        for r in self.srv.listar_auditoria():
            self.tree.insert("", "end", tags=("quebra",) if quebra and r["n"] >= quebra else (),
                             values=(r["n"], servicos.formatar_data_hora(r["quando"]), r["usuario"], r["acao"], r["detalhe"], r["hash"][:16] + "…"))

    def _verificar(self) -> None:
        self.atualizar()

    def _simular(self) -> None:
        if not messagebox.askyesno("Simular adulteração", "Isto altera um registro antigo diretamente no banco, como faria alguém com acesso ao arquivo, "
                                   "para mostrar que a cadeia detecta a mudança. Dá para desfazer em seguida.\n\nContinuar?", parent=self):
            return
        try:
            self.srv.simular_adulteracao()
        except (ValueError, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
        self.atualizar()

    def _desfazer(self) -> None:
        self.srv.desfazer_adulteracao()
        self.atualizar()


class AbaAdmin(Aba):
    def __init__(self, nb, app):
        super().__init__(nb, app)
        _cabecalho(self, "Administração de TI",
                   "Backup com verificação de integridade e gestão de acessos. O perfil de TI não enxerga os dados de negócio.")
        cima = ttk.LabelFrame(self, text="  Backups  ", padding=12)
        cima.pack(fill="both", expand=True, pady=(0, 12))
        barra = ttk.Frame(cima, style="Cartao.TFrame")
        barra.pack(fill="x", pady=(0, 8))
        self.btn_criar = ttk.Button(barra, text="Criar backup agora", style="Primario.TButton", command=self._criar)
        self.btn_criar.pack(side="left")
        self.btn_testar = ttk.Button(barra, text="Testar restauração do selecionado", command=self._testar)
        self.btn_testar.pack(side="left", padx=8)
        ttk.Label(barra, text="Regra 3-2-1: guarde cópias em dois tipos de mídia e uma fora do local.", style="CartaoSuave.TLabel").pack(side="left", padx=8)
        self.tree_bk = tabela(cima, [("arquivo", "Arquivo", 260, "w"), ("quando", "Criado em", 130, "w"), ("tam", "Tamanho", 90, "e")], altura=5)
        self.tree_bk.quadro.pack(fill="both", expand=True)
        self.lbl_teste = ttk.Label(cima, style="Cartao.TLabel", wraplength=900, justify="left")
        self.lbl_teste.pack(anchor="w", pady=(8, 0))
        baixo = ttk.LabelFrame(self, text="  Usuários e perfis  ", padding=12)
        baixo.pack(fill="both", expand=True)
        self.tree_us = tabela(baixo, [("login", "Login", 120, "w"), ("nome", "Nome", 200, "w"), ("perfil", "Perfil", 160, "w"), ("ativo", "Situação", 90, "w")], altura=6)
        self.tree_us.quadro.pack(fill="both", expand=True)
        self.btn_alt = ttk.Button(baixo, text="Ativar / desativar selecionado", command=self._alternar)
        self.btn_alt.pack(anchor="e", pady=(8, 0))

    def atualizar(self) -> None:
        self.btn_criar.state(["!disabled"] if self.srv.pode("backup.executar") else ["disabled"])
        self.tree_bk.delete(*self.tree_bk.get_children())
        for b in self.srv.listar_backups():
            self.tree_bk.insert("", "end", iid=b["arquivo"], values=(b["arquivo"], servicos.formatar_data_hora(b["criado_em"]), f"{b['tamanho'] / 1024:.0f} KB"))
        self.tree_us.delete(*self.tree_us.get_children())
        for u in self.srv.listar_usuarios():
            self.tree_us.insert("", "end", iid=str(u["id"]), values=(u["login"], u["nome"], seguranca.PERFIS[u["perfil"]]["nome"], "Ativo" if u["ativo"] else "Desativado"))

    def _criar(self) -> None:
        try:
            caminho = self.srv.criar_backup()
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        self.app.atualizar_tudo()
        self.lbl_teste.configure(text=f"Backup {caminho.name} criado com sucesso. Teste a restauração para confirmar que ele é confiável.",
                                 foreground=COR["tinta"])

    def _testar(self) -> None:
        sel = self.tree_bk.selection()
        if not sel:
            avisar(self, "Selecione um backup na lista.")
            return
        rel = self.srv.testar_backup(banco.PASTA_BACKUPS / sel[0])
        sim = lambda v: "sim" if v else "NÃO"  # noqa: E731
        texto = (f"{'APROVADO' if rel['aprovado'] else 'REPROVADO'}: {rel['arquivo']}\n"
                 f"Hash SHA-256 confere: {sim(rel['hash_confere'])}  |  Integridade do arquivo: {sim(rel['integridade_sqlite'])}  |  "
                 f"Cadeia de auditoria íntegra: {sim(rel['cadeia_integra'])}\n"
                 f"Registros de auditoria: {rel['registros_auditoria']}  |  Clientes: {rel['clientes']}  |  Tickets: {rel['tickets']}"
                 + (f"\nErro: {rel['erro']}" if rel["erro"] else ""))
        self.lbl_teste.configure(text=texto, foreground=COR["ok"] if rel["aprovado"] else COR["ruim"])
        self.app.atualizar_tudo()

    def _alternar(self) -> None:
        sel = self.tree_us.selection()
        if not sel:
            avisar(self, "Selecione um usuário na lista.")
            return
        try:
            self.srv.alternar_usuario(int(sel[0]))
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        self.app.atualizar_tudo()


# ------------------------------------------------- app do cliente (simulação)
class JanelaAppCliente(tk.Toplevel):
    """Protótipo da tela de avaliação (Passo 4): nota e comentário em até 3 cliques."""
    FUNDO, TINTA, SUAVE, LINHA, ESTRELA_OFF = "#FBFAFE", "#25222E", "#6A657A", "#E1DEEC", "#CFCBDC"

    def __init__(self, app):
        super().__init__(app.root)
        self.app, self.srv = app, app.srv
        self.title("App do cliente (simulação)")
        self.configure(bg=COR["fundo"])
        self.caminho = tk.StringVar(value="notificacao")
        self.var_pedido = tk.StringVar()
        self.mapa: dict = {}
        self.ctx = None
        self.campo = None
        self._zerar()
        esq = ttk.Frame(self, padding=18)
        esq.pack(side="left", fill="y")
        ttk.Label(esq, text="Avaliação em até 3 cliques", style="Titulo.TLabel").pack(anchor="w")
        ttk.Label(esq, text="Este é o wireframe do Passo 4 funcionando.\nEscolha por onde o cliente chega e toque na tela do celular.",
                  style="Suave.TLabel", justify="left").pack(anchor="w", pady=(4, 14))
        ttk.Label(esq, text="Ponto de partida", style="Negrito.TLabel").pack(anchor="w")
        for texto, valor in (("Pela notificação de entrega", "notificacao"), ("Pelo cartão na tela inicial do aplicativo", "cartao")):
            ttk.Radiobutton(esq, text=texto, value=valor, variable=self.caminho, command=self._trocar_caminho).pack(anchor="w", pady=2)
        ttk.Label(esq, text="Pedido entregue, sem avaliação", style="Negrito.TLabel").pack(anchor="w", pady=(14, 4))
        self.combo = ttk.Combobox(esq, textvariable=self.var_pedido, state="readonly", width=44)
        self.combo.pack(anchor="w")
        self.combo.bind("<<ComboboxSelected>>", lambda e: self._trocar_pedido())
        botoes = ttk.Frame(esq)
        botoes.pack(anchor="w", pady=10)
        self.btn_entrega = ttk.Button(botoes, text="Simular entrega", style="Mel.TButton", command=self._simular_entrega)
        self.btn_entrega.pack(side="left")
        ttk.Button(botoes, text="Reiniciar tela", command=self._reiniciar).pack(side="left", padx=8)
        self.lbl_msg = ttk.Label(esq, style="Suave.TLabel", wraplength=360, justify="left")
        self.lbl_msg.pack(anchor="w")
        ttk.Label(esq, text="Cliques no caminho (limite: 3)", style="Negrito.TLabel").pack(anchor="w", pady=(16, 6))
        pips = ttk.Frame(esq)
        pips.pack(anchor="w")
        self.pips = [tk.Label(pips, text=str(i), width=3, bg=COR["linha"], fg=COR["tinta2"], font=FONTE["negrito"]) for i in (1, 2, 3)]
        for p in self.pips:
            p.pack(side="left", padx=(0, 6))
        self.lbl_cont = ttk.Label(esq, style="Suave.TLabel", wraplength=360, justify="left")
        self.lbl_cont.pack(anchor="w", pady=(8, 0))
        ttk.Label(esq, text="O campo de comentário recebe foco sozinho depois da nota, então digitar não conta como clique. "
                  "As etiquetas são opcionais e ficam fora do caminho mínimo.", style="Suave.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(8, 0))
        ttk.Label(esq, text="Regra de segurança: uma avaliação por pedido entregue, ligada ao pedido e ao lote. "
                  "Notas 1 ou 2 abrem um ticket de qualidade automaticamente no CRM.", style="Suave.TLabel", wraplength=360, justify="left").pack(anchor="w", pady=(10, 0))
        self.celular = tk.Frame(self, bg=self.FUNDO, width=340, height=680, highlightthickness=10, highlightbackground="#1D1A27",
                                highlightcolor="#1D1A27")
        self.celular.pack(side="left", padx=(8, 26), pady=18)
        self.celular.pack_propagate(False)
        self.tela = tk.Frame(self.celular, bg=self.FUNDO)
        self.tela.pack(fill="both", expand=True)
        self._carregar_pedidos()
        self._desenhar()

    # ---- estado
    def _zerar(self) -> None:
        self.estado = "bloqueio" if self.caminho.get() == "notificacao" else "cartao"
        self.nota, self.etiquetas, self.comentario = 0, [], ""
        self.cliques, self.opcionais, self.t0 = 0, 0, None
        self.resultado, self.ticket_id, self.contato = None, None, False

    def _carregar_pedidos(self, preferido: int | None = None) -> None:
        pend = self.srv.pedidos_aguardando_avaliacao()
        self.mapa = {f"P-{p['id']} – {p['cliente_nome']}": p["id"] for p in pend}
        self.combo.configure(values=list(self.mapa))
        alvo = next((k for k, v in self.mapa.items() if v == preferido), None) if preferido else None
        atual = self.var_pedido.get()
        self.var_pedido.set(alvo or (atual if atual in self.mapa else next(iter(self.mapa), "")))
        self.ctx = self.srv.contexto_pedido(self.mapa[self.var_pedido.get()]) if self.var_pedido.get() in self.mapa else None
        self.btn_entrega.state(["!disabled"] if self.srv.pedidos_em_rota() else ["disabled"])
        self.btn_entrega.configure(text=f"Simular entrega ({len(self.srv.pedidos_em_rota())})")

    def _trocar_caminho(self) -> None:
        self._zerar()
        self._desenhar()

    def _trocar_pedido(self) -> None:
        self.ctx = self.srv.contexto_pedido(self.mapa[self.var_pedido.get()])
        self._zerar()
        self._desenhar()

    def _reiniciar(self) -> None:
        self._carregar_pedidos()
        self._zerar()
        self.lbl_msg.configure(text="")
        self._desenhar()

    def _simular_entrega(self) -> None:
        try:
            pid = self.srv.simular_entrega()
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        if pid is None:
            return
        self.lbl_msg.configure(text=f"Entrega do pedido P-{pid} confirmada. A notificação chegou ao celular do cliente.")
        self.app.atualizar_tudo()
        self._carregar_pedidos(preferido=pid)
        self._zerar()
        self._desenhar()

    def _guardar_comentario(self) -> None:
        if self.campo is not None and self.campo.winfo_exists():
            self.comentario = self.campo.get("1.0", "end").strip()

    # ---- toques do cliente
    def toque_notificacao(self) -> None:
        self.cliques += 1
        self.t0 = time.time()
        self.estado = "avaliar"
        self._desenhar()

    def toque_estrela(self, n: int) -> None:
        self._guardar_comentario()
        self.cliques += 1
        self.t0 = self.t0 or time.time()
        self.nota = n
        self.estado = "avaliar"
        self._desenhar()
        if self.campo is not None:
            self.campo.focus_set()

    def alternar_etiqueta(self, nome: str) -> None:
        self._guardar_comentario()
        self.opcionais += 1
        if nome in self.etiquetas:
            self.etiquetas.remove(nome)
        else:
            self.etiquetas.append(nome)
        self._desenhar()

    def agora_nao(self) -> None:
        self._guardar_comentario()
        self.estado = "bloqueio" if self.caminho.get() == "notificacao" else "cartao"
        self._desenhar()

    def enviar(self) -> None:
        self._guardar_comentario()
        self.cliques += 1
        segundos = max(1, round(time.time() - (self.t0 or time.time())))
        try:
            _, ticket = self.srv.registrar_feedback(
                self.ctx["id"], self.nota, self.etiquetas, self.comentario,
                self.cliques, segundos, cliente_id=self.ctx["cliente_id"])
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            self.cliques -= 1
            avisar(self, str(e))
            return
        self.resultado = {"segundos": segundos, "cliques": self.cliques}
        self.ticket_id = ticket
        self.estado = "obrigado"
        self.app.atualizar_tudo()
        self._desenhar()

    def falar_com_a_gente(self) -> None:
        try:
            self.srv.solicitar_contato(self.ticket_id, cliente_id=self.ctx["cliente_id"] if self.ctx else None)
        except (ErroValidacao, seguranca.PermissaoNegada) as e:
            avisar(self, str(e))
            return
        self.contato = True
        self.app.atualizar_tudo()
        self._desenhar()

    def avaliar_outro(self) -> None:
        self._carregar_pedidos()
        self._zerar()
        self._desenhar()

    # ---- desenho
    def _desenhar(self) -> None:
        for w in self.tela.winfo_children():
            w.destroy()
        self.campo = None
        F, T, S = self.FUNDO, self.TINTA, self.SUAVE
        if self.ctx is None and self.estado != "obrigado":
            tk.Label(self.tela, text="Nenhum pedido entregue\naguardando avaliação.\n\nUse “Simular entrega”\nao lado.", bg=F, fg=S, font=FONTE["base"],
                     justify="center").pack(expand=True)
            self._atualizar_contador()
            return
        c = self.ctx
        if self.estado == "bloqueio":
            f = tk.Frame(self.tela, bg="#3B3160")
            f.pack(fill="both", expand=True)
            tk.Label(f, text=time.strftime("%H:%M"), font=FONTE["relogio"], fg="white", bg="#3B3160").pack(pady=(46, 0))
            tk.Label(f, text=time.strftime("%d/%m/%Y"), fg="#D9D3F0", bg="#3B3160", font=FONTE["base"]).pack(pady=(0, 34))
            tk.Button(f, text=f"CAMC Mel & Chia, agora\nComo estava {c['curto']}?\nToque para avaliar em segundos.", justify="left", anchor="w",
                      bg="white", fg=T, activebackground="#EFEDF7", relief="flat", bd=0, padx=14, pady=12, wraplength=250, font=FONTE["base"],
                      cursor="hand2", highlightthickness=0, command=self.toque_notificacao).pack(fill="x", padx=16)
            tk.Label(f, text=f"Seu pedido {c['codigo']} foi entregue.", fg="#D9D3F0", bg="#3B3160", font=FONTE["pequena"]).pack(pady=14)
        elif self.estado == "cartao":
            f = tk.Frame(self.tela, bg=F, padx=18, pady=18)
            f.pack(fill="both", expand=True)
            tk.Label(f, text=f"Olá, {c['primeiro_nome']}", font=FONTE["subtitulo"], bg=F, fg=T).pack(anchor="w", pady=(10, 0))
            q = tk.Frame(f, bg="white", highlightthickness=1, highlightbackground=self.LINHA, padx=14, pady=12)
            q.pack(fill="x", pady=16)
            tk.Label(q, text=f"Pedido {c['codigo']} entregue", font=FONTE["negrito"], bg="white", fg=T).pack(anchor="w")
            tk.Label(q, text=f"Avalie {c['curto']} com um toque.", bg="white", fg=S, font=FONTE["base"], wraplength=240,
                     justify="left").pack(anchor="w", pady=(0, 6))
            self._estrelas(q, "white")
            q2 = tk.Frame(f, bg="white", highlightthickness=1, highlightbackground=self.LINHA, padx=14, pady=12)
            q2.pack(fill="x")
            tk.Label(q2, text="Meus pedidos", font=FONTE["negrito"], bg="white", fg=S).pack(anchor="w")
        elif self.estado == "avaliar":
            f = tk.Frame(self.tela, bg=F, padx=16, pady=8)
            f.pack(fill="both", expand=True)
            topo = tk.Frame(f, bg=F)
            topo.pack(fill="x")
            tk.Button(topo, text="←", bg=F, fg=T, bd=0, relief="flat", font=FONTE["grande"], activebackground=F, cursor="hand2",
                      highlightthickness=0, command=self.agora_nao).pack(side="left")
            tk.Label(topo, text="Avaliar produto", font=FONTE["subtitulo"], bg=F, fg=T).pack(side="left", padx=6)
            prod = tk.Frame(f, bg=F)
            prod.pack(fill="x", pady=(10, 8))
            cv = tk.Canvas(prod, width=54, height=60, bg=F, highlightthickness=0)
            cv.create_polygon(pontos_hexagono(27, 30, 50, 56), fill=COR["mel"], outline=COR["mel"])
            cv.create_text(27, 30, text="M&C", font=FONTE["negrito"], fill=COR["mel_tinta"])
            cv.pack(side="left")
            info = tk.Frame(prod, bg=F)
            info.pack(side="left", padx=10)
            tk.Label(info, text=c["produto"], font=FONTE["negrito"], bg=F, fg=T, wraplength=210, justify="left").pack(anchor="w")
            tk.Label(info, text=f"Pedido {c['codigo']}, lote {c['lote']}", font=FONTE["pequena"], bg=F, fg=S).pack(anchor="w")
            tk.Label(f, text="Como foi sua experiência?", font=FONTE["negrito"], bg=F, fg=T).pack(anchor="w", pady=(8, 0))
            self._estrelas(f, F)
            rotulos = ["Toque para avaliar", "Muito ruim", "Podia ser melhor", "Foi bom", "Gostei muito", "Adorei!"]
            tk.Label(f, text=rotulos[self.nota], font=FONTE["negrito"], bg=F, fg=S).pack(pady=(0, 6))
            tk.Label(f, text="O que mais chamou sua atenção? (opcional)", font=FONTE["base"], bg=F, fg=T, wraplength=280,
                     justify="left").pack(anchor="w")
            tags = tk.Frame(f, bg=F)
            tags.pack(fill="x", pady=6)
            for i, nome in enumerate(ETIQUETAS):
                on = nome in self.etiquetas
                tk.Button(tags, text=nome, bg=COR["chia"] if on else "white", fg="white" if on else T, activebackground=COR["chia_suave"],
                          relief="solid", bd=1, padx=10, pady=3, font=FONTE["base"], cursor="hand2", highlightthickness=0,
                          activeforeground=T, command=lambda n=nome: self.alternar_etiqueta(n)).grid(row=i // 3, column=i % 3, padx=(0, 6), pady=3, sticky="w")
            tk.Label(f, text="Quer contar mais? (opcional)", font=FONTE["pequena"], bg=F, fg=S).pack(anchor="w", pady=(4, 2))
            self.campo = tk.Text(f, height=3, width=10, wrap="word", relief="solid", bd=1, font=FONTE["base"], bg="white", fg=T)
            self.campo.pack(fill="x", pady=(0, 10))
            if self.comentario:
                self.campo.insert("1.0", self.comentario)
            tk.Button(f, text="Enviar avaliação", bg=COR["chia"] if self.nota else "#CFCBDC", fg="white", disabledforeground="white",
                      activebackground=COR["chia_escuro"], activeforeground="white", relief="flat", bd=0, pady=10, font=FONTE["grande"],
                      cursor="hand2", highlightthickness=0, state="normal" if self.nota else "disabled", command=self.enviar).pack(fill="x")
            tk.Button(f, text="Agora não", bg=F, fg=S, bd=0, relief="flat", activebackground=F, font=FONTE["base"], cursor="hand2",
                      highlightthickness=0, command=self.agora_nao).pack(pady=(6, 0))
        else:  # obrigado
            f = tk.Frame(self.tela, bg=F, padx=22, pady=22)
            f.pack(fill="both", expand=True)
            cv = tk.Canvas(f, width=84, height=94, bg=F, highlightthickness=0)
            cv.create_polygon(pontos_hexagono(42, 47, 80, 90), fill=COR["ok"], outline=COR["ok"])
            cv.create_text(42, 47, text="✓", font=FONTE["relogio"], fill="white")
            cv.pack(pady=(40, 12))
            tk.Label(f, text="Obrigado!", font=FONTE["titulo"], bg=F, fg=T).pack()
            tk.Label(f, text=f"Sua opinião ajuda a melhorar {c['curto']}.", bg=F, fg=S, font=FONTE["base"], wraplength=260).pack(pady=6)
            if self.ticket_id:
                tk.Label(f, text="Abrimos um atendimento para cuidar disso.", bg=F, fg=T, font=FONTE["negrito"], wraplength=260).pack(pady=(10, 4))
                if self.contato:
                    tk.Label(f, text="Pedimos que a equipe entre em contato.", bg=F, fg=COR["ok"], font=FONTE["negrito"]).pack()
                else:
                    tk.Button(f, text="Falar com a gente", bg="white", relief="solid", bd=1, padx=14, pady=6, font=FONTE["base"], cursor="hand2",
                              command=self.falar_com_a_gente).pack(pady=6)
            r = self.resultado or {}
            tk.Label(f, text=f"Concluído em {r.get('segundos', 0)} s, com {r.get('cliques', 0)} cliques.", bg=F, fg=S, font=FONTE["pequena"]).pack(pady=(14, 6))
            tk.Button(f, text="Avaliar outro pedido", bg="white", relief="solid", bd=1, padx=14, pady=6, font=FONTE["base"], cursor="hand2",
                      command=self.avaliar_outro).pack()
        self._atualizar_contador()

    def _estrelas(self, mestre, fundo) -> None:
        linha = tk.Frame(mestre, bg=fundo)
        linha.pack(fill="x")
        for n in range(1, 6):
            tk.Button(linha, text="★", font=FONTE["estrela"], bd=0, relief="flat", bg=fundo, activebackground=fundo, cursor="hand2",
                      highlightthickness=0, padx=0, pady=2,
                      fg=COR["mel"] if n <= self.nota else self.ESTRELA_OFF, activeforeground=COR["mel"],
                      command=lambda n=n: self.toque_estrela(n)).pack(side="left", expand=True, fill="x")

    def _atualizar_contador(self) -> None:
        for i, p in enumerate(self.pips, start=1):
            if self.cliques >= i:
                p.configure(bg=COR["ruim"] if self.cliques > 3 else COR["mel"], fg="white" if self.cliques > 3 else COR["mel_tinta"])
            else:
                p.configure(bg=COR["linha"], fg=COR["tinta2"])
        extra = f" Ultrapassou o limite de 3 cliques." if self.cliques > 3 else ""
        self.lbl_cont.configure(text=f"{self.cliques} clique(s) no caminho. Toques opcionais (etiquetas): {self.opcionais}.{extra}")


# ------------------------------------------------------------ login e janela principal
def desenhar_logo(parent, fundo, larg=48, alt=54):
    cv = tk.Canvas(parent, width=larg, height=alt, bg=fundo, highlightthickness=0)
    cv.create_polygon(pontos_hexagono(larg / 2, alt / 2, larg - 2, alt - 2), fill=COR["mel"], outline=COR["mel"])
    for dx, dy, r in ((-7, -6, 2.6), (4, -8, 2.2), (0, 3, 2.8), (9, 5, 2.0), (-9, 9, 2.0)):
        cv.create_oval(larg / 2 + dx - r, alt / 2 + dy - r, larg / 2 + dx + r, alt / 2 + dy + r, fill=COR["lateral"], outline="")
    return cv


class TelaLogin(ttk.Frame):
    def __init__(self, mestre, con, ao_entrar):
        super().__init__(mestre)
        self.con, self.ao_entrar = con, ao_entrar
        centro = cartao(self, padx=38, pady=30)
        centro.place(relx=0.5, rely=0.5, anchor="center")
        desenhar_logo(centro, COR["superficie"], 56, 62).pack()
        ttk.Label(centro, text="CAMC", style="Titulo.TLabel", background=COR["superficie"]).pack(pady=(8, 0))
        ttk.Label(centro, text="Cadeia Alimentar do Mel e Chia", style="CartaoSuave.TLabel").pack(pady=(0, 18))
        self.login, self.senha, self.erro = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Label(centro, text="Login", style="CartaoNegrito.TLabel").pack(anchor="w")
        e1 = ttk.Entry(centro, textvariable=self.login, width=30)
        e1.pack(fill="x", pady=(2, 10))
        ttk.Label(centro, text="Senha", style="CartaoNegrito.TLabel").pack(anchor="w")
        e2 = ttk.Entry(centro, textvariable=self.senha, show="•")
        e2.pack(fill="x", pady=(2, 8))
        ttk.Label(centro, textvariable=self.erro, style="Erro.TLabel", background=COR["superficie"], wraplength=270, justify="left").pack(anchor="w")
        ttk.Button(centro, text="Entrar", style="Primario.TButton", command=self.entrar).pack(fill="x", pady=(10, 14))
        ttk.Label(centro, text="Use seu login e senha corporativos para acessar o sistema.",
                  style="CartaoSuave.TLabel", font=FONTE["pequena"], justify="left").pack(anchor="w")
        e1.focus_set()
        for e in (e1, e2):
            e.bind("<Return>", lambda ev: self.entrar())

    def entrar(self) -> None:
        try:
            sessao = seguranca.autenticar(self.con, self.login.get(), self.senha.get())
        except seguranca.ErroAutenticacao as e:
            self.erro.set(str(e))
            self.senha.set("")
            return
        self.ao_entrar(sessao)


class AppPrincipal(ttk.Frame):
    def __init__(self, root, con, sessao, ao_sair):
        super().__init__(root)
        self.root, self.con, self.sessao, self.ao_sair = root, con, sessao, ao_sair
        self.srv = ServicoCRM(con, sessao)
        self.janela_cliente = None
        topo = tk.Frame(self, bg=COR["lateral"])
        topo.pack(fill="x")
        desenhar_logo(topo, COR["lateral"], 36, 40).pack(side="left", padx=(16, 8), pady=8)
        tk.Label(topo, text="CAMC", bg=COR["lateral"], fg="white", font=FONTE["subtitulo"]).pack(side="left")
        tk.Label(topo, text="  Mel & Chia", bg=COR["lateral"], fg="#A9A3C4", font=FONTE["base"]).pack(side="left")
        ttk.Button(topo, text="Sair", command=self.sair).pack(side="right", padx=16)
        tk.Label(topo, text=sessao.rotulo, bg=COR["lateral"], fg="white", font=FONTE["negrito"]).pack(side="right", padx=4)
        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=14, pady=(10, 14))
        self.abas = {}
        definicoes = [("painel", "Painel", self.srv.pode("painel.ver"), AbaPainel), ("tickets", "Tickets", self.srv.pode("tickets.ver"), AbaTickets),
                      ("clientes", "Clientes", self.srv.pode("clientes.ver"), AbaClientes),
                      ("rastreio", "Rastreabilidade", self.srv.pode("rastreio.ver"), AbaRastreio),
                      ("auditoria", "Auditoria", self.srv.pode("auditoria.ver"), AbaAuditoria),
                      ("admin", "Administração", self.srv.pode("backup.executar") or self.srv.pode("usuarios.gerir"), AbaAdmin)]
        for chave, titulo, permitido, classe in definicoes:
            if permitido:
                aba = classe(self.nb, self)
                self.nb.add(aba, text=titulo)
                self.abas[chave] = aba
        self._menu()
        self.atualizar_tudo()

    def _menu(self) -> None:
        barra = tk.Menu(self.root)
        arquivo = tk.Menu(barra, tearoff=0)
        arquivo.add_command(label="Abrir app do cliente (simulação)", command=self.abrir_app_cliente,
                            state="normal" if self.srv.pode("feedback.simular") else "disabled")
        arquivo.add_command(label="Trocar minha senha…", command=lambda: DialogoSenha(self, self.srv, ao_alterar=self.sair))
        arquivo.add_separator()
        arquivo.add_command(label="Sair da sessão", command=self.sair)
        barra.add_cascade(label="Arquivo", menu=arquivo)
        ajuda = tk.Menu(barra, tearoff=0)
        ajuda.add_command(label="Sobre", command=lambda: messagebox.showinfo(
            "Sobre", "CAMC – sistema integrado (protótipo)\nProjeto Integrado de Análise e Desenvolvimento de Sistemas.\n\n"
            "Dados de exemplo fictícios.", parent=self.root))
        barra.add_cascade(label="Ajuda", menu=ajuda)
        self.root.configure(menu=barra)
        if self.srv.pode("feedback.simular"):
            # atalho visível: o app do cliente é parte central da demonstração
            self.bind_all("<Control-Shift-A>", lambda e: self.abrir_app_cliente())

    def atualizar_tudo(self) -> None:
        for aba in self.abas.values():
            aba.atualizar()

    def ir_para_cliente(self, cliente_id: int) -> None:
        if "clientes" in self.abas:
            self.nb.select(self.abas["clientes"])
            self.abas["clientes"].selecionar(cliente_id)

    def abrir_app_cliente(self) -> None:
        if self.janela_cliente is not None and self.janela_cliente.winfo_exists():
            self.janela_cliente.lift()
            return
        self.janela_cliente = JanelaAppCliente(self)

    def sair(self) -> None:
        seguranca.revogar_sessao(self.con, self.sessao)
        self.destruir()
        self.ao_sair()

    def destruir(self) -> None:
        if self.janela_cliente is not None and self.janela_cliente.winfo_exists():
            self.janela_cliente.destroy()
        self.root.configure(menu="")
        self.unbind_all("<Control-Shift-A>")
        self.destroy()


class Aplicacao:
    def __init__(self, con):
        self.con = con
        self.root = tk.Tk()
        self.root.title("CAMC – Sistema integrado")
        aplicar_tema(self.root)
        self.atual = None
        self.root.report_callback_exception = self._tratar_erro_ui
        self.root.protocol("WM_DELETE_WINDOW", self.fechar)
        self.mostrar_login()

    def _tratar_erro_ui(self, exc_type, exc_value, _exc_tb) -> None:
        """Evita exposição de stack traces ou erros crus do banco na interface."""
        if isinstance(exc_value, seguranca.SessaoInvalida):
            avisar(self.root, str(exc_value), titulo="Sessão encerrada")
            if isinstance(self.atual, AppPrincipal):
                self.atual.sair()
            return
        if isinstance(exc_value, (ErroValidacao, seguranca.PermissaoNegada, seguranca.ErroAutenticacao)):
            avisar(self.root, str(exc_value))
            return
        messagebox.showerror("Erro", "Ocorreu um erro interno ao processar a operação.", parent=self.root)

    def _geometria(self, largura: int, altura: int, minimo=None) -> None:
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        largura, altura = min(largura, sw - 40), min(altura, sh - 90)
        self.root.geometry(f"{largura}x{altura}+{(sw - largura) // 2}+{max((sh - altura) // 3, 0)}")
        self.root.minsize(*(minimo or (largura, altura)))

    def mostrar_login(self) -> None:
        self._geometria(520, 620)
        self.atual = TelaLogin(self.root, self.con, self.entrar)
        self.atual.pack(fill="both", expand=True)

    def entrar(self, sessao) -> None:
        self.atual.destroy()
        self._geometria(1280, 860, minimo=(1000, 640))
        self.atual = AppPrincipal(self.root, self.con, sessao, self.mostrar_login)
        self.atual.pack(fill="both", expand=True)

    def fechar(self) -> None:
        try:
            if isinstance(self.atual, AppPrincipal):
                seguranca.revogar_sessao(self.con, self.atual.sessao)
            self.con.close()
        finally:
            self.root.destroy()

    def executar(self) -> None:
        self.root.mainloop()


def main() -> None:
    con = banco.conectar()
    banco.inicializar(con)
    if banco.banco_vazio(con) and os.environ.get("CAMC_AMBIENTE", "").strip().lower() != "producao":
        from . import exemplo
        exemplo.popular(con)
    Aplicacao(con).executar()
