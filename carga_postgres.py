"""
Carga do Censo Escolar 2025 e do IDEB/Saeb 2025 para o PostgreSQL
(banco educacao_jd_macedonia, schema educacao).

Modos de execução (a partir da pasta Entrega_final):

    python carga_postgres.py --dry-run
        Lê os CSVs, monta as quatro tabelas em memória e valida tudo contra o
        DDL aprovado. NÃO abre conexão com o banco.

    python carga_postgres.py --load [--pedir-senha]
        Repete todas as validações do dry-run e, se tudo passar, grava as
        quatro tabelas em UMA transação. Qualquer falha desfaz tudo (ROLLBACK).
        A carga é recusada se alguma tabela de destino já tiver registros.

Contrato de destino: modelagem/fisico/01_criacao_tabelas.sql
Driver: psycopg 3 (importado somente no modo --load).
"""

import argparse
import getpass
import sys
from collections import namedtuple
from decimal import Decimal

import numpy as np
import pandas as pd

import ingestao
import tratamento

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BANCO = "educacao_jd_macedonia"
SCHEMA = "educacao"

ANO_REFERENCIA = int(tratamento.ANO_CENSO)  # 2025
CODIGO_MUNICIPIO = ingestao.CODIGO_MUNICIPIO_SAO_PAULO  # "3550308"

CAMINHO_ESCOLAS = ingestao.CAMINHO_DADOS_BRUTOS
CAMINHO_MATRICULAS = ingestao.CAMINHO_MATRICULAS_BRUTAS
CAMINHO_INTEGRADA = tratamento.CAMINHO_DADOS_IDEB_PROCESSADOS

# Escolas principais da análise (mesmos códigos de integrar_ideb.py).
ESCOLAS_INTERESSE = ["35010281", "35044386"]  # EMEF César Yasigi, EE David Nasser

# Código curto de cada etapa (decisão da modelagem aprovada).
CODIGOS_ETAPA = {
    "Anos iniciais do Ensino Fundamental": "AI",
    "Anos finais do Ensino Fundamental": "AF",
    "Ensino Médio": "EM",
}

SITUACOES_IDEB = {
    "DIVULGADO": "Divulgado",
    "NAO_DIVULGADO": "Não divulgado pelo Inep",
    "NAO_LOCALIZADO": "Escola/etapa não localizada no arquivo do Inep",
}

# ---------------------------------------------------------------------------
# Contrato do DDL: colunas, tipos e restrições de cada tabela
# ---------------------------------------------------------------------------

# tipo = nome usado pelo PostgreSQL em information_schema.columns
Coluna = namedtuple("Coluna", "nome tipo tamanho precisao escala aceita_nulo")


def coluna(nome, tipo, tamanho=None, precisao=None, escala=None, aceita_nulo=False):
    return Coluna(nome, tipo, tamanho, precisao, escala, aceita_nulo)


VARCHAR, SMALLINT, INTEGER, BOOLEAN, NUMERIC = (
    "character varying", "smallint", "integer", "boolean", "numeric")

CONTRATO = {
    "etapa_ensino": [
        coluna("co_etapa_ensino", VARCHAR, 2),
        coluna("no_etapa_ensino", VARCHAR, 60),
        coluna("coluna_matricula_censo", VARCHAR, 30),
    ],
    "escola": [
        coluna("co_entidade", VARCHAR, 8),
        coluna("no_entidade", VARCHAR, 100),
        coluna("co_municipio", VARCHAR, 7),
        coluna("no_distrito", VARCHAR, 100),
        coluna("tp_dependencia", SMALLINT),
        coluna("tp_situacao_funcionamento", SMALLINT),
        coluna("ano_censo", SMALLINT),
        coluna("possui_registro_matricula", BOOLEAN),
    ],
    "oferta_ensino": [
        coluna("co_entidade", VARCHAR, 8),
        coluna("co_etapa_ensino", VARCHAR, 2),
        coluna("ano_referencia", SMALLINT),
        coluna("qt_matriculas", INTEGER),
    ],
    "indicador_educacional": [
        coluna("co_entidade", VARCHAR, 8),
        coluna("co_etapa_ensino", VARCHAR, 2),
        coluna("ano_referencia", SMALLINT),
        coluna("situacao_ideb", VARCHAR, 60),
        coluna("vl_indicador_rendimento", NUMERIC, precisao=7, escala=6, aceita_nulo=True),
        coluna("vl_nota_matematica", NUMERIC, precisao=5, escala=2, aceita_nulo=True),
        coluna("vl_nota_portugues", NUMERIC, precisao=5, escala=2, aceita_nulo=True),
        coluna("vl_nota_media_padronizada", NUMERIC, precisao=8, escala=6, aceita_nulo=True),
        coluna("vl_ideb", NUMERIC, precisao=3, escala=1, aceita_nulo=True),
    ],
}

COLUNAS_DESTINO = {tabela: [c.nome for c in colunas] for tabela, colunas in CONTRATO.items()}

# Quantidade de restrições por tipo no DDL (p = PK, f = FK, u = UNIQUE, c = CHECK).
RESTRICOES_ESPERADAS = {
    "etapa_ensino": {"p": 1, "u": 2, "c": 2},
    "escola": {"p": 1, "c": 7},
    "oferta_ensino": {"p": 1, "f": 2, "c": 2},
    "indicador_educacional": {"p": 1, "f": 1, "c": 10},
}

# Ordem obrigatória: as tabelas "pai" antes das tabelas "filhas" (FKs).
ORDEM_CARGA = ["etapa_ensino", "escola", "oferta_ensino", "indicador_educacional"]

CHAVES_PRIMARIAS = {
    "etapa_ensino": ["co_etapa_ensino"],
    "escola": ["co_entidade"],
    "oferta_ensino": ["co_entidade", "co_etapa_ensino", "ano_referencia"],
    "indicador_educacional": ["co_entidade", "co_etapa_ensino", "ano_referencia"],
}

# Origem de cada indicador na base integrada -> coluna de destino.
INDICADORES = {
    "INDICADOR_RENDIMENTO_2025": "vl_indicador_rendimento",
    "NOTA_MATEMATICA_SAEB_2025": "vl_nota_matematica",
    "NOTA_PORTUGUES_SAEB_2025": "vl_nota_portugues",
    "NOTA_MEDIA_PADRONIZADA_2025": "vl_nota_media_padronizada",
    "IDEB_2025": "vl_ideb",
}

# Valores aprovados na modelagem. Servem só para CONFERIR, nunca para ajustar.
CONTAGENS_ESPERADAS = {
    "etapa_ensino": 3,
    "escola": 7905,
    "oferta_ensino": 5984,
    "indicador_educacional": 2973,
}
ESPERADO_SEM_IDEB = 377
ESPERADO_SEM_REGISTRO_MATRICULA = 718

