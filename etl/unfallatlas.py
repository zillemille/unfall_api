import pandas as pd
import psycopg2

from psycopg2.extras import execute_values
from pathlib import Path

from data.const.constants import DB_CONFIG



BASE_DIR = Path(__file__).resolve().parent.parent

CSV_PATH = BASE_DIR / "data" / "unfallatlas" / "Unfallorte2024_LinRef.csv"




def load_csv():
    """
    Lädt die CSV-Datei mit pandas.
    """

    df = pd.read_csv(
        CSV_PATH,
        sep=";",
        dtype={
            "ULAND": str,
            'UIDENTSTLAE': str,
            'UREGBEZ': int,
            'UKREIS': int,
            'UGEMEINDE': int,

        },
        decimal=",",
    )


    print(f"{len(df)} Zeilen geladen")

    return df


def transform_data(df):
    """
    Bereitet die Rohdaten für den DB-Import vor.
    """

    print("Transformiere Daten...")


    df["bundesland"] = pd.to_numeric(df["ULAND"], errors="coerce")
    df["regierungsbezirk"] = pd.to_numeric(df["UREGBEZ"], errors="coerce")
    df["kreis"] = pd.to_numeric(df["UKREIS"], errors="coerce")
    df["gemeinde"] = pd.to_numeric(df["UGEMEINDE"], errors="coerce")


    df["jahr"] = pd.to_numeric(df["UJAHR"], errors="coerce")
    df["monat"] = pd.to_numeric(df["UMONAT"], errors="coerce")
    df["stunde"] = pd.to_numeric(df["USTUNDE"], errors="coerce")

    df["kategorie"] = pd.to_numeric(df["UKATEGORIE"], errors="coerce")
    df["typ"] = pd.to_numeric(df["UTYP1"], errors="coerce")


    df["ist_rad"] = df["IstRad"].fillna(0).astype(bool)
    df["ist_fuss"] = df["IstFuss"].fillna(0).astype(bool)
    df["ist_pkw"] = df["IstPKW"].fillna(0).astype(bool)
    df["ist_kraftrad"] = df["IstKrad"].fillna(0).astype(bool)


    df = df[[
        "UIDENTSTLAE",
        "jahr",
        "monat",
        "stunde",
        "bundesland",
        "regierungsbezirk",
        "kreis",
        "gemeinde",
        "kategorie",
        "typ",
        "ist_rad",
        "ist_fuss",
        "ist_pkw",
        "ist_kraftrad",
        "XGCSWGS84",
        "YGCSWGS84"
    ]]


    df = df.dropna(subset=["UIDENTSTLAE"])

    print("Transformation abgeschlossen")

    return df



def create_connection():
    """
    Erstellt Verbindung zur PostgreSQL-Datenbank.
    """

    conn = psycopg2.connect(**DB_CONFIG)

    return conn



def insert_data(conn, df):
    """
    Importiert Daten in die Tabelle 'unfaelle'.
    """

    print("Importiere Daten in PostgreSQL...")

    cursor = conn.cursor()


    values = []
    for _, row in df.iterrows():
        values.append((
            row["UIDENTSTLAE"],
            row["jahr"],
            row["monat"],
            row["stunde"],
            row["bundesland"],
            row["regierungsbezirk"],
            row["kreis"],
            row["gemeinde"],
            row["kategorie"],
            row["typ"],
            row["ist_rad"],
            row["ist_fuss"],
            row["ist_pkw"],
            row["ist_kraftrad"],
            row["XGCSWGS84"],
            row["YGCSWGS84"]
        ))

    query = """
        INSERT INTO unfaelle (
            extern_id,
            jahr,
            monat,
            stunde,
            bundesland,
            regierungsbezirk,
            kreis,
            gemeinde,
            kategorie,
            typ,
            ist_rad,
            ist_fuss,
            ist_pkw,
            ist_kraftrad,
            lon,
            lat
        )
        VALUES %s
        ON CONFLICT (extern_id) DO NOTHING
        RETURNING unfall_id;
    """

    inserted_rows = execute_values(
        cursor,
        query,
        values,
        fetch=True)
    count_inserted = len(inserted_rows)
    count_processed = len(values)
    count_skipped = count_processed - count_inserted

    conn.commit()

    print(f"{len(values)} Datensätze importiert")

    return {
        "processed": count_processed,
        "inserted": count_inserted,
        "skipped": count_skipped
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
        "unfallatlas",
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