from fastapi import APIRouter, Query

from api.db.queries import search_regions, get_license_note, validate_ags

router = APIRouter(prefix="/regions", tags=["Regionen"])


@router.get(
    "/",
    summary="Regionen suchen",
    description="""
Sucht Regionen per Name (Teilstring) oder AGS-Präfix.
Gibt AGS zurück, der für alle anderen Endpunkte verwendet werden kann.

**Beispielhafter Client-Flow:**
1. Nutzer gibt "Sachsen" ein → dieser Endpunkt
2. Client erhält `ags_prefix = "14"`
3. Client nutzt `14` für `/accidents/count`, `/accidents/trend` etc.

Gibt eine leere Liste zurück, wenn keine Region dem Suchbegriff entspricht.
    """,
)
def regions(
    name:       str | None = Query(default=None, description="Teilstring-Suche, z.B. 'Sach'"),
    level:      str | None = Query(default=None, description="'bundesland' oder 'kreis'"),
    ags_prefix: str | None = Query(default=None, description="AGS-Präfix, z.B. '14'"),
):
    validate_ags(ags_prefix)
    return {
        "regions": search_regions(name, level, ags_prefix),
        "_lizenz": get_license_note("regionalatlas")
    }