COLUNAS_FONTE = {
    "escolas": ["NU_ANO_CENSO", "CO_ENTIDADE", "NO_ENTIDADE", "CO_MUNICIPIO",
                "NO_DISTRITO", "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO"],
    "matriculas": ["NU_ANO_CENSO", "CO_ENTIDADE", "QT_MAT_FUND",
                   "QT_MAT_FUND_AI", "QT_MAT_FUND_AF", "QT_MAT_MED"],
    "integrada": ["CO_ENTIDADE", "ETAPA_ENSINO", "ANO_CENSO", "ANO_IDEB",
                  "MATRICULAS_ETAPA_2025", "SITUACAO_IDEB_2025", *INDICADORES.keys()],
}

# Tipos Python que o psycopg converte diretamente para o PostgreSQL.
TIPOS_ACEITOS_PELO_DRIVER = (str, int, bool, Decimal, type(None))


class ErroValidacao(Exception):
    """Os dados locais não podem seguir para a carga."""


class ErroCarga(Exception):
    """A carga no banco foi recusada ou falhou (a transação é desfeita)."""


# ---------------------------------------------------------------------------
# Registro das validações
# ---------------------------------------------------------------------------

class RelatorioValidacao:
    """Guarda o resultado de cada verificação (OK ou FALHA) e um detalhe."""

    def __init__(self):
        self.resultados = []

    def verificar(self, grupo, nome, condicao, detalhe=""):
        self.resultados.append((grupo, nome, bool(condicao), detalhe))
        return bool(condicao)

    def falhas(self):
        return [r for r in self.resultados if not r[2]]

    def interromper_se_falhou(self, etapa):
        """Para a preparação na primeira etapa que tiver alguma falha."""
        falhas = self.falhas()
        if falhas:
            linhas = [f"  - [{g}] {n}: {d}" for g, n, _, d in falhas]
            raise ErroValidacao(
                f"A validação falhou na etapa '{etapa}'. Os dados NÃO estão "
                "prontos para carga:\n" + "\n".join(linhas)
            )

    def imprimir(self):
        grupo_atual = None
        for grupo, nome, ok, detalhe in self.resultados:
            if grupo != grupo_atual:
                print(f"\n[{grupo}]")
                grupo_atual = grupo
            marca = "OK   " if ok else "FALHA"
            print(f"  {marca} {nome}" + (f" ({detalhe})" if detalhe else ""))


# ---------------------------------------------------------------------------
# 1. Leitura das fontes
# ---------------------------------------------------------------------------

def ler_csv(caminho, encoding="utf-8"):
    """Lê um CSV do projeto mantendo tudo como texto.

    dtype=str             -> códigos INEP não perdem zeros nem viram número
    keep_default_na=False -> textos como "NA" ou "null" NÃO viram nulo
    na_values=[""]        -> somente a célula vazia é considerada ausente
    """
    return pd.read_csv(caminho, sep=";", dtype=str, encoding=encoding,
                       keep_default_na=False, na_values=[""])


def ler_fontes():
    """Lê os três CSVs de 2025 usados na carga."""
    return {
        "escolas": ler_csv(CAMINHO_ESCOLAS),
        "matriculas": ler_csv(CAMINHO_MATRICULAS),
        # A base integrada foi salva com BOM (utf-8-sig) pelo pipeline.
        "integrada": ler_csv(CAMINHO_INTEGRADA, encoding="utf-8-sig"),
    }


def validar_fontes(fontes, relatorio):
    """Confere colunas obrigatórias, ano e município das fontes."""
    grupo = "Fontes"
    for nome, colunas in COLUNAS_FONTE.items():
        faltantes = [c for c in colunas if c not in fontes[nome].columns]
        relatorio.verificar(grupo, f"{nome}: colunas obrigatórias presentes",
                            not faltantes, f"faltando {faltantes}" if faltantes else "")
    relatorio.interromper_se_falhou("leitura das fontes")

    escolas, matriculas = fontes["escolas"], fontes["matriculas"]
    for nome, dados in [("escolas", escolas), ("matriculas", matriculas)]:
        anos = sorted(dados["NU_ANO_CENSO"].dropna().unique())
        relatorio.verificar(grupo, f"{nome}: somente NU_ANO_CENSO = {ANO_REFERENCIA}",
                            anos == [str(ANO_REFERENCIA)], f"encontrado {anos}")
        relatorio.verificar(grupo, f"{nome}: CO_ENTIDADE sem duplicidade",
                            not dados["CO_ENTIDADE"].duplicated().any())
    relatorio.verificar(grupo, f"escolas: somente CO_MUNICIPIO = {CODIGO_MUNICIPIO}",
                        (escolas["CO_MUNICIPIO"] == CODIGO_MUNICIPIO).all())
    orfas = ~matriculas["CO_ENTIDADE"].isin(escolas["CO_ENTIDADE"])
    relatorio.verificar(grupo, "matriculas: toda escola existe no cadastro",
                        not orfas.any(), f"{int(orfas.sum())} sem cadastro")
    relatorio.interromper_se_falhou("leitura das fontes")


# ---------------------------------------------------------------------------
# 2. Conversão de tipos
# ---------------------------------------------------------------------------

def converter_inteiro(serie, nome):
    """Converte texto em inteiro (Int64) sem aceitar valores inválidos.

    errors="raise" -> se aparecer um texto que não é número, o script para
    em vez de transformar o valor em nulo silenciosamente.
    """
    try:
        return pd.to_numeric(serie, errors="raise").astype("Int64")
    except (ValueError, TypeError) as erro:
        raise ErroValidacao(f"Valor não inteiro na coluna {nome}: {erro}") from erro


def converter_decimal(serie):
    """Converte texto em Decimal, mantendo None onde o valor está ausente.

    Decimal guarda o número exatamente como está no CSV (ex.: 0.971452),
    sem os arredondamentos binários do tipo float. É o mesmo comportamento
    do NUMERIC do PostgreSQL.
    """
    return serie.map(lambda valor: None if pd.isna(valor) else Decimal(valor)).astype(object)


def cabe_em_numeric(valor, precisao, escala):
    """Indica se um Decimal cabe em NUMERIC(precisao, escala) sem arredondar."""
    _, digitos, expoente = valor.as_tuple()
    casas_decimais = max(0, -expoente)
    digitos_inteiros = max(0, len(digitos) + expoente)
    return casas_decimais <= escala and digitos_inteiros <= precisao - escala


def valor_para_banco(valor):
    """Converte um valor do pandas para um tipo Python simples.

    pd.NA / NaN -> None (vira NULL no banco, nunca zero)
    numpy.int64 / numpy.bool_ -> int / bool (o driver não aceita tipos numpy)
    """
    if valor is None or (not isinstance(valor, (str, Decimal)) and pd.isna(valor)):
        return None
    if isinstance(valor, np.generic):
        return valor.item()
    return valor


