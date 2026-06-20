"""
Streamlit-Dashboard für die Unfallatlas-API.

API-Basis-URL wird über die Umgebungsvariable API_URL gesetzt,
Standard: http://localhost:8000 (lokale Entwicklung).
"""

import os
import requests
import streamlit as st
import folium
from streamlit_folium import st_folium
import json
import plotly.express as px
import pandas as pd

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ─── Hilfsfunktion ───────────────────────────────────────────────────────────

@st.cache_data(ttl=5*60)
def cached_api_get(path: str, **kwargs):
    return api_get(path, params=kwargs if kwargs else None)


def api_get(path: str, params: dict = None):
    """
    GET-Request an die API. Gibt (data, error) zurück.
    data ist None bei Fehler, error ist None bei Erfolg.
    """
    try:
        resp = requests.get(f"{API_URL}{path}", params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json(), None
        else:
            detail = resp.json().get("detail", resp.text)
            return None, f"HTTP {resp.status_code}: {detail}"
    except requests.exceptions.ConnectionError:
        return None, f"API nicht erreichbar unter {API_URL}"
    except Exception as e:
        return None, str(e)


def render_lizenz(lizenz: dict):
    """Kompakte, einheitliche Lizenzanzeige für alle Endpunkte."""
    if not lizenz:
        return
    with st.expander("📄 Quellen & Lizenz", expanded=False):
        st.caption(
            f"**{lizenz.get('lizenz', '')}** ({lizenz.get('lizenz_id', '')})  \n"
            f"[Lizenztext]({lizenz.get('lizenz_url', '')})"
        )
        for q in lizenz.get("quellen", []):
            st.caption(f"• {q}")
        if lizenz.get("hinweis"):
            st.caption(f"_{lizenz['hinweis']}_")


def display_response(data: dict, error: str):
    """
    Erkennt anhand der Antwortstruktur das passende Darstellungsformat
    und rendert entsprechend — Metrik, Tabelle oder Diagramm.
    """
    if error:
        st.error(error)
        return

    if data is None:
        st.info("Keine Daten.")
        return

    # ─── Einzelwert-Antworten → st.metric ────────────────────────────
    if "earliest_year" in data:
        st.metric("Frühestes Jahr", data["earliest_year"])

    elif "unfaelle_pro_100k" in data:
        col1, col2 = st.columns(2)
        col1.metric("Unfälle je 100.000 Einwohner", data["unfaelle_pro_100k"])
        col2.metric("Bevölkerungsjahr", data.get("bevoelkerung_jahr", "—"))

    elif "count" in data and "kategorie" in data:
        st.metric(f"Unfälle ({data.get('region', '')}, {data.get('year', '')})", data["count"])

    elif "count" in data and "punkte" not in data:
        st.metric("Anzahl", data["count"])

    # ─── Jahreslisten → Tabelle ───────────────────────────────────────
    elif "years" in data:
        st.write(f"**{len(data['years'])} Jahre verfügbar** ({data.get('ags_prefix', '')})")
        st.dataframe(pd.DataFrame({"Jahr": data["years"]}), use_container_width=True, hide_index=True)

    # ─── Trend → Liniendiagramm + Tabelle ─────────────────────────────
    elif "trend" in data:
        df = pd.DataFrame(data["trend"])
        if not df.empty:
            fig = px.line(
                df, x="jahr", y="unfaelle", markers=True,
                title=f"Unfalltrend {data.get('ags_prefix', '')}",
                labels={"jahr": "Jahr", "unfaelle": "Anzahl Unfälle"},
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Trenddaten.")

    # ─── Top-N / Ranking → Balkendiagramm + Tabelle ───────────────────
    elif "ranking" in data:
        df = pd.DataFrame(data["ranking"])
        if not df.empty:
            fig = px.bar(
                df, x="unfaelle", y="name", orientation="h",
                title=f"Top {len(df)} — {data.get('year', '')}",
                labels={"unfaelle": "Unfälle", "name": "Region"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Ranking-Daten.")

    # ─── Aggregates → Balkendiagramm + Tabelle ────────────────────────
    elif "data" in data and isinstance(data["data"], list):
        df = pd.DataFrame(data["data"])
        if not df.empty and "unfaelle" in df.columns:
            fig = px.bar(
                df.sort_values("unfaelle", ascending=True),
                x="unfaelle", y="name", orientation="h",
                title=f"Unfälle nach {data.get('level', '')} — {data.get('year', '')}",
            )
            st.plotly_chart(fig, use_container_width=True)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Daten.")

    # ─── Regionen-Liste (Suche oder Zero-Accidents) → Tabelle ─────────
    elif "regions" in data:
        df = pd.DataFrame(data["regions"])
        st.write(f"**{len(df)} Treffer**")
        if not df.empty:
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("Keine Treffer.")

    # ─── Fallback: rohes JSON ──────────────────────────────────────────
    else:
        st.json(data)

    # ─── Lizenz immer am Ende, einheitlich ─────────────────────────────
    if "_lizenz" in data:
        render_lizenz(data["_lizenz"])


# ─── Layout ──────────────────────────────────────────────────────────────────
if "map_data" not in st.session_state:
    st.session_state["map_data"] = None


st.set_page_config(
    page_title="Unfallatlas Dashboard",
    layout="centered",
)

st.title("Unfallatlas Dashboard")
st.caption(f"API: `{API_URL}`")
st.divider()


# ─── Pflichtfragen ───────────────────────────────────────────────────────────

st.header("Pflichtfragen")

# 1 — Frühestes Unfalljahr
with st.expander("Was ist das früheste Unfalljahr im gesamten Datensatz?"):
    if st.button("Abfragen", key="earliest"):
        data, error = cached_api_get("/accidents/earliest")
        display_response(data, error)

# 2 — Unfälle mit Personenschäden 2023 in Sachsen
with st.expander("Wie viele Unfälle mit Personenschäden ereigneten sich 2023 in Sachsen?"):
    if st.button("Abfragen", key="sachsen_2023"):
        data, error = cached_api_get("/accidents/count", ags_prefix="14", year=2023)
        display_response(data, error)

# 3 — Daten ab wann für NRW
with st.expander("Ab welchem Jahr sind Daten für Nordrhein-Westfalen verfügbar?"):
    if st.button("Abfragen", key="nrw_years"):
        data, error = cached_api_get("/accidents/earliest", ags_prefix="05")
        display_response(data, error)

# 4 — Daten ab wann für MV
with st.expander("Ab welchem Jahr sind Daten für Mecklenburg-Vorpommern verfügbar?"):
    if st.button("Abfragen", key="mv_years"):
        data, error = cached_api_get("/accidents/earliest", ags_prefix="13")
        display_response(data, error)

# 5 — Fußgängerunfälle 2023 in Berlin
with st.expander("Wie viele Unfälle mit Fußgängerbeteiligung ereigneten sich 2023 in Berlin?"):
    if st.button("Abfragen", key="berlin_fuss"):
        data, error = cached_api_get(
            "/accidents/count",
            ags_prefix="11", year=2023, ist_fuss=True
        )
        display_response(data, error)

st.divider()

# ─── Multi-Source-Fragen ─────────────────────────────────────────────────────

st.header("Multi-Source-Abfragen")

# 6 — Unfälle je 100.000 Einwohner
with st.expander("Unfälle je 100.000 Einwohner"):
    col1, col2 = st.columns(2)
    region_pc = col1.text_input("AGS-Präfix", value="14", key="pc_region")
    year_pc   = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="pc_year")
    if st.button("Abfragen", key="per_capita"):
        data, error = cached_api_get("/accidents/per-capita", ags_prefix=region_pc, year=year_pc)
        display_response(data, error)

# 7 — Unfalldichte je km²
with st.expander("Unfalldichte je km²"):
    col1, col2 = st.columns(2)
    level_d = col1.selectbox("Level", ["kreis", "bundesland"], key="density_level")
    year_d  = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="density_year")
    if st.button("Abfragen", key="density"):
        data, error = cached_api_get("/accidents/density", level=level_d, year=year_d)
        display_response(data, error)

st.divider()

# ─── Bonus-Abfragen ──────────────────────────────────────────────────────────

st.header("Weitere Abfragen")


# Kreise ohne Unfälle
with st.expander("(Bonus) Kreise ohne Unfälle in einem Jahr"):
    col1, col2 = st.columns(2)
    ags_z  = col1.text_input("AGS-Präfix (Bundesland)", value="14", key="zero_ags")
    year_z = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="zero_year")
    if st.button("Abfragen", key="zero"):
        data, error = cached_api_get("/accidents/zero-accidents", ags_prefix=ags_z, year=year_z, level="kreis")
        display_response(data, error)


# ──────── nützliche Abfragen ────────────────────────────

st.header("nützliche Abfragen")

with st.expander("Ags zu Regionennamen bekommen"):
    region_name = st.text_input("Regionennamen", key="region_name")
    level = st.text_input("Level", key="level")
    ags_pre = st.text_input("AGS-Präfix", key="ags_pre")
    if st.button("Abfragen", key="ags_search"):
        params = {}
        if region_name: params["name"] = region_name
        if level:       params["level"] = level
        if ags_pre:     params["ags_prefix"] = ags_pre
        data, error = api_get("/regions/", params=params)
        display_response(data, error)



# ──────────────── Map ────────────────────────────────────────────────

st.divider()
st.header("🗺️ Kartenansicht")

col1, col2, col3 = st.columns(3)
ags_map  = col1.text_input("AGS-Präfix", value="14", key="map_ags")
year_map = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="map_year")
kat_map  = col3.selectbox(
    "Kategorie",
    [None, 1, 2, 3],
    format_func=lambda x: "Alle" if x is None else {
        1: "🔴 Getötete",
        2: "🟠 Schwerverletzte",
        3: "🟡 Leichtverletzte"
    }[x],
    key="map_kat"
)

