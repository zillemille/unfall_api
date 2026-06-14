# DBW Projekt

## Projekt klonen

```bash
git clone <REPOSITORY_URL>
cd dbw_projekt
```

---

## Voraussetzungen

- Docker Desktop (läuft im Hintergrund)
- Python 3.12+

---
## Datenbeschaffung

- aus regionalatlas, unfallatlas und genesis alle csv's herunterladen, die man will
- in jeweilige Ordner unter ./data legen (Namensgebung egal, da automatisch eingelesen)
---

## Datenbank starten

```bash
docker compose up -d
```

Prüfen ob der Container läuft:

```bash
docker ps
```

---

## Python-Umgebung einrichten

```bash
python3 -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

---

## Daten importieren

Alle ETL-Schritte werden über ein zentrales Skript ausgeführt.
Die Reihenfolge ist fest vorgegeben — Regionalatlas muss vor dem
Unfallatlas importiert werden, da Unfälle per räumlichem Join
den Regionen zugeordnet werden.

```bash
python -m data.etl.main
```

Die Schritte im Überblick:

| Schritt | Quelle | Beschreibung |
|---|---|---|
| 1 | Regionalatlas | Bundesländer und Landkreise mit Geometrien |
| 2 | Unfallatlas | Unfalldaten inkl. räumlicher Zuordnung (`region_id`) |
| 3 | GENESIS | Bevölkerungsdaten je Region und Jahr |
| 4 | Checks | Plausibilitätsprüfungen nach dem Import |

Den Importstatus einsehen:

```bash
docker exec -it dbw_projekt-db-1 psql -U dbw_user -d dbw_db \
  -c "SELECT quelle, status, verarbeitet, hinzugef, verworfen, beendet_am FROM import_log ORDER BY beendet_am DESC;"
```

---

## API starten

```bash
uvicorn api.main:app --reload
```

Die API ist erreichbar unter:

| URL | Beschreibung |
|---|---|
| `http://localhost:8000` | API-Root |
| `http://localhost:8000/docs` | Swagger UI (interaktive Dokumentation) |
| `http://localhost:8000/redoc` | ReDoc-Dokumentation |

---

## Beispielabfragen

```bash
# Frühestes Unfalljahr gesamt
curl "http://localhost:8000/accidents/earliest"

# Frühestes Jahr für NRW
curl "http://localhost:8000/accidents/earliest?ags_prefix=05"

# Unfälle mit Personenschäden 2023 in Sachsen
curl "http://localhost:8000/accidents/count?ags_prefix=14&year=2023&kategorien=1&kategorien=2&kategorien=3"

# Fußgängerunfälle 2023 in Berlin
curl "http://localhost:8000/accidents/pedestrian?region=Berlin&year=2023"

# Unfälle je 100.000 Einwohner in Sachsen 2024
curl "http://localhost:8000/accidents/per-capita?region=Sachsen&year=2024"

# Top 5 Landkreise mit Todesunfällen 2024
curl "http://localhost:8000/accidents/top?level=kreis&year=2024&kategorie=1&limit=5"
```

---

## Datenbank direkt abfragen

```bash
docker exec -it dbw_projekt-db-1 psql -U dbw_user -d dbw_db
```

```sql
-- Überblick
\dt

-- Datenmengen prüfen
SELECT COUNT(*) FROM unfaelle;
SELECT COUNT(*) FROM regionen;
SELECT COUNT(*) FROM bevoelkerung;

-- Unfälle ohne region_id (sollte 0 sein nach erfolgreichem Import)
SELECT COUNT(*) FROM unfaelle WHERE region_id IS NULL;

-- Unfälle ohne Geometrie (sollte 0 sein)
SELECT COUNT(*) FROM unfaelle WHERE geom IS NULL;
```

---

## Container stoppen

```bash
docker compose down
```

Datenbank-Volume ebenfalls löschen (setzt alle Daten zurück):

```bash
docker compose down -v
```