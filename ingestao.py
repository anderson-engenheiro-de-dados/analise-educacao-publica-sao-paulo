"""
Módulo de INGESTÃO.

Responsabilidade: obter e ler os arquivos originais do Censo Escolar 2025
e do IDEB 2025, sem aplicar regras de negócio aos dados.
"""

from datetime import date
from hashlib import md5, sha256
from io import BytesIO
from pathlib import Path
from zipfile import BadZipFile, ZipFile, is_zipfile

import pandas as pd
import requests

# Recortes do município de São Paulo gerados por preparar_censo_2025.py
# a partir dos microdados oficiais (nunca alteramos estes arquivos à mão).
# Em 2025 o Inep separou o cadastro das escolas e as matrículas em tabelas
# diferentes, ligadas pelo código INEP (CO_ENTIDADE).
CAMINHO_DADOS_BRUTOS = "data/raw/escolas_sp_2025.csv"
CAMINHO_MATRICULAS_BRUTAS = "data/raw/matriculas_sp_2025.csv"

# Microdados oficiais do Censo Escolar 2025, conforme a página do Inep:
# https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar
PASTA_CENSO = Path("data/raw/censo")
URL_CENSO_2025 = (
    "https://download.inep.gov.br/dados_abertos/"
    "microdados_censo_escolar_2025_.zip"
)
VERSAO_CENSO_2025 = "v2 - documento atualizado em julho/2026"
TABELA_ESCOLA_2025 = (
    "microdados_censo_escolar_2025_v2/dados/Tabela_Escola_2025_V2.csv"
)
TABELA_MATRICULA_2025 = (
    "microdados_censo_escolar_2025_v2/dados/Tabela_Matricula_2025_V2.csv"
)

# Código IBGE do município de São Paulo
CODIGO_MUNICIPIO_SAO_PAULO = "3550308"

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


def baixar_microdados_censo_2025():
    """Baixa (ou reutiliza) o ZIP oficial dos microdados do Censo 2025."""
    nome_arquivo = URL_CENSO_2025.rsplit("/", maxsplit=1)[-1]
    caminho = PASTA_CENSO / nome_arquivo
    # O arquivo tem cerca de 512 MB: damos mais tempo para cada leitura.
    return baixar_arquivo(URL_CENSO_2025, caminho, timeout=(10, 300))


def salvar_metadados_fonte_censo(caminho_zip):
    """Registra URL, versão, data, tamanho e assinatura do ZIP do Censo."""
    caminho_zip = Path(caminho_zip)
    metadados = pd.DataFrame([{
        "FONTE": "Inep - Microdados do Censo Escolar da Educação Básica 2025",
        "VERSAO": VERSAO_CENSO_2025,
        "URL_FONTE": URL_CENSO_2025,
        "DATA_REGISTRO": date.today().isoformat(),
        "ARQUIVO": caminho_zip.name,
        "TAMANHO_BYTES": caminho_zip.stat().st_size,
        "SHA256": calcular_sha256(caminho_zip),
    }])
    caminho_metadados = PASTA_CENSO / "fonte_censo_2025.csv"
    metadados.to_csv(
        caminho_metadados,
        sep=";",
        index=False,
        encoding="utf-8-sig",
    )
    return caminho_metadados


def conferir_md5_oficial(caminho_zip, tabela):
    """Compara o MD5 de uma tabela com o valor publicado pelo Inep no ZIP."""
    pasta_dados = tabela.rsplit("/", maxsplit=1)[0]
    nome_tabela = tabela.rsplit("/", maxsplit=1)[-1].lower()

    with ZipFile(caminho_zip) as arquivo_zip:
        texto = arquivo_zip.read(
            f"{pasta_dados}/md5_microdados_ed_basica_2025.txt"
        ).decode("latin-1")

        # Cada linha do arquivo oficial tem o formato: MD5 *nome_do_arquivo
        md5_oficial = None
        for linha in texto.splitlines():
            if linha.strip().lower().endswith(nome_tabela):
                md5_oficial = linha.split()[0].lower()

        assinatura = md5()
        with arquivo_zip.open(tabela) as arquivo:
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                assinatura.update(bloco)

    if md5_oficial != assinatura.hexdigest():
        raise ValueError(f"MD5 diferente do publicado pelo Inep: {tabela}")
    return md5_oficial


def ler_tabela_censo_do_municipio(caminho_zip, tabela, codigo_municipio):
    """Lê uma tabela do ZIP do Censo e mantém só as linhas do município."""
    partes = []

    with ZipFile(caminho_zip) as arquivo_zip:
        with arquivo_zip.open(tabela) as arquivo:
            # encoding="latin-1" -> codificação real dos CSVs do Censo 2025
            # chunksize -> lê o arquivo nacional em blocos, sem esgotar a memória
            blocos = pd.read_csv(
                arquivo,
                sep=";",
                dtype=str,
                encoding="latin-1",
                chunksize=50_000,
            )
            for bloco in blocos:
                partes.append(
                    bloco[bloco["CO_MUNICIPIO"] == codigo_municipio]
                )

    return pd.concat(partes, ignore_index=True)


def salvar_recorte(dados, caminho):
    """Salva um recorte dos microdados em CSV (separador ;, UTF-8)."""
    dados.to_csv(caminho, sep=";", index=False, encoding="utf-8")
    return caminho


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