# ---------------------------------------------------------------------------
# 3. Preparação de cada tabela
# ---------------------------------------------------------------------------

def preparar_etapa_ensino():
    """Monta os 3 registros de domínio a partir da regra do pipeline."""
    registros = [
        {
            "co_etapa_ensino": CODIGOS_ETAPA[descricao],
            "no_etapa_ensino": descricao,
            "coluna_matricula_censo": coluna_censo,
        }
        for descricao, coluna_censo in tratamento.ETAPAS_E_MATRICULAS.items()
    ]
    return pd.DataFrame(registros, columns=COLUNAS_DESTINO["etapa_ensino"])


def preparar_escola(escolas, matriculas):
    """Mapeia a Tabela de Escola para educacao.escola (1 linha por INEP)."""
    escola = pd.DataFrame({
        "co_entidade": escolas["CO_ENTIDADE"],
        "no_entidade": escolas["NO_ENTIDADE"],
        "co_municipio": escolas["CO_MUNICIPIO"],
        "no_distrito": escolas["NO_DISTRITO"],
        "tp_dependencia": converter_inteiro(escolas["TP_DEPENDENCIA"], "TP_DEPENDENCIA"),
        "tp_situacao_funcionamento": converter_inteiro(
            escolas["TP_SITUACAO_FUNCIONAMENTO"], "TP_SITUACAO_FUNCIONAMENTO"),
        "ano_censo": converter_inteiro(escolas["NU_ANO_CENSO"], "NU_ANO_CENSO"),
        # Campo derivado: a escola aparece na Tabela de Matrícula 2025?
        # FALSE significa "matrícula desconhecida", e não "zero matrículas".
        "possui_registro_matricula": escolas["CO_ENTIDADE"].isin(matriculas["CO_ENTIDADE"]),
    })
    return escola[COLUNAS_DESTINO["escola"]]


def preparar_oferta_ensino(matriculas, etapa_ensino):
    """Transforma as colunas de matrícula por etapa em linhas (unpivot).

    Para cada escola e cada etapa, cria uma linha SOMENTE se houver
    matrícula maior que zero. Zero = a escola não oferece a etapa.
    """
    partes = []
    for _, etapa in etapa_ensino.iterrows():
        coluna_censo = etapa["coluna_matricula_censo"]
        quantidade = converter_inteiro(matriculas[coluna_censo], coluna_censo)
        tem_matricula = quantidade > 0
        partes.append(pd.DataFrame({
            "co_entidade": matriculas.loc[tem_matricula, "CO_ENTIDADE"],
            "co_etapa_ensino": etapa["co_etapa_ensino"],
            "ano_referencia": converter_inteiro(
                matriculas.loc[tem_matricula, "NU_ANO_CENSO"], "NU_ANO_CENSO"),
            "qt_matriculas": quantidade[tem_matricula],
        }))
    oferta = pd.concat(partes, ignore_index=True)
    return oferta[COLUNAS_DESTINO["oferta_ensino"]]


def preparar_indicador_educacional(integrada):
    """Mapeia a base integrada Censo x IDEB para educacao.indicador_educacional.

    ano_referencia vem de ANO_CENSO (sempre 2025). ANO_IDEB não é usado,
    pois fica vazio nas linhas "não localizadas"; essa ausência é
    representada por situacao_ideb.
    """
    indicador = pd.DataFrame({
        "co_entidade": integrada["CO_ENTIDADE"],
        "co_etapa_ensino": integrada["ETAPA_ENSINO"].map(CODIGOS_ETAPA),
        "ano_referencia": converter_inteiro(integrada["ANO_CENSO"], "ANO_CENSO"),
        "situacao_ideb": integrada["SITUACAO_IDEB_2025"],
    })
    for origem, destino in INDICADORES.items():
        indicador[destino] = converter_decimal(integrada[origem])
    return indicador[COLUNAS_DESTINO["indicador_educacional"]]


def preparar_tabelas(fontes):
    """Prepara as quatro tabelas na ordem de carga."""
    etapa_ensino = preparar_etapa_ensino()
    return {
        "etapa_ensino": etapa_ensino,
        "escola": preparar_escola(fontes["escolas"], fontes["matriculas"]),
        "oferta_ensino": preparar_oferta_ensino(fontes["matriculas"], etapa_ensino),
        "indicador_educacional": preparar_indicador_educacional(fontes["integrada"]),
    }


# ---------------------------------------------------------------------------
# 4. Validações locais (espelham as restrições do DDL)
# ---------------------------------------------------------------------------

def validar_estrutura(tabelas, relatorio):
    """Colunas iguais às do DDL, NOT NULL respeitado e textos cabendo no VARCHAR."""
    grupo = "Estrutura e NOT NULL"
    for nome in ORDEM_CARGA:
        dados = tabelas[nome]
        relatorio.verificar(grupo, f"{nome}: colunas na ordem do DDL",
                            list(dados.columns) == COLUNAS_DESTINO[nome])
        obrigatorias = [c.nome for c in CONTRATO[nome] if not c.aceita_nulo]
        nulos = dados[obrigatorias].isna().sum()
        nulos = nulos[nulos > 0].to_dict()
        relatorio.verificar(grupo, f"{nome}: colunas NOT NULL sem nulos",
                            not nulos, f"nulos: {nulos}" if nulos else "")
        for c in CONTRATO[nome]:
            if c.tipo == VARCHAR:
                maior = int(dados[c.nome].str.len().max())
                relatorio.verificar(grupo, f"{nome}.{c.nome} cabe em VARCHAR({c.tamanho})",
                                    maior <= c.tamanho, f"maior = {maior}")


def validar_chaves_primarias(tabelas, relatorio):
    """Nenhuma PK repetida (equivale a PRIMARY KEY)."""
    for nome in ORDEM_CARGA:
        chave = CHAVES_PRIMARIAS[nome]
        repetidas = int(tabelas[nome].duplicated(subset=chave).sum())
        relatorio.verificar("Chaves primárias", f"pk_{nome} ({', '.join(chave)}) única",
                            repetidas == 0, f"{repetidas} repetidas" if repetidas else "")
    etapa = tabelas["etapa_ensino"]
    for nome_coluna in ["no_etapa_ensino", "coluna_matricula_censo"]:
        relatorio.verificar("Chaves primárias", f"uq_etapa_ensino_{nome_coluna} única",
                            etapa[nome_coluna].is_unique)


def contar_orfas(filha, pai, colunas):
    """Quantas linhas da tabela filha não encontram a chave na tabela pai."""
    ligacao = filha[colunas].merge(pai[colunas].drop_duplicates(), on=colunas,
                                   how="left", indicator=True)
    return int((ligacao["_merge"] == "left_only").sum())