if st.button("Karte laden", key="map_btn"):

    region_data, err1 = cached_api_get("/map/region", ags_prefix=ags_map)
    accident_data, err2 = cached_api_get(
        "/map/accidents",
        ags_prefix=ags_map,
        year=year_map,
        limit=5000,
        **({"kategorie": kat_map} if kat_map is not None else {})
    )

    if err1 or err2:
        st.error(err1 or err2)
        st.session_state["map_data"] = None     # ← Fehler: alten Stand löschen
    else:
        # ← Daten im Session State speichern statt direkt rendern
        st.session_state["map_data"] = {
            "region":    region_data,
            "accidents": accident_data,
            "ags":       ags_map,
            "year":      year_map,
        }

# ← Karte wird aus Session State gerendert — bleibt nach Interact erhalten
if st.session_state.get("map_data"):
    map_data = st.session_state["map_data"]

    region_data   = map_data["region"]
    accident_data = map_data["accidents"]

    FARBEN = {1: "red", 2: "orange", 3: "yellow", None: "blue"}

    m = folium.Map(location=[51.0, 10.5], zoom_start=6)

    for feature in region_data.get("map", []):
        geojson = json.loads(feature["geojson"])
        folium.GeoJson(
            geojson,
            name=feature["name"],
            style_function=lambda _: {
                "fillColor": "transparent",
                "color":     "#3388ff",
                "weight":    2,
            },
        ).add_to(m)

    punkte = accident_data.get("punkte", [])
    for p in punkte:
        folium.CircleMarker(
            location=[p["lat"], p["lon"]],
            radius=3,
            color=FARBEN.get(p["kategorie"], "blue"),
            fill=True,
            fill_opacity=0.7,
            popup=folium.Popup(
                f"Kategorie: {p['kategorie']}<br>"
                f"Rad: {p['ist_rad']} | "
                f"Fuß: {p['ist_fuss']} | "
                f"PKW: {p['ist_pkw']}",
                max_width=200,
            ),
        ).add_to(m)

    st.caption(
        f"{len(punkte)} Unfälle angezeigt für AGS '{map_data['ags']}' "
        f"im Jahr {map_data['year']} (max. 5.000)"
    )
    st_folium(m, width=700, height=500, returned_objects=[])

    st.markdown("""
    🔴 Getötete &nbsp;&nbsp;
    🟠 Schwerverletzte &nbsp;&nbsp;
    🟡 Leichtverletzte
    """)


