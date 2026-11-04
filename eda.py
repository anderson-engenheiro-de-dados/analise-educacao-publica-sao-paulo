"""
Análise exploratória (EDA) - Censo Escolar 2025 e IDEB/Saeb 2025.

Responde às três perguntas de pesquisa, salva as tabelas em resultados/ e os
três gráficos finais em graficos/.

    python eda.py --fonte csv                    (reprodutível, sem banco)
    python eda.py --fonte postgres [--pedir-senha]  (views do PostgreSQL)

No modo postgres, os resultados também são comparados com as views 02 e 03 e
com o modo CSV (se o CSV existir): as duas fontes devem dar o mesmo resultado.
"""

import argparse
import sys
from pathlib import Path

import pandas as pd

import carga_postgres as carga
import estatisticas_eda as est
import fonte_dados_eda as fonte
import graficos_eda as graficos

PASTA_RESULTADOS = Path("resultados")
PASTA_GRAFICOS = Path("graficos")
GRAFICOS = {
    "p1": "eda_p1_matriculas_rede_2025.png",
    "p2": "eda_p2_ideb_rede_etapa_2025.png",
    "p3": "eda_p3_jardim_macedonia_2025.png",
}
TABELAS = {
    "diagnostico": "diagnostico_qualidade_2025.csv",
    "matriculas_por_rede": "p1_matriculas_por_rede_2025.csv",
    "outliers_matriculas": "p1_outliers_matriculas_2025.csv",
    "ideb_rede_etapa": "p2_ideb_rede_etapa_2025.csv",
    "jardim_macedonia": "p3_jardim_macedonia_2025.csv",
}
TABELAS_COMPARADAS_ENTRE_FONTES = ["matriculas_por_rede", "outliers_matriculas",
                                   "ideb_rede_etapa", "jardim_macedonia"]


def salvar_tabela(tabela, caminho):
    """CSV com ; e vírgula decimal (abre corretamente no Excel em português)."""
    tabela.to_csv(caminho, sep=";", decimal=",", index=False, encoding="utf-8-sig",
                  float_format="%.4f")


def mostrar(titulo, tabela, colunas=None):
    print(f"\n=== {titulo} ===")
    print((tabela[colunas] if colunas else tabela).round(2).to_string(index=False))


def mostrar_resultados(resultados):
    mostrar("Diagnóstico de qualidade (primeiras verificações)",
            resultados["diagnostico"].head(11))
    mostrar("P1 - Matrículas por escola, por rede", resultados["matriculas_por_rede"],
            ["rede_administrativa", "escolas", "total_matriculas", "media", "mediana",
             "q1", "q3", "iqr", "desvio_padrao", "coef_variacao_pct", "assimetria",
             "minimo", "maximo"])
    inferior, superior = resultados["limites_tukey"]
    outliers = resultados["outliers_matriculas"]
    print(f"\nLimites de Tukey: [{inferior:.1f}; {superior:.1f}] | escolas fora: {len(outliers)} "
          f"(por rede: {outliers['rede_administrativa'].value_counts().to_dict()}) - mantidas")
    mostrar("P2 - IDEB 2025 por rede e etapa (somente IDEBs divulgados)",
            resultados["ideb_rede_etapa"],
            ["rede_administrativa", "co_etapa_ensino", "ofertas", "ideb_divulgados",
             "ideb_ausentes", "pct_ausente", "media_2casas", "mediana", "q1", "q3",
             "desvio_padrao", "minimo", "maximo", "aviso"])
    mostrar("P3 - Jardim Macedônia x média da mesma rede e etapa", resultados["jardim_macedonia"],
            ["co_entidade", "rede_administrativa", "co_etapa_ensino", "qt_matriculas",
             "situacao_ideb", "ideb_escola", "media_rede_etapa", "diferenca",
             "percentil_na_rede_etapa"])


