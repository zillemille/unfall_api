# DBW Projekt

## Projekt klonen

```bash
git clone <REPOSITORY_URL>
cd dbw_projekt
```

---

## Docker starten

Stelle sicher, dass Docker Desktop läuft.

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

## Python-Umgebung erstellen

```bash
python3 -m venv .venv
source .venv/bin/activate
```

---

## Abhängigkeiten installieren

```bash
pip install -r requirements.txt
```

---

## Unfallatlas-ETL ausführen

```bash
python etl/unfallatlas.py
```

---

## Regionalatlas-ETL ausführen

```bash
python etl/regionalatlas.py
```

---

## Datenbank testen

Mit PostgreSQL verbinden:

```bash
docker exec -it dbw_projekt-db-1 psql -U dbw_user -d dbw_db
```

Tabellen anzeigen:

```sql
\dt
```

Beispielabfrage:

```sql
SELECT COUNT(*) FROM unfaelle;

SELECT COUNT(*) FROM regionen;
```

---

## Container stoppen

```bash
docker compose down
```
