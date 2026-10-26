import tkinter as tk
from datetime import date, datetime
from pathlib import Path
from tkinter import messagebox
from tkinter import ttk

from auth import AuthService
from auth_views import LoginView, UserManagementView
from database import SQLiteRepository

BASE_DIR = Path(__file__).resolve().parent
DATABASE_FILE = BASE_DIR / "autopecas.db"
DATA_FILE = BASE_DIR / "estoque_autopecas.json"
DATA_FILE_VENDAS = BASE_DIR / "vendas_autopecas.json"
REPOSITORY = SQLiteRepository(DATABASE_FILE, DATA_FILE, DATA_FILE_VENDAS)


def formatar_peca(item):
    marca = item.get("marca", "")
    nome = item.get("nome", "")
    numero_fabrica = item.get("numero_fabrica", "")
    quantidade = item.get("quantidade", 0)
    preco = item.get("preco", 0)
    status = status_por_quantidade(quantidade)
    return (
        f"{marca} | {nome} | {numero_fabrica} | "
        f"Qtd: {quantidade} | R$ {float(preco):.2f} | {status}"
    )


def validar_peca(item):
    for campo in ["nome", "numero_fabrica", "marca", "categoria"]:
        if not str(item.get(campo, "")).strip():
            return False

    try:
        quantidade = int(item.get("quantidade", "0"))
        preco = float(item.get("preco", "0"))
    except (TypeError, ValueError):
        return False

    if quantidade < 0 or preco < 0:
        return False

    return True


def status_por_quantidade(quantidade):
    try:
        return "Esgotado" if int(quantidade) <= 0 else "Disponível"
    except (TypeError, ValueError):
        return "Disponível"


def carregar_pecas():
    return [peca for peca in REPOSITORY.load_parts() if validar_peca(peca)]


def carregar_vendas():
    return REPOSITORY.load_sales()


def salvar_pecas(pecas):
    REPOSITORY.save_parts(pecas)


def salvar_vendas(vendas):
    REPOSITORY.save_sales(vendas)


def filtrar_pecas(pecas, termo, categoria=None):
    termo = termo.lower().strip()
    categoria = (categoria or "").strip().lower()
    filtradas = pecas

    if categoria and categoria != "todas":
        filtradas = [
            p for p in filtradas
            if p.get("categoria", "").lower() == categoria
        ]

    if not termo:
        return filtradas

    return [
        p for p in filtradas
        if termo in p.get("nome", "").lower()
        or termo in p.get("marca", "").lower()
        or termo in p.get("numero_fabrica", "").lower()
        or termo in p.get("categoria", "").lower()
    ]


def buscar_pecas_para_venda(pecas, termo):
    termo = str(termo or "").strip().casefold()
    if not termo:
        return []

    resultados = []
    for indice, peca in enumerate(pecas):
        try:
            quantidade = int(peca.get("quantidade", 0))
        except (TypeError, ValueError):
            continue
        if quantidade <= 0:
            continue
        campos = ("nome", "marca", "numero_fabrica", "categoria")
        if any(termo in str(peca.get(campo, "")).casefold() for campo in campos):
            resultados.append((indice, peca))
    return resultados


def estoque_baixo(item):
    try:
        quantidade = int(item.get("quantidade", 0))
    except (TypeError, ValueError):
        return False

    return quantidade <= 5


def registrar_venda(pecas, indice, quantidade_vendida):
    if indice < 0 or indice >= len(pecas):
        return None

    item = pecas[indice]
    quantidade_atual = int(item.get("quantidade", 0))
    quantidade_vendida = int(quantidade_vendida)

    if quantidade_vendida <= 0:
        return None

    if quantidade_vendida > quantidade_atual:
        return None

    item["quantidade"] = quantidade_atual - quantidade_vendida
    item["status"] = status_por_quantidade(item["quantidade"])
    valor_total = float(item.get("preco", 0)) * quantidade_vendida

    venda = {
        "nome": item.get("nome", ""),
        "quantidade": quantidade_vendida,
        "valor_total": round(valor_total, 2),
        "data": date.today().isoformat(),
        "status": item["status"],
    }

    return venda


def total_valor_estoque(pecas):
    total = 0.0
    for item in pecas:
        try:
            quantidade = int(item.get("quantidade", 0))
            preco = float(item.get("preco", 0))
        except (TypeError, ValueError):
            continue
        total += quantidade * preco
    return round(total, 2)


def total_valor_vendas(vendas):
    total = 0.0
    for venda in vendas:
        try:
            total += float(venda.get("valor_total", 0))
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def resumo_vendas_por_produto(vendas, termo="", data_inicio="", data_fim=""):
    termo = termo.strip().casefold()
    inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date() if data_inicio else None
    fim = datetime.strptime(data_fim, "%Y-%m-%d").date() if data_fim else None
    if inicio and fim and inicio > fim:
        raise ValueError("A data inicial deve ser anterior ou igual à data final.")

    resumo = {}
    for venda in vendas:
        nome = str(venda.get("nome", "Peça")).strip() or "Peça"
        if termo and termo not in nome.casefold():
            continue

        data_texto = venda.get("data")
        if inicio or fim:
            if not data_texto:
                continue
            try:
                data_venda = date.fromisoformat(data_texto)
            except (TypeError, ValueError):
                continue
            if inicio and data_venda < inicio or fim and data_venda > fim:
                continue

        try:
            quantidade = int(venda.get("quantidade", 0))
            valor = float(venda.get("valor_total", 0))
        except (TypeError, ValueError):
            continue

        dados = resumo.setdefault(nome, {"nome": nome, "quantidade": 0, "valor_total": 0.0})
        dados["quantidade"] += quantidade
        dados["valor_total"] += valor

    return [
        {**dados, "valor_total": round(dados["valor_total"], 2)}
        for dados in sorted(resumo.values(), key=lambda item: item["nome"].casefold())
    ]


