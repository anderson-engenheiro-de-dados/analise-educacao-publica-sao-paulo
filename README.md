# Análise da Educação Pública em São Paulo — Censo Escolar 2024 e IDEB 2025

Projeto acadêmico da pós-graduação em Engenharia de Dados da PUC Minas.

## Objetivo

Estudar características da educação pública no município de São Paulo, com
foco nas escolas do Jardim Macedônia, utilizando dados públicos oficiais do
Inep e técnicas de Engenharia de Dados: ingestão, tratamento, validação,
análise exploratória e integração entre fontes.

## Tecnologias utilizadas

- **Python** (testado com a versão 3.14)
- **pandas** — leitura, tratamento, filtros e `merge` dos dados
- **Matplotlib** — geração dos gráficos
- **requests** — download dos arquivos oficiais do IDEB, com timeout e
  tratamento de erros
- **openpyxl** — leitura das planilhas XLSX do IDEB pelo pandas

O NumPy não é importado diretamente pelos scripts; ele é instalado
automaticamente como dependência do pandas.

## Fontes de dados

| Fonte | Uso no projeto | Onde obter |
|---|---|---|
| Inep — Censo Escolar 2024 (microdados, tabela de escolas) | Cadastro das escolas e matrículas de 2024 | [Microdados do Censo Escolar](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar) |
| Inep — IDEB 2025 por escola | Indicadores de qualidade por etapa | [Resultados do IDEB 2005-2025](https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados/2005-2025) |

Os dados abertos do Inep são disponibilizados, por padrão, sob a licença
Creative Commons Atribuição 4.0 (CC BY 4.0), conforme a Portaria Inep
nº 496/2021. Os créditos dos dados pertencem ao Inep.

### Censo Escolar 2024

O arquivo `data/raw/escolas_2024.csv` contém **8.023 registros e 426 colunas**:
o recorte da tabela de escolas dos microdados do Censo Escolar 2024 para o
município de São Paulo (`CO_MUNICIPIO = 3550308`). São dados institucionais
das escolas (endereço, dependência administrativa, matrículas etc.), sem
dados individuais de alunos.

Esse recorte foi feito antes da construção dos scripts e **não há, neste
repositório, um script que o gere automaticamente**. Para reconstruí-lo:

1. baixe os microdados do Censo Escolar 2024 na página oficial do Inep;
2. abra o CSV da tabela de escolas (separador `;`);
3. mantenha somente as linhas com `CO_MUNICIPIO = 3550308`;
4. salve como `data/raw/escolas_2024.csv`, com separador `;` e codificação
   UTF-8.

### IDEB 2025

Na investigação realizada em 3 de novembro de 2026, não foi identificada uma
API pública e documentada para consultar o IDEB 2025 por escola. Por isso, o
projeto usa os arquivos oficiais para download, sem APIs comunitárias nem
endpoints internos não documentados.

| Etapa | Arquivo do Inep |
|---|---|
| Anos iniciais do Ensino Fundamental | [divulgacao_anos_iniciais_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_anos_iniciais_escolas_2025.zip) |
| Anos finais do Ensino Fundamental | [divulgacao_anos_finais_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_anos_finais_escolas_2025.zip) |
| Ensino Médio | [divulgacao_ensino_medio_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_ensino_medio_escolas_2025.zip) |

Os três ZIPs somam cerca de 200 MB e **não são versionados** (estão no
`.gitignore`). O script `integrar_ideb.py` os baixa automaticamente para
`data/raw/ideb/`. A URL, a data de execução e a assinatura SHA-256 de cada
ZIP ficam registradas em `data/raw/ideb/fontes_ideb_2025.csv`, o que permite
conferir se o arquivo baixado é o mesmo usado nesta análise.

## Estrutura do repositório

```text
.
├── data/
│   ├── raw/
│   │   ├── escolas_2024.csv            # recorte do Censo Escolar 2024 (SP)
│   │   └── ideb/
│   │       ├── fontes_ideb_2025.csv    # URL e SHA-256 dos ZIPs oficiais
│   │       └── *.zip                   # baixados pelo script (não versionados)
│   └── processed/
│       ├── escolas_macedonia.csv               # gerado por main.py
│       └── escolas_publicas_sp_ideb_2025.csv   # gerado por integrar_ideb.py
├── graficos/                   # gráficos gerados por main.py
├── main.py                     # pipeline principal do Censo Escolar 2024
├── ingestao.py                 # leitura do Censo e download/leitura do IDEB
├── tratamento.py               # filtros, conversões, chave escola/etapa e merge
├── analise.py                  # estatísticas, validações e gráficos
├── integrar_ideb.py            # integração Censo 2024 × IDEB 2025
├── explorar_ideb.py            # conferência rápida da base integrada
├── requirements.txt
└── README.md
```

