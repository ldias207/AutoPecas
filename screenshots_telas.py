import time
from pathlib import Path
from PIL import ImageGrab

import main


OUTPUT_DIR = Path(__file__).with_name("prints_telas")
OUTPUT_DIR.mkdir(exist_ok=True)


def capturar_tela(app, nome):
    app.root.state("normal")
    app.root.lift()
    app.root.focus_force()
    app.root.update_idletasks()
    app.root.update()
    time.sleep(0.5)
    app.root.update()
    x = app.root.winfo_rootx()
    y = app.root.winfo_rooty()
    largura = app.root.winfo_width()
    altura = app.root.winfo_height()
    imagem = ImageGrab.grab(bbox=(x, y, x + largura, y + altura))
    caminho = OUTPUT_DIR / f"{nome}.png"
    imagem.save(caminho)
    return caminho


def criar_documentacao_com_prints():
    app = main.AppController()
    try:
        app.root.lift()
        app.root.attributes("-topmost", True)
        app.root.focus_force()
        app.root.update()

        app.login_view.frame.pack(fill="both", expand=True)
        app.login_view.show_initial_admin()
        capturar_tela(app, "primeiro_administrador")
        app.login_view.show_login()
        capturar_tela(app, "login")

        app.active_user = {"id": -1, "username": "Administrador", "role": "admin"}
        app.menu_view.atualizar_sessao()
        app.mostrar_menu()

        capturar_tela(app, "menu_principal")

        app.mostrar_cadastro()
        capturar_tela(app, "cadastro_peca")

        app.mostrar_consulta()
        capturar_tela(app, "consulta_pecas")

        app.mostrar_vendas()
        capturar_tela(app, "registro_vendas")

        app.mostrar_financeiro()
        capturar_tela(app, "consulta_financeira")

        app.mostrar_usuarios()
        capturar_tela(app, "gerenciamento_usuarios")

        app.root.destroy()
    except Exception:
        try:
            app.root.destroy()
        except Exception:
            pass
        raise


if __name__ == "__main__":
    criar_documentacao_com_prints()
