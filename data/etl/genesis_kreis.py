import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from pathlib import Path
from data.const.constants import DB_CONFIG

BASE_DIR = Path(__file__).resolve().parent.parent
CSV_PATH = BASE_DIR / "genesis" / "bevoelkerung_kreis.csv"


def load_csv():
    df = pd.read_csv(
        CSV_PATH,
        sep=";",
        skiprows=5,
        header=0,
        dtype=str,
    )
    return df


def transform_data(df):
    cols = df.columns.tolist()

    ags_col  = cols[0]
    wert_cols = [cols[i] for i in range(2, len(cols), 2)]

    rows = []

    for _, row in df.iterrows():
        ags = str(row[ags_col]).strip()

        # Fußzeilen und leere Zeilen überspringen
        if not ags or len(ags) != 5 or not ags.isdigit():
            continue

        ags_8 = ags + "000"

        for col in wert_cols:
            wert = str(row[col]).strip()

            if wert == "-" or wert == "" or pd.isna(row[col]):
                continue

            try:
                jahr = int(str(col)[-4:])
            except ValueError:
                continue

            try:
                einwohner = int(float(wert))
            except ValueError:
                continue

            rows.append({
                "ags":       ags_8,
                "jahr":      jahr,
                "einwohner": einwohner,
            })

    return pd.DataFrame(rows)


def add_region_ids(conn, df):
    """
    Verknüpft über AGS
    """
    regionen_df = pd.read_sql("""
        SELECT region_id, ags
        FROM regionen
        WHERE level = 'kreis'
    """, conn)

    df = df.merge(regionen_df, on="ags", how="left")

    fehlende = df[df["region_id"].isna()]["ags"].unique()
    if len(fehlende) > 0:
        print(f"  Keine region_id für {len(fehlende)} AGS (aufgelöste Kreise, normal):")
        for a in fehlende[:5]:
            print(f"    {a}")

    df = df.dropna(subset=["region_id"])
    df = df[["region_id", "jahr", "einwohner"]]

    return df


def create_connection():
    return psycopg2.connect(**DB_CONFIG)


def insert_data(conn, df):
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

    inserted_rows = execute_values(cursor, query, values, fetch=True)
    conn.commit()

    count_processed = len(values)
    count_inserted  = len(inserted_rows)

    return {
        "processed": count_processed,
        "inserted":  count_inserted,
        "skipped":   count_processed - count_inserted,
    }


def write_import_log(conn, status, log_info, hinweis=None):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_log (
            quelle, beendet_am, status,
            verarbeitet, hinzugef, verworfen, hinweis
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
    """, (
        "genesis_kreis",
        status,
        log_info.get("processed"),
        log_info.get("inserted"),
        log_info.get("skipped"),
        hinweis,
    ))
    conn.commit()


def main():
    conn = None
    try:
        df = load_csv()
        df = transform_data(df)

        print(f"  {len(df)} Zeilen nach Transformation")

        conn = create_connection()
        df   = add_region_ids(conn, df)

        print(f"  {len(df)} Zeilen mit region_id verknüpft")

        log_info = insert_data(conn, df)

        print(f"  Verarbeitet: {log_info['processed']}")
        print(f"  Neu/aktualisiert: {log_info['inserted']}")

        write_import_log(conn, status="success", log_info=log_info)

    except Exception as e:
        print(f"FEHLER: {e}")
        if conn:
            write_import_log(conn, status="failed",
                log_info={"processed": 0, "inserted": 0, "skipped": 0},
                hinweis=str(e))
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()