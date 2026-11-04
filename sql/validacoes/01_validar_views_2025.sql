-- =============================================================================
-- Validação das views analíticas 2025 (SOMENTE LEITURA)
-- Banco  : educacao_jd_macedonia (PostgreSQL 17) | Schema: educacao
--
-- Pré-requisito: views criadas pelos scripts sql/views/01, 02 e 03.
--
-- Consulta 1: lista de 28 verificações. Cada linha mostra o valor esperado, o
-- valor obtido e ok = true/false. Todas as linhas devem ter ok = true.
-- Consultas 2 e 3: resultados detalhados para conferência visual.
--
-- Nenhum comando deste arquivo grava, altera ou apaga dados.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Consulta 1 - Lista de verificações
-- -----------------------------------------------------------------------------
WITH
v1 AS (SELECT * FROM educacao.vw_escolas_matriculas_2025),
v2 AS (SELECT * FROM educacao.vw_ideb_rede_etapa_2025),
v3 AS (SELECT * FROM educacao.vw_ideb_jardim_macedonia_2025),

-- Base direta nas tabelas: ofertas de escolas públicas ativas (para comparar)
base_oferta AS (
    SELECT o.co_entidade, o.co_etapa_ensino, o.ano_referencia, o.qt_matriculas
    FROM educacao.oferta_ensino AS o
    JOIN educacao.escola AS e ON e.co_entidade = o.co_entidade
    WHERE e.tp_dependencia IN (1, 2, 3)
      AND e.tp_situacao_funcionamento = 1
      AND o.ano_referencia = 2025
),

-- Recalcula a média por rede e etapa diretamente nas tabelas (sum/count dos não nulos)
media_recalculada AS (
    SELECT e.tp_dependencia, i.co_etapa_ensino,
           round(sum(i.vl_ideb) / count(i.vl_ideb), 2) AS media
    FROM educacao.indicador_educacional AS i
    JOIN educacao.escola AS e ON e.co_entidade = i.co_entidade
    WHERE i.ano_referencia = 2025
      AND e.tp_dependencia IN (1, 2, 3)
      AND e.tp_situacao_funcionamento = 1
    GROUP BY e.tp_dependencia, i.co_etapa_ensino
),

-- Média de matrículas POR ESCOLA (soma por co_entidade antes da média)
matriculas_por_escola AS (
    SELECT co_entidade, sum(qt_matriculas) AS total
    FROM v1
    GROUP BY co_entidade
),

