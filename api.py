import base64
import hashlib
import hmac
import json
import os
import time
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from auth import AuthService
from database import SQLiteRepository


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATABASE_FILE = Path(os.environ.get("AUTOPECAS_DATABASE", BASE_DIR / "autopecas.db"))
TOKEN_SECRET = os.environ.get("AUTOPECAS_TOKEN_SECRET")
TOKEN_LIFETIME_SECONDS = 8 * 60 * 60


class LoginInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=1, max_length=256)


class ProductInput(BaseModel):
    nome: str = Field(min_length=1, max_length=160)
    marca: str = Field(min_length=1, max_length=120)
    numero_fabrica: str = Field(min_length=1, max_length=120)
    categoria: str = Field(min_length=1, max_length=120)
    quantidade: int = Field(ge=0)
    preco: float = Field(ge=0)


class SaleInput(BaseModel):
    produto_id: int = Field(gt=0)
    quantidade: int = Field(gt=0)


class UserInput(BaseModel):
    username: str = Field(min_length=3, max_length=80)
    password: str = Field(min_length=8, max_length=256)


class TokenOutput(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def create_app(repository=None, token_secret=None):
    repository = repository or SQLiteRepository(
        DATABASE_FILE,
        BASE_DIR / "estoque_autopecas.json",
        BASE_DIR / "vendas_autopecas.json",
    )
    auth_service = AuthService(repository)
    configured_secret = token_secret or TOKEN_SECRET
    secret = configured_secret.encode("utf-8") if isinstance(configured_secret, str) else configured_secret
    secret = secret or os.urandom(32)
    app = FastAPI(title="AutoPeças API", version="1.0.0")
    app.state.repository = repository
    app.state.auth_service = auth_service
    app.state.token_secret = secret

    def current_user(authorization: Annotated[str | None, Header()] = None):
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token ausente.")
        token = authorization[7:]
        token_user_id = _decode_token_with_secret(token, app.state.token_secret)
        if token_user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido ou expirado.")
        user = repository.get_user_by_id(token_user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário não encontrado.")
        return user

    def require_permission(permission):
        def dependency(user=Depends(current_user)):
            if not auth_service.has_permission(user, permission):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso não autorizado.")
            return user
        return dependency

    @app.get("/", include_in_schema=False)
    def root():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.post("/auth/login", response_model=TokenOutput)
    def login(credentials: LoginInput):
        user = auth_service.authenticate(credentials.username, credentials.password)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuário ou senha inválidos.")
        return {
            "access_token": _encode_token_with_secret(user["id"], app.state.token_secret),
            "expires_in": TOKEN_LIFETIME_SECONDS,
        }

    @app.get("/auth/me")
    def who_am_i(user=Depends(current_user)):
        return {"id": user["id"], "username": user["username"], "role": user["role"]}

    @app.post("/admin/users", status_code=status.HTTP_201_CREATED)
    def create_user(
        credentials: UserInput,
        user=Depends(require_permission("gerenciar_usuarios")),
    ):
        try:
            auth_service.create_user(credentials.username, credentials.password, user)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        return {"username": credentials.username.strip(), "role": "user"}

    @app.delete("/admin/users/{username}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_user(
        username: str,
        user=Depends(require_permission("gerenciar_usuarios")),
    ):
        try:
            auth_service.delete_user(username, user)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error

    @app.get("/products")
    def list_products(
        q: str = "",
        user=Depends(require_permission("consultar_estoque")),
    ):
        query = q.strip().casefold()
        products = repository.load_parts()
        if query:
            products = [
                product for product in products
                if any(query in str(product.get(field, "")).casefold()
                       for field in ("nome", "marca", "numero_fabrica", "categoria"))
            ]
        return products

    @app.post("/products", status_code=status.HTTP_201_CREATED)
    def create_product(
        product: ProductInput,
        user=Depends(require_permission("gerenciar_estoque")),
    ):
        return repository.create_part(product.model_dump())

    @app.put("/products/{product_id}")
    def update_product(
        product_id: int,
        product: ProductInput,
        user=Depends(require_permission("gerenciar_estoque")),
    ):
        updated = repository.update_part(product_id, product.model_dump())
        if not updated:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")
        return updated

    @app.delete("/products/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_product(
        product_id: int,
        user=Depends(require_permission("gerenciar_estoque")),
    ):
        if not repository.delete_part(product_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Produto não encontrado.")

    @app.get("/sales")
    def list_sales(user=Depends(require_permission("registrar_vendas"))):
        return repository.load_sales()

    @app.post("/sales", status_code=status.HTTP_201_CREATED)
    def create_sale(
        sale: SaleInput,
        user=Depends(require_permission("registrar_vendas")),
    ):
        result = repository.register_sale(sale.produto_id, sale.quantidade, user["id"])
        if not result:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quantidade indisponível para venda.")
        return result

    @app.get("/reports/sales")
    def sales_report(
        data_inicio: date | None = None,
        data_fim: date | None = None,
        user=Depends(require_permission("consultar_financeiro")),
    ):
        if data_inicio and data_fim and data_inicio > data_fim:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Intervalo de datas inválido.")
        sales = repository.load_sales()
        filtered = []
        for sale in sales:
            if not sale.get("data"):
                if not data_inicio and not data_fim:
                    filtered.append(sale)
                continue
            try:
                sale_date = datetime.strptime(sale["data"], "%Y-%m-%d").date()
            except ValueError:
                continue
            if data_inicio and sale_date < data_inicio:
                continue
            if data_fim and sale_date > data_fim:
                continue
            filtered.append(sale)
        return {
            "quantidade_vendas": len(filtered),
            "unidades_vendidas": sum(sale["quantidade"] for sale in filtered),
            "valor_total": round(sum(sale["valor_total"] for sale in filtered), 2),
            "vendas": filtered,
        }

    return app


app = create_app()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _encode_token_with_secret(user_id, secret):
    payload = {"sub": user_id, "exp": int(time.time()) + TOKEN_LIFETIME_SECONDS}
    body = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(secret, body, hashlib.sha256).digest()
    return f"{body.decode()}.{base64.urlsafe_b64encode(signature).rstrip(b'=').decode()}"


def _decode_token_with_secret(token, secret):
    try:
        body_text, signature_text = token.split(".", 1)
        body = body_text.encode()
        signature = base64.urlsafe_b64decode(signature_text + "=" * (-len(signature_text) % 4))
        if not hmac.compare_digest(signature, hmac.new(secret, body, hashlib.sha256).digest()):
            return None
        payload = json.loads(base64.urlsafe_b64decode(body_text + "=" * (-len(body_text) % 4)))
        if int(payload["exp"]) <= int(time.time()):
            return None
        return int(payload["sub"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return None

