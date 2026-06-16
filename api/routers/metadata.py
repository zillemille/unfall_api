from fastapi import APIRouter
from api.db.queries import get_sources, get_import_runs

router = APIRouter(tags=["Metadaten"])


@router.get(
    "/sources",
    summary="Datenquellen und Lizenzen",
    description="""
Gibt alle verwendeten Datenquellen mit ihren Lizenzangaben zurück.

Alle Datensätze stehen unter der
**Datenlizenz Deutschland – Namensnennung – Version 2.0** (dl-de/by-2-0).

Bei Weiterverwendung ist folgender Quellenvermerk erforderlich:
- Bezeichnung des Bereitstellers
- Hinweis auf dl-de/by-2-0
- Verweis auf den Originaldatensatz
- Bei Veränderungen: Hinweis dass Daten geändert wurden
    """,
)
def sources():
    return {
        "lizenzhinweis": (
            "Die verwendeten Daten wurden verändert und zusammengeführt. "
            "Originalquellen und Lizenzen siehe 'quellen'."
        ),
        "quellen": get_sources(),
    }


@router.get(
    "/imports",
    summary="Import-Protokoll",
    description="Zeigt alle ETL-Läufe mit Status und Zählern.",
)
def imports():
    return {"imports": get_import_runs()}