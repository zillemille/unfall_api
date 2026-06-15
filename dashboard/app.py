"""
Streamlit-Dashboard für die Unfallatlas-API.

Ruft ausschließlich die FastAPI auf — keine direkte DB-Verbindung.
API-Basis-URL wird über die Umgebungsvariable API_URL gesetzt,
Standard: http://localhost:8000 (lokale Entwicklung).
"""

import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ─── Hilfsfunktion ───────────────────────────────────────────────────────────

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


def show_result(data, error):
    """Einheitliche Ausgabe von Ergebnis oder Fehler."""
    if error:
        st.error(error)
    else:
        st.json(data)


# ─── Layout ──────────────────────────────────────────────────────────────────

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
        data, error = api_get("/accidents/earliest")
        show_result(data, error)

# 2 — Unfälle mit Personenschäden 2023 in Sachsen
with st.expander("Wie viele Unfälle mit Personenschäden ereigneten sich 2023 in Sachsen?"):
    if st.button("Abfragen", key="sachsen_2023"):
        data, error = api_get("/accidents/count", params={
            "ags_prefix": "14",
            "year": 2023,
        })
        show_result(data, error)

# 3 — Daten ab wann für NRW
with st.expander("Ab welchem Jahr sind Daten für Nordrhein-Westfalen verfügbar?"):
    if st.button("Abfragen", key="nrw_years"):
        data, error = api_get("/accidents/earliest", params={"ags_prefix": "05"})
        show_result(data, error)

# 4 — Daten ab wann für MV
with st.expander("Ab welchem Jahr sind Daten für Mecklenburg-Vorpommern verfügbar?"):
    if st.button("Abfragen", key="mv_years"):
        data, error = api_get("/accidents/earliest", params={"ags_prefix": "13"})
        show_result(data, error)

# 5 — Fußgängerunfälle 2023 in Berlin
with st.expander("Wie viele Unfälle mit Fußgängerbeteiligung ereigneten sich 2023 in Berlin?"):
    if st.button("Abfragen", key="berlin_fuss"):
        data, error = api_get("/accidents/count", params={
            "ags_prefix": "11",
            "year": 2023,
            "ist_fuss": True,
        })
        show_result(data, error)

st.divider()

# ─── Multi-Source-Fragen ─────────────────────────────────────────────────────

st.header("Multi-Source-Abfragen")

# 6 — Unfälle je 100.000 Einwohner
with st.expander("Unfälle je 100.000 Einwohner"):
    col1, col2 = st.columns(2)
    region_pc = col1.text_input("AGS-Präfix", value="14", key="pc_region")
    year_pc   = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="pc_year")
    if st.button("Abfragen", key="per_capita"):
        data, error = api_get("/accidents/per-capita", params={
            "ags_prefix": region_pc,
            "year": year_pc,
        })
        show_result(data, error)

# 7 — Unfalldichte je km²
with st.expander("Unfalldichte je km²"):
    col1, col2 = st.columns(2)
    level_d = col1.selectbox("Level", ["kreis", "bundesland"], key="density_level")
    year_d  = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="density_year")
    if st.button("Abfragen", key="density"):
        data, error = api_get("/accidents/density", params={
            "level": level_d,
            "year": year_d,
        })
        show_result(data, error)

st.divider()

# ─── Bonus-Abfragen ──────────────────────────────────────────────────────────

st.header("Weitere Abfragen")

# Top-N Regionen
with st.expander("Top-N Regionen nach Unfallzahl"):
    col1, col2, col3 = st.columns(3)
    level_t = col1.selectbox("Level", ["kreis", "bundesland"], key="top_level")
    year_t  = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="top_year")
    limit_t = col3.number_input("Top N", value=5, min_value=1, max_value=50, key="top_limit")
    kat_t   = st.selectbox(
        "Kategorie (optional)",
        [None, 1, 2, 3],
        format_func=lambda x: "Alle" if x is None else {1: "Getötete", 2: "Schwerverletzte", 3: "Leichtverletzte"}[x],
        key="top_kat"
    )
    if st.button("Abfragen", key="top"):
        params = {"level": level_t, "year": year_t, "limit": limit_t}
        if kat_t:
            params["kategorie"] = kat_t
        data, error = api_get("/accidents/top", params=params)
        show_result(data, error)

# Jahrestrend
with st.expander("Jahrestrend für eine Region"):
    col1, col2, col3 = st.columns(3)
    ags_tr    = col1.text_input("AGS-Präfix", value="14", key="trend_ags")
    von_tr    = col2.number_input("Von Jahr", value=2019, min_value=2000, max_value=2100, key="trend_von")
    bis_tr    = col3.number_input("Bis Jahr", value=2024, min_value=2000, max_value=2100, key="trend_bis")
    if st.button("Abfragen", key="trend"):
        data, error = api_get("/accidents/trend", params={
            "ags_prefix": ags_tr,
            "von_jahr": von_tr,
            "bis_jahr": bis_tr,
        })
        show_result(data, error)

# Kreise ohne Unfälle
with st.expander("(Bonus) Kreise ohne Unfälle in einem Jahr"):
    col1, col2 = st.columns(2)
    ags_z  = col1.text_input("AGS-Präfix (Bundesland)", value="14", key="zero_ags")
    year_z = col2.number_input("Jahr", value=2024, min_value=2000, max_value=2100, key="zero_year")
    if st.button("Abfragen", key="zero"):
        data, error = api_get("/accidents/zero-accidents", params={
            "ags_prefix": ags_z,
            "year": year_z,
            "level": "kreis",
        })
        show_result(data, error)


# ──────── nützliche Abfragen ────────────────────────────

st.header("nützliche Abfragen")

with st.expander("Ags zu Regionennamen bekommen"):
    region_name = st.text_input("Regionennamen", key="region_name")
    level = st.text_input("Level", key="level")
    ags_pre = st.text_input("AGS-Präfix", key="ags_pre")
    params = {}
    if region_name:
        params.update({"name": region_name})
    if level:
        params.update({"level": level})
    if ags_pre:
        params.update({"ags_prefix": ags_pre})
    if st.button("Abfragen", key="ags_search"):
        data, error = api_get("/regions/", params= params)
        show_result(data, error)