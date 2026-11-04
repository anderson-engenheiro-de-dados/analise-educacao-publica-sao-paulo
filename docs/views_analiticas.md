# Camada analítica SQL — views de 2025

Banco `educacao_jd_macedonia` (PostgreSQL 17), schema `educacao`. Dados
exclusivamente do **Censo Escolar 2025** e do **IDEB/Saeb 2025** (Inep).

As views não armazenam dados: são consultas salvas sobre as quatro tabelas
carregadas por `carga_postgres.py`. Elas concentram as regras de negócio em um
só lugar, para que as análises em Python e os gráficos usem sempre os mesmos
filtros e cálculos.

## 1. Arquivos

| Arquivo | Conteúdo |
|---|---|
| [sql/views/01_vw_escolas_matriculas_2025.sql](../sql/views/01_vw_escolas_matriculas_2025.sql) | `educacao.vw_escolas_matriculas_2025` |
| [sql/views/02_vw_ideb_rede_etapa_2025.sql](../sql/views/02_vw_ideb_rede_etapa_2025.sql) | `educacao.vw_ideb_rede_etapa_2025` |
| [sql/views/03_vw_ideb_jardim_macedonia_2025.sql](../sql/views/03_vw_ideb_jardim_macedonia_2025.sql) | `educacao.vw_ideb_jardim_macedonia_2025` (depende da 02) |
| [sql/validacoes/01_validar_views_2025.sql](../sql/validacoes/01_validar_views_2025.sql) | 28 verificações e 2 consultas de conferência, todas de leitura |
| [sql/views/04_vw_ideb_escolas_2025.sql](../sql/views/04_vw_ideb_escolas_2025.sql) | `educacao.vw_ideb_escolas_2025` (IDEB individual; base da EDA) |
| [sql/validacoes/02_validar_vw_ideb_escolas_2025.sql](../sql/validacoes/02_validar_vw_ideb_escolas_2025.sql) | 16 verificações da view 04 e 1 consulta de conferência |

Cada script de view:

- tem uma trava que interrompe a execução fora do banco `educacao_jd_macedonia`;
- roda em uma transação (`BEGIN`/`COMMIT`);
- usa `CREATE OR REPLACE VIEW`, então pode ser executado de novo sem apagar
  nada (uma view não guarda dados);
- documenta a view e as colunas principais com `COMMENT`.

**Ordem obrigatória:** 01 → 02 → 03, porque a view 03 lê a view 02. A view 04
usa somente as tabelas e pode ser criada a qualquer momento. A validação 02,
porém, compara a view 04 com as views 01 a 03, então precisa de todas elas.

## 2. Relacionamentos usados

```text
etapa_ensino 1 ──< oferta_ensino >── 1 escola
                        │
                        1
                        │
                      0..1
               indicador_educacional
```

| JOIN | Cardinalidade | Por que não multiplica linhas |
|---|---|---|
| `oferta_ensino` → `escola` | N:1 | `co_entidade` é a PK de `escola`: cada oferta encontra exatamente uma escola |
| `oferta_ensino` → `etapa_ensino` | N:1 | `co_etapa_ensino` é a PK de `etapa_ensino` |
| `indicador_educacional` → `oferta_ensino` | 1:1 | a PK do indicador é igual à PK da oferta (e é a FK) |
| `indicador_educacional` → `escola` / `etapa_ensino` | N:1 | mesmas PKs acima |
| view 03 → view 02 (`LEFT JOIN`) | N:1 | a view 02 tem uma linha por ano × rede × etapa, a mesma chave usada no JOIN |

Todo JOIN chega a uma chave primária ou a uma linha única. Por isso nenhuma
junção multiplica registros, o que a verificação 4 confirma (2.973 = 2.973).

## 3. As três views

### 3.1 `educacao.vw_escolas_matriculas_2025`

**Objetivo:** matrículas das escolas **públicas** (federal, estadual e
municipal) **em atividade**, por escola, rede e etapa, em 2025.

**Granularidade:** 1 linha por escola × etapa × ano
(`co_entidade`, `co_etapa_ensino`, `ano_referencia`).

