from api.db.database import get_connection


def get_earliest_year():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT MIN(jahr)
        FROM unfaelle
    """)

    result = cursor.fetchone()[0]

    conn.close()

    return result


def get_accident_count(state: str, year: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM unfaelle
        WHERE bundesland = %s
          AND jahr = %s
    """, (state, year))

    result = cursor.fetchone()[0]

    conn.close()

    return result


def get_available_years(state: str):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT DISTINCT jahr
        FROM unfaelle
        WHERE bundesland = %s
        ORDER BY jahr
    """, (state,))

    result = [row[0] for row in cursor.fetchall()]

    conn.close()

    return result


def get_pedestrian_accidents(city: str, year: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM unfaelle
        WHERE gemeinde = %s
          AND jahr = %s
          AND ist_fuss = TRUE
    """, (city, year))

    result = cursor.fetchone()[0]

    conn.close()

    return result


def get_accident_aggregates(level: str, year: int, category: int):
    conn = get_connection()
    cursor = conn.cursor()

    if level == "bundesland":

        cursor.execute("""
            SELECT bundesland,
                   COUNT(*) AS unfaelle
            FROM unfaelle
            WHERE jahr = %s
              AND kategorie = %s
            GROUP BY bundesland
            ORDER BY unfaelle DESC
        """, (year, category))

    else:

        cursor.execute("""
            SELECT kreis,
                   COUNT(*) AS unfaelle
            FROM unfaelle
            WHERE jahr = %s
              AND kategorie = %s
            GROUP BY kreis
            ORDER BY unfaelle DESC
        """, (year, category))

    result = cursor.fetchall()

    conn.close()

    return result


def get_sources():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT quelle,
               lizenz_name,
               lizenz_url,
               abgerufen_am
        FROM lizenzen
        ORDER BY quelle
    """)

    result = cursor.fetchall()

    conn.close()

    return result


def get_import_runs():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM import_log
        ORDER BY beendet_am DESC
    """)

    result = cursor.fetchall()

    conn.close()

    return result


def get_per_capita(region: str, year: int):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            COUNT(u.unfall_id)::float /
            b.einwohner * 100000
        FROM unfaelle u
        JOIN regionen r
            ON u.region_id = r.region_id
        JOIN bevoelkerung b
            ON r.region_id = b.region_id
        WHERE r.name = %s
          AND b.jahr = %s
          AND u.jahr = %s
        GROUP BY b.einwohner
    """, (region, year, year))

    result = cursor.fetchone()

    conn.close()

    return result[0] if result else None