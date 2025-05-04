import streamlit as st
from lib.style import apply_custom_style
import pandas as pd

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

st.title("2. Configurazione Risorse e Opzioni di Simulazione")

st.markdown(
    "Personalizza i parametri di simulazione e filtra il dataset dei lotti."
)

df_lotti = st.session_state["df_lotti"]
df_fasi = st.session_state["df_fasi"]

# --- Risorse disponibili ---
st.subheader("Risorse Disponibili")
col1, col2 = st.columns(2)
with col1:
    max_carrelli = st.number_input(
        "Numero massimo carrelli disponibili",
        min_value=1, value=10, step=1,
        key="config_max_carrelli"
    )
    max_personale = st.number_input(
        "Numero massimo operatori disponibili",
        min_value=1, value=5, step=1,
        key="config_max_personale"
    )
with col2:
    st.markdown("**Capacità per macchine**")
    machines = df_fasi['Macchina'].unique().tolist()
    machine_caps = {}
    for mac in machines:
        cap = st.number_input(
            f"{mac} capacity", min_value=1, value=1, step=1,
            key=f"config_cap_{mac}"
        )
        machine_caps[mac] = cap

# --- Parametri di turno ---
st.subheader("Parametri di Turnazione")
col3, col4 = st.columns(2)
with col3:
    work_std = st.number_input(
        "Minuti di lavoro standard (giorni feriali)",
        min_value=60, value=480*2, step=60,
        key="config_work_std"
    )
    work_ven = st.number_input(
        "Minuti di lavoro venerdì",
        min_value=0, value=480*2-120, step=60,
        key="config_work_ven"
    )
with col4:
    workday_minutes = st.number_input(
        "Durata giornata (minuti)",
        min_value=60, value=480*3, step=60,
        key="config_workday"
    )
    extension = st.number_input(
        "Estensione turno extra (minuti)",
        min_value=0, value=0, step=10,
        key="config_extension"
    )
    fri38 = st.selectbox(
        "Giorno 38h (weekday index)",
        options=list(range(7)), index=5,
        key="config_fri38"
    )

# --- Opzioni di simulazione ---
st.subheader("Opzioni di Simulazione")
col5, col6 = st.columns(2)
with col5:
    includi_posticipi = st.checkbox(
        "Includi posticipi autorizzati",
        value=True, key="config_includi_posticipi"
    )
    includi_fisiologici = st.checkbox(
        "Includi ritardi fisiologici",
        value=False, key="config_includi_fisiologici"
    )
    variability_factor = st.slider(
        "Fattore variabilità fasi (%)",
        min_value=0.0, max_value=100.0, value=0.0, step=1.0,
        key="config_variability"
    )
    margin_pct = st.slider(
        "Margine tempo extra (%)",
        min_value=0.0, max_value=100.0, value=0.0, step=1.0,
        key="config_margin"
    )
with col6:
    granularity = st.selectbox(
        "Granularità risorse (minuti)",
        options=[1, 5, 15, 30], index=2,
        key="config_granularity"
    )
    filter_format = st.multiselect(
        "Filtra Formati (lascia vuoto per tutti)",
        options=df_lotti['Formato'].unique().tolist(),
        key="config_filter_format"
    )
    filter_line = st.multiselect(
        "Filtra Linee (lascia vuoto per tutte)",
        options=df_lotti['Linea'].unique().tolist() if 'Linea' in df_lotti.columns else [],
        key="config_filter_line"
    )

# --- Data di inizio override ---
st.subheader("Data e Ora di Inizio")
override = st.checkbox(
    "Sovrascrivi data/ora di inizio simulazione",
    value=False, key="config_override_start"
)
if override:
    data_inizio = st.datetime_input(
        "Data e ora di inizio",
        value=df_lotti['Giorno'].min().to_pydatetime().replace(hour=6, minute=0),
        key="config_data_inizio"
    )
else:
    data_inizio = None

# Salvataggio configurazione
if st.button("💾 Salva Configurazione"):
    st.session_state["config_simulazione"] = {
        "max_carrelli": max_carrelli,
        "max_personale": max_personale,
        "machine_caps": machine_caps,
        "work_std": work_std,
        "work_ven": work_ven,
        "workday_minutes": workday_minutes,
        "extension": extension,
        "fri38": fri38,
        "includi_posticipi": includi_posticipi,
        "includi_fisiologici": includi_fisiologici,
        "variability_factor": variability_factor / 100.0,
        "margin_pct": margin_pct / 100.0,
        "granularity": granularity,
        "filter_format": filter_format,
        "filter_line": filter_line,
        "data_inizio": data_inizio
    }
    st.success("✅ Configurazione salvata! Procedi alla simulazione.")

