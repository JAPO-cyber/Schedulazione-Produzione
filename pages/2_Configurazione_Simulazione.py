import streamlit as st
from lib.style import apply_custom_style

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

st.title("2. Configurazione Risorse Disponibili")

st.markdown(
    "Questa pagina consente di impostare i limiti massimi delle risorse **disponibili contemporaneamente** "
    "durante la simulazione. La data di inizio sarà determinata automaticamente "
    "dal primo ordine in `df_lotti`."
)

# Input risorse disponibili
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

# Salvataggio configurazione
if st.button("💾 Salva Configurazione"):
    st.session_state["config_simulazione"] = {
        "max_carrelli": max_carrelli,
        "max_personale": max_personale
    }
    st.success("✅ Configurazione salvata correttamente! Procedi alla simulazione.")