def validar_chaves_estrangeiras(tabelas, relatorio):
    """Nenhuma FK órfã (equivale às FOREIGN KEY do DDL)."""
    oferta, indicador = tabelas["oferta_ensino"], tabelas["indicador_educacional"]
    casos = [
        ("fk_oferta_ensino_escola", oferta, tabelas["escola"], ["co_entidade"]),
        ("fk_oferta_ensino_etapa_ensino", oferta, tabelas["etapa_ensino"], ["co_etapa_ensino"]),
        ("fk_indicador_educacional_oferta_ensino", indicador, oferta,
         CHAVES_PRIMARIAS["oferta_ensino"]),
    ]
    for nome, filha, pai, colunas in casos:
        orfas = contar_orfas(filha, pai, colunas)
        relatorio.verificar("Chaves estrangeiras", f"{nome} sem órfãs", orfas == 0,
                            f"{orfas} órfãs" if orfas else "")


def validar_checks_escola(escola, relatorio):
    """CHECKs de educacao.escola."""
    grupo, v = "CHECK escola", relatorio.verificar
    v(grupo, "ck_escola_co_entidade (8 dígitos)",
      escola["co_entidade"].str.fullmatch(r"[0-9]{8}").all())
    v(grupo, "ck_escola_no_entidade (não vazio)", escola["no_entidade"].str.strip().ne("").all())
    v(grupo, "ck_escola_co_municipio (= 3550308)", (escola["co_municipio"] == CODIGO_MUNICIPIO).all())
    v(grupo, "ck_escola_no_distrito (não vazio)", escola["no_distrito"].str.strip().ne("").all())
    v(grupo, "ck_escola_tp_dependencia (1 a 4)", escola["tp_dependencia"].isin([1, 2, 3, 4]).all())
    v(grupo, "ck_escola_tp_situacao_funcionamento (1 a 4)",
      escola["tp_situacao_funcionamento"].isin([1, 2, 3, 4]).all())
    v(grupo, f"ck_escola_ano_censo (= {ANO_REFERENCIA})", (escola["ano_censo"] == ANO_REFERENCIA).all())


def validar_checks_etapa(etapa, relatorio):
    """CHECKs de educacao.etapa_ensino."""
    grupo = "CHECK etapa_ensino"
    relatorio.verificar(grupo, "ck_etapa_ensino_co_etapa_ensino (AI, AF, EM)",
                        set(etapa["co_etapa_ensino"]) == {"AI", "AF", "EM"})
    relatorio.verificar(grupo, "ck_etapa_ensino_coluna_matricula_censo",
                        set(etapa["coluna_matricula_censo"])
                        == {"QT_MAT_FUND_AI", "QT_MAT_FUND_AF", "QT_MAT_MED"})


def validar_checks_oferta(oferta, relatorio):
    """CHECKs de educacao.oferta_ensino."""
    grupo = "CHECK oferta_ensino"
    relatorio.verificar(grupo, f"ck_oferta_ensino_ano_referencia (= {ANO_REFERENCIA})",
                        (oferta["ano_referencia"] == ANO_REFERENCIA).all())
    relatorio.verificar(grupo, "ck_oferta_ensino_qt_matriculas (> 0)",
                        (oferta["qt_matriculas"] > 0).all())
    relatorio.verificar(grupo, "INTEGER: qt_matriculas cabe", oferta["qt_matriculas"].max() < 2**31)


def validar_checks_indicador(indicador, relatorio):
    """CHECKs de educacao.indicador_educacional e precisão dos NUMERIC."""
    grupo, v = "CHECK indicador_educacional", relatorio.verificar
    situacao = indicador["situacao_ideb"]
    valores = list(INDICADORES.values())
    preenchido = indicador[valores].notna()
    divulgado = situacao == SITUACOES_IDEB["DIVULGADO"]
    nao_localizado = situacao == SITUACOES_IDEB["NAO_LOCALIZADO"]

    v(grupo, f"ck_indicador_educacional_ano_referencia (= {ANO_REFERENCIA})",
      (indicador["ano_referencia"] == ANO_REFERENCIA).all())
    v(grupo, "ck_indicador_educacional_situacao_ideb (3 valores)",
      situacao.isin(SITUACOES_IDEB.values()).all())
    v(grupo, "ck_indicador_educacional_ideb_conforme_situacao",
      (divulgado == preenchido["vl_ideb"]).all())
    v(grupo, "ck_indicador_educacional_divulgado_completo",
      preenchido.loc[divulgado].all().all())
    v(grupo, "ck_indicador_educacional_nao_localizado_sem_valores",
      not preenchido.loc[nao_localizado].any().any())

    faixas = {
        "vl_indicador_rendimento": (0, 1),
        "vl_nota_matematica": (0, 500),
        "vl_nota_portugues": (0, 500),
        "vl_nota_media_padronizada": (0, 10),
        "vl_ideb": (0, 10),
    }
    for nome_coluna, (minimo, maximo) in faixas.items():
        existentes = indicador[nome_coluna].dropna()
        v(grupo, f"ck_indicador_educacional_{nome_coluna} ({minimo} a {maximo})",
          all(minimo <= valor <= maximo for valor in existentes))

    for c in CONTRATO["indicador_educacional"]:
        if c.tipo == NUMERIC:
            existentes = indicador[c.nome].dropna()
            v("Precisão NUMERIC",
              f"{c.nome} cabe em NUMERIC({c.precisao},{c.escala}) sem arredondar",
              all(cabe_em_numeric(valor, c.precisao, c.escala) for valor in existentes))


