import psycopg2

from data.utils.utils import DB_CONFIG


def run_checks():

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT COUNT(*)
        FROM unfaelle
    """)

    print("Unfälle:", cursor.fetchone()[0])

    cursor.execute("""
        SELECT COUNT(*)
        FROM regionen
    """)

    print("Regionen:", cursor.fetchone()[0])

    cursor.execute("""
        SELECT COUNT(*)
        FROM bevoelkerung
    """)

    print("Bevölkerung:", cursor.fetchone()[0])

    conn.close()


if __name__ == "__main__":
    run_checks()