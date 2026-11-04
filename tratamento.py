"""
Módulo de TRATAMENTO.

Responsabilidade: selecionar colunas, aplicar os filtros,
converter tipos, calcular totais e salvar o CSV processado.

Cada função recebe um DataFrame, faz UMA tarefa e retorna o resultado.
"""

import pandas as pd

# Ano de referência do Censo Escolar usado em todo o processamento
ANO_CENSO = "2025"

# Caminhos onde os resultados tratados serão salvos (o ano fica no nome)
CAMINHO_DADOS_PROCESSADOS = "data/processed/escolas_macedonia_2025.csv"
CAMINHO_DADOS_IDEB_PROCESSADOS = (
    "data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv"
)

# Colunas que usamos na análise
COLUNAS_NECESSARIAS = [
    "NU_ANO_CENSO",
    "CO_ENTIDADE",
    "NO_ENTIDADE",
    "NO_DISTRITO",
    "TP_DEPENDENCIA",
    "QT_MAT_FUND",
    "QT_MAT_MED",
    "TP_SITUACAO_FUNCIONAMENTO"
]

COLUNAS_CENSO_IDEB = [
    "NU_ANO_CENSO",
    "CO_ENTIDADE",
    "NO_ENTIDADE",
    "NO_DISTRITO",
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

# Colunas trazidas da Tabela de Matrícula (em 2025 elas não estão mais
# na Tabela de Escola)
COLUNAS_MATRICULAS = [
    "QT_MAT_FUND",
    "QT_MAT_FUND_AI",
    "QT_MAT_FUND_AF",
    "QT_MAT_MED",
]

# O Censo 2025 não publica o bairro (NO_BAIRRO) nos microdados.
# Por isso, as escolas do Jardim Macedônia são localizadas por uma lista
# fixa de códigos INEP, usada apenas como referência cadastral (a lista
# veio do cadastro do Censo anterior, que ainda trazia o bairro).
# Limitação: escolas novas no bairro não entram automaticamente.
CODIGOS_JARDIM_MACEDONIA = [
    "35010281",  # EMEF CESAR YASIGI PROF
    "35044386",  # DAVID NASSER JORNALISTA
    "35238946",  # CEI DIRET JARDIM MACEDONIA
    "35578502",  # CR P CONV PENTAGRAMA II
    "35582633",  # CR P CONV VO CHICA
    "35902524",  # CESAR YASIGI PROFESSOR
]


def validar_ano_censo(dados, ano=ANO_CENSO):
    """Interrompe o processamento se a base não for do ano esperado."""
    anos_encontrados = sorted(dados["NU_ANO_CENSO"].dropna().unique())
    if anos_encontrados != [ano]:
        raise ValueError(
            f"Esperado somente o Censo {ano}, encontrado: {anos_encontrados}"
        )
    return dados


def juntar_escolas_e_matriculas(escolas, matriculas):
    """Acrescenta ao cadastro das escolas as matrículas de cada uma."""
    validar_ano_censo(matriculas)

    if matriculas["CO_ENTIDADE"].duplicated().any():
        raise ValueError("A Tabela de Matrícula possui código INEP duplicado")

    # how="left" -> mantém todas as escolas do cadastro, mesmo sem matrícula
    # validate="one_to_one" -> garante que o merge não multiplica registros
    dados = pd.merge(
        escolas,
        matriculas[["CO_ENTIDADE"] + COLUNAS_MATRICULAS],
        how="left",
        on="CO_ENTIDADE",
        validate="one_to_one",
    )

    if dados.shape[0] != escolas.shape[0]:
        raise ValueError("A junção escola x matrícula alterou a quantidade")

    return dados


def selecionar_colunas(dados):
    """Mantém somente as colunas necessárias para a análise."""
    escolas = dados[COLUNAS_NECESSARIAS].copy()
    return escolas


def selecionar_colunas_integracao_ideb(dados):
    """Seleciona as colunas adicionais usadas somente na integração IDEB."""
    escolas = dados[COLUNAS_CENSO_IDEB].copy()
    return escolas


def filtrar_jardim_macedonia(escolas):
    """Mantém os estabelecimentos identificados no Jardim Macedônia."""
    # O bairro não existe nos microdados de 2025: usamos a lista de
    # códigos INEP de referência cadastral (ver CODIGOS_JARDIM_MACEDONIA).
    escolas_macedonia = escolas[
        escolas["CO_ENTIDADE"].isin(CODIGOS_JARDIM_MACEDONIA)
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
    """Cria uma linha por escola e etapa com matrícula no Censo 2025."""
    escolas = escolas.copy()
    partes = []

    for etapa, coluna_matriculas in ETAPAS_E_MATRICULAS.items():
        matriculas = pd.to_numeric(
            escolas[coluna_matriculas],
            errors="coerce",
        )
        parte = escolas.loc[matriculas > 0].copy()
        parte["ETAPA_ENSINO"] = etapa
        parte["MATRICULAS_ETAPA_2025"] = (
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
    """Relaciona Censo 2025 e IDEB 2025 por código INEP e etapa."""
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
