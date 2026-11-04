"""
Integração do Censo Escolar 2025 com os resultados oficiais do IDEB 2025.

Execute a partir da pasta Entrega_final (depois de preparar_censo_2025.py):
    python integrar_ideb.py
"""

import pandas as pd

import analise
import ingestao
import tratamento


CODIGOS_ESCOLAS_INTERESSE = ["35010281", "35044386"]


def preparar_base_censo_por_etapa():
    """Lê o Censo e mantém escolas públicas ativas com matrícula por etapa."""
    dados = ingestao.carregar_dados_brutos(ingestao.CAMINHO_DADOS_BRUTOS)
    tratamento.validar_ano_censo(dados)
    matriculas = ingestao.carregar_dados_brutos(
        ingestao.CAMINHO_MATRICULAS_BRUTAS
    )
    dados = tratamento.juntar_escolas_e_matriculas(dados, matriculas)
    escolas = tratamento.selecionar_colunas_integracao_ideb(dados)
    escolas = tratamento.filtrar_escolas_publicas_sp(escolas)
    escolas = tratamento.filtrar_escolas_ativas(escolas)
    return tratamento.criar_base_escola_etapa(escolas)


def executar_integracao():
    """Executa download, leitura, tratamento, merge e validações."""
    print("Baixando ou reutilizando os arquivos oficiais do IDEB 2025...")
    arquivos = ingestao.baixar_arquivos_ideb_2025()
    metadados = ingestao.salvar_metadados_fontes_ideb(arquivos)

    print("Lendo as três planilhas oficiais...")
    ideb_bruto = ingestao.carregar_dados_ideb_2025(arquivos)
    ideb = tratamento.tratar_dados_ideb_2025(ideb_bruto)

    base_etapas = preparar_base_censo_por_etapa()
    resultado = tratamento.integrar_censo_com_ideb(base_etapas, ideb)
    tratamento.salvar_integracao_ideb(
        resultado,
        tratamento.CAMINHO_DADOS_IDEB_PROCESSADOS,
    )

    # Releitura simples para conferir que o CSV foi realmente gravado.
    resultado_salvo = pd.read_csv(
        tratamento.CAMINHO_DADOS_IDEB_PROCESSADOS,
        sep=";",
        dtype={
            "CO_ENTIDADE": str,
            "ANO_CENSO": str,
            "ANO_IDEB": str,
            "MATRICULAS_ETAPA_2025": "Int64",
        },
    )

    analise.validar_integracao_ideb(base_etapas, resultado_salvo)
    analise.validar_redes(resultado_salvo)
    analise.mostrar_resultados_escolas_interesse(
        resultado_salvo,
        CODIGOS_ESCOLAS_INTERESSE,
    )
    analise.validar_correspondencia_fonte(
        resultado_salvo,
        ideb,
        CODIGOS_ESCOLAS_INTERESSE,
    )
    print(f"Metadados das fontes salvos em: {metadados}")


if __name__ == "__main__":
    executar_integracao()