# ─── 1. Diagramme für Trend ──────────────────────────────────────────────────

with st.expander("Jahrestrend für eine Region"):
    col1, col2, col3 = st.columns(3)
    ags_tr = col1.text_input("AGS-Präfix", value="14", key="trend_ags")
    von_tr = col2.number_input("Von", value=2019, min_value=2000, max_value=2100, key="trend_von")
    bis_tr = col3.number_input("Bis", value=2024, min_value=2000, max_value=2100, key="trend_bis")

    if st.button("Abfragen", key="trend"):
        data, error = cached_api_get(
            "/accidents/trend",
            ags_prefix=ags_tr, von_jahr=von_tr, bis_jahr=bis_tr
        )
        if error:
            st.error(error)
        else:
            trend = data.get("trend", [])
            df = pd.DataFrame(trend)
            # Liniendiagramm statt rohem JSON
            fig = px.line(
                df, x="jahr", y="unfaelle",
                title=f"Unfalltrend {ags_tr}",
                markers=True,
                labels={"jahr": "Jahr", "unfaelle": "Anzahl Unfälle"}
            )
            st.plotly_chart(fig, use_container_width=True)
            # Veränderung zum Vorjahr als Tabelle
            st.dataframe(df[["jahr", "unfaelle", "veraenderung_zum_vorjahr"]])


