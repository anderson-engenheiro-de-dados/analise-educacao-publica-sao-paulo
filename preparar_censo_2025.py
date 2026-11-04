"""
Preparação dos dados do Censo Escolar 2025 para o município de São Paulo.

Baixa (ou reutiliza) o ZIP oficial do Inep, confere sua integridade e gera
os recortes de São Paulo usados por main.py e integrar_ideb.py:

    data/raw/escolas_sp_2025.csv     -> Tabela de Escola (cadastro)
    data/raw/matriculas_sp_2025.csv  -> Tabela de Matrícula (quantidades)

Execute a partir da pasta Entrega_final, antes dos demais scripts:
    python preparar_censo_2025.py
"""

import ingestao
import tratamento


def preparar_tabela(caminho_zip, tabela, caminho_saida):
    """Confere, recorta para São Paulo e salva uma tabela do Censo."""
    print(f"\nConferindo o MD5 oficial de {tabela.rsplit('/')[-1]}...")
    ingestao.conferir_md5_oficial(caminho_zip, tabela)

    print("Lendo a tabela nacional e mantendo só o município de São Paulo...")
    dados = ingestao.ler_tabela_censo_do_municipio(
        caminho_zip,
        tabela,
        ingestao.CODIGO_MUNICIPIO_SAO_PAULO,
    )

    # Validações do recorte
    tratamento.validar_ano_censo(dados)
    municipios = dados["CO_MUNICIPIO"].unique().tolist()
    if municipios != [ingestao.CODIGO_MUNICIPIO_SAO_PAULO]:
        raise ValueError(f"Recorte com municípios inesperados: {municipios}")
    if dados["CO_ENTIDADE"].duplicated().any():
        raise ValueError("O recorte possui código INEP duplicado")

    ingestao.salvar_recorte(dados, caminho_saida)
    print(f"Registros: {dados.shape[0]} | Colunas: {dados.shape[1]}")
    print(f"Recorte salvo em: {caminho_saida}")


def main():
    print("Baixando ou reutilizando os microdados oficiais do Censo 2025...")
    caminho_zip = ingestao.baixar_microdados_censo_2025()
    metadados = ingestao.salvar_metadados_fonte_censo(caminho_zip)
    print(f"Metadados da fonte salvos em: {metadados}")

    preparar_tabela(
        caminho_zip,
        ingestao.TABELA_ESCOLA_2025,
        ingestao.CAMINHO_DADOS_BRUTOS,
    )
    preparar_tabela(
        caminho_zip,
        ingestao.TABELA_MATRICULA_2025,
        ingestao.CAMINHO_MATRICULAS_BRUTAS,
    )


if __name__ == "__main__":
    main()
