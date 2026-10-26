import tkinter as tk
from tkinter import messagebox, ttk


class LoginView:
    def __init__(self, controller, auth_service):
        self.controller = controller
        self.auth_service = auth_service
        self.frame = tk.Frame(controller.root, bg="#0f172a")
        self.login_panel = tk.Frame(self.frame, bg="#111827", padx=36, pady=32)
        self.setup_panel = tk.Frame(self.frame, bg="#111827", padx=36, pady=32)
        self._build_login()
        self._build_first_admin()

    @staticmethod
    def _field(parent, label):
        tk.Label(parent, text=label, bg="#111827", fg="#e2e8f0", font=("Arial", 10)).pack(anchor="w", pady=(12, 4))
        entry = tk.Entry(parent, font=("Arial", 11), width=34, show="*" if label.startswith("Senha") or label == "Confirmar senha" else "")
        entry.pack(fill="x")
        return entry

    def _build_login(self):
        tk.Label(self.login_panel, text="AutoPeças", bg="#111827", fg="#f8fafc", font=("Arial", 25, "bold")).pack()
        tk.Label(self.login_panel, text="Acesse sua conta", bg="#111827", fg="#cbd5e1", font=("Arial", 11)).pack(pady=(6, 18))
        self.login_username = self._field(self.login_panel, "Usuário")
        self.login_password = self._field(self.login_panel, "Senha")
        tk.Button(
            self.login_panel,
            text="Entrar",
            command=self._login,
            bg="#22c55e",
            fg="white",
            font=("Arial", 11, "bold"),
        ).pack(fill="x", pady=(20, 0), ipady=6)

    def _build_first_admin(self):
        tk.Label(self.setup_panel, text="Configuração inicial", bg="#111827", fg="#f8fafc", font=("Arial", 22, "bold")).pack()
        tk.Label(
            self.setup_panel,
            text="Crie a primeira conta administradora para começar.",
            bg="#111827",
            fg="#cbd5e1",
            font=("Arial", 10),
        ).pack(pady=(8, 12))
        self.admin_username = self._field(self.setup_panel, "Usuário administrador")
        self.admin_password = self._field(self.setup_panel, "Senha")
        self.admin_password_confirm = self._field(self.setup_panel, "Confirmar senha")
        tk.Button(
            self.setup_panel,
            text="Criar administrador",
            command=self._create_first_admin,
            bg="#22c55e",
            fg="white",
            font=("Arial", 11, "bold"),
        ).pack(fill="x", pady=(20, 0), ipady=6)

    def show(self):
        if self.auth_service.has_users():
            self.show_login()
        else:
            self.show_initial_admin()

    def show_login(self):
        self.login_panel.pack_forget()
        self.setup_panel.pack_forget()
        self.login_panel.pack(expand=True)
        self.login_username.focus_set()

    def show_initial_admin(self):
        self.login_panel.pack_forget()
        self.setup_panel.pack_forget()
        self.setup_panel.pack(expand=True)
        self.admin_username.focus_set()

    def _login(self):
        user = self.auth_service.authenticate(self.login_username.get(), self.login_password.get())
        if not user:
            messagebox.showerror("Acesso negado", "Usuário ou senha inválidos.", parent=self.controller.root)
            return
        self.login_password.delete(0, tk.END)
        self.controller.login_success(user)

    def _create_first_admin(self):
        password = self.admin_password.get()
        if password != self.admin_password_confirm.get():
            messagebox.showwarning("Senhas diferentes", "Confirme a mesma senha nos dois campos.", parent=self.controller.root)
            return
        try:
            self.auth_service.create_initial_admin(self.admin_username.get(), password)
        except ValueError as error:
            messagebox.showwarning("Cadastro inválido", str(error), parent=self.controller.root)
            return
        user = self.auth_service.authenticate(self.admin_username.get(), password)
        for entry in (self.admin_password, self.admin_password_confirm):
            entry.delete(0, tk.END)
        self.controller.login_success(user)


