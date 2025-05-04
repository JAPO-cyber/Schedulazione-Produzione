import streamlit as st
import pandas as pd
from lib.style import apply_custom_style

# Importa la funzione di simulazione dal modulo simulator
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="3. Esecuzione Simulazione", layout="wide")
apply_custom_style()

# ✅ Verifica accesso
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# ✅ Verifica che i dati e la configurazione siano presenti
required_keys = [
    "df_lotti", "df_fasi", "df_posticipi", 
    "df_posticipi_fisiologici", "df_equivalenze", 
    "config_simulazione"
]
missing = [k for k in required_keys if k not in st.session_state]
if missing:
    st.warning(f"⚠️ Mancano: {', '.join(missing)}. Completa caricamenti e configurazione.")
    st.stop()

st.title("3. Esecuzione della Simulazione")

# Mostra riepilogo dati
with st.expander("📋 Riepilogo Dati Caricati", expanded=False):
    st.dataframe(st.session_state["df_lotti"].head(), use_container_width=True)
    st.dataframe(st.session_state["df_fasi"].head(), use_container_width=True)
    st.dataframe(st.session_state["df_posticipi"].head(), use_container_width=True)
    st.dataframe(st.session_state["df_posticipi_fisiologici"].head(), use_container_width=True)
    st.dataframe(st.session_state["df_equivalenze"].head(), use_container_width=True)

# Parametri configurazione
config = st.session_state["config_simulazione"]
with st.expander("⚙️ Parametri di Simulazione", expanded=False):
    st.json(config, expanded=False)

# Bottone per eseguire
if st.button("🚀 Avvia Simulazione"):
    with st.spinner("Simulazione in corso..."):
        # Estrai DataFrame e config
        df_lotti = st.session_state["df_lotti"]
        df_tempi = st.session_state["df_fasi"]
        df_posticipi = st.session_state["df_posticipi"]
        df_equiv = st.session_state["df_equivalenze"]
        df_post_fisio = st.session_state["df_posticipi_fisiologici"]
        config = st.session_state["config_simulazione"]

        # Chiamata alla funzione centralizzata
        df_risultati, df_persone, df_energia, df_carrelli = esegui_simulazione(
            df_lotti, df_tempi, df_posticipi, df_equiv, df_post_fisio,
            config
        )
        # Salva risultati in session state
        st.session_state["risultato_simulazione"] = {
            "df_risultati": df_risultati,
            "df_persone": df_persone,
            "df_energia": df_energia,
            "df_carrelli": df_carrelli
        }
    st.success("✅ Simulazione completata!")

    # Visualizza primi risultati
    with st.expander("📊 Risultati Simulazione", expanded=True):
        st.markdown("**Output produzione**")
        st.dataframe(df_risultati.head(), use_container_width=True)
        st.markdown("**Andamento persone**")
        st.line_chart(df_persone.set_index('timestamp'))
        st.markdown("**Andamento energia**")
        st.line_chart(df_energia.set_index('timestamp'))
        st.markdown("**Carrelli occupati**")
        st.line_chart(df_carrelli.set_index('timestamp'))

elif "risultato_simulazione" in st.session_state:
    st.info("🛈 Risultati già disponibili. Espandi l'area Risultati Simulazione.")
