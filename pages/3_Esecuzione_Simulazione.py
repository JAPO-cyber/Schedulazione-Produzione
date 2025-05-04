import streamlit as st
import pandas as pd
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="3. Esecuzione Simulazione", layout="wide")
apply_custom_style()

if not st.session_state.get("logged_in"):
    st.error("❌ Login richiesto"); st.stop()

# Verifica file e scenari
req = ["df_lotti","df_fasi","df_posticipi","df_posticipi_fisiologici","df_equivalenze","scenari"]
if any(k not in st.session_state for k in req):
    st.warning("⚠️ Completa Pagine 1 e 2 prima di procedere.")
    st.stop()

st.title("3. Esecuzione di Tutti gli Scenari")

if st.button("🚀 Avvia tutti gli scenari"):
    results = {}
    for idx, cfg in enumerate(st.session_state["scenari"], start=1):
        df_ris, df_pers, df_eng, df_car = esegui_simulazione(
            st.session_state["df_lotti"],
            st.session_state["df_fasi"],
            st.session_state["df_posticipi"],
            st.session_state["df_equivalenze"],
            st.session_state["df_posticipi_fisiologici"],
            cfg
        )
        results[f"Scenario {idx}"] = {
            "df_risultati": df_ris,
            "df_persone": df_pers,
            "df_energia": df_eng,
            "df_carrelli": df_car
        }
    st.session_state["risultati_scenari"] = results
    st.success("✅ Tutti gli scenari sono stati simulati!")

# Se già simulato, avvisa
elif "risultati_scenari" in st.session_state:
    st.info("ℹ️ Risultati scenari già disponibili. Vai alla Pagina 4.")

