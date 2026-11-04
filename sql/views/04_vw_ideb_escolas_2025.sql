-- =============================================================================
-- View    : educacao.vw_ideb_escolas_2025
-- Projeto : Análise da Educação Pública no Jardim Macedônia (São Paulo)
-- Fontes  : Inep - Censo Escolar 2025 e IDEB/Saeb 2025
--           (tabelas escola, etapa_ensino, oferta_ensino, indicador_educacional)
-- Banco   : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Objetivo: IDEB 2025 INDIVIDUAL por escola e etapa, junto com as matrículas,
--           para as escolas públicas em atividade de São Paulo. É a base
--           granular da análise exploratória (eda.py): distribuições,
--           quartis e comparações calculadas em Python.
--
-- Granularidade: 1 linha por escola x etapa x ano
--                (co_entidade, co_etapa_ensino, ano_referencia).
-- Resultado esperado: 2.973 linhas | 1.709 escolas |
--                     2.596 com IDEB divulgado | 377 sem IDEB (NULL).
--
-- Regras:
--   * A base é a oferta (escola com matrícula > 0 na etapa). O LEFT JOIN com o
--     indicador preserva a oferta mesmo que não houvesse indicador; nos dados
--     de 2025 toda oferta pública ativa tem indicador (validação 02).
--   * IDEB ausente permanece NULL; nunca é convertido em zero.
--
-- Independe das views 01 a 03 (usa somente as tabelas).
--
-- Execução (somente após revisão), interrompendo no primeiro erro:
--   psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1 -f 04_vw_ideb_escolas_2025.sql
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

CREATE OR REPLACE VIEW educacao.vw_ideb_escolas_2025 AS
SELECT
    e.co_entidade,
    e.no_entidade,
    e.tp_dependencia,
    CASE e.tp_dependencia
        WHEN 1 THEN 'Federal'
        WHEN 2 THEN 'Estadual'
        WHEN 3 THEN 'Municipal'
    END                     AS rede_administrativa,
    o.co_etapa_ensino,
    t.no_etapa_ensino,
    o.qt_matriculas,
    i.vl_ideb,
    i.situacao_ideb,
    o.ano_referencia
FROM educacao.oferta_ensino AS o
-- N:1 -> cada oferta tem exatamente uma escola
JOIN educacao.escola AS e
  ON e.co_entidade = o.co_entidade
-- N:1 -> cada oferta tem exatamente uma etapa
JOIN educacao.etapa_ensino AS t
  ON t.co_etapa_ensino = o.co_etapa_ensino
-- 1:0..1 -> no máximo um indicador por oferta (PK do indicador = PK da oferta)
LEFT JOIN educacao.indicador_educacional AS i
  ON  i.co_entidade     = o.co_entidade
  AND i.co_etapa_ensino = o.co_etapa_ensino
  AND i.ano_referencia  = o.ano_referencia
WHERE e.tp_dependencia IN (1, 2, 3)          -- públicas: federal, estadual, municipal
  AND e.tp_situacao_funcionamento = 1        -- em atividade
  AND o.ano_referencia = 2025;

COMMENT ON VIEW educacao.vw_ideb_escolas_2025 IS
    'IDEB 2025 individual e matrículas por escola e etapa (escolas públicas ativas de SP). 1 linha por escola x etapa x ano. IDEB ausente = NULL, nunca zero.';
COMMENT ON COLUMN educacao.vw_ideb_escolas_2025.vl_ideb IS
    'IDEB 2025 observado da escola na etapa. NULL quando não divulgado pelo Inep ou não localizado no arquivo do Inep.';
COMMENT ON COLUMN educacao.vw_ideb_escolas_2025.situacao_ideb IS
    'Divulgado, Não divulgado pelo Inep ou Escola/etapa não localizada no arquivo do Inep.';
COMMENT ON COLUMN educacao.vw_ideb_escolas_2025.qt_matriculas IS
    'Matrículas da escola na etapa (Censo 2025). Indica porte, não desempenho.';

COMMIT;
