from fastapi import APIRouter, Query

from api.db.queries import get_per_capita, search_regions

router = APIRouter(prefix="/regions", tags=["Regionen"])


@router.get("/per-capita")
def per_capita(region: str, year: int):
    return {
        "region": region,
        "year": year,
        "accidents_per_100k": get_per_capita(
            region,
            year
        )
    }


@router.get(
    "/",
    summary="Regionen suchen",
    description="""
Sucht Regionen per Name (Teilstring) oder AGS-Präfix.
Gibt AGS zurück, der für alle anderen Endpunkte verwendet werden kann.

**Typischer Client-Flow:**
1. Nutzer gibt "Sachsen" ein → dieser Endpunkt
2. Client erhält `ags_prefix = "14"`
3. Client nutzt `14` für `/accidents/count`, `/accidents/trend` etc.
    """,
)
def regions(
    name:       str | None = Query(default=None, description="Teilstring-Suche, z.B. 'Sach'"),
    level:      str | None = Query(default=None, description="'bundesland' oder 'kreis'"),
    ags_prefix: str | None = Query(default=None, description="AGS-Präfix, z.B. '14'"),
):
    return {"regions": search_regions(name, level, ags_prefix)}