class UserManagementView:
    def __init__(self, controller, auth_service):
        self.controller = controller
        self.auth_service = auth_service
        self.frame = tk.Frame(controller.root, bg="#111827")
        self._build()

    def _build(self):
        container = tk.Frame(self.frame, bg="#111827", padx=28, pady=24)
        container.pack(fill="both", expand=True)
        header = tk.Frame(container, bg="#111827")
        header.pack(fill="x")
        tk.Label(header, text="Gerenciamento de Usuários", bg="#111827", fg="#f9fafb", font=("Arial", 22, "bold")).pack(side="left")
        tk.Button(
            header,
            text="Voltar ao menu",
            command=self.controller.mostrar_menu,
            bg="#f59e0b",
            fg="black",
            font=("Arial", 10, "bold"),
        ).pack(side="right")

        form = tk.Frame(container, bg="#1f2937", padx=16, pady=14)
        form.pack(fill="x", pady=18)
        tk.Label(form, text="Novo usuário", bg="#1f2937", fg="#f9fafb", font=("Arial", 13, "bold")).grid(row=0, column=0, columnspan=4, sticky="w", pady=(0, 10))
        tk.Label(form, text="Usuário", bg="#1f2937", fg="#e2e8f0").grid(row=1, column=0, sticky="w")
        self.username = tk.Entry(form, font=("Arial", 10), width=22)
        self.username.grid(row=1, column=1, padx=(8, 18), sticky="ew")
        tk.Label(form, text="Senha", bg="#1f2937", fg="#e2e8f0").grid(row=1, column=2, sticky="w")
        self.password = tk.Entry(form, font=("Arial", 10), width=22, show="*")
        self.password.grid(row=1, column=3, padx=8, sticky="ew")
        tk.Button(
            form,
            text="Cadastrar usuário",
            command=self._create_user,
            bg="#22c55e",
            fg="white",
            font=("Arial", 10, "bold"),
        ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(14, 0))
        form.columnconfigure(1, weight=1)
        form.columnconfigure(3, weight=1)

        tk.Label(container, text="Contas cadastradas", bg="#111827", fg="#f9fafb", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 8))
        self.table = ttk.Treeview(container, columns=("username", "role", "created"), show="headings", height=12)
        for key, title, width in (
            ("username", "Usuário", 260),
            ("role", "Perfil", 160),
            ("created", "Criado em", 220),
        ):
            self.table.heading(key, text=title)
            self.table.column(key, width=width, anchor="center")
        self.table.pack(fill="both", expand=True)
        tk.Button(
            container,
            text="Remover usuário selecionado",
            command=self._delete_user,
            bg="#ef4444",
            fg="white",
            font=("Arial", 9, "bold"),
        ).pack(anchor="w", pady=(10, 0))
        self.status = tk.Label(container, text="", bg="#111827", fg="#86efac", anchor="w")
        self.status.pack(fill="x", pady=(10, 0))

    def atualizar_lista(self):
        self.table.delete(*self.table.get_children())
        for user in self.auth_service.repository.list_users():
            perfil = "Administrador" if user["role"] == "admin" else "Operacional"
            self.table.insert("", "end", values=(user["username"], perfil, user["criado_em"]))

    def _create_user(self):
        try:
            self.auth_service.create_user(
                self.username.get(), self.password.get(), self.controller.active_user
            )
        except (ValueError, PermissionError) as error:
            messagebox.showwarning("Não foi possível cadastrar", str(error), parent=self.controller.root)
            return
        self.username.delete(0, tk.END)
        self.password.delete(0, tk.END)
        self.status.config(text="Usuário cadastrado com perfil operacional.")
        self.atualizar_lista()

    def _delete_user(self):
        selection = self.table.selection()
        if not selection:
            messagebox.showwarning("Seleção necessária", "Selecione um usuário para remover.", parent=self.controller.root)
            return
        username = self.table.item(selection[0], "values")[0]
        if not messagebox.askyesno(
            "Confirmar remoção",
            f"Deseja realmente remover o usuário '{username}'?",
            parent=self.controller.root,
        ):
            return
        try:
            self.auth_service.delete_user(username, self.controller.active_user)
        except (ValueError, PermissionError) as error:
            messagebox.showwarning("Não foi possível remover", str(error), parent=self.controller.root)
            return
        self.status.config(text=f"Usuário removido: {username}")
        self.atualizar_lista()