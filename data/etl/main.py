from data.etl import genesis_bl, regionalatlas, unfallatlas, checks, genesis_kreis


def run_step(name, func):

    print(f"\n=== {name} ===")

    try:
        func()
        print(f"{name} erfolgreich")

    except Exception as e:
        print(f"{name} fehlgeschlagen")
        print(e)


def main():
    run_step("Regionalatlas", regionalatlas.main)
    run_step("Unfallatlas", unfallatlas.main)
    run_step("GENESIS Bundesländer", genesis_bl.main)
    run_step("GENESIS Kreise", genesis_kreis.main)

    print(f"\n=== Checks ===")
    summary = checks.run_checks()
    if summary["status"] == "fehler":
        print("⚠ ETL abgeschlossen, aber Datenqualität weist Fehler auf — siehe oben.")


if __name__ == "__main__":
    main()