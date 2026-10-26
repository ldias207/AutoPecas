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