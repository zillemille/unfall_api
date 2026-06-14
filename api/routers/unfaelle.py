"""
Router: /accidents

Endpunkte für Unfallstatistiken auf Basis des Unfallatlas-Datensatzes.
Alle Gebietsangaben erfolgen über AGS-Präfixe (Amtlicher Gemeindeschlüssel)
oder Regionsnamen aus der Tabelle `regionen`.

AGS-Präfixe wichtiger Bundesländer:
    05 = Nordrhein-Westfalen
    11 = Berlin
    13 = Mecklenburg-Vorpommern
    14 = Sachsen
"""

from fastapi import APIRouter, HTTPException, Query

from api.db.queries import (
    get_earliest_year,
    get_accident_count,
    get_available_years,
    get_pedestrian_accidents,
    get_accident_aggregates,
    get_per_capita,
    get_accident_density,
    get_trend,
    get_top_regions,
    get_zero_accident_regions,
)

from api.models.response import (
    EarliestYearResponse,
    AccidentCountResponse,
    AvailableYearsResponse,
    PedestrianAccidentsResponse,
    AggregatesResponse,
    RegionAggregate,
    PerCapitaResponse,
    AccidentDensityResponse,
)

router = APIRouter(prefix="/accidents", tags=["Unfälle"])

_VALID_LEVELS = {"bundesland", "kreis", "gemeinde"}


# ─── Hilfsfunktion ───────────────────────────────────────────────────────────

def _require_level(level: str) -> None:
    if level not in _VALID_LEVELS:
        raise HTTPException(
            status_code=422,
            detail=f"Ungültiger Level '{level}'. Erlaubt: {sorted(_VALID_LEVELS)}"
        )


# ─── Endpunkte ───────────────────────────────────────────────────────────────

@router.get(
    "/earliest",
    response_model=EarliestYearResponse,
    summary="Frühestes Datenjahr",
    description="""
Gibt das früheste Jahr zurück, für das Unfalldaten vorliegen.

- Ohne `ags_prefix`: global über alle Bundesländer
- Mit `ags_prefix`: nur für die angegebene Region

**Beispiele:**
- Frühestes Jahr gesamt: `/accidents/earliest`
- Frühestes Jahr NRW:    `/accidents/earliest?ags_prefix=05`
- Frühestes Jahr MV:     `/accidents/earliest?ags_prefix=13`
    """,
)
def earliest(
    ags_prefix: str | None = Query(
        default=None,
        description="AGS-Präfix des Bundeslandes, z.B. '05' für NRW.",
        examples=["05"]
    )
):
    year = get_earliest_year(ags_prefix)
    if year is None:
        detail = (
            f"Keine Daten für AGS-Präfix '{ags_prefix}'."
            if ags_prefix
            else "Keine Unfalldaten in der Datenbank vorhanden."
        )
        raise HTTPException(status_code=404, detail=detail)
    return EarliestYearResponse(earliest_year=year)


@router.get(
    "/count",
    response_model=AccidentCountResponse,
    summary="Unfallanzahl mit allen Filtern",
    description="""
Zählt Unfälle für eine Region mit optionalen Filtern.

**Unfallkategorien:**
- `1` = Unfall mit Getöteten
- `2` = Unfall mit Schwerverletzten
- `3` = Unfall mit Leichtverletzten

**Beteiligte:** `ist_rad`, `ist_fuss`, `ist_pkw`, `ist_kraftrad` als Boolean-Filter.
    """,
)
def count(
    ags_prefix: str  = Query(examples=["14"]),
    year:       int  = Query(ge=2000, le=2100),
    kategorien: list[int] | None = Query(default=None, ge=1, le=3),
    monat:      int  | None = Query(default=None, ge=1, le=12),
    stunde:     int  | None = Query(default=None, ge=0, le=23),
    ist_rad:      bool | None = Query(default=None),
    ist_fuss:     bool | None = Query(default=None),
    ist_pkw:      bool | None = Query(default=None),
    ist_kraftrad: bool | None = Query(default=None),
):
    result = get_accident_count(
        ags_prefix, year, kategorien, monat, stunde,
        ist_rad, ist_fuss, ist_pkw, ist_kraftrad
    )
    return AccidentCountResponse(
        region=ags_prefix, year=year,
        kategorie=kategorien, count=result
    )


