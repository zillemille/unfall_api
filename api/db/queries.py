# api/db/queries.py

from contextlib import contextmanager
from api.db.database import get_connection
import re

import psycopg2
from fastapi import HTTPException


# ─── Hilfsmittel ────────────────────────────────────────────────────────────

@contextmanager
def _cursor():
    """
    Context Manager: gibt einen Cursor zurück, schließt Connection sicher
    und übersetzt Datenbankfehler in aussagekräftige HTTP-Antworten.
    """
    try:
        conn = get_connection()
    except psycopg2.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Datenbankverbindung nicht verfügbar."
        )

    try:
        cur = conn.cursor()
        yield cur
        conn.commit()
    except psycopg2.OperationalError:
        raise HTTPException(
            status_code=503,
            detail="Datenbankverbindung während der Abfrage verloren."
        )
    except psycopg2.Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Datenbankfehler ({e.pgcode or 'unbekannt'}): {e.pgerror or str(e)}"
        )

    finally:
        conn.close()


def _fetchone(cur) -> any:
    row = cur.fetchone()
    return row[0] if row else None


LIZENZ_BASIS = {
    "lizenz":     "Datenlizenz Deutschland – Namensnennung – Version 2.0",
    "lizenz_id":  "dl-de/by-2-0",
    "lizenz_url": "https://www.govdata.de/dl-de/by-2-0",
    "hinweis":    "Daten wurden zusammengeführt und verändert.",
}

QUELLEN = {
    "unfallatlas":   "Statistische Ämter des Bundes und der Länder – Unfallatlas",
    "regionalatlas": "Bundesamt für Kartographie und Geodäsie – Regionalatlas",
    "genesis":       "Statistisches Bundesamt (Destatis) – Genesis-Online",
}

def get_license_note(*quellen_keys: str) -> dict:
    return {
        **LIZENZ_BASIS,
        "quellen": [QUELLEN[k] for k in quellen_keys],
    }


def validate_ags(ags_prefix: str | None) -> None:
    if ags_prefix is None:
        return
    if not re.match(r"^\d{2,8}$", ags_prefix):
        raise HTTPException(
            status_code=422,
            detail=f"Ungültiges AGS-Format '{ags_prefix}'. "
                   f"Erwartet: 2–8 Ziffern, z.B. '05' oder '14522'."
        )

def _normalize_ags_prefix(ags_prefix: str) -> str:
    """
    Normalisiert einen AGS-Präfix für LIKE-Suchen.

    Bundesland-AGS enden auf 000000 — für LIKE-Suchen müssen sie
    auf 2 Stellen gekürzt werden, da Unfälle auf Kreisebene gespeichert
    sind und nie direkt auf einen Bundesland-Eintrag zeigen.

    """

    if len(ags_prefix) == 8 and ags_prefix.endswith("000000"):
        return ags_prefix[:2]
    if len(ags_prefix) == 8 and ags_prefix.endswith("000"):
        return ags_prefix[:5]
    return ags_prefix

# ─── Einfache Abfragen ───────────────────────────────────────────────────────

def get_earliest_year(ags_prefix: str | None = None) -> int | None:
    """
    Frühestes Unfalljahr.
    - Ohne ags_prefix: global (gesamter Datensatz)
    - Mit ags_prefix:  nur für diese Region
    """
    with _cursor() as cur:
        if ags_prefix:
            cur.execute("""
                SELECT MIN(u.jahr)
                FROM unfaelle u
                JOIN regionen r ON u.region_id = r.region_id
                WHERE r.ags LIKE %(prefix)s
            """, {"prefix": f"{_normalize_ags_prefix(ags_prefix)}%"})
        else:
            cur.execute("SELECT MIN(jahr) FROM unfaelle")
        return _fetchone(cur)