## Etapas do projeto

1. **Ingestão dos dados** — leitura do CSV do Censo como texto (`dtype=str`),
   preservando códigos e zeros à esquerda; download dos ZIPs do IDEB.
2. **Seleção das escolas públicas** — filtro por dependência administrativa.
3. **Tratamento e validação** — escolas em atividade, conversão das matrículas
   para número, cálculo do total e verificação de duplicidades e ausentes.
4. **Análise exploratória** — estatísticas descritivas e comparação de
   matrículas por rede.
5. **Geração dos gráficos** — média de matrículas por rede e matrículas no
   Jardim Macedônia.
6. **Integração com indicadores do IDEB** — uma linha por escola e etapa,
   unida ao IDEB pela chave `CO_ENTIDADE + ETAPA_ENSINO`.
7. **Análises comparativas** — validação do merge, conferência das redes e
   comparação dos resultados das escolas de interesse com a fonte oficial.

## Como executar

### 1. Instalar as dependências

Na pasta do projeto (recomenda-se um ambiente virtual):

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/macOS: source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 2. Executar os scripts

Todos os caminhos são relativos: **execute os comandos de dentro da pasta do
projeto**. A ordem abaixo é a recomendada:

```bash
python main.py
python integrar_ideb.py
python explorar_ideb.py
```

| Script | Precisa de | Gera |
|---|---|---|
| `main.py` | `data/raw/escolas_2024.csv` | `data/processed/escolas_macedonia.csv` e os dois PNGs em `graficos/` |
| `integrar_ideb.py` | `data/raw/escolas_2024.csv` e acesso à internet na primeira execução | ZIPs do IDEB, `fontes_ideb_2025.csv` e `data/processed/escolas_publicas_sp_ideb_2025.csv` |
| `explorar_ideb.py` | `data/processed/escolas_publicas_sp_ideb_2025.csv` | apenas saída no terminal |

Observações:

- `integrar_ideb.py` não depende de `main.py`; ele lê o Censo diretamente.
  Se os ZIPs já existirem e forem válidos, eles são reutilizados.
- `explorar_ideb.py` depende do CSV gerado por `integrar_ideb.py`. O CSV
  integrado já está versionado, então o script também funciona sem baixar
  os ZIPs.
- `main.py` abre as janelas dos gráficos (`plt.show()`); feche cada janela
  para a execução continuar.

### 3. Visualizar os gráficos

Os gráficos são salvos em `graficos/` e podem ser abertos em qualquer
visualizador de imagens ou diretamente no GitHub:

- [Média de matrículas por rede — São Paulo (2024)](graficos/media_matriculas_por_rede.png)
- [Matrículas no Jardim Macedônia (2024)](graficos/matriculas_macedonia.png)

## Resultados

Valores reproduzidos na execução dos scripts em 4 de novembro de 2026.

### Censo Escolar 2024 — município de São Paulo (`main.py`)

| Etapa da seleção | Registros |
|---|---:|
| Base original utilizada | 8.023 |
| Escolas públicas (federais, estaduais e municipais) | 2.886 |
| Escolas públicas ativas | 2.768 |
| Escolas com matrículas no Ensino Fundamental ou Médio | 1.710 |
| Códigos INEP duplicados na seleção final | 0 |

### Integração Censo 2024 × IDEB 2025 (`integrar_ideb.py`)

| Validação | Resultado |
|---|---:|
| Registros escola/etapa antes do merge | 2.991 |
| Registros escola/etapa depois do merge | 2.991 |
| Chaves duplicadas depois do merge | 0 |
| Registros escola/etapa com IDEB 2025 divulgado | 2.577 |
| Registros escola/etapa sem IDEB 2025 divulgado | 414 |
| Escolas distintas com pelo menos um IDEB divulgado | 1.599 |
| Escolas distintas sem IDEB em nenhuma etapa | 111 |
| Divergências de rede entre Censo e IDEB | 0 |
| Valores das escolas de interesse iguais à fonte oficial | Sim |

> **Atenção:** um registro escola/etapa **não equivale** a uma escola
> distinta. Uma mesma escola pode aparecer até três vezes (anos iniciais,
> anos finais e Ensino Médio), uma para cada etapa com matrícula em 2024.
> Por isso, 2.991 registros escola/etapa correspondem a 1.710 escolas.

### Escolas do Jardim Macedônia

No Censo 2024 foram encontrados 6 estabelecimentos no bairro; 4 são
registros públicos (estaduais ou municipais), 3 estão em atividade e 2 têm
matrículas no Ensino Fundamental ou Médio.

