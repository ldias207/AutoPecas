import sqlite3
import tempfile
import unittest
from pathlib import Path

from auth import AuthService
from database import SQLiteRepository


class TestAuthService(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        base_path = Path(self.temp_dir.name)
        self.repository = SQLiteRepository(base_path / "autopecas.db")
        self.auth = AuthService(self.repository)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_primeiro_usuario_e_administrador_e_senha_nao_fica_em_texto_puro(self):
        self.auth.create_initial_admin("Admin", "SenhaForte123")

        usuario = self.auth.authenticate("admin", "SenhaForte123")
        self.assertEqual(usuario["role"], "admin")
        stored = self.repository.get_user("admin")
        self.assertNotIn("SenhaForte123", stored["password_hash"])

    def test_nao_permite_segundo_admin_inicial(self):
        self.auth.create_initial_admin("admin", "SenhaForte123")

        with self.assertRaises(ValueError):
            self.auth.create_initial_admin("outro", "SenhaForte456")

    def test_validacao_de_usuario_senha_e_nome_duplicado(self):
        with self.assertRaises(ValueError):
            self.auth.create_initial_admin("ab", "SenhaForte123")
        with self.assertRaises(ValueError):
            self.auth.create_initial_admin("admin", "curta")

        self.auth.create_initial_admin("admin", "SenhaForte123")
        admin = self.auth.authenticate("admin", "SenhaForte123")
        with self.assertRaises(ValueError):
            self.auth.create_user("ADMIN", "OutraSenha123", admin)

    def test_cadastro_de_usuario_exige_admin_e_login_rejeita_senha_incorreta(self):
        self.auth.create_initial_admin("admin", "SenhaForte123")

        with self.assertRaises(PermissionError):
            self.auth.create_user("operador", "SenhaForte456", {"role": "user"})

        self.auth.create_user("operador", "SenhaForte456", {"role": "admin"})
        self.assertIsNone(self.auth.authenticate("operador", "errada"))
        self.assertEqual(self.auth.authenticate("operador", "SenhaForte456")["role"], "user")

    def test_login_sem_usuario_inexistente(self):
        self.assertIsNone(self.auth.authenticate("naoexiste", "SenhaForte123"))

    def test_admin_remove_usuario_operacional(self):
        self.auth.create_initial_admin("admin", "SenhaForte123")
        admin = self.auth.authenticate("admin", "SenhaForte123")
        self.auth.create_user("operador", "SenhaForte456", admin)

        self.auth.delete_user("operador", admin)

        self.assertIsNone(self.repository.get_user("operador"))

    def test_impede_remover_propria_conta_e_ultimo_admin(self):
        self.auth.create_initial_admin("admin", "SenhaForte123")
        admin = self.auth.authenticate("admin", "SenhaForte123")

        with self.assertRaises(ValueError):
            self.auth.delete_user("admin", admin)

    def test_operador_nao_pode_remover_usuario(self):
        self.auth.create_initial_admin("admin", "SenhaForte123")
        admin = self.auth.authenticate("admin", "SenhaForte123")
        self.auth.create_user("operador", "SenhaForte456", admin)
        operador = self.auth.authenticate("operador", "SenhaForte456")

        with self.assertRaises(PermissionError):
            self.auth.delete_user("admin", operador)

    def test_permissoes_por_perfil(self):
        admin = {"role": "admin"}
        operador = {"role": "user"}

        self.assertTrue(self.auth.has_permission(admin, "gerenciar_estoque"))
        self.assertTrue(self.auth.has_permission(admin, "consultar_financeiro"))
        self.assertTrue(self.auth.has_permission(operador, "consultar_estoque"))
        self.assertTrue(self.auth.has_permission(operador, "registrar_vendas"))
        self.assertFalse(self.auth.has_permission(operador, "gerenciar_estoque"))
        self.assertFalse(self.auth.has_permission(operador, "consultar_financeiro"))
        self.assertFalse(self.auth.has_permission(operador, "gerenciar_usuarios"))
        self.assertFalse(self.auth.has_permission(None, "consultar_estoque"))


if __name__ == "__main__":
    unittest.main()