| Coluna | Origem |
|---|---|
| co_entidade, no_entidade, no_distrito, tp_dependencia | `escola` |
| rede_administrativa | derivada de `tp_dependencia` (1 Federal, 2 Estadual, 3 Municipal) |
| co_etapa_ensino, no_etapa_ensino | `etapa_ensino` |
| qt_matriculas, ano_referencia | `oferta_ensino` |

**Filtros:** `tp_dependencia IN (1, 2, 3)`, `tp_situacao_funcionamento = 1` e
`ano_referencia = 2025`.

**Média por escola × média por oferta.** Uma escola pode ter até 3 linhas, uma
por etapa. Por isso:

```sql
-- CORRETO: média de matrículas POR ESCOLA (resultado: 751,33)
SELECT round(avg(total), 2)
FROM (SELECT co_entidade, sum(qt_matriculas) AS total
      FROM educacao.vw_escolas_matriculas_2025
      GROUP BY co_entidade) AS por_escola;

-- ATENÇÃO: isto é a média POR OFERTA (escola x etapa), não por escola (431,89)
SELECT round(avg(qt_matriculas), 2) FROM educacao.vw_escolas_matriculas_2025;
```

### 3.2 `educacao.vw_ideb_rede_etapa_2025`

**Objetivo:** indicadores agregados do IDEB 2025 por rede e etapa, para as
escolas públicas ativas de São Paulo.

**Granularidade:** 1 linha por ano × rede × etapa
(`ano_referencia`, `tp_dependencia`, `co_etapa_ensino`).

| Coluna | Cálculo |
|---|---|
| qt_ofertas_avaliadas | `count(*)`: ofertas incluídas na integração com o IDEB, com ou sem resultado |
| qt_ideb_divulgado | `count(vl_ideb)`: conta apenas valores não nulos |
| qt_ideb_ausente | `count(*) FILTER (WHERE vl_ideb IS NULL)` |
| qt_nao_divulgado_inep / qt_nao_localizado_inep | contagem por `situacao_ideb` (somam `qt_ideb_ausente`) |
| media_ideb | `round(avg(vl_ideb), 2)` |
| mediana_ideb | `percentile_cont(0.5)`, arredondada em 2 casas |
| menor_ideb / maior_ideb | `min` / `max` |

**Tratamento do NULL:** em SQL, `avg`, `percentile_cont`, `min`, `max` e
`count(coluna)` **ignoram NULL**. O IDEB ausente não entra no cálculo e nunca
é tratado como zero. Se fosse tratado como zero, as médias cairiam
artificialmente.

> **Interpretação:** os indicadores refletem os **resultados disponíveis**,
> não necessariamente todas as escolas da rede. Por exemplo, na rede municipal
> (anos finais), 125 das 552 ofertas não têm IDEB 2025.

### 3.3 `educacao.vw_ideb_jardim_macedonia_2025`

**Objetivo:** comparar o IDEB 2025 das escolas de interesse com a média da
**mesma rede** e da **mesma etapa** em São Paulo.

**Escolas:** EMEF César Yasigi (`35010281`, municipal) e EE Jornalista David
Nasser (`35044386`, estadual).

**Granularidade:** 1 linha por escola × etapa × ano.

| Coluna | Cálculo |
|---|---|
| ideb_escola | `indicador_educacional.vl_ideb` |
| media_ideb_rede_etapa | `media_ideb` da view 02, para a mesma rede e etapa |
| diferenca_ideb_rede_etapa | `round(ideb_escola - media_ideb_rede_etapa, 2)`; **NULL** quando a escola não tem IDEB (NULL − número = NULL) |
| qt_ideb_na_media_rede_etapa | quantos IDEBs formam a média de comparação |
| qt_matriculas, situacao_ideb, ano_referencia | `oferta_ensino` e `indicador_educacional` |

A média de comparação **inclui a própria escola**, porque é a média de todas
as escolas da rede e etapa com IDEB divulgado.

### 3.4 `educacao.vw_ideb_escolas_2025`

**Objetivo:** IDEB 2025 **individual** por escola e etapa, junto com as
matrículas. É a base granular da análise exploratória (`eda.py`): permite
calcular em Python distribuições, quartis, outliers e a posição percentil das
escolas, o que as views agregadas não permitem.

