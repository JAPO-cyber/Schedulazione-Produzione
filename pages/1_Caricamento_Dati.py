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

# Definizione delle tab per ogni caricamento
tabs = st.tabs(["Lotti", "Tempi", "Posticipi", "Equivalenze", "Post. Fisiologici"])
data_keys = ["lotti", "tempi", "posticipi", "equivalenze", "posticipi_fisiologici"]
for tab, key in zip(tabs, data_keys):
    with tab:
        st.subheader(f"Carica file {key.replace('_', ' ').title()}")
        file = st.file_uploader(f"Carica {key}", type=["xlsx"], key=f"file_{key}")
        if file:
            df = pd.read_excel(file)
            st.session_state[f"df_{key}"] = df
            st.markdown(f"**Anteprima {key.replace('_', ' ').title()}**")
            edited = st.data_editor(df, use_container_width=True, key=f"editor_{key}")
            st.session_state[f"df_{key}"] = edited

# Controllo se tutti i dati sono caricati
all_loaded = all(st.session_state.get(f"df_{key}") is not None for key in data_keys)

# Sezione conferma
st.markdown("---")
if all_loaded:
    if st.button("✅ Conferma dati caricati"):
        st.success("Dati confermati correttamente!")
        st.session_state["dati_confermati"] = True
else:
    st.info("Carica e modifica tutti i file prima di confermare.")

