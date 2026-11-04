
import pandas as pd

# Caminho do arquivo integrado
arquivo = "data/processed/escolas_publicas_sp_ideb_2025.csv"

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
