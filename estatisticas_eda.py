"""
Estatísticas da análise exploratória (EDA) - Censo Escolar 2025 e IDEB 2025.

Todas as regras estatísticas ficam AQUI, uma única vez, e valem para as duas
fontes (CSV e PostgreSQL). As funções recebem a tabela padronizada de
fonte_dados_eda.py (1 linha por escola x etapa x ano) e devolvem DataFrames.

Funções NumPy usadas:
    np.percentile   -> quartis (Q1, mediana, Q3), com interpolação linear,
                       o mesmo critério do percentile_cont do PostgreSQL
    np.mean/np.std  -> média, desvio-padrão (ddof=1, amostral), assimetria
    np.isnan        -> separa valores ausentes ANTES de qualquer cálculo
    np.mean(x <= v) -> posição percentil de uma escola no seu grupo
"""

from decimal import ROUND_HALF_UP, Decimal

import numpy as np
import pandas as pd

from fonte_dados_eda import ESCOLAS_INTERESSE, ORDEM_ETAPAS, ORDEM_REDES

FATOR_TUKEY = 1.5
LIMITE_AMOSTRA_PEQUENA = 10  # grupos com menos IDEBs divulgados recebem aviso


# ---------------------------------------------------------------------------
# Funções básicas (NumPy)
# ---------------------------------------------------------------------------

def valores_validos(valores):
    """Array float sem NaN: ausências são excluídas, nunca tratadas como zero."""
    x = np.asarray(valores, dtype=float)
    return x[~np.isnan(x)]


def arredondar(valor, casas=2):
    """Arredonda "meio para cima", como o round(numeric) do PostgreSQL.

    O round() do Python arredonda 2,675 para 2,67 por causa da representação
    binária; aqui usamos Decimal para obter 2,68, igual ao banco.
    """
    if valor is None or (isinstance(valor, float) and np.isnan(valor)):
        return np.nan
    quantum = Decimal(1).scaleb(-casas)
    return float(Decimal(repr(float(valor))).quantize(quantum, rounding=ROUND_HALF_UP))


def media_exata(valores, casas=2):
    """Média calculada com Decimal (sem erro binário) e arredondada.

    Os IDEBs têm 1 casa decimal; somá-los em float pode produzir 5,114999...
    em vez de 5,115. Com Decimal, o resultado é igual ao avg(numeric) do banco.
    """
    x = valores_validos(valores)
    if x.size == 0:
        return np.nan
    soma = sum(Decimal(repr(float(v))) for v in x)
    quantum = Decimal(1).scaleb(-casas)
    return float((soma / x.size).quantize(quantum, rounding=ROUND_HALF_UP))


def resumo_numerico(valores):
    """Estatísticas descritivas de um conjunto de valores (NaN ignorado)."""
    x = valores_validos(valores)
    n = int(x.size)
    if n == 0:
        return {"n": 0, "media": np.nan, "mediana": np.nan, "q1": np.nan, "q3": np.nan,
                "iqr": np.nan, "desvio_padrao": np.nan, "coef_variacao_pct": np.nan,
                "assimetria": np.nan, "minimo": np.nan, "maximo": np.nan}
    q1, mediana, q3 = np.percentile(x, [25, 50, 75])
    media = float(np.mean(x))
    desvio = float(np.std(x, ddof=1)) if n > 1 else np.nan
    desvio_pop = float(np.std(x))
    assimetria = float(np.mean((x - media) ** 3) / desvio_pop ** 3) if n > 2 and desvio_pop > 0 else np.nan
    return {
        "n": n,
        "media": media,
        "mediana": float(mediana),
        "q1": float(q1),
        "q3": float(q3),
        "iqr": float(q3 - q1),
        "desvio_padrao": desvio,
        "coef_variacao_pct": desvio / media * 100 if n > 1 and media else np.nan,
        "assimetria": assimetria,
        "minimo": float(np.min(x)),
        "maximo": float(np.max(x)),
    }


def limites_tukey(valores, fator=FATOR_TUKEY):
    """Limites de Tukey: Q1 - 1,5 x IQR e Q3 + 1,5 x IQR."""
    x = valores_validos(valores)
    q1, q3 = np.percentile(x, [25, 75])
    iqr = q3 - q1
    return float(q1 - fator * iqr), float(q3 + fator * iqr)


def percentil_no_grupo(valor, valores_grupo):
    """Percentual de valores do grupo menores ou iguais ao valor informado."""
    x = valores_validos(valores_grupo)
    if np.isnan(valor) or x.size == 0:
        return np.nan
    return float(np.mean(x <= valor) * 100)


# ---------------------------------------------------------------------------
# Diagnóstico de qualidade
# ---------------------------------------------------------------------------