def validar_regras_de_negocio(fontes, tabelas, relatorio):
    """Regras que envolvem mais de uma tabela ou a comparação com a origem."""
    grupo, v = "Regras de negócio e origem", relatorio.verificar
    escolas, matriculas, integrada = fontes["escolas"], fontes["matriculas"], fontes["integrada"]
    escola, oferta = tabelas["escola"], tabelas["oferta_ensino"]
    indicador = tabelas["indicador_educacional"]

    # Códigos INEP preservados exatamente como na origem.
    v(grupo, "códigos INEP de escola idênticos à origem (sem truncar)",
      escola["co_entidade"].tolist() == escolas["CO_ENTIDADE"].tolist())
    v(grupo, "códigos INEP de oferta e indicador com 8 dígitos",
      oferta["co_entidade"].str.fullmatch(r"[0-9]{8}").all()
      and indicador["co_entidade"].str.fullmatch(r"[0-9]{8}").all())
    v(grupo, "códigos INEP do indicador idênticos à base integrada",
      indicador["co_entidade"].tolist() == integrada["CO_ENTIDADE"].tolist())
    etapas_sem_codigo = integrada.loc[indicador["co_etapa_ensino"].isna(), "ETAPA_ENSINO"].unique()
    v(grupo, "toda ETAPA_ENSINO da base integrada tem código",
      len(etapas_sem_codigo) == 0, f"sem código: {list(etapas_sem_codigo)}")

    # Escolas sem registro de matrícula continuam na tabela escola.
    sem_registro = int((~escola["possui_registro_matricula"]).sum())
    esperado_sem_registro = int((~escolas["CO_ENTIDADE"].isin(matriculas["CO_ENTIDADE"])).sum())
    v(grupo, "escolas sem registro de matrícula preservadas",
      sem_registro == esperado_sem_registro and len(escola) == len(escolas),
      f"{sem_registro} escolas")
    sem_registro_com_oferta = escola.loc[~escola["possui_registro_matricula"]
                                         & escola["co_entidade"].isin(set(oferta["co_entidade"]))]
    v(grupo, "oferta somente para escolas com registro de matrícula", sem_registro_com_oferta.empty)

    # Matrículas zero excluídas; nenhuma linha positiva perdida.
    colunas_etapa = list(tratamento.ETAPAS_E_MATRICULAS.values())
    quantidades = [converter_inteiro(matriculas[c], c) for c in colunas_etapa]
    positivas = sum(int((q > 0).sum()) for q in quantidades)
    zeros = sum(int((q == 0).sum()) for q in quantidades)
    v(grupo, "ofertas = células de matrícula > 0 na origem", len(oferta) == positivas,
      f"{positivas} positivas; {zeros} células zero excluídas")
    fund = converter_inteiro(matriculas["QT_MAT_FUND"], "QT_MAT_FUND")
    v(grupo, "QT_MAT_FUND = AI + AF (por isso não é carregada)",
      (fund == quantidades[0] + quantidades[1]).all())

    # Indicador apenas para ofertas de escolas públicas em atividade.
    publicas_ativas = escola.loc[escola["tp_dependencia"].isin([1, 2, 3])
                                 & (escola["tp_situacao_funcionamento"] == 1), "co_entidade"]
    oferta_publica = oferta[oferta["co_entidade"].isin(publicas_ativas)]
    chave = CHAVES_PRIMARIAS["oferta_ensino"]
    v(grupo, "indicador = ofertas de escolas públicas ativas (mesmas chaves)",
      set(map(tuple, indicador[chave].values)) == set(map(tuple, oferta_publica[chave].values)))

    # Matrículas da base integrada iguais às da oferta.
    comparacao = indicador[chave].assign(
        qt_integrada=converter_inteiro(integrada["MATRICULAS_ETAPA_2025"], "MATRICULAS_ETAPA_2025")
    ).merge(oferta, on=chave, how="left")
    v(grupo, "MATRICULAS_ETAPA_2025 = qt_matriculas da oferta",
      (comparacao["qt_integrada"] == comparacao["qt_matriculas"]).all())

    # Nulos preservados: nenhum NULL virou zero e nenhum valor foi perdido.
    for origem, destino in INDICADORES.items():
        nulos_origem = int(integrada[origem].isna().sum())
        nulos_destino = int(indicador[destino].isna().sum())
        v(grupo, f"{destino}: nulos preservados", nulos_origem == nulos_destino,
          f"{nulos_destino} nulos")
    anos_ideb = set(integrada["ANO_IDEB"].dropna())
    nao_localizado = indicador["situacao_ideb"] == SITUACOES_IDEB["NAO_LOCALIZADO"]
    v(grupo, f"ANO_IDEB vazio somente nas linhas 'não localizada'; demais = {ANO_REFERENCIA}",
      (integrada["ANO_IDEB"].isna() == nao_localizado).all()
      and anos_ideb == {str(ANO_REFERENCIA)})


def conferir_contagens(tabelas, relatorio):
    """Compara as contagens com a modelagem (apenas confere, não ajusta)."""
    for nome in ORDEM_CARGA:
        obtido, esperado = len(tabelas[nome]), CONTAGENS_ESPERADAS[nome]
        relatorio.verificar("Contagens", f"{nome}: {obtido} registros", obtido == esperado,
                            f"esperado {esperado}")
    sem_ideb = int(tabelas["indicador_educacional"]["vl_ideb"].isna().sum())
    relatorio.verificar("Contagens", f"indicadores sem IDEB divulgado: {sem_ideb}",
                        sem_ideb == ESPERADO_SEM_IDEB, f"esperado {ESPERADO_SEM_IDEB}")
    sem_registro = int((~tabelas["escola"]["possui_registro_matricula"]).sum())
    relatorio.verificar("Contagens", f"escolas sem registro de matrícula: {sem_registro}",
                        sem_registro == ESPERADO_SEM_REGISTRO_MATRICULA,
                        f"esperado {ESPERADO_SEM_REGISTRO_MATRICULA}")


def validar_tabelas(fontes, tabelas, relatorio):
    """Executa todas as validações, parando na primeira etapa com falha."""
    validar_estrutura(tabelas, relatorio)
    relatorio.interromper_se_falhou("estrutura e NOT NULL")
    validar_chaves_primarias(tabelas, relatorio)
    validar_chaves_estrangeiras(tabelas, relatorio)
    relatorio.interromper_se_falhou("chaves")
    validar_checks_etapa(tabelas["etapa_ensino"], relatorio)
    validar_checks_escola(tabelas["escola"], relatorio)
    validar_checks_oferta(tabelas["oferta_ensino"], relatorio)
    validar_checks_indicador(tabelas["indicador_educacional"], relatorio)
    relatorio.interromper_se_falhou("CHECK e precisão")
    validar_regras_de_negocio(fontes, tabelas, relatorio)
    relatorio.interromper_se_falhou("regras de negócio")
    conferir_contagens(tabelas, relatorio)
    relatorio.interromper_se_falhou("contagens")


# ---------------------------------------------------------------------------
# 5. Plano de carga (o que será enviado ao banco)
# ---------------------------------------------------------------------------

def preparar_registros(dados, colunas):
    """Converte um DataFrame em lista de tuplas de tipos Python simples."""
    return [
        tuple(valor_para_banco(valor) for valor in linha)
        for linha in dados[colunas].itertuples(index=False, name=None)
    ]


def montar_plano_de_carga(tabelas):
    """Monta, em memória, os registros de cada tabela na ordem das FKs."""
    return [
        {
            "tabela": nome,
            "colunas": COLUNAS_DESTINO[nome],
            "registros": preparar_registros(tabelas[nome], COLUNAS_DESTINO[nome]),
        }
        for nome in ORDEM_CARGA
    ]


