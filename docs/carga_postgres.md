# Carga dos dados de 2025 para o PostgreSQL

Módulo: [`carga_postgres.py`](../carga_postgres.py) · Testes:
[`tests/test_carga_postgres.py`](../tests/test_carga_postgres.py)

## 1. Objetivo

Carregar o **Censo Escolar 2025** e o **IDEB/Saeb 2025** nas quatro tabelas do
schema `educacao` (banco `educacao_jd_macedonia`, PostgreSQL 17), respeitando
o DDL aprovado ([01_criacao_tabelas.sql](../modelagem/fisico/01_criacao_tabelas.sql)).

O módulo tem dois modos:

| Modo | Comando | Acessa o banco? |
|---|---|---|
| Simulação | `python carga_postgres.py --dry-run` | **Não.** Valida tudo em memória. |
| Carga real | `python carga_postgres.py --load` | Sim, em **uma única transação**. |

### Situação: primeira carga real concluída em 04/11/2026

A primeira execução de `python carga_postgres.py --load` foi concluída com
**COMMIT** no banco `educacao_jd_macedonia`, schema `educacao`.

| Tabela | Registros |
|---|---:|
| `educacao.etapa_ensino` | 3 |
| `educacao.escola` | 7.905 |
| `educacao.oferta_ensino` | 5.984 |
| `educacao.indicador_educacional` | 2.973 |
| **Total** | **16.865** |

Verificações realizadas:

- **Antes da carga:** dry-run com 91 verificações locais e 0 falhas.
- **Durante a carga, antes do COMMIT, pelo próprio programa:**
  - banco, schema e estrutura das tabelas conforme o DDL;
  - tabelas vazias;
  - contagens;
  - nenhuma PK duplicada e nenhuma FK órfã;
  - indicadores somente de escolas públicas ativas;
  - 377 indicadores sem IDEB divulgado e 718 escolas sem registro de
    matrícula;
  - soma das matrículas;
  - valores da EMEF César Yasigi e da EE Jornalista David Nasser.
- **Depois do COMMIT:** as contagens foram conferidas em uma sessão
  independente, no DBeaver.

Como as tabelas já contêm dados, **uma nova execução de `--load` será
recusada** (ver 8.4). O `--dry-run` continua disponível para conferência
local.

O módulo é independente das análises e dos gráficos. Ele reutiliza apenas
constantes de `ingestao.py` e `tratamento.py` (caminhos, ano, município e mapa
de etapas). Esses módulos só definem funções e constantes, sem nenhum código
executado na importação, então importá-los não dispara downloads nem
processamento.

## 2. Instalação do driver

O driver escolhido é o **psycopg 3**, o driver atual do PostgreSQL para
Python:

- a transação é controlada pelo programa, com `commit()` e `rollback()`;
- os dados vão como parâmetros (`%s`), nunca dentro do texto SQL;
- converte `Decimal` em `NUMERIC` e `None` em `NULL` sem perda;
- o pacote `psycopg[binary]` já traz a biblioteca do PostgreSQL (libpq), então
  não é preciso compilar nada no Windows.

Na pasta `Entrega_final`, com o ambiente virtual ativo:

```bash
python -m pip install -r requirements.txt
```

O driver só é importado no modo `--load`. O dry-run funciona mesmo sem ele
instalado.

## 3. Arquivos utilizados

| Fonte | Arquivo | Granularidade | Linhas |
|---|---|---|---:|
| Tabela de Escola 2025 (SP) | `data/raw/escolas_sp_2025.csv` | 1 por escola | 7.905 |
| Tabela de Matrícula 2025 (SP) | `data/raw/matriculas_sp_2025.csv` | 1 por escola com registro | 7.187 |
| Base integrada Censo × IDEB | `data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv` | 1 por escola pública ativa × etapa | 2.973 |

Todos são lidos como **texto** (`dtype=str`), e **somente a célula vazia** é
tratada como ausente. Assim, nenhum código INEP perde zeros e nenhum texto
como "NA" vira nulo por engano.

## 4. Ordem das tabelas

As tabelas "pai" vêm antes das "filhas", por causa das chaves estrangeiras:

1. `educacao.etapa_ensino` — 3 registros
2. `educacao.escola` — 7.905 registros
3. `educacao.oferta_ensino` — 5.984 registros (FK para escola e etapa)
4. `educacao.indicador_educacional` — 2.973 registros (FK para oferta)

## 5. Origem e destino de cada campo

### etapa_ensino (domínio fixo)

