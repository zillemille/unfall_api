import pandas as pd
import psycopg2

from psycopg2.extras import execute_values
from pathlib import Path

from data.const.constants import BUNDESLAENDER
from data.const.constants import DB_CONFIG


BASE_DIR = Path(__file__).resolve().parent.parent

CSV_PATH = BASE_DIR / "data" / "genesis" / "bevoelkerung_bundeslaender.csv"


def load_csv():

    df = pd.read_csv(
        CSV_PATH,
        sep=";",
        skiprows=5,
        header=0
    )

    bundesland_col = df.columns[0]

    df = df[df[bundesland_col].isin(BUNDESLAENDER)]

    return df


def transform_data(df):

    rows = []

    bundesland_col = df.columns[0]

    jahr_spalten = [
        col
        for col in df.columns[1:]
        if not str(col).endswith(".1")
    ]

    for _, row in df.iterrows():

        bundesland = row[bundesland_col]

        for col in jahr_spalten:

            jahr = int(str(col)[-4:])

            rows.append({
                "bundesland": bundesland,
                "jahr": jahr,
                "einwohner": row[col]
            })

    df_long = pd.DataFrame(rows)

    df_long["einwohner"] = pd.to_numeric(
        df_long["einwohner"],
        errors="coerce"
    )

    df_long = df_long.dropna(
        subset=["einwohner"]
    )

    df_long["einwohner"] = (
        df_long["einwohner"]
        .astype(int)
    )

    return df_long


def add_region_ids(conn, df):

    query = """
        SELECT
            region_id,
            name
        FROM regionen
        WHERE level = 'bundesland'
    """

    regionen_df = pd.read_sql(query, conn)

    df = df.merge(
        regionen_df,
        left_on="bundesland",
        right_on="name",
        how="left"
    )

    if df["region_id"].isna().any():

        fehlende = (
            df[df["region_id"].isna()]
            ["bundesland"]
            .unique()
        )

        raise ValueError(
            f"Keine region_id gefunden für: {fehlende}"
        )

    df = df[[
        "region_id",
        "jahr",
        "einwohner"
    ]]

    return df



def create_connection():
    """
    Erstellt Verbindung zur PostgreSQL-Datenbank.
    """

    conn = psycopg2.connect(**DB_CONFIG)

    return conn


def insert_data(conn, df):

    cursor = conn.cursor()

    values = []

    for _, row in df.iterrows():

        values.append((
            int(row["region_id"]),
            int(row["jahr"]),
            int(row["einwohner"])
        ))

    query = """
        INSERT INTO bevoelkerung (
            region_id,
            jahr,
            einwohner
        )
        VALUES %s

        ON CONFLICT (region_id, jahr)
        DO UPDATE
        SET einwohner = EXCLUDED.einwohner

        RETURNING bev_id;
    """

    inserted_rows = execute_values(
        cursor,
        query,
        values,
        fetch=True
    )

    count_processed = len(values)
    count_inserted = len(inserted_rows)

    conn.commit()

    return {
        "processed": count_processed,
        "inserted": count_inserted,
        "skipped": count_processed - count_inserted
    }


def write_import_log(conn, status, log_info, hinweis=None):

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO import_log (
            quelle,
            beendet_am,
            status,
            verarbeitet,
            hinzugef,
            verworfen,
            hinweis
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
    """, (
        "genesis",
        status,
        log_info.get("processed"),
        log_info.get("inserted"),
        log_info.get("skipped"),
        hinweis
    ))

    conn.commit()


def main():

    conn = None

    try:

        df = load_csv()

        df = transform_data(df)

        conn = create_connection()

        df = add_region_ids(conn, df)

        log_info = insert_data(conn, df)

        write_import_log(
            conn,
            status="success",
            log_info=log_info
        )

        print("ETL erfolgreich abgeschlossen")

    except Exception as e:

        print("FEHLER:")
        print(e)

        if conn:

            write_import_log(
                conn,
                status="failed",
                log_info={
                    "processed": 0,
                    "inserted": 0,
                    "skipped": 0
                },
                hinweis=str(e)
            )

    finally:

        if conn:
            conn.close()


if __name__ == "__main__":
    main()