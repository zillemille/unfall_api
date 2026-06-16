CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS regionen (
    region_id     SERIAL PRIMARY KEY,
    ags           VARCHAR(8) UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    level         VARCHAR(20) NOT NULL,
    parent_ags    VARCHAR(8),
    geometrie     GEOMETRY(MULTIPOLYGON, 4326)
);
ALTER TABLE regionen DROP CONSTRAINT regionen_ags_key;
ALTER TABLE regionen ADD CONSTRAINT regionen_ags_level_key UNIQUE (ags, level);

CREATE INDEX IF NOT EXISTS idx_regionen_geom ON regionen USING GIST (geometrie);
CREATE INDEX IF NOT EXISTS idx_regionen_ags  ON regionen (ags);

CREATE TABLE IF NOT EXISTS unfaelle (
    unfall_id     SERIAL PRIMARY KEY,

    extern_id     TEXT UNIQUE NOT NULL,

    jahr          INT,
    monat         INT,
    stunde        INT,

    bundesland    INT,
    regierungsbezirk INT,
    kreis         INT,
    gemeinde      INT,

    kategorie     INT,
    typ           INT,

    ist_rad       BOOLEAN,
    ist_fuss      BOOLEAN,
    ist_pkw       BOOLEAN,
    ist_kraftrad  BOOLEAN,

    lon           DOUBLE PRECISION,
    lat           DOUBLE PRECISION,

    geom          GEOMETRY(POINT, 4326),

    region_id     INT REFERENCES regionen(region_id),

    importiert_am TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_unfaelle_region ON unfaelle (region_id);
CREATE INDEX IF NOT EXISTS idx_unfaelle_jahr   ON unfaelle (jahr);
CREATE INDEX IF NOT EXISTS idx_unfaelle_geom   ON unfaelle USING GIST (geom);

CREATE TABLE IF NOT EXISTS bevoelkerung (
    bev_id        SERIAL PRIMARY KEY,
    region_id     INT REFERENCES regionen(region_id),
    jahr          INT,
    einwohner     INT,
    UNIQUE (region_id, jahr)
);

CREATE TABLE IF NOT EXISTS import_log (
    log_id        SERIAL PRIMARY KEY,
    quelle        TEXT,
    gestartet_am  TIMESTAMP DEFAULT NOW(),
    beendet_am    TIMESTAMP,
    status        TEXT,
    verarbeitet    INT,
    hinzugef      INT,
    verworfen     INT,
    hinweis       TEXT
);

CREATE TABLE IF NOT EXISTS lizenzen (
    lizenz_id     SERIAL PRIMARY KEY,
    quelle        TEXT UNIQUE,
    lizenz_name   TEXT,
    lizenz_url    TEXT,
    abgerufen_am  DATE
);

-- scripts/init_db.sql — am Ende ergänzen

INSERT INTO lizenzen (quelle, lizenz_name, lizenz_url, abgerufen_am)
VALUES
(
    'Unfallatlas – Statistische Ämter des Bundes und der Länder',
    'Datenlizenz Deutschland – Namensnennung – Version 2.0',
    'https://www.govdata.de/dl-de/by-2-0',
    '2025-01-01'
),
(
    'Regionalatlas – Bundesamt für Kartographie und Geodäsie (BKG)',
    'Datenlizenz Deutschland – Namensnennung – Version 2.0',
    'https://www.govdata.de/dl-de/by-2-0',
    '2025-01-01'
),
(
    'Genesis-Online – Statistisches Bundesamt (Destatis)',
    'Datenlizenz Deutschland – Namensnennung – Version 2.0',
    'https://www.govdata.de/dl-de/by-2-0',
    '2025-01-01'
)
ON CONFLICT (quelle) DO NOTHING;