def comparar_fontes(resultados_a, resultados_b):
    """True se as tabelas analíticas das duas fontes forem iguais."""
    for nome in TABELAS_COMPARADAS_ENTRE_FONTES:
        try:
            pd.testing.assert_frame_equal(resultados_a[nome], resultados_b[nome],
                                          check_exact=False, rtol=1e-9)
        except AssertionError as erro:
            print(f"  DIVERGE {nome}: {str(erro).splitlines()[0]}")
            return False
        print(f"  OK {nome}")
    return True


def conferir_postgres(dados, resultados):
    """No modo postgres: compara com as views 02 e 03 e com o modo CSV."""
    ok = True
    referencias = dados["referencias"]
    print("\n=== Conferência com as views do PostgreSQL ===")
    rede = est.comparar_com_view_rede_etapa(resultados["ideb_rede_etapa"],
                                            referencias["ideb_rede_etapa"])
    print(rede.to_string(index=False))
    macedonia = est.comparar_com_view_macedonia(resultados["jardim_macedonia"],
                                                referencias["jardim_macedonia"])
    print(macedonia.to_string(index=False))
    salvar_tabela(rede, PASTA_RESULTADOS / "conferencia_view_ideb_rede_etapa_2025.csv")
    salvar_tabela(macedonia, PASTA_RESULTADOS / "conferencia_view_jardim_macedonia_2025.csv")
    ok &= bool(rede["confere"].all()) and bool(macedonia["confere"].all())

    if Path(fonte.CAMINHO_CSV).exists():
        print("\n=== Equivalência entre as fontes PostgreSQL e CSV ===")
        resultados_csv = est.calcular_tudo(fonte.carregar_csv()["escolas_etapas"])
        ok &= comparar_fontes(resultados, resultados_csv)
    return ok


def executar(origem, pedir_senha=False):
    dados = fonte.carregar(origem, pedir_senha)
    base = dados["escolas_etapas"]
    print(f"Fonte: {origem} | {len(base)} registros escola x etapa | "
          f"{base['co_entidade'].nunique()} escolas | ano {fonte.ANO_REFERENCIA}")

    resultados = est.calcular_tudo(base)
    mostrar_resultados(resultados)

    PASTA_RESULTADOS.mkdir(exist_ok=True)
    PASTA_GRAFICOS.mkdir(exist_ok=True)
    for chave, arquivo in TABELAS.items():
        salvar_tabela(resultados[chave], PASTA_RESULTADOS / arquivo)

    graficos.grafico_matriculas_por_rede(resultados["matriculas_por_rede"],
                                         resultados["limites_tukey"],
                                         resultados["outliers_matriculas"],
                                         PASTA_GRAFICOS / GRAFICOS["p1"])
    graficos.grafico_ideb_rede_etapa(resultados["ideb_rede_etapa"], PASTA_GRAFICOS / GRAFICOS["p2"])
    graficos.grafico_jardim_macedonia(resultados["jardim_macedonia"],
                                      PASTA_GRAFICOS / GRAFICOS["p3"])
    print(f"\nTabelas salvas em {PASTA_RESULTADOS}/: {', '.join(TABELAS.values())}")
    print(f"Gráficos salvos em {PASTA_GRAFICOS}/: {', '.join(GRAFICOS.values())}")

    if origem == "postgres" and not conferir_postgres(dados, resultados):
        print("\nATENÇÃO: há divergências entre as fontes. Revise antes de usar os resultados.")
        return 1
    return 0


def main(argumentos=None):
    parser = argparse.ArgumentParser(description="EDA do Censo Escolar 2025 e IDEB 2025.")
    parser.add_argument("--fonte", choices=["csv", "postgres"], default="csv",
                        help="origem dos dados (padrão: csv)")
    parser.add_argument("--pedir-senha", action="store_true",
                        help="(com --fonte postgres) digita a senha de forma oculta")
    opcoes = parser.parse_args(argumentos)
    if opcoes.pedir_senha and opcoes.fonte != "postgres":
        parser.error("--pedir-senha só pode ser usado com --fonte postgres")
    try:
        return executar(opcoes.fonte, opcoes.pedir_senha)
    except (fonte.ErroFonteDados, carga.ErroCarga) as erro:
        print(f"\nERRO: {erro}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