def get_sources() -> list[dict]:
    """Alle Lizenz-/Quelleneinträge."""
    with _cursor() as cur:
        cur.execute("""
            SELECT quelle, lizenz_name, lizenz_url, abgerufen_am
            FROM lizenzen
            ORDER BY quelle
        """)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_import_runs() -> list[dict]:
    """Import-Protokoll, neueste zuerst."""
    with _cursor() as cur:
        cur.execute("""
            SELECT log_id, quelle, gestartet_am, beendet_am,
                   status, verarbeitet, hinzugef, verworfen, hinweis
            FROM import_log
            ORDER BY gestartet_am DESC
        """)
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def search_regions(
    name: str | None = None,
    level: str | None = None,
    ags_prefix: str | None = None,
) -> list[dict]:
    """
    Regionen suchen — Brücke zwischen Name und AGS.
    Unterstützt Teilstring-Suche (ILIKE) für Autocomplete.
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT
                region_id,
                ags,
                LEFT(ags, 2)  AS ags_prefix,
                name,
                level,
                parent_ags
            FROM regionen
            WHERE (%(name)s      IS NULL OR name  ILIKE %(name_pattern)s)
              AND (%(level)s     IS NULL OR level = %(level)s)
              AND (%(ags_prefix)s IS NULL OR ags  LIKE %(ags_pattern)s)
            ORDER BY
                CASE level
                    WHEN 'bundesland' THEN 1
                    WHEN 'kreis'      THEN 2
                    ELSE 3
                END,
                name
            LIMIT 20
        """, {
            "name":         name,
            "name_pattern": f"%{name}%" if name else None,
            "level":        level,
            "ags_prefix":   ags_prefix,
            "ags_pattern":  f"{ags_prefix}%" if ags_prefix else None,
        })
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─── Regions-Abfragen ──────────────────

