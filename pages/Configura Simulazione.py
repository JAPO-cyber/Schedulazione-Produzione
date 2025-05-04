import streamlit as st
from lib.style import apply_custom_style
from datetime import datetime

st.set_page_config(page_title="2. Configurazione Simulazione", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# Controllo dati caricati
if "df_lotti" not in st.session_state:
    st.warning("Carica prima i dati nella pagina 1.")
    st.stop()

st.title("2. Configurazione Simulazione")

# Schede per configurazione
tabs = st.tabs(["Parametri Generali", "Risorse Opzionali"])

with tabs[0]:
    st.subheader("Parametri Generali")
    data_inizio = st.date_input(
        "Data di inizio simulazione",
        value=datetime.today(),
        key="config_data_inizio"
    )
    includi_posticipi = st.checkbox(
        "Includi posticipi autorizzati",
        value=True,
        key="config_posticipi"
    )
    includi_fisiologici = st.checkbox(
        "Includi posticipi fisiologici",
        value=True,
        key="config_fisiologici"
    )

with tabs[1]:
    st.subheader("Risorse Opzionali")
    max_carrelli = st.number_input(
        "Numero massimo carrelli disponibili",
        min_value=1,
        value=10,
        step=1,
        key="config_carrelli"
    )
    max_personale = st.number_input(
        "Numero massimo operatori disponibili",
        min_value=1,
        value=5,
        step=1,
        key="config_personale"
    )

if st.button("Salva Configurazione", key="save_config"):
    st.session_state["config_simulazione"] = {
        "data_inizio": data_inizio,
        "includi_posticipi": includi_posticipi,
        "includi_fisiologici": includi_fisiologici,
        "max_carrelli": max_carrelli,
        "max_personale": max_personale
    }
    st.success("Configurazione salvata con successo!")