**Granularidade:** 1 linha por escola × etapa × ano.

| Coluna | Origem |
|---|---|
| co_entidade, no_entidade, tp_dependencia | `escola` |
| rede_administrativa | derivada de `tp_dependencia` |
| co_etapa_ensino, no_etapa_ensino | `etapa_ensino` |
| qt_matriculas, ano_referencia | `oferta_ensino` |
| vl_ideb, situacao_ideb | `indicador_educacional` (`vl_ideb` NULL quando não divulgado) |

**Relacionamentos:**

- a base é `oferta_ensino`, com JOIN N:1 para `escola` e para `etapa_ensino`;
- o `LEFT JOIN` 1:0..1 com `indicador_educacional` preserva a oferta mesmo sem
  indicador. Em 2025, toda oferta pública ativa tem indicador (verificação 7).

**Filtros:** os mesmos da view 01 (escolas públicas, em atividade, ano 2025).

**Resultado esperado:**

- 2.973 linhas, de 1.709 escolas;
- 2.596 com IDEB divulgado e 377 com IDEB `NULL`;
- 1.284.021 matrículas.

**Validação** (`sql/validacoes/02_validar_vw_ideb_escolas_2025.sql`, 16
verificações):

- contagens, granularidade única e ausência de IDEB igual a zero;
- coerência entre o IDEB e a situação de divulgação;
- mesmas chaves e matrículas da view 01;
- mesmos agregados da view 02;
- mesmos valores da view 03.

**Validação real no PostgreSQL (04/11/2026):**

- a view 04 foi criada no banco `educacao_jd_macedonia`;
- a validação 02 foi executada no DBeaver: **16 de 16 verificações
  aprovadas**;
- antes disso, a mesma validação já havia passado no DuckDB local.

## 4. Resultados esperados

Valores calculados localmente com os mesmos dados que foram carregados:

**View 01:**
- 2.973 linhas, de 1.709 escolas;
- 1.284.021 matrículas;
- média por escola de 751,33 e mediana de 723.

| Rede | Linhas | Escolas | Matrículas |
|---|---:|---:|---:|
| Federal | 6 | 5 | 2.506 |
| Estadual | 1.796 | 1.093 | 829.862 |
| Municipal | 1.171 | 611 | 451.653 |

**View 02** (9 linhas, num total de 2.973 ofertas: 2.596 com IDEB divulgado e
377 sem):

| Rede | Etapa | Ofertas | Divulgado | Ausente | Média | Mediana | Menor | Maior |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Federal | AF | 1 | 1 | 0 | 7,60 | 7,60 | 7,6 | 7,6 |
| Federal | AI | 1 | 1 | 0 | 8,20 | 8,20 | 8,2 | 8,2 |
| Federal | EM | 4 | 1 | 3 | 5,60 | 5,60 | 5,6 | 5,6 |
| Estadual | AF | 625 | 574 | 51 | 5,11 | 5,00 | 3,7 | 6,7 |
| Estadual | AI | 539 | 514 | 25 | 6,53 | 6,50 | 4,7 | 8,5 |
| Estadual | EM | 632 | 532 | 100 | 4,44 | 4,30 | 2,9 | 7,3 |
| Municipal | AF | 552 | 427 | 125 | 4,93 | 4,90 | 3,5 | 6,3 |
| Municipal | AI | 610 | 543 | 67 | 5,87 | 5,90 | 4,5 | 7,3 |
| Municipal | EM | 9 | 3 | 6 | 4,03 | 3,90 | 3,6 | 4,6 |

**View 03** (4 linhas):

| Escola | Rede | Etapa | Matrículas | IDEB | Média rede/etapa | Diferença | Situação |
|---|---|---|---:|---:|---:|---:|---|
| EMEF César Yasigi | Municipal | AI | 464 | 6,4 | 5,87 | +0,53 | Divulgado |
| EE Jornalista David Nasser | Estadual | AI | 233 | 5,7 | 6,53 | −0,83 | Divulgado |
| EE Jornalista David Nasser | Estadual | AF | 336 | 3,9 | 5,11 | −1,21 | Divulgado |
| EE Jornalista David Nasser | Estadual | EM | 393 | NULL | 4,44 | NULL | Não divulgado pelo Inep |