| Destino | Origem |
|---|---|
| co_etapa_ensino | código definido na modelagem: AI, AF, EM |
| no_etapa_ensino | chaves de `tratamento.ETAPAS_E_MATRICULAS` (texto idêntico ao da base integrada) |
| coluna_matricula_censo | valores de `tratamento.ETAPAS_E_MATRICULAS` (QT_MAT_FUND_AI, QT_MAT_FUND_AF, QT_MAT_MED) |

### escola

| Destino | Origem (escolas_sp_2025.csv) | Conversão |
|---|---|---|
| co_entidade | CO_ENTIDADE | texto, sem alteração |
| no_entidade | NO_ENTIDADE | texto |
| co_municipio | CO_MUNICIPIO | texto |
| no_distrito | NO_DISTRITO | texto |
| tp_dependencia | TP_DEPENDENCIA | inteiro |
| tp_situacao_funcionamento | TP_SITUACAO_FUNCIONAMENTO | inteiro |
| ano_censo | NU_ANO_CENSO | inteiro |
| possui_registro_matricula | **derivado** | TRUE se o CO_ENTIDADE aparece em matriculas_sp_2025.csv |

### oferta_ensino (*unpivot* da Tabela de Matrícula)

| Destino | Origem (matriculas_sp_2025.csv) |
|---|---|
| co_entidade | CO_ENTIDADE |
| co_etapa_ensino | AI, AF ou EM, conforme a coluna de matrícula |
| ano_referencia | NU_ANO_CENSO |
| qt_matriculas | QT_MAT_FUND_AI, QT_MAT_FUND_AF ou QT_MAT_MED, **somente quando > 0** |

### indicador_educacional

| Destino | Origem (base integrada) | Conversão |
|---|---|---|
| co_entidade | CO_ENTIDADE | texto |
| co_etapa_ensino | ETAPA_ENSINO | descrição → AI, AF ou EM |
| ano_referencia | ANO_CENSO | inteiro (2025) |
| situacao_ideb | SITUACAO_IDEB_2025 | texto |
| vl_indicador_rendimento | INDICADOR_RENDIMENTO_2025 | Decimal ou NULL |
| vl_nota_matematica | NOTA_MATEMATICA_SAEB_2025 | Decimal ou NULL |
| vl_nota_portugues | NOTA_PORTUGUES_SAEB_2025 | Decimal ou NULL |
| vl_nota_media_padronizada | NOTA_MEDIA_PADRONIZADA_2025 | Decimal ou NULL |
| vl_ideb | IDEB_2025 | Decimal ou NULL |

Colunas da base integrada **não carregadas**, como previsto na modelagem:

- REDE_CENSO, REDE_IDEB, NO_ESCOLA_IDEB, SG_UF, CO_MUNICIPIO, NO_MUNICIPIO,
  QT_MAT_*, ARQUIVO_FONTE;
- ANO_IDEB, que é substituído por `ano_referencia` + `situacao_ideb`.

## 6. Tratamento dos valores nulos

| Situação | Tratamento |
|---|---|
| Escola sem registro na Tabela de Matrícula | permanece em `escola` com `possui_registro_matricula = FALSE`; matrícula **desconhecida**, não zero |
| Etapa com zero matrículas | **não** gera linha em `oferta_ensino` (a escola não oferece a etapa) |
| IDEB não divulgado pelo Inep | linha em `indicador_educacional` com `vl_ideb` = NULL |
| Escola/etapa não localizada no arquivo do Inep | linha com todos os valores NULL |
| Célula vazia em qualquer indicador | `None` em Python, gravado como `NULL`; **nunca 0** |

## 7. Dry-run (simulação)

```bash
python carga_postgres.py --dry-run
```

Lê as fontes, monta as quatro tabelas e executa **91 verificações locais**:

| Grupo | O que confere |
|---|---|
| Fontes | colunas obrigatórias, ano 2025, município 3550308, INEP sem duplicidade, matrícula sem escola órfã |
| Estrutura e NOT NULL | colunas na ordem do DDL; nenhuma coluna NOT NULL com nulo; textos cabem no VARCHAR |
| Chaves primárias | as 4 PKs e os 2 UNIQUE sem repetição |
| Chaves estrangeiras | as 3 FKs sem registros órfãos |
| CHECK | cada `CHECK` do DDL reproduzido em Python, com o mesmo nome da restrição |
| Precisão NUMERIC | cada valor cabe em `NUMERIC(p,s)` **sem arredondamento** |
| Regras de negócio e origem | INEP idêntico à origem; zeros excluídos; escolas sem registro preservadas; indicador só para escolas públicas ativas; nulos preservados |
| Contagens | 3 / 7.905 / 5.984 / 2.973, 377 sem IDEB e 718 sem registro de matrícula, apenas **conferidas**, nunca ajustadas |
| Plano de carga | todos os valores com tipos aceitos pelo driver (`str`, `int`, `bool`, `Decimal`, `None`) |

