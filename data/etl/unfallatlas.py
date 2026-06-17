import pandas as pd

from psycopg2.extras import execute_values
from pathlib import Path

from data.utils.utils import create_connection, write_import_log


BASE_DIR = Path(__file__).resolve().parent.parent
CSV_DIR  = BASE_DIR / "unfallatlas"

SOURCE = "unfallatlas"


def find_csv_files(conn) -> list[Path]:
    """
    Gibt nur Dateien zurück, die noch nicht vollständig importiert wurden.
    Vergleicht Dateinamen mit import_log.
    """
    all_files = sorted(CSV_DIR.glob("*.csv"))

    cursor = conn.cursor()
    cursor.execute("""
        SELECT hinweis
        FROM import_log
        WHERE quelle = 'unfallatlas'
          AND status = 'success'
          AND hinweis IS NOT NULL
    """)
    imported = {row[0] for row in cursor.fetchall()}

    new_files     = [f for f in all_files if f.name not in imported]
    already_done  = [f for f in all_files if f.name in imported]

    print(f"  Dateien gesamt:        {len(all_files)}")
    print(f"  Bereits importiert:    {len(already_done)}")
    print(f"  Neu zu verarbeiten:    {len(new_files)}")

    for f in already_done:
        print(f"    ↷ übersprungen: {f.name}")
    for f in new_files:
        print(f"    → neu:          {f.name}")

    return new_files


def load_csv(path: Path) -> pd.DataFrame:
    """
    Lädt eine einzelne CSV-Datei mit pandas.
    """
    df = pd.read_csv(
        path,
        sep=";",
        dtype={
            "ULAND":       str,
            "UIDENTSTLAE": str,
            "UREGBEZ":     int,
            "UKREIS":      int,
            "UGEMEINDE":   int,
        },
        decimal=",",
    )

    print(f"  {len(df)} Zeilen geladen aus {path.name}")
    return df


