import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
import io
from datetime import datetime, timedelta, date, time
from lib.style import apply_custom_style
from lib.simulator import esegui_simulazione

st.set_page_config(page_title="7. Analisi Avanzata & What-If", layout="wide")
apply_custom_style()

st.title("7. Analisi Avanzata & What-If Scheduling")

# -- 1) Download template consultivo
template_cols = ['ID_Lotto','Fase','Start_Actual','End_Actual']
df_template = pd.DataFrame(columns=template_cols)
csv_buffer = df_template.to_csv(index=False).encode('utf-8')
st.download_button(
    label="📥 Scarica template CSV consultivo",
    data=csv_buffer,
    file_name="consultivo_template.csv",
    mime="text/csv"
)

# -- 2) Upload consultivo
uploaded = st.file_uploader(
    "Carica report reale (consultivo) Excel/CSV",
    type=["xlsx","csv"]
)
if not uploaded:
    st.info("⚠️ Carica il consultivo per procedere.")
    st.stop()
if uploaded.name.endswith('.csv'):
    df_cons = pd.read_csv(uploaded, parse_dates=['Start_Actual','End_Actual'])
else:
    df_cons = pd.read_excel(uploaded, parse_dates=['Start_Actual','End_Actual'])

# Compute actual duration
df_cons['Duration_Actual'] = df_cons['End_Actual'] - df_cons['Start_Actual']
st.subheader("Consultivo Caricato")
st.dataframe(df_cons.head())

# -- 3) Soglia e selettori
delta_min = st.number_input(
    "Soglia Delta (minuti) per considerare criticità",
    min_value=0, value=10, step=1
)
threshold = timedelta(minutes=delta_min)

# Filtri dinamici
lots = df_cons['ID_Lotto'].unique().tolist()
phases = df_cons['Fase'].unique().tolist()
date_min = df_cons['Start_Actual'].min().date()
date_max = df_cons['Start_Actual'].max().date()

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    sel_lots = st.multiselect("Filtra Lotti", options=lots, default=lots)
with col_f2:
    sel_phases = st.multiselect("Filtra Fasi", options=phases, default=phases)
with col_f3:
    sel_dates = st.date_input(
        "Intervallo Date Start",
        value=(date_min, date_max)
    )
# apply filters
df_cons = df_cons[df_cons['ID_Lotto'].isin(sel_lots)]
df_cons = df_cons[df_cons['Fase'].isin(sel_phases)]
df_cons = df_cons[ df_cons['Start_Actual'].dt.date.between(sel_dates[0], sel_dates[1]) ]

# -- 4) Risultati teorici
if 'risultati_scenari' not in st.session_state:
    st.error("❌ Esegui prima la simulazione (Pagina 3).")
    st.stop()
sce_keys = list(st.session_state['risultati_scenari'].keys())
sel_scenario = st.selectbox("Scenario teorico", sce_keys)
res = st.session_state['risultati_scenari'][sel_scenario]
df_theory = res['df_risultati'].copy()
df_pers = res['df_persone']
start_time = df_pers['timestamp'].min()
for col in ['Start','End']:
    df_theory[f'{col}_dt'] = start_time + pd.to_timedelta(df_theory[col], unit='m')
df_theory['Duration_Theory'] = df_theory['End_dt'] - df_theory['Start_dt']

# merge
cols_cons = ['ID_Lotto','Fase','Start_Actual','End_Actual','Duration_Actual']
df_cmp = pd.merge(
    df_theory[['ID_Lotto','Fase','Start_dt','End_dt','Duration_Theory']],
    df_cons[cols_cons], on=['ID_Lotto','Fase'], how='inner'
)
mask = df_cmp['Duration_Actual'].notna()
df_cmp = df_cmp[mask]
df_cmp['Delta'] = df_cmp['Duration_Actual'] - df_cmp['Duration_Theory']
st.subheader("Scostamenti Teorico vs Reale")
st.dataframe(df_cmp[['ID_Lotto','Fase','Duration_Theory','Duration_Actual','Delta']])