**Matrículas (Censo Escolar 2024):**

| Escola | Código INEP | Rede | Etapa | Matrículas 2024 |
|---|---:|---|---|---:|
| EMEF César Yasigi | 35010281 | Municipal | Anos iniciais do EF | 457 |
| EE Jornalista David Nasser | 35044386 | Estadual | Anos iniciais do EF | 205 |
| EE Jornalista David Nasser | 35044386 | Estadual | Anos finais do EF | 350 |
| EE Jornalista David Nasser | 35044386 | Estadual | Ensino Médio | 337 |
| **Total** | | | | **1.349** |

**IDEB 2025 (Inep):**

| Escola | Código INEP | Etapa | IDEB 2025 |
|---|---:|---|---:|
| EMEF César Yasigi | 35010281 | Anos iniciais do EF | 6,4 |
| EE Jornalista David Nasser | 35044386 | Anos iniciais do EF | 5,7 |
| EE Jornalista David Nasser | 35044386 | Anos finais do EF | 3,9 |
| EE Jornalista David Nasser | 35044386 | Ensino Médio | Não divulgado |

A EMEF César Yasigi aparece apenas nos anos iniciais porque o Censo 2024 não
registra matrículas dessa escola nas outras etapas. No arquivo oficial de
Ensino Médio, a EE Jornalista David Nasser possui registro, mas o campo
`VL_OBSERVADO_2025` está com o marcador `-`; por isso o valor permanece
ausente (não é tratado como zero).

> **Matrículas não medem qualidade.** A quantidade de matrículas indica o
> porte da escola em cada etapa; ela não é um indicador de qualidade do
> ensino. O IDEB, por sua vez, combina o rendimento escolar (aprovação) com o
> desempenho no Saeb, e também não é uma média de notas individuais.

## Significado dos principais campos da base integrada

- `ANO_CENSO = 2024`: ano das matrículas e do cadastro da escola;
- `ANO_IDEB = 2025`: edição do indicador oficial;
- `MATRICULAS_ETAPA_2024`: matrículas da etapa, usadas para identificar as
  etapas oferecidas pela escola;
- `IDEB_2025`: índice observado divulgado pelo Inep;
- `ETAPA_ENSINO`: anos iniciais, anos finais ou Ensino Médio;
- `REDE_CENSO` e `REDE_IDEB`: rede informada em cada fonte;
- `SITUACAO_IDEB_2025`: "Divulgado", "Não divulgado pelo Inep" ou
  "Escola/etapa não localizada no arquivo do Inep".

## Limitações metodológicas

- **Anos diferentes:** as matrículas são de 2024 e o IDEB é de 2025. Os anos
  permanecem explícitos e não são tratados como o mesmo período.
- **Recorte do Censo:** o arquivo bruto já é um recorte do município de São
  Paulo, feito fora dos scripts deste repositório.
- **Definição de escola pública:** a análise municipal considera as redes
  federal, estadual e municipal (`TP_DEPENDENCIA` 1, 2 e 3); a análise do
  Jardim Macedônia considera apenas as redes estadual e municipal (2 e 3).
- **Identificação do bairro:** o Jardim Macedônia é identificado pelo texto
  do campo `NO_BAIRRO` (contém "MACEDONIA"); variações de grafia no cadastro
  podem não ser capturadas.
- **Etapas consideradas:** apenas Ensino Fundamental e Médio. Educação
  Infantil, EJA e outras modalidades não entram no total de matrículas.
- **IDEB ausente:** resultados não divulgados (`-`, `ND`, `ND***`) ficam como
  valor ausente, o que reduz a cobertura das comparações.
- **Data em `fontes_ideb_2025.csv`:** o campo `DATA_EXTRACAO` registra a data
  da última execução de `integrar_ideb.py`, mesmo quando os ZIPs já baixados
  são reutilizados. A garantia de que o arquivo é o mesmo é dada pelo SHA-256.
- **Sem testes automatizados:** a verificação é feita pelas validações
  exibidas no terminal durante a execução.

## Estado atual do desenvolvimento

Concluído:

- pipeline de análise do Censo Escolar 2024 (`main.py`);
- gráficos de matrículas por rede e do Jardim Macedônia;
- integração com o IDEB 2025 e validações do merge (`integrar_ideb.py`);
- conferência rápida da base integrada (`explorar_ideb.py`).

Ainda não implementado:

- script para gerar automaticamente o recorte `escolas_2024.csv` a partir dos
  microdados completos;
- análises estatísticas e gráficos sobre o IDEB 2025;
- testes automatizados.

O projeto não utiliza banco de dados nem dashboard nesta etapa.
