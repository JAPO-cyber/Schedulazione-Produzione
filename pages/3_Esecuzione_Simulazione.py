import streamlit as st
import pandas as pd
from lib.style import apply_custom_style

st.set_page_config(page_title="3. Esecuzione Simulazione", layout="wide")
apply_custom_style()

# ✅ Verifica accesso
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# ✅ Verifica che i dati siano stati caricati e confermati
required_keys = [
    "df_lotti", "df_fasi", "df_posticipi", 
    "df_posticipi_fisiologici", "df_equivalenze", 
    "config_simulazione"
]

missing = [k for k in required_keys if k not in st.session_state]
if missing:
    st.warning(f"⚠️ Dati mancanti: {', '.join(missing)}. Torna alle pagine precedenti per completare il caricamento.")
    st.stop()

st.title("3. Esecuzione della Simulazione")

# Mostra un riepilogo dei dati caricati
with st.expander("📋 Riepilogo Dati Caricati", expanded=False):
    for key in required_keys[:-1]:
        df = st.session_state[key]
        st.markdown(f"**{key.replace('df_', '').replace('_', ' ').title()}**")
        st.dataframe(df.head(), use_container_width=True)

# Parametri configurati
config = st.session_state["config_simulazione"]
with st.expander("⚙️ Parametri di Simulazione"):
    st.json(config, expanded=False)

# Pulsante per eseguire simulazione
if st.button("🚀 Avvia Simulazione"):
    st.success("✅ Simulazione avviata (placeholder)")
    # Qui andrà la chiamata alla funzione `esegui_simulazione(...)`
    # risultato = esegui_simulazione(...)
    # st.session_state["risultato_simulazione"] = risultato
    # st.success("✅ Simulazione completata!")

