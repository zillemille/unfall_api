# DBW Projekt — Unfallatlas API

REST-API und Dashboard zur Analyse von Verkehrsunfalldaten auf Basis des
Unfallatlas (Destatis), angereichert mit Regionsdaten und Bevölkerungsstatistiken.

---

## Projektstruktur

```
dbw_projekt/
├── api/                        # FastAPI-Anwendung
│   ├── db/
│   │   ├── database.py         # Datenbankverbindung
│   │   └── queries.py          # SQL-Abfragen
│   ├── models/
│   │   └── response.py         # Pydantic-Antwortmodelle
│   ├── routers/
│   │   ├── unfaelle.py         # /accidents Endpunkte
│   │   ├── regionen.py         # /regions Endpunkte
│   │   ├── metadata.py         # /sources, /imports
│   │   └── map.py              # /map Endpunkte
│   └── main.py                 # FastAPI App
├── dashboard/                  # Streamlit-Client
│   ├── app.py
│   └── Dockerfile
├── data/
│   ├── const/
│   │   └── constants.py        # DB-Konfiguration
│   ├── etl/                    # Import-Skripte
│   │   ├── main.py             # Zentraler ETL-Einstiegspunkt
│   │   ├── regionalatlas.py    # Regionen + Geometrien
│   │   ├── unfallatlas.py      # Unfalldaten + Georeferenzierung
│   │   ├── genesis_bl.py       # Bevölkerung Bundesländer
│   │   ├── genesis_kreis.py    # Bevölkerung Kreise
│   │   └── checks.py           # Plausibilitätsprüfungen
│   ├── genesis/                # Bevölkerungsdaten (CSV)
│   ├── regionalatlas/          # Geodaten (GeoJSON)
│   └── unfallatlas/            # Unfalldaten (CSV, mehrere Jahre)
├── scripts/
│   └── init_db.sql             # Datenbankschema
├── Dockerfile                  # Image für API + ETL
├── docker-compose.yml
└── requirements.txt
```

---

## Voraussetzungen

- Docker Desktop
- Python 3.12+ (nur für lokale Entwicklung)

---

## Quickstart mit Docker

### 1. Images bauen

```bash
docker compose build
```

### 2. Datenbank, API und Dashboard starten

```bash
docker compose up -d db api dashboard
```

### 3. Daten importieren

```bash
docker compose run --rm etl
```

Fertig. Die Anwendung ist erreichbar unter:

| URL | Beschreibung |
|---|---|
| `http://localhost:8501` | Streamlit-Dashboard |
| `http://localhost:8000/docs` | Swagger UI |
| `http://localhost:8000/redoc` | ReDoc |

---

## Lokale Entwicklung (ohne Docker, unwichtig für Bewertung)

### Umgebung einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### Datenbank starten

```bash
docker compose up -d db
```

### ETL ausführen

```bash
python -m data.etl.main
```

### API starten

```bash
uvicorn api.main:app --reload
```

### Dashboard starten

```bash
streamlit run dashboard/app.py
```

---

## Neue Unfalldaten importieren

CSV-Dateien aus dem Unfallatlas (Destatis) in den Ordner legen:

```
data/unfallatlas/Unfallorte2025_LinRef.csv
```

ETL erneut ausführen — bereits vorhandene Datensätze werden automatisch
übersprungen (`ON CONFLICT DO NOTHING`):

```bash
# Docker
docker compose run --rm etl

# Lokal
python -m data.etl.main
```

---

## ETL-Reihenfolge

Die Reihenfolge ist fest vorgegeben und wird von `data/etl/main.py` gesteuert:

| Schritt | Skript | Beschreibung |
|---|---|---|
| 1 | `regionalatlas.py` | Bundesländer und Kreise mit Geometrien |
| 2 | `unfallatlas.py` | Unfalldaten, Geometrien und `region_id` setzen |
| 3 | `genesis_bl.py` | Bevölkerungsdaten Bundesländer |
| 4 | `genesis_kreis.py` | Bevölkerungsdaten Kreise |
| 5 | `checks.py` | Plausibilitätsprüfungen |

