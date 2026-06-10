from fastapi import APIRouter

from api.db.queries import get_per_capita

router = APIRouter(prefix="/regions", tags=["Regions"])


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