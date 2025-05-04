import streamlit as st
import pandas as pd
import plotly.express as px
from lib.style import apply_custom_style

st.set_page_config(page_title="4. Analisi Risultati", layout="wide")
apply_custom_style()

if "risultati_scenari" not in st.session_state:
    st.warning("⚠️ Esegui prima la simulazione (Pagina 3).")
    st.stop()

# Seleziona scenario
sce_list = list(st.session_state["risultati_scenari"].keys())
sel = st.selectbox("Scegli Scenario", sce_list)
res = st.session_state["risultati_scenari"][sel]
df_ris = res["df_risultati"]
df_pers= res["df_persone"]
df_eng = res["df_energia"]
df_car = res["df_carrelli"]

st.title(f"4. Analisi Risultati — {sel}")

# KPI sintetici
st.subheader("KPI Principali")
dur_tot = (df_ris.End - df_ris.Start).sum()
wip_media = df_pers["Persone_occupate"].mean()
st.metric("✔️ Tempo totale produzione", f"{dur_tot}")
st.metric("👥 WIP medio (operatori)", f"{wip_media:.2f}")

# Pivot: durata media per fase
st.subheader("Durata Media per Fase")
df_ris["Duration"] = df_ris.End - df_ris.Start
df_media = df_ris.groupby("Fase")["Duration"].mean().reset_index()
st.dataframe(df_media)

# Heatmap occupazione oraria
st.subheader("Heatmap Occupazione Operatori (per ora)")
df_pers["hour"] = df_pers["timestamp"].dt.hour
heat = df_pers.pivot_table(index="hour", values="Persone_occupate", aggfunc="mean")
fig_h = px.imshow(heat, labels=dict(x="","y":"Ora","color":"Operatori"))
st.plotly_chart(fig_h, use_container_width=True)

# Confronto tra scenari sul consumo energetico
st.subheader("Confronto Energia tra tutti gli scenari")
fig_cmp = px.line(
    pd.concat([
        df.assign(Scenario=sc) 
        for sc, r in st.session_state["risultati_scenari"].items() 
        for df in [r["df_energia"]]
    ]),
    x="timestamp", y="Energia", color="Scenario"
)
st.plotly_chart(fig_cmp, use_container_width=True)

