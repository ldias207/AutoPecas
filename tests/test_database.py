import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from database import SQLiteRepository
from auth import AuthService


class TestSQLiteRepository(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_path = Path(self.temp_dir.name)
        self.database_path = self.base_path / "autopecas.db"
        self.stock_path = self.base_path / "estoque_autopecas.json"
        self.sales_path = self.base_path / "vendas_autopecas.json"
        self.parts = [{
            "nome": "Pastilha",
            "marca": "Bosch",
            "numero_fabrica": "PA-10",
            "categoria": "Freio",
            "quantidade": 8,
            "preco": 25.5,
            "status": "Disponível",
        }]

    def tearDown(self):
        self.temp_dir.cleanup()

    def criar_repositorio(self):
        return SQLiteRepository(self.database_path, self.stock_path, self.sales_path)

    def test_migra_json_uma_vez_e_preserva_arquivos_originais(self):
        legado_vendas = [{
            "nome": "Filtro",
            "quantidade": 2,
            "valor_total": 30.0,
            "data": "2026-10-20",
        }]
        self.stock_path.write_text(json.dumps(self.parts), encoding="utf-8")
        self.sales_path.write_text(json.dumps(legado_vendas), encoding="utf-8")
        conteudo_estoque_original = self.stock_path.read_text(encoding="utf-8")
        conteudo_vendas_original = self.sales_path.read_text(encoding="utf-8")

        repository = self.criar_repositorio()
        loaded_parts = repository.load_parts()
        self.assertEqual(len(loaded_parts), 1)
        self.assertEqual({key: loaded_parts[0][key] for key in self.parts[0]}, self.parts[0])
        self.assertEqual(repository.load_sales()[0]["nome"], "Filtro")

        repository.save_parts([])
        repository.save_sales([])
        repository = self.criar_repositorio()

        self.assertEqual(repository.load_parts(), [])
        self.assertEqual(repository.load_sales(), [])
        self.assertEqual(self.stock_path.read_text(encoding="utf-8"), conteudo_estoque_original)
        self.assertEqual(self.sales_path.read_text(encoding="utf-8"), conteudo_vendas_original)

    def test_registrar_venda_atualiza_estoque_e_historico(self):
        repository = self.criar_repositorio()
        repository.save_parts(self.parts)
        auth = AuthService(repository)
        auth.create_initial_admin("admin", "SenhaForte123")
        admin = auth.authenticate("admin", "SenhaForte123")

        part_id = repository.load_parts()[0]["id"]
        sale = repository.register_sale(part_id, 3, admin["id"])

        self.assertEqual(sale["quantidade"], 3)
        self.assertEqual(sale["valor_total"], 76.5)
        self.assertEqual(sale["preco_unitario"], 25.5)
        self.assertEqual(sale["produto_id"], part_id)
        self.assertEqual(sale["usuario_id"], admin["id"])
        self.assertEqual(repository.load_parts()[0]["quantidade"], 5)
        self.assertEqual(repository.load_parts()[0]["status"], "Disponível")
        self.assertEqual(sale["status"], "Disponível")
        stored_sale = repository.load_sales()[0]
        self.assertEqual(stored_sale["produto_id"], part_id)
        self.assertEqual(stored_sale["usuario_id"], admin["id"])
        self.assertEqual(stored_sale["preco_unitario"], 25.5)
        self.assertEqual(stored_sale["usuario"], "admin")

    def test_venda_invalida_nao_altera_estoque_nem_historico(self):
        repository = self.criar_repositorio()
        repository.save_parts(self.parts)

        part_id = repository.load_parts()[0]["id"]
        sale = repository.register_sale(part_id, 20, 1)

        self.assertIsNone(sale)
        self.assertEqual(repository.load_parts()[0]["quantidade"], 8)
        self.assertEqual(repository.load_sales(), [])

    def test_historico_legado_mantem_venda_sem_atribuicoes(self):
        self.sales_path.write_text(json.dumps([{
            "nome": "Pastilha",
            "quantidade": 1,
            "valor_total": 25.5,
            "data": "2026-10-20",
        }]), encoding="utf-8")

        repository = self.criar_repositorio()
        venda = repository.load_sales()[0]

        self.assertIsNone(venda["produto_id"])
        self.assertIsNone(venda["usuario_id"])
        self.assertEqual(venda["preco_unitario"], 25.5)

    def test_persistencia_de_pecas_apos_reabrir(self):
        repository = self.criar_repositorio()
        repository.save_parts(self.parts)

        reopened = SQLiteRepository(self.database_path, self.stock_path, self.sales_path)

        loaded_part = reopened.load_parts()[0]
        self.assertEqual({key: loaded_part[key] for key in self.parts[0]}, self.parts[0])
        self.assertIsNotNone(loaded_part["id"])

    def test_edicao_preserva_identidade_do_produto_ligado_a_venda(self):
        repository = self.criar_repositorio()
        repository.save_parts(self.parts)
        auth = AuthService(repository)
        auth.create_initial_admin("admin", "SenhaForte123")
        admin = auth.authenticate("admin", "SenhaForte123")
        product_id = repository.load_parts()[0]["id"]
        repository.register_sale(product_id, 1, admin["id"])

        part = repository.load_parts()[0]
        part["preco"] = 30.0
        repository.save_parts([part])

        self.assertEqual(repository.load_parts()[0]["id"], product_id)
        sale = repository.load_sales()[0]
        self.assertEqual(sale["produto_id"], product_id)
        self.assertEqual(sale["preco_unitario"], 25.5)

    def test_migra_esquema_antigo_sem_perder_vendas(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.executescript(
                """
                CREATE TABLE pecas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    marca TEXT NOT NULL,
                    numero_fabrica TEXT NOT NULL,
                    categoria TEXT NOT NULL,
                    quantidade INTEGER NOT NULL,
                    preco REAL NOT NULL,
                    status TEXT NOT NULL
                );
                CREATE TABLE vendas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL,
                    quantidade INTEGER NOT NULL,
                    valor_total REAL NOT NULL,
                    data TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'Disponível'
                );
                CREATE TABLE metadata (chave TEXT PRIMARY KEY, valor TEXT NOT NULL);
                CREATE TABLE usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL,
                    criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                INSERT INTO vendas (nome, quantidade, valor_total, data)
                VALUES ('Pastilha', 2, 51.0, '2026-10-20');
                """
            )
        finally:
            connection.close()

        repository = self.criar_repositorio()
        sale = repository.load_sales()[0]

        self.assertEqual(sale["nome"], "Pastilha")
        self.assertEqual(sale["preco_unitario"], 25.5)
        self.assertIsNone(sale["produto_id"])
        self.assertIsNone(sale["usuario_id"])

    def test_migracao_normaliza_status_de_acordo_com_quantidade(self):
        pecas_legadas = [
            {**self.parts[0], "quantidade": 0, "status": "Disponível"},
            {**self.parts[0], "nome": "Correia", "quantidade": 5, "status": "Em breve"},
        ]
        self.stock_path.write_text(json.dumps(pecas_legadas), encoding="utf-8")
        repository = self.criar_repositorio()

        self.assertEqual([p["status"] for p in repository.load_parts()], ["Esgotado", "Disponível"])

    def test_salvar_pecas_deriva_status_da_quantidade(self):
        repository = self.criar_repositorio()
        pecas = [
            {**self.parts[0], "quantidade": 0, "status": "Disponível"},
            {**self.parts[0], "nome": "Correia", "quantidade": 5, "status": "Em breve"},
        ]

        repository.save_parts(pecas)

        self.assertEqual([p["status"] for p in repository.load_parts()], ["Esgotado", "Disponível"])


if __name__ == "__main__":
    unittest.main()