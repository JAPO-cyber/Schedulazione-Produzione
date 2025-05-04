import streamlit as st
import pandas as pd
import plotly.express as px
from lib.style import apply_custom_style

st.set_page_config(page_title="4. Analisi Risultati", layout="wide")
apply_custom_style()

# Verifica login
if not st.session_state.get("logged_in", False):
    st.error("❌ Devi effettuare il login per accedere a questa pagina.")
    st.stop()

# Verifica esistenza risultati
if "risultati_lotti" not in st.session_state or "risultati_risorse" not in st.session_state:
    st.warning("❌ Esegui prima la simulazione nella pagina 3.")
    st.stop()

st.title("4. Analisi dei Risultati")

# Load DataFrames
df_risultati = st.session_state["risultati_lotti"]
df_risorse = st.session_state["risultati_risorse"]

# Tabs per analisi principali
tabs = st.tabs(["Gantt Lotti", "Dashboard Risorse"])

with tabs[0]:
    st.subheader("Diagramma di Gantt dei Lotti")
    gantt = px.timeline(
        df_risultati,
        x_start="Start",
        x_end="End",
        y="ID_Lotto",
        color="Fase",
        title="Schedulazione Lotti"
    )
    gantt.update_yaxes(autorange="reversed")
    st.plotly_chart(gantt, use_container_width=True)
    st.markdown("---")
    st.download_button(
        "⬇️ Scarica Gantt come CSV",
        df_risultati.to_csv(index=False).encode("utf-8"),
        "gantt_lotti.csv",
        "text/csv"
    )

with tabs[1]:
    st.subheader("Utilizzo Risorse nel Tempo")
    # Line chart per occupazione
    line_fig = px.line(
        df_risorse,
        x="Time",
        y=["Persone_occupate", "Carrelli_occupati"],
        title="Occupazione Risorse"
    )
    st.plotly_chart(line_fig, use_container_width=True)

    st.subheader("Andamento Persone")
    area_pers = px.area(
        df_risorse,
        x="Time",
        y="Persone_occupate",
        title="Operai Occupati nel Tempo"
    )
    st.plotly_chart(area_pers, use_container_width=True)

    st.subheader("Andamento Carrelli")
    area_car = px.area(
        df_risorse,
        x="Time",
        y="Carrelli_occupati",
        title="Carrelli Occupati nel Tempo"
    )
    st.plotly_chart(area_car, use_container_width=True)

    st.markdown("---")
    st.download_button(
        "⬇️ Scarica Uso Risorse come CSV",
        df_risorse.to_csv(index=False).encode("utf-8"),
        "uso_risorse.csv",
        "text/csv"
    )
