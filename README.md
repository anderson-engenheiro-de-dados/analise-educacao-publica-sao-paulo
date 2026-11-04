# Análise da Educação Pública em São Paulo — Censo Escolar 2025 e IDEB 2025

Projeto acadêmico da pós-graduação em Engenharia de Dados da PUC Minas.

## Objetivo

Estudar características da educação pública no município de São Paulo, com
foco nas escolas do Jardim Macedônia, utilizando dados públicos oficiais do
Inep e técnicas de Engenharia de Dados: ingestão, tratamento, validação,
análise exploratória e integração entre fontes.

A pesquisa trata **exclusivamente do ano de 2025**: o cadastro das escolas e
as matrículas vêm do Censo Escolar 2025, e os indicadores de qualidade vêm do
IDEB 2025 (que incorpora as notas do Saeb 2025). O projeto não faz
comparações com outros anos.

## Tecnologias utilizadas

- **Python** (testado com a versão 3.14)
- **pandas** — leitura, tratamento, filtros e `merge` dos dados
- **Matplotlib** — geração dos gráficos
- **requests** — download dos arquivos oficiais, com timeout e tratamento de
  erros
- **openpyxl** — leitura das planilhas XLSX do IDEB pelo pandas

O NumPy não é importado diretamente pelos scripts; ele é instalado
automaticamente como dependência do pandas.

## Fontes de dados

| Fonte | Uso no projeto | Onde obter |
|---|---|---|
| Inep — Microdados do Censo Escolar da Educação Básica 2025 (versão v2, documento atualizado em julho/2026) | Cadastro das escolas e matrículas de 2025 | [Microdados do Censo Escolar](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar) |
| Inep — IDEB 2025 por escola | Indicadores de qualidade por etapa | [Resultados do IDEB 2005-2025](https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados/2005-2025) |

Os dados abertos do Inep são disponibilizados, por padrão, sob a licença
Creative Commons Atribuição 4.0 (CC BY 4.0), conforme a Portaria Inep
nº 496/2021. Os créditos dos dados pertencem ao Inep.

### Censo Escolar 2025

Arquivo oficial: [microdados_censo_escolar_2025_.zip](https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip)
(cerca de 512 MB, **não versionado**). O script `preparar_censo_2025.py`:

1. baixa o ZIP para `data/raw/censo/` ou reutiliza um ZIP válido já salvo;
2. registra URL, versão, data, tamanho e SHA-256 em
   `data/raw/censo/fonte_censo_2025.csv`;
3. confere cada tabela com o MD5 publicado pelo Inep dentro do próprio ZIP;
4. lê as tabelas nacionais (CSV com `;`, codificação Latin-1) em blocos e
   mantém apenas o município de São Paulo pelo código IBGE
   `CO_MUNICIPIO = 3550308`;
5. salva os recortes, sem alterar as colunas:
   - `data/raw/escolas_sp_2025.csv` — Tabela de Escola (7.905 registros,
     290 colunas);
   - `data/raw/matriculas_sp_2025.csv` — Tabela de Matrícula (7.187
     registros, 263 colunas).

**Mudanças de leiaute em 2025** (confirmadas no dicionário de dados oficial):

- as quantidades de matrículas (`QT_MAT_*`) saíram da Tabela de Escola e
  passaram para uma Tabela de Matrícula própria, com uma linha por escola. As
  duas tabelas são unidas pelo código INEP (`CO_ENTIDADE`);
- os campos de endereço, **incluindo o bairro (`NO_BAIRRO`)**, foram retirados
  dos microdados. Segundo o Inep, essas informações continuam disponíveis no
  [Catálogo de Escolas](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas).

As variáveis usadas pelo projeto (`CO_ENTIDADE`, `NO_ENTIDADE`,
`CO_MUNICIPIO`, `TP_DEPENDENCIA`, `TP_SITUACAO_FUNCIONAMENTO`, `QT_MAT_FUND`,
`QT_MAT_FUND_AI`, `QT_MAT_FUND_AF`, `QT_MAT_MED`, `NU_ANO_CENSO`) foram
conferidas no dicionário de dados do Censo 2025. Como o bairro não está
disponível, as colunas de saída trazem o distrito (`NO_DISTRITO`).

