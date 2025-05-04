# Ricostruzione del codice completo per 1_Caricamento_Dati.py
# Include tutti i file Excel: lotti, fasi, posticipi, equivalenze, posticipi fisiologici

page1_code_complete = '''import streamlit as st
import pandas as pd
from lib.style import apply_custom_style

st.set_page_config(page_title="1. Caricamento Dati", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

st.title("1. Caricamento Dati")

# Tabs per caricamento
tabs = st.tabs([
    "Fasi per Prodotto", 
    "Lotti Giornalieri", 
    "Posticipi Autorizzati", 
    "Posticipi Fisiologici", 
    "Equivalenze", 
    "Caricamento Completo"
])

# Schema atteso
schema = {
    "fasi": [
        ("Fase", "Nome fase (es. 'SPERLATURA')"),
        ("Macchina", "Nome macchina"),
        ("Prodotto", "Codice prodotto"),
        ("Tempo", "Durata della fase in minuti"),
        ("Addetti", "Numero operatori"),
        ("Pezzi", "Numero pezzi per ciclo"),
        ("EnergiaFase", "Consumo energia fase"),
        ("Variabilità", "Fattore di variabilità")
    ],
    "lotti": [
        ("Giorno", "Data produzione (yyyy-mm-dd)"),
        ("Lotto", "ID lotto"),
        ("Prodotto", "Codice prodotto"),
        ("Formato", "Formato confezione"),
        ("Quantità", "Quantità da produrre")
    ],
    "posticipi": [
        ("Fase", "Nome fase"),
        ("Ritardo_Minuti", "Ritardo autorizzato in minuti")
    ],
    "posticipi_fisiologici": [
        ("Fase", "Nome fase"),
        ("Ritardo_Fisiologico_Min", "Ritardo fisiologico stimato in minuti")
    ],
    "equivalenze": [
        ("Formato", "Formato del prodotto"),
        ("Fase", "Nome fase"),
        ("Equivalenza_Unita", "Fattore di equivalenza")
    ]
}

data_keys = [
    "fasi", 
    "lotti", 
    "posticipi", 
    "posticipi_fisiologici", 
    "equivalenze"
]

# Tab individuali
for tab, key in zip(tabs[:-1], data_keys):
    with tab:
        st.subheader(f"Carica file {key.replace('_', ' ').title()}")
        st.markdown("**Struttura attesa:**")
        for col, desc in schema[key]:
            st.markdown(f"- **{col}**: {desc}")
        file = st.file_uploader(f"Carica {key}", type=["xlsx"], key=f"file_{key}")
        if file:
            df = pd.read_excel(file)
            st.session_state[f"df_{key}"] = st.data_editor(df, use_container_width=True, key=f"editor_{key}")

# Tab caricamento completo
with tabs[-1]:
    st.subheader("Caricamento Completo di tutti i file")
    st.markdown("Carica tutti i file Excel insieme. I nomi devono contenere: "
                "`fasi`, `lotti`, `posticipi`, `fisiologici`, `equivalenze`.")
    files = st.file_uploader("Carica file multipli", type=["xlsx"], accept_multiple_files=True, key="file_all")
    if files:
        for f in files:
            name = f.name.lower()
            for key in data_keys:
                if key in name:
                    df = pd.read_excel(f)
                    st.session_state[f"df_{key}"] = df
                    st.write(f"📄 {key.replace('_', ' ').title()}:")
                    st.write(df.head())
        if st.button("✅ Conferma caricamento completo"):
            st.session_state["dati_confermati"] = True
            st.success("✅ Dati confermati correttamente!")

# Conferma manuale
if all(st.session_state.get(f"df_{k}") is not None for k in data_keys):
    if st.button("✅ Conferma dati caricati"):
        st.session_state["dati_confermati"] = True
        st.success("✅ Tutti i dati caricati e confermati!")
else:
    st.info("Carica tutti i file richiesti per abilitare la conferma.")
'''

# Scrive il codice aggiornato sul file corretto
file_path = Path("/mnt/data/schedulazione_app/pages/1_Caricamento_Dati.py")
file_path.write_text(page1_code_complete, encoding="utf-8")

# Mostra all'utente il contenuto aggiornato
page1_code_complete



