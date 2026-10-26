import json
import sqlite3
from contextlib import contextmanager
from datetime import date
from pathlib import Path


class SQLiteRepository:
    def __init__(self, database_path, legacy_stock_path=None, legacy_sales_path=None):
        self.database_path = Path(database_path)
        self.legacy_stock_path = Path(legacy_stock_path) if legacy_stock_path else None
        self.legacy_sales_path = Path(legacy_sales_path) if legacy_sales_path else None
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._create_schema()
        self._migrate_json_once()

    def _connect(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self):
        connection = self._connect()
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _create_schema(self):
        with self._connection() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS pecas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    marca TEXT NOT NULL,
                    numero_fabrica TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    quantidade INTEGER NOT NULL CHECK (quantidade >= 0),
                    preco REAL NOT NULL CHECK (preco >= 0),
                    status TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS vendas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    quantidade INTEGER NOT NULL CHECK (quantidade > 0),
                    valor_total REAL NOT NULL CHECK (valor_total >= 0),
                    data TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Disponível',
                    produto_id INTEGER REFERENCES pecas(id) ON DELETE SET NULL,
                    preco_unitario REAL,
                    usuario_id INTEGER REFERENCES usuarios(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS metadata (
                    chave TEXT PRIMARY KEY,
                    valor TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (role IN ('admin', 'user')),
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                """
            )
            self._ensure_column(connection, "vendas", "produto_id", "INTEGER REFERENCES pecas(id) ON DELETE SET NULL")
            self._ensure_column(connection, "vendas", "preco_unitario", "REAL")
            self._ensure_column(connection, "vendas", "usuario_id", "INTEGER REFERENCES usuarios(id) ON DELETE SET NULL")
            connection.execute(
                "UPDATE vendas SET preco_unitario = valor_total / quantidade WHERE preco_unitario IS NULL AND quantidade > 0"
            )
            connection.execute(
                """UPDATE pecas
                SET status = CASE WHEN quantidade <= 0 THEN 'Esgotado' ELSE 'Disponível' END"""
            )

    @staticmethod
    def _ensure_column(connection, table, column, definition):
        columns = {row["name"] for row in connection.execute(f"PRAGMA table_info({table})")}
        if column not in columns:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")

    def has_users(self):
        with self._connection() as connection:
            return connection.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone() is not None

    def get_user(self, username):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role FROM usuarios WHERE username = ?",
                (username,),
            ).fetchone()
        return dict(row) if row else None

    def get_user_by_id(self, user_id):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT id, username, password_hash, role FROM usuarios WHERE id = ?",
                (user_id,),
            ).fetchone()
        return dict(row) if row else None

    def list_users(self):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, username, role, criado_em FROM usuarios ORDER BY username COLLATE NOCASE"
            ).fetchall()
        return [dict(row) for row in rows]

    def create_user(self, username, password_hash, role):
        with self._connection() as connection:
            try:
                cursor = connection.execute(
                    "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, ?)",
                    (username, password_hash, role),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Esse nome de usuário já está cadastrado.") from error
            return cursor.lastrowid

    def create_initial_admin(self, username, password_hash):
        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if connection.execute("SELECT 1 FROM usuarios LIMIT 1").fetchone():
                raise ValueError("O administrador inicial já foi criado.")
            try:
                cursor = connection.execute(
                    "INSERT INTO usuarios (username, password_hash, role) VALUES (?, ?, 'admin')",
                    (username, password_hash),
                )
            except sqlite3.IntegrityError as error:
                raise ValueError("Esse nome de usuário já está cadastrado.") from error
            return cursor.lastrowid

    def delete_user(self, username):
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM usuarios WHERE username = ?", (username,))
            return cursor.rowcount > 0

    @staticmethod
    def _read_json_list(path):
        if not path or not path.exists():
            return []
        try:
            with path.open("r", encoding="utf-8") as file:
                value = json.load(file)
        except (OSError, json.JSONDecodeError):
            return []
        return value if isinstance(value, list) else []

    def _migrate_json_once(self):
        with self._connection() as connection:
            migrated = connection.execute(
                "SELECT valor FROM metadata WHERE chave = ?", ("json_migrado",)
            ).fetchone()
            if migrated:
                return

            parts = self._read_json_list(self.legacy_stock_path)
            sales = self._read_json_list(self.legacy_sales_path)

            for part in parts:
                if not isinstance(part, dict):
                    continue
                try:
                    quantity = int(part.get("quantidade", 0))
                    price = float(part.get("preco", 0))
                    fields = (
                        str(part.get("nome", "")).strip(),
                        str(part.get("marca", "")).strip(),
                        str(part.get("numero_fabrica", "")).strip(),
                        str(part.get("categoria", "")).strip(),
                        quantity,
                        price,
                        "Esgotado" if quantity <= 0 else "Disponível",
                    )
                    if not all(fields[:4]) or not fields[6] or quantity < 0 or price < 0:
                        continue
                except (TypeError, ValueError):
                    continue
                connection.execute(
                    """INSERT INTO pecas
                    (nome, marca, numero_fabrica, categoria, quantidade, preco, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    fields,
                )

            for sale in sales:
                if not isinstance(sale, dict):
                    continue
                try:
                    name = str(sale.get("nome", "Peça")).strip() or "Peça"
                    quantity = int(sale.get("quantidade", 0))
                    total = float(sale.get("valor_total", 0))
                    if quantity <= 0 or total < 0:
                        continue
                except (TypeError, ValueError):
                    continue
                connection.execute(
                    """INSERT INTO vendas
                    (nome, quantidade, valor_total, data, status, preco_unitario)
                    VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        name,
                        quantity,
                        total,
                        str(sale.get("data", "")),
                        str(sale.get("status", "Disponível")),
                        total / quantity,
                    ),
                )

            connection.execute(
                "INSERT INTO metadata (chave, valor) VALUES (?, ?)",
                ("json_migrado", "1"),
            )

    @staticmethod
    def _part_dict(row):
        return {
            "id": row["id"],
            "nome": row["nome"],
            "marca": row["marca"],
            "numero_fabrica": row["numero_fabrica"],
            "categoria": row["categoria"],
            "quantidade": row["quantidade"],
            "preco": row["preco"],
            "status": row["status"],
        }

    @staticmethod
    def _sale_dict(row):
        return {
            "nome": row["nome"],
            "quantidade": row["quantidade"],
            "valor_total": row["valor_total"],
            "data": row["data"],
            "status": row["status"],
            "produto_id": row["produto_id"],
            "preco_unitario": row["preco_unitario"],
            "usuario_id": row["usuario_id"],
            "usuario": row["usuario"],
        }

    def load_parts(self):
        with self._connection() as connection:
            rows = connection.execute("SELECT * FROM pecas ORDER BY id").fetchall()
        return [self._part_dict(row) for row in rows]

    def create_part(self, part):
        quantity = int(part["quantidade"])
        fields = (
            part["nome"],
            part["marca"],
            part["numero_fabrica"],
            part["categoria"],
            quantity,
            float(part["preco"]),
            "Esgotado" if quantity <= 0 else "Disponível",
        )
        with self._connection() as connection:
            cursor = connection.execute(
                """INSERT INTO pecas
                (nome, marca, numero_fabrica, categoria, quantidade, preco, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                fields,
            )
            row = connection.execute("SELECT * FROM pecas WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return self._part_dict(row)

    def update_part(self, part_id, part):
        quantity = int(part["quantidade"])
        fields = (
            part["nome"],
            part["marca"],
            part["numero_fabrica"],
            part["categoria"],
            quantity,
            float(part["preco"]),
            "Esgotado" if quantity <= 0 else "Disponível",
            part_id,
        )
        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE pecas SET nome = ?, marca = ?, numero_fabrica = ?, categoria = ?,
                quantidade = ?, preco = ?, status = ? WHERE id = ?""",
                fields,
            )
            if not cursor.rowcount:
                return None
            row = connection.execute("SELECT * FROM pecas WHERE id = ?", (part_id,)).fetchone()
        return self._part_dict(row)

    def delete_part(self, part_id):
        with self._connection() as connection:
            cursor = connection.execute("DELETE FROM pecas WHERE id = ?", (part_id,))
        return cursor.rowcount > 0

    def load_sales(self):
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT vendas.*, usuarios.username AS usuario
                FROM vendas LEFT JOIN usuarios ON usuarios.id = vendas.usuario_id
                ORDER BY vendas.id"""
            ).fetchall()
        return [self._sale_dict(row) for row in rows]

    def save_parts(self, parts):
        with self._connection() as connection:
            retained_ids = []
            for part in parts:
                quantity = int(part.get("quantidade", 0))
                fields = (
                    part.get("nome", ""),
                    part.get("marca", ""),
                    part.get("numero_fabrica", ""),
                    part.get("categoria", ""),
                    quantity,
                    float(part.get("preco", 0)),
                    "Esgotado" if quantity <= 0 else "Disponível",
                )
                part_id = part.get("id")
                if part_id is not None:
                    cursor = connection.execute(
                        """UPDATE pecas SET nome = ?, marca = ?, numero_fabrica = ?, categoria = ?,
                        quantidade = ?, preco = ?, status = ? WHERE id = ?""",
                        (*fields, part_id),
                    )
                    if cursor.rowcount:
                        retained_ids.append(part_id)
                        continue
                cursor = connection.execute(
                    """INSERT INTO pecas
                    (nome, marca, numero_fabrica, categoria, quantidade, preco, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    fields,
                )
                part["id"] = cursor.lastrowid
                retained_ids.append(cursor.lastrowid)

            if retained_ids:
                placeholders = ",".join("?" for _ in retained_ids)
                connection.execute(f"DELETE FROM pecas WHERE id NOT IN ({placeholders})", retained_ids)
            else:
                connection.execute("DELETE FROM pecas")

    def save_sales(self, sales):
        with self._connection() as connection:
            connection.execute("DELETE FROM vendas")
            connection.executemany(
                """INSERT INTO vendas (nome, quantidade, valor_total, data, status)
                VALUES (?, ?, ?, ?, ?)""",
                [
                    (
                        sale.get("nome", "Peça"),
                        int(sale.get("quantidade", 0)),
                        float(sale.get("valor_total", 0)),
                        sale.get("data", ""),
                        sale.get("status", "Disponível"),
                    )
                    for sale in sales
                ],
            )

    def register_sale(self, part_id, quantity, user_id):
        with self._connection() as connection:
            row = connection.execute("SELECT * FROM pecas WHERE id = ?", (part_id,)).fetchone()
            if not row:
                return None

            part = self._part_dict(row)
            try:
                quantity = int(quantity)
                current_quantity = int(part["quantidade"])
                price = float(part["preco"])
            except (TypeError, ValueError):
                return None
            if quantity <= 0 or quantity > current_quantity:
                return None

            remaining = current_quantity - quantity
            new_status = "Esgotado" if remaining <= 0 else "Disponível"
            sale = {
                "nome": part["nome"],
                "quantidade": quantity,
                "valor_total": round(price * quantity, 2),
                "preco_unitario": price,
                "data": date.today().isoformat(),
                "status": new_status,
                "produto_id": part_id,
                "usuario_id": user_id,
            }
            connection.execute(
                """UPDATE pecas SET quantidade = ?, status = ? WHERE id = ?""",
                (remaining, new_status, part_id),
            )
            connection.execute(
                """INSERT INTO vendas
                (nome, quantidade, valor_total, data, status, produto_id, preco_unitario, usuario_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    sale["nome"],
                    sale["quantidade"],
                    sale["valor_total"],
                    sale["data"],
                    sale["status"],
                    sale["produto_id"],
                    sale["preco_unitario"],
                    sale["usuario_id"],
                ),
            )
            return sale