# ─── 2. Balkendiagramm für Top-Regionen ──────────────────────────────────────

with st.expander("Top-N Regionen nach Unfallzahl"):
    col1, col2, col3 = st.columns(3)
    level_t = col1.selectbox("Level", ["kreis", "bundesland"], key="top_level")
    year_t  = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="top_year")
    limit_t = col3.number_input("Top N", value=10, min_value=1, max_value=50, key="top_limit")
    kat_t   = st.selectbox(                                           # ← neu
        "Kategorie (optional)",
        [None, 1, 2, 3],
        format_func=lambda x: "Alle" if x is None else {
            1: "Getötete", 2: "Schwerverletzte", 3: "Leichtverletzte"
        }[x],
        key="top_kat"
    )
    if st.button("Abfragen", key="top"):
        params = {"level": level_t, "year": year_t, "limit": limit_t}
        if kat_t:
            params["kategorie"] = kat_t
        data, error = api_get("/accidents/top", params=params)
        if error:
            st.error(error)
        else:
            ranking = data.get("ranking", [])
            df = pd.DataFrame(ranking)
            fig = px.bar(
                df, x="unfaelle", y="name",
                orientation="h",
                title=f"Top {limit_t} nach Unfallzahl {year_t}",
                labels={"unfaelle": "Unfälle", "name": "Region"},
            )
            fig.update_layout(yaxis={"categoryorder": "total ascending"})
            st.plotly_chart(fig, use_container_width=True)


# ─── 3. Quellangaben / Metadaten ─────────────────────────────────────────────

st.divider()
st.header("ℹ️ Quellen & Metadaten")

col1, col2 = st.columns(2)

with col1:
    if st.button("Datenquellen anzeigen", key="sources"):
        data, error = api_get("/sources")   # ← kein Cache, immer aktuell
        if error:
            st.error(error)
        else:
            for q in data.get("quellen", []):
                st.markdown(f"""
                **{q['quelle']}**
                Lizenz: [{q['lizenz_name']}]({q['lizenz_url']})
                Abgerufen: {q['abgerufen_am']}
                """)

with col2:
    if st.button("Import-Protokoll", key="imports"):
        data, error = api_get("/imports")   # ← kein Cache
        if error:
            st.error(error)
        else:
            df = pd.DataFrame(data.get("imports", []))
            if not df.empty:
                st.dataframe(
                    df[["quelle", "status", "verarbeitet", "hinzugef", "beendet_am"]],
                    use_container_width=True
                )


# ─── 4. Link zur API-Dokumentation ───────────────────────────────────────────

st.divider()
api_docs_url = f"localhost:8000/docs"
st.markdown(f"📖 [API-Dokumentation (Swagger)]({api_docs_url})")