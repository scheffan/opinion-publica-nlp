-- Vistas que lee Grafana. Toda la lógica de métricas vive acá, no en el tablero,
-- para que cualquier número del tablero se pueda reproducir con una consulta SQL.
SET search_path TO opinion;

-- Intervalo de confianza de Wilson al 95 % para una proporción k/n.
-- Más confiable que p ± 1,96·√(p(1-p)/n) cuando n es chico o p está cerca de 0 o 1.
CREATE OR REPLACE FUNCTION wilson(k bigint, n bigint, extremo text)
RETURNS double precision LANGUAGE sql IMMUTABLE AS $$
    SELECT CASE WHEN n = 0 THEN NULL ELSE
        (p + z*z/(2*n) + CASE extremo WHEN 'sup' THEN 1 ELSE -1 END
             * z * sqrt(p*(1-p)/n + z*z/(4.0*n*n))) / (1 + z*z/n)
    END
    FROM (SELECT k::double precision / NULLIF(n, 0) AS p, 1.96::double precision AS z) c
$$;

-- Semanas completas: excluye la semana en curso (hora argentina).
CREATE OR REPLACE VIEW v_semana_completa AS
SELECT DISTINCT semana_iso, inicio_semana
FROM dim_fecha
WHERE inicio_semana + 7 <= (now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date;

-- Métrica principal: % de posts negativos por tema y semana, con margen de error.
CREATE OR REPLACE VIEW v_bsky_semanal_tema AS
WITH base AS (
    SELECT f.semana_iso, f.inicio_semana, pt.tema, a.texto_util, a.sentimiento, a.odio
    FROM bsky_post p
    JOIN bsky_post_tema pt USING (post_id)
    JOIN dim_fecha f USING (fecha)
    LEFT JOIN bsky_analisis a USING (post_id)
    JOIN v_semana_completa USING (semana_iso, inicio_semana)
), agregado AS (
    SELECT semana_iso, inicio_semana, tema,
           count(*)                                          AS posts,
           count(*) FILTER (WHERE texto_util)                AS posts_utiles,
           count(*) FILTER (WHERE sentimiento = 'negativo')  AS negativos,
           count(*) FILTER (WHERE sentimiento = 'positivo')  AS positivos,
           count(*) FILTER (WHERE odio)                      AS con_odio
    FROM base GROUP BY 1, 2, 3
), total_semana AS (
    -- Volumen total recolectado en la semana (todos los temas), para normalizar.
    SELECT f.semana_iso, count(DISTINCT p.post_id) AS posts_semana
    FROM bsky_post p JOIN dim_fecha f USING (fecha) GROUP BY 1
)
SELECT a.semana_iso, a.inicio_semana, a.tema, t.etiqueta, t.categoria,
       a.posts, a.posts_utiles,
       round(100.0 * a.posts / s.posts_semana, 2)                      AS pct_del_volumen,
       round(100.0 * a.negativos / NULLIF(a.posts_utiles, 0), 1)       AS pct_negativo,
       round(100 * wilson(a.negativos, a.posts_utiles, 'inf')::numeric, 1) AS pct_negativo_ic_inf,
       round(100 * wilson(a.negativos, a.posts_utiles, 'sup')::numeric, 1) AS pct_negativo_ic_sup,
       round(100.0 * a.positivos / NULLIF(a.posts_utiles, 0), 1)       AS pct_positivo,
       round(100.0 * a.con_odio / NULLIF(a.posts_utiles, 0), 1)        AS pct_odio,
       a.posts_utiles < 30                                             AS poca_muestra
FROM agregado a
JOIN dim_tema t USING (tema)
JOIN total_semana s USING (semana_iso);

-- Distribución de emociones por tema y semana (sobre posts útiles).
CREATE OR REPLACE VIEW v_bsky_emociones_semanal AS
SELECT f.semana_iso, f.inicio_semana, pt.tema, a.emocion,
       count(*) AS posts,
       round(100.0 * count(*) / sum(count(*)) OVER (PARTITION BY f.semana_iso, pt.tema), 1) AS pct
FROM bsky_post p
JOIN bsky_post_tema pt USING (post_id)
JOIN bsky_analisis a USING (post_id)
JOIN dim_fecha f USING (fecha)
JOIN v_semana_completa USING (semana_iso, inicio_semana)
WHERE a.texto_util
GROUP BY 1, 2, 3, 4;

-- Cobertura de la recolección: días sin consulta o con ventanas truncadas.
CREATE OR REPLACE VIEW v_bsky_cobertura AS
SELECT f.semana_iso,
       count(DISTINCT c.fecha)             AS dias_con_datos,
       count(*) FILTER (WHERE c.truncada)  AS consultas_truncadas,
       sum(c.posts)                        AS posts_reportados_api
FROM dim_fecha f
LEFT JOIN bsky_consulta c USING (fecha)
WHERE f.fecha <= (SELECT max(fecha) FROM bsky_consulta)
  AND f.fecha >= (SELECT min(fecha) FROM bsky_consulta)
GROUP BY 1;

-- Misma métrica por mes: para temas chicos (AySA, servicios, Jorge Macri) la
-- semana casi nunca llega a 30 posts útiles; el mes sí.
CREATE OR REPLACE VIEW v_bsky_mensual_tema AS
WITH base AS (
    SELECT date_trunc('month', p.fecha)::date AS mes, pt.tema, a.texto_util, a.sentimiento, a.odio
    FROM bsky_post p
    JOIN bsky_post_tema pt USING (post_id)
    LEFT JOIN bsky_analisis a USING (post_id)
    WHERE p.fecha < date_trunc('month', now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
), agregado AS (
    SELECT mes, tema,
           count(*)                                         AS posts,
           count(*) FILTER (WHERE texto_util)               AS posts_utiles,
           count(*) FILTER (WHERE sentimiento = 'negativo') AS negativos,
           count(*) FILTER (WHERE odio)                     AS con_odio
    FROM base GROUP BY 1, 2
)
SELECT a.mes, a.tema, t.etiqueta, t.categoria, a.posts, a.posts_utiles,
       round(100.0 * a.negativos / NULLIF(a.posts_utiles, 0), 1)           AS pct_negativo,
       round(100 * wilson(a.negativos, a.posts_utiles, 'inf')::numeric, 1) AS pct_negativo_ic_inf,
       round(100 * wilson(a.negativos, a.posts_utiles, 'sup')::numeric, 1) AS pct_negativo_ic_sup,
       round(100.0 * a.con_odio / NULLIF(a.posts_utiles, 0), 1)            AS pct_odio,
       a.posts_utiles < 30                                                 AS poca_muestra
FROM agregado a JOIN dim_tema t USING (tema);

-- ─── Vistas extra para el tablero ──────────────────────────────────────────

-- Conteos por mes y tema (además de los porcentajes de v_bsky_mensual_tema),
-- para poder sumar varios meses sin promediar porcentajes.
CREATE OR REPLACE VIEW v_bsky_mensual_conteos AS
SELECT date_trunc('month', p.fecha)::date AS mes, pt.tema, t.etiqueta,
       count(*)                                           AS posts,
       count(*) FILTER (WHERE a.texto_util)               AS posts_utiles,
       count(*) FILTER (WHERE a.sentimiento = 'negativo') AS negativos,
       count(*) FILTER (WHERE a.odio)                     AS con_odio
FROM bsky_post p
JOIN bsky_post_tema pt USING (post_id)
JOIN dim_tema t USING (tema)
LEFT JOIN bsky_analisis a USING (post_id)
WHERE p.fecha < date_trunc('month', now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
GROUP BY 1, 2, 3;

-- Emociones por mes y tema (sobre posts útiles).
CREATE OR REPLACE VIEW v_bsky_emociones_mensual AS
SELECT date_trunc('month', p.fecha)::date AS mes, pt.tema, t.etiqueta, a.emocion, count(*) AS posts
FROM bsky_post p
JOIN bsky_post_tema pt USING (post_id)
JOIN dim_tema t USING (tema)
JOIN bsky_analisis a USING (post_id)
WHERE a.texto_util
  AND p.fecha < date_trunc('month', now() AT TIME ZONE 'America/Argentina/Buenos_Aires')::date
GROUP BY 1, 2, 3, 4;

-- Números generales y estado del ETL, para el encabezado del tablero.
CREATE OR REPLACE VIEW v_bsky_resumen AS
SELECT (SELECT count(*) FROM bsky_post)                               AS posts,
       (SELECT count(*) FROM bsky_analisis WHERE texto_util)          AS posts_utiles,
       (SELECT min(fecha) FROM bsky_post)                             AS desde,
       (SELECT max(fecha) FROM bsky_post)                             AS hasta,
       (SELECT max(fin) FROM etl_corrida WHERE estado = 'ok')         AS ultima_carga,
       (SELECT count(*) FROM bsky_consulta WHERE truncada)            AS consultas_truncadas;
