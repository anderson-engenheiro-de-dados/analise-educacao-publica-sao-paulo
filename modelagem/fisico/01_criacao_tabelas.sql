-- =============================================================================
-- Projeto : Análise da Educação Pública no Jardim Macedônia (São Paulo)
-- Fontes  : Inep - Censo Escolar 2025 (microdados v2) e IDEB/Saeb 2025
-- Banco   : educacao_jd_macedonia (PostgreSQL 17)
-- Schema  : educacao (já existente; nenhum objeto é criado em public)
-- Script  : 01_criacao_tabelas.sql - modelo físico (DDL)
--
-- ATENÇÃO: script para REVISÃO. Não executar antes da aprovação do modelo.
--
-- Ordem de criação (respeita as chaves estrangeiras):
--   1. educacao.escola
--   2. educacao.etapa_ensino
--   3. educacao.oferta_ensino          (associativa escola x etapa)
--   4. educacao.indicador_educacional  (0 ou 1 por oferta)
--
-- Índices: não são criados índices extras. As PKs e UNIQUEs já geram índices.
-- A FK oferta_ensino.co_entidade é coberta pela PK (primeira coluna).
-- A FK oferta_ensino.co_etapa_ensino tem apenas 3 valores distintos: um índice
-- não traria ganho. A FK de indicador_educacional é igual à sua PK.
--
-- Execução recomendada (após aprovação), interrompendo no primeiro erro:
--   psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1 -f 01_criacao_tabelas.sql
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

-- -----------------------------------------------------------------------------
-- 0. Trava de segurança: só prossegue no banco e no schema corretos.
--    Apenas consulta o catálogo; não cria nem altera nada.
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF current_database() <> 'educacao_jd_macedonia' THEN
        RAISE EXCEPTION 'Banco incorreto: %. Esperado: educacao_jd_macedonia.',
            current_database();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_namespace WHERE nspname = 'educacao') THEN
        RAISE EXCEPTION 'O schema educacao não existe no banco %.',
            current_database();
    END IF;
END
$$;

-- -----------------------------------------------------------------------------
-- 1. ESCOLA - uma linha por escola do recorte do município de São Paulo
--    Origem: data/raw/escolas_sp_2025.csv (Tabela de Escola, Censo 2025)
-- -----------------------------------------------------------------------------
CREATE TABLE educacao.escola (
    co_entidade                VARCHAR(8)   NOT NULL,
    no_entidade                VARCHAR(100) NOT NULL,
    co_municipio               VARCHAR(7)   NOT NULL,
    no_distrito                VARCHAR(100) NOT NULL,
    tp_dependencia             SMALLINT     NOT NULL,
    tp_situacao_funcionamento  SMALLINT     NOT NULL,
    ano_censo                  SMALLINT     NOT NULL,
    possui_registro_matricula  BOOLEAN      NOT NULL,

    CONSTRAINT pk_escola
        PRIMARY KEY (co_entidade),
    CONSTRAINT ck_escola_co_entidade
        CHECK (co_entidade ~ '^[0-9]{8}$'),
    CONSTRAINT ck_escola_no_entidade
        CHECK (btrim(no_entidade) <> ''),
    CONSTRAINT ck_escola_co_municipio
        CHECK (co_municipio = '3550308'),
    CONSTRAINT ck_escola_no_distrito
        CHECK (btrim(no_distrito) <> ''),
    CONSTRAINT ck_escola_tp_dependencia
        CHECK (tp_dependencia IN (1, 2, 3, 4)),
    CONSTRAINT ck_escola_tp_situacao_funcionamento
        CHECK (tp_situacao_funcionamento IN (1, 2, 3, 4)),
    CONSTRAINT ck_escola_ano_censo
        CHECK (ano_censo = 2025)
);

COMMENT ON TABLE educacao.escola IS
    'Cadastro das escolas do município de São Paulo no Censo Escolar 2025 (uma linha por código INEP).';