O dry-run **não importa o driver e não abre conexão**. Isso é comprovado por
um teste que executa o dry-run com a rede bloqueada.

| Código de saída | Significado |
|---|---|
| 0 | tudo certo |
| 1 | alguma validação ou a carga falhou (com ROLLBACK) |
| 2 | nenhum modo escolhido |

## 8. Carga real (`--load`)

### 8.1 Como a transação funciona

Uma **transação** é um bloco de comandos que o banco trata como uma coisa só:
ou todos são confirmados (`COMMIT`), ou nenhum (`ROLLBACK`). Enquanto ela não
é confirmada, outras sessões não veem os dados novos.

A função `executar_carga` segue estes passos, todos **na mesma transação**:

1. **Antes de escrever:**
   - confere que o banco é `educacao_jd_macedonia` e que o schema `educacao`
     existe;
   - compara colunas, tipos, nulidade e a quantidade de PK, FK, UNIQUE e
     CHECK de cada tabela com o DDL aprovado;
   - bloqueia as quatro tabelas contra escritas de outras sessões
     (`LOCK TABLE ... IN SHARE ROW EXCLUSIVE MODE`; a leitura continua
     liberada);
   - confere que as quatro tabelas estão **vazias**.
2. **Inserção:** `INSERT` parametrizado (`executemany`) nas quatro tabelas, na
   ordem das FKs.
3. **Validação no banco, antes do COMMIT:**
   - contagens: 3 / 7.905 / 5.984 / 2.973;
   - nenhuma PK duplicada e nenhuma FK órfã;
   - indicadores só para escolas públicas em atividade;
   - nenhuma oferta de escola sem registro de matrícula;
   - quantidade por situação do IDEB e 377 indicadores sem IDEB;
   - 718 escolas sem registro de matrícula;
   - soma das matrículas igual à das tabelas em memória;
   - matrículas, notas e IDEB da **EMEF César Yasigi (35010281)** e da **EE
     Jornalista David Nasser (35044386)** iguais aos das fontes de 2025.
4. **COMMIT** somente se tudo estiver correto.

### 8.2 O que causa ROLLBACK

Qualquer um destes eventos desfaz a transação inteira, e **nada** fica
gravado:

- banco errado, schema ausente, tabela ausente ou com estrutura diferente do
  DDL;
- alguma tabela já com registros (ver 8.4);
- erro do PostgreSQL em qualquer `INSERT`, por exemplo um `CHECK` ou uma FK
  violada;
- qualquer divergência na validação do passo 3;
- interrupção pelo usuário (Ctrl+C) ou erro inesperado do programa.

Se a conexão cair no meio do processo, o próprio PostgreSQL descarta a
transação não confirmada.

### 8.3 Autenticação (sem credenciais no projeto)

O programa usa os mecanismos padrão do PostgreSQL (libpq) e **nunca** grava,
registra ou exibe a senha:

- **banco:** fixo no código (`educacao_jd_macedonia`);
- **servidor, porta e usuário:** variáveis `PGHOST`, `PGPORT` e `PGUSER`,
  definidas só na sessão do terminal (ou os padrões da libpq);
- **senha:** uma destas opções:
  - `--pedir-senha`: digitada na hora, sem aparecer na tela (`getpass`);
    **recomendada**;
  - o arquivo de senhas do PostgreSQL (`pgpass.conf`), fora do projeto, se
    você preferir configurá-lo.

Se a conexão falhar, a mensagem é genérica, sem mostrar servidor, usuário ou
senha.

### 8.4 Por que uma segunda execução é bloqueada

A política é **conservadora**: se qualquer uma das quatro tabelas já tiver
registros, a carga é recusada antes de qualquer `INSERT`. O programa **não**
apaga, substitui nem atualiza dados.

- Isso impede duplicar ou misturar cargas: rodar `--load` duas vezes não
  altera nada na segunda vez.
- Combinado com a transação única, garante que o banco fique em um de dois
  estados: **vazio** ou **com a carga completa e validada**. Nunca fica pela
  metade.
- Uma recarga futura exigiria esvaziar as tabelas manualmente, com decisão e
  autorização explícitas, fora deste programa.