def transform_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Bereitet die Rohdaten für den DB-Import vor.
    """
    df["bundesland"]       = pd.to_numeric(df["ULAND"],     errors="coerce")
    df["regierungsbezirk"] = pd.to_numeric(df["UREGBEZ"],   errors="coerce")
    df["kreis"]            = pd.to_numeric(df["UKREIS"],    errors="coerce")
    df["gemeinde"]         = pd.to_numeric(df["UGEMEINDE"], errors="coerce")

    df["jahr"]   = pd.to_numeric(df["UJAHR"],    errors="coerce")
    df["monat"]  = pd.to_numeric(df["UMONAT"],   errors="coerce")
    df["stunde"] = pd.to_numeric(df["USTUNDE"],  errors="coerce")

    df["kategorie"] = pd.to_numeric(df["UKATEGORIE"], errors="coerce")
    df["typ"]       = pd.to_numeric(df["UTYP1"],      errors="coerce")

    df["ist_rad"]      = df["IstRad"].fillna(0).astype(bool)
    df["ist_fuss"]     = df["IstFuss"].fillna(0).astype(bool)
    df["ist_pkw"]      = df["IstPKW"].fillna(0).astype(bool)
    df["ist_kraftrad"] = df["IstKrad"].fillna(0).astype(bool)

    df = df[[
        "UIDENTSTLAE",
        "jahr", "monat", "stunde",
        "bundesland", "regierungsbezirk", "kreis", "gemeinde",
        "kategorie", "typ",
        "ist_rad", "ist_fuss", "ist_pkw", "ist_kraftrad",
        "XGCSWGS84", "YGCSWGS84",
    ]]

    df = df.dropna(subset=["UIDENTSTLAE"])
    return df


def insert_data(conn, df: pd.DataFrame) -> dict:
    """
    Importiert Daten in die Tabelle 'unfaelle'.
    ON CONFLICT DO NOTHING sorgt dafür, dass bereits vorhandene
    extern_ids (z.B. aus einem früheren Import) übersprungen werden.
    So können Dateien gefahrlos erneut eingelesen werden.
    """
    cursor = conn.cursor()

    values = [
        (
            row["UIDENTSTLAE"],
            row["jahr"], row["monat"], row["stunde"],
            row["bundesland"], row["regierungsbezirk"],
            row["kreis"], row["gemeinde"],
            row["kategorie"], row["typ"],
            row["ist_rad"], row["ist_fuss"],
            row["ist_pkw"], row["ist_kraftrad"],
            row["XGCSWGS84"], row["YGCSWGS84"],
        )
        for _, row in df.iterrows()
    ]

    query = """
        INSERT INTO unfaelle (
            extern_id,
            jahr, monat, stunde,
            bundesland, regierungsbezirk, kreis, gemeinde,
            kategorie, typ,
            ist_rad, ist_fuss, ist_pkw, ist_kraftrad,
            lon, lat
        )
        VALUES %s
        ON CONFLICT (extern_id) DO NOTHING
        RETURNING unfall_id;
    """

    inserted_rows = execute_values(cursor, query, values, fetch=True)

    count_inserted  = len(inserted_rows)
    count_processed = len(values)
    count_skipped   = count_processed - count_inserted

    conn.commit()
    return {
        "processed": count_processed,
        "inserted":  count_inserted,
        "skipped":   count_skipped,
    }


def enrich_geodata(conn):
    """
    Schritt 1: geom aus lon/lat generieren.
    Schritt 2: region_id per räumlichem Join auf Kreis-Ebene setzen.
    Schritt 3: Fallback für Stadtstaaten (kein Kreis-Eintrag → Bundesland).
    Läuft einmal nach allen Datei-Importen — nur unverknüpfte Zeilen werden angefasst.
    """
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE unfaelle
        SET geom = ST_SetSRID(ST_MakePoint(lon, lat), 4326)
        WHERE geom IS NULL
          AND lon IS NOT NULL
          AND lat IS NOT NULL
    """)
    print(f"  geom gesetzt:              {cursor.rowcount}")

    cursor.execute("""
        UPDATE unfaelle u
        SET region_id = r.region_id
        FROM regionen r
        WHERE u.region_id IS NULL
          AND u.geom IS NOT NULL
          AND r.level = 'kreis'
          AND ST_Within(u.geom, r.geometrie)
    """)
    print(f"  region_id (Kreis):         {cursor.rowcount}")

    cursor.execute("""
        UPDATE unfaelle u
        SET region_id = r.region_id
        FROM regionen r
        WHERE u.region_id IS NULL
          AND u.geom IS NOT NULL
          AND r.level = 'bundesland'
          AND u.bundesland IN (2, 4, 11)
          AND ST_Within(u.geom, r.geometrie)
    """)
    print(f"  region_id (Stadtstaaten):  {cursor.rowcount}")

    cursor.execute("SELECT COUNT(*) FROM unfaelle WHERE region_id IS NULL")
    print(f"  Noch unverknüpft:          {cursor.fetchone()[0]}")

    conn.commit()


def main():
    conn = None
    try:
        conn = create_connection()

        csv_files = find_csv_files(conn)

        if not csv_files:
            print("Keine neuen Dateien zu importieren.")
            return

        for path in csv_files:
            print(f"\n=== {path.name} ===")
            try:
                df = load_csv(path)
                df = transform_data(df)

                log_info = insert_data(conn, df)

                print(f"  Verarbeitet: {log_info['processed']}")
                print(f"  Neu:         {log_info['inserted']}")
                print(f"  Übersprungen:{log_info['skipped']}")

                write_import_log(
                    conn,
                    status="success",
                    log_info=log_info,
                    filename=path.name,
                    source=SOURCE
                )

            except Exception as e:
                print(f"  FEHLER bei {path.name}: {e}")
                write_import_log(
                    conn,
                    status="failed",
                    log_info={"processed": 0, "inserted": 0, "skipped": 0},
                    filename=path.name,
                    hinweis=str(e),
                    source=SOURCE
                )
                continue

        print("\nGeodaten anreichern...")
        enrich_geodata(conn)
        print("\nETL erfolgreich abgeschlossen")

    except FileNotFoundError as e:
        print(f"\nFEHLER: {e}")

    except Exception as e:
        print(f"\nFEHLER: {e}")

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()