def validar_plano(plano, relatorio):
    """Confere se todos os valores têm tipos que o driver aceita."""
    for item in plano:
        invalidos = {type(valor).__name__ for registro in item["registros"]
                     for valor in registro if not isinstance(valor, TIPOS_ACEITOS_PELO_DRIVER)}
        relatorio.verificar("Plano de carga",
                            f"{item['tabela']}: valores com tipos aceitos pelo driver",
                            not invalidos, f"tipos inválidos: {sorted(invalidos)}" if invalidos else "")
    relatorio.interromper_se_falhou("plano de carga")


# ---------------------------------------------------------------------------
# 6. Persistência no PostgreSQL (somente no modo --load)
# ---------------------------------------------------------------------------
# Todas as consultas usam parâmetros (%s) para os DADOS. Nomes de schema,
# tabela e coluna vêm das constantes acima e são compostos com psycopg.sql,
# que os coloca entre aspas com segurança. Nenhum valor é interpolado no SQL.

CONSULTAS_FK_ORFAS = {
    "fk_oferta_ensino_escola": """
        SELECT count(*) FROM educacao.oferta_ensino o
        LEFT JOIN educacao.escola e ON e.co_entidade = o.co_entidade
        WHERE e.co_entidade IS NULL""",
    "fk_oferta_ensino_etapa_ensino": """
        SELECT count(*) FROM educacao.oferta_ensino o
        LEFT JOIN educacao.etapa_ensino t ON t.co_etapa_ensino = o.co_etapa_ensino
        WHERE t.co_etapa_ensino IS NULL""",
    "fk_indicador_educacional_oferta_ensino": """
        SELECT count(*) FROM educacao.indicador_educacional i
        LEFT JOIN educacao.oferta_ensino o
               ON o.co_entidade = i.co_entidade
              AND o.co_etapa_ensino = i.co_etapa_ensino
              AND o.ano_referencia = i.ano_referencia
        WHERE o.co_entidade IS NULL""",
}

CONSULTA_INDICADOR_FORA_DO_ESCOPO = """
    SELECT count(*) FROM educacao.indicador_educacional i
    JOIN educacao.escola e ON e.co_entidade = i.co_entidade
    WHERE NOT (e.tp_dependencia IN (1, 2, 3) AND e.tp_situacao_funcionamento = 1)"""

CONSULTA_OFERTA_SEM_REGISTRO = """
    SELECT count(*) FROM educacao.oferta_ensino o
    JOIN educacao.escola e ON e.co_entidade = o.co_entidade
    WHERE NOT e.possui_registro_matricula"""

CONSULTA_ESCOLAS_INTERESSE = """
    SELECT o.co_entidade, o.co_etapa_ensino, o.qt_matriculas, i.situacao_ideb,
           i.vl_indicador_rendimento, i.vl_nota_matematica, i.vl_nota_portugues,
           i.vl_nota_media_padronizada, i.vl_ideb
    FROM educacao.oferta_ensino o
    JOIN educacao.indicador_educacional i
      ON i.co_entidade = o.co_entidade
     AND i.co_etapa_ensino = o.co_etapa_ensino
     AND i.ano_referencia = o.ano_referencia
    WHERE o.co_entidade = ANY(%s) AND o.ano_referencia = %s
    ORDER BY o.co_entidade, o.co_etapa_ensino"""


def calcular_esperado(tabelas):
    """Calcula, a partir das tabelas em memória, o que o banco deve conter."""
    escola, oferta = tabelas["escola"], tabelas["oferta_ensino"]
    indicador = tabelas["indicador_educacional"]
    interesse = (
        oferta[oferta["co_entidade"].isin(ESCOLAS_INTERESSE)]
        .merge(indicador, on=CHAVES_PRIMARIAS["oferta_ensino"])
        .sort_values(["co_entidade", "co_etapa_ensino"])
    )
    colunas_interesse = (["co_entidade", "co_etapa_ensino", "qt_matriculas", "situacao_ideb"]
                         + list(INDICADORES.values()))
    return {
        "contagens": {nome: len(tabelas[nome]) for nome in ORDEM_CARGA},
        "chaves_duplicadas": {nome: 0 for nome in ORDEM_CARGA},
        "fks_orfas": {nome: 0 for nome in CONSULTAS_FK_ORFAS},
        "indicador_fora_de_publica_ativa": 0,
        "oferta_sem_registro_matricula": 0,
        "situacoes_ideb": {s: int(n) for s, n in indicador["situacao_ideb"].value_counts().items()},
        "sem_ideb": int(indicador["vl_ideb"].isna().sum()),
        "sem_registro_matricula": int((~escola["possui_registro_matricula"]).sum()),
        "soma_matriculas": int(oferta["qt_matriculas"].sum()),
        "escolas_interesse": preparar_registros(interesse, colunas_interesse),
    }


def nome_tabela(tabela):
    """educacao.<tabela> como identificador SQL seguro."""
    from psycopg import sql
    return sql.Identifier(SCHEMA, tabela)


def montar_insert(tabela, colunas):
    """INSERT INTO educacao.<tabela> (colunas) VALUES (%s, %s, ...)."""
    from psycopg import sql
    return sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
        nome_tabela(tabela),
        sql.SQL(", ").join(sql.Identifier(c) for c in colunas),
        sql.SQL(", ").join(sql.Placeholder() * len(colunas)),
    )


def consultar_um(cursor, consulta, parametros=None):
    """Executa uma consulta e devolve o primeiro valor da primeira linha."""
    cursor.execute(consulta, parametros)
    return cursor.fetchone()[0]


def verificar_banco_e_schema(cursor):
    """Garante que a conexão está no banco e no schema corretos."""
    banco = consultar_um(cursor, "SELECT current_database()")
    if banco != BANCO:
        raise ErroCarga(f"Banco incorreto: {banco}. Esperado: {BANCO}.")
    existe = consultar_um(cursor, "SELECT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = %s)",
                          (SCHEMA,))
    if not existe:
        raise ErroCarga(f"O schema {SCHEMA} não existe no banco {BANCO}.")
    print(f"  OK banco {banco} e schema {SCHEMA}")


