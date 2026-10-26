import unittest
from datetime import date

import main


class TestEstoqueAutopecas(unittest.TestCase):
    def test_formatar_peca(self):
        item = {
            "nome": "Filtro de Óleo",
            "numero_fabrica": "FO-220",
            "marca": "Bosch",
            "categoria": "Motor",
            "quantidade": 10,
            "preco": 49.9,
            "status": "Disponível",
        }

        esperado = "Bosch | Filtro de Óleo | FO-220 | Qtd: 10 | R$ 49.90 | Disponível"
        self.assertEqual(main.formatar_peca(item), esperado)

    def test_validar_peca(self):
        item = {
            "nome": "Pastilha",
            "numero_fabrica": "PA-99",
            "marca": "Mitsuboshi",
            "categoria": "Freio",
            "quantidade": "12",
            "preco": "89.50",
            "status": "Disponível",
        }

        self.assertTrue(main.validar_peca(item))

        item_invalida = {
            "nome": "",
            "numero_fabrica": "PA-99",
            "marca": "Mitsuboshi",
            "categoria": "Freio",
            "quantidade": "-2",
            "preco": "89.50",
            "status": "Disponível",
        }

        self.assertFalse(main.validar_peca(item_invalida))

    def test_estoque_baixo(self):
        item_critico = {"nome": "Correia", "quantidade": 3, "status": "Disponível"}
        item_normal = {"nome": "Vela", "quantidade": 20, "status": "Disponível"}
        item_com_status_inconsistente = {"nome": "Bomba", "quantidade": 20, "status": "Esgotado"}

        self.assertTrue(main.estoque_baixo(item_critico))
        self.assertFalse(main.estoque_baixo(item_normal))
        self.assertFalse(main.estoque_baixo(item_com_status_inconsistente))

    def test_status_produto_depende_apenas_da_quantidade(self):
        self.assertEqual(main.status_por_quantidade(0), "Esgotado")
        self.assertEqual(main.status_por_quantidade(1), "Disponível")
        self.assertEqual(main.status_por_quantidade(5), "Disponível")
        self.assertEqual(main.status_por_quantidade(20), "Disponível")

    def test_registrar_venda_reduz_estoque(self):
        pecas = [{
            "nome": "Pastilha",
            "numero_fabrica": "PA-99",
            "marca": "Mitsuboshi",
            "categoria": "Freio",
            "quantidade": 10,
            "preco": 89.50,
            "status": "Disponível",
        }]

        venda = main.registrar_venda(pecas, 0, 3)

        self.assertIsNotNone(venda)
        self.assertEqual(pecas[0]["quantidade"], 7)
        self.assertEqual(venda["quantidade"], 3)
        self.assertEqual(venda["valor_total"], 268.5)
        self.assertEqual(venda["data"], date.today().isoformat())
        self.assertEqual(pecas[0]["status"], "Disponível")

    def test_venda_da_ultima_unidade_marca_produto_esgotado(self):
        pecas = [{
            "nome": "Filtro",
            "quantidade": 1,
            "preco": 10.0,
            "status": "Disponível",
        }]

        venda = main.registrar_venda(pecas, 0, 1)

        self.assertIsNotNone(venda)
        self.assertEqual(pecas[0]["quantidade"], 0)
        self.assertEqual(pecas[0]["status"], "Esgotado")

    def test_total_valor_vendas_e_estoque(self):
        pecas = [
            {"nome": "Pastilha", "quantidade": 2, "preco": 50.0},
            {"nome": "Filtro", "quantidade": 5, "preco": 15.0},
        ]
        vendas = [
            {"nome": "Pastilha", "valor_total": 100.0},
            {"nome": "Filtro", "valor_total": 45.0},
        ]

        self.assertEqual(main.total_valor_vendas(vendas), 145.0)
        self.assertEqual(main.total_valor_estoque(pecas), 175.0)

    def test_resumo_vendas_por_produto_com_filtros(self):
        vendas = [
            {"nome": "Pastilha", "quantidade": 2, "valor_total": 100.0, "data": "2026-10-20"},
            {"nome": "Pastilha", "quantidade": 1, "valor_total": 50.0, "data": "2026-10-22"},
            {"nome": "Filtro", "quantidade": 3, "valor_total": 45.0, "data": "2026-10-22"},
            {"nome": "Correia", "quantidade": 1, "valor_total": 30.0},
        ]

        resultado = main.resumo_vendas_por_produto(
            vendas,
            termo="past",
            data_inicio="2026-10-21",
            data_fim="2026-10-23",
        )

        self.assertEqual(resultado, [{"nome": "Pastilha", "quantidade": 1, "valor_total": 50.0}])

    def test_valor_estoque_por_categoria(self):
        pecas = [
            {"categoria": "Freio", "quantidade": 2, "preco": 50.0},
            {"categoria": "Freio", "quantidade": 1, "preco": 20.0},
            {"categoria": "Motor", "quantidade": 3, "preco": 15.0},
        ]

        resultado = main.valor_estoque_por_categoria(pecas)

        self.assertEqual(resultado, [
            {"categoria": "Freio", "quantidade": 3, "valor_total": 120.0},
            {"categoria": "Motor", "quantidade": 3, "valor_total": 45.0},
        ])

    def test_busca_para_venda_exige_termo_e_filtra_produtos_com_saldo(self):
        pecas = [
            {"nome": "Pastilha", "marca": "Bosch", "numero_fabrica": "PA-10", "categoria": "Freio", "quantidade": 3},
            {"nome": "Pastilha traseira", "marca": "ACME", "numero_fabrica": "PA-20", "categoria": "Freio", "quantidade": 0},
            {"nome": "Filtro", "marca": "Bosch", "numero_fabrica": "FI-10", "categoria": "Motor", "quantidade": 5},
        ]

        self.assertEqual(main.buscar_pecas_para_venda(pecas, ""), [])
        resultado = main.buscar_pecas_para_venda(pecas, "bosch")

        self.assertEqual([indice for indice, _ in resultado], [0, 2])


if __name__ == "__main__":
    unittest.main()
