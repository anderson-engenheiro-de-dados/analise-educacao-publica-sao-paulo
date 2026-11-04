"""
Fontes de dados da análise exploratória (EDA) - Censo Escolar 2025 e IDEB 2025.

As duas fontes entregam EXATAMENTE o mesmo formato: uma tabela com uma linha
por escola x etapa x ano, com as colunas da view educacao.vw_ideb_escolas_2025.

    origem "csv"      -> data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv
                         (reprodutível sem banco de dados)
    origem "postgres" -> views do schema educacao (somente leitura)

Nenhuma estatística é calculada aqui: os cálculos ficam em estatisticas_eda.py,
iguais para as duas fontes.
"""

import numpy as np
import pandas as pd

import carga_postgres as carga

ANO_REFERENCIA = carga.ANO_REFERENCIA  # 2025
ESCOLAS_INTERESSE = carga.ESCOLAS_INTERESSE  # César Yasigi e David Nasser
CAMINHO_CSV = carga.CAMINHO_INTEGRADA
ORDEM_ETAPAS = ["AI", "AF", "EM"]
ORDEM_REDES = ["Federal", "Estadual", "Municipal"]
REDES = {1: "Federal", 2: "Estadual", 3: "Municipal"}

# Colunas padronizadas (iguais às da view 04) e seus tipos em pandas.
COLUNAS = {
    "co_entidade": "str",
    "no_entidade": "str",
    "tp_dependencia": "int64",
    "rede_administrativa": "str",
    "co_etapa_ensino": "str",
    "no_etapa_ensino": "str",
    "qt_matriculas": "int64",
    "vl_ideb": "float64",      # NaN quando o IDEB não foi divulgado (nunca zero)
    "situacao_ideb": "str",
    "ano_referencia": "int64",
}

CONSULTA_VIEW_ESCOLAS = """
    SELECT co_entidade, no_entidade, tp_dependencia, rede_administrativa,
           co_etapa_ensino, no_etapa_ensino, qt_matriculas, vl_ideb,
           situacao_ideb, ano_referencia
    FROM educacao.vw_ideb_escolas_2025
    ORDER BY co_entidade, co_etapa_ensino"""

CONSULTA_VIEW_MATRICULAS = """
    SELECT co_entidade, co_etapa_ensino, ano_referencia, qt_matriculas
    FROM educacao.vw_escolas_matriculas_2025
    ORDER BY co_entidade, co_etapa_ensino"""

CONSULTA_VIEW_REDE_ETAPA = """
    SELECT tp_dependencia, co_etapa_ensino, qt_ofertas_avaliadas, qt_ideb_divulgado,
           qt_ideb_ausente, media_ideb, mediana_ideb, menor_ideb, maior_ideb
    FROM educacao.vw_ideb_rede_etapa_2025
    ORDER BY tp_dependencia, co_etapa_ensino"""

CONSULTA_VIEW_MACEDONIA = """
    SELECT co_entidade, co_etapa_ensino, qt_matriculas, situacao_ideb, ideb_escola,
           media_ideb_rede_etapa, diferenca_ideb_rede_etapa
    FROM educacao.vw_ideb_jardim_macedonia_2025
    ORDER BY co_entidade, co_etapa_ensino"""


class ErroFonteDados(Exception):
    """Os dados da EDA não respeitam as regras do recorte de 2025."""


# ---------------------------------------------------------------------------
# Padronização e validação (iguais para as duas fontes)
# ---------------------------------------------------------------------------

def numero_ou_nan(valor):
    """Converte Decimal/texto/None em float; ausência vira NaN (nunca zero)."""
    if valor is None or (isinstance(valor, float) and np.isnan(valor)) or valor is pd.NA:
        return np.nan
    if isinstance(valor, str) and valor.strip() == "":
        return np.nan
    return float(valor)


