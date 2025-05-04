# pages/6_Consultivo_e_Ripianificazione.py

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="6. Consultivo & Ripianificazione", layout="wide")
apply_custom_style()

# 1) Upload del consultivo
uploaded = st.file_uploader("Carica report reale (consultivo) Excel/CSV", type=["xlsx","csv"])
if not uploaded:
    st.info("⚠️ Carica il consultivo per procedere.")
    st.stop()

if uploaded.name.endswith(".csv"):
    df_cons = pd.read_csv(uploaded, parse_dates=['Start_Actual','End_Actual'])
else:
    df_cons = pd.read_excel(uploaded, parse_dates=['Start_Actual','End_Actual'])

# Calcolo durata reale come Timedelta
# End_Actual può essere NaT per fasi in corso
df_cons['Duration_Actual'] = df_cons['End_Actual'] - df_cons['Start_Actual']
st.subheader("Consultivo Caricato")
st.dataframe(df_cons.head())

# 1.1) Soglia di delta per ri-pianificazione
delta_min = st.number_input(
    "Soglia Delta (minuti) per ri-pianificazione", min_value=0, value=10, step=1
)
threshold = timedelta(minutes=delta_min)

# 2) Risultati teorici
def check_theory():
    if "risultati_scenari" not in st.session_state:
        st.error("❌ Prima esegui la simulazione (Pagina 3).")
        st.stop()

check_theory()

# Seleziona scenario teorico
sce_list = list(st.session_state["risultati_scenari"].keys())
sel = st.selectbox("Scenario teorico da confrontare", sce_list)
res = st.session_state["risultati_scenari"][sel]

df_theory = res["df_risultati"].copy()
df_pers = res["df_persone"]
start_time = df_pers["timestamp"].min()
# Calcolo Start/End assoluti e durata teorica
for col in ['Start','End']:
    df_theory[f'{col}_dt'] = start_time + pd.to_timedelta(df_theory[col], unit='m')
df_theory['Duration_Theory'] = df_theory['End_dt'] - df_theory['Start_dt']

st.subheader(f"Risultati Teorici – {sel}")
st.dataframe(df_theory[['ID_Lotto','Fase','Start_dt','End_dt','Duration_Theory']].head())

# 3) Merge teorico vs reale
cols_cons = ['ID_Lotto','Fase','Start_Actual','End_Actual','Duration_Actual']
df_cmp = pd.merge(
    df_theory[['ID_Lotto','Fase','Start_dt','End_dt','Duration_Theory']],
    df_cons[cols_cons],
    on=['ID_Lotto','Fase'], how='inner'
)
# Scostamento
# durata actual NaT esclude correttamente
mask_valid = df_cmp['Duration_Actual'].notna()
df_cmp = df_cmp[mask_valid]
df_cmp['Delta'] = df_cmp['Duration_Actual'] - df_cmp['Duration_Theory']

st.subheader("Confronto Teorico vs Reale")
st.dataframe(df_cmp[['ID_Lotto','Fase','Duration_Theory','Duration_Actual','Delta']])

# 4) Grafici alternativi
st.subheader("Analisi Delta")
col1, col2 = st.columns(2)
with col1:
    st.markdown("**Bar Chart Scostamenti**")
    df_bar = df_cmp.copy()
    df_bar['Delta_min'] = df_bar['Delta'].dt.total_seconds() / 60
    fig_bar = px.bar(
        df_bar, x='Fase', y='Delta_min', color='ID_Lotto',
        title='Delta (min) per Fase e Lotto', barmode='group'
    )
    st.plotly_chart(fig_bar, use_container_width=True)
with col2:
    st.markdown("**Scatter Delta vs Teoria**")
    df_scatter = df_bar.copy()
    df_scatter['Theory_min'] = df_scatter['Duration_Theory'].dt.total_seconds() / 60
    fig_sca = px.scatter(
        df_scatter, x='Theory_min', y='Delta_min', color='Fase',
        hover_data=['ID_Lotto'], title='Delta vs Durata Teorica'
    )
    st.plotly_chart(fig_sca, use_container_width=True)

# 5) Gantt combinato (teoria vs reale) per fasi selezionate
st.subheader("Gantt Comparativo (Teoria vs Reale)")
# costruisci df per timeline
g_th = df_cmp.rename(columns={'Start_dt':'Start','End_dt':'End'})[['ID_Lotto','Fase','Start','End']].assign(Source='Teorico')
g_re = df_cmp.rename(columns={'Start_Actual':'Start','End_Actual':'End'})[['ID_Lotto','Fase','Start','End']].assign(Source='Reale')
df_gantt = pd.concat([g_th, g_re], ignore_index=True)
fig_gant = px.timeline(
    df_gantt, x_start='Start', x_end='End', y='Fase', color='Source',
    facet_row='ID_Lotto', title='Timeline Teoria vs Reale per Lotto'
)
fig_gant.update_yaxes(autorange='reversed')
st.plotly_chart(fig_gant, use_container_width=True)

# 6) Ripianificazione con soglia delta
st.subheader("Ri-pianificazione in base al Delta")
# seleziona solo le fasi con Delta > soglia
to_replan = df_cmp[df_cmp['Delta'].abs() > threshold]
if to_replan.empty:
    st.success("✅ Nessuna fase supera la soglia: nessuna ripianificazione necessaria.")
else:
    st.write(f"⚠️ {len(to_replan)} fasi superano la soglia: procedo a ri-pianificare")
    # crea df_lotti filtrato solo per lotti con scostamenti
    lots_to = to_replan['ID_Lotto'].unique().tolist()
    df_lotti0 = st.session_state['df_lotti'].copy()
    df_lotti0 = df_lotti0[df_lotti0['Lotto'].isin(lots_to)]
    df_lotti0['DifferenzaTempo'] = 0
    cfg = st.session_state['scenari'][sce_list.index(sel)]
    df_r2, df_p2, df_e2, df_c2 = esegui_simulazione(
        df_lotti0, st.session_state['df_fasi'],
        st.session_state['df_posticipi'], st.session_state['df_equivalenze'],
        st.session_state['df_posticipi_fisiologici'], cfg
    )
    st.success("🔄 Simulazione ri-pianificata completata per i lotti interessati.")
    st.dataframe(df_r2)

