import streamlit as st
from lib.style import apply_custom_style
import pandas as pd

st.set_page_config(page_title="2. Configurazione Simulazione", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# Controllo dati caricati
if "df_lotti" not in st.session_state or "df_fasi" not in st.session_state:
    st.warning("⚠️ Carica prima i dati nella pagina 1.")
    st.stop()

st.title("2. Configurazione Risorse e Scenari di Simulazione")

df_lotti = st.session_state["df_lotti"]
df_fasi   = st.session_state["df_fasi"]

# (Qui vanno tutti gli input già definiti: max_carrelli, max_personale, machine_caps, etc.)
# … [omesso per brevità, copia pure la logica di prima] …

# Raccogli la config in un dict
config = {
    "max_carrelli": max_carrelli,
    "max_personale": max_personale,
    "machine_caps": machine_caps,
    "work_std": work_std,
    "work_ven": work_ven,
    "workday_minutes": workday_minutes,
    "extension": extension,
    "fri38": fri38,
    "includi_posticipi": includi_posticipi,
    "includi_fisiologici": includi_fisiologici,
    "variability_factor": variability_factor / 100.0,
    "margin_pct": margin_pct / 100.0,
    "granularity": granularity,
    "filter_format": filter_format,
    "filter_line": filter_line,
    "data_inizio": data_inizio
}

# Inizializza lista scenari
if "scenari" not in st.session_state:
    st.session_state["scenari"] = []

# Bottone per salvare uno scenario
if st.button("💾 Aggiungi scenario"):
    st.session_state["scenari"].append(config.copy())
    st.success(f"✅ Scenario #{len(st.session_state['scenari'])} aggiunto")

# Visualizza lista scenari
if st.session_state["scenari"]:
    st.subheader("Scenari salvati")
    for i, sc in enumerate(st.session_state["scenari"], start=1):
        st.write(f"**Scenario {i}:** {sc}")