def padronizar(dados):
    """Ordena, tipa e confere as colunas no formato da view 04."""
    faltantes = [c for c in COLUNAS if c not in dados.columns]
    if faltantes:
        raise ErroFonteDados(f"Colunas ausentes na fonte: {faltantes}")
    dados = dados[list(COLUNAS)].copy()
    obrigatorias = [c for c in COLUNAS if c != "vl_ideb"]
    nulos = dados[obrigatorias].isna().sum()
    if nulos.any():
        raise ErroFonteDados(f"Nulos em colunas obrigatórias: {nulos[nulos > 0].to_dict()}")
    dados["vl_ideb"] = dados["vl_ideb"].map(numero_ou_nan).astype("float64")
    for coluna, tipo in COLUNAS.items():
        if tipo == "int64":
            dados[coluna] = pd.to_numeric(dados[coluna], errors="raise").astype("int64")
        elif tipo == "str":
            dados[coluna] = dados[coluna].astype(str)
    dados["ordem_etapa"] = dados["co_etapa_ensino"].map(ORDEM_ETAPAS.index)
    dados = (dados.sort_values(["co_entidade", "ordem_etapa"])
                  .drop(columns="ordem_etapa").reset_index(drop=True))
    validar_base(dados)
    return dados


def validar_base(dados):
    """Regras do recorte, aplicadas a qualquer fonte. Interrompe se falhar."""
    problemas = []
    chave = ["co_entidade", "co_etapa_ensino", "ano_referencia"]
    if dados.duplicated(subset=chave).any():
        problemas.append("chave escola x etapa x ano duplicada")
    if set(dados["ano_referencia"]) != {ANO_REFERENCIA}:
        problemas.append(f"anos diferentes de {ANO_REFERENCIA}: {sorted(set(dados['ano_referencia']))}")
    if not dados["tp_dependencia"].isin(list(REDES)).all():
        problemas.append("há escolas que não são públicas (tp_dependencia fora de 1, 2, 3)")
    if not dados["co_etapa_ensino"].isin(ORDEM_ETAPAS).all():
        problemas.append("etapa fora de AI, AF, EM")
    if not dados["co_entidade"].str.fullmatch(r"[0-9]{8}").all():
        problemas.append("código INEP fora do padrão de 8 dígitos")
    if (dados["qt_matriculas"] <= 0).any():
        problemas.append("oferta com matrícula menor ou igual a zero")
    if (dados["vl_ideb"] == 0).any():
        problemas.append("IDEB igual a zero (ausência não pode virar zero)")
    divulgado = dados["situacao_ideb"] == "Divulgado"
    if (divulgado != dados["vl_ideb"].notna()).any():
        problemas.append("IDEB preenchido sem situação 'Divulgado' (ou o inverso)")
    if (dados.groupby("co_entidade")["tp_dependencia"].nunique() > 1).any():
        problemas.append("escola com mais de uma rede")
    if problemas:
        raise ErroFonteDados("Base da EDA inválida: " + "; ".join(problemas))


# ---------------------------------------------------------------------------
# Fonte 1: CSV processado de 2025
# ---------------------------------------------------------------------------

def carregar_csv(caminho=CAMINHO_CSV):
    """Lê a base integrada do pipeline e a converte para o formato da view 04."""
    integrada = carga.ler_csv(caminho, encoding="utf-8-sig")

    # O CSV já é o recorte de escolas públicas ativas; aqui apenas conferimos.
    if not (integrada["TP_SITUACAO_FUNCIONAMENTO"] == "1").all():
        raise ErroFonteDados("O CSV contém escolas que não estão em atividade.")

    dados = pd.DataFrame({
        "co_entidade": integrada["CO_ENTIDADE"],
        "no_entidade": integrada["NO_ENTIDADE"],
        "tp_dependencia": integrada["TP_DEPENDENCIA"],
        "rede_administrativa": integrada["TP_DEPENDENCIA"].astype(int).map(REDES),
        "co_etapa_ensino": integrada["ETAPA_ENSINO"].map(carga.CODIGOS_ETAPA),
        "no_etapa_ensino": integrada["ETAPA_ENSINO"],
        "qt_matriculas": integrada["MATRICULAS_ETAPA_2025"],
        "vl_ideb": integrada["IDEB_2025"],
        "situacao_ideb": integrada["SITUACAO_IDEB_2025"],
        "ano_referencia": integrada["ANO_CENSO"],
    })
    return {"origem": "csv", "escolas_etapas": padronizar(dados), "referencias": {}}


