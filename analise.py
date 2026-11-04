"""
Módulo de ANÁLISE.

Responsabilidade: mostrar na tela as consultas e contagens
sobre os dados já tratados. Estas funções NÃO alteram os dados.
"""

import pandas as pd
import matplotlib.pyplot as plt


def mostrar_tamanho_da_base(dados):
    """Mostra quantos registros (linhas) e colunas existem na origem."""
    print("\nTamanho da base original (registros, colunas):")
    print(dados.shape)


def mostrar_escolas(escolas, titulo):
    """Mostra a tabela de escolas com um título."""
    print(f"\n{titulo}")
    print(escolas)


def mostrar_quantidade(escolas, titulo):
    """Mostra quantas linhas (escolas) existem no DataFrame."""
    print(f"\n{titulo}")
    print(escolas.shape[0])


def contar_por_situacao(escolas):
    """Conta os registros por situação de funcionamento."""
    print("\nSituação de funcionamento:")
    # dropna=False -> também conta os valores ausentes, se existirem
    print(
        escolas["TP_SITUACAO_FUNCIONAMENTO"]
        .value_counts(dropna=False)
    )


def mostrar_matriculas_por_etapa(escolas):
    """Mostra as matrículas do Fundamental e do Médio por escola."""
    print("\nMatrículas por etapa de ensino:")
    print(escolas[[
        "NO_ENTIDADE",
        "QT_MAT_FUND",
        "QT_MAT_MED"
    ]])


def mostrar_tipos_das_matriculas(escolas):
    """Confere o tipo de dado das colunas de matrículas."""
    print("\nTipos de dados após conversão:")
    print(
        escolas[
            ["QT_MAT_FUND", "QT_MAT_MED"]
        ].dtypes
    )


def mostrar_total_por_escola(escolas):
    """Mostra as matrículas por etapa e o total de cada escola."""
    print("\nTotal de matrículas por escola:")
    print(escolas[[
        "NO_ENTIDADE",
        "QT_MAT_FUND",
        "QT_MAT_MED",
        "TOTAL_MATRICULAS"
    ]])


def mostrar_escolas_com_ensino(escolas):
    """Mostra as escolas com Ensino Fundamental ou Médio."""
    print("\nEscolas com Ensino Fundamental ou Médio:")
    print(escolas[[
        "NO_ENTIDADE",
        "TOTAL_MATRICULAS"
    ]])


def mostrar_total_geral(escolas):
    """Soma as matrículas de todas as escolas selecionadas."""
    total_geral = escolas["TOTAL_MATRICULAS"].sum()
    print("\nTotal de matrículas (Fundamental + Médio) no bairro:")
    print(total_geral)


def conferir_arquivo_salvo(caminho):
    """Lê novamente o CSV tratado para conferir o que foi salvo."""
    dados_salvos = pd.read_csv(
        caminho,
        sep=";",
        dtype=str
    )

    print("\nValidando o arquivo tratado:")
    print(dados_salvos[[
        "NO_ENTIDADE",
        "TOTAL_MATRICULAS"
    ]])

    print("\nQuantidade de registros salvos:")
    print(dados_salvos.shape[0])


def mostrar_estatisticas_matriculas(escolas):
    """Mostra estatísticas descritivas das matrículas."""

    print("\nEstatísticas das matrículas em São Paulo:")

    print(
        escolas["TOTAL_MATRICULAS"].describe()
    )



def comparar_matriculas_por_rede(escolas):
    """Compara as matrículas por dependência administrativa."""

    print("\nMatrículas por rede de ensino:")

    resultado = escolas.groupby("TP_DEPENDENCIA")[
        "TOTAL_MATRICULAS"
    ].agg(["count", "mean", "median"])

    print(resultado)



def grafico_media_matriculas_por_rede(escolas):
    """Mostra a média de matrículas por rede de ensino."""

    medias = escolas.groupby("TP_DEPENDENCIA")[
        "TOTAL_MATRICULAS"
    ].mean()

    # Substituir os códigos pelos nomes das redes
    medias.index = medias.index.map({
        "1": "Federal",
        "2": "Estadual",
        "3": "Municipal"
    })

    # Criar o gráfico
    medias.plot(kind="bar")

    plt.title(
        "Média de matrículas no Fundamental e Médio por rede\n"
        "São Paulo - Censo Escolar 2025"
    )
    plt.xlabel("Rede de ensino")
    plt.ylabel("Média de matrículas por escola")
    plt.xticks(rotation=0)
    plt.tight_layout()
    plt.savefig(
        "graficos/media_matriculas_por_rede_2025.png",
        dpi=300,
        bbox_inches="tight"
    )
    print("\nGráfico salvo com sucesso!")
    plt.show()



