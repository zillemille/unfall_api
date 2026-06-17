import psycopg2
import os

# Datenbankkennungen
DB_CONFIG = {
    "host":     os.getenv("DB_HOST", "localhost"),
    "port":     int(os.getenv("DB_PORT", "5432")),
    "user":     os.getenv("DB_USER", "dbw_user"),
    "password": os.getenv("DB_PASS", "dbw_pass"),
    "dbname":   os.getenv("DB_NAME", "dbw_db"),
}

def create_connection():
    return psycopg2.connect(**DB_CONFIG)


def write_import_log(conn, status: str, log_info: dict, hinweis: str = None, source: str = None, filename: str = None):
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO import_log (
            quelle, beendet_am, status,
            verarbeitet, hinzugef, verworfen, hinweis
        )
        VALUES (%s, NOW(), %s, %s, %s, %s, %s)
    """, (
        source,
        status,
        log_info.get("processed"),
        log_info.get("inserted"),
        log_info.get("skipped"),
        hinweis or filename,
    ))
    conn.commit()



# Bundesländerzuordnungen
BUNDESLAENDER = [
    "Baden-Württemberg",
    "Bayern",
    "Berlin",
    "Brandenburg",
    "Bremen",
    "Hamburg",
    "Hessen",
    "Mecklenburg-Vorpommern",
    "Niedersachsen",
    "Nordrhein-Westfalen",
    "Rheinland-Pfalz",
    "Saarland",
    "Sachsen",
    "Sachsen-Anhalt",
    "Schleswig-Holstein",
    "Thüringen"
]

BUNDESLAENDER_ID = {
    "01": "Schleswig-Holstein",
    "02": "Hamburg",
    "03": "Niedersachsen",
    "04": "Bremen",
    "05": "Nordrhein-Westfalen",
    "06": "Hessen",
    "07": "Rheinland-Pfalz",
    "08": "Baden-Württemberg",
    "09": "Bayern",
    "10": "Saarland",
    "11": "Berlin",
    "12": "Brandenburg",
    "13": "Mecklenburg-Vorpommern",
    "14": "Sachsen",
    "15": "Sachsen-Anhalt",
    "16": "Thüringen",
}

BUNDESLAENDER_NAME = {
    "Schleswig-Holstein": "01",
    "Hamburg": "02",
    "Niedersachsen": "03",
    "Bremen": "04",
    "Nordrhein-Westfalen": "05",
    "Hessen": "06",
    "Rheinland-Pfalz": "07",
    "Baden-Württemberg": "08",
    "Bayern": "09",
    "Saarland": "10",
    "Berlin": "11",
    "Brandenburg": "12",
    "Mecklenburg-Vorpommern": "13",
    "Sachsen": "14",
    "Sachsen-Anhalt": "15",
    "Thüringen": "16",
}

BUNDESLÄNDER_AGS = {
            "01000000": "Schleswig-Holstein",
            "02000000": "Hamburg",
            "03000000": "Niedersachsen",
            "04000000": "Bremen",
            "05000000": "Nordrhein-Westfalen",
            "06000000": "Hessen",
            "07000000": "Rheinland-Pfalz",
            "08000000": "Baden-Württemberg",
            "09000000": "Bayern",
            "10000000": "Saarland",
            "11000000": "Berlin",
            "12000000": "Brandenburg",
            "13000000": "Mecklenburg-Vorpommern",
            "14000000": "Sachsen",
            "15000000": "Sachsen-Anhalt",
            "16000000": "Thüringen"
        }




# Unfallketegorien
UNFALLKATEGORIE = {
    "1" : "Unfall mit Getöteten",
    "2" : "Unfall mit Schwerverletzten",
    "3" : "Unfall mit Leichtverletzten",
}

UNFALLTYP = {
    "1": "Fahrunfall",
    "2": "Abbiegeunfall",
    "3": "Einbiegen / Kreuzen-Unfall",
    "4": "Überschreiten-Unfall",
    "5": "Unfall durch ruhenden Verkehr",
    "6": "Unfall im Längsverkehr",
    "7": "sonstiger Unfall",
}




# Genesis Statistik
STATISTIC_GENESIS = {
    "-": "nichts vorhanden, genau Null oder ggf. zur Sicherstellung der statistischen Geheimhaltung auf Null geändert",
    "e": "endgültiger Wert",
    "0": "Zahlenwert von Null verschieden, jedoch so nahe an Null, dass auf Null gerundet",
    "r": "berichtigte Zahl",
    "p": "vorläufige Zahl",
    "s": "geschätzte Zahl",
    "()": "Aussagewert eingeschränkt, da der Zahlenwert statistisch relativ unsicher ist",
    "/": "keine Angaben, da Zahlenwert nicht sicher genug",
    ".": "Zahlenwert unbekannt oder geheim zu halten",
    "...": "Angabe fällt später an",
    "x": "Tabellenfach gesperrt, weil Aussage nicht sinnvoll"
}