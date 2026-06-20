from fastapi import APIRouter, Query
from api.db.queries import get_map_region, get_accident_points, get_license_note, validate_ags

router = APIRouter(prefix="/map", tags=["Karte"])


@router.get("/region", summary="Geometrie einer Region")
def map_region(ags_prefix: str = Query(examples=["14"])):
    validate_ags(ags_prefix)
    return {
        "map":      get_map_region(ags_prefix),
        "_lizenz":  get_license_note("regionalatlas"),
    }


@router.get("/accidents", summary="Unfallpunkte für Kartenansicht")
def map_accidents(
    ags_prefix: str       = Query(examples=["14"]),
    year:       int       = Query(ge=2000, le=2100, examples=[2024]),
    kategorie:  int | None = Query(default=None, ge=1, le=3),
    limit:      int       = Query(default=2000, ge=1, le=5000),
):
    validate_ags(ags_prefix)
    points = get_accident_points(ags_prefix, year, kategorie, limit)
    return {
        "ags_prefix": ags_prefix,
        "year":       year,
        "count":      len(points),
        "punkte":     points,
        "_lizenz":    get_license_note("unfallatlas", "regionalatlas"),
    }