def grafico_matriculas_macedonia(escolas):
    """Cria o gráfico das matrículas do Jardim Macedônia."""

    plt.figure(figsize=(9, 5))

    plt.bar(
        escolas["NO_ENTIDADE"],
        escolas["TOTAL_MATRICULAS"]
    )

    plt.title("Matrículas no Jardim Macedônia - Censo Escolar 2025")
    plt.xlabel("Escolas")
    plt.ylabel("Matrículas no Fundamental e Médio")
    plt.xticks(rotation=15, ha="right")

    plt.tight_layout()

    plt.savefig(
        "graficos/matriculas_macedonia_2025.png",
        dpi=300,
        bbox_inches="tight"
    )

    print("\nGráfico do Jardim Macedônia salvo com sucesso!")

    plt.show()


def validar_integracao_ideb(base_etapas, resultado):
    """Mostra contagens e verifica se o merge preservou as linhas."""
    chave = ["CO_ENTIDADE", "ANO_CENSO", "ETAPA_ENSINO"]
    antes = base_etapas.shape[0]
    depois = resultado.shape[0]
    duplicados = resultado.duplicated(subset=chave).sum()
    divulgado = resultado["IDEB_2025"].notna()
    escolas_sem_ideb = (
        resultado.groupby("CO_ENTIDADE")["IDEB_2025"]
        .apply(lambda valores: valores.notna().sum() == 0)
        .sum()
    )

    print("\nValidação da integração Censo 2025 x IDEB 2025:")
    print(f"Registros escola/etapa antes do merge: {antes}")
    print(f"Registros escola/etapa depois do merge: {depois}")
    print(f"Chaves duplicadas após o merge: {duplicados}")
    print(f"Registros escola/etapa com IDEB divulgado: {divulgado.sum()}")
    print(f"Registros escola/etapa sem IDEB divulgado: {(~divulgado).sum()}")
    print(
        "Escolas distintas com pelo menos um IDEB divulgado: "
        f"{resultado.loc[divulgado, 'CO_ENTIDADE'].nunique()}"
    )
    print(
        "Escolas distintas sem IDEB em nenhuma etapa: "
        f"{escolas_sem_ideb}"
    )

    if antes != depois:
        raise ValueError("O merge alterou a quantidade de registros escola/etapa")
    if duplicados != 0:
        raise ValueError("A integração produziu chaves duplicadas")


def validar_redes(resultado):
    """Confere se a rede do Censo coincide com a rede informada no IDEB."""
    localizados = resultado["REDE_IDEB"].notna()
    divergencias = resultado.loc[
        localizados & (resultado["REDE_CENSO"] != resultado["REDE_IDEB"])
    ]
    print(f"Divergências de rede Censo x IDEB: {divergencias.shape[0]}")

    if not divergencias.empty:
        raise ValueError("Foram encontradas redes divergentes entre as fontes")


def mostrar_resultados_escolas_interesse(resultado, codigos):
    """Mostra os resultados das duas escolas do Jardim Macedônia."""
    colunas = [
        "CO_ENTIDADE",
        "NO_ENTIDADE",
        "ETAPA_ENSINO",
        "ANO_CENSO",
        "MATRICULAS_ETAPA_2025",
        "ANO_IDEB",
        "IDEB_2025",
        "SITUACAO_IDEB_2025",
    ]
    escolas = resultado[resultado["CO_ENTIDADE"].isin(codigos)]
    print("\nResultados das escolas de interesse:")
    print(escolas[colunas].to_string(index=False))


def validar_correspondencia_fonte(resultado, ideb, codigos):
    """Confere se o IDEB integrado é igual ao valor lido da fonte oficial."""
    colunas_chave = ["CO_ENTIDADE", "ETAPA_ENSINO"]
    integrado = resultado[
        resultado["CO_ENTIDADE"].isin(codigos)
    ][colunas_chave + ["IDEB_2025"]]
    oficial = ideb[
        ideb["CO_ENTIDADE"].isin(codigos)
    ][colunas_chave + ["IDEB_2025"]]

    comparacao = pd.merge(
        integrado,
        oficial,
        on=colunas_chave,
        how="left",
        suffixes=("_INTEGRADO", "_OFICIAL"),
        validate="one_to_one",
    )
    iguais = (
        comparacao["IDEB_2025_INTEGRADO"].eq(
            comparacao["IDEB_2025_OFICIAL"]
        )
        | (
            comparacao["IDEB_2025_INTEGRADO"].isna()
            & comparacao["IDEB_2025_OFICIAL"].isna()
        )
    )
    print(f"Valores das escolas de interesse iguais à fonte: {iguais.all()}")

    if not iguais.all():
        raise ValueError("O resultado integrado diverge da fonte oficial")
