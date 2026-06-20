"""
Plausibilitätsprüfungen für die importierten Daten.

Prüft strukturelle und inhaltliche Konsistenz nach dem ETL-Lauf:
- Vollständigkeit (NULL-Werte an kritischen Stellen)
- Wertebereiche (z.B. Jahr, Monat, Stunde plausibel)
- Referenzielle Integrität (Fremdschlüssel verweisen auf existierende Zeilen)
- Duplikate (sollten durch ON CONFLICT bereits verhindert sein)
- Geodaten-Konsistenz (Geometrien gültig, Punkte innerhalb Deutschlands)

Jede Prüfung gibt OK/WARNUNG/FEHLER zurück und wird im Ergebnis gesammelt,
sodass am Ende ein Gesamtstatus feststeht.
"""

import psycopg2
from data.utils.utils import DB_CONFIG


class CheckResult:
    """Sammelt Ergebnisse aller Prüfungen für eine Zusammenfassung am Ende."""

    def __init__(self):
        self.ok = []
        self.warnungen = []
        self.fehler = []

    def add_ok(self, name: str, detail: str = ""):
        self.ok.append((name, detail))
        print(f"  ✓ {name}" + (f" — {detail}" if detail else ""))

    def add_warnung(self, name: str, detail: str):
        self.warnungen.append((name, detail))
        print(f"  ⚠ {name} — {detail}")

    def add_fehler(self, name: str, detail: str):
        self.fehler.append((name, detail))
        print(f"  ✗ {name} — {detail}")

    def summary(self) -> dict:
        return {
            "ok":        len(self.ok),
            "warnungen": len(self.warnungen),
            "fehler":    len(self.fehler),
            "status":    "fehler" if self.fehler else ("warnung" if self.warnungen else "ok"),
        }


def create_connection():
    return psycopg2.connect(**DB_CONFIG)


# ─── Vollständigkeit ─────────────────────────────────────────────────────────

def check_grunddaten_vorhanden(cur, result: CheckResult):
    """Prüft ob überhaupt Daten in den Kerntabellen liegen."""
    tabellen = ["unfaelle", "regionen", "bevoelkerung"]
    for tabelle in tabellen:
        cur.execute(f"SELECT COUNT(*) FROM {tabelle}")
        count = cur.fetchone()[0]
        if count == 0:
            result.add_fehler(f"{tabelle} leer", "keine Datensätze vorhanden")
        else:
            result.add_ok(f"{tabelle} befüllt", f"{count:,} Zeilen")


def check_unfaelle_geodaten(cur, result: CheckResult):
    """Prüft wie viele Unfälle noch keine Geometrie oder region_id haben."""
    cur.execute("SELECT COUNT(*) FROM unfaelle")
    gesamt = cur.fetchone()[0]
    if gesamt == 0:
        return

    cur.execute("SELECT COUNT(*) FROM unfaelle WHERE geom IS NULL")
    ohne_geom = cur.fetchone()[0]
    anteil_geom = ohne_geom / gesamt * 100

    if ohne_geom == 0:
        result.add_ok("Alle Unfälle georeferenziert", f"{gesamt:,} Zeilen mit geom")
    elif anteil_geom < 1:
        result.add_warnung("Unfälle ohne geom", f"{ohne_geom:,} von {gesamt:,} ({anteil_geom:.2f}%)")
    else:
        result.add_fehler("Unfälle ohne geom", f"{ohne_geom:,} von {gesamt:,} ({anteil_geom:.2f}%)")

    cur.execute("SELECT COUNT(*) FROM unfaelle WHERE region_id IS NULL")
    ohne_region = cur.fetchone()[0]
    anteil_region = ohne_region / gesamt * 100

    if ohne_region == 0:
        result.add_ok("Alle Unfälle einer Region zugeordnet")
    elif anteil_region < 1:
        result.add_warnung("Unfälle ohne region_id", f"{ohne_region:,} von {gesamt:,} ({anteil_region:.2f}%)")
    else:
        result.add_fehler("Unfälle ohne region_id", f"{ohne_region:,} von {gesamt:,} ({anteil_region:.2f}%)")


# ─── Wertebereiche ───────────────────────────────────────────────────────────

def check_jahr_plausibel(cur, result: CheckResult):
    """Unfalljahre müssen in einem sinnvollen Bereich liegen (Unfallatlas startet 2016)."""
    cur.execute("""
        SELECT MIN(jahr), MAX(jahr)
        FROM unfaelle
        WHERE jahr IS NOT NULL
    """)
    row = cur.fetchone()
    if row[0] is None:
        result.add_fehler("Jahr-Bereich", "keine jahr-Werte vorhanden")
        return

    min_jahr, max_jahr = row
    if min_jahr < 2016 or max_jahr > 2030:
        result.add_warnung("Jahr-Bereich unplausibel", f"{min_jahr}–{max_jahr}")
    else:
        result.add_ok("Jahr-Bereich plausibel", f"{min_jahr}–{max_jahr}")


