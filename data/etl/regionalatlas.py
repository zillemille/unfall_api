import geopandas as gpd
import pandas as pd
from psycopg2.extras import execute_values
from pathlib import Path

from data.utils.utils import BUNDESLÄNDER_AGS,create_connection, write_import_log

BASE_DIR    = Path(__file__).resolve().parent.parent
GEOJSON_PATH = BASE_DIR / "regionalatlas" / "regionalatlas.geojson"

FILENAME = GEOJSON_PATH.name   # "regionalatlas.geojson"
SOURCE    = "regionalatlas"


# ─── Bereits importiert? ─────────────────────────────────────────────────────

def already_imported(conn) -> bool:
    """
    Prüft ob diese Datei bereits erfolgreich importiert wurde.
    Verhindert doppelten Import bei erneutem ETL-Lauf.
    """
    cursor = conn.cursor()
    cursor.execute("""
        SELECT 1 FROM import_log
        WHERE quelle = %s
          AND status = 'success'
          AND hinweis = %s
        LIMIT 1
    """, (SOURCE, FILENAME))
    return cursor.fetchone() is not None


# ─── Laden ───────────────────────────────────────────────────────────────────

def load_geojson() -> gpd.GeoDataFrame:
    if not GEOJSON_PATH.exists():
        raise FileNotFoundError(
            f"GeoJSON nicht gefunden: {GEOJSON_PATH}\n"
            f"Bitte Datei unter data/regionalatlas/ ablegen."
        )
    print(f"  Lade {FILENAME}...")
    gdf = gpd.read_file(GEOJSON_PATH)
    print(f"  {len(gdf)} Features geladen")
    return gdf


# ─── Transformieren ──────────────────────────────────────────────────────────

def normalize_ags(ags: str) -> str | None:
    ags = str(ags)
    if len(ags) == 2:
        return ags + "000000"
    if len(ags) == 5:
        return ags + "000"
    return None


def transform_data(gdf: gpd.GeoDataFrame) -> pd.DataFrame:
    gdf = gdf.to_crs(4326)
    gdf = gdf[["schluessel", "gen", "geometry"]].rename(columns={
        "schluessel": "ags",
        "gen":        "name",
        "geometry":   "geometrie",
    })
    gdf.set_geometry("geometrie", inplace=True)

    # Kreise
    landkreise = gdf.copy()
    landkreise["ags"]        = landkreise["ags"].astype(str).apply(normalize_ags)
    landkreise["level"]      = "kreis"
    landkreise["parent_ags"] = landkreise["ags"].str[:2] + "000000"

    # Bundesländer — durch dissolve aus Kreisen aggregiert
    bundeslaender = landkreise.copy()
    bundeslaender["bundesland_ags"] = bundeslaender["ags"].str[:2] + "000000"
    bundeslaender = bundeslaender.dissolve(by="bundesland_ags", as_index=False)
    bundeslaender["ags"]        = bundeslaender["bundesland_ags"]
    bundeslaender["name"]       = bundeslaender["ags"].map(BUNDESLÄNDER_AGS)
    bundeslaender["level"]      = "bundesland"
    bundeslaender["parent_ags"] = None
    bundeslaender = bundeslaender[["ags", "name", "level", "parent_ags", "geometrie"]]

    # Stadtstaaten: als Bundesland UND als Kreis eintragen
    stadtstaaten_ags = ["02000000", "11000000", "04000000"]
    landkreise = landkreise[~landkreise["ags"].isin(stadtstaaten_ags)]

    stadtstaaten_als_kreis = bundeslaender[
        bundeslaender["ags"].isin(stadtstaaten_ags)
    ].copy()
    stadtstaaten_als_kreis["level"] = "kreis"

    gdf_final = pd.concat(
        [landkreise, bundeslaender, stadtstaaten_als_kreis],
        ignore_index=True
    )

    gdf_final["geometrie_wkt"] = gdf_final["geometrie"].to_wkt()
    gdf_final = gdf_final.dropna(subset=["ags", "name"])

    print(f"  {len(gdf_final)} Regionen transformiert "
          f"({len(landkreise)} Kreise, "
          f"{len(bundeslaender)} Bundesländer, "
          f"{len(stadtstaaten_als_kreis)} Stadtstaaten als Kreis)")

    return gdf_final


# ─── Einfügen ────────────────────────────────────────────────────────────────

def insert_data(conn, gdf: pd.DataFrame) -> dict:
    cursor = conn.cursor()

    values = [
        (row["ags"], row["name"], row["level"], row["parent_ags"], row["geometrie_wkt"])
        for _, row in gdf.iterrows()
    ]

    query = """
        INSERT INTO regionen (ags, name, level, parent_ags, geometrie)
        VALUES %s
        ON CONFLICT (ags, level) DO NOTHING
        RETURNING region_id;
    """

    template = """
    (
        %s, %s, %s, %s,
        ST_Multi(ST_GeomFromText(%s, 4326))
    )
    """

    inserted_rows = execute_values(cursor, query, values, template=template, fetch=True)
    conn.commit()

    count_inserted  = len(inserted_rows)
    count_processed = len(values)

    return {
        "processed": count_processed,
        "inserted":  count_inserted,
        "skipped":   count_processed - count_inserted,
    }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    conn = None
    try:
        conn = create_connection()

        if already_imported(conn):
            print(f"  ↷ {FILENAME} bereits importiert — übersprungen")
            return

        gdf      = load_geojson()
        gdf      = transform_data(gdf)
        log_info = insert_data(conn, gdf)

        print(f"  Verarbeitet: {log_info['processed']}")
        print(f"  Neu:         {log_info['inserted']}")
        print(f"  Übersprungen:{log_info['skipped']}")

        write_import_log(conn, status="success", log_info=log_info, source=SOURCE, filename=FILENAME)
        print(f"  ✓ {FILENAME} erfolgreich importiert")

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