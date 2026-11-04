# Dicionário de dados — schema `educacao`

Banco `educacao_jd_macedonia` (PostgreSQL 17), schema `educacao`. Todos os
dados são de **2025**, das fontes oficiais do Inep:

- Censo Escolar 2025, microdados v2 (documento atualizado em julho/2026);
- IDEB/Saeb 2025 por escola.

Os nomes e tamanhos de origem foram conferidos no dicionário oficial do Censo
2025 (`dicionário_dados_educação_básica.xlsx`) e nos CSVs do projeto.

Convenções de nomes:

- `co_` = código (identificador);
- `no_` = nome ou descrição;
- `tp_` = tipo codificado;
- `qt_` = quantidade;
- `vl_` = valor de indicador;
- `ano_` = ano.

Arquivos de origem (pasta `Entrega_final/`):

| Sigla | Arquivo | Granularidade | Linhas |
|---|---|---|---:|
| **ESC** | `data/raw/escolas_sp_2025.csv` (Tabela de Escola, recorte de São Paulo) | 1 por escola | 7.905 |
| **MAT** | `data/raw/matriculas_sp_2025.csv` (Tabela de Matrícula, recorte de São Paulo) | 1 por escola com registro de matrícula | 7.187 |
| **INT** | `data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv` (base integrada) | 1 por escola pública ativa × etapa com matrícula | 2.973 |

---

## 1. `educacao.escola`

Cadastro das escolas do município de São Paulo no Censo 2025.
**Granularidade:** uma linha por código INEP. **Linhas esperadas:** 7.905.

| Coluna | Tipo | Nulo | Chave | Descrição | Origem | Regra / domínio |
|---|---|---|---|---|---|---|
| co_entidade | VARCHAR(8) | não | PK | Código INEP da escola | ESC.CO_ENTIDADE | 8 dígitos (`^[0-9]{8}$`); texto, não medida |
| no_entidade | VARCHAR(100) | não | | Nome da escola | ESC.NO_ENTIDADE | não vazio; tamanho oficial 100 (máximo observado: 73) |
| co_municipio | VARCHAR(7) | não | | Código IBGE do município | ESC.CO_MUNICIPIO | = '3550308' (São Paulo) |
| no_distrito | VARCHAR(100) | não | | Distrito, a divisão intramunicipal | ESC.NO_DISTRITO | não vazio; **não é bairro** |
| tp_dependencia | SMALLINT | não | | Dependência administrativa | ESC.TP_DEPENDENCIA | 1 Federal; 2 Estadual; 3 Municipal; 4 Privada |
| tp_situacao_funcionamento | SMALLINT | não | | Situação de funcionamento | ESC.TP_SITUACAO_FUNCIONAMENTO | 1 Em atividade; 2 Paralisada; 3 Extinta (ano do Censo); 4 Extinta em anos anteriores |
| ano_censo | SMALLINT | não | | Ano do Censo do cadastro | ESC.NU_ANO_CENSO | = 2025 |
| possui_registro_matricula | BOOLEAN | não | | Indica se a escola tem linha na Tabela de Matrícula | **derivado** | TRUE se ESC.CO_ENTIDADE existe em MAT.CO_ENTIDADE; FALSE indica matrícula desconhecida (718 escolas) |

Valores observados em 2025:

- `tp_dependencia`: 1 = 5; 2 = 1.231; 3 = 1.712; 4 = 4.957;
- `tp_situacao_funcionamento`: 1 = 7.310; 2 = 510; 3 = 85.

## 2. `educacao.etapa_ensino`

Domínio das etapas avaliadas pelo IDEB. **Granularidade:** uma linha por
etapa. **Linhas esperadas:** 3.

| Coluna | Tipo | Nulo | Chave | Descrição | Origem | Regra / domínio |
|---|---|---|---|---|---|---|
| co_etapa_ensino | VARCHAR(2) | não | PK | Código curto da etapa | **definido pelo projeto** | 'AI', 'AF', 'EM' |
| no_etapa_ensino | VARCHAR(60) | não | UK | Descrição da etapa | INT.ETAPA_ENSINO | texto idêntico ao da base integrada |
| coluna_matricula_censo | VARCHAR(30) | não | UK | Coluna da Tabela de Matrícula usada para a etapa | `tratamento.ETAPAS_E_MATRICULAS` | 'QT_MAT_FUND_AI', 'QT_MAT_FUND_AF', 'QT_MAT_MED' |

| co_etapa_ensino | no_etapa_ensino | coluna_matricula_censo | Arquivo do IDEB 2025 (referência, não armazenado) |
|---|---|---|---|
| AI | Anos iniciais do Ensino Fundamental | QT_MAT_FUND_AI | divulgacao_anos_iniciais_escolas_2025.zip |
| AF | Anos finais do Ensino Fundamental | QT_MAT_FUND_AF | divulgacao_anos_finais_escolas_2025.zip |
| EM | Ensino Médio | QT_MAT_MED | divulgacao_ensino_medio_escolas_2025.zip |

