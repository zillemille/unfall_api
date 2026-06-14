"""
Pydantic-Modelle für alle API-Antworten.
"""

from pydantic import BaseModel, Field


class EarliestYearResponse(BaseModel):
    earliest_year: int | None = Field(
        description="Frühestes Jahr, für das Unfalldaten vorliegen.",
        examples=[2016]
    )


class AccidentCountResponse(BaseModel):
    region:     str = Field(description="AGS-Präfix der Region")
    year:       int = Field(description="Abfragejahr", examples=[2023])
    kategorie:  list[int] | None = Field(
        default=None,
        description="Unfallkategorien (1=Getötete, 2=Schwerverletzte, 3=Leichtverletzte)."
    )
    count:      int = Field(description="Anzahl der Unfälle")


class AvailableYearsResponse(BaseModel):
    ags_prefix: str  = Field(description="AGS-Präfix des Bundeslandes, z.B. '14' für Sachsen")
    years:      list[int] = Field(description="Sortierte Liste verfügbarer Datenjahre")


class PedestrianAccidentsResponse(BaseModel):
    region: str = Field(description="Name der Region (Gemeinde, Kreis, …)")
    year:   int
    count:  int = Field(description="Anzahl der Unfälle mit Fußgängerbeteiligung")


class RegionAggregate(BaseModel):
    ags:      str = Field(description="Amtlicher Gemeindeschlüssel")
    name:     str = Field(description="Name der Region")
    unfaelle: int = Field(description="Anzahl der Unfälle")


class AggregatesResponse(BaseModel):
    level:     str = Field(description="Aggregationsebene: 'bundesland' oder 'kreis'")
    year:      int
    kategorie: int | None
    data:      list[RegionAggregate]


class PerCapitaResponse(BaseModel):
    region:             str
    year:               int
    unfaelle_pro_100k:  float | None
    bevoelkerung_jahr:  int | None = Field(
        default=None,
        description="Jahr der verwendeten Bevölkerungsdaten — "
                    "kann vom Abfragejahr abweichen."
    )


class AccidentDensityEntry(BaseModel):
    name:               str
    unfaelle:           int
    flaeche_km2:        float
    unfaelle_pro_km2:   float


class AccidentDensityResponse(BaseModel):
    level:  str
    year:   int
    data:   list[AccidentDensityEntry]