# ---------------------------------------------------------------------------
# Fonte 2: views do PostgreSQL (somente leitura)
# ---------------------------------------------------------------------------

def ler_consulta(conexao, consulta):
    """Executa uma consulta de leitura e devolve um DataFrame."""
    cursor = conexao.cursor()
    try:
        cursor.execute(consulta)
        colunas = [c.name if hasattr(c, "name") else c[0] for c in cursor.description]
        return pd.DataFrame(cursor.fetchall(), columns=colunas)
    finally:
        cursor.close()


def carregar_postgres(pedir_senha=False, conectar=None):
    """Lê as views 04 (base), 01, 02 e 03 em uma sessão somente leitura.

    A autenticação é a mesma da carga (carga_postgres.abrir_conexao): banco
    fixo, PGHOST/PGPORT/PGUSER na sessão e senha digitada ou do arquivo de
    senhas do PostgreSQL. Nenhuma credencial fica no código.
    """
    conexao = (conectar or carga.abrir_conexao)(pedir_senha)
    try:
        conexao.read_only = True  # psycopg 3: o banco recusa qualquer escrita
        escolas = ler_consulta(conexao, CONSULTA_VIEW_ESCOLAS)
        matriculas = ler_consulta(conexao, CONSULTA_VIEW_MATRICULAS)
        rede_etapa = ler_consulta(conexao, CONSULTA_VIEW_REDE_ETAPA)
        macedonia = ler_consulta(conexao, CONSULTA_VIEW_MACEDONIA)
    finally:
        conexao.close()

    base = padronizar(escolas)
    conferir_view_matriculas(base, matriculas)
    return {
        "origem": "postgres",
        "escolas_etapas": base,
        "referencias": {
            "ideb_rede_etapa": converter_numericos(rede_etapa),
            "jardim_macedonia": converter_numericos(macedonia),
        },
    }


def converter_numericos(dados):
    """Converte colunas Decimal/None das views em float/NaN."""
    dados = dados.copy()
    for coluna in dados.columns:
        if coluna.startswith(("media", "mediana", "menor", "maior", "ideb", "diferenca")):
            dados[coluna] = dados[coluna].map(numero_ou_nan).astype("float64")
        elif coluna.startswith(("qt_", "tp_")):
            dados[coluna] = pd.to_numeric(dados[coluna]).astype("int64")
    return dados


def conferir_view_matriculas(base, matriculas):
    """A view 01 deve ter as mesmas chaves e matrículas da view 04."""
    chave = ["co_entidade", "co_etapa_ensino", "ano_referencia"]
    comparacao = base[chave + ["qt_matriculas"]].merge(
        matriculas.astype({"ano_referencia": "int64", "qt_matriculas": "int64"}),
        on=chave, how="outer", suffixes=("_v4", "_v1"), indicator=True)
    divergentes = (comparacao["_merge"] != "both") | (
        comparacao["qt_matriculas_v4"] != comparacao["qt_matriculas_v1"])
    if divergentes.any():
        raise ErroFonteDados(f"Views 01 e 04 divergem em {int(divergentes.sum())} linhas.")


def carregar(origem, pedir_senha=False):
    """Ponto único de entrada: devolve os dados no formato padronizado."""
    if origem == "csv":
        return carregar_csv()
    if origem == "postgres":
        return carregar_postgres(pedir_senha)
    raise ValueError("origem deve ser 'csv' ou 'postgres'")