## 5. Validações

### 5.1 Validação real no PostgreSQL (04/11/2026)

As três views foram criadas no banco `educacao_jd_macedonia`, schema
`educacao` (PostgreSQL 17). Em seguida, o arquivo
`sql/validacoes/01_validar_views_2025.sql` foi executado no DBeaver.

**Resultado: 28 de 28 verificações aprovadas, nenhuma falha.**

- **View 01:**
  - 2.973 ofertas, de 1.709 escolas;
  - 1.284.021 matrículas;
  - média de 751,33 matrículas por escola.
- **View 02:** 9 combinações de rede e etapa, com 2.596 IDEBs divulgados e
  377 ausentes.
- **View 03:** 4 registros (EMEF César Yasigi e EE Jornalista David Nasser),
  com indicadores e diferenças iguais aos da seção 4.
- **Geral:** nenhuma duplicidade nem multiplicação de registros por JOIN, e
  todos os valores `NULL` preservados.

### 5.2 Validação prévia (antes da criação no banco)

- **Sintaxe:** os quatro arquivos foram analisados pelo parser oficial do
  PostgreSQL 17 (libpg_query), sem conexão.
  - Cada script de view cria apenas uma view, no schema `educacao`.
  - O arquivo de validação contém só `SELECT`.
  - Nenhum comando de escrita ou exclusão.
- **Lógica:**
  - as views e as 28 verificações foram executadas em um banco SQL local e
    descartável (DuckDB, em memória), com as mesmas 4 tabelas preparadas para
    a carga (16.865 registros): **28 de 28 verificações OK**;
  - os mesmos números foram recalculados de forma independente em pandas.

O DuckDB é muito parecido com o PostgreSQL, mas não é idêntico. Por isso, a
confirmação definitiva foi a execução real descrita em 5.1.

### 5.3 O que a Consulta 1 verifica

| Nº | Verificação |
|---|---|
| 1–3 | View 01: 2.973 linhas, 1.709 escolas e granularidade única |
| 4–6 | sem multiplicação por JOIN; soma de matrículas igual à tabela e ao valor preparado (1.284.021) |
| 7 | média por escola de 751,33 (agregando antes por `co_entidade`) |
| 8 | as chaves da view 01 são exatamente as 2.973 chaves de `indicador_educacional` |
| 9–10 | códigos INEP com 8 dígitos; toda linha com rede |
| 11–12 | View 02: 9 combinações rede × etapa, sem repetição |
| 13–17 | 2.973 ofertas = 2.596 divulgados + 377 ausentes; ausentes = não divulgados + não localizados |
| 18–19 | média igual ao recálculo `sum/count` só com valores válidos; média e mediana dentro de [menor, maior] |
| 20 | 377 IDEB ausentes contados diretamente na tabela |
| 21–24 | View 03: 4 linhas, 2 escolas, granularidade única; diferença NULL exatamente quando o IDEB é NULL |
| 25–28 | valores das 4 linhas das escolas do Jardim Macedônia |

## 6. Como executar e validar no DBeaver

1. Conecte-se ao banco `educacao_jd_macedonia`.
2. Abra `sql/views/01_vw_escolas_matriculas_2025.sql` e execute como
   **script** (Alt+X), não apenas a instrução selecionada (Ctrl+Enter). O
   script tem `BEGIN`, um bloco `DO` e `COMMIT`.
3. Repita para os arquivos `02` e `03`, **nessa ordem**.
4. Confira no navegador do DBeaver: `educacao` → *Views* → as três views.
5. Abra `sql/validacoes/01_validar_views_2025.sql` e execute a **Consulta 1**.
   As 28 linhas devem ter `ok = true`.
6. Execute as Consultas 2 e 3 e compare com as tabelas da seção 4.
7. **View 04:**
   - execute `sql/views/04_vw_ideb_escolas_2025.sql` como script (Alt+X);
   - execute a Consulta 1 de
     `sql/validacoes/02_validar_vw_ideb_escolas_2025.sql`: as 16 linhas devem
     ter `ok = true`;
   - depois, rode `python eda.py --fonte postgres --pedir-senha`; ele deve
     terminar com "OK" nas conferências e código de saída 0.

