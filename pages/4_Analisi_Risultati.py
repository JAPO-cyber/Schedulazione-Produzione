import streamlit as st
import pandas as pd
import plotly.express as px
from lib.style import apply_custom_style

st.set_page_config(page_title="4. Analisi Risultati", layout="wide")
apply_custom_style()

# Verifica che i risultati degli scenari esistano
if "risultati_scenari" not in st.session_state:
    st.warning("⚠️ Esegui prima la simulazione nella pagina 3.")
    st.stop()

# Selezione dello scenario da analizzare
sce_list = list(st.session_state["risultati_scenari"].keys())
sel = st.selectbox("Seleziona uno scenario", sce_list)
res = st.session_state["risultati_scenari"][sel]

df_ris  = res["df_risultati"]
df_pers = res["df_persone"]
df_eng  = res["df_energia"]
df_car  = res["df_carrelli"]

st.title(f"4. Analisi Risultati — {sel}")

# KPI sintetici
st.subheader("KPI Principali")
dur_tot = (df_ris.End - df_ris.Start).sum()
wip_media = df_pers["Persone_occupate"].mean()
st.metric("⏱️ Tempo totale produzione", f"{dur_tot}")
st.metric("👷 WIP medio (operatori)", f"{wip_media:.2f}")

# 1) Gantt Chart delle fasi per lotto
st.subheader("Timeline Fasi per Lotto (Gantt Chart)")
# Converti offset minuti in orari effettivi
start_time = df_pers["timestamp"].min()
df_gantt = df_ris.copy()
df_gantt["Start_dt"] = start_time + pd.to_timedelta(df_gantt["Start"], unit="m")
df_gantt["End_dt"]   = start_time + pd.to_timedelta(df_gantt["End"], unit="m")

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
st.subheader("Serie Temporali: Risorse")
col1, col2, col3 = st.columns(3)
with col1:
    st.markdown("**Operatori occupati**")
    fig_p = px.line(df_pers, x="timestamp", y="Persone_occupate")
    st.plotly_chart(fig_p, use_container_width=True)
with col2:
    st.markdown("**Energia consumata**")
    fig_e = px.line(df_eng, x="timestamp", y="Energia")
    st.plotly_chart(fig_e, use_container_width=True)
with col3:
    st.markdown("**Carrelli occupati**")
    fig_c = px.line(df_car, x="timestamp", y="Carrelli_occupati")
    st.plotly_chart(fig_c, use_container_width=True)

# 3) Durata totale per lotto (Bar Chart)
st.subheader("Durata Totale di Produzione per Lotto")
df_dur = df_ris.copy()
df_dur["Duration"] = df_dur.End - df_dur.Start
df_tot = df_dur.groupby("ID_Lotto")["Duration"].sum().reset_index()
fig_bar = px.bar(df_tot, x="ID_Lotto", y="Duration", title="Durata complessiva per lotto")
st.plotly_chart(fig_bar, use_container_width=True)

# 4) Distribuzione tempo per fase (Pie Chart)
st.subheader("Distribuzione del Tempo per Fase")
df_phase = df_dur.groupby("Fase")["Duration"].sum().reset_index()
fig_pie = px.pie(df_phase, names="Fase", values="Duration", title="Tempo totale per fase")
st.plotly_chart(fig_pie, use_container_width=True)

# 5) Heatmap occupazione operativa
st.subheader("Heatmap Occupazione Operatori (per ora)")
df_pers["hour"] = df_pers["timestamp"].dt.hour
heat = df_pers.pivot_table(index="hour", values="Persone_occupate", aggfunc="mean")
fig_h = px.imshow(heat, labels={"x":"","y":"Ora","color":"Operatori"})
st.plotly_chart(fig_h, use_container_width=True)