COMMENT ON COLUMN educacao.escola.co_entidade IS
    'Código INEP da escola (CO_ENTIDADE). Identificador com 8 dígitos, não é medida numérica.';
COMMENT ON COLUMN educacao.escola.no_entidade IS
    'Nome da escola no Censo 2025 (NO_ENTIDADE).';
COMMENT ON COLUMN educacao.escola.co_municipio IS
    'Código IBGE do município (CO_MUNICIPIO). O recorte contém apenas São Paulo (3550308).';
COMMENT ON COLUMN educacao.escola.no_distrito IS
    'Distrito (divisão intramunicipal) informado pelo Censo (NO_DISTRITO). Não equivale a bairro.';
COMMENT ON COLUMN educacao.escola.tp_dependencia IS
    'Dependência administrativa (TP_DEPENDENCIA): 1 Federal, 2 Estadual, 3 Municipal, 4 Privada.';
COMMENT ON COLUMN educacao.escola.tp_situacao_funcionamento IS
    'Situação de funcionamento (TP_SITUACAO_FUNCIONAMENTO): 1 Em atividade, 2 Paralisada, 3 Extinta (ano do Censo), 4 Extinta em anos anteriores.';
COMMENT ON COLUMN educacao.escola.ano_censo IS
    'Ano do Censo Escolar do cadastro (NU_ANO_CENSO). O projeto usa somente 2025.';
COMMENT ON COLUMN educacao.escola.possui_registro_matricula IS
    'Campo derivado: TRUE se o código INEP aparece na Tabela de Matrícula 2025. FALSE indica matrícula desconhecida (não é zero).';

-- -----------------------------------------------------------------------------
-- 2. ETAPA_ENSINO - tabela de domínio com as 3 etapas avaliadas pelo IDEB
--    Origem: regra do projeto (tratamento.ETAPAS_E_MATRICULAS)
-- -----------------------------------------------------------------------------
CREATE TABLE educacao.etapa_ensino (
    co_etapa_ensino         VARCHAR(2)  NOT NULL,
    no_etapa_ensino         VARCHAR(60) NOT NULL,
    coluna_matricula_censo  VARCHAR(30) NOT NULL,

    CONSTRAINT pk_etapa_ensino
        PRIMARY KEY (co_etapa_ensino),
    CONSTRAINT uq_etapa_ensino_no_etapa_ensino
        UNIQUE (no_etapa_ensino),
    CONSTRAINT uq_etapa_ensino_coluna_matricula_censo
        UNIQUE (coluna_matricula_censo),
    CONSTRAINT ck_etapa_ensino_co_etapa_ensino
        CHECK (co_etapa_ensino IN ('AI', 'AF', 'EM')),
    CONSTRAINT ck_etapa_ensino_coluna_matricula_censo
        CHECK (coluna_matricula_censo IN ('QT_MAT_FUND_AI', 'QT_MAT_FUND_AF', 'QT_MAT_MED'))
);

COMMENT ON TABLE educacao.etapa_ensino IS
    'Etapas de ensino analisadas: anos iniciais e finais do Ensino Fundamental e Ensino Médio.';
COMMENT ON COLUMN educacao.etapa_ensino.co_etapa_ensino IS
    'Código curto definido pelo projeto: AI, AF ou EM (o Inep não fornece código para estas etapas nos arquivos usados).';
COMMENT ON COLUMN educacao.etapa_ensino.no_etapa_ensino IS
    'Descrição da etapa, idêntica à coluna ETAPA_ENSINO da base integrada.';
COMMENT ON COLUMN educacao.etapa_ensino.coluna_matricula_censo IS
    'Coluna da Tabela de Matrícula 2025 que fornece a quantidade de matrículas da etapa.';