> **Observação sobre o download:** o servidor do Inep não envia o certificado
> intermediário da cadeia TLS. Navegadores e o Windows completam a cadeia
> automaticamente, mas o Python pode falhar com `CERTIFICATE_VERIFY_FAILED`.
> Nesse caso, baixe o ZIP pelo navegador, salve-o em `data/raw/censo/` e
> execute o script novamente: o arquivo será reutilizado e validado.

### IDEB 2025

Não foi identificada uma API pública e documentada para consultar o IDEB 2025
por escola. Por isso, o projeto usa os arquivos oficiais para download:

| Etapa | Arquivo do Inep |
|---|---|
| Anos iniciais do Ensino Fundamental | [divulgacao_anos_iniciais_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_anos_iniciais_escolas_2025.zip) |
| Anos finais do Ensino Fundamental | [divulgacao_anos_finais_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_anos_finais_escolas_2025.zip) |
| Ensino Médio | [divulgacao_ensino_medio_escolas_2025.zip](https://download.inep.gov.br/ideb/resultados/divulgacao_ensino_medio_escolas_2025.zip) |

Os três ZIPs somam cerca de 200 MB e **não são versionados**. O script
`integrar_ideb.py` os baixa para `data/raw/ideb/` (ou reutiliza os existentes)
e registra URL, data de execução e SHA-256 em
`data/raw/ideb/fontes_ideb_2025.csv`.

## Estrutura do repositório

```text
.
├── data/
│   ├── raw/
│   │   ├── escolas_sp_2025.csv         # Tabela de Escola 2025 (SP)
│   │   ├── matriculas_sp_2025.csv      # Tabela de Matrícula 2025 (SP)
│   │   ├── censo/
│   │   │   ├── fonte_censo_2025.csv    # URL, versão e SHA-256 do ZIP
│   │   │   └── *.zip                   # microdados (não versionados)
│   │   └── ideb/
│   │       ├── fontes_ideb_2025.csv    # URL e SHA-256 dos ZIPs do IDEB
│   │       └── *.zip                   # IDEB por escola (não versionados)
│   └── processed/
│       ├── escolas_macedonia_2025.csv                  # gerado por main.py
│       └── escolas_publicas_sp_censo_2025_ideb_2025.csv  # integrar_ideb.py
├── graficos/                     # gráficos gerados por main.py
├── preparar_censo_2025.py        # download, validação e recorte do Censo 2025
├── main.py                       # pipeline principal do Censo Escolar 2025
├── ingestao.py                   # download e leitura das fontes oficiais
├── tratamento.py                 # filtros, junções, chave escola/etapa e merge
├── analise.py                    # estatísticas, validações e gráficos
├── integrar_ideb.py              # integração Censo 2025 × IDEB 2025
├── explorar_ideb.py              # exploração da base integrada
├── requirements.txt
└── README.md
```

## Metodologia

### Filtros

| Etapa | Critério |
|---|---|
| Município | `CO_MUNICIPIO = 3550308` (código IBGE de São Paulo) |
| Escolas públicas | `TP_DEPENDENCIA` 1 (federal), 2 (estadual) ou 3 (municipal) |
| Em atividade | `TP_SITUACAO_FUNCIONAMENTO = 1` |
| Com Fundamental ou Médio | `QT_MAT_FUND + QT_MAT_MED > 0` |
| Jardim Macedônia | lista de códigos INEP de referência cadastral (ver abaixo); depois, redes estadual ou municipal (2 ou 3), em atividade e com Fundamental ou Médio |

**Identificação do Jardim Macedônia.** Os microdados do Censo 2025 não
contêm o campo de bairro. Por isso, as escolas do bairro são localizadas por
uma lista fixa de 6 códigos INEP (`CODIGOS_JARDIM_MACEDONIA`, em
`tratamento.py`), usada **apenas como referência cadastral**: ela foi obtida
no cadastro do Censo Escolar 2024, a última edição que trazia o campo
`NO_BAIRRO`. Nenhum dado de 2024 é usado nas análises: rede, situação de
funcionamento, matrículas e IDEB vêm exclusivamente de 2025.

Limitações dessa identificação:

- escolas abertas no bairro depois daquele cadastro não são capturadas;
- a localização das escolas da lista não pode ser reconfirmada com os
  microdados de 2025, que não trazem bairro nem endereço;
- uma alternativa futura é confirmar o bairro pelo
  [Catálogo de Escolas](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/inep-data/catalogo-de-escolas)
  do Inep.

### Valores ausentes

- Todos os CSVs são lidos como texto (`dtype=str`), preservando códigos e
  zeros à esquerda.
- Escolas do cadastro sem linha na Tabela de Matrícula ficam com matrículas
  ausentes (não zero) e não entram no filtro "com Fundamental ou Médio".
- No IDEB, os marcadores `-`, `ND` e `ND***` viram valor ausente, nunca zero.
- Registros escola/etapa não localizados no arquivo do IDEB ficam com os campos
  do IDEB ausentes (inclusive `ANO_IDEB`) e com a situação "Escola/etapa não
  localizada no arquivo do Inep".

### Validações automáticas

- a base precisa conter **somente** `NU_ANO_CENSO = 2025`; caso contrário, o
  pipeline é interrompido;
- MD5 oficial de cada tabela do Censo e SHA-256 dos arquivos baixados;
- recortes com um único município e sem código INEP duplicado;
- junção escola × matrícula `one_to_one`, sem alterar a quantidade de escolas;
- integração com o IDEB `one_to_one`, com a mesma quantidade de registros
  antes e depois do merge e sem chave duplicada;
- rede do Censo igual à rede do IDEB;
- IDEB das escolas de interesse igual ao valor lido da fonte oficial.

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
projeto**, nesta ordem:

```bash
python preparar_censo_2025.py
python main.py
python integrar_ideb.py
python explorar_ideb.py
```

| Script | Precisa de | Gera |
|---|---|---|
| `preparar_censo_2025.py` | internet na primeira execução (ZIP de ~512 MB) | `escolas_sp_2025.csv`, `matriculas_sp_2025.csv` e `fonte_censo_2025.csv` |
| `main.py` | os dois recortes de 2025 | `data/processed/escolas_macedonia_2025.csv` e os dois PNGs de 2025 |
| `integrar_ideb.py` | os dois recortes de 2025 e internet na primeira execução | ZIPs do IDEB, `fontes_ideb_2025.csv` e a base integrada |
| `explorar_ideb.py` | a base integrada | apenas saída no terminal |

Os recortes de 2025 e a base integrada já estão versionados. Por isso, é
possível executar `main.py`, `integrar_ideb.py` (que precisa dos ZIPs do IDEB)
e `explorar_ideb.py` sem baixar os microdados do Censo.

`main.py` abre as janelas dos gráficos (`plt.show()`); feche cada janela para
a execução continuar.

### 3. Gráficos gerados

- [Média de matrículas no Fundamental e Médio por rede — São Paulo, Censo 2025](graficos/media_matriculas_por_rede_2025.png)
- [Matrículas no Jardim Macedônia — Censo 2025](graficos/matriculas_macedonia_2025.png)

## Resultados (Censo Escolar 2025 e IDEB 2025)

Valores obtidos na execução dos scripts em 4 de novembro de 2026.

### Município de São Paulo (`main.py`)

| Etapa da seleção | Registros |
|---|---:|
| Escolas na Tabela de Escola (recorte de SP) | 7.905 |
| Escolas públicas (federais, estaduais e municipais) | 2.948 |
| Escolas públicas ativas | 2.825 |
| Escolas com matrículas no Ensino Fundamental ou Médio | 1.709 |
| Valores ausentes nas colunas analisadas | 0 |
| Códigos INEP duplicados na seleção final | 0 |

Matrículas no Fundamental e Médio por escola (1.709 escolas): média de
751,3, mediana de 723, mínimo de 1 e máximo de 2.237.

| Rede | Escolas | Média de matrículas | Mediana |
|---|---:|---:|---:|
| Federal | 5 | 501,2 | 345 |
| Estadual | 1.093 | 759,3 | 695 |
| Municipal | 611 | 739,2 | 745 |

### Integração Censo 2025 × IDEB 2025 (`integrar_ideb.py`)

| Validação | Resultado |
|---|---:|
| Registros escola/etapa antes do merge | 2.973 |
| Registros escola/etapa depois do merge | 2.973 |
| Chaves duplicadas depois do merge | 0 |
| Registros escola/etapa com IDEB 2025 divulgado | 2.596 |
| Registros escola/etapa sem IDEB 2025 divulgado | 377 |
| — não divulgado pelo Inep | 311 |
| — escola/etapa não localizada no arquivo do Inep | 66 |
| Escolas distintas com pelo menos um IDEB divulgado | 1.618 |
| Escolas distintas sem IDEB em nenhuma etapa | 91 |
| Divergências de rede entre Censo e IDEB | 0 |
| Valores das escolas de interesse iguais à fonte oficial | Sim |

> **Atenção:** um registro escola/etapa **não equivale** a uma escola
> distinta. Uma mesma escola pode aparecer até três vezes (anos iniciais,
> anos finais e Ensino Médio). Os 2.973 registros escola/etapa correspondem a
> 1.709 escolas.

### Escolas do Jardim Macedônia

Dos 6 estabelecimentos identificados, 4 são públicos (estaduais ou
municipais), 3 estão em atividade e 2 têm matrículas no Ensino Fundamental ou
Médio em 2025.

| Escola | Código INEP | Rede | Etapa | Matrículas 2025 | IDEB 2025 |
|---|---:|---|---|---:|---:|
| EMEF César Yasigi | 35010281 | Municipal | Anos iniciais do EF | 464 | 6,4 |
| EE Jornalista David Nasser | 35044386 | Estadual | Anos iniciais do EF | 233 | 5,7 |
| EE Jornalista David Nasser | 35044386 | Estadual | Anos finais do EF | 336 | 3,9 |
| EE Jornalista David Nasser | 35044386 | Estadual | Ensino Médio | 393 | Não divulgado |
| **Total** | | | | **1.426** | |

No arquivo oficial de Ensino Médio, a EE Jornalista David Nasser possui
registro, mas o campo `VL_OBSERVADO_2025` está com o marcador `-`; por isso o
valor permanece ausente.

> **Matrículas não medem qualidade.** A quantidade de matrículas indica o
> porte da escola em cada etapa, não a qualidade do ensino. O IDEB combina o
> rendimento escolar (aprovação) com o desempenho no Saeb e também não é uma
> média de notas individuais.

## Significado dos principais campos da base integrada

- `ANO_CENSO = 2025`: ano das matrículas e do cadastro da escola;
- `ANO_IDEB = 2025`: edição do indicador oficial;
- `MATRICULAS_ETAPA_2025`: matrículas da etapa no Censo 2025;
- `IDEB_2025`: índice observado divulgado pelo Inep;
- `NOTA_MATEMATICA_SAEB_2025` e `NOTA_PORTUGUES_SAEB_2025`: notas do Saeb;
- `INDICADOR_RENDIMENTO_2025`: indicador de rendimento (aprovação);
- `ETAPA_ENSINO`: anos iniciais, anos finais ou Ensino Médio;
- `REDE_CENSO` e `REDE_IDEB`: rede informada em cada fonte;
- `SITUACAO_IDEB_2025`: "Divulgado", "Não divulgado pelo Inep" ou
  "Escola/etapa não localizada no arquivo do Inep".

## Limitações da pesquisa

- **Bairro indisponível em 2025:** o Jardim Macedônia é identificado por uma
  lista fixa de códigos INEP de referência cadastral (ver "Metodologia").
  Novas escolas no bairro não são detectadas.
- **Escolas sem linha de matrícula:** 122 escolas públicas ativas de São Paulo
  não aparecem na Tabela de Matrícula 2025 e, por isso, não entram nas análises
  de matrículas.
- **Etapas consideradas:** apenas Ensino Fundamental e Médio regulares.
  Educação Infantil, EJA e outras modalidades não entram no total.
- **IDEB ausente:** resultados não divulgados reduzem a cobertura das
  comparações.
- **Data em `fontes_ideb_2025.csv` e `fonte_censo_2025.csv`:** registra a data
  da última execução, mesmo quando o ZIP é reutilizado. A garantia de que o
  arquivo é o mesmo é dada pelo SHA-256.
- **Sem testes automatizados:** a verificação é feita pelas validações
  executadas durante o pipeline.

## Estado atual do desenvolvimento

Concluído:

- download, validação e recorte automatizados do Censo Escolar 2025;
- pipeline de análise do Censo Escolar 2025 (`main.py`) e seus gráficos;
- integração com o IDEB 2025 e validações do merge (`integrar_ideb.py`);
- exploração da base integrada (`explorar_ideb.py`).

Ainda não implementado:

- identificação do bairro por uma fonte oficial de 2025 (Catálogo de Escolas);
- testes automatizados.

O projeto não utiliza banco de dados nem dashboard nesta etapa.