@router.get(
    "/years",
    response_model=AvailableYearsResponse,
    summary="Verfügbare Datenjahre je Bundesland",
    description="Gibt alle Jahre zurück, für die in einer Region mindestens ein Unfall erfasst ist.",
)
def years(
    ags_prefix: str = Query(
        description="AGS-Präfix, z.B. '05' für NRW oder '13' für Mecklenburg-Vorpommern.",
        examples=["05"]
    )
):
    result = get_available_years(ags_prefix)
    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"Keine Daten für AGS-Präfix '{ags_prefix}' gefunden. "
                   f"Bitte AGS-Präfix prüfen (z.B. '14' für Sachsen)."
        )
    return AvailableYearsResponse(ags_prefix=ags_prefix, years=result)


@router.get(
    "/pedestrian",
    response_model=PedestrianAccidentsResponse,
    summary="Fußgängerunfälle je Region und Jahr",
    description=(
        "Zählt Unfälle mit Fußgängerbeteiligung (`ist_fuss = true`) "
        "für eine benannte Region. Der Name muss exakt dem Eintrag "
        "in der Tabelle `regionen` entsprechen."
    ),
)
def pedestrian(
    region: str = Query(
        description="Exakter Regionsname, z.B. 'Berlin' oder 'Dresden'.",
        examples=["Berlin"]
    ),
    year: int = Query(
        ge=2000, le=2100,
        examples=[2023]
    ),
):
    result = get_pedestrian_accidents(region, year)
    # 0 ist ein valides Ergebnis — keine 404
    return PedestrianAccidentsResponse(region=region, year=year, count=result)


@router.get(
    "/aggregates",
    response_model=AggregatesResponse,
    summary="Unfälle aggregiert nach Regionslevel",
    description=(
        "Gibt Unfallzahlen gruppiert nach Regionslevel zurück, "
        "absteigend sortiert. "
        "Levels: `bundesland`, `kreis`."
    ),
)
def aggregates(
    level: str = Query(
        description="Aggregationsebene: 'bundesland', 'kreis' oder 'gemeinde'.",
        examples=["kreis"]
    ),
    year: int = Query(ge=2000, le=2100, examples=[2023]),
    kategorie: int | None = Query(
        default=None,
        description="Unfallkategorie (1–3). Ohne Angabe: alle.",
        ge=1, le=3
    ),
):
    _require_level(level)
    rows = get_accident_aggregates(level, year, kategorie)
    return AggregatesResponse(
        level=level,
        year=year,
        kategorie=kategorie,
        data=[RegionAggregate(**row) for row in rows],
    )


@router.get(
    "/per-capita",
    response_model=PerCapitaResponse,
    summary="Unfälle je 100.000 Einwohner",
    description=(
        "Kombiniert Unfall- und Bevölkerungsdaten. "
        "Gibt None zurück wenn für das Jahr keine Bevölkerungszahl hinterlegt ist."
    ),
)
def per_capita(
    region: str = Query(description="Exakter Regionsname.", examples=["Sachsen"]),
    year:   int = Query(ge=2000, le=2100, examples=[2023]),
):
    result = get_per_capita(region, year)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Keine Bevölkerungsdaten für '{region}' im Jahr {year}."
        )

    unfaelle_pro_100k, bev_jahr = result

    return PerCapitaResponse(
        region=region,
        year=year,
        unfaelle_pro_100k=unfaelle_pro_100k,
        bevoelkerung_jahr=bev_jahr,
    )