## 3. `educacao.oferta_ensino`

Tabela associativa (N:N) entre escola e etapa: matrículas por etapa no Censo
2025.

- **Granularidade:** uma linha por escola × etapa × ano, **somente quando há
  matrícula maior que zero**.
- **Linhas esperadas:** 5.984 (AI 2.480; AF 2.170; EM 1.334), em 3.129
  escolas.

| Coluna | Tipo | Nulo | Chave | Descrição | Origem | Regra / domínio |
|---|---|---|---|---|---|---|
| co_entidade | VARCHAR(8) | não | PK, FK → escola | Código INEP da escola | MAT.CO_ENTIDADE | deve existir em `escola` |
| co_etapa_ensino | VARCHAR(2) | não | PK, FK → etapa_ensino | Etapa | **derivado** da coluna de matrícula | AI, AF, EM |
| ano_referencia | SMALLINT | não | PK | Ano do Censo das matrículas | MAT.NU_ANO_CENSO | = 2025 |
| qt_matriculas | INTEGER | não | | Matrículas da etapa | MAT.QT_MAT_FUND_AI / QT_MAT_FUND_AF / QT_MAT_MED | > 0 (de 1 a 1.983 nas escolas públicas ativas) |

**Regra de construção (*unpivot*):** para cada linha de MAT e cada etapa,
cria-se uma linha se o valor da coluna `coluna_matricula_censo` for maior que
zero. Zero **não** gera linha, porque a escola não oferece a etapa.
`QT_MAT_FUND` não é carregada: é igual a `QT_MAT_FUND_AI + QT_MAT_FUND_AF` em
100% das linhas de MAT.

## 4. `educacao.indicador_educacional`

Resultado do IDEB 2025 e de seus componentes por oferta.

- **Granularidade:** no máximo uma linha por oferta (escola × etapa × ano).
- **Escopo:** somente ofertas de escolas públicas (dependência 1, 2 ou 3) em
  atividade (situação 1).
- **Linhas esperadas:** 2.973 (Divulgado 2.596; Não divulgado pelo Inep 311;
  Escola/etapa não localizada no arquivo do Inep 66).

| Coluna | Tipo | Nulo | Chave | Descrição | Origem | Regra / domínio |
|---|---|---|---|---|---|---|
| co_entidade | VARCHAR(8) | não | PK, FK → oferta_ensino | Código INEP | INT.CO_ENTIDADE | a oferta deve existir |
| co_etapa_ensino | VARCHAR(2) | não | PK, FK → oferta_ensino | Etapa | INT.ETAPA_ENSINO convertida pelo `no_etapa_ensino` | AI, AF, EM |
| ano_referencia | SMALLINT | não | PK, FK → oferta_ensino | Ano comum ao Censo e à edição do IDEB | INT.ANO_CENSO | = 2025 (ver nota 1) |
| situacao_ideb | VARCHAR(60) | não | | Disponibilidade do IDEB | INT.SITUACAO_IDEB_2025 (**derivado** no pipeline) | 'Divulgado'; 'Não divulgado pelo Inep'; 'Escola/etapa não localizada no arquivo do Inep' |
| vl_indicador_rendimento | NUMERIC(7,6) | sim | | Indicador de rendimento (aprovação) | INT.INDICADOR_RENDIMENTO_2025 ← VL_INDICADOR_REND_2025 | 0 a 1; observado 0,605588 a 1 |
| vl_nota_matematica | NUMERIC(5,2) | sim | | Nota média de Matemática (Saeb) | INT.NOTA_MATEMATICA_SAEB_2025 ← VL_NOTA_MATEMATICA_2025 | 0 a 500; observado 178,55 a 387,42 |
| vl_nota_portugues | NUMERIC(5,2) | sim | | Nota média de Língua Portuguesa (Saeb) | INT.NOTA_PORTUGUES_SAEB_2025 ← VL_NOTA_PORTUGUES_2025 | 0 a 500; observado 168,72 a 350,60 |
| vl_nota_media_padronizada | NUMERIC(8,6) | sim | | Nota média padronizada (N) | INT.NOTA_MEDIA_PADRONIZADA_2025 ← VL_NOTA_MEDIA_2025 | 0 a 10; observado 3,6455 a 8,530606 |
| vl_ideb | NUMERIC(3,1) | sim | | IDEB 2025 observado | INT.IDEB_2025 ← VL_OBSERVADO_2025 | 0 a 10; observado 2,9 a 8,5 |

**Regras de consistência (CHECK):**

