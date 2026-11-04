-- =============================================================================
-- View    : educacao.vw_ideb_jardim_macedonia_2025
-- Projeto : Análise da Educação Pública no Jardim Macedônia (São Paulo)
-- Fontes  : Inep - IDEB/Saeb 2025 e Censo Escolar 2025
-- Banco   : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Objetivo: comparar o IDEB 2025 das escolas de interesse do Jardim Macedônia
--           com a média da MESMA rede e da MESMA etapa em São Paulo.
--
-- Escolas : EMEF César Yasigi (35010281) e EE Jornalista David Nasser (35044386).
--
-- Granularidade: 1 linha por escola x etapa x ano
--                (co_entidade, co_etapa_ensino, ano_referencia).
-- Resultado esperado: 4 linhas (Yasigi AI; David Nasser AI, AF e EM).
--
-- LIMITAÇÃO GEOGRÁFICA: o Censo 2025 não possui campo de bairro. As escolas
-- foram identificadas por códigos INEP previamente documentados
-- (tratamento.CODIGOS_JARDIM_MACEDONIA) e NÃO representam necessariamente
-- todos os estabelecimentos do bairro.
--
-- DEPENDÊNCIA: usa educacao.vw_ideb_rede_etapa_2025 (criar o arquivo 02 antes).
--
-- Execução (somente após revisão), interrompendo no primeiro erro:
--   psql -d educacao_jd_macedonia -v ON_ERROR_STOP=1 -f 03_vw_ideb_jardim_macedonia_2025.sql
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

CREATE OR REPLACE VIEW educacao.vw_ideb_jardim_macedonia_2025 AS
SELECT
    e.co_entidade,
    e.no_entidade,
    e.tp_dependencia,
    CASE e.tp_dependencia
        WHEN 1 THEN 'Federal'
        WHEN 2 THEN 'Estadual'
        WHEN 3 THEN 'Municipal'
    END                                   AS rede_administrativa,
    i.co_etapa_ensino,
    t.no_etapa_ensino,
    o.qt_matriculas,
    i.situacao_ideb,
    i.vl_ideb                             AS ideb_escola,
    r.media_ideb                          AS media_ideb_rede_etapa,
    -- NULL - número = NULL: sem IDEB divulgado, a diferença fica ausente.
    round(i.vl_ideb - r.media_ideb, 2)    AS diferenca_ideb_rede_etapa,
    r.qt_ideb_divulgado                   AS qt_ideb_na_media_rede_etapa,
    i.ano_referencia
FROM educacao.indicador_educacional AS i
-- 1:1 -> o indicador tem exatamente uma oferta (PK = FK)
JOIN educacao.oferta_ensino AS o
  ON  o.co_entidade     = i.co_entidade
  AND o.co_etapa_ensino = i.co_etapa_ensino
  AND o.ano_referencia  = i.ano_referencia
JOIN educacao.escola AS e
  ON e.co_entidade = i.co_entidade
JOIN educacao.etapa_ensino AS t
  ON t.co_etapa_ensino = i.co_etapa_ensino
-- N:1 -> no máximo uma linha da view agregada por ano x rede x etapa
LEFT JOIN educacao.vw_ideb_rede_etapa_2025 AS r
  ON  r.ano_referencia  = i.ano_referencia
  AND r.tp_dependencia  = e.tp_dependencia
  AND r.co_etapa_ensino = i.co_etapa_ensino
WHERE i.ano_referencia = 2025
  AND i.co_entidade IN ('35010281', '35044386');

COMMENT ON VIEW educacao.vw_ideb_jardim_macedonia_2025 IS
    'IDEB 2025 da EMEF César Yasigi (35010281) e da EE Jornalista David Nasser (35044386) comparado com a média da mesma rede e etapa em SP. Escolas identificadas por código INEP: o Censo 2025 não possui bairro.';
COMMENT ON COLUMN educacao.vw_ideb_jardim_macedonia_2025.media_ideb_rede_etapa IS
    'Média do IDEB 2025 da mesma rede e etapa (vw_ideb_rede_etapa_2025), arredondada em 2 casas; inclui a própria escola.';
COMMENT ON COLUMN educacao.vw_ideb_jardim_macedonia_2025.diferenca_ideb_rede_etapa IS
    'IDEB da escola menos a média da rede e etapa. NULL quando o IDEB da escola não foi divulgado.';

COMMIT;