Regionalatlas muss vor dem Unfallatlas laufen, da Unfälle per räumlichem
Join (`ST_Within`) den Regionen zugeordnet werden.

---

## API-Endpunkte

### Unfälle `/accidents`

| Endpunkt | Beschreibung |
|---|---|
| `GET /accidents/earliest` | Frühestes Datenjahr (optional je Bundesland) |
| `GET /accidents/count` | Unfallanzahl mit Filtern (Jahr, Kategorie, Beteiligte) |
| `GET /accidents/years` | Verfügbare Datenjahre je Region |
| `GET /accidents/pedestrian` | Fußgängerunfälle je Region und Jahr |
| `GET /accidents/aggregates` | Unfälle gruppiert nach Bundesland oder Kreis |
| `GET /accidents/top` | Top-N Regionen nach Unfallzahl |
| `GET /accidents/trend` | Jahrestrend mit Veränderung zum Vorjahr |
| `GET /accidents/per-capita` | Unfälle je 100.000 Einwohner |
| `GET /accidents/density` | Unfälle je km² (PostGIS) |
| `GET /accidents/zero-accidents` | Kreise ohne Unfälle in einem Jahr |

### Regionen `/regions`

| Endpunkt | Beschreibung |
|---|---|
| `GET /regions` | Regionen suchen (Name, Level, AGS-Präfix) |

### AGS-Präfixe wichtiger Bundesländer

| Bundesland | AGS-Präfix |
|---|---|
| Schleswig-Holstein | `01` |
| Hamburg | `02` |
| Bremen | `04` |
| Nordrhein-Westfalen | `05` |
| Berlin | `11` |
| Mecklenburg-Vorpommern | `13` |
| Sachsen | `14` |
| Bayern | `09` |

---

## Pflichtfragen — Beispielabfragen

```bash
# Frühestes Unfalljahr gesamt
curl "http://localhost:8000/accidents/earliest"

# Ab welchem Jahr sind Daten für NRW verfügbar?
curl "http://localhost:8000/accidents/earliest?ags_prefix=05"

# Ab welchem Jahr sind Daten für Mecklenburg-Vorpommern verfügbar?
curl "http://localhost:8000/accidents/earliest?ags_prefix=13"

# Unfälle mit Personenschäden 2023 in Sachsen (Kategorien 1+2+3)
curl "http://localhost:8000/accidents/count?ags_prefix=14&year=2023&kategorien=1&kategorien=2&kategorien=3"

# Fußgängerunfälle 2023 in Berlin
curl "http://localhost:8000/accidents/count?ags_prefix=11&year=2023&ist_fuss=true"

# Unfälle je 100.000 Einwohner in Sachsen 2024
curl "http://localhost:8000/accidents/per-capita?ags_prefix=14&year=2024"

# Unfalldichte je km² nach Kreis 2024
curl "http://localhost:8000/accidents/density?year=2024&level=kreis"
```

---

## Datenbank direkt abfragen

```bash
docker exec -it dbw_projekt-db-1 psql -U dbw_user -d dbw_db
```

```sql
-- Überblick
\dt

-- Datenmengen
SELECT COUNT(*) FROM unfaelle;
SELECT COUNT(*) FROM regionen;
SELECT COUNT(*) FROM bevoelkerung;

-- Importstatus
SELECT quelle, status, verarbeitet, hinzugef, verworfen, beendet_am
FROM import_log
ORDER BY beendet_am DESC;

-- Qualitätsprüfung
SELECT COUNT(*) FROM unfaelle WHERE region_id IS NULL;
SELECT COUNT(*) FROM unfaelle WHERE geom IS NULL;
```

---

## Docker-Befehle

```bash
# Alles starten
docker compose up -d

# Stoppen
docker compose down

# Alles zurücksetzen (Datenbank leeren)
docker compose down -v
docker compose up -d db api dashboard
docker compose run --rm etl

# Logs
docker compose logs -f api
docker compose logs -f etl

# Neu bauen (nach Codeänderungen)
docker compose build
docker compose up -d --build
```

---

## API-Dokumentation exportieren

```bash
curl http://localhost:8000/openapi.json -o openapi.json
```