def get_accident_count(
    ags_prefix: str,
    year: int,
    kategorien: list[int] | None = None,
    monat: int | None = None,
    stunde: int | None = None,
    ist_rad: bool | None = None,
    ist_fuss: bool | None = None,
    ist_pkw: bool | None = None,
    ist_kraftrad: bool | None = None,
) -> int:
    with _cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
              AND u.jahr = %(year)s
              AND (%(kategorien)s IS NULL OR u.kategorie = ANY(%(kategorien)s))
              AND (%(monat)s        IS NULL OR u.monat        = %(monat)s)
              AND (%(stunde)s       IS NULL OR u.stunde       = %(stunde)s)
              AND (%(ist_rad)s      IS NULL OR u.ist_rad      = %(ist_rad)s)
              AND (%(ist_fuss)s     IS NULL OR u.ist_fuss     = %(ist_fuss)s)
              AND (%(ist_pkw)s      IS NULL OR u.ist_pkw      = %(ist_pkw)s)
              AND (%(ist_kraftrad)s IS NULL OR u.ist_kraftrad = %(ist_kraftrad)s)
        """, {
            "prefix": f"{_normalize_ags_prefix(ags_prefix)}%", "year": year,
            "kategorien": kategorien, "monat": monat, "stunde": stunde,
            "ist_rad": ist_rad, "ist_fuss": ist_fuss,
            "ist_pkw": ist_pkw, "ist_kraftrad": ist_kraftrad,
        })
        return _fetchone(cur) or 0


def get_available_years(ags_prefix: str) -> list[int]:
    """
    Verfügbare Datenjahre für ein Bundesland.
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT DISTINCT u.jahr
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
              AND u.jahr IS NOT NULL
            ORDER BY u.jahr
        """, {"prefix": f"{_normalize_ags_prefix(ags_prefix)}%"})
        return [row[0] for row in cur.fetchall()]


def get_pedestrian_accidents(ags_prefix: str, year: int) -> int:
    with _cursor() as cur:
        cur.execute("""
            SELECT COUNT(*)
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
              AND u.jahr     = %(year)s
              AND u.ist_fuss = TRUE
        """, {"prefix": f"{_normalize_ags_prefix(ags_prefix)}%", "year": year})
        return _fetchone(cur) or 0


def get_accident_aggregates(
    level: str,
    year: int,
    kategorie: int | None = None,
) -> list[dict]:
    if level not in ("bundesland", "kreis"):
        raise ValueError(f"Ungültiger Level: {level!r}")

    with _cursor() as cur:

        if level == "bundesland":
            cur.execute("""
                SELECT
                    bl.ags,
                    bl.name,
                    COUNT(u.unfall_id) AS unfaelle
                FROM regionen bl
                JOIN regionen kr
                    ON kr.ags LIKE (LEFT(bl.ags, 2) || '%%')
                    AND kr.level = 'kreis'
                JOIN unfaelle u
                    ON u.region_id = kr.region_id
                    AND u.jahr     = %(year)s
                    AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
                WHERE bl.level = 'bundesland'
                GROUP BY bl.ags, bl.name
                ORDER BY unfaelle DESC
            """, {"year": year, "kat": kategorie})

        else:
            cur.execute("""
                SELECT
                    r.ags,
                    r.name,
                    COUNT(u.unfall_id) AS unfaelle
                FROM unfaelle u
                JOIN regionen r ON u.region_id = r.region_id
                WHERE u.jahr  = %(year)s
                  AND r.level = 'kreis'
                  AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
                GROUP BY r.ags, r.name
                ORDER BY unfaelle DESC
            """, {"year": year, "kat": kategorie})

        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


# ─── Multi-Source-Abfragen ───────────────────────────────────────────────────

def get_per_capita(ags_prefix: str, year: int) -> tuple[float, int] | None:
    with _cursor() as cur:

        cur.execute("""
            SELECT b.jahr, b.einwohner
            FROM bevoelkerung b
            JOIN regionen r ON b.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
            ORDER BY ABS(b.jahr - %(year)s)
            LIMIT 1
        """, {"prefix": f"{_normalize_ags_prefix(ags_prefix)}%", "year": year})

        bev_row = cur.fetchone()
        if not bev_row:
            return None
        bev_jahr, einwohner = bev_row

        cur.execute("""
            SELECT COUNT(u.unfall_id)
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
              AND u.jahr = %(year)s
        """, {"prefix": f"{_normalize_ags_prefix(ags_prefix)}%", "year": year})

        unfall_count = cur.fetchone()[0]
        if einwohner == 0:
            return None

        return round(unfall_count * 100000 / einwohner, 1), bev_jahr


def get_accident_density(year: int, level: str = "kreis") -> list[dict]:
    with _cursor() as cur:

        if level == "bundesland":
            cur.execute("""
                SELECT
                    bl.name,
                    COUNT(u.unfall_id)                                        AS unfaelle,
                    ROUND(
                        ST_Area(bl.geometrie::geography)::numeric / 1e6, 1
                    )                                                         AS flaeche_km2,
                    ROUND(
                        COUNT(u.unfall_id)::numeric
                        / NULLIF(
                            ST_Area(bl.geometrie::geography)::numeric / 1e6,
                          0),
                        3
                    )                                                         AS unfaelle_pro_km2
                FROM regionen bl                          
                JOIN regionen kr                          
                    ON kr.ags LIKE (LEFT(bl.ags, 2) || '%%')
                    AND kr.level = 'kreis'
                JOIN unfaelle u
                    ON u.region_id = kr.region_id
                    AND u.jahr     = %(year)s
                WHERE bl.level = 'bundesland'
                GROUP BY bl.region_id, bl.name, bl.geometrie
                ORDER BY unfaelle_pro_km2 DESC
            """, {"year": year})

        else:
            cur.execute("""
                SELECT
                    r.name,
                    COUNT(u.unfall_id)                                        AS unfaelle,
                    ROUND(
                        ST_Area(r.geometrie::geography)::numeric / 1e6, 1
                    )                                                         AS flaeche_km2,
                    ROUND(
                        COUNT(u.unfall_id)::numeric
                        / NULLIF(
                            ST_Area(r.geometrie::geography)::numeric / 1e6,
                          0),
                        3
                    )                                                         AS unfaelle_pro_km2
                FROM unfaelle u
                JOIN regionen r ON u.region_id = r.region_id
                WHERE u.jahr  = %(year)s
                  AND r.level = 'kreis'
                GROUP BY r.region_id, r.name, r.geometrie
                ORDER BY unfaelle_pro_km2 DESC
            """, {"year": year})

        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]




def get_trend(
    ags_prefix: str,
    von_jahr: int,
    bis_jahr: int,
    kategorie: int | None = None,
) -> list[dict]:
    """
    Jahresübergreifende Unfallzahlen — Basis für Trendanalyse.
    Gibt pro Jahr die Anzahl zurück, sodass der Client die Veränderung berechnen kann.
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT
                u.jahr,
                COUNT(*)            AS unfaelle,
                COUNT(*) - LAG(COUNT(*)) OVER (ORDER BY u.jahr)
                                    AS veraenderung_zum_vorjahr
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags LIKE %(prefix)s
              AND u.jahr BETWEEN %(von)s AND %(bis)s
              AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
            GROUP BY u.jahr
            ORDER BY u.jahr
        """, {
            "prefix": f"{_normalize_ags_prefix(ags_prefix)}%",
            "von":    von_jahr,
            "bis":    bis_jahr,
            "kat":    kategorie,
        })
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_top_regions(
    level: str,
    year: int,
    kategorie: int | None = None,
        limit: int = 5,
    ags_prefix: str | None = None,
) -> list[dict]:
    """
    Top-N Regionen nach Unfallzahl.
    Beispiel: 5 schlimmste Landkreise mit Todesunfällen 2024.
    ags_prefix="14" → nur Sachsen.
    """
    with _cursor() as cur:
        if level == "bundesland":
            cur.execute("""
                        SELECT bl.ags,
                               bl.name,
                               COUNT(u.unfall_id) AS unfaelle
                        FROM regionen bl
                                 JOIN regionen kr
                                      ON kr.ags LIKE (LEFT(bl.ags, 2) || '%%')
                                          AND kr.level = 'kreis'
                                 JOIN unfaelle u
                                      ON u.region_id = kr.region_id
                                          AND u.jahr = %(year)s
                                          AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
                        WHERE bl.level = 'bundesland'
                        GROUP BY bl.ags, bl.name
                        ORDER BY unfaelle DESC
                            LIMIT %(limit)s
                        """, {"year": year, "kat": kategorie, "limit": limit})
        else:
            cur.execute("""
                        SELECT r.ags,
                               r.name,
                               COUNT(u.unfall_id) AS unfaelle
                        FROM unfaelle u
                                 JOIN regionen r ON u.region_id = r.region_id
                        WHERE u.jahr = %(year)s
                          AND r.level = 'kreis'
                          AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
                          AND (%(ags_prefix)s IS NULL OR r.ags LIKE %(ags_prefix)s)
                        GROUP BY r.ags, r.name
                        ORDER BY unfaelle DESC
                            LIMIT %(limit)s
                        """, {"year": year, "kat": kategorie,
                              "ags_prefix": f"{_normalize_ags_prefix(ags_prefix)}%" if ags_prefix else None,
                              "limit": limit})
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_zero_accident_regions(
    year: int,
    ags_prefix: str,
    level: str = "kreis",
) -> list[dict]:
    if level == "bundesland":
        raise ValueError(
            "level='bundesland' nicht unterstützt — Unfälle liegen auf Kreisebene. "
            "Verwende level='kreis'."
        )
    with _cursor() as cur:
        cur.execute("""
            SELECT r.ags, r.name
            FROM regionen r
            LEFT JOIN unfaelle u
                ON  u.region_id = r.region_id
                AND u.jahr      = %(year)s
            WHERE r.level = %(level)s
              AND r.ags   LIKE %(prefix)s
              AND u.unfall_id IS NULL
            ORDER BY r.name
        """, {"year": year, "level": level, "prefix": f"{_normalize_ags_prefix(ags_prefix)}%"})
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_map_region(
        ags_prefix: str
) -> list[dict]:
    with _cursor() as cur:
        cur.execute("""
            SELECT ST_AsGeoJSON(geometrie) AS geojson,
                   name
            FROM regionen
            WHERE ags LIKE %(ags)s
            ORDER BY name
            """, {"ags": f"{_normalize_ags_prefix(ags_prefix)}%"})
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


def get_accident_points(
    ags_prefix: str,
    year: int,
    kategorie: int | None = None,
    limit: int = 5000,
) -> list[dict]:
    """
    Gibt Unfallkoordinaten für eine Region zurück.
    Nur Unfälle mit gesetzter Geometrie werden zurückgegeben.
    """
    with _cursor() as cur:
        cur.execute("""
            SELECT
                ST_Y(u.geom) AS lat,
                ST_X(u.geom) AS lon,
                u.kategorie,
                u.ist_rad,
                u.ist_fuss,
                u.ist_pkw
            FROM unfaelle u
            JOIN regionen r ON u.region_id = r.region_id
            WHERE r.ags    LIKE %(prefix)s
              AND u.jahr   = %(year)s
              AND u.geom   IS NOT NULL
              AND (%(kat)s IS NULL OR u.kategorie = %(kat)s)
            LIMIT %(limit)s
        """, {
            "prefix": f"{_normalize_ags_prefix(ags_prefix)}%",
            "year":   year,
            "kat":    kategorie,
            "limit":  limit,
        })
        cols = [d.name for d in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]