def diagnostico_qualidade(base):
    """Tabela de diagnóstico: tamanho, duplicatas, nulos, tipos e IDEB ausente."""
    chave = ["co_entidade", "co_etapa_ensino", "ano_referencia"]
    linhas = [
        ("Registros escola x etapa", len(base)),
        ("Escolas distintas", base["co_entidade"].nunique()),
        ("Chaves escola x etapa x ano duplicadas", int(base.duplicated(subset=chave).sum())),
        ("Anos de referência", ", ".join(map(str, sorted(base["ano_referencia"].unique())))),
        ("Matrículas menores ou iguais a zero", int((base["qt_matriculas"] <= 0).sum())),
        ("IDEB divulgado", int(base["vl_ideb"].notna().sum())),
        ("IDEB ausente (NULL, não convertido em zero)", int(base["vl_ideb"].isna().sum())),
        ("IDEB igual a zero", int((base["vl_ideb"] == 0).sum())),
    ]
    for situacao, quantidade in base["situacao_ideb"].value_counts().items():
        linhas.append((f"Situação do IDEB: {situacao}", int(quantidade)))
    for coluna in base.columns:
        linhas.append((f"Nulos em {coluna}", int(base[coluna].isna().sum())))
    for coluna, tipo in base.dtypes.items():
        linhas.append((f"Tipo de {coluna}", str(tipo)))
    return pd.DataFrame(linhas, columns=["verificacao", "resultado"])


# ---------------------------------------------------------------------------
# P1 - Matrículas por escola e por rede
# ---------------------------------------------------------------------------

def matriculas_por_escola(base):
    """Soma as etapas de cada escola: a ESCOLA passa a ser a unidade de análise."""
    por_escola = (
        base.groupby(["co_entidade", "no_entidade", "tp_dependencia", "rede_administrativa"],
                     as_index=False)
        .agg(total_matriculas=("qt_matriculas", "sum"), etapas=("co_etapa_ensino", "count"))
    )
    if por_escola["co_entidade"].duplicated().any():
        raise ValueError("Uma escola apareceu em mais de uma linha após a agregação.")
    return por_escola


def estatisticas_matriculas_por_rede(por_escola):
    """Total, quantidade de escolas e distribuição das matrículas por rede."""
    linhas = []
    grupos = [(rede, por_escola[por_escola["rede_administrativa"] == rede]) for rede in ORDEM_REDES]
    grupos.append(("Total", por_escola))
    for rede, grupo in grupos:
        resumo = resumo_numerico(grupo["total_matriculas"])
        linhas.append({
            "rede_administrativa": rede,
            "escolas": resumo.pop("n"),
            "total_matriculas": int(grupo["total_matriculas"].sum()),
            **resumo,
        })
    return pd.DataFrame(linhas)


def outliers_matriculas(por_escola):
    """Escolas fora dos limites de Tukey (calculados sobre todas as escolas).

    As escolas NÃO são removidas: são registros oficiais válidos (porte real
    da escola). A tabela serve para documentar e interpretar esses casos.
    """
    inferior, superior = limites_tukey(por_escola["total_matriculas"])
    fora = por_escola[(por_escola["total_matriculas"] < inferior)
                      | (por_escola["total_matriculas"] > superior)].copy()
    fora["tipo"] = np.where(fora["total_matriculas"] > superior,
                            "acima do limite superior", "abaixo do limite inferior")
    fora["limite_inferior"] = inferior
    fora["limite_superior"] = superior
    fora["tratamento"] = "mantida (registro válido do Censo 2025)"
    return fora.sort_values("total_matriculas", ascending=False).reset_index(drop=True)


# ---------------------------------------------------------------------------
# P2 - IDEB por rede e etapa
# ---------------------------------------------------------------------------

def estatisticas_ideb_rede_etapa(base):
    """IDEB por rede e etapa usando SOMENTE as notas divulgadas."""
    linhas = []
    for rede in ORDEM_REDES:
        for etapa in ORDEM_ETAPAS:
            grupo = base[(base["rede_administrativa"] == rede) & (base["co_etapa_ensino"] == etapa)]
            if grupo.empty:
                continue
            resumo = resumo_numerico(grupo["vl_ideb"])
            divulgados = resumo.pop("n")
            ofertas = len(grupo)
            linhas.append({
                "tp_dependencia": int(grupo["tp_dependencia"].iloc[0]),
                "rede_administrativa": rede,
                "co_etapa_ensino": etapa,
                "no_etapa_ensino": grupo["no_etapa_ensino"].iloc[0],
                "ofertas": ofertas,
                "ideb_divulgados": divulgados,
                "ideb_ausentes": ofertas - divulgados,
                "pct_ausente": (ofertas - divulgados) / ofertas * 100,
                "media_2casas": media_exata(grupo["vl_ideb"]),
                **resumo,
                "aviso": (f"amostra pequena: {divulgados} nota(s) divulgada(s)"
                          if divulgados < LIMITE_AMOSTRA_PEQUENA else ""),
            })
    return pd.DataFrame(linhas)