verificacoes (n, verificacao, esperado, obtido) AS (
    -- View 1: matrículas -------------------------------------------------------
    SELECT 1, 'V1: registros escola/etapa', '2973',
           (SELECT count(*) FROM v1)::text
    UNION ALL
    SELECT 2, 'V1: escolas distintas', '1709',
           (SELECT count(DISTINCT co_entidade) FROM v1)::text
    UNION ALL
    SELECT 3, 'V1: granularidade única (escola, etapa, ano)', '2973',
           (SELECT count(*) FROM (SELECT DISTINCT co_entidade, co_etapa_ensino, ano_referencia
                                  FROM v1) AS d)::text
    UNION ALL
    SELECT 4, 'V1: sem multiplicação por JOIN (= ofertas públicas ativas)',
           (SELECT count(*) FROM base_oferta)::text,
           (SELECT count(*) FROM v1)::text
    UNION ALL
    SELECT 5, 'V1: soma de matrículas = tabela oferta_ensino',
           (SELECT sum(qt_matriculas) FROM base_oferta)::text,
           (SELECT sum(qt_matriculas) FROM v1)::text
    UNION ALL
    SELECT 6, 'V1: soma de matrículas (valor preparado na carga)', '1284021',
           (SELECT sum(qt_matriculas) FROM v1)::text
    UNION ALL
    SELECT 7, 'V1: média de matrículas POR ESCOLA', '751.33',
           (SELECT round(avg(total), 2) FROM matriculas_por_escola)::text
    UNION ALL
    SELECT 8, 'V1: chaves iguais às de indicador_educacional (diferenças)', '0',
           (SELECT count(*) FROM (
                (SELECT co_entidade, co_etapa_ensino, ano_referencia FROM v1
                 EXCEPT
                 SELECT co_entidade, co_etapa_ensino, ano_referencia
                 FROM educacao.indicador_educacional)
                UNION ALL
                (SELECT co_entidade, co_etapa_ensino, ano_referencia
                 FROM educacao.indicador_educacional
                 EXCEPT
                 SELECT co_entidade, co_etapa_ensino, ano_referencia FROM v1)
            ) AS dif)::text
    UNION ALL
    SELECT 9, 'V1: códigos INEP fora do padrão de 8 dígitos', '0',
           (SELECT count(*) FROM v1 WHERE co_entidade !~ '^[0-9]{8}$')::text
    UNION ALL
    SELECT 10, 'V1: linhas sem rede administrativa', '0',
           (SELECT count(*) FROM v1 WHERE rede_administrativa IS NULL)::text

    -- View 2: IDEB por rede e etapa -------------------------------------------
    UNION ALL
    SELECT 11, 'V2: combinações rede x etapa', '9',
           (SELECT count(*) FROM v2)::text
    UNION ALL
    SELECT 12, 'V2: granularidade única (ano, rede, etapa)', '9',
           (SELECT count(*) FROM (SELECT DISTINCT ano_referencia, tp_dependencia, co_etapa_ensino
                                  FROM v2) AS d)::text
    UNION ALL
    SELECT 13, 'V2: total de ofertas avaliadas', '2973',
           (SELECT sum(qt_ofertas_avaliadas) FROM v2)::text
    UNION ALL
    SELECT 14, 'V2: total de IDEB divulgados', '2596',
           (SELECT sum(qt_ideb_divulgado) FROM v2)::text
    UNION ALL
    SELECT 15, 'V2: total de IDEB ausentes', '377',
           (SELECT sum(qt_ideb_ausente) FROM v2)::text
    UNION ALL
    SELECT 16, 'V2: linhas com divulgados + ausentes <> ofertas', '0',
           (SELECT count(*) FROM v2
            WHERE qt_ideb_divulgado + qt_ideb_ausente <> qt_ofertas_avaliadas)::text
    UNION ALL
    SELECT 17, 'V2: linhas com não divulgado + não localizado <> ausentes', '0',
           (SELECT count(*) FROM v2
            WHERE qt_nao_divulgado_inep + qt_nao_localizado_inep <> qt_ideb_ausente)::text
    UNION ALL
    SELECT 18, 'V2: médias diferentes do recálculo só com valores válidos', '0',
           (SELECT count(*) FROM v2
            JOIN media_recalculada AS m
              ON m.tp_dependencia = v2.tp_dependencia
             AND m.co_etapa_ensino = v2.co_etapa_ensino
            WHERE m.media <> v2.media_ideb)::text
    UNION ALL
    SELECT 19, 'V2: linhas com média fora do intervalo [menor, maior]', '0',
           (SELECT count(*) FROM v2
            WHERE media_ideb < menor_ideb OR media_ideb > maior_ideb
               OR mediana_ideb < menor_ideb OR mediana_ideb > maior_ideb)::text
    UNION ALL
    SELECT 20, 'V2: IDEB ausentes no indicador (contagem direta)', '377',
           (SELECT count(*) FROM educacao.indicador_educacional
            WHERE ano_referencia = 2025 AND vl_ideb IS NULL)::text

    -- View 3: Jardim Macedônia ------------------------------------------------
    UNION ALL
    SELECT 21, 'V3: registros', '4',
           (SELECT count(*) FROM v3)::text
    UNION ALL
    SELECT 22, 'V3: granularidade única (escola, etapa, ano)', '4',
           (SELECT count(*) FROM (SELECT DISTINCT co_entidade, co_etapa_ensino, ano_referencia
                                  FROM v3) AS d)::text
    UNION ALL
    SELECT 23, 'V3: escolas distintas', '2',
           (SELECT count(DISTINCT co_entidade) FROM v3)::text
    UNION ALL
    SELECT 24, 'V3: diferença preenchida sem IDEB da escola', '0',
           (SELECT count(*) FROM v3
            WHERE (ideb_escola IS NULL) <> (diferenca_ideb_rede_etapa IS NULL))::text
    UNION ALL
    SELECT 25, 'V3: 35010281 AI (matr. | IDEB | média | diferença | situação)',
           '464 | 6.4 | 5.87 | 0.53 | Divulgado',
           (SELECT qt_matriculas || ' | ' || coalesce(ideb_escola::text, 'NULL') || ' | '
                   || media_ideb_rede_etapa || ' | '
                   || coalesce(diferenca_ideb_rede_etapa::text, 'NULL') || ' | ' || situacao_ideb
            FROM v3 WHERE co_entidade = '35010281' AND co_etapa_ensino = 'AI')
    UNION ALL
    SELECT 26, 'V3: 35044386 AI (matr. | IDEB | média | diferença | situação)',
           '233 | 5.7 | 6.53 | -0.83 | Divulgado',
           (SELECT qt_matriculas || ' | ' || coalesce(ideb_escola::text, 'NULL') || ' | '
                   || media_ideb_rede_etapa || ' | '
                   || coalesce(diferenca_ideb_rede_etapa::text, 'NULL') || ' | ' || situacao_ideb
            FROM v3 WHERE co_entidade = '35044386' AND co_etapa_ensino = 'AI')
    UNION ALL
    SELECT 27, 'V3: 35044386 AF (matr. | IDEB | média | diferença | situação)',
           '336 | 3.9 | 5.11 | -1.21 | Divulgado',
           (SELECT qt_matriculas || ' | ' || coalesce(ideb_escola::text, 'NULL') || ' | '
                   || media_ideb_rede_etapa || ' | '
                   || coalesce(diferenca_ideb_rede_etapa::text, 'NULL') || ' | ' || situacao_ideb
            FROM v3 WHERE co_entidade = '35044386' AND co_etapa_ensino = 'AF')
    UNION ALL
    SELECT 28, 'V3: 35044386 EM (matr. | IDEB | média | diferença | situação)',
           '393 | NULL | 4.44 | NULL | Não divulgado pelo Inep',
           (SELECT qt_matriculas || ' | ' || coalesce(ideb_escola::text, 'NULL') || ' | '
                   || media_ideb_rede_etapa || ' | '
                   || coalesce(diferenca_ideb_rede_etapa::text, 'NULL') || ' | ' || situacao_ideb
            FROM v3 WHERE co_entidade = '35044386' AND co_etapa_ensino = 'EM')
)
SELECT n, verificacao, esperado, obtido,
       (esperado IS NOT DISTINCT FROM obtido) AS ok
FROM verificacoes
ORDER BY n;

-- -----------------------------------------------------------------------------
-- Consulta 2 - IDEB por rede e etapa (conferência visual)
-- -----------------------------------------------------------------------------
SELECT rede_administrativa, co_etapa_ensino, qt_ofertas_avaliadas, qt_ideb_divulgado,
       qt_ideb_ausente, qt_nao_divulgado_inep, qt_nao_localizado_inep,
       media_ideb, mediana_ideb, menor_ideb, maior_ideb
FROM educacao.vw_ideb_rede_etapa_2025
ORDER BY tp_dependencia, co_etapa_ensino;

-- -----------------------------------------------------------------------------
-- Consulta 3 - Jardim Macedônia (conferência visual)
-- -----------------------------------------------------------------------------
SELECT co_entidade, no_entidade, rede_administrativa, co_etapa_ensino, qt_matriculas,
       situacao_ideb, ideb_escola, media_ideb_rede_etapa, diferenca_ideb_rede_etapa
FROM educacao.vw_ideb_jardim_macedonia_2025
ORDER BY co_entidade, co_etapa_ensino;