def valor_estoque_por_categoria(pecas):
    resumo = {}
    for peca in pecas:
        categoria = str(peca.get("categoria", "Sem categoria")).strip() or "Sem categoria"
        try:
            quantidade = int(peca.get("quantidade", 0))
            valor = quantidade * float(peca.get("preco", 0))
        except (TypeError, ValueError):
            continue

        dados = resumo.setdefault(categoria, {"categoria": categoria, "quantidade": 0, "valor_total": 0.0})
        dados["quantidade"] += quantidade
        dados["valor_total"] += valor

    return [
        {**dados, "valor_total": round(dados["valor_total"], 2)}
        for dados in sorted(resumo.values(), key=lambda item: item["categoria"].casefold())
    ]


class CadastroView:
    def __init__(self, controller):
        self.controller = controller
        self.frame = tk.Frame(controller.root, bg="#111827")
        self.frame.pack(fill="both", expand=True)

        self.item_em_edicao = None
        self.produtos_para_edicao = []
        self.campos = {}
        self.criar_widgets()

    def criar_widgets(self):
        container = tk.Frame(self.frame, bg="#111827", padx=28, pady=24)
        container.pack(fill="both", expand=True)

        titulo = tk.Label(
            container,
            text="Cadastro de Peça",
            font=("Arial", 22, "bold"),
            bg="#111827",
            fg="#f9fafb",
        )
        titulo.pack(anchor="w", pady=20)

        seletor_frame = tk.Frame(container, bg="#1f2937", padx=18, pady=14)
        seletor_frame.pack(fill="x", pady=(0, 14))
        tk.Label(
            seletor_frame,
            text="Editar produto existente:",
            bg="#1f2937",
            fg="#f9fafb",
            font=("Arial", 10, "bold"),
        ).pack(side="left")
        self.seletor_produto = ttk.Combobox(seletor_frame, state="readonly", font=("Arial", 10))
        self.seletor_produto.pack(side="left", fill="x", expand=True, padx=10)
        tk.Button(
            seletor_frame,
            text="Carregar para edição",
            command=self.carregar_produto_selecionado,
            bg="#3b82f6",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side="left", padx=(0, 8))
        tk.Button(
            seletor_frame,
            text="Novo produto",
            command=self.iniciar_novo_produto,
            bg="#22c55e",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(side="left")

        form = tk.Frame(container, bg="#1f2937", padx=18, pady=18)
        form.pack(fill="x")

        campos = [
            ("Nome da Peça", "nome"),
            ("Marca", "marca"),
            ("Número de Fabrica", "numero_fabrica"),
            ("Categoria", "categoria"),
            ("Quantidade em Estoque", "quantidade"),
            ("Preço", "preco"),
            ("Status", "status"),
        ]

        for texto, chave in campos:
            linha = tk.Frame(form, bg="#1f2937", pady=7)
            linha.pack(fill="x")

            label = tk.Label(
                linha,
                text=texto,
                width=22,
                anchor="w",
                bg="#1f2937",
                fg="#e5e7eb",
                font=("Arial", 11),
            )
            label.pack(side="left")

            if chave == "status":
                entrada = ttk.Combobox(
                    linha,
                    values=["Disponível", "Esgotado"],
                    state="readonly",
                    width=38,
                    font=("Arial", 11),
                )
            else:
                entrada = tk.Entry(linha, font=("Arial", 11), width=40, bg="#f9fafb")

            entrada.pack(side="left", fill="x", expand=True, padx=10)
            self.campos[chave] = entrada
            if chave == "quantidade":
                entrada.bind("<KeyRelease>", self.atualizar_status_por_campo)
            elif chave == "status":
                entrada.bind("<<ComboboxSelected>>", self.atualizar_status_por_campo)

        botoes = tk.Frame(form, bg="#1f2937", pady=20)
        botoes.pack(fill="x")

        btn_voltar_menu = tk.Button(
            botoes,
            text="Voltar ao menu",
            command=self.controller.mostrar_menu,
            width=16,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        )
        btn_voltar_menu.pack(side="left", padx=10)

        btn_salvar = tk.Button(
            botoes,
            text="Salvar Peça",
            command=self.salvar_peca,
            width=18,
            bg="#22c55e",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        btn_salvar.pack(side="left", padx=10)

        btn_limpar = tk.Button(
            botoes,
            text="Limpar",
            command=self.limpar_campos,
            width=12,
            bg="#60a5fa",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        btn_limpar.pack(side="left")

        btn_consulta = tk.Button(
            botoes,
            text="Ir para consulta",
            command=self.controller.mostrar_consulta,
            width=18,
            bg="#3b82f6",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        btn_consulta.pack(side="right")

        self.status = tk.Label(
            container,
            text="Sistema pronto.",
            bg="#111827",
            fg="#86efac",
            anchor="w",
            font=("Arial", 10),
        )
        self.status.pack(fill="x", pady=20)

    def limpar_campos(self):
        for entrada in self.campos.values():
            if isinstance(entrada, ttk.Combobox):
                entrada.set("")
            else:
                entrada.delete(0, tk.END)

    def atualizar_opcoes_produtos(self):
        self.produtos_para_edicao = list(range(len(self.controller.pecas)))
        opcoes = [
            f"{peca.get('nome', 'Peça')} | {peca.get('numero_fabrica', '')} | {peca.get('marca', '')}"
            for peca in self.controller.pecas
        ]
        self.seletor_produto["values"] = opcoes
        if self.seletor_produto.get() not in opcoes:
            self.seletor_produto.set("")

    def iniciar_novo_produto(self):
        self.item_em_edicao = None
        self.limpar_campos()
        self.campos["status"].set("")
        self.seletor_produto.set("")
        self.status.config(text="Novo produto: preencha os campos e salve.", fg="#86efac")

    def carregar_produto_selecionado(self):
        selecao = self.seletor_produto.current()
        if selecao < 0 or selecao >= len(self.produtos_para_edicao):
            messagebox.showwarning("Seleção necessária", "Selecione um produto para editar.")
            return
        indice = self.produtos_para_edicao[selecao]
        self.preencher_formulario(self.controller.pecas[indice], indice)

    def coletar_dados(self):
        quantidade = self.campos["quantidade"].get().strip()
        return {
            "nome": self.campos["nome"].get().strip(),
            "marca": self.campos["marca"].get().strip(),
            "numero_fabrica": self.campos["numero_fabrica"].get().strip(),
            "categoria": self.campos["categoria"].get().strip(),
            "quantidade": quantidade,
            "preco": self.campos["preco"].get().strip().replace(",", "."),
            "status": status_por_quantidade(quantidade),
        }

    def atualizar_status_por_campo(self, event=None):
        quantidade = self.campos["quantidade"].get().strip()
        if not quantidade:
            self.campos["status"].set("")
            return
        try:
            self.campos["status"].set(status_por_quantidade(int(quantidade)))
        except ValueError:
            self.campos["status"].set("")

    def atualizar_status_label(self, valor):
        valor = str(valor or "").strip().lower()
        cores = {
            "disponível": "#86efac",
            "esgotado": "#fca5a5",
        }
        self.status.config(fg=cores.get(valor, "#86efac"))

    def preencher_formulario(self, item, indice):
        self.item_em_edicao = indice
        self.atualizar_opcoes_produtos()
        if indice in self.produtos_para_edicao:
            self.seletor_produto.current(self.produtos_para_edicao.index(indice))
        for chave, entrada in self.campos.items():
            entrada.delete(0, tk.END)
            valor = str(item.get(chave, ""))
            if isinstance(entrada, ttk.Combobox):
                entrada.set(valor)
            else:
                entrada.insert(0, valor)
        self.atualizar_status_por_campo()
        self.atualizar_status_label(item.get("status", "Disponível"))
        self.status.config(text=f"Editando peça: {item['nome']}")

    def salvar_peca(self):
        dados = self.coletar_dados()

        if not validar_peca(dados):
            messagebox.showwarning("Aviso", "Preencha todos os campos corretamente antes de cadastrar.")
            return

        dados["quantidade"] = int(dados["quantidade"])
        dados["preco"] = round(float(dados["preco"]), 2)
        dados["status"] = status_por_quantidade(dados["quantidade"])

        if self.item_em_edicao is None:
            self.controller.pecas.append(dados)
            self.status.config(text=f"Peça cadastrada: {dados['nome']}")
        else:
            self.controller.pecas[self.item_em_edicao] = dados
            self.status.config(text=f"Peça atualizada: {dados['nome']}")
            self.item_em_edicao = None

        salvar_pecas(self.controller.pecas)
        self.atualizar_opcoes_produtos()
        self.iniciar_novo_produto()
        self.controller.consulta_view.atualizar_lista()


class ConsultaView:
    def __init__(self, controller):
        self.controller = controller
        self.itens_visiveis = []
        self.frame = tk.Frame(controller.root, bg="#111827")

        container = tk.Frame(self.frame, bg="#111827", padx=28, pady=24)
        container.pack(fill="both", expand=True)

        topo = tk.Frame(container, bg="#111827")
        topo.pack(fill="x")

        titulo = tk.Label(
            topo,
            text="Consulta de Peças",
            font=("Arial", 22, "bold"),
            bg="#111827",
            fg="#f9fafb",
        )
        titulo.pack(side="left")

        btn_voltar = tk.Button(
            topo,
            text="Voltar ao menu",
            command=self.controller.mostrar_menu,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        )
        btn_voltar.pack(side="right")

        busca_frame = tk.Frame(container, bg="#1f2937", padx=16, pady=12)
        busca_frame.pack(fill="x", pady=20)

        tk.Label(
            busca_frame,
            text="Buscar peça:",
            bg="#1f2937",
            fg="#f9fafb",
            font=("Arial", 11),
        ).pack(side="left")

        self.busca = tk.Entry(busca_frame, font=("Arial", 11), width=30)
        self.busca.pack(side="left", padx=10, fill="x", expand=True)
        self.busca.bind("<KeyRelease>", self.atualizar_lista)

        tk.Label(
            busca_frame,
            text="Categoria:",
            bg="#1f2937",
            fg="#f9fafb",
            font=("Arial", 11),
        ).pack(side="left", padx=(10, 0))

        self.filtro_categoria = ttk.Combobox(
            busca_frame,
            values=["Todas"],
            state="readonly",
            width=18,
            font=("Arial", 10),
        )
        self.filtro_categoria.pack(side="left", padx=10)
        self.filtro_categoria.bind("<<ComboboxSelected>>", self.atualizar_lista)

        btn_limpar = tk.Button(
            busca_frame,
            text="Limpar filtros",
            command=self.limpar_filtros,
            bg="#94a3b8",
            fg="black",
            font=("Arial", 9, "bold"),
        )
        btn_limpar.pack(side="left", padx=10)

        self.atualizar_opcoes_categoria()

        resumo = tk.Frame(container, bg="#111827")
        resumo.pack(fill="x", pady=(0, 12))

        self.resumo_total_itens = tk.Label(resumo, text="Itens: 0", bg="#111827", fg="#e2e8f0", font=("Arial", 10, "bold"))
        self.resumo_total_itens.pack(side="left", padx=(0, 18))

        self.resumo_estoque = tk.Label(resumo, text="Unidades em estoque: 0", bg="#111827", fg="#86efac", font=("Arial", 10, "bold"))
        self.resumo_estoque.pack(side="left", padx=(0, 18))

        self.resumo_criticos = tk.Label(resumo, text="Críticos: 0", bg="#111827", fg="#fca5a5", font=("Arial", 10, "bold"))
        self.resumo_criticos.pack(side="left", padx=(0, 18))

        self.resumo_valor = tk.Label(resumo, text="Valor estimado: R$ 0.00", bg="#111827", fg="#fbbf24", font=("Arial", 10, "bold"))
        self.resumo_valor.pack(side="left")

        lista_frame = tk.Frame(container, bg="#1f2937", padx=14, pady=14)
        lista_frame.pack(fill="both", expand=True)

        colunas = ("nome", "marca", "numero_fabrica", "categoria", "quantidade", "preco", "status")
        self.tree = ttk.Treeview(
            lista_frame,
            columns=colunas,
            show="headings",
            height=16,
        )

        cabecalhos = {
            "nome": "Nome",
            "marca": "Marca",
            "numero_fabrica": "Nº Fabrica",
            "categoria": "Categoria",
            "quantidade": "Quantidade",
            "preco": "Preço",
            "status": "Status",
        }

        for coluna in colunas:
            self.tree.heading(coluna, text=cabecalhos[coluna])
            self.tree.column(coluna, width=120, anchor="center")

        self.tree.tag_configure("disponivel", foreground="#166534", background="#dcfce7")
        self.tree.tag_configure("esgotado", foreground="#991b1b", background="#fee2e2")
        self.tree.pack(fill="both", expand=True)

        scrollbar = tk.Scrollbar(lista_frame, orient="vertical", command=self.tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scrollbar.set)

        botoes = tk.Frame(container, bg="#111827", pady=12)
        botoes.pack(fill="x")

        self.btn_editar = tk.Button(
            botoes,
            text="Editar",
            command=self.editar_peca,
            width=12,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        )
        self.btn_editar.pack(side="left", padx=10)

        self.btn_excluir = tk.Button(
            botoes,
            text="Excluir",
            command=self.excluir_peca,
            width=12,
            bg="#ef4444",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        self.btn_excluir.pack(side="left")

        self.status = tk.Label(
            container,
            text="Consulta ativa.",
            bg="#111827",
            fg="#86efac",
            anchor="w",
            font=("Arial", 10),
        )
        self.status.pack(fill="x", pady=16)

        self.atualizar_lista()
        self.atualizar_permissoes()

    def atualizar_permissoes(self):
        if self.controller.tem_permissao("gerenciar_estoque"):
            self.btn_editar.pack(side="left", padx=10)
            self.btn_excluir.pack(side="left")
        else:
            self.btn_editar.pack_forget()
            self.btn_excluir.pack_forget()

    def atualizar_opcoes_categoria(self):
        categorias = sorted({
            p.get("categoria", "").strip()
            for p in self.controller.pecas
            if str(p.get("categoria", "")).strip()
        })
        opcoes = ["Todas"] + categorias
        self.filtro_categoria["values"] = opcoes
        if self.filtro_categoria.get() not in opcoes:
            self.filtro_categoria.set("Todas")

    def limpar_filtros(self):
        self.busca.delete(0, tk.END)
        self.filtro_categoria.set("Todas")
        self.atualizar_lista()

    def atualizar_resumo(self):
        total_itens = len(self.controller.pecas)
        total_estoque = sum(int(p.get("quantidade", 0)) for p in self.controller.pecas)
        valor_total = sum(float(p.get("preco", 0)) * int(p.get("quantidade", 0)) for p in self.controller.pecas)
        criticos = sum(1 for p in self.controller.pecas if estoque_baixo(p))

        self.resumo_total_itens.config(text=f"Itens: {total_itens}")
        self.resumo_estoque.config(text=f"Unidades em estoque: {total_estoque}")
        self.resumo_criticos.config(text=f"Críticos: {criticos}")
        self.resumo_valor.config(text=f"Valor estimado: R$ {valor_total:.2f}")

    def tag_status(self, item):
        if status_por_quantidade(item.get("quantidade", 0)) == "Esgotado":
            return "esgotado"
        return "disponivel"

    def atualizar_lista(self, event=None):
        for item in self.tree.get_children():
            self.tree.delete(item)
        self.itens_visiveis = []
        termo = self.busca.get()
        categoria = self.filtro_categoria.get()
        pecas_filtradas = filtrar_pecas(self.controller.pecas, termo, categoria)

        if not pecas_filtradas:
            self.tree.insert("", "end", values=("Nenhuma peça encontrada.", "", "", "", "", "", ""))
            self.atualizar_resumo()
            return

        for indice, item in enumerate(self.controller.pecas):
            if item in pecas_filtradas:
                self.itens_visiveis.append(indice)
                status = status_por_quantidade(item.get("quantidade", 0))
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        item.get("nome", ""),
                        item.get("marca", ""),
                        item.get("numero_fabrica", ""),
                        item.get("categoria", ""),
                        item.get("quantidade", 0),
                        f"R$ {float(item.get('preco', 0)):.2f}",
                        status,
                    ),
                    tags=(self.tag_status(item),),
                )

        self.atualizar_resumo()

    def editar_peca(self):
        if not self.controller.tem_permissao("gerenciar_estoque"):
            messagebox.showwarning("Acesso restrito", "Somente administradores podem editar produtos.")
            return
        if not self.controller.pecas:
            messagebox.showwarning("Aviso", "Nenhuma peça cadastrada.")
            return

        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma peça para editar.")
            return

        indice_original = self.itens_visiveis[int(self.tree.index(selecionado[0]))]
        item = self.controller.pecas[indice_original]
        self.controller.mostrar_cadastro(indice_original)

    def confirmar_exclusao(self, nome_peca):
        confirmacao = tk.Toplevel(self.controller.root)
        confirmacao.title("Confirmação")
        confirmacao.geometry("360x150")
        confirmacao.resizable(False, False)
        confirmacao.transient(self.controller.root)
        confirmacao.grab_set()

        mensagem = tk.Label(
            confirmacao,
            text=f"Deseja realmente excluir a peça '{nome_peca}'?",
            font=("Arial", 11),
            wraplength=300,
            justify="center",
            padx=20,
            pady=20,
        )
        mensagem.pack(fill="both")

        botoes = tk.Frame(confirmacao, pady=10)
        botoes.pack()

        resultado = {"confirmado": False}

        def excluir():
            resultado["confirmado"] = True
            confirmacao.destroy()

        def cancelar():
            confirmacao.destroy()

        btn_sim = tk.Button(botoes, text="Sim", width=12, command=excluir, bg="#22c55e", fg="white")
        btn_sim.pack(side="left", padx=10)

        btn_nao = tk.Button(botoes, text="Não", width=12, command=cancelar, bg="#ef4444", fg="white")
        btn_nao.pack(side="left", padx=10)

        confirmacao.wait_window()
        return resultado["confirmado"]

    def excluir_peca(self):
        if not self.controller.tem_permissao("gerenciar_estoque"):
            messagebox.showwarning("Acesso restrito", "Somente administradores podem excluir produtos.")
            return
        if not self.controller.pecas:
            messagebox.showwarning("Aviso", "Nenhuma peça cadastrada.")
            return

        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione uma peça para excluir.")
            return

        indice_original = self.itens_visiveis[int(self.tree.index(selecionado[0]))]
        item_excluido = self.controller.pecas[indice_original]

        if not self.confirmar_exclusao(item_excluido.get("nome", "Peça")):
            self.status.config(text="Exclusão cancelada.")
            return

        self.controller.pecas.pop(indice_original)
        salvar_pecas(self.controller.pecas)
        self.atualizar_lista()
        self.status.config(text=f"Peça removida: {item_excluido['nome']}")


class VendasView:
    def __init__(self, controller):
        self.controller = controller
        self.produto_selecionado = None
        self.frame = tk.Frame(controller.root, bg="#111827")
        self.frame.pack(fill="both", expand=True)
        self.criar_widgets()

    def criar_widgets(self):
        container = tk.Frame(self.frame, bg="#111827", padx=28, pady=24)
        container.pack(fill="both", expand=True)

        topo = tk.Frame(container, bg="#111827")
        topo.pack(fill="x")

        titulo = tk.Label(
            topo,
            text="Registro de Vendas",
            font=("Arial", 22, "bold"),
            bg="#111827",
            fg="#f9fafb",
        )
        titulo.pack(side="left")

        btn_voltar = tk.Button(
            topo,
            text="Voltar ao menu",
            command=self.controller.mostrar_menu,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        )
        btn_voltar.pack(side="right")

        form = tk.Frame(container, bg="#1f2937", padx=18, pady=18)
        form.pack(fill="x", pady=20)

        tk.Label(form, text="Produto selecionado:", bg="#1f2937", fg="#f9fafb", font=("Arial", 11)).pack(anchor="w")
        linha_produto = tk.Frame(form, bg="#1f2937")
        linha_produto.pack(fill="x", pady=(6, 14))
        self.produto_label = tk.Label(
            linha_produto,
            text="Nenhum produto consultado",
            bg="#f9fafb",
            fg="#334155",
            anchor="w",
            padx=10,
            pady=8,
            font=("Arial", 10),
        )
        self.produto_label.pack(side="left", fill="x", expand=True)
        tk.Button(
            linha_produto,
            text="Consultar produto",
            command=self.abrir_consulta_produtos,
            bg="#3b82f6",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(10, 0), ipady=4)

        linha = tk.Frame(form, bg="#1f2937")
        linha.pack(fill="x")

        tk.Label(linha, text="Quantidade vendida:", bg="#1f2937", fg="#f9fafb", font=("Arial", 11)).pack(side="left")
        self.quantidade = tk.Entry(linha, font=("Arial", 11), width=15)
        self.quantidade.pack(side="left", padx=10)

        btn_vender = tk.Button(
            form,
            text="Registrar venda",
            command=self.registrar_venda,
            width=20,
            bg="#22c55e",
            fg="white",
            font=("Arial", 10, "bold"),
        )
        btn_vender.pack(pady=(20, 0), anchor="w")

        resumo = tk.Frame(container, bg="#111827")
        resumo.pack(fill="x", pady=(0, 12))

        self.resumo_estoque = tk.Label(resumo, text="Estoque: R$ 0.00", bg="#111827", fg="#86efac", font=("Arial", 10, "bold"))
        self.resumo_estoque.pack(side="left", padx=(0, 18))

        self.resumo_vendas = tk.Label(resumo, text="Vendas: R$ 0.00", bg="#111827", fg="#fbbf24", font=("Arial", 10, "bold"))
        self.resumo_vendas.pack(side="left")

        self.status = tk.Label(
            container,
            text="Sistema de vendas pronto.",
            bg="#111827",
            fg="#86efac",
            anchor="w",
            font=("Arial", 10),
        )
        self.status.pack(fill="x", pady=16)

        self.historico_frame = tk.Frame(container, bg="#1f2937", padx=14, pady=14)
        self.historico_frame.pack(fill="both", expand=True)

        self.lista_vendas = tk.Listbox(
            self.historico_frame,
            font=("Arial", 10),
            height=12,
            activestyle="none",
            bg="#f9fafb",
        )
        self.lista_vendas.pack(fill="both", expand=True)

        self.atualizar_historico()
        self.atualizar_resumo()

    def abrir_consulta_produtos(self):
        consulta = tk.Toplevel(self.controller.root)
        consulta.title("Consultar produtos para venda")
        consulta.geometry("780x440")
        consulta.minsize(650, 360)
        consulta.transient(self.controller.root)
        consulta.grab_set()

        container = tk.Frame(consulta, padx=18, pady=16)
        container.pack(fill="both", expand=True)
        tk.Label(
            container,
            text="Consultar produto",
            font=("Arial", 16, "bold"),
        ).pack(anchor="w")
        tk.Label(
            container,
            text="Pesquise por nome, marca, número de fábrica ou categoria.",
            font=("Arial", 10),
        ).pack(anchor="w", pady=(4, 12))

        linha_busca = tk.Frame(container)
        linha_busca.pack(fill="x", pady=(0, 12))
        busca = tk.Entry(linha_busca, font=("Arial", 11))
        busca.pack(side="left", fill="x", expand=True)
        tabela = ttk.Treeview(
            container,
            columns=("nome", "marca", "numero_fabrica", "categoria", "quantidade"),
            show="headings",
            height=10,
        )
        titulos = {
            "nome": "Produto",
            "marca": "Marca",
            "numero_fabrica": "Nº fábrica",
            "categoria": "Categoria",
            "quantidade": "Unidades disponíveis",
        }
        for coluna, titulo in titulos.items():
            tabela.heading(coluna, text=titulo)
            tabela.column(coluna, anchor="center", width=140)
        tabela.pack(fill="both", expand=True)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=tabela.yview)
        scrollbar.place(relx=1.0, rely=0.45, relheight=0.43, anchor="ne")
        tabela.configure(yscrollcommand=scrollbar.set)
        status = tk.Label(container, text="Digite um termo e clique em Consultar.", anchor="w")
        status.pack(fill="x", pady=(8, 4))
        resultados = {}

        def executar_consulta(event=None):
            tabela.delete(*tabela.get_children())
            resultados.clear()
            termo = busca.get().strip()
            if not termo:
                status.config(text="Informe um termo para consultar os produtos.")
                return
            encontrados = buscar_pecas_para_venda(self.controller.pecas, termo)
            for indice, peca in encontrados:
                iid = tabela.insert(
                    "",
                    "end",
                    values=(
                        peca.get("nome", ""),
                        peca.get("marca", ""),
                        peca.get("numero_fabrica", ""),
                        peca.get("categoria", ""),
                        peca.get("quantidade", 0),
                    ),
                )
                resultados[iid] = indice
            status.config(text=f"{len(encontrados)} produto(s) disponível(is) encontrado(s).")

        def selecionar_produto(event=None):
            selecionados = tabela.selection()
            if not selecionados:
                status.config(text="Selecione um produto dos resultados da consulta.")
                return
            indice = resultados[selecionados[0]]
            produto = self.controller.pecas[indice]
            self.produto_selecionado = indice
            self.produto_label.config(
                text=(
                    f"{produto.get('nome', '')} | {produto.get('marca', '')} | "
                    f"Nº {produto.get('numero_fabrica', '')} | "
                    f"{produto.get('quantidade', 0)} unidade(s) disponíveis"
                )
            )
            consulta.destroy()

        tk.Button(
            linha_busca,
            text="Consultar",
            command=executar_consulta,
            bg="#0ea5e9",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side="left", padx=(8, 0), ipady=3)
        botoes = tk.Frame(container)
        botoes.pack(fill="x", pady=(8, 0))
        tk.Button(
            botoes,
            text="Selecionar produto",
            command=selecionar_produto,
            bg="#22c55e",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(side="left")
        tk.Button(botoes, text="Cancelar", command=consulta.destroy).pack(side="right")
        busca.bind("<Return>", executar_consulta)
        tabela.bind("<Double-1>", selecionar_produto)
        busca.focus_set()

    def limpar_produto_selecionado(self):
        self.produto_selecionado = None
        self.produto_label.config(text="Nenhum produto consultado")

    def atualizar_resumo(self):
        valor_estoque = total_valor_estoque(self.controller.pecas)
        valor_vendas = total_valor_vendas(self.controller.vendas)
        self.resumo_estoque.config(text=f"Estoque: R$ {valor_estoque:.2f}")
        self.resumo_vendas.config(text=f"Vendas: R$ {valor_vendas:.2f}")

    def atualizar_historico(self):
        self.lista_vendas.delete(0, tk.END)
        if not self.controller.vendas:
            self.lista_vendas.insert(tk.END, "Nenhuma venda registrada.")
            return

        for venda in self.controller.vendas[-10:]:
            nome = venda.get("nome", "Peça")
            quantidade = venda.get("quantidade", 0)
            valor = venda.get("valor_total", 0)
            data_venda = venda.get("data", "Sem data")
            operador = venda.get("usuario") or "Histórico legado"
            preco_unitario = venda.get("preco_unitario")
            preco_texto = f" | Unitário: R$ {float(preco_unitario):.2f}" if preco_unitario is not None else ""
            self.lista_vendas.insert(
                tk.END,
                f"{data_venda} | {nome} | Qtd: {quantidade}{preco_texto} | Total: R$ {float(valor):.2f} | Usuário: {operador}",
            )

    def registrar_venda(self):
        if not self.controller.pecas:
            messagebox.showwarning("Aviso", "Nenhuma peça cadastrada para venda.")
            return

        indice = self.produto_selecionado
        if indice is None or indice >= len(self.controller.pecas):
            messagebox.showwarning("Aviso", "Consulte e selecione um produto antes de registrar a venda.")
            return

        try:
            quantidade = int(self.quantidade.get().strip())
        except ValueError:
            messagebox.showwarning("Aviso", "Informe uma quantidade válida.")
            return

        if quantidade <= 0:
            messagebox.showwarning("Aviso", "A quantidade da venda precisa ser maior que zero.")
            return

        produto = self.controller.pecas[indice]
        if int(produto.get("quantidade", 0)) <= 0:
            self.produto_selecionado = None
            self.produto_label.config(text="Nenhum produto consultado")
            messagebox.showwarning("Aviso", "O produto selecionado está sem unidades disponíveis. Consulte novamente.")
            return

        venda = REPOSITORY.register_sale(
            produto["id"], quantidade, self.controller.active_user["id"]
        )
        if venda is None:
            messagebox.showwarning("Aviso", "Quantidade indisponível para venda.")
            return

        self.controller.pecas = REPOSITORY.load_parts()
        self.controller.vendas = REPOSITORY.load_sales()

        self.quantidade.delete(0, tk.END)
        self.limpar_produto_selecionado()
        self.atualizar_historico()
        self.atualizar_resumo()
        self.controller.consulta_view.atualizar_lista()
        self.status.config(text=f"Venda registrada: {venda['nome']} - {venda['quantidade']} unidade(s)")


class ConsultaFinanceiraView:
    def __init__(self, controller):
        self.controller = controller
        self.frame = tk.Frame(controller.root, bg="#111827")
        self.criar_widgets()

    def criar_widgets(self):
        container = tk.Frame(self.frame, bg="#111827", padx=28, pady=24)
        container.pack(fill="both", expand=True)

        topo = tk.Frame(container, bg="#111827")
        topo.pack(fill="x")
        tk.Label(topo, text="Consulta Financeira", font=("Arial", 22, "bold"), bg="#111827", fg="#f9fafb").pack(side="left")
        tk.Button(
            topo,
            text="Voltar ao menu",
            command=self.controller.mostrar_menu,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        filtros = tk.Frame(container, bg="#1f2937", padx=14, pady=12)
        filtros.pack(fill="x", pady=(18, 12))
        tk.Label(filtros, text="Produto:", bg="#1f2937", fg="#f9fafb").grid(row=0, column=0, sticky="w")
        self.filtro_produto = tk.Entry(filtros, font=("Arial", 10), width=24)
        self.filtro_produto.grid(row=0, column=1, padx=(6, 14), sticky="ew")
        tk.Label(filtros, text="De (AAAA-MM-DD):", bg="#1f2937", fg="#f9fafb").grid(row=0, column=2, sticky="w")
        self.data_inicio = tk.Entry(filtros, font=("Arial", 10), width=13)
        self.data_inicio.grid(row=0, column=3, padx=(6, 14))
        tk.Label(filtros, text="Até:", bg="#1f2937", fg="#f9fafb").grid(row=0, column=4, sticky="w")
        self.data_fim = tk.Entry(filtros, font=("Arial", 10), width=13)
        self.data_fim.grid(row=0, column=5, padx=(6, 14))
        tk.Button(
            filtros,
            text="Consultar",
            command=self.atualizar_relatorio,
            bg="#22c55e",
            fg="white",
            font=("Arial", 9, "bold"),
        ).grid(row=0, column=6, padx=(0, 6))
        tk.Button(
            filtros,
            text="Limpar",
            command=self.limpar_filtros,
            bg="#94a3b8",
            fg="black",
            font=("Arial", 9, "bold"),
        ).grid(row=0, column=7)
        filtros.columnconfigure(1, weight=1)

        resumos = tk.Frame(container, bg="#111827")
        resumos.pack(fill="x", pady=(0, 12))
        self.total_vendas = tk.Label(resumos, text="Vendas no período: R$ 0.00", bg="#111827", fg="#fbbf24", font=("Arial", 11, "bold"))
        self.total_vendas.pack(side="left", padx=(0, 24))
        self.total_estoque = tk.Label(resumos, text="Valor estimado do estoque: R$ 0.00", bg="#111827", fg="#86efac", font=("Arial", 11, "bold"))
        self.total_estoque.pack(side="left")

        abas = ttk.Notebook(container)
        abas.pack(fill="both", expand=True)
        vendas_frame = tk.Frame(abas, bg="#1f2937", padx=12, pady=12)
        estoque_frame = tk.Frame(abas, bg="#1f2937", padx=12, pady=12)
        abas.add(vendas_frame, text="Vendas por produto")
        abas.add(estoque_frame, text="Estoque por categoria")

        self.tabela_vendas = self.criar_tabela(
            vendas_frame,
            ("nome", "quantidade", "valor_total"),
            {"nome": "Produto", "quantidade": "Unidades vendidas", "valor_total": "Valor vendido"},
        )
        self.tabela_vendas.pack(fill="both", expand=True)
        self.tabela_estoque = self.criar_tabela(
            estoque_frame,
            ("categoria", "quantidade", "valor_total"),
            {"categoria": "Categoria", "quantidade": "Unidades em estoque", "valor_total": "Valor em estoque"},
        )
        self.tabela_estoque.pack(fill="both", expand=True)
        self.status = tk.Label(container, text="Relatório atualizado.", bg="#111827", fg="#cbd5e1", anchor="w")
        self.status.pack(fill="x", pady=(10, 0))

    @staticmethod
    def criar_tabela(parent, colunas, cabecalhos):
        tabela = ttk.Treeview(parent, columns=colunas, show="headings", height=14)
        for coluna in colunas:
            tabela.heading(coluna, text=cabecalhos[coluna])
            tabela.column(coluna, anchor="center", width=180)
        return tabela

    def limpar_filtros(self):
        self.filtro_produto.delete(0, tk.END)
        self.data_inicio.delete(0, tk.END)
        self.data_fim.delete(0, tk.END)
        self.atualizar_relatorio()

    def atualizar_relatorio(self):
        inicio = self.data_inicio.get().strip()
        fim = self.data_fim.get().strip()
        try:
            resumo_vendas = resumo_vendas_por_produto(
                self.controller.vendas,
                self.filtro_produto.get(),
                inicio,
                fim,
            )
        except ValueError:
            messagebox.showwarning("Filtro inválido", "Informe datas válidas no formato AAAA-MM-DD e confira o intervalo.")
            return

        for tabela in (self.tabela_vendas, self.tabela_estoque):
            tabela.delete(*tabela.get_children())

        for item in resumo_vendas:
            self.tabela_vendas.insert(
                "", "end", values=(item["nome"], item["quantidade"], f"R$ {item['valor_total']:.2f}")
            )

        resumo_estoque = valor_estoque_por_categoria(self.controller.pecas)
        for item in resumo_estoque:
            self.tabela_estoque.insert(
                "", "end", values=(item["categoria"], item["quantidade"], f"R$ {item['valor_total']:.2f}")
            )

        total_filtrado = sum(item["valor_total"] for item in resumo_vendas)
        self.total_vendas.config(text=f"Vendas no período: R$ {total_filtrado:.2f}")
        self.total_estoque.config(text=f"Valor estimado do estoque: R$ {total_valor_estoque(self.controller.pecas):.2f}")
        self.status.config(text=f"{len(resumo_vendas)} produto(s) com vendas no filtro atual.")


class MenuView:
    def __init__(self, controller):
        self.controller = controller
        self.frame = tk.Frame(controller.root, bg="#0f172a")

        container = tk.Frame(self.frame, bg="#111827", padx=40, pady=40)
        container.pack(fill="both", expand=True)

        titulo = tk.Label(
            container,
            text="AutoPeças",
            font=("Arial", 28, "bold"),
            bg="#111827",
            fg="#f8fafc",
        )
        titulo.pack(pady=(0, 8))

        sub = tk.Label(
            container,
            text="Controle de estoque e vendas",
            font=("Arial", 12),
            bg="#111827",
            fg="#cbd5e1",
        )
        sub.pack(pady=(0, 30))

        botoes = tk.Frame(container, bg="#111827")
        botoes.pack()

        self.btn_cadastro = tk.Button(
            botoes,
            text="Cadastro",
            width=22,
            height=2,
            bg="#22c55e",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.controller.mostrar_cadastro,
        )
        self.btn_cadastro.pack(pady=10)

        self.btn_consulta = tk.Button(
            botoes,
            text="Consulta",
            width=22,
            height=2,
            bg="#3b82f6",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.controller.mostrar_consulta,
        )
        self.btn_consulta.pack(pady=10)

        self.btn_vendas = tk.Button(
            botoes,
            text="Vendas",
            width=22,
            height=2,
            bg="#f97316",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.controller.mostrar_vendas,
        )
        self.btn_vendas.pack(pady=10)

        self.btn_financeiro = tk.Button(
            botoes,
            text="Consulta Financeira",
            width=22,
            height=2,
            bg="#0ea5e9",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.controller.mostrar_financeiro,
        )
        self.btn_financeiro.pack(pady=10)

        self.usuario_sessao = tk.Label(
            container,
            text="",
            bg="#111827",
            fg="#cbd5e1",
            font=("Arial", 10),
        )
        self.usuario_sessao.pack(pady=(18, 0))

        self.btn_usuarios = tk.Button(
            botoes,
            text="Gerenciar Usuários",
            width=22,
            height=2,
            bg="#64748b",
            fg="white",
            font=("Arial", 12, "bold"),
            command=self.controller.mostrar_usuarios,
        )

        self.btn_sair = tk.Button(
            container,
            text="Sair da sessão",
            command=self.controller.logout,
            bg="#475569",
            fg="white",
            font=("Arial", 9, "bold"),
        )
        self.btn_sair.pack(pady=(12, 0))
        self.atualizar_sessao()

    def atualizar_sessao(self):
        usuario = self.controller.active_user
        if not usuario:
            self.btn_cadastro.pack_forget()
            self.btn_consulta.pack_forget()
            self.btn_vendas.pack_forget()
            self.btn_financeiro.pack_forget()
            self.btn_usuarios.pack_forget()
            self.usuario_sessao.config(text="")
            return
        self.usuario_sessao.config(text=f"Sessão: {usuario['username']}")
        self.btn_consulta.pack(pady=10)
        self.btn_vendas.pack(pady=10)
        if usuario.get("role") == "admin":
            self.btn_cadastro.pack(pady=10)
            self.btn_financeiro.pack(pady=10)
            self.btn_usuarios.pack(pady=10)
        else:
            self.btn_cadastro.pack_forget()
            self.btn_financeiro.pack_forget()
            self.btn_usuarios.pack_forget()


class AppController:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("AutoPeças")
        self.root.geometry("900x650")
        self.root.configure(bg="#0f172a")
        self.root.resizable(False, False)

        self.active_user = None
        self.auth_service = AuthService(REPOSITORY)
        self.pecas = carregar_pecas()
        self.vendas = carregar_vendas()
        self.login_view = LoginView(self, self.auth_service)
        self.user_management_view = UserManagementView(self, self.auth_service)
        self.menu_view = MenuView(self)
        self.cadastro_view = CadastroView(self)
        self.consulta_view = ConsultaView(self)
        self.vendas_view = VendasView(self)
        self.financeiro_view = ConsultaFinanceiraView(self)
        self.frames = [
            self.login_view.frame,
            self.menu_view.frame,
            self.cadastro_view.frame,
            self.consulta_view.frame,
            self.vendas_view.frame,
            self.financeiro_view.frame,
            self.user_management_view.frame,
        ]
        for frame in self.frames:
            frame.pack_forget()
        self.mostrar_autenticacao()

    def mostrar_autenticacao(self):
        for frame in self.frames:
            frame.pack_forget()
        self.login_view.frame.pack(fill="both", expand=True)
        self.login_view.show()

    def login_success(self, user):
        self.active_user = user
        self.menu_view.atualizar_sessao()
        self.consulta_view.atualizar_permissoes()
        self.mostrar_menu()

    def logout(self):
        self.active_user = None
        self.mostrar_autenticacao()

    def mostrar_menu(self):
        for frame in self.frames:
            frame.pack_forget()
        self.menu_view.frame.pack(fill="both", expand=True)

    def mostrar_cadastro(self, indice=None):
        if not self.tem_permissao("gerenciar_estoque"):
            messagebox.showwarning("Acesso restrito", "Somente administradores podem cadastrar ou editar produtos.")
            return
        for frame in self.frames:
            frame.pack_forget()
        self.cadastro_view.atualizar_opcoes_produtos()
        if indice is None:
            self.cadastro_view.iniciar_novo_produto()
        else:
            self.cadastro_view.preencher_formulario(self.pecas[indice], indice)
        self.cadastro_view.frame.pack(fill="both", expand=True)

    def mostrar_consulta(self):
        if not self.tem_permissao("consultar_estoque"):
            messagebox.showwarning("Acesso restrito", "Entre no sistema para consultar o estoque.")
            return
        for frame in self.frames:
            frame.pack_forget()
        self.consulta_view.atualizar_permissoes()
        self.consulta_view.atualizar_lista()
        self.consulta_view.frame.pack(fill="both", expand=True)

    def mostrar_vendas(self):
        if not self.tem_permissao("registrar_vendas"):
            messagebox.showwarning("Acesso restrito", "Entre no sistema para acessar as vendas.")
            return
        for frame in self.frames:
            frame.pack_forget()
        self.vendas_view.limpar_produto_selecionado()
        self.vendas_view.atualizar_historico()
        self.vendas_view.frame.pack(fill="both", expand=True)

    def mostrar_financeiro(self):
        if not self.tem_permissao("consultar_financeiro"):
            messagebox.showwarning("Acesso restrito", "Somente administradores podem consultar os relatórios financeiros.")
            return
        for frame in self.frames:
            frame.pack_forget()
        self.financeiro_view.atualizar_relatorio()
        self.financeiro_view.frame.pack(fill="both", expand=True)

    def mostrar_usuarios(self):
        if not self.tem_permissao("gerenciar_usuarios"):
            messagebox.showwarning("Acesso restrito", "Somente administradores podem gerenciar usuários.")
            return
        for frame in self.frames:
            frame.pack_forget()
        self.user_management_view.atualizar_lista()
        self.user_management_view.frame.pack(fill="both", expand=True)

    def tem_permissao(self, permissao):
        return self.auth_service.has_permission(self.active_user, permissao)

    def iniciar(self):
        self.root.mainloop()


def main():
    app = AppController()
    app.iniciar()


if __name__ == "__main__":
    main()