@router.get(
    "/density",
    response_model=AccidentDensityResponse,
    summary="Unfälle je km² (räumliche Dichte)",
    description=(
        "Berechnet die Unfalldichte pro Quadratkilometer auf Basis "
        "der PostGIS-Geometrien aus `regionen`. "
        "Levels: `bundesland` oder `kreis`."
    ),
)
def density(
    year:  int = Query(ge=2000, le=2100, examples=[2023]),
    level: str = Query(default="kreis", examples=["kreis"]),
):
    if level not in ("bundesland", "kreis"):
        raise HTTPException(
            status_code=422,
            detail=f"Level '{level}' für Dichte-Abfrage nicht unterstützt. "
                   f"Erlaubt: 'bundesland', 'kreis'."
        )
    rows = get_accident_density(year, level)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Keine Daten für Jahr {year} auf Level '{level}'."
        )
    return AccidentDensityResponse(level=level, year=year, data=rows)

@router.get(
    "/trend",
    summary="Jahrestrend für eine Region",
    description="Unfallzahlen pro Jahr inkl. Veränderung zum Vorjahr.",
)
def trend(
    ags_prefix: str = Query(examples=["14"]),
    von_jahr:   int = Query(ge=2000, le=2100, examples=[2018]),
    bis_jahr:   int = Query(ge=2000, le=2100, examples=[2023]),
    kategorie:  int | None = Query(default=None, ge=1, le=3),
):
    if von_jahr > bis_jahr:
        raise HTTPException(
            status_code=422,
            detail=f"von_jahr ({von_jahr}) muss ≤ bis_jahr ({bis_jahr}) sein."
        )
    rows = get_trend(ags_prefix, von_jahr, bis_jahr, kategorie)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Keine Daten für AGS '{ags_prefix}' zwischen {von_jahr} und {bis_jahr}."
        )
    return {"ags_prefix": ags_prefix, "trend": rows}


@router.get(
    "/top",
    summary="Top-N Regionen nach Unfallzahl",
    description="""
Rangliste der unfallreichsten Regionen.

Beispielaufruf für *„5 schlimmste Landkreise mit Todesunfällen 2024"*:
`/accidents/top?level=kreis&year=2024&kategorie=1&limit=5`

Mit `ags_prefix=14` wird die Suche auf Sachsen eingeschränkt.
    """,
)
def top(
    level:      str = Query(examples=["kreis"]),
    year:       int = Query(ge=2000, le=2100),
    kategorie:  int | None = Query(default=None, ge=1, le=3),
    limit:      int = Query(default=5, ge=1, le=100),
    ags_prefix: str | None = Query(default=None, examples=["14"]),
):
    _require_level(level)
    rows = get_top_regions(level, year, kategorie, limit, ags_prefix)
    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Keine Daten für Level '{level}', Jahr {year}."
        )
    return {"level": level, "year": year, "ranking": rows}


@router.get(
    "/zero-accidents",
    summary="Regionen ohne Unfälle",
    description="""
Gibt alle Gemeinden (oder Kreise) zurück, für die im angegebenen Jahr
**kein einziger Unfall** erfasst wurde.

Erfordert vollständige Regionsreferenz via `LEFT JOIN` auf `regionen` —
ein einfaches Filtern der Unfalltabelle würde diese Fälle nie liefern.
    """,
)
def zero_accidents(
    year:       int = Query(ge=2000, le=2100),
    ags_prefix: str = Query(
        description="Bundesland eingrenzen, z.B. '14' für Sachsen.",
        examples=["14"]
    ),
    level: str = Query(default="gemeinde"),
):
    if level == "bundesland":
        raise HTTPException(
            status_code=422,
            detail="level=bundesland nicht unterstützt. Verwende 'kreis."
        )
    _require_level(level)
    rows = get_zero_accident_regions(year, ags_prefix, level)
    return {
        "year":       year,
        "ags_prefix": ags_prefix,
        "level":      level,
        "count":      len(rows),
        "regions":    rows,
    }