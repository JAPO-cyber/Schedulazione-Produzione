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

# Tabs per caricamento
tabs = st.tabs(["Fasi per Prodotto", "Lotti Giornalieri", "Caricamento Completo", "Scarica Modelli Excel"])

# Schema atteso
schema = {
    "fasi": [
        ("Fase", "Nome della fase (es. 'SPERLATURA')"),
        ("Macchina", "Nome macchina usata nella fase"),
        ("Prodotto", "Codice del prodotto"),
        ("Tempo", "Durata della fase in minuti"),
        ("Addetti", "Numero operatori richiesti"),
        ("Pezzi", "Numero di pezzi per ciclo"),
        ("EnergiaFase", "Consumo stimato per fase"),
        ("Variabilità", "Fattore di variabilità (int)")
    ],
    "lotti": [
        ("Giorno", "Data del giorno di produzione (yyyy-mm-dd)"),
        ("Lotto", "Codice identificativo lotto"),
        ("Prodotto", "Codice del prodotto"),
        ("Formato", "Formato confezione"),
        ("Quantità", "Quantità da produrre")
    ]
}

# Tab 1: Fasi per prodotto
with tabs[0]:
    st.subheader("Carica Fasi per Prodotto")
    st.markdown("**Struttura attesa:**")
    for col, desc in schema["fasi"]:
        st.markdown(f"- **{col}**: {desc}")
    file_fasi = st.file_uploader("Carica file fasi", type=["xlsx"], key="file_fasi")
    if file_fasi:
        df_fasi = pd.read_excel(file_fasi)
        st.session_state["df_fasi"] = st.data_editor(df_fasi, use_container_width=True, key="editor_fasi")

# Tab 2: Lotti giornalieri
with tabs[1]:
    st.subheader("Carica Lotti Giornalieri")
    st.markdown("**Struttura attesa:**")
    for col, desc in schema["lotti"]:
        st.markdown(f"- **{col}**: {desc}")
    file_lotti = st.file_uploader("Carica file lotti", type=["xlsx"], key="file_lotti")
    if file_lotti:
        df_lotti = pd.read_excel(file_lotti)
        st.session_state["df_lotti"] = st.data_editor(df_lotti, use_container_width=True, key="editor_lotti")

# Tab 3: Caricamento completo
with tabs[2]:
    st.subheader("Caricamento Completo (Fasi + Lotti)")
    st.markdown("Assicurati che i nomi dei file contengano le parole chiave `fasi` e `lotti`.")
    files = st.file_uploader("Carica i file Excel", type=["xlsx"], accept_multiple_files=True, key="file_all")
    if files:
        for f in files:
            name = f.name.lower()
            if "fasi" in name:
                df = pd.read_excel(f)
                st.session_state["df_fasi"] = df
                st.write("📄 Fasi per Prodotto:")
                st.write(df.head())
            elif "lotti" in name:
                df = pd.read_excel(f)
                st.session_state["df_lotti"] = df
                st.write("📄 Lotti Giornalieri:")
                st.write(df.head())
        if st.button("✅ Conferma caricamento completo"):
            st.session_state["dati_confermati"] = True
            st.success("✅ Dati confermati correttamente!")

# Tab 4: Download modelli Excel
with tabs[3]:
    st.subheader("📥 Scarica Modelli Excel")
    st.markdown("Scarica i template con la struttura richiesta da compilare.")
    st.download_button(
        "⬇️ Scarica Fasi per Prodotto",
        data=open("/mnt/data/excel_modelli_simulazione/fasi_per_prodotto.xlsx", "rb").read(),
        file_name="fasi_per_prodotto.xlsx"
    )
    st.download_button(
        "⬇️ Scarica Lotti Giornalieri",
        data=open("/mnt/data/excel_modelli_simulazione/lotti_giornalieri.xlsx", "rb").read(),
        file_name="lotti_giornalieri.xlsx"
    )

# Conferma dati se caricati
if "df_fasi" in st.session_state and "df_lotti" in st.session_state:
    if st.button("✅ Conferma dati caricati"):
        st.session_state["dati_confermati"] = True
        st.success("✅ Dati confermati correttamente! Procedi alla configurazione.")
else:
    st.info("Carica i dati richiesti per abilitare la conferma.")