def verificar_estrutura_tabelas(cursor):
    """Compara colunas, tipos e restrições do banco com o contrato do DDL."""
    for tabela in ORDEM_CARGA:
        cursor.execute(
            """SELECT column_name, data_type, character_maximum_length,
                      numeric_precision, numeric_scale, is_nullable
               FROM information_schema.columns
               WHERE table_schema = %s AND table_name = %s
               ORDER BY ordinal_position""",
            (SCHEMA, tabela),
        )
        no_banco = [
            Coluna(nome, tipo, tamanho if tipo == VARCHAR else None,
                   precisao if tipo == NUMERIC else None,
                   escala if tipo == NUMERIC else None, nulo == "YES")
            for nome, tipo, tamanho, precisao, escala, nulo in cursor.fetchall()
        ]
        if not no_banco:
            raise ErroCarga(f"A tabela {SCHEMA}.{tabela} não existe.")
        if no_banco != CONTRATO[tabela]:
            raise ErroCarga(f"A estrutura de {SCHEMA}.{tabela} difere do DDL aprovado.")

        cursor.execute(
            """SELECT c.contype, count(*)
               FROM pg_constraint c
               JOIN pg_class t ON t.oid = c.conrelid
               JOIN pg_namespace n ON n.oid = t.relnamespace
               WHERE n.nspname = %s AND t.relname = %s
               GROUP BY c.contype""",
            (SCHEMA, tabela),
        )
        restricoes = {tipo: int(qtd) for tipo, qtd in cursor.fetchall()}
        if restricoes != RESTRICOES_ESPERADAS[tabela]:
            raise ErroCarga(f"As restrições de {SCHEMA}.{tabela} diferem do DDL aprovado: "
                            f"{restricoes} (esperado {RESTRICOES_ESPERADAS[tabela]}).")
    print("  OK estrutura das 4 tabelas (colunas, tipos, PK, FK, UNIQUE, CHECK)")


def bloquear_tabelas(cursor):
    """Impede escritas de outras sessões até o fim da transação (leitura liberada)."""
    from psycopg import sql
    cursor.execute(sql.SQL("LOCK TABLE {} IN SHARE ROW EXCLUSIVE MODE").format(
        sql.SQL(", ").join(nome_tabela(t) for t in ORDEM_CARGA)))


def verificar_tabelas_vazias(cursor):
    """Política conservadora: recusa a carga se alguma tabela já tiver dados."""
    from psycopg import sql
    com_dados = [
        tabela for tabela in ORDEM_CARGA
        if consultar_um(cursor, sql.SQL("SELECT EXISTS (SELECT 1 FROM {})").format(
            nome_tabela(tabela)))
    ]
    if com_dados:
        raise ErroCarga(
            "Carga recusada: as tabelas a seguir já possuem registros: "
            + ", ".join(f"{SCHEMA}.{t}" for t in com_dados)
            + ". Este programa não apaga nem substitui dados."
        )
    print("  OK as 4 tabelas estão vazias")


def inserir_dados(cursor, plano):
    """Insere os registros de cada tabela, na ordem das FKs, com parâmetros."""
    for item in plano:
        cursor.executemany(montar_insert(item["tabela"], item["colunas"]), item["registros"])
        print(f"  INSERT {SCHEMA}.{item['tabela']}: {len(item['registros'])} registros enviados")


def medir_banco_apos_carga(cursor):
    """Lê do banco (dentro da mesma transação) os números a conferir."""
    from psycopg import sql
    medidas = {"contagens": {}, "chaves_duplicadas": {}, "fks_orfas": {}}
    for tabela in ORDEM_CARGA:
        medidas["contagens"][tabela] = consultar_um(
            cursor, sql.SQL("SELECT count(*) FROM {}").format(nome_tabela(tabela)))
        chave = sql.SQL(", ").join(sql.Identifier(c) for c in CHAVES_PRIMARIAS[tabela])
        medidas["chaves_duplicadas"][tabela] = consultar_um(cursor, sql.SQL(
            "SELECT count(*) FROM (SELECT {chave} FROM {tabela} "
            "GROUP BY {chave} HAVING count(*) > 1) AS repetidas"
        ).format(chave=chave, tabela=nome_tabela(tabela)))
    for nome, consulta in CONSULTAS_FK_ORFAS.items():
        medidas["fks_orfas"][nome] = consultar_um(cursor, consulta)
    medidas["indicador_fora_de_publica_ativa"] = consultar_um(cursor, CONSULTA_INDICADOR_FORA_DO_ESCOPO)
    medidas["oferta_sem_registro_matricula"] = consultar_um(cursor, CONSULTA_OFERTA_SEM_REGISTRO)
    cursor.execute("SELECT situacao_ideb, count(*) FROM educacao.indicador_educacional "
                   "GROUP BY situacao_ideb")
    medidas["situacoes_ideb"] = {situacao: int(qtd) for situacao, qtd in cursor.fetchall()}
    medidas["sem_ideb"] = consultar_um(
        cursor, "SELECT count(*) FROM educacao.indicador_educacional WHERE vl_ideb IS NULL")
    medidas["sem_registro_matricula"] = consultar_um(
        cursor, "SELECT count(*) FROM educacao.escola WHERE NOT possui_registro_matricula")
    medidas["soma_matriculas"] = consultar_um(
        cursor, "SELECT COALESCE(sum(qt_matriculas), 0) FROM educacao.oferta_ensino")
    cursor.execute(CONSULTA_ESCOLAS_INTERESSE, (ESCOLAS_INTERESSE, ANO_REFERENCIA))
    medidas["escolas_interesse"] = [tuple(linha) for linha in cursor.fetchall()]
    return medidas


def comparar_com_esperado(medido, esperado):
    """Compara cada medida do banco com o valor esperado; devolve as falhas."""
    falhas = []
    for chave, valor_esperado in esperado.items():
        valor_medido = medido.get(chave)
        ok = valor_medido == valor_esperado
        print(f"  {'OK   ' if ok else 'FALHA'} {chave}: {valor_medido}"
              + ("" if ok else f" (esperado {valor_esperado})"))
        if not ok:
            falhas.append(chave)
    return falhas


def executar_carga(conexao, plano, esperado, medir=medir_banco_apos_carga):
    """Executa a carga em UMA transação: tudo é gravado ou nada é gravado.

    1. confere banco, schema e estrutura das tabelas
    2. bloqueia as tabelas e confere que estão vazias
    3. insere as 4 tabelas na ordem das FKs
    4. mede o banco e compara com o esperado
    5. COMMIT somente se tudo estiver correto; caso contrário, ROLLBACK
    """
    cursor = conexao.cursor()
    try:
        print("\n1. Conferências antes da escrita")
        verificar_banco_e_schema(cursor)
        verificar_estrutura_tabelas(cursor)
        bloquear_tabelas(cursor)
        verificar_tabelas_vazias(cursor)

        print("\n2. Inserção (transação aberta, nada visível para outras sessões)")
        inserir_dados(cursor, plano)

        print("\n3. Validação no banco, antes do COMMIT")
        falhas = comparar_com_esperado(medir(cursor), esperado)
        if falhas:
            raise ErroCarga(f"Validação pós-carga falhou em: {', '.join(falhas)}.")

        conexao.commit()
        print("\nCOMMIT realizado: os dados de 2025 foram gravados.")
    except BaseException:
        # Qualquer erro (inclusive Ctrl+C) desfaz a transação inteira.
        try:
            conexao.rollback()
            print("\nROLLBACK realizado: nenhum dado foi gravado.")
        except Exception:
            print("\nA conexão foi perdida; o PostgreSQL descarta a transação não confirmada.")
        raise
    finally:
        cursor.close()


