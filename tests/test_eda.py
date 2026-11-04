"""
Testes da análise exploratória (EDA) sem PostgreSQL real.

O modo PostgreSQL é simulado por uma conexão falsa que devolve as linhas das
views como o psycopg devolveria (Decimal para numeric, None para NULL).
Os valores de referência das views 02 e 03 são os validados no PostgreSQL
em 04/11/2026 (docs/views_analiticas.md).

Execute a partir da pasta Entrega_final:
    python -m unittest discover -s tests -v
"""

import os
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

import numpy as np
import pandas as pd

PASTA_PROJETO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PASTA_PROJETO))
os.chdir(PASTA_PROJETO)

import estatisticas_eda as est  # noqa: E402
import fonte_dados_eda as fonte  # noqa: E402
import graficos_eda as graficos  # noqa: E402

# Resultado real da view 02 no PostgreSQL:
# (tp_dependencia, etapa, ofertas, divulgados, ausentes, média, mediana, menor, maior)
VIEW_02_VALIDADA = [
    (1, "AF", 1, 1, 0, "7.60", "7.60", "7.6", "7.6"),
    (1, "AI", 1, 1, 0, "8.20", "8.20", "8.2", "8.2"),
    (1, "EM", 4, 1, 3, "5.60", "5.60", "5.6", "5.6"),
    (2, "AF", 625, 574, 51, "5.11", "5.00", "3.7", "6.7"),
    (2, "AI", 539, 514, 25, "6.53", "6.50", "4.7", "8.5"),
    (2, "EM", 632, 532, 100, "4.44", "4.30", "2.9", "7.3"),
    (3, "AF", 552, 427, 125, "4.93", "4.90", "3.5", "6.3"),
    (3, "AI", 610, 543, 67, "5.87", "5.90", "4.5", "7.3"),
    (3, "EM", 9, 3, 6, "4.03", "3.90", "3.6", "4.6"),
]
# Resultado real da view 03: (código, etapa, matrículas, situação, IDEB, média, diferença)
VIEW_03_VALIDADA = [
    ("35010281", "AI", 464, "Divulgado", "6.4", "5.87", "0.53"),
    ("35044386", "AF", 336, "Divulgado", "3.9", "5.11", "-1.21"),
    ("35044386", "AI", 233, "Divulgado", "5.7", "6.53", "-0.83"),
    ("35044386", "EM", 393, "Não divulgado pelo Inep", None, "4.44", None),
]


def decimal_ou_none(valor):
    return None if valor is None or (isinstance(valor, float) and np.isnan(valor)) else Decimal(str(valor))


class CursorFalso:
    def __init__(self, conexao):
        self.conexao = conexao
        self.description, self.linhas = [], []

    def execute(self, consulta, parametros=None):
        self.conexao.consultas.append(consulta)
        tabelas = self.conexao.tabelas
        for nome, (colunas, linhas) in tabelas.items():
            if nome in consulta:
                self.description = [(c,) for c in colunas]
                self.linhas = linhas
                return
        raise AssertionError(f"consulta inesperada: {consulta}")

    def fetchall(self):
        return self.linhas

    def close(self):
        pass


class ConexaoFalsa:
    def __init__(self, tabelas):
        self.tabelas, self.consultas = tabelas, []
        self.read_only = False
        self.fechada = False

    def cursor(self):
        return CursorFalso(self)

    def close(self):
        self.fechada = True


