"""
Módulo de INGESTÃO.

Responsabilidade: obter e ler os arquivos originais do Censo Escolar 2024
e do IDEB 2025, sem aplicar regras de negócio aos dados.
"""

from datetime import date
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

import pandas as pd
import requests

# Caminho do arquivo CSV original (dados brutos - nunca alteramos este arquivo)
CAMINHO_DADOS_BRUTOS = "data/raw/escolas_2024.csv"

# O Inep publica um arquivo oficial por etapa de ensino.
PASTA_IDEB = Path("data/raw/ideb")
FONTES_IDEB_2025 = {
    "Anos iniciais do Ensino Fundamental": (
        "https://download.inep.gov.br/ideb/resultados/"
        "divulgacao_anos_iniciais_escolas_2025.zip"
    ),
    "Anos finais do Ensino Fundamental": (
        "https://download.inep.gov.br/ideb/resultados/"
        "divulgacao_anos_finais_escolas_2025.zip"
    ),
    "Ensino Médio": (
        "https://download.inep.gov.br/ideb/resultados/"
        "divulgacao_ensino_medio_escolas_2025.zip"
    ),
}

# Colunas reais encontradas na linha 10 das planilhas oficiais.
COLUNAS_IDEB_2025 = {
    "SG_UF",
    "CO_MUNICIPIO",
    "NO_MUNICIPIO",
    "ID_ESCOLA",
    "NO_ESCOLA",
    "REDE",
    "VL_INDICADOR_REND_2025",
    "VL_NOTA_MATEMATICA_2025",
    "VL_NOTA_PORTUGUES_2025",
    "VL_NOTA_MEDIA_2025",
    "VL_OBSERVADO_2025",
}


def carregar_dados_brutos(caminho):
    """Lê o CSV original e retorna o DataFrame completo."""
    # sep=";"  -> o arquivo do INEP usa ponto e vírgula como separador
    # dtype=str -> lemos tudo como texto para não perder zeros nem códigos
    dados = pd.read_csv(caminho, sep=";", dtype=str)
    return dados


def baixar_arquivo(url, caminho, timeout=(10, 120)):
    """Baixa um ZIP oficial, com timeout e validação da resposta."""
    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)

    # Evita baixar novamente um arquivo oficial que já está íntegro.
    if caminho.exists() and is_zipfile(caminho):
        return caminho

    caminho_temporario = caminho.with_suffix(caminho.suffix + ".part")

    try:
        with requests.get(url, stream=True, timeout=timeout) as resposta:
            resposta.raise_for_status()

            with open(caminho_temporario, "wb") as arquivo:
                for bloco in resposta.iter_content(chunk_size=1024 * 1024):
                    if bloco:
                        arquivo.write(bloco)

        if not is_zipfile(caminho_temporario):
            raise ValueError("a resposta recebida não é um arquivo ZIP válido")

        caminho_temporario.replace(caminho)
        return caminho

    except (requests.RequestException, OSError, ValueError) as erro:
        caminho_temporario.unlink(missing_ok=True)
        raise RuntimeError(
            f"Não foi possível baixar o arquivo oficial: {url}"
        ) from erro


def baixar_arquivos_ideb_2025():
    """Baixa os três arquivos oficiais do IDEB 2025 por escola."""
    arquivos = {}

    for etapa, url in FONTES_IDEB_2025.items():
        nome_arquivo = url.rsplit("/", maxsplit=1)[-1]
        caminho = PASTA_IDEB / nome_arquivo
        arquivos[etapa] = baixar_arquivo(url, caminho)

    return arquivos


def calcular_sha256(caminho):
    """Calcula a assinatura SHA-256 de um arquivo baixado."""
    assinatura = sha256()

    with open(caminho, "rb") as arquivo:
        for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
            assinatura.update(bloco)

    return assinatura.hexdigest()


def salvar_metadados_fontes_ideb(arquivos):
    """Registra URL, data da extração e assinatura dos arquivos."""
    registros = []

    for etapa, caminho in arquivos.items():
        registros.append({
            "ETAPA_ENSINO": etapa,
            "URL_FONTE": FONTES_IDEB_2025[etapa],
            "DATA_EXTRACAO": date.today().isoformat(),
            "ARQUIVO": Path(caminho).name,
            "SHA256": calcular_sha256(caminho),
        })

    metadados = pd.DataFrame(registros)
    caminho_metadados = PASTA_IDEB / "fontes_ideb_2025.csv"
    metadados.to_csv(
        caminho_metadados,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )
    return caminho_metadados


def ler_planilha_ideb(caminho_zip, etapa):
    """Lê somente as colunas de 2025 do XLSX guardado no ZIP oficial."""
    try:
        with ZipFile(caminho_zip) as arquivo_zip:
            planilhas = [
                nome
                for nome in arquivo_zip.namelist()
                if nome.lower().endswith(".xlsx")
            ]

            if len(planilhas) != 1:
                raise ValueError(
                    "o ZIP deveria conter exatamente uma planilha XLSX"
                )

            conteudo = BytesIO(arquivo_zip.read(planilhas[0]))

    except (BadZipFile, KeyError, OSError) as erro:
        raise ValueError(
            f"Não foi possível ler o ZIP oficial: {caminho_zip}"
        ) from erro

    # header=9: os nomes técnicos dos campos estão na linha 10 do Excel.
    dados = pd.read_excel(
        conteudo,
        header=9,
        dtype=str,
        usecols=lambda coluna: coluna in COLUNAS_IDEB_2025,
        engine="openpyxl",
    )

    faltantes = COLUNAS_IDEB_2025 - set(dados.columns)
    if faltantes:
        raise ValueError(
            f"Colunas esperadas não encontradas no IDEB: {sorted(faltantes)}"
        )

    dados["ETAPA_ENSINO"] = etapa
    dados["ANO_IDEB"] = "2025"
    dados["ARQUIVO_FONTE"] = Path(caminho_zip).name
    return dados


def carregar_dados_ideb_2025(arquivos):
    """Reúne as três etapas oficiais em um único DataFrame."""
    partes = []

    for etapa, caminho in arquivos.items():
        partes.append(ler_planilha_ideb(caminho, etapa))

    return pd.concat(partes, ignore_index=True)
