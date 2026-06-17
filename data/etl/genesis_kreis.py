import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path

from data.const.constants import DB_CONFIG

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "genesis" / "bevoelkerung_kreis.csv"

DATEINAME = CSV_PATH.name   # "bevoelkerung_kreis.csv"
QUELLE    = "genesis_kreis"


# ─── Bereits importiert? ─────────────────────────────────────────────────────

def already_imported(conn) -> bool:
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM import_log
        WHERE quelle = %s
          AND status = 'success'
          AND hinweis = %s
        LIMIT 1
    """, (QUELLE, DATEINAME))
    return cursor.fetchone() is not None


# ─── Laden ───────────────────────────────────────────────────────────────────

def load_csv() -> pd.DataFrame:
    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"CSV nicht gefunden: {CSV_PATH}\n"
            f"Bitte Datei unter data/genesis/ ablegen."
        )

    df = pd.read_csv(CSV_PATH, sep=";", skiprows=5, header=0, dtype=str)
    print(f"  {len(df)} Rohdaten-Zeilen geladen")
    return df


# ─── Transformieren ──────────────────────────────────────────────────────────

def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    cols     = df.columns.tolist()
    ags_col  = cols[0]

    # Nur Wert-Spalten (gerade Indizes ab 2) — Qualitätsspalten überspringen
    wert_cols = [cols[i] for i in range(2, len(cols), 2)]

    rows = []
    for _, row in df.iterrows():
        ags = str(row[ags_col]).strip()

        # Fußzeilen und leere Zeilen überspringen
        if not ags or len(ags) != 5 or not ags.isdigit():
            continue

        # AGS auf 8 Stellen: '01001' → '01001000'
        ags_8 = ags + "000"

        for col in wert_cols:
            wert = str(row[col]).strip()

            # "-" = aufgelöster Kreis oder kein Wert
            if wert in ("-", "") or pd.isna(row[col]):
                continue

            try:
                jahr      = int(str(col)[-4:])
                einwohner = int(float(wert))
                rows.append({
                    "ags":       ags_8,
                    "jahr":      jahr,
                    "einwohner": einwohner,
                })
            except (ValueError, TypeError):
                continue

    df_result = pd.DataFrame(rows)
    print(f"  {len(df_result)} Zeilen nach Transformation")
    return df_result


# ─── Region-IDs verknüpfen ───────────────────────────────────────────────────

def add_region_ids(conn, df: pd.DataFrame) -> pd.DataFrame:
    regionen_df = pd.read_sql("""
        SELECT region_id, ags
        FROM regionen
        WHERE level = 'kreis'
    """, conn)

    df = df.merge(regionen_df, on="ags", how="left")

    fehlende = df[df["region_id"].isna()]["ags"].unique()
    if len(fehlende) > 0:
        print(f"  Keine region_id für {len(fehlende)} AGS "
              f"(aufgelöste Kreise — wird übersprungen):")
        for a in fehlende[:5]:
            print(f"    {a}")
        if len(fehlende) > 5:
            print(f"    ... und {len(fehlende) - 5} weitere")

    df = df.dropna(subset=["region_id"])
    print(f"  {len(df)} Zeilen mit region_id verknüpft")
    return df[["region_id", "jahr", "einwohner"]]


# ─── Einfügen ────────────────────────────────────────────────────────────────

def insert_data(conn, df: pd.DataFrame) -> dict:
    cursor = conn.cursor()

    values = [
        (int(row["region_id"]), int(row["jahr"]), int(row["einwohner"]))
        for _, row in df.iterrows()
    ]

    query = """
        INSERT INTO bevoelkerung (region_id, jahr, einwohner)
        VALUES %s
        ON CONFLICT (region_id, jahr)
        DO UPDATE SET einwohner = EXCLUDED.einwohner
        RETURNING bev_id;
    """

    inserted_rows   = execute_values(cursor, query, values, fetch=True)
    conn.commit()

    count_processed = len(values)
    count_inserted  = len(inserted_rows)

    return {
        "processed": count_processed,
        "inserted":  count_inserted,
        "skipped":   count_processed - count_inserted,
    }


# ─── Log ─────────────────────────────────────────────────────────────────────

def write_import_log(conn, status: str, log_info: dict, hinweis: str = None):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_log (
            quelle, beendet_am, status,
            verarbeitet, hinzugef, verworfen, hinweis
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
    """, (
        QUELLE,
        status,
        log_info.get("processed"),
        log_info.get("inserted"),
        log_info.get("skipped"),
        hinweis or DATEINAME,
    ))
    conn.commit()


# ─── Main ────────────────────────────────────────────────────────────────────

def create_connection():
    return psycopg2.connect(**DB_CONFIG)


def main():
    conn = None
    try:
        conn = create_connection()

        if already_imported(conn):
            print(f"  ↷ {DATEINAME} bereits importiert — übersprungen")
            return

        df       = load_csv()
        df       = transform_data(df)
        df       = add_region_ids(conn, df)
        log_info = insert_data(conn, df)

        print(f"  Verarbeitet:      {log_info['processed']}")
        print(f"  Neu/aktualisiert: {log_info['inserted']}")

        write_import_log(conn, status="success", log_info=log_info)
        print(f"  ✓ {DATEINAME} erfolgreich importiert")

    except FileNotFoundError as e:
        print(f"  FEHLER: {e}")

    except Exception as e:
        print(f"  FEHLER: {e}")
        if conn:
            write_import_log(conn, status="failed",
                log_info={"processed": 0, "inserted": 0, "skipped": 0},
                hinweis=str(e))
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()