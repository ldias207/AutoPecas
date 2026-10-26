import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from api import create_app
from auth import AuthService
from database import SQLiteRepository


class TestAutopecasApi(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_dir.name) / "api-test.db"
        self.repository = SQLiteRepository(database_path)
        self.auth = AuthService(self.repository)
        self.auth.create_initial_admin("admin", "SenhaAdmin123")
        self.admin = self.auth.authenticate("admin", "SenhaAdmin123")
        self.auth.create_user("vendedor", "SenhaVendedor123", self.admin)
        self.app = create_app(self.repository, b"test-secret-for-api")
        self.client = TestClient(self.app)
        self.admin_token = self.login("admin", "SenhaAdmin123")
        self.operator_token = self.login("vendedor", "SenhaVendedor123")

    def tearDown(self):
        self.client.close()
        self.temp_dir.cleanup()

    def login(self, username, password):
        response = self.client.post("/auth/login", json={"username": username, "password": password})
        self.assertEqual(response.status_code, 200)
        return response.json()["access_token"]

    @staticmethod
    def headers(token):
        return {"Authorization": f"Bearer {token}"}

    def test_operador_consulta_estoque_sem_poder_criar_produto(self):
        product = {
            "nome": "Pastilha",
            "marca": "Bosch",
            "numero_fabrica": "PA-10",
            "categoria": "Freio",
            "quantidade": 8,
            "preco": 25.5,
        }
        created = self.client.post("/products", json=product, headers=self.headers(self.admin_token))
        self.assertEqual(created.status_code, 201)

        result = self.client.get("/products?q=bosch", headers=self.headers(self.operator_token))
        denied = self.client.post("/products", json=product, headers=self.headers(self.operator_token))

        self.assertEqual(result.status_code, 200)
        self.assertEqual(len(result.json()), 1)
        self.assertEqual(denied.status_code, 403)

    def test_produto_preserva_preco_de_custo_e_preco_de_venda(self):
        response = self.client.post("/products", json={
            "nome": "Filtro",
            "marca": "Bosch",
            "numero_fabrica": "FI-21",
            "categoria": "Motor",
            "quantidade": 4,
            "preco_custo": 12.5,
            "preco": 19.9,
        }, headers=self.headers(self.admin_token))
        product = self.client.get("/products", headers=self.headers(self.operator_token)).json()[0]

        self.assertEqual(response.status_code, 201)
        self.assertEqual(product["preco_custo"], 12.5)
        self.assertEqual(product["preco"], 19.9)

    def test_venda_registra_usuario_produto_preco_e_reduz_estoque(self):
        product = self.client.post(
            "/products",
            json={
                "nome": "Filtro",
                "marca": "Bosch",
                "numero_fabrica": "FI-21",
                "categoria": "Motor",
                "quantidade": 4,
                "preco": 19.9,
            },
            headers=self.headers(self.admin_token),
        ).json()

        sale = self.client.post(
            "/sales",
            json={"produto_id": product["id"], "quantidade": 2},
            headers=self.headers(self.operator_token),
        )
        stored = self.client.get("/sales", headers=self.headers(self.operator_token)).json()[0]
        updated_product = self.client.get("/products", headers=self.headers(self.operator_token)).json()[0]

        self.assertEqual(sale.status_code, 201)
        self.assertEqual(stored["produto_id"], product["id"])
        self.assertEqual(stored["preco_unitario"], 19.9)
        self.assertEqual(stored["usuario"], "vendedor")
        self.assertEqual(updated_product["quantidade"], 2)

    def test_pedido_com_multiplos_produtos_e_cliente(self):
        headers = self.headers(self.admin_token)
        products = []
        for name, price, quantity in (("Filtro", 20, 5), ("Pastilha", 30, 4)):
            products.append(self.client.post("/products", json={
                "nome": name,
                "marca": "Bosch",
                "numero_fabrica": f"{name}-01",
                "categoria": "Auto",
                "quantidade": quantity,
                "preco": price,
            }, headers=headers).json())
        customer = self.client.post(
            "/customers", json={"nome": "Maria Silva", "telefone": "11999990000"}, headers=headers
        )

        order = self.client.post("/sales", json={
            "cliente_id": customer.json()["id"],
            "itens": [
                {"produto_id": products[0]["id"], "quantidade": 2},
                {"produto_id": products[1]["id"], "quantidade": 1},
            ],
        }, headers=self.headers(self.operator_token))
        stored_sales = self.client.get("/sales", headers=self.headers(self.operator_token)).json()

        self.assertEqual(customer.status_code, 201)
        self.assertEqual(order.status_code, 201)
        self.assertEqual(order.json()["valor_total"], 70)
        self.assertEqual(order.json()["cliente_nome"], "Maria Silva")
        self.assertEqual(len(order.json()["itens"]), 2)
        self.assertEqual({sale["pedido_id"] for sale in stored_sales}, {order.json()["id"]})
        self.assertEqual({sale["cliente_id"] for sale in stored_sales}, {customer.json()["id"]})
        report = self.client.get("/reports/sales", headers=headers).json()
        self.assertEqual(report["quantidade_vendas"], 1)
        self.assertEqual(report["unidades_vendidas"], 3)
        self.assertEqual(report["valor_total"], 70)

    def test_pedido_invalido_nao_baixa_estoque_parcialmente(self):
        headers = self.headers(self.admin_token)
        first = self.client.post("/products", json={
            "nome": "Filtro", "marca": "Bosch", "numero_fabrica": "F-1",
            "categoria": "Auto", "quantidade": 5, "preco": 20,
        }, headers=headers).json()
        second = self.client.post("/products", json={
            "nome": "Pastilha", "marca": "Bosch", "numero_fabrica": "P-1",
            "categoria": "Auto", "quantidade": 1, "preco": 30,
        }, headers=headers).json()

        order = self.client.post("/sales", json={"itens": [
            {"produto_id": first["id"], "quantidade": 2},
            {"produto_id": second["id"], "quantidade": 2},
        ]}, headers=self.headers(self.operator_token))
        products = self.client.get("/products", headers=self.headers(self.operator_token)).json()
        sales = self.client.get("/sales", headers=self.headers(self.operator_token)).json()

        self.assertEqual(order.status_code, 409)
        self.assertEqual([product["quantidade"] for product in products], [5, 1])
        self.assertEqual(sales, [])

    def test_operador_nao_acessa_relatorio_financeiro(self):
        response = self.client.get("/reports/sales", headers=self.headers(self.operator_token))
        self.assertEqual(response.status_code, 403)

    def test_admin_acessa_relatorio_e_gerencia_usuarios(self):
        report = self.client.get("/reports/sales", headers=self.headers(self.admin_token))
        created = self.client.post(
            "/admin/users",
            json={"username": "caixa", "password": "SenhaCaixa123"},
            headers=self.headers(self.admin_token),
        )

        self.assertEqual(report.status_code, 200)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()["role"], "user")

    def test_rejeita_token_invalido(self):
        response = self.client.get("/products", headers=self.headers("token-falso"))
        self.assertEqual(response.status_code, 401)

    def test_root_serves_web_app_shell(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("AutoPeças", response.text)

    def test_token_de_usuario_removido_perde_acesso_imediatamente(self):
        deleted = self.client.delete(
            "/admin/users/vendedor",
            headers=self.headers(self.admin_token),
        )
        response = self.client.get("/products", headers=self.headers(self.operator_token))

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()