def comparar_com_view_rede_etapa(ideb_rede_etapa, view):
    """Compara os cálculos em Python com a view vw_ideb_rede_etapa_2025."""
    comparacao = ideb_rede_etapa.merge(view, on=["tp_dependencia", "co_etapa_ensino"],
                                       how="outer", indicator=True)
    pares = [("ofertas", "qt_ofertas_avaliadas"), ("ideb_divulgados", "qt_ideb_divulgado"),
             ("ideb_ausentes", "qt_ideb_ausente"), ("media_2casas", "media_ideb"),
             ("minimo", "menor_ideb"), ("maximo", "maior_ideb")]
    ok = comparacao["_merge"] == "both"
    for python, sql in pares:
        ok &= np.isclose(comparacao[python].astype(float), comparacao[sql].astype(float))
    ok &= np.isclose(comparacao["mediana"].map(arredondar), comparacao["mediana_ideb"])
    comparacao["confere"] = ok
    return comparacao[["rede_administrativa", "co_etapa_ensino", "ofertas", "qt_ofertas_avaliadas",
                       "media_2casas", "media_ideb", "mediana", "mediana_ideb", "confere"]]


# ---------------------------------------------------------------------------
# P3 - Jardim Macedônia x média da mesma rede e etapa
# ---------------------------------------------------------------------------

def comparar_jardim_macedonia(base, ideb_rede_etapa, codigos=ESCOLAS_INTERESSE):
    """IDEB de cada escola de interesse x média da MESMA rede e etapa em SP.

    A média da rede inclui a própria escola (média de todos os IDEBs
    divulgados do grupo). Sem IDEB da escola, diferença e percentil = NaN.
    """
    linhas = []
    escolas = base[base["co_entidade"].isin(codigos)]
    for _, escola in escolas.iterrows():
        grupo = base[(base["tp_dependencia"] == escola["tp_dependencia"])
                     & (base["co_etapa_ensino"] == escola["co_etapa_ensino"])]
        referencia = ideb_rede_etapa[
            (ideb_rede_etapa["tp_dependencia"] == escola["tp_dependencia"])
            & (ideb_rede_etapa["co_etapa_ensino"] == escola["co_etapa_ensino"])].iloc[0]
        ideb = escola["vl_ideb"]
        media = referencia["media_2casas"]
        linhas.append({
            "co_entidade": escola["co_entidade"],
            "no_entidade": escola["no_entidade"],
            "rede_administrativa": escola["rede_administrativa"],
            "co_etapa_ensino": escola["co_etapa_ensino"],
            "no_etapa_ensino": escola["no_etapa_ensino"],
            "qt_matriculas": int(escola["qt_matriculas"]),
            "situacao_ideb": escola["situacao_ideb"],
            "ideb_escola": ideb,
            "media_rede_etapa": media,
            "diferenca": arredondar(ideb - media) if not np.isnan(ideb) else np.nan,
            "mediana_rede_etapa": referencia["mediana"],
            "q1_rede_etapa": referencia["q1"],
            "q3_rede_etapa": referencia["q3"],
            "ideb_divulgados_rede_etapa": int(referencia["ideb_divulgados"]),
            "percentil_na_rede_etapa": percentil_no_grupo(ideb, grupo["vl_ideb"]),
        })
    resultado = pd.DataFrame(linhas)
    resultado["ordem"] = resultado["co_etapa_ensino"].map(ORDEM_ETAPAS.index)
    return (resultado.sort_values(["co_entidade", "ordem"]).drop(columns="ordem")
                     .reset_index(drop=True))


def comparar_com_view_macedonia(macedonia, view):
    """Compara os cálculos em Python com a view vw_ideb_jardim_macedonia_2025."""
    comparacao = macedonia.merge(view, on=["co_entidade", "co_etapa_ensino"], how="outer",
                                 suffixes=("", "_view"), indicator=True)

    def iguais(a, b):
        return np.isclose(a.astype(float), b.astype(float), equal_nan=True)

    comparacao["confere"] = (
        (comparacao["_merge"] == "both")
        & iguais(comparacao["ideb_escola"], comparacao["ideb_escola_view"])
        & iguais(comparacao["media_rede_etapa"], comparacao["media_ideb_rede_etapa"])
        & iguais(comparacao["diferenca"], comparacao["diferenca_ideb_rede_etapa"])
        & (comparacao["qt_matriculas"] == comparacao["qt_matriculas_view"])
        & (comparacao["situacao_ideb"] == comparacao["situacao_ideb_view"])
    )
    return comparacao[["co_entidade", "co_etapa_ensino", "ideb_escola", "media_rede_etapa",
                       "media_ideb_rede_etapa", "diferenca", "diferenca_ideb_rede_etapa", "confere"]]


# ---------------------------------------------------------------------------
# Execução completa
# ---------------------------------------------------------------------------

def calcular_tudo(base):
    """Calcula as tabelas das três perguntas a partir da base padronizada."""
    por_escola = matriculas_por_escola(base)
    ideb_rede_etapa = estatisticas_ideb_rede_etapa(base)
    inferior, superior = limites_tukey(por_escola["total_matriculas"])
    return {
        "diagnostico": diagnostico_qualidade(base),
        "matriculas_por_escola": por_escola,
        "matriculas_por_rede": estatisticas_matriculas_por_rede(por_escola),
        "outliers_matriculas": outliers_matriculas(por_escola),
        "limites_tukey": (inferior, superior),
        "ideb_rede_etapa": ideb_rede_etapa,
        "jardim_macedonia": comparar_jardim_macedonia(base, ideb_rede_etapa),
    }
