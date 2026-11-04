
import pandas as pd

# Caminho do arquivo integrado
arquivo = "data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv"

# Ler os dados
df = pd.read_csv(arquivo, sep=";")

# Conferir quantidade de linhas e colunas
print("\nDimensões da base integrada:")
print(df.shape)

# Conferir os tipos de dados
print("\nTipos das colunas do IDEB:")
print(df[[
    "ETAPA_ENSINO",
    "IDEB_2025",
    "NOTA_MATEMATICA_SAEB_2025",
    "NOTA_PORTUGUES_SAEB_2025"
]].dtypes)

# Conferir exemplos de resultados
print("\nPrimeiros valores de IDEB:")
print(df[[
    "NO_ENTIDADE",
    "ETAPA_ENSINO",
    "IDEB_2025"
]].head())


# Calcular o IDEB médio por rede e etapa de ensino
print("\nIDEB 2025 por rede e etapa de ensino:")

media_ideb_rede = df.groupby(
    ["TP_DEPENDENCIA", "ETAPA_ENSINO"]
)["IDEB_2025"].agg(
    ["count", "mean", "median"]
)

print(media_ideb_rede.round(2))


# Consultar o IDEB das escolas do Jardim Macedônia

codigos_escolas = ["35010281", "35044386"]

# Filtrar as escolas pelo código INEP
escolas_macedonia = df[
    df["CO_ENTIDADE"].astype(str).isin(codigos_escolas)
].copy()

print("\nIDEB das escolas do Jardim Macedônia:")

print(escolas_macedonia[[
    "CO_ENTIDADE",
    "NO_ENTIDADE",
    "ETAPA_ENSINO",
    "IDEB_2025"
]].to_string(index=False))
