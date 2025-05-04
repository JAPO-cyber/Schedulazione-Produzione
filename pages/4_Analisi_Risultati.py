import streamlit as st
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

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
    st.warning(
        f"⚠️ Dati mancanti: {', '.join(missing)}. Torna alle pagine precedenti per completare il caricamento."
    )
    st.stop()

st.title("3. Esecuzione della Simulazione")

# riepilogo dati/config come prima…
# ...

if st.button("🚀 Avvia Simulazione"):
    progress_bar = st.progress(0.0, text="⏳ Avvio simulazione…")
    with st.spinner("⏳ Simulazione in corso…"):
        # recupero input
        df_lotti   = st.session_state["df_lotti"]
        df_fasi    = st.session_state["df_fasi"]
        df_post    = st.session_state["df_posticipi"]
        df_pf      = st.session_state["df_posticipi_fisiologici"]
        df_eq      = st.session_state["df_equivalenze"]
        config     = st.session_state["config_simulazione"]

        # callback che aggiorna la progress bar
        def _update_progress(pct: float):
            # pct fra 0.0 e 1.0
            progress_bar.progress(pct)

        # avvio simulazione con callback
        risultato = esegui_simulazione(
            df_lotti, df_fasi, df_post, df_pf, df_eq,
            config,
            progress_callback=_update_progress
        )
        st.session_state["risultato_simulazione_raw"] = risultato

    st.success("✅ Simulazione completata!")
    st.info("I DataFrame dei risultati saranno creati nella pagina successiva.")