# -- 5) KPI sintetici
st.subheader("KPI Sintetici")
n_total = len(df_cmp)
n_crit = df_cmp['Delta'].abs() > threshold
percent_crit = n_crit.sum() / n_total * 100 if n_total>0 else 0
mean_abs = df_cmp['Delta'].abs().mean().total_seconds()/60 if n_total>0 else 0
col_k1, col_k2, col_k3 = st.columns(3)
col_k1.metric("📦 Fasi confrontate", n_total)
col_k2.metric("⚠️ Fasi critiche", f"{n_crit.sum()} ({percent_crit:.1f}% )")
col_k3.metric("⏱️ Delta medio (min)", f"{mean_abs:.1f}")

# -- 6) Visualizzazioni avanzate
st.subheader("Visualizzazioni Analitiche")
# Box plot
df_box = df_cmp.copy()
df_box['Delta_min'] = df_box['Delta'].dt.total_seconds()/60
fig_box = px.box(df_box, x='Fase', y='Delta_min', points='all', title='Distribuzione Delta per Fase')
st.plotly_chart(fig_box, use_container_width=True)
# Pareto by Phase
st.markdown("**Diagramma di Pareto (fase vs somma delta assoluto)**")
df_pareto = df_box.groupby('Fase')['Delta_min'].apply(lambda x: x.abs().sum()).reset_index()
df_pareto = df_pareto.sort_values('Delta_min', ascending=False)
fig_par = px.bar(df_pareto, x='Fase', y='Delta_min', title='Pareto Scostamento assoluto per Fase')
st.plotly_chart(fig_par, use_container_width=True)
# Heatmap phase vs lot
df_heat = df_box.pivot_table(index='Fase', columns='ID_Lotto', values='Delta_min', aggfunc='mean').fillna(0)
fig_heat = px.imshow(df_heat, labels=dict(x='Lotto', y='Fase', color='Delta (min)'), aspect='auto')
st.plotly_chart(fig_heat, use_container_width=True)

# -- 7) What-If: modifica risorse e ripianifica
st.subheader("What-If Scheduling per Lotti Critici")
if n_crit.sum() > 0:
    st.markdown("### Parametri What-If")
    w_max_pers = st.slider("Nuovo max operatori", 1, 20, value=st.session_state['config_simulazione']['max_personale'])
    w_max_car = st.slider("Nuovo max carrelli", 1, 20, value=st.session_state['config_simulazione']['max_carrelli'])
    # aggiorna config copia
    cfg_new = st.session_state['config_simulazione'].copy()
    cfg_new['max_personale'] = w_max_pers
    cfg_new['max_carrelli'] = w_max_car
    if st.button("🔄 Esegui What-If per lotti critici"):
        lots_to = df_cmp.loc[n_crit, 'ID_Lotto'].unique().tolist()
        df_lotti0 = st.session_state['df_lotti'].loc[ st.session_state['df_lotti']['Lotto'].isin(lots_to) ].copy()
        df_lotti0['DifferenzaTempo'] = 0
        df_rw, df_pw, df_ew, df_cw = esegui_simulazione(
            df_lotti0, st.session_state['df_fasi'], st.session_state['df_posticipi'],
            st.session_state['df_equivalenze'], st.session_state['df_posticipi_fisiologici'], cfg_new
        )
        st.success("✅ What-If completato")
        # mostra Gantt semplificato
        df_rw['Start_dt'] = start_time + pd.to_timedelta(df_rw['Start'], unit='m')
        df_rw['End_dt']   = start_time + pd.to_timedelta(df_rw['End'], unit='m')
        fig_w = px.timeline(df_rw, x_start='Start_dt', x_end='End_dt', y='Fase', color='ID_Lotto',
                            title='What-If: ripianificazione fasi critiche')
        fig_w.update_yaxes(autorange='reversed')
        st.plotly_chart(fig_w, use_container_width=True)
        # export risultati
        csv_replan = df_rw.to_csv(index=False)
        st.download_button("📥 Esporta risultati What-If CSV", csv_replan, "whatif_results.csv", "text/csv")
else:
    st.info("✅ Nessuna fase critica: salta What-If.")
