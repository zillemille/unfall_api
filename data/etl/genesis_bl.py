import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path

from data.const.constants import DB_CONFIG
from data.const.constants import BUNDESLAENDER

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "genesis" / "bevoelkerung_bundeslaender.csv"

DATEINAME = CSV_PATH.name   # "bevoelkerung_bundeslaender.csv"
QUELLE    = "genesis_bl"


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

    df = pd.read_csv(CSV_PATH, sep=";", skiprows=5, header=0)

    bundesland_col = df.columns[0]
    df = df[df[bundesland_col].isin(BUNDESLAENDER)]

    print(f"  {len(df)} Bundesländer geladen")
    return df


# ─── Transformieren ──────────────────────────────────────────────────────────

def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    bundesland_col = df.columns[0]

    # Qualitätsspalten (.1-Suffix) überspringen
    jahr_spalten = [
        col for col in df.columns[1:]
        if not str(col).endswith(".1")
    ]

    rows = []
    for _, row in df.iterrows():
        bundesland = row[bundesland_col]
        for col in jahr_spalten:
            try:
                jahr      = int(str(col)[-4:])
                einwohner = int(pd.to_numeric(row[col], errors="raise"))
                rows.append({
                    "bundesland": bundesland,
                    "jahr":       jahr,
                    "einwohner":  einwohner,
                })
            except (ValueError, TypeError):
                continue

    df_long = pd.DataFrame(rows)
    print(f"  {len(df_long)} Zeilen nach Transformation")
    return df_long


# ─── Region-IDs verknüpfen ───────────────────────────────────────────────────

def add_region_ids(conn, df: pd.DataFrame) -> pd.DataFrame:
    regionen_df = pd.read_sql("""
        SELECT region_id, name
        FROM regionen
        WHERE level = 'bundesland'
    """, conn)

    df = df.merge(regionen_df, left_on="bundesland", right_on="name", how="left")

    fehlende = df[df["region_id"].isna()]["bundesland"].unique()
    if len(fehlende) > 0:
        raise ValueError(f"Keine region_id für: {fehlende}")

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

        print(f"  Verarbeitet: {log_info['processed']}")
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