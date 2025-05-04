from pathlib import Path

# Path to the page
page1_path = Path("/mnt/data/schedulazione_app/pages/1_Caricamento_Dati.py")

# Updated page code
page1_code = '''import streamlit as st
import pandas as pd
from lib.style import apply_custom_style

st.set_page_config(page_title="1. Caricamento Dati", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

st.title("1. Caricamento Dati")

# Tabs per caricamento singolo
tabs = st.tabs(["Lotti", "Tempi", "Posticipi", "Equivalenze", "Post. Fisiologici", "Caricamento Completo"])

# Descrizioni dei formati Excel
schema = {
    "lotti": [
        ("ID_Lotto", "Identificativo univoco del lotto (es. 1, 2, 3)"),
        ("Quantità", "Quantità da produrre per lotto (numero intero)"),
        ("Formato", "Formato del prodotto (es. P_1000, P_3000)")
    ],
    "tempi": [
        ("Fase", "Nome fase di lavorazione (es. Riempimento)"),
        ("Tempo_Minuti", "Durata fase in minuti (numero)")
    ],
    "posticipi": [
        ("Fase", "Nome fase di lavorazione"),
        ("Ritardo_Minuti", "Minuti di ritardo autorizzato (numero)")
    ],
    "equivalenze": [
        ("Formato", "Formato del prodotto"),
        ("Fase", "Nome fase di lavorazione"),
        ("Equivalenza_Unita", "Fattore di equivalenza (float)")
    ],
    "posticipi_fisiologici": [
        ("Fase", "Nome fase di lavorazione"),
        ("Ritardo_Fisiologico_Min", "Minuti di ritardo fisiologico stimato (float)")
    ]
}

data_keys = ["lotti", "tempi", "posticipi", "equivalenze", "posticipi_fisiologici"]

# Caricamento individuale con schema
for tab, key in zip(tabs[:-1], data_keys):
    with tab:
        st.subheader(f"Carica file {key.replace('_', ' ').title()}")
        # Mostra schema atteso
        st.markdown("**Struttura del file Excel:**")
        for col, desc in schema[key]:
            st.markdown(f"- **{col}**: {desc}")
        # Uploader
        file = st.file_uploader(f"Carica {key}", type=["xlsx"], key=f"file_{key}")
        if file:
            df = pd.read_excel(file)
            st.session_state[f"df_{key}"] = df
            st.markdown("**Anteprima**")
            st.write(df.head())
            # Editor opzionale
            edited = st.data_editor(df, use_container_width=True, key=f"editor_{key}")
            st.session_state[f"df_{key}"] = edited

# Tab di caricamento completo
with tabs[-1]:
    st.subheader("Caricamento Completo di tutti i file")
    st.markdown("Carica tutti e 5 i file in un unico step. I nomi dei file devono contenere le parole chiave:\n"
                "`lotti`, `tempi`, `posticipi`, `equivalenze`, `fisiologici`.")
    files = st.file_uploader("Carica tutti i file Excel", type=["xlsx"], accept_multiple_files=True, key="file_all")
    if files:
        # Mappatura automatica
        for file in files:
            fname = file.name.lower()
            for key in data_keys:
                if key in fname:
                    df = pd.read_excel(file)
                    st.session_state[f"df_{key}"] = df
        st.success("Tutti i file caricati!")
        # Anteprima file confermati
        for key in data_keys:
            df = st.session_state.get(f"df_{key}")
            if df is not None:
                st.markdown(f"**Anteprima {key.replace('_', ' ').title()}**")
                st.write(df.head())
        if st.button("✅ Conferma caricamento completo"):
            st.session_state["dati_confermati"] = True
            st.success("Dati confermati correttamente!")'''

# Write to file
page1_path.write_text(page1_code, encoding="utf-8")

# Display the updated code
print(page1_code)



