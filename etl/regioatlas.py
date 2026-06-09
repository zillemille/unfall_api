import geopandas as gpd
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

from pathlib import Path

from data.const.constants import DB_CONFIG
from data.const.constants import BUNDESLÄNDER_AGS

BASE_DIR = Path(__file__).resolve().parent.parent

GEOJSON_PATH = (
    BASE_DIR
    / "data"
    / "regioatlas"
    / "regioatlas.geojson"
)


def load_geojson():

    gdf = gpd.read_file(GEOJSON_PATH)

    return gdf


def transform_data(gdf):

    gdf = gdf.to_crs(4326)

    gdf = gdf[[
        "schluessel",
        "gen",
        "geometry"
    ]]

    gdf = gdf.rename(columns={
        "schluessel": "ags",
        "gen": "name",
        "geometry": "geometrie"
    })

    gdf.set_geometry("geometrie", inplace=True)

    # -----------------------------
    # LANDKREISE
    # -----------------------------

    landkreise = gdf.copy()

    landkreise["ags"] = (
        landkreise["ags"]
        .astype(str)
        .apply(normalize_ags)
    )

    landkreise["level"] = "landkreis"

    landkreise["parent_ags"] = (
        landkreise["ags"].str[:2]
        + "000000"
    )

    # -----------------------------
    # BUNDESLÄNDER
    # -----------------------------

    bundeslaender = landkreise.copy()

    bundeslaender["bundesland_ags"] = bundeslaender["ags"].str[:2] + "000000"
    bundeslaender = bundeslaender.dissolve(
        by="bundesland_ags",
        as_index=False
    )

    bundeslaender["ags"] = bundeslaender["bundesland_ags"]
    bundeslaender["name"] = bundeslaender["ags"].map(BUNDESLÄNDER_AGS)
    bundeslaender["level"] = "bundesland"
    bundeslaender["parent_ags"] = None


    bundeslaender = bundeslaender[[
        "ags",
        "name",
        "level",
        "parent_ags",
        "geometrie"
    ]]


    # -----------------------------
    # KOMBINIEREN
    # -----------------------------

    # hamburg, berlin und bremen  rausfiltern aus landkreisen
    landkreise = landkreise[
        ~landkreise["ags"].isin([
            "02000000",
            "11000000",
            "04000000"
        ])
    ]

    gdf_final = pd.concat([
        landkreise,
        bundeslaender
    ], ignore_index=True)

    gdf_final["geometrie_wkt"] = (
        gdf_final["geometrie"]
        .to_wkt()
    )


    gdf_final = gdf_final.dropna(subset=["ags"])

    return gdf_final


def normalize_ags(ags):

    ags = str(ags)

    if len(ags) == 2:
        return ags + "000000"

    if len(ags) == 5:
        return ags + "000"

    return None


def create_connection():

    conn = psycopg2.connect(**DB_CONFIG)

    return conn



def insert_data(conn, gdf):

    cursor = conn.cursor()

    values = []
    for _, row in gdf.iterrows():
        values.append((
            row["ags"],
            row["name"],
            row["level"],
            row["parent_ags"],
            row["geometrie_wkt"]
        ))


    query = """
        INSERT INTO regionen (
            ags,
            name,
            level,
            parent_ags,
            geometrie
        )
        VALUES %s

        ON CONFLICT (ags)
        DO NOTHING

        RETURNING region_id;
    """

    template = """
    (
        %s,
        %s,
        %s,
        %s,
        ST_Multi(
            ST_GeomFromText(%s, 4326)
        )
    )
    """

    inserted_rows = execute_values(
        cursor,
        query,
        values,
        template=template,
        fetch=True
    )

    count_inserted = len(inserted_rows)
    count_processed = len(values)
    count_skipped = count_processed - count_inserted

    conn.commit()

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
        "regionalatlas",
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

        print("laden")
        gdf = load_geojson()

        print("transform")
        gdf = transform_data(gdf)

        print("conn")
        conn = create_connection()

        print("insert")
        log_info = insert_data(conn, gdf)

        print("log")
        write_import_log(
            conn,
            status="success",
            log_info=log_info
        )

    except Exception as e:

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