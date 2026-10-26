import hashlib
import hmac
import os


class AuthService:
    ITERATIONS = 310_000
    PERMISSIONS = {
        "admin": {
            "gerenciar_estoque",
            "consultar_estoque",
            "registrar_vendas",
            "consultar_financeiro",
            "gerenciar_usuarios",
        },
        "user": {"consultar_estoque", "registrar_vendas"},
    }

    def __init__(self, repository):
        self.repository = repository

    @classmethod
    def _hash_password(cls, password, salt=None, iterations=None):
        salt = salt or os.urandom(16)
        iterations = iterations or cls.ITERATIONS
        derived_key = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt, iterations
        )
        return f"pbkdf2_sha256${iterations}${salt.hex()}${derived_key.hex()}"

    @staticmethod
    def _validate_credentials(username, password):
        username = username.strip()
        if len(username) < 3:
            raise ValueError("O usuário deve ter pelo menos 3 caracteres.")
        if len(password) < 8:
            raise ValueError("A senha deve ter pelo menos 8 caracteres.")
        return username

    def has_users(self):
        return self.repository.has_users()

    @classmethod
    def has_permission(cls, user, permission):
        if not user:
            return False
        return permission in cls.PERMISSIONS.get(user.get("role"), set())

    def create_initial_admin(self, username, password):
        username = self._validate_credentials(username, password)
        self.repository.create_initial_admin(username, self._hash_password(password))

    def create_user(self, username, password, current_user):
        if not current_user or current_user.get("role") != "admin":
            raise PermissionError("Somente um administrador pode cadastrar usuários.")
        username = self._validate_credentials(username, password)
        self.repository.create_user(username, self._hash_password(password), "user")

    def authenticate(self, username, password):
        user = self.repository.get_user(username.strip())
        if not user:
            return None
        try:
            algorithm, iterations_text, salt_hex, expected_hash = user["password_hash"].split("$")
            iterations = int(iterations_text)
            if algorithm != "pbkdf2_sha256" or iterations < 100_000:
                return None
            actual_hash = self._hash_password(
                password, bytes.fromhex(salt_hex), iterations
            ).split("$")[-1]
        except (ValueError, TypeError):
            return None
        if not hmac.compare_digest(actual_hash, expected_hash):
            return None
        return {"id": user["id"], "username": user["username"], "role": user["role"]}

    def delete_user(self, username, current_user):
        if not current_user or current_user.get("role") != "admin":
            raise PermissionError("Somente um administrador pode remover usuários.")
        target = self.repository.get_user(username)
        if not target:
            raise ValueError("Usuário não encontrado.")
        if target["id"] == current_user.get("id"):
            raise ValueError("Não é possível remover a própria conta durante a sessão.")
        if target["role"] == "admin":
            admins = [user for user in self.repository.list_users() if user["role"] == "admin"]
            if len(admins) <= 1:
                raise ValueError("Não é possível remover o último administrador.")
        self.repository.delete_user(username)