def abrir_conexao(pedir_senha=False):
    """Abre a conexão usando os mecanismos padrão do PostgreSQL (libpq).

    O banco é fixo (educacao_jd_macedonia). Servidor, porta e usuário vêm das
    variáveis de ambiente PGHOST, PGPORT e PGUSER (ou dos padrões da libpq).
    A senha vem do arquivo de senhas do PostgreSQL, da variável PGPASSWORD
    definida só na sessão, ou é digitada (--pedir-senha). Ela nunca é
    gravada nem exibida.
    """
    try:
        import psycopg
    except ImportError:
        raise ErroCarga("O driver psycopg não está instalado. "
                        "Execute: python -m pip install -r requirements.txt") from None

    parametros = {"dbname": BANCO, "connect_timeout": 10, "application_name": "carga_postgres"}
    if pedir_senha:
        parametros["password"] = getpass.getpass("Senha do PostgreSQL (não será exibida): ")
    try:
        return psycopg.connect(**parametros)
    except psycopg.Error:
        # "from None" descarta o erro original, que pode conter dados de conexão.
        raise ErroCarga(
            "Não foi possível conectar ao PostgreSQL. Verifique se o serviço está ativo, "
            "as variáveis PGHOST, PGPORT e PGUSER e a autenticação."
        ) from None


def mensagem_segura(erro):
    """Mensagem do servidor sem dados de conexão (usada em erros do driver)."""
    diagnostico = getattr(erro, "diag", None)
    primaria = getattr(diagnostico, "message_primary", None) if diagnostico else None
    return primaria or type(erro).__name__


# ---------------------------------------------------------------------------
# 7. Execução
# ---------------------------------------------------------------------------

def preparar_e_validar():
    """Lê, prepara e valida tudo em memória (comum ao dry-run e à carga)."""
    relatorio = RelatorioValidacao()
    fontes = ler_fontes()
    for nome, dados in fontes.items():
        print(f"Fonte lida: {nome:<11} {dados.shape[0]:>5} linhas x {dados.shape[1]} colunas")
    validar_fontes(fontes, relatorio)
    tabelas = preparar_tabelas(fontes)
    validar_tabelas(fontes, tabelas, relatorio)
    plano = montar_plano_de_carga(tabelas)
    validar_plano(plano, relatorio)
    return tabelas, plano, relatorio


def mostrar_resumo_qualidade(tabelas, plano):
    """Mostra contagens previstas e indicadores de qualidade dos dados."""
    escola, oferta = tabelas["escola"], tabelas["oferta_ensino"]
    indicador = tabelas["indicador_educacional"]

    print("\n=== Contagens previstas (ordem de carga) ===")
    for item in plano:
        print(f"  {SCHEMA}.{item['tabela']:<25} {len(item['registros']):>6} registros")

    print("\n=== Resumo da qualidade dos dados ===")
    sem_registro = int((~escola["possui_registro_matricula"]).sum())
    print(f"  Escolas sem registro de matrícula (matrícula desconhecida): {sem_registro}")
    print(f"  Escolas com pelo menos uma oferta: {oferta['co_entidade'].nunique()}")
    print(f"  Ofertas por etapa: {oferta['co_etapa_ensino'].value_counts().to_dict()}")
    print("  Indicadores por situação:")
    for situacao, quantidade in indicador["situacao_ideb"].value_counts().items():
        print(f"    - {situacao}: {quantidade}")
    print(f"  Indicadores sem IDEB divulgado (vl_ideb NULL): {int(indicador['vl_ideb'].isna().sum())}")
    nulos = indicador[list(INDICADORES.values())].isna().sum().to_dict()
    print(f"  NULLs por coluna do indicador: {nulos}")
    nulos_enviados = sum(valor is None for item in plano
                         if item["tabela"] == "indicador_educacional"
                         for registro in item["registros"] for valor in registro)
    print(f"  NULLs que seriam enviados ao banco (indicador): {nulos_enviados}")


def executar_dry_run():
    """Simulação: valida tudo em memória, sem nenhum acesso ao banco."""
    print("DRY-RUN: nenhuma conexão com o PostgreSQL será aberta.\n")
    tabelas, plano, relatorio = preparar_e_validar()
    relatorio.imprimir()
    mostrar_resumo_qualidade(tabelas, plano)
    drivers = [m for m in ("psycopg", "psycopg2", "sqlalchemy") if m in sys.modules]
    print(f"\nDrivers de banco carregados nesta execução: {drivers or 'nenhum'}")
    print(f"Verificações: {len(relatorio.resultados)} executadas, {len(relatorio.falhas())} falhas.")
    print("RESULTADO: dados PRONTOS para carga (simulação). Nenhum dado foi gravado.")
    return tabelas


def executar_load(pedir_senha=False):
    """Carga real: valida localmente e só então grava em uma transação."""
    print(f"CARGA REAL no banco {BANCO}, schema {SCHEMA}.\n")
    tabelas, plano, relatorio = preparar_e_validar()
    print(f"Validação local: {len(relatorio.resultados)} verificações, "
          f"{len(relatorio.falhas())} falhas.")
    esperado = calcular_esperado(tabelas)
    conexao = abrir_conexao(pedir_senha)
    try:
        executar_carga(conexao, plano, esperado)
    finally:
        conexao.close()


def main(argumentos=None):
    parser = argparse.ArgumentParser(
        description="Carga do Censo 2025 e IDEB 2025 para o PostgreSQL.")
    modo = parser.add_mutually_exclusive_group()
    modo.add_argument("--dry-run", action="store_true",
                      help="simula a carga em memória, sem acessar o banco")
    modo.add_argument("--load", action="store_true",
                      help="grava os dados no banco em uma única transação")
    parser.add_argument("--pedir-senha", action="store_true",
                        help="(com --load) digita a senha do PostgreSQL de forma oculta")
    opcoes = parser.parse_args(argumentos)

    if opcoes.pedir_senha and not opcoes.load:
        parser.error("--pedir-senha só pode ser usado com --load")
    if not (opcoes.dry_run or opcoes.load):
        print("Escolha um modo: --dry-run (simulação) ou --load (carga real).")
        return 2

    try:
        if opcoes.dry_run:
            executar_dry_run()
        else:
            executar_load(opcoes.pedir_senha)
    except ErroValidacao as erro:
        print(f"\nERRO DE VALIDAÇÃO: {erro}")
        return 1
    except ErroCarga as erro:
        print(f"\nCARGA NÃO REALIZADA: {erro}")
        return 1
    except Exception as erro:  # erros do driver durante a carga
        print(f"\nCARGA NÃO REALIZADA ({type(erro).__name__}): {mensagem_segura(erro)}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