### 8.5 Como executar a primeira carga

No PowerShell, na pasta `Entrega_final`:

```powershell
python -m pip install -r requirements.txt   # instala o psycopg 3
python carga_postgres.py --dry-run          # deve terminar com "0 falhas"
$env:PGHOST = "localhost"                   # vale só para esta janela
$env:PGPORT = "5432"
$env:PGUSER = "postgres"                    # ajuste para o seu usuário
python carga_postgres.py --load --pedir-senha
```

A execução termina com `COMMIT realizado` (código 0) ou com
`ROLLBACK realizado` e o motivo (código 1).

## 9. Testes automatizados (sem banco real)

```bash
python -m unittest discover -s tests -v
```

O banco é simulado por uma conexão falsa (`ConexaoFalsa`). Ela responde às
consultas de conferência, guarda os `INSERT` em memória e registra
`COMMIT`/`ROLLBACK`. Os 22 testes cobrem:

- **dry-run:**
  - contagens, ordem das FKs, tipos enviados ao driver e nulos como `None`;
  - valores das escolas de interesse;
  - execução com a rede bloqueada, sem importar o driver;
- **carga bem-sucedida:**
  - um único `COMMIT`;
  - SQL sempre parametrizado e sem comandos de exclusão ou alteração;
- **recusas com ROLLBACK e nenhum `INSERT`:**
  - tabela com dados;
  - banco errado;
  - schema, tabela ou restrição ausente;
  - estrutura diferente do DDL;
- **ROLLBACK depois de começar a inserir:**
  - falha no meio dos `INSERT`;
  - divergências na validação pós-carga;
  - Ctrl+C;
- **segurança:**
  - erro de conexão sem expor a senha;
  - senha digitada repassada só ao driver.

Os testes de transação precisam do psycopg instalado. Sem ele, são pulados
automaticamente.

## 10. Principais funções (explicação didática)

| Função | O que faz | Por que é assim |
|---|---|---|
| `ler_csv` | Lê um CSV com tudo como texto | Códigos INEP são identificadores; se viram número, podem perder zeros. |
| `converter_inteiro` | Texto → inteiro (`Int64`), com `errors="raise"` | Um valor inválido interrompe o processo, em vez de virar nulo em silêncio. |
| `converter_decimal` | Texto → `Decimal` ou `None` | `Decimal` guarda o número exato (0.971452), como o `NUMERIC`; `float` poderia arredondar. |
| `cabe_em_numeric` | Testa se um valor cabe em `NUMERIC(p,s)` | O PostgreSQL arredonda sem avisar quando há casas demais. |
| `preparar_escola` | Mapeia o cadastro e calcula `possui_registro_matricula` | Distingue "sem dado" (FALSE) de "zero matrículas". |
| `preparar_oferta_ensino` | Transforma 3 colunas de matrícula em linhas (*unpivot*) | Representa o N:N escola × etapa; só cria linha se houver matrícula > 0. |
| `RelatorioValidacao` | Registra cada verificação como OK ou FALHA | Gera a evidência do dry-run e interrompe quando algo falha. |
| `valor_para_banco` / `preparar_registros` | Convertem tipos do pandas/numpy em tipos Python simples | O driver aceita `int` e `bool`, não `numpy.int64` nem `numpy.bool_`; nulos viram `None`. |
| `CONTRATO` | Descreve colunas, tipos e restrições do DDL | É usado tanto pelo dry-run quanto pela conferência no banco, então não há duas "verdades". |
| `montar_insert` | Monta `INSERT INTO "educacao"."tabela" (...) VALUES (%s, ...)` | Nomes compostos com `psycopg.sql` (seguros); dados sempre como parâmetros. |
| `verificar_estrutura_tabelas` | Lê o catálogo (`information_schema`, `pg_constraint`) | Garante que as tabelas no banco são as do DDL aprovado. |
| `verificar_tabelas_vazias` | Recusa a carga se houver dados | É a política conservadora contra uma segunda execução. |
| `medir_banco_apos_carga` / `comparar_com_esperado` | Medem o banco e comparam com o calculado em memória | O `COMMIT` só acontece se o banco confirmar exatamente o esperado. |
| `executar_carga` | Orquestra tudo com `try/except`: `commit()` no fim ou `rollback()` em qualquer erro | Implementa o "tudo ou nada" da transação. |
| `abrir_conexao` | Conecta pela libpq, com senha opcional digitada | Nenhuma credencial no código; mensagem de erro genérica. |