1. `vl_ideb` preenchido **se e somente se** `situacao_ideb = 'Divulgado'`.
2. Se `situacao_ideb = 'Divulgado'`, as notas e o rendimento também estão
   preenchidos (observado em 2.596 de 2.596 casos).
3. Se a situação for "Escola/etapa não localizada no arquivo do Inep", todos
   os valores são NULL.
4. "Não divulgado pelo Inep" pode ter rendimento preenchido e IDEB nulo (283
   de 311 casos).
5. Marcadores do Inep (`-`, `ND`, `ND***`) já chegam como NULL; **nunca** como
   zero.

**Escala numérica:** as casas decimais foram dimensionadas pelo máximo
observado: 6 no rendimento e na nota padronizada, 2 nas notas do Saeb e 1 no
IDEB.

**Nota 1:** na base integrada, `ANO_IDEB` fica vazio nas 66 linhas não
localizadas no arquivo do Inep. No banco, `ano_referencia = 2025` nessas
linhas, porque o ano indica **qual edição foi consultada**; a ausência de
resultado é informada por `situacao_ideb`.

---

## 5. Colunas de origem não armazenadas

| Coluna (origem) | Motivo |
|---|---|
| QT_MAT_FUND (MAT, INT) | Derivada: AI + AF. |
| REDE_CENSO (INT) | Derivada de `tp_dependencia`. |
| REDE_IDEB, NO_ESCOLA_IDEB (INT) | Repetem a escola; validados sem divergência com o Censo. |
| SG_UF, CO_MUNICIPIO, NO_MUNICIPIO (INT, vindas do IDEB) | Repetem a escola (São Paulo). |
| ARQUIVO_FONTE (INT) | Determinado pela etapa (tabela da seção 2); proveniência registrada em `data/raw/ideb/fontes_ideb_2025.csv`. |
| ANO_IDEB (INT) | Representado por `ano_referencia` (nota 1). |
| CO_DISTRITO (ESC) | Evita a dependência transitiva `co_distrito → no_distrito` sem nova tabela. |
| Demais colunas de ESC (290) e MAT (263) | Fora do escopo da pesquisa. |

## 6. Jardim Macedônia

Não há coluna nem tabela de bairro: os microdados de 2025 não trazem bairro
nem endereço. As escolas de interesse são selecionadas **por consulta**, a
partir da lista de códigos de referência cadastral documentada em
`tratamento.py` (`CODIGOS_JARDIM_MACEDONIA`), obtida no cadastro do Censo
2024, a última edição com `NO_BAIRRO`.

- Principais: EMEF César Yasigi (`35010281`) e EE Jornalista David Nasser
  (`35044386`).
- A lista **não** representa necessariamente todos os estabelecimentos do
  bairro.
- O distrito dessas escolas ("Capão Redondo") **não** equivale ao bairro.

```sql
-- Exemplo de seleção (não executar antes da carga aprovada)
SELECT e.co_entidade, e.no_entidade, o.co_etapa_ensino, o.qt_matriculas,
       i.situacao_ideb, i.vl_ideb
FROM educacao.escola e
JOIN educacao.oferta_ensino o ON o.co_entidade = e.co_entidade
LEFT JOIN educacao.indicador_educacional i
       ON  i.co_entidade = o.co_entidade
       AND i.co_etapa_ensino = o.co_etapa_ensino
       AND i.ano_referencia = o.ano_referencia
WHERE e.co_entidade IN ('35010281', '35044386')
ORDER BY e.co_entidade, o.co_etapa_ensino;
```

## 7. Regras para a futura carga

1. **Ordem:**
   - `etapa_ensino` (3 linhas fixas);
   - `escola` (ESC + a flag derivada de MAT);
   - `oferta_ensino` (*unpivot* de MAT com valor > 0);
   - `indicador_educacional` (INT).
2. **Leitura:** CSVs com `;` e `dtype=str`, para preservar os códigos com 8
   dígitos. Converter os números somente na carga, sem trocar ausente por
   zero.
3. **Transação única:** carregar as quatro tabelas em uma transação e
   confirmar (`COMMIT`) apenas se todas as contagens baterem.
4. **Conferências pós-carga** (valores esperados):
   - `escola` 7.905;
   - `etapa_ensino` 3;
   - `oferta_ensino` 5.984;
   - `indicador_educacional` 2.973 (2.596 / 311 / 66);
   - escolas públicas ativas com oferta: 1.709;
   - média de matrículas por escola: 751,33.
5. **Regras não garantidas por CHECK**, porque envolvem mais de uma tabela;
   validar por consulta na carga:
   - indicador apenas para ofertas de escolas públicas em atividade;
   - oferta apenas para escolas com `possui_registro_matricula = TRUE`.
