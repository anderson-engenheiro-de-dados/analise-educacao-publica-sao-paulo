"""
Módulo de TRATAMENTO.

Responsabilidade: selecionar colunas, aplicar os filtros,
converter tipos, calcular totais e salvar o CSV processado.

Cada função recebe um DataFrame, faz UMA tarefa e retorna o resultado.
"""

import pandas as pd

# Caminho onde o resultado tratado será salvo
CAMINHO_DADOS_PROCESSADOS = "data/processed/escolas_macedonia.csv"
CAMINHO_DADOS_IDEB_PROCESSADOS = (
    "data/processed/escolas_publicas_sp_ideb_2025.csv"
)

# Colunas que usamos na análise
COLUNAS_NECESSARIAS = [
    "CO_ENTIDADE",
    "NO_ENTIDADE",
    "NO_BAIRRO",
    "TP_DEPENDENCIA",
    "QT_MAT_FUND",
    "QT_MAT_MED",
    "TP_SITUACAO_FUNCIONAMENTO"
]

COLUNAS_CENSO_IDEB = [
    "NU_ANO_CENSO",
    "CO_ENTIDADE",
    "NO_ENTIDADE",
    "NO_BAIRRO",
    "TP_DEPENDENCIA",
    "QT_MAT_FUND",
    "QT_MAT_FUND_AI",
    "QT_MAT_FUND_AF",
    "QT_MAT_MED",
    "TP_SITUACAO_FUNCIONAMENTO",
]

ETAPAS_E_MATRICULAS = {
    "Anos iniciais do Ensino Fundamental": "QT_MAT_FUND_AI",
    "Anos finais do Ensino Fundamental": "QT_MAT_FUND_AF",
    "Ensino Médio": "QT_MAT_MED",
}


def selecionar_colunas(dados):
    """Mantém somente as colunas necessárias para a análise."""
    escolas = dados[COLUNAS_NECESSARIAS].copy()
    return escolas


def selecionar_colunas_integracao_ideb(dados):
    """Seleciona as colunas adicionais usadas somente na integração IDEB."""
    escolas = dados[COLUNAS_CENSO_IDEB].copy()
    return escolas


def filtrar_jardim_macedonia(escolas):
    """Mantém somente as escolas cujo bairro contém 'MACEDONIA'."""
    # case=False -> ignora maiúsculas/minúsculas
    # na=False   -> bairro vazio é tratado como "não é Macedônia"
    escolas_macedonia = escolas[
        escolas["NO_BAIRRO"].str.contains(
            "MACEDONIA", case=False, na=False
        )
    ]
    return escolas_macedonia


def filtrar_escolas_publicas(escolas):
    """Mantém somente escolas estaduais (2) e municipais (3)."""
    escolas_publicas = escolas[
        escolas["TP_DEPENDENCIA"].isin(["2", "3"])
    ]
    return escolas_publicas


def filtrar_escolas_publicas_sp(escolas):
    """Filtra as escolas públicas de São Paulo."""

    escolas_publicas_sp = escolas[
        escolas["TP_DEPENDENCIA"].isin(["1", "2", "3"])
    ].copy()

    return escolas_publicas_sp



def filtrar_escolas_ativas(escolas):
    """Mantém somente escolas em atividade (situação de funcionamento = 1)."""
    escolas_ativas = escolas[
        escolas["TP_SITUACAO_FUNCIONAMENTO"] == "1"
    ].copy()
    return escolas_ativas


def converter_matriculas_para_numero(escolas):
    """Converte as colunas de matrículas de texto para número."""
    # .copy() evita alterar o DataFrame que foi recebido
    escolas = escolas.copy()

    # errors="coerce" -> o que não for número vira NaN (valor ausente)
    escolas["QT_MAT_FUND"] = pd.to_numeric(
        escolas["QT_MAT_FUND"],
        errors="coerce"
    )

    escolas["QT_MAT_MED"] = pd.to_numeric(
        escolas["QT_MAT_MED"],
        errors="coerce"
    )
    return escolas


def calcular_total_matriculas(escolas):
    """Cria a coluna TOTAL_MATRICULAS = Fundamental + Médio."""
    escolas = escolas.copy()
    escolas["TOTAL_MATRICULAS"] = (
        escolas["QT_MAT_FUND"] +
        escolas["QT_MAT_MED"]
    )
    return escolas


def selecionar_escolas_com_ensino(escolas):
    """Mantém somente escolas com matrículas no Fundamental ou Médio."""
    escolas_ensino = escolas[
        escolas["TOTAL_MATRICULAS"] > 0
    ].copy()
    return escolas_ensino