-- -----------------------------------------------------------------------------
-- 3. OFERTA_ENSINO - associativa N:N entre escola e etapa_ensino
--    Uma linha por escola, etapa e ano, somente quando há matrícula (> 0)
--    Origem: data/raw/matriculas_sp_2025.csv (Tabela de Matrícula, Censo 2025)
-- -----------------------------------------------------------------------------
CREATE TABLE educacao.oferta_ensino (
    co_entidade      VARCHAR(8) NOT NULL,
    co_etapa_ensino  VARCHAR(2) NOT NULL,
    ano_referencia   SMALLINT   NOT NULL,
    qt_matriculas    INTEGER    NOT NULL,

    CONSTRAINT pk_oferta_ensino
        PRIMARY KEY (co_entidade, co_etapa_ensino, ano_referencia),
    CONSTRAINT fk_oferta_ensino_escola
        FOREIGN KEY (co_entidade)
        REFERENCES educacao.escola (co_entidade)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT fk_oferta_ensino_etapa_ensino
        FOREIGN KEY (co_etapa_ensino)
        REFERENCES educacao.etapa_ensino (co_etapa_ensino)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ck_oferta_ensino_ano_referencia
        CHECK (ano_referencia = 2025),
    CONSTRAINT ck_oferta_ensino_qt_matriculas
        CHECK (qt_matriculas > 0)
);

COMMENT ON TABLE educacao.oferta_ensino IS
    'Etapas oferecidas por cada escola no Censo 2025. A linha só existe quando a etapa tem matrícula maior que zero.';
COMMENT ON COLUMN educacao.oferta_ensino.co_entidade IS
    'Código INEP da escola (FK para educacao.escola).';
COMMENT ON COLUMN educacao.oferta_ensino.co_etapa_ensino IS
    'Etapa de ensino (FK para educacao.etapa_ensino).';
COMMENT ON COLUMN educacao.oferta_ensino.ano_referencia IS
    'Ano do Censo Escolar das matrículas (NU_ANO_CENSO). O projeto usa somente 2025.';
COMMENT ON COLUMN educacao.oferta_ensino.qt_matriculas IS
    'Matrículas da etapa (QT_MAT_FUND_AI, QT_MAT_FUND_AF ou QT_MAT_MED). Sempre maior que zero.';

-- -----------------------------------------------------------------------------
-- 4. INDICADOR_EDUCACIONAL - resultado do IDEB 2025 para uma oferta
--    No máximo uma linha por oferta (PK = FK). Ausência de valor = NULL, nunca 0.
--    Origem: data/processed/escolas_publicas_sp_censo_2025_ideb_2025.csv
-- -----------------------------------------------------------------------------
CREATE TABLE educacao.indicador_educacional (
    co_entidade                VARCHAR(8)    NOT NULL,
    co_etapa_ensino            VARCHAR(2)    NOT NULL,
    ano_referencia             SMALLINT      NOT NULL,
    situacao_ideb              VARCHAR(60)   NOT NULL,
    vl_indicador_rendimento    NUMERIC(7, 6),
    vl_nota_matematica         NUMERIC(5, 2),
    vl_nota_portugues          NUMERIC(5, 2),
    vl_nota_media_padronizada  NUMERIC(8, 6),
    vl_ideb                    NUMERIC(3, 1),

    CONSTRAINT pk_indicador_educacional
        PRIMARY KEY (co_entidade, co_etapa_ensino, ano_referencia),
    CONSTRAINT fk_indicador_educacional_oferta_ensino
        FOREIGN KEY (co_entidade, co_etapa_ensino, ano_referencia)
        REFERENCES educacao.oferta_ensino (co_entidade, co_etapa_ensino, ano_referencia)
        ON UPDATE RESTRICT ON DELETE RESTRICT,
    CONSTRAINT ck_indicador_educacional_ano_referencia
        CHECK (ano_referencia = 2025),
    CONSTRAINT ck_indicador_educacional_situacao_ideb
        CHECK (situacao_ideb IN (
            'Divulgado',
            'Não divulgado pelo Inep',
            'Escola/etapa não localizada no arquivo do Inep'
        )),
    -- O IDEB está preenchido se, e somente se, a situação é "Divulgado".
    CONSTRAINT ck_indicador_educacional_ideb_conforme_situacao
        CHECK ((situacao_ideb = 'Divulgado') = (vl_ideb IS NOT NULL)),
    -- Um IDEB divulgado é calculado a partir das notas e do rendimento.
    CONSTRAINT ck_indicador_educacional_divulgado_completo
        CHECK (
            situacao_ideb <> 'Divulgado'
            OR (vl_indicador_rendimento IS NOT NULL
                AND vl_nota_matematica IS NOT NULL
                AND vl_nota_portugues IS NOT NULL
                AND vl_nota_media_padronizada IS NOT NULL)
        ),
    -- Escola/etapa ausente no arquivo do Inep não possui nenhum valor.
    CONSTRAINT ck_indicador_educacional_nao_localizado_sem_valores
        CHECK (
            situacao_ideb <> 'Escola/etapa não localizada no arquivo do Inep'
            OR (vl_indicador_rendimento IS NULL
                AND vl_nota_matematica IS NULL
                AND vl_nota_portugues IS NULL
                AND vl_nota_media_padronizada IS NULL
                AND vl_ideb IS NULL)
        ),
    -- Faixas válidas (um CHECK com valor NULL é considerado satisfeito).
    CONSTRAINT ck_indicador_educacional_vl_indicador_rendimento
        CHECK (vl_indicador_rendimento BETWEEN 0 AND 1),
    CONSTRAINT ck_indicador_educacional_vl_nota_matematica
        CHECK (vl_nota_matematica BETWEEN 0 AND 500),
    CONSTRAINT ck_indicador_educacional_vl_nota_portugues
        CHECK (vl_nota_portugues BETWEEN 0 AND 500),
    CONSTRAINT ck_indicador_educacional_vl_nota_media_padronizada
        CHECK (vl_nota_media_padronizada BETWEEN 0 AND 10),
    CONSTRAINT ck_indicador_educacional_vl_ideb
        CHECK (vl_ideb BETWEEN 0 AND 10)
);