Alternativa pelo terminal: `psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1
-f <arquivo>`.

## 7. Limitações

- **Geográfica:** o Censo 2025 não possui campo de bairro. As escolas do
  Jardim Macedônia foram identificadas pelos códigos INEP documentados em
  `tratamento.CODIGOS_JARDIM_MACEDONIA`. A view 03 contém apenas as duas
  escolas principais da análise, que **não representam necessariamente todos
  os estabelecimentos do bairro**.
- **Cobertura do IDEB:** as médias consideram só os IDEBs divulgados (2.596 de
  2.973 ofertas). Escolas sem resultado não entram nas médias.
- **Grupos pequenos:** a rede federal tem uma única oferta com IDEB em cada
  etapa, e a rede municipal tem apenas 3 IDEBs no Ensino Médio. Médias desses
  grupos não são representativas.
- **Média de comparação:** inclui a própria escola e é arredondada em 2 casas
  antes do cálculo da diferença.
- **Matrículas:** a view 01 só tem linhas para etapas com matrícula > 0. As
  122 escolas públicas ativas sem registro de matrícula não aparecem.
- **Ano fixo:** as views filtram `ano_referencia = 2025`.

## 8. Integração com Python (psycopg + pandas)

**Implementado em `fonte_dados_eda.py`** (`python eda.py --fonte postgres`):

- lê as views 01 a 04 em uma sessão **somente leitura**
  (`conexao.read_only = True`);
- converte `Decimal` em `float` e `None` em `NaN`;
- confere os resultados com as views 02 e 03 e com o modo CSV.

**Execução real (04/11/2026):** `python eda.py --fonte postgres --pedir-senha`
foi concluído com sucesso.

- **Valores:**
  - 1.709 escolas, 1.284.021 matrículas e média de 751,33 por escola;
  - 49 outliers pelo critério de Tukey;
  - 2.596 IDEBs divulgados e 377 ausentes.
- **Conferências:**
  - as 9 combinações de rede e etapa conferem com a view 02;
  - as 4 linhas da César Yasigi e da David Nasser conferem com a view 03;
  - os quatro conjuntos analíticos (P1 por rede, outliers, P2 e P3) são
    idênticos entre PostgreSQL e CSV.

As evidências estão em `resultados/conferencia_view_*.csv`.

O exemplo abaixo mostra o mesmo padrão de forma resumida. As análises leem as
views diretamente, sem repetir as regras de negócio em Python. A conexão segue o mesmo padrão de
`carga_postgres.py`:

- nenhuma senha no código;
- servidor, porta e usuário em `PGHOST`, `PGPORT` e `PGUSER`;
- senha digitada com `getpass`.

```python
import getpass

import pandas as pd
import psycopg


def ler_view(consulta, parametros=None):
    """Executa uma consulta de leitura e devolve um DataFrame."""
    senha = getpass.getpass("Senha do PostgreSQL: ")
    with psycopg.connect(dbname="educacao_jd_macedonia", password=senha) as conexao:
        with conexao.cursor() as cursor:
            cursor.execute(consulta, parametros)
            colunas = [coluna.name for coluna in cursor.description]
            return pd.DataFrame(cursor.fetchall(), columns=colunas)


ideb_rede = ler_view(
    "SELECT * FROM educacao.vw_ideb_rede_etapa_2025 ORDER BY tp_dependencia, co_etapa_ensino"
)
macedonia = ler_view(
    "SELECT * FROM educacao.vw_ideb_jardim_macedonia_2025 WHERE co_entidade = %s",
    ("35044386",),
)
```

Observações para a próxima fase:

- As colunas `numeric` chegam como `Decimal`. Para gráficos, converta com
  `pd.to_numeric(df["media_ideb"])` ou `.astype(float)`.
- `NULL` chega como `None` e vira `NaN` após a conversão. **Não** preencha com
  zero.
- Use `%s` com parâmetros, nunca monte o SQL concatenando valores.
- `analise.py` e `main.py` não foram alterados nesta etapa.
