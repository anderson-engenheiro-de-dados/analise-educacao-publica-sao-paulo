"""
Ponto de entrada do projeto.

Análise das escolas públicas do Jardim Macedônia (São Paulo)
com os microdados do Censo Escolar 2024.

Execute a partir da pasta Entrega_final:
    python main.py
"""

import ingestao
import tratamento
import analise


def main():
    # 1. INGESTÃO: ler o CSV original
    dados = ingestao.carregar_dados_brutos(ingestao.CAMINHO_DADOS_BRUTOS)
    analise.mostrar_tamanho_da_base(dados)

    
    # 2. TRATAMENTO + ANÁLISE: cada etapa recebe o resultado da anterior
    escolas = tratamento.selecionar_colunas(dados)

    # Selecionar escolas públicas de São Paulo
    escolas_publicas_sp = tratamento.filtrar_escolas_publicas_sp(
        escolas
    )

    analise.mostrar_quantidade(
        escolas_publicas_sp,
        "Quantidade de escolas públicas de São Paulo:"
    )

    print("\nEscolas por dependência administrativa:")
    print(escolas_publicas_sp["TP_DEPENDENCIA"].value_counts())


    # Filtrar escolas públicas de São Paulo em atividade
    escolas_ativas_sp = tratamento.filtrar_escolas_ativas(
        escolas_publicas_sp
    )

    analise.mostrar_quantidade(
        escolas_ativas_sp,
        "Quantidade de escolas públicas ativas em São Paulo:"
    )

    print("\nSituação de funcionamento após o filtro:")
    print(
        escolas_ativas_sp["TP_SITUACAO_FUNCIONAMENTO"]
        .value_counts()
    )


    # Converter as matrículas para números
    escolas_ativas_sp = tratamento.converter_matriculas_para_numero(
        escolas_ativas_sp
    )

    # Calcular o total de matrículas
    escolas_ativas_sp = tratamento.calcular_total_matriculas(
        escolas_ativas_sp
    )

    # Selecionar escolas com Fundamental ou Médio
    escolas_ensino_sp = tratamento.selecionar_escolas_com_ensino(
        escolas_ativas_sp
    )

    # Mostrar a quantidade de registros
    analise.mostrar_quantidade(
        escolas_ensino_sp,
        "Escolas públicas de SP com Fundamental ou Médio:"
    )


    # Verificar valores ausentes na base municipal
    print("\nValores ausentes por coluna:")

    print(escolas_ensino_sp.isna().sum())


    # Verificar escolas duplicadas pelo código INEP
    duplicados = escolas_ensino_sp.duplicated(
        subset=["CO_ENTIDADE"]
    ).sum()

    print("\nQuantidade de códigos INEP duplicados:")
    print(duplicados)


    # Analisar a distribuição das matrículas
    analise.mostrar_estatisticas_matriculas(
        escolas_ensino_sp
    )

    # Comparar matrículas por rede de ensino
    analise.comparar_matriculas_por_rede(
        escolas_ensino_sp
    )

    # Mostrar gráfico da média de matrículas por rede
    analise.grafico_media_matriculas_por_rede(
        escolas_ensino_sp
    )

    # Continuar a análise do Jardim Macedônia
    escolas_macedonia = tratamento.filtrar_jardim_macedonia(escolas)


    escolas_publicas = tratamento.filtrar_escolas_publicas(escolas_macedonia)
    analise.mostrar_escolas(
        escolas_publicas, "Escolas públicas do Jardim Macedônia:"
    )
    analise.mostrar_quantidade(
        escolas_publicas, "Quantidade de registros públicos:"
    )
    analise.contar_por_situacao(escolas_publicas)

    escolas_ativas = tratamento.filtrar_escolas_ativas(escolas_publicas)
    analise.mostrar_escolas(escolas_ativas, "Escolas públicas em atividade:")
    analise.mostrar_quantidade(
        escolas_ativas, "Quantidade de escolas em atividade:"
    )
    analise.mostrar_matriculas_por_etapa(escolas_ativas)

    escolas_ativas = tratamento.converter_matriculas_para_numero(escolas_ativas)
    analise.mostrar_tipos_das_matriculas(escolas_ativas)

    escolas_ativas = tratamento.calcular_total_matriculas(escolas_ativas)
    analise.mostrar_total_por_escola(escolas_ativas)

    escolas_ensino = tratamento.selecionar_escolas_com_ensino(escolas_ativas)
    analise.mostrar_escolas_com_ensino(escolas_ensino)
    analise.mostrar_quantidade(escolas_ensino, "Quantidade de escolas:")
    analise.mostrar_total_geral(escolas_ensino)

    # Gerar gráfico das escolas do Jardim Macedônia
    analise.grafico_matriculas_macedonia(
    escolas_ensino
    )

    # 3. SAÍDA: salvar o CSV processado e conferir o arquivo gerado
    tratamento.salvar_csv_processado(
        escolas_ensino, tratamento.CAMINHO_DADOS_PROCESSADOS
    )
    analise.conferir_arquivo_salvo(tratamento.CAMINHO_DADOS_PROCESSADOS)


# Só executa main() quando rodamos "python main.py" diretamente
if __name__ == "__main__":
    main()
