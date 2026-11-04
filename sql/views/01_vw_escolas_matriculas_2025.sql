-- =============================================================================
-- View    : educacao.vw_escolas_matriculas_2025
-- Projeto : Análise da Educação Pública no Jardim Macedônia (São Paulo)
-- Fontes  : Inep - Censo Escolar 2025 (tabelas escola, oferta_ensino, etapa_ensino)
-- Banco   : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Objetivo: matrículas das escolas PÚBLICAS e EM ATIVIDADE de São Paulo,
--           por escola, rede administrativa e etapa de ensino (2025).
--
-- Granularidade: 1 linha por escola x etapa x ano
--                (co_entidade, co_etapa_ensino, ano_referencia).
-- Resultado esperado: 2.973 linhas | 1.709 escolas | 1.284.021 matrículas.
--
-- ATENÇÃO: média de matrículas POR ESCOLA exige somar antes por co_entidade
-- (ver docs/views_analiticas.md). A média direta das linhas é por oferta.
--
-- Execução (somente após revisão), interrompendo no primeiro erro:
--   psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1 -f 01_vw_escolas_matriculas_2025.sql
-- =============================================================================

SET client_encoding = 'UTF8';

BEGIN;

-- Trava de segurança: só prossegue no banco correto.
DO $$
BEGIN
    IF current_database() <> 'educacao_jd_macedonia' THEN
        RAISE EXCEPTION 'Banco incorreto: %. Esperado: educacao_jd_macedonia.',
            current_database();
    END IF;
END
$$;

CREATE OR REPLACE VIEW educacao.vw_escolas_matriculas_2025 AS
SELECT
    e.co_entidade,
    e.no_entidade,
    e.no_distrito,
    e.tp_dependencia,
    CASE e.tp_dependencia
        WHEN 1 THEN 'Federal'
        WHEN 2 THEN 'Estadual'
        WHEN 3 THEN 'Municipal'
    END                     AS rede_administrativa,
    o.co_etapa_ensino,
    t.no_etapa_ensino,
    o.qt_matriculas,
    o.ano_referencia
FROM educacao.oferta_ensino AS o
-- N:1 -> cada oferta tem exatamente uma escola (FK fk_oferta_ensino_escola)
JOIN educacao.escola AS e
  ON e.co_entidade = o.co_entidade
-- N:1 -> cada oferta tem exatamente uma etapa (FK fk_oferta_ensino_etapa_ensino)
JOIN educacao.etapa_ensino AS t
  ON t.co_etapa_ensino = o.co_etapa_ensino
WHERE e.tp_dependencia IN (1, 2, 3)          -- públicas: federal, estadual, municipal
  AND e.tp_situacao_funcionamento = 1        -- em atividade
  AND o.ano_referencia = 2025;

COMMENT ON VIEW educacao.vw_escolas_matriculas_2025 IS
    'Matrículas 2025 das escolas públicas ativas de São Paulo: 1 linha por escola e etapa (AI, AF, EM). Só há linha quando a etapa tem matrícula > 0.';
COMMENT ON COLUMN educacao.vw_escolas_matriculas_2025.rede_administrativa IS
    'Rede derivada de tp_dependencia: 1 Federal, 2 Estadual, 3 Municipal.';
COMMENT ON COLUMN educacao.vw_escolas_matriculas_2025.qt_matriculas IS
    'Matrículas da escola na etapa (Censo 2025). Para média por escola, somar antes por co_entidade.';

COMMIT;