def salvar_csv_processado(escolas, caminho):
    """Salva o DataFrame tratado em um novo arquivo CSV."""
    escolas.to_csv(
        caminho,
        sep=";",
        index=False,
        encoding="utf-8-sig"
    )
    print("\nArquivo CSV tratado salvo com sucesso!")


def tratar_dados_ideb_2025(dados):
    """Padroniza código, nomes e indicadores oficiais do IDEB 2025."""
    dados = dados.copy()

    # As planilhas terminam com notas de rodapé sem código de escola.
    dados = dados[dados["ID_ESCOLA"].notna()].copy()

    dados["ID_ESCOLA"] = (
        dados["ID_ESCOLA"]
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.zfill(8)
    )

    dados = dados.rename(columns={
        "ID_ESCOLA": "CO_ENTIDADE",
        "NO_ESCOLA": "NO_ESCOLA_IDEB",
        "REDE": "REDE_IDEB",
        "VL_INDICADOR_REND_2025": "INDICADOR_RENDIMENTO_2025",
        "VL_NOTA_MATEMATICA_2025": "NOTA_MATEMATICA_SAEB_2025",
        "VL_NOTA_PORTUGUES_2025": "NOTA_PORTUGUES_SAEB_2025",
        "VL_NOTA_MEDIA_2025": "NOTA_MEDIA_PADRONIZADA_2025",
        "VL_OBSERVADO_2025": "IDEB_2025",
    })

    colunas_numericas = [
        "INDICADOR_RENDIMENTO_2025",
        "NOTA_MATEMATICA_SAEB_2025",
        "NOTA_PORTUGUES_SAEB_2025",
        "NOTA_MEDIA_PADRONIZADA_2025",
        "IDEB_2025",
    ]

    # Marcadores oficiais como "-", "ND" e "ND***" viram NaN, nunca zero.
    for coluna in colunas_numericas:
        dados[coluna] = pd.to_numeric(dados[coluna], errors="coerce")

    chave = ["CO_ENTIDADE", "ANO_IDEB", "ETAPA_ENSINO"]
    duplicados = dados.duplicated(subset=chave, keep=False)
    if duplicados.any():
        exemplos = dados.loc[duplicados, chave].head().to_dict("records")
        raise ValueError(f"Chave duplicada nos arquivos do IDEB: {exemplos}")

    return dados


def criar_base_escola_etapa(escolas):
    """Cria uma linha por escola e etapa com matrícula no Censo 2024."""
    escolas = escolas.copy()
    partes = []

    for etapa, coluna_matriculas in ETAPAS_E_MATRICULAS.items():
        matriculas = pd.to_numeric(
            escolas[coluna_matriculas],
            errors="coerce",
        )
        parte = escolas.loc[matriculas > 0].copy()
        parte["ETAPA_ENSINO"] = etapa
        parte["MATRICULAS_ETAPA_2024"] = (
            matriculas[matriculas > 0].astype("Int64")
        )
        partes.append(parte)

    base_etapas = pd.concat(partes, ignore_index=True)
    base_etapas["ANO_CENSO"] = base_etapas["NU_ANO_CENSO"]
    base_etapas["REDE_CENSO"] = base_etapas["TP_DEPENDENCIA"].map({
        "1": "Federal",
        "2": "Estadual",
        "3": "Municipal",
    })

    chave = ["CO_ENTIDADE", "ANO_CENSO", "ETAPA_ENSINO"]
    if base_etapas.duplicated(subset=chave).any():
        raise ValueError("A base do Censo possui chave escola/ano/etapa duplicada")

    return base_etapas


def integrar_censo_com_ideb(base_etapas, ideb):
    """Relaciona Censo 2024 e IDEB 2025 por código INEP e etapa."""
    ideb_sp = ideb[ideb["SG_UF"] == "SP"].copy()

    resultado = pd.merge(
        base_etapas,
        ideb_sp,
        how="left",
        on=["CO_ENTIDADE", "ETAPA_ENSINO"],
        validate="one_to_one",
        indicator=True,
    )

    resultado["SITUACAO_IDEB_2025"] = "Não divulgado pelo Inep"
    resultado.loc[
        resultado["_merge"] == "left_only",
        "SITUACAO_IDEB_2025",
    ] = "Escola/etapa não localizada no arquivo do Inep"
    resultado.loc[
        resultado["IDEB_2025"].notna(),
        "SITUACAO_IDEB_2025",
    ] = "Divulgado"

    return resultado.drop(columns="_merge")


def salvar_integracao_ideb(resultado, caminho):
    """Salva o resultado da integração sem alterar os CSVs existentes."""
    resultado.to_csv(
        caminho,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )
    print(f"\nIntegração IDEB salva em: {caminho}")
