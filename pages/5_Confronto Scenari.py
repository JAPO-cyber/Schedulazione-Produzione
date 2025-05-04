import streamlit as st
import pandas as pd
import plotly.express as px
from lib.style import apply_custom_style

st.set_page_config(page_title="5. Confronto Scenari", layout="wide")
apply_custom_style()

# Verifica che i risultati degli scenari esistano
if "risultati_scenari" not in st.session_state:
    st.warning("⚠️ Nessun risultato di scenario trovato. Esegui la simulazione (Pagina 3) prima.")
    st.stop()

st.title("5. Confronto tra Scenari")

# Estrai dizionario di risultati
results = st.session_state["risultati_scenari"]
scenario_names = list(results.keys())

# KPI di ogni scenario
st.subheader("KPI per Scenario")
summary = []
for name, data in results.items():
    df_ris = data["df_risultati"]
    df_pers = data["df_persone"]
    # tempo totale produzione
    total_time = (df_ris.End - df_ris.Start).sum()
    # WIP medio
    wip_avg = df_pers["Persone_occupate"].mean()
    summary.append({"Scenario": name, 
                    "Tempo Totale": total_time,
                    "WIP Medio": round(wip_avg, 2)})

df_summary = pd.DataFrame(summary)
st.dataframe(df_summary.set_index("Scenario"))

# Selezione metriche da confrontare
st.subheader("Grafici di Confronto")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Confronto Energia consumata**")
    df_e_all = pd.concat([
        data["df_energia"].assign(Scenario=name)
        for name, data in results.items()
    ])
    fig_e = px.line(df_e_all, x="timestamp", y="Energia", color="Scenario", 
                    title="Energia consumata nel tempo per Scenario")
    st.plotly_chart(fig_e, use_container_width=True)
with col2:
    st.markdown("**Confronto Occupazione Operatori**")
    df_p_all = pd.concat([
        data["df_persone"].assign(Scenario=name)
        for name, data in results.items()
    ])
    fig_p = px.line(df_p_all, x="timestamp", y="Persone_occupate", color="Scenario",
                    title="Operatori occupati nel tempo per Scenario")
    st.plotly_chart(fig_p, use_container_width=True)

# Durata complessiva confronto
st.subheader("Durata Complessiva per Scenario")
df_dur_s = []
for name, data in results.items():
    df_ris = data["df_risultati"]
    dur = (df_ris.End - df_ris.Start).sum()
    df_dur_s.append({"Scenario": name, "Durata Totale": dur})
df_dur_s = pd.DataFrame(df_dur_s)
fig_bar = px.bar(df_dur_s, x="Scenario", y="Durata Totale", 
                 title="Durata complessiva produzione per Scenario")
st.plotly_chart(fig_bar, use_container_width=True)

# Distribuzione tempi fasi a confronto
st.subheader("Distribuzione Tempo per Fase per Scenario")
df_phase_all = []
for name, data in results.items():
    df_ris = data["df_risultati"].copy()
    df_ris["Duration"] = df_ris.End - df_ris.Start
    agg = df_ris.groupby("Fase")["Duration"].sum().reset_index()
    agg["Scenario"] = name
    df_phase_all.append(agg)
df_phase_all = pd.concat(df_phase_all)
fig_pie = px.sunburst(df_phase_all, path=["Scenario", "Fase"], values="Duration",
                      title="Distribuzione tempo per fase e scenario")
st.plotly_chart(fig_pie, use_container_width=True)
