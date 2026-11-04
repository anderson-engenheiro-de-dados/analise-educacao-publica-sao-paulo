-- =============================================================================
-- View    : educacao.vw_ideb_rede_etapa_2025
-- Projeto : Análise da Educação Pública no Jardim Macedônia (São Paulo)
-- Fontes  : Inep - IDEB/Saeb 2025 e Censo Escolar 2025
--           (tabelas indicador_educacional, escola, etapa_ensino)
-- Banco   : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Objetivo: indicadores agregados do IDEB 2025 por rede administrativa e
--           etapa de ensino, para as escolas públicas ativas de São Paulo.
--
-- Granularidade: 1 linha por ano x rede x etapa
--                (ano_referencia, tp_dependencia, co_etapa_ensino).
-- Resultado esperado: 9 linhas | 2.973 ofertas | 2.596 IDEB divulgados | 377 ausentes.
--
-- Regras:
--   * avg, percentile_cont, min, max e count(coluna) IGNORAM valores NULL:
--     IDEB ausente não entra no cálculo e nunca é tratado como zero.
--   * Os indicadores refletem os resultados DISPONÍVEIS, não necessariamente
--     todas as escolas da rede.
--
-- Execução (somente após revisão), interrompendo no primeiro erro:
--   psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1 -f 02_vw_ideb_rede_etapa_2025.sql
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

CREATE OR REPLACE VIEW educacao.vw_ideb_rede_etapa_2025 AS
SELECT
    i.ano_referencia,
    e.tp_dependencia,
    CASE e.tp_dependencia
        WHEN 1 THEN 'Federal'
        WHEN 2 THEN 'Estadual'
        WHEN 3 THEN 'Municipal'
    END                                                   AS rede_administrativa,
    i.co_etapa_ensino,
    t.no_etapa_ensino,
    count(*)                                              AS qt_ofertas_avaliadas,
    count(i.vl_ideb)                                      AS qt_ideb_divulgado,
    count(*) FILTER (WHERE i.vl_ideb IS NULL)             AS qt_ideb_ausente,
    count(*) FILTER (
        WHERE i.situacao_ideb = 'Não divulgado pelo Inep')
                                                          AS qt_nao_divulgado_inep,
    count(*) FILTER (
        WHERE i.situacao_ideb = 'Escola/etapa não localizada no arquivo do Inep')
                                                          AS qt_nao_localizado_inep,
    round(avg(i.vl_ideb), 2)                              AS media_ideb,
    round((percentile_cont(0.5) WITHIN GROUP (
              ORDER BY i.vl_ideb::double precision))::numeric, 2)
                                                          AS mediana_ideb,
    min(i.vl_ideb)                                        AS menor_ideb,
    max(i.vl_ideb)                                        AS maior_ideb
FROM educacao.indicador_educacional AS i
-- N:1 -> cada indicador pertence a uma escola (via oferta; co_entidade é PK de escola)
JOIN educacao.escola AS e
  ON e.co_entidade = i.co_entidade
-- N:1 -> cada indicador pertence a uma etapa
JOIN educacao.etapa_ensino AS t
  ON t.co_etapa_ensino = i.co_etapa_ensino
WHERE i.ano_referencia = 2025
  AND e.tp_dependencia IN (1, 2, 3)          -- públicas
  AND e.tp_situacao_funcionamento = 1        -- em atividade
GROUP BY
    i.ano_referencia,
    e.tp_dependencia,
    i.co_etapa_ensino,
    t.no_etapa_ensino;

COMMENT ON VIEW educacao.vw_ideb_rede_etapa_2025 IS
    'IDEB 2025 agregado por rede e etapa (escolas públicas ativas de SP). Médias, mediana, mínimo e máximo ignoram IDEB ausente (NULL). Reflete os resultados disponíveis, não necessariamente todas as escolas da rede.';
COMMENT ON COLUMN educacao.vw_ideb_rede_etapa_2025.qt_ofertas_avaliadas IS
    'Ofertas (escola x etapa) incluídas na integração com o IDEB, com ou sem resultado divulgado.';
COMMENT ON COLUMN educacao.vw_ideb_rede_etapa_2025.qt_ideb_divulgado IS
    'Ofertas com IDEB 2025 divulgado (vl_ideb não nulo). É o número de valores usados na média e na mediana.';
COMMENT ON COLUMN educacao.vw_ideb_rede_etapa_2025.qt_ideb_ausente IS
    'Ofertas sem IDEB 2025 (não divulgado pelo Inep ou não localizado no arquivo do Inep).';
COMMENT ON COLUMN educacao.vw_ideb_rede_etapa_2025.media_ideb IS
    'Média do IDEB 2025 (2 casas decimais), somente com valores divulgados.';
COMMENT ON COLUMN educacao.vw_ideb_rede_etapa_2025.mediana_ideb IS
    'Mediana do IDEB 2025 (percentile_cont 0,5; 2 casas decimais), somente com valores divulgados.';

COMMIT;
