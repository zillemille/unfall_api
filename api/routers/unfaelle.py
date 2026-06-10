from fastapi import APIRouter

from api.db.queries import (
    get_earliest_year,
    get_accident_count,
    get_available_years,
    get_pedestrian_accidents,
    get_accident_aggregates
)

router = APIRouter(prefix="/accidents", tags=["Accidents"])


@router.get("/earliest")
def earliest():
    return {
        "earliest_year": get_earliest_year()
    }


@router.get("/count")
def count(state: str, year: int):
    return {
        "state": state,
        "year": year,
        "count": get_accident_count(state, year)
    }


@router.get("/years")
def years(state: str):
    return {
        "state": state,
        "years": get_available_years(state)
    }


@router.get("/pedestrian")
def pedestrian(city: str, year: int):
    return {
        "city": city,
        "year": year,
        "count": get_pedestrian_accidents(city, year)
    }


@router.get("/aggregates")
def aggregates(
        level: str,
        year: int,
        category: int
):
    return {
        "data": get_accident_aggregates(
            level,
            year,
            category
        )
    }