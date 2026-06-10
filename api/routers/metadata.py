from fastapi import APIRouter

from api.db.queries import (
    get_sources,
    get_import_runs
)

router = APIRouter(prefix="/metadata", tags=["Metadata"])


@router.get("/sources")
def sources():
    return {
        "sources": get_sources()
    }


@router.get("/imports")
def imports():
    return {
        "imports": get_import_runs()
    }