-- =============================================================================
-- Validação da view educacao.vw_ideb_escolas_2025 (SOMENTE LEITURA)
-- Banco  : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Pré-requisito: views 01, 02, 03 (já criadas) e 04 (sql/views/04_...).
--
-- Consulta 1: lista de 16 verificações (esperado, obtido, ok).
--             Todas as linhas devem ter ok = true.
-- Consulta 2: amostra das escolas de interesse (conferência visual).
--
-- Nenhum comando deste arquivo grava, altera ou apaga dados.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Consulta 1 - Lista de verificações
-- -----------------------------------------------------------------------------
WITH
v4 AS (SELECT * FROM educacao.vw_ideb_escolas_2025),

-- Recalcula, a partir da view 04, os agregados da view 02
agregado_v4 AS (
    SELECT ano_referencia, tp_dependencia, co_etapa_ensino,
           count(*)                     AS ofertas,
           count(vl_ideb)               AS divulgados,
           round(avg(vl_ideb), 2)       AS media
    FROM v4
    GROUP BY ano_referencia, tp_dependencia, co_etapa_ensino
),

verificacoes (n, verificacao, esperado, obtido) AS (
    SELECT 1, 'V4: registros escola/etapa', '2973',
           (SELECT count(*) FROM v4)::text
    UNION ALL
    SELECT 2, 'V4: granularidade única (escola, etapa, ano)', '2973',
           (SELECT count(*) FROM (SELECT DISTINCT co_entidade, co_etapa_ensino, ano_referencia
                                  FROM v4) AS d)::text
    UNION ALL
    SELECT 3, 'V4: escolas distintas', '1709',
           (SELECT count(DISTINCT co_entidade) FROM v4)::text
    UNION ALL
    SELECT 4, 'V4: registros com IDEB divulgado', '2596',
           (SELECT count(vl_ideb) FROM v4)::text
    UNION ALL
    SELECT 5, 'V4: registros sem IDEB (NULL)', '377',
           (SELECT count(*) FROM v4 WHERE vl_ideb IS NULL)::text
    UNION ALL
    SELECT 6, 'V4: IDEB igual a zero (não pode haver)', '0',
           (SELECT count(*) FROM v4 WHERE vl_ideb = 0)::text
    UNION ALL
    SELECT 7, 'V4: ofertas sem indicador (situação NULL)', '0',
           (SELECT count(*) FROM v4 WHERE situacao_ideb IS NULL)::text
    UNION ALL
    SELECT 8, 'V4: IDEB preenchido sem situação "Divulgado" (ou o inverso)', '0',
           (SELECT count(*) FROM v4
            WHERE (situacao_ideb = 'Divulgado') <> (vl_ideb IS NOT NULL))::text
    UNION ALL
    SELECT 9, 'V4: soma de matrículas', '1284021',
           (SELECT sum(qt_matriculas) FROM v4)::text
    UNION ALL
    SELECT 10, 'V4: códigos INEP fora do padrão de 8 dígitos', '0',
           (SELECT count(*) FROM v4 WHERE co_entidade !~ '^[0-9]{8}$')::text
    UNION ALL
    SELECT 11, 'V4 x V1: chaves diferentes (nos dois sentidos)', '0',
           (SELECT count(*) FROM (
                (SELECT co_entidade, co_etapa_ensino, ano_referencia FROM v4
                 EXCEPT
                 SELECT co_entidade, co_etapa_ensino, ano_referencia
                 FROM educacao.vw_escolas_matriculas_2025)
                UNION ALL
                (SELECT co_entidade, co_etapa_ensino, ano_referencia
                 FROM educacao.vw_escolas_matriculas_2025
                 EXCEPT
                 SELECT co_entidade, co_etapa_ensino, ano_referencia FROM v4)
            ) AS dif)::text
    UNION ALL
    SELECT 12, 'V4 x V1: matrículas diferentes na mesma chave', '0',
           (SELECT count(*) FROM v4
            JOIN educacao.vw_escolas_matriculas_2025 AS v1
              ON  v1.co_entidade     = v4.co_entidade
             AND v1.co_etapa_ensino = v4.co_etapa_ensino
             AND v1.ano_referencia  = v4.ano_referencia
            WHERE v1.qt_matriculas <> v4.qt_matriculas)::text
    UNION ALL
    SELECT 13, 'V4 x V2: grupos rede x etapa com contagem ou média diferente', '0',
           (SELECT count(*) FROM agregado_v4 AS a
            JOIN educacao.vw_ideb_rede_etapa_2025 AS v2
              ON  v2.ano_referencia  = a.ano_referencia
             AND v2.tp_dependencia  = a.tp_dependencia
             AND v2.co_etapa_ensino = a.co_etapa_ensino
            WHERE v2.qt_ofertas_avaliadas <> a.ofertas
               OR v2.qt_ideb_divulgado    <> a.divulgados
               OR v2.media_ideb           <> a.media)::text
    UNION ALL
    SELECT 14, 'V4 x V2: grupos rede x etapa', '9',
           (SELECT count(*) FROM agregado_v4)::text
    UNION ALL
    SELECT 15, 'V4 x V3: linhas das escolas de interesse', '4',
           (SELECT count(*) FROM v4 WHERE co_entidade IN ('35010281', '35044386'))::text
    UNION ALL
    SELECT 16, 'V4 x V3: IDEB, matrículas ou situação diferentes', '0',
           (SELECT count(*) FROM v4
            JOIN educacao.vw_ideb_jardim_macedonia_2025 AS v3
              ON  v3.co_entidade     = v4.co_entidade
             AND v3.co_etapa_ensino = v4.co_etapa_ensino
             AND v3.ano_referencia  = v4.ano_referencia
            WHERE v3.ideb_escola IS DISTINCT FROM v4.vl_ideb
               OR v3.qt_matriculas <> v4.qt_matriculas
               OR v3.situacao_ideb <> v4.situacao_ideb)::text
)
SELECT n, verificacao, esperado, obtido,
       (esperado IS NOT DISTINCT FROM obtido) AS ok
FROM verificacoes
ORDER BY n;

-- -----------------------------------------------------------------------------
-- Consulta 2 - Escolas de interesse (conferência visual)
-- -----------------------------------------------------------------------------
SELECT co_entidade, no_entidade, rede_administrativa, co_etapa_ensino,
       qt_matriculas, vl_ideb, situacao_ideb, ano_referencia
FROM educacao.vw_ideb_escolas_2025
WHERE co_entidade IN ('35010281', '35044386')
ORDER BY co_entidade, co_etapa_ensino;
