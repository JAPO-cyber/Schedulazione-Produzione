import streamlit as st
import pandas as pd
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="3. Esecuzione Simulazione", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# Verifica dati caricati e confermati
if not st.session_state.get("dati_confermati", False):
    st.warning("❌ Devi confermare i dati nella pagina 1 prima di eseguire la simulazione.")
    st.stop()

# Verifica configurazione simulazione
if "config_simulazione" not in st.session_state:
    st.warning("❌ Devi configurare la simulazione nella pagina 2.")
    st.stop()

st.title("3. Esecuzione Simulazione")

# Parametri e dati
config = st.session_state["config_simulazione"]
df_lotti = st.session_state["df_lotti"]
df_tempi = st.session_state["df_tempi"]
df_posticipi = st.session_state["df_posticipi"]
df_equivalenze = st.session_state["df_equivalenze"]
df_pf = st.session_state["df_posticipi_fisiologici"]

if st.button("▶️ Avvia Simulazione"):
    with st.spinner("Simulazione in corso..."):
        df_risultati, df_risorse = esegui_simulazione(
            df_lotti=df_lotti,
            df_tempi=df_tempi,
            df_posticipi=df_posticipi,
            df_equivalenze=df_equivalenze,
            df_posticipi_fisiologici=df_pf,
            data_inizio=config["data_inizio"],
            includi_posticipi=config["includi_posticipi"],
            includi_fisiologici=config["includi_fisiologici"],
            max_carrelli=config.get("max_carrelli"),
            max_personale=config.get("max_personale")
        )
    st.success("✅ Simulazione completata!")

    # Salva risultati in session_state
    st.session_state["risultati_lotti"] = df_risultati
    st.session_state["risultati_risorse"] = df_risorse

# Mostra anteprime se già esistono
if "risultati_lotti" in st.session_state:
    st.subheader("Risultati Lotti")
    st.dataframe(st.session_state["risultati_lotti"])
    csv = st.session_state["risultati_lotti"].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Scarica Risultati Lotti", csv, "risultati_lotti.csv", "text/csv")

if "risultati_risorse" in st.session_state:
    st.subheader("Utilizzo Risorse")
    st.dataframe(st.session_state["risultati_risorse"])
    csv2 = st.session_state["risultati_risorse"].to_csv(index=False).encode('utf-8')
    st.download_button("⬇️ Scarica Utilizzo Risorse", csv2, "risultati_risorse.csv", "text/csv")