def check_monat_stunde_bereich(cur, result: CheckResult):
    """Monat muss 1-12, Stunde 0-23 sein."""
    cur.execute("""
        SELECT COUNT(*) FROM unfaelle
        WHERE monat IS NOT NULL AND (monat < 1 OR monat > 12)
    """)
    ungueltige_monate = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM unfaelle
        WHERE stunde IS NOT NULL AND (stunde < 0 OR stunde > 23)
    """)
    ungueltige_stunden = cur.fetchone()[0]

    if ungueltige_monate == 0:
        result.add_ok("Monat-Werte gültig (1-12)")
    else:
        result.add_fehler("Ungültige Monat-Werte", f"{ungueltige_monate} Zeilen außerhalb 1-12")

    if ungueltige_stunden == 0:
        result.add_ok("Stunde-Werte gültig (0-23)")
    else:
        result.add_fehler("Ungültige Stunde-Werte", f"{ungueltige_stunden} Zeilen außerhalb 0-23")


def check_kategorie_bereich(cur, result: CheckResult):
    """Unfallkategorie sollte 1-3 sein (Getötete, Schwerverletzte, Leichtverletzte)."""
    cur.execute("""
        SELECT kategorie, COUNT(*)
        FROM unfaelle
        WHERE kategorie IS NOT NULL
        GROUP BY kategorie
        ORDER BY kategorie
    """)
    rows = cur.fetchall()
    unerwartete = [k for k, _ in rows if k not in (1, 2, 3)]

    if not unerwartete:
        verteilung = ", ".join(f"{k}={c:,}" for k, c in rows)
        result.add_ok("Kategorie-Werte im Bereich 1-3", verteilung)
    else:
        result.add_warnung("Unerwartete Kategorie-Werte", f"{unerwartete}")


def check_einwohner_plausibel(cur, result: CheckResult):
    """Einwohnerzahlen sollten positiv und nicht unrealistisch groß sein."""
    cur.execute("""
        SELECT COUNT(*) FROM bevoelkerung
        WHERE einwohner <= 0 OR einwohner > 20000000
    """)
    unplausibel = cur.fetchone()[0]

    if unplausibel == 0:
        result.add_ok("Einwohnerzahlen plausibel")
    else:
        result.add_fehler("Unplausible Einwohnerzahlen", f"{unplausibel} Zeilen ≤0 oder >20 Mio.")


# ─── Referenzielle Integrität ────────────────────────────────────────────────

def check_region_id_referenz(cur, result: CheckResult):
    """Jede gesetzte region_id muss tatsächlich in regionen existieren (FK sollte das erzwingen)."""
    cur.execute("""
        SELECT COUNT(*)
        FROM unfaelle u
        LEFT JOIN regionen r ON u.region_id = r.region_id
        WHERE u.region_id IS NOT NULL AND r.region_id IS NULL
    """)
    verwaist = cur.fetchone()[0]
    if verwaist == 0:
        result.add_ok("Keine verwaisten region_id-Referenzen in unfaelle")
    else:
        result.add_fehler("Verwaiste region_id", f"{verwaist} Unfälle ohne gültige Region")


def check_parent_ags_referenz(cur, result: CheckResult):
    """parent_ags sollte (sofern gesetzt) auf ein existierendes Bundesland verweisen."""
    cur.execute("""
        SELECT COUNT(*)
        FROM regionen child
        WHERE child.parent_ags IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM regionen parent
              WHERE parent.ags = child.parent_ags
                AND parent.level = 'bundesland'
          )
    """)
    verwaist = cur.fetchone()[0]
    if verwaist == 0:
        result.add_ok("Alle parent_ags verweisen auf existierende Bundesländer")
    else:
        result.add_warnung("Verwaiste parent_ags", f"{verwaist} Regionen ohne gültiges Elternbundesland")


def check_bevoelkerung_region_referenz(cur, result: CheckResult):
    """Jede region_id in bevoelkerung muss in regionen existieren."""
    cur.execute("""
        SELECT COUNT(*)
        FROM bevoelkerung b
        LEFT JOIN regionen r ON b.region_id = r.region_id
        WHERE r.region_id IS NULL
    """)
    verwaist = cur.fetchone()[0]
    if verwaist == 0:
        result.add_ok("Keine verwaisten region_id-Referenzen in bevoelkerung")
    else:
        result.add_fehler("Verwaiste Bevölkerungsdaten", f"{verwaist} Zeilen ohne gültige Region")


# ─── Duplikate ───────────────────────────────────────────────────────────────

def check_duplikate_extern_id(cur, result: CheckResult):
    """extern_id ist UNIQUE NOT NULL — sollte strukturell unmöglich sein, trotzdem prüfen."""
    cur.execute("""
        SELECT extern_id, COUNT(*)
        FROM unfaelle
        GROUP BY extern_id
        HAVING COUNT(*) > 1
    """)
    duplikate = cur.fetchall()
    if not duplikate:
        result.add_ok("Keine doppelten extern_id in unfaelle")
    else:
        result.add_fehler("Doppelte extern_id gefunden", f"{len(duplikate)} Fälle")


def check_duplikate_bevoelkerung(cur, result: CheckResult):
    """(region_id, jahr) ist UNIQUE — sollte strukturell unmöglich sein, trotzdem prüfen."""
    cur.execute("""
        SELECT region_id, jahr, COUNT(*)
        FROM bevoelkerung
        GROUP BY region_id, jahr
        HAVING COUNT(*) > 1
    """)
    duplikate = cur.fetchall()
    if not duplikate:
        result.add_ok("Keine doppelten (region_id, jahr) in bevoelkerung")
    else:
        result.add_fehler("Doppelte Bevölkerungseinträge", f"{len(duplikate)} Fälle")


# ─── Geodaten ────────────────────────────────────────────────────────────────

def check_geometrien_gueltig(cur, result: CheckResult):
    """Alle gespeicherten Geometrien sollten laut PostGIS gültig sein (ST_IsValid)."""
    cur.execute("""
        SELECT COUNT(*) FROM regionen
        WHERE geometrie IS NOT NULL AND NOT ST_IsValid(geometrie)
    """)
    ungueltig = cur.fetchone()[0]
    if ungueltig == 0:
        result.add_ok("Alle Regionsgeometrien gültig (ST_IsValid)")
    else:
        result.add_fehler("Ungültige Geometrien", f"{ungueltig} Regionen mit ST_IsValid = false")


def check_koordinaten_in_deutschland(cur, result: CheckResult):
    """
    Grobe Plausibilitätsprüfung: liegen die Unfallkoordinaten im
    geografischen Bereich Deutschlands (5.5–15.5° Ost, 47–55.5° Nord)?
    """
    cur.execute("""
        SELECT COUNT(*) FROM unfaelle
        WHERE geom IS NOT NULL
          AND (ST_X(geom) < 5.5 OR ST_X(geom) > 15.5
               OR ST_Y(geom) < 47.0 OR ST_Y(geom) > 55.5)
    """)
    ausserhalb = cur.fetchone()[0]
    if ausserhalb == 0:
        result.add_ok("Alle Unfallkoordinaten innerhalb Deutschlands")
    else:
        result.add_warnung("Koordinaten außerhalb Deutschlands", f"{ausserhalb} Zeilen")


# ─── Konsistenz zwischen Quellen ──────────────────────────────────────────────

def check_unfaelle_ohne_bevoelkerungsdaten(cur, result: CheckResult):
    """
    Informativ: für wie viele Kreise mit Unfällen liegen keine
    Bevölkerungsdaten vor (betrifft /per-capita).
    """
    cur.execute("""
        SELECT COUNT(DISTINCT r.region_id)
        FROM regionen r
        JOIN unfaelle u ON u.region_id = r.region_id
        WHERE r.level = 'kreis'
          AND NOT EXISTS (
              SELECT 1 FROM bevoelkerung b WHERE b.region_id = r.region_id
          )
    """)
    fehlend = cur.fetchone()[0]
    if fehlend == 0:
        result.add_ok("Alle Kreise mit Unfällen haben Bevölkerungsdaten")
    else:
        result.add_warnung(
            "Kreise ohne Bevölkerungsdaten",
            f"{fehlend} Kreise — /per-capita liefert dort 404"
        )


# ─── Ausführung ──────────────────────────────────────────────────────────────

def run_checks() -> dict:
    """
    Führt alle Plausibilitätsprüfungen aus und gibt eine Zusammenfassung zurück.
    Wird nach jedem ETL-Lauf aufgerufen (siehe data/etl/main.py).
    """
    print("\n=== Plausibilitätsprüfungen ===")

    conn = create_connection()
    cur = conn.cursor()
    result = CheckResult()

    try:
        print("\n-- Vollständigkeit --")
        check_grunddaten_vorhanden(cur, result)
        check_unfaelle_geodaten(cur, result)

        print("\n-- Wertebereiche --")
        check_jahr_plausibel(cur, result)
        check_monat_stunde_bereich(cur, result)
        check_kategorie_bereich(cur, result)
        check_einwohner_plausibel(cur, result)

        print("\n-- Referenzielle Integrität --")
        check_region_id_referenz(cur, result)
        check_parent_ags_referenz(cur, result)
        check_bevoelkerung_region_referenz(cur, result)

        print("\n-- Duplikate --")
        check_duplikate_extern_id(cur, result)
        check_duplikate_bevoelkerung(cur, result)

        print("\n-- Geodaten --")
        check_geometrien_gueltig(cur, result)
        check_koordinaten_in_deutschland(cur, result)

        print("\n-- Quellenübergreifende Konsistenz --")
        check_unfaelle_ohne_bevoelkerungsdaten(cur, result)

    finally:
        cur.close()
        conn.close()

    summary = result.summary()
    print(f"\n=== Ergebnis: {summary['ok']} OK, "
          f"{summary['warnungen']} Warnungen, "
          f"{summary['fehler']} Fehler ===")
    print(f"Gesamtstatus: {summary['status'].upper()}\n")

    return summary


if __name__ == "__main__":
    run_checks()