def montar_views_simuladas(base):
    """Linhas das views como o psycopg entregaria (Decimal e None)."""
    v4_colunas = list(fonte.COLUNAS)
    v4 = [tuple(decimal_ou_none(v) if c == "vl_ideb" else (v.item() if hasattr(v, "item") else v)
                for c, v in zip(v4_colunas, linha))
          for linha in base[v4_colunas].itertuples(index=False, name=None)]
    v1_colunas = ["co_entidade", "co_etapa_ensino", "ano_referencia", "qt_matriculas"]
    v1 = [tuple(v.item() if hasattr(v, "item") else v for v in linha)
          for linha in base[v1_colunas].itertuples(index=False, name=None)]
    v2 = [(*l[:5], *[Decimal(x) for x in l[5:]]) for l in VIEW_02_VALIDADA]
    v3 = [(c, e, q, s, decimal_ou_none(i), Decimal(m), decimal_ou_none(d))
          for c, e, q, s, i, m, d in VIEW_03_VALIDADA]
    return {
        "vw_ideb_escolas_2025": (v4_colunas, v4),
        "vw_escolas_matriculas_2025": (v1_colunas, v1),
        "vw_ideb_rede_etapa_2025": (["tp_dependencia", "co_etapa_ensino", "qt_ofertas_avaliadas",
                                     "qt_ideb_divulgado", "qt_ideb_ausente", "media_ideb",
                                     "mediana_ideb", "menor_ideb", "maior_ideb"], v2),
        "vw_ideb_jardim_macedonia_2025": (["co_entidade", "co_etapa_ensino", "qt_matriculas",
                                           "situacao_ideb", "ideb_escola", "media_ideb_rede_etapa",
                                           "diferenca_ideb_rede_etapa"], v3),
    }


class TesteFuncoesNumpy(unittest.TestCase):
    """Funções estatísticas com dados sintéticos de resultado conhecido."""

    def test_resumo_numerico(self):
        r = est.resumo_numerico([1, 2, 3, 4, 100])
        self.assertEqual(r["n"], 5)
        self.assertAlmostEqual(r["media"], 22.0)
        self.assertEqual((r["q1"], r["mediana"], r["q3"], r["iqr"]), (2.0, 3.0, 4.0, 2.0))
        self.assertAlmostEqual(r["desvio_padrao"], np.std([1, 2, 3, 4, 100], ddof=1))
        self.assertGreater(r["assimetria"], 1)  # cauda longa à direita

    def test_nan_e_ignorado_e_nunca_vira_zero(self):
        com_nan = est.resumo_numerico([4.0, np.nan, 6.0])
        self.assertEqual(com_nan["n"], 2)
        self.assertEqual(com_nan["media"], 5.0)  # com zero no lugar do NaN seria 3,33
        self.assertTrue(np.isnan(est.resumo_numerico([np.nan])["media"]))

    def test_limites_de_tukey_e_outliers(self):
        self.assertEqual(est.limites_tukey([1, 2, 3, 4, 100]), (-1.0, 7.0))
        por_escola = pd.DataFrame({"co_entidade": list("ABCDE"), "total_matriculas": [1, 2, 3, 4, 100]})
        fora = est.outliers_matriculas(por_escola)
        self.assertEqual(fora["co_entidade"].tolist(), ["E"])
        self.assertEqual(fora["tipo"].iloc[0], "acima do limite superior")

    def test_percentil_no_grupo(self):
        self.assertEqual(est.percentil_no_grupo(3.0, [1, 2, 3, 4]), 75.0)
        self.assertTrue(np.isnan(est.percentil_no_grupo(np.nan, [1, 2, 3])))

    def test_arredondamento_meio_para_cima(self):
        self.assertEqual(est.arredondar(2.675), 2.68)  # round() do Python daria 2.67
        self.assertEqual(est.media_exata([5.1, 5.12]), 5.11)


class TesteEdaCsv(unittest.TestCase):
    """Modo CSV: contagens, granularidade, NULL e resultados das 3 perguntas."""

    @classmethod
    def setUpClass(cls):
        cls.base = fonte.carregar_csv()["escolas_etapas"]
        cls.r = est.calcular_tudo(cls.base)

    def test_granularidade_e_contagens(self):
        chave = ["co_entidade", "co_etapa_ensino", "ano_referencia"]
        self.assertFalse(self.base.duplicated(subset=chave).any())
        self.assertEqual(len(self.base), 2973)
        self.assertEqual(self.base["co_entidade"].nunique(), 1709)
        self.assertEqual(set(self.base["ano_referencia"]), {2025})

    def test_null_preservado(self):
        self.assertEqual(int(self.base["vl_ideb"].notna().sum()), 2596)
        self.assertEqual(int(self.base["vl_ideb"].isna().sum()), 377)
        self.assertEqual(int((self.base["vl_ideb"] == 0).sum()), 0)

    def test_p1_media_por_escola_e_nao_por_oferta(self):
        total = self.r["matriculas_por_rede"].set_index("rede_administrativa").loc["Total"]
        self.assertEqual(total["escolas"], 1709)
        self.assertEqual(total["total_matriculas"], 1284021)
        self.assertEqual(round(total["media"], 2), 751.33)
        self.assertNotAlmostEqual(self.base["qt_matriculas"].mean(), total["media"], places=0)

    def test_p1_por_rede(self):
        p1 = self.r["matriculas_por_rede"].set_index("rede_administrativa")
        self.assertEqual(p1.loc[["Federal", "Estadual", "Municipal"], "escolas"].tolist(), [5, 1093, 611])
        self.assertEqual(p1.loc["Estadual", "total_matriculas"], 829862)
        self.assertEqual(round(p1.loc["Municipal", "media"], 2), 739.2)

    def test_p1_outliers_mantidos(self):
        self.assertEqual(self.r["limites_tukey"], (-112.0, 1552.0))
        self.assertEqual(len(self.r["outliers_matriculas"]), 49)
        self.assertEqual(len(self.r["matriculas_por_escola"]), 1709)  # nenhuma escola removida

    def test_p2_igual_a_view_02_validada(self):
        view = pd.DataFrame(VIEW_02_VALIDADA, columns=[
            "tp_dependencia", "co_etapa_ensino", "qt_ofertas_avaliadas", "qt_ideb_divulgado",
            "qt_ideb_ausente", "media_ideb", "mediana_ideb", "menor_ideb", "maior_ideb"])
        view[["media_ideb", "mediana_ideb", "menor_ideb", "maior_ideb"]] = \
            view[["media_ideb", "mediana_ideb", "menor_ideb", "maior_ideb"]].astype(float)
        comparacao = est.comparar_com_view_rede_etapa(self.r["ideb_rede_etapa"], view)
        self.assertEqual(len(comparacao), 9)
        self.assertTrue(comparacao["confere"].all(), comparacao)

    def test_p2_avisos_de_amostra_pequena(self):
        p2 = self.r["ideb_rede_etapa"].set_index(["rede_administrativa", "co_etapa_ensino"])
        for etapa in ["AI", "AF", "EM"]:
            self.assertEqual(p2.loc[("Federal", etapa), "ideb_divulgados"], 1)
            self.assertIn("amostra pequena", p2.loc[("Federal", etapa), "aviso"])
        self.assertEqual(p2.loc[("Municipal", "EM"), "ideb_divulgados"], 3)

    def test_p3_escolas_do_jardim_macedonia(self):
        p3 = self.r["jardim_macedonia"].set_index(["co_entidade", "co_etapa_ensino"])
        esperado = {("35010281", "AI"): (6.4, 5.87, 0.53), ("35044386", "AI"): (5.7, 6.53, -0.83),
                    ("35044386", "AF"): (3.9, 5.11, -1.21)}
        for chave, (ideb, media, diferenca) in esperado.items():
            self.assertEqual(tuple(p3.loc[chave, ["ideb_escola", "media_rede_etapa", "diferenca"]]),
                             (ideb, media, diferenca))
        em = p3.loc[("35044386", "EM")]
        self.assertTrue(np.isnan(em["ideb_escola"]) and np.isnan(em["diferenca"]))
        self.assertEqual(em["media_rede_etapa"], 4.44)
        self.assertEqual(em["situacao_ideb"], "Não divulgado pelo Inep")

    def test_graficos_sao_gerados(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminhos = [
                graficos.grafico_matriculas_por_rede(self.r["matriculas_por_rede"],
                                                     self.r["limites_tukey"],
                                                     self.r["outliers_matriculas"],
                                                     Path(pasta) / "p1.png"),
                graficos.grafico_ideb_rede_etapa(self.r["ideb_rede_etapa"], Path(pasta) / "p2.png"),
                graficos.grafico_jardim_macedonia(self.r["jardim_macedonia"], Path(pasta) / "p3.png"),
            ]
            for caminho in caminhos:
                self.assertGreater(Path(caminho).stat().st_size, 50_000)

    def test_formatacao_brasileira(self):
        self.assertEqual(graficos.formatar(1284021), "1.284.021")
        self.assertEqual(graficos.formatar(751.3264, 2), "751,33")


class TesteEdaPostgresSimulado(unittest.TestCase):
    """Modo PostgreSQL com conexão falsa: mesmas estatísticas do modo CSV."""

    @classmethod
    def setUpClass(cls):
        cls.base_csv = fonte.carregar_csv()["escolas_etapas"]
        cls.conexao = ConexaoFalsa(montar_views_simuladas(cls.base_csv))
        cls.dados_pg = fonte.carregar_postgres(conectar=lambda pedir_senha: cls.conexao)

    def test_sessao_somente_leitura_e_fechada(self):
        self.assertTrue(self.conexao.read_only)
        self.assertTrue(self.conexao.fechada)
        for consulta in self.conexao.consultas:
            self.assertTrue(consulta.lstrip().upper().startswith("SELECT"))

    def test_mesma_base_que_o_csv(self):
        pd.testing.assert_frame_equal(self.dados_pg["escolas_etapas"], self.base_csv)

    def test_mesmas_estatisticas_que_o_csv(self):
        r_pg = est.calcular_tudo(self.dados_pg["escolas_etapas"])
        r_csv = est.calcular_tudo(self.base_csv)
        for nome in ["matriculas_por_rede", "outliers_matriculas", "ideb_rede_etapa",
                     "jardim_macedonia"]:
            pd.testing.assert_frame_equal(r_pg[nome], r_csv[nome])

    def test_confere_com_views_02_e_03(self):
        r = est.calcular_tudo(self.dados_pg["escolas_etapas"])
        refs = self.dados_pg["referencias"]
        self.assertTrue(est.comparar_com_view_rede_etapa(r["ideb_rede_etapa"],
                                                         refs["ideb_rede_etapa"])["confere"].all())
        self.assertTrue(est.comparar_com_view_macedonia(r["jardim_macedonia"],
                                                        refs["jardim_macedonia"])["confere"].all())

    def test_divergencia_com_a_view_e_detectada(self):
        r = est.calcular_tudo(self.dados_pg["escolas_etapas"])
        view = self.dados_pg["referencias"]["ideb_rede_etapa"].copy()
        view.loc[0, "media_ideb"] = 9.99
        self.assertFalse(est.comparar_com_view_rede_etapa(r["ideb_rede_etapa"], view)["confere"].all())

    def test_base_invalida_e_recusada(self):
        tabelas = montar_views_simuladas(self.base_csv)
        colunas, linhas = tabelas["vw_ideb_escolas_2025"]
        posicao = colunas.index("vl_ideb")
        linha = list(linhas[0])
        linha[posicao] = Decimal("0")  # IDEB zero = ausência convertida indevidamente
        tabelas["vw_ideb_escolas_2025"] = (colunas, [tuple(linha)] + linhas[1:])
        with self.assertRaises(fonte.ErroFonteDados):
            fonte.carregar_postgres(conectar=lambda pedir_senha: ConexaoFalsa(tabelas))


if __name__ == "__main__":
    unittest.main()
