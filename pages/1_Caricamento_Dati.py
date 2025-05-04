import streamlit as st
import pandas as pd
from lib.style import apply_custom_style

st.set_page_config(page_title="1. Caricamento Dati", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

st.title("1. Caricamento Dati")

tabs = st.tabs(["Carica Excel", "Modifica Dati"])

with tabs[0]:
    st.subheader("Carica i file Excel")
    file_lotti = st.file_uploader("Carica file lotti", type=["xlsx"], key="file_lotti")
    file_tempi = st.file_uploader("Carica file tempi", type=["xlsx"], key="file_tempi")
    file_posticipi = st.file_uploader("Carica file posticipi", type=["xlsx"], key="file_posticipi")
    file_equivalenze = st.file_uploader("Carica file equivalenze", type=["xlsx"], key="file_equivalenze")
    file_posticipi_fisiologici = st.file_uploader("Carica file posticipi fisiologici", type=["xlsx"], key="file_posticipi_fisiologici")

    if st.button("Carica Dati", key="load_data"):
        if not all([file_lotti, file_tempi, file_posticipi, file_equivalenze, file_posticipi_fisiologici]):
            st.error("Per favore carica tutti i file richiesti.")
        else:
            df_lotti = pd.read_excel(file_lotti)
            df_tempi = pd.read_excel(file_tempi)
            df_posticipi = pd.read_excel(file_posticipi)
            df_equivalenze = pd.read_excel(file_equivalenze)
            df_posticipi_fisiologici = pd.read_excel(file_posticipi_fisiologici)

            st.session_state["df_lotti"] = df_lotti
            st.session_state["df_tempi"] = df_tempi
            st.session_state["df_posticipi"] = df_posticipi
            st.session_state["df_equivalenze"] = df_equivalenze
            st.session_state["df_posticipi_fisiologici"] = df_posticipi_fisiologici

            st.success("Dati caricati correttamente!")

with tabs[1]:
    st.subheader("Modifica Dati")
    if st.session_state.get("df_lotti") is not None:
        st.markdown("**Lotti**")
        st.session_state["df_lotti"] = st.data_editor(
            st.session_state["df_lotti"], use_container_width=True
        )
        st.markdown("**Tempi**")
        st.session_state["df_tempi"] = st.data_editor(
            st.session_state["df_tempi"], use_container_width=True
        )
        st.markdown("**Posticipi**")
        st.session_state["df_posticipi"] = st.data_editor(
            st.session_state["df_posticipi"], use_container_width=True
        )
        st.markdown("**Equivalenze**")
        st.session_state["df_equivalenze"] = st.data_editor(
            st.session_state["df_equivalenze"], use_container_width=True
        )
        st.markdown("**Posticipi Fisiologici**")
        st.session_state["df_posticipi_fisiologici"] = st.data_editor(
            st.session_state["df_posticipi_fisiologici"], use_container_width=True
        )
    else:
        st.info("Carica prima i dati nella scheda 'Carica Excel' per poterli modificare.")