COMMENT ON TABLE educacao.indicador_educacional IS
    'IDEB 2025 e componentes (Saeb e rendimento) por escola e etapa. Existe apenas para ofertas de escolas públicas em atividade.';
COMMENT ON COLUMN educacao.indicador_educacional.co_entidade IS
    'Código INEP da escola (parte da FK para educacao.oferta_ensino).';
COMMENT ON COLUMN educacao.indicador_educacional.co_etapa_ensino IS
    'Etapa de ensino (parte da FK para educacao.oferta_ensino).';
COMMENT ON COLUMN educacao.indicador_educacional.ano_referencia IS
    'Ano de referência comum ao Censo e à edição do IDEB consultada (2025).';
COMMENT ON COLUMN educacao.indicador_educacional.situacao_ideb IS
    'Disponibilidade do IDEB: Divulgado, Não divulgado pelo Inep ou Escola/etapa não localizada no arquivo do Inep.';
COMMENT ON COLUMN educacao.indicador_educacional.vl_indicador_rendimento IS
    'Indicador de rendimento (VL_INDICADOR_REND_2025), entre 0 e 1. Pode existir mesmo sem IDEB divulgado.';
COMMENT ON COLUMN educacao.indicador_educacional.vl_nota_matematica IS
    'Nota média de Matemática no Saeb 2025 (VL_NOTA_MATEMATICA_2025).';
COMMENT ON COLUMN educacao.indicador_educacional.vl_nota_portugues IS
    'Nota média de Língua Portuguesa no Saeb 2025 (VL_NOTA_PORTUGUES_2025).';
COMMENT ON COLUMN educacao.indicador_educacional.vl_nota_media_padronizada IS
    'Nota média padronizada do Saeb 2025, entre 0 e 10 (VL_NOTA_MEDIA_2025).';
COMMENT ON COLUMN educacao.indicador_educacional.vl_ideb IS
    'IDEB 2025 observado (VL_OBSERVADO_2025). NULL quando não divulgado; nunca substituído por zero.';

COMMIT;
