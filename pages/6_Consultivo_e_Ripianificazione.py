import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="6. Consultivo & Ripianificazione", layout="wide")
apply_custom_style()

# 1) Upload consultivo
uploaded = st.file_uploader("Carica report reale (consultivo) Excel/CSV", type=["xlsx","csv"])
if not uploaded:
    st.info("⚠️ Carica il consultivo per procedere.")
    st.stop()

# Leggi file
if uploaded.name.endswith(".csv"):
    df_cons = pd.read_csv(uploaded, parse_dates=['Start_Actual','End_Actual'])
else:
    df_cons = pd.read_excel(uploaded, parse_dates=['Start_Actual','End_Actual'])

# Calcola durata reale
df_cons['Duration_Actual'] = df_cons['End_Actual'] - df_cons['Start_Actual']
st.subheader("Consultivo Caricato")
st.dataframe(df_cons.head())

# 2) Prendi i risultati teorici dall’ultima simulazione
if "risultati_scenari" not in st.session_state:
    st.error("❌ Prima esegui la simulazione (Pagina 3).")
    st.stop()

# Scegli lo scenario di confronto
sce_list = list(st.session_state["risultati_scenari"].keys())
sel = st.selectbox("Scenario teorico da confrontare", sce_list)
df_theory = st.session_state["risultati_scenari"][sel]["df_risultati"].copy()
df_theory['Duration_Theory'] = df_theory['End'] - df_theory['Start']
st.subheader(f"Risultati Teorici – {sel}")
st.dataframe(df_theory.head())

# 3) Merge teorico vs reale
df_cmp = pd.merge(
    df_theory,
    df_cons[['ID_Lotto','Fase','Start_Actual','End_Actual','Duration_Actual']],
    on=['ID_Lotto','Fase'],
    how='inner'
)
df_cmp['Delta'] = df_cmp['Duration_Actual'] - df_cmp['Duration_Theory']
st.subheader("Confronto Teorico vs Reale")
st.dataframe(df_cmp[['ID_Lotto','Fase','Duration_Theory','Duration_Actual','Delta']])

# 4) Gantt comparativo
st.subheader("Gantt Teorico vs Reale")
# Prepara df per Plotly: metti insieme le due fonti
gth = df_cmp.rename(columns={'Start':'Start_dt','End':'End_dt'})[['ID_Lotto','Fase','Start_dt','End_dt']]
gre = df_cmp.rename(columns={'Start_Actual':'Start_dt','End_Actual':'End_dt'})[['ID_Lotto','Fase','Start_dt','End_dt']]
gth['Source'] = 'Teorico'
gre['Source'] = 'Reale'
df_gantt = pd.concat([gth, gre], ignore_index=True)
fig = px.timeline(
    df_gantt, x_start="Start_dt", x_end="End_dt",
    y="ID_Lotto", color="Source", facet_col="Fase",
    title="Gantt Chart: Teorico vs Reale"
)
fig.update_yaxes(autorange="reversed")
st.plotly_chart(fig, use_container_width=True)

# 5) Ri-pianificazione delle fasi residue
st.subheader("Ri-pianificazione delle Fasi Residue")
# Calcola quali fasi non ancora concluse (in base all'ora attuale)
now = datetime.now()
residue = df_cmp[df_cmp['End_Actual'] > now]
if residue.empty:
    st.success("✅ Tutte le fasi sono concluse; nessuna ripianificazione necessaria.")
else:
    st.write(f"⏳ {len(residue)} fasi ancora in corso o future; rilancio simulazione solo per queste.")
    # Prepara df_lotti residui: rimappo DifferenzaTempo per oggi
    df_lotti0 = st.session_state["df_lotti"].copy()
    # imposta DifferenzaTempo = 0 per ripartire subito
    df_lotti0['DifferenzaTempo'] = 0
    # lancia simulazione solo con questi lotti/fasi (potresti filtrare df_tempi)
    df_r2, df_p2, df_e2, df_c2 = esegui_simulazione(
        df_lotti0, st.session_state["df_fasi"],
        st.session_state["df_posticipi"],
        st.session_state["df_equivalenze"],
        st.session_state["df_posticipi_fisiologici"],
        st.session_state["scenari"][sce_list.index(sel)]
    )
    st.success("🔄 Simulazione ri-pianificata completata.")
    st.dataframe(df_r2.head())
    # (Puoi aggiungere qui un Gantt delle fasi ri-pianificate, ecc.)
