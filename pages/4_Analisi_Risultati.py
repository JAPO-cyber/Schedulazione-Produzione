import streamlit as st
import pandas as pd
from lib.style import apply_custom_style
import plotly.express as px

st.set_page_config(page_title="4. Analisi Risultati", layout="wide")
apply_custom_style()

# Verifica che i risultati esistano
if not st.session_state.get("risultato_simulazione"):
    st.warning("⚠️ Nessuna simulazione trovata. Esegui prima la simulazione nella pagina 3.")
    st.stop()

# Estrai DataFrame
res = st.session_state["risultato_simulazione"]
df_ris = res["df_risultati"]
df_pers = res["df_persone"]
df_eng = res["df_energia"]
df_car = res["df_carrelli"]

st.title("4. Analisi e Visualizzazione Risultati")

# 1) Gantt Chart per lotto/fase
st.subheader("Timeline delle Fasi per Lotto")
# Converti offset minuti in datetime assoluti
start_time = df_pers["timestamp"].min()
df_gantt = df_ris.copy()
df_gantt["Start_dt"] = start_time + pd.to_timedelta(df_gantt["Start"], unit="m")
df_gantt["End_dt"]   = start_time + pd.to_timedelta(df_gantt["End"],   unit="m")

fig_gantt = px.timeline(
    df_gantt,
    x_start="Start_dt",
    x_end="End_dt",
    y="ID_Lotto",
    color="Fase",
    title="Gantt Chart: fasi di produzione per lotto"
)
fig_gantt.update_yaxes(autorange="reversed")
st.plotly_chart(fig_gantt, use_container_width=True)

# 2) Serie temporali di risorse
col1, col2, col3 = st.columns(3)
with col1:
    st.subheader("Occupazione Operatori")
    fig_p = px.line(df_pers, x="timestamp", y="Persone_occupate", title="Operatori occupati nel tempo")
    st.plotly_chart(fig_p, use_container_width=True)
with col2:
    st.subheader("Energia Consumo")
    fig_e = px.line(df_eng, x="timestamp", y="Energia", title="Energia consumata nel tempo")
    st.plotly_chart(fig_e, use_container_width=True)
with col3:
    st.subheader("Carrelli Occupati")
    fig_c = px.line(df_car, x="timestamp", y="Carrelli_occupati", title="Carrelli occupati nel tempo")
    st.plotly_chart(fig_c, use_container_width=True)

# 3) Durata Totale per Lotto
st.subheader("Durata Totale di Produzione per Lotto")
df_durations = df_ris.copy()
df_durations["Duration"] = df_durations["End"] - df_durations["Start"]
df_tot = df_durations.groupby("ID_Lotto")["Duration"].sum().reset_index()
fig_bar = px.bar(df_tot, x="ID_Lotto", y="Duration", title="Durata complessiva per lotto")
st.plotly_chart(fig_bar, use_container_width=True)

# 4) Distribuzione del Tempo per Fase
st.subheader("Distribuzione del Tempo per Fase")
df_phase = df_durations.groupby("Fase")["Duration"].sum().reset_index()
fig_pie = px.pie(df_phase, names="Fase", values="Duration", title="Tempo totale per fase")
st.plotly_chart(fig_pie, use_container_width=True)
