from etl import unfallatlas, regionalatlas, genesis, checks


def run_step(name, func):

    print(f"\n=== {name} ===")

    try:
        func()
        print(f"{name} erfolgreich")

    except Exception as e:
        print(f"{name} fehlgeschlagen")
        print(e)


def main():

    run_step("Unfallatlas", unfallatlas.main)
    run_step("Regionalatlas", regionalatlas.main)
    run_step("GENESIS", genesis.main)

    # WARUM FUNKTIONIERST DU HIER NCIHT??????
    # todo: zum laufen bekommen
    run_step("checks",checks.run_checks())


if __name__ == "__main__":
    main()