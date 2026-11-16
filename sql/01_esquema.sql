-- Esquema de la base de datos del termómetro de descontento.
-- Idempotente: se puede correr muchas veces sin romper nada.
-- Modelo estrella: dimensiones compartidas (fecha, tema) y hechos por fuente.

CREATE SCHEMA IF NOT EXISTS opinion;
SET search_path TO opinion;

-- ─── Dimensiones compartidas por todas las fuentes ──────────────────────────

CREATE TABLE IF NOT EXISTS dim_fecha (
    fecha            date PRIMARY KEY,
    anio             smallint NOT NULL,
    mes              smallint NOT NULL CHECK (mes BETWEEN 1 AND 12),
    semana_iso       text     NOT NULL,          -- '2026-W46'
    inicio_semana    date     NOT NULL,          -- lunes de esa semana
    dia_semana       smallint NOT NULL CHECK (dia_semana BETWEEN 1 AND 7),  -- 1 = lunes
    es_fin_de_semana boolean  NOT NULL
);

CREATE TABLE IF NOT EXISTS dim_tema (
    tema      text PRIMARY KEY,                  -- 'aysa', 'servicios_publicos'
    etiqueta  text NOT NULL,                     -- 'AySA', 'Servicios públicos'
    categoria text NOT NULL                      -- 'politica', 'servicios', 'transporte', 'estado', 'polarizacion'
);

-- ─── Bluesky ────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS bsky_post (
    post_id      text PRIMARY KEY,               -- hash de la URI: no permite llegar al autor
    fecha        date NOT NULL REFERENCES dim_fecha,  -- día argentino de la ventana de búsqueda
    creado       timestamptz,
    texto        text NOT NULL,                  -- menciones y perfiles ya enmascarados
    es_respuesta boolean NOT NULL,
    likes        integer NOT NULL DEFAULT 0 CHECK (likes >= 0),
    reposts      integer NOT NULL DEFAULT 0 CHECK (reposts >= 0),
    respuestas   integer NOT NULL DEFAULT 0 CHECK (respuestas >= 0),
    citas        integer NOT NULL DEFAULT 0 CHECK (citas >= 0),
    recolectado  timestamptz NOT NULL
);
CREATE INDEX IF NOT EXISTS bsky_post_fecha_idx ON bsky_post (fecha);

-- Un post puede tocar varios temas (relación muchos a muchos).
CREATE TABLE IF NOT EXISTS bsky_post_tema (
    post_id text NOT NULL REFERENCES bsky_post ON DELETE CASCADE,
    tema    text NOT NULL REFERENCES dim_tema,
    PRIMARY KEY (post_id, tema)
);
CREATE INDEX IF NOT EXISTS bsky_post_tema_tema_idx ON bsky_post_tema (tema);

-- Resultado del análisis de texto (pysentimiento). Un registro por post.
CREATE TABLE IF NOT EXISTS bsky_analisis (
    post_id      text PRIMARY KEY REFERENCES bsky_post ON DELETE CASCADE,
    modelo       text NOT NULL,                  -- versión del análisis, para recalcular si cambia
    texto_util   boolean NOT NULL,               -- false: vacío, solo links o demasiado corto
    sentimiento  text CHECK (sentimiento IN ('positivo', 'neutro', 'negativo')),
    p_positivo   real CHECK (p_positivo BETWEEN 0 AND 1),
    p_neutro     real CHECK (p_neutro   BETWEEN 0 AND 1),
    p_negativo   real CHECK (p_negativo BETWEEN 0 AND 1),
    emocion      text CHECK (emocion IN ('alegria', 'tristeza', 'enojo', 'miedo', 'asco', 'sorpresa', 'otra')),
    p_alegria    real, p_tristeza real, p_enojo real, p_miedo real,
    p_asco       real, p_sorpresa real, p_otra  real,
    odio         boolean,                        -- el modelo marcó 'hateful'
    p_odio       real, p_agresivo real, p_dirigido real,
    analizado    timestamptz NOT NULL,
    CHECK (texto_util = (sentimiento IS NOT NULL))
);

-- Registro de cada consulta a la API: sirve para medir cobertura y volumen total.
CREATE TABLE IF NOT EXISTS bsky_consulta (
    fecha    date    NOT NULL REFERENCES dim_fecha,
    tema     text    NOT NULL REFERENCES dim_tema,
    termino  text    NOT NULL,
    posts    integer NOT NULL CHECK (posts >= 0),
    ventanas integer NOT NULL CHECK (ventanas >= 1),
    truncada boolean NOT NULL,
    PRIMARY KEY (fecha, termino)
);

-- ─── Bitácora del ETL ───────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS etl_corrida (
    corrida_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    fuente     text NOT NULL,                    -- 'bluesky', 'suaci', 'consumo'
    paso       text NOT NULL,                    -- 'carga'
    inicio     timestamptz NOT NULL,
    fin        timestamptz,
    estado     text NOT NULL CHECK (estado IN ('en_curso', 'ok', 'error')),
    filas      jsonb,                            -- filas por tabla
    detalle    text,
    origen     text                              -- link a la corrida de GitHub Actions
);
