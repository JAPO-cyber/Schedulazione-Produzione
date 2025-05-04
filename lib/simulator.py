"""
lib/simulator.py
Modulo di simulazione avanzato per schedulazione produzione.
Accetta configurazione completa da Streamlit.
"""
import random
import simpy
import pandas as pd
from datetime import timedelta

def esegui_simulazione(
    df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici,
    config
):
    # --------------------------------------------------
    # 0) VALIDAZIONE INIZIALE: colonne MINIME necessarie
    # --------------------------------------------------
    # df_tempi
    required_tempi = {'Fase', 'Macchina'}
    # il tempo può chiamarsi "Tempo_Minuti" o "Tempo"
    if 'Tempo_Minuti' in df_tempi.columns:
        required_tempi.add('Tempo_Minuti')
    else:
        required_tempi.add('Tempo')
    # colonne obbligatorie: Pezzi, Addetti, EnergiaFase
    for col in ('Pezzi', 'Addetti', 'EnergiaFase'):
        if col not in df_tempi.columns:
            raise KeyError(f"df_tempi manca la colonna '{col}'")
    missing = required_tempi - set(df_tempi.columns)
    if missing:
        raise KeyError(f"df_tempi manca le colonne: {missing}")

    # df_lotti
    for col in ('ID_Lotto', 'Formato', 'Quantita', 'Giorno'):
        if col not in df_lotti.columns:
            raise KeyError(f"df_lotti manca la colonna '{col}'")

    # df_posticipi
    if config.get("includi_posticipi"):
        if 'Fase' not in df_posticipi.columns or not any(c.lower() in df_posticipi.columns for c in ('Lotto','lotto')):
            raise KeyError("df_posticipi deve contenere 'Fase' e 'Lotto' (o 'lotto')")

    # df_equivalenze
    for col in ('Formato', 'Fase', 'Equivalenza_Unita'):
        if col not in df_equivalenze.columns:
            raise KeyError(f"df_equivalenze manca la colonna '{col}'")

    # df_posticipi_fisiologici
    if config.get("includi_fisiologici"):
        for col in ('FORMATO', 'FASE', 'QUANDO', 'TEMPO'):
            if col not in df_posticipi_fisiologici.columns:
                raise KeyError(f"df_posticipi_fisiologici manca la colonna '{col}'")

    # --------------------------------------------------
    # 1) Estrazione configurazione
    # --------------------------------------------------
    mc = config.get("max_carrelli")
    mp = config.get("max_personale")
    machine_caps = config.get("machine_caps", {})
    work_std = config.get("work_std")
    work_ven = config.get("work_ven")
    workday = config.get("workday_minutes")
    extension = config.get("extension")
    fri38 = config.get("fri38")
    include_post = config.get("includi_posticipi")
    include_fisio = config.get("includi_fisiologici")
    variability = config.get("variability_factor")
    margin = config.get("margin_pct")
    gran = config.get("granularity")
    filt_fmt = config.get("filter_format")
    filt_line = config.get("filter_line")
    start_override = config.get("data_inizio")

    # --------------------------------------------------
    # 2) Pre-elaborazione lotti (filtri formato/linea)
    # --------------------------------------------------
    lotti = df_lotti.copy()
    if filt_fmt:
        lotti = lotti[lotti['Formato'].isin(filt_fmt)]
    if 'Linea' in lotti.columns and filt_line:
        lotti = lotti[lotti['Linea'].isin(filt_line)]

    # --------------------------------------------------
    # 3) Calcolo window temporale simulazione
    # --------------------------------------------------
    if start_override is not None:
        primo = pd.to_datetime(start_override)
    else:
        lotti['Giorno'] = pd.to_datetime(lotti['Giorno'])
        primo = lotti['Giorno'].min().replace(hour=6, minute=0)
    fine = lotti['Giorno'].max() + timedelta(days=1)

    # --------------------------------------------------
    # 4) Creazione timeline per output risorse
    # --------------------------------------------------
    total_minutes = int((fine - primo).total_seconds() // 60)
    timestamps = [primo + timedelta(minutes=i * gran) for i in range(total_minutes // gran)]
    df_persone = pd.DataFrame({'timestamp': timestamps, 'Persone_occupate': 0})
    df_energia = pd.DataFrame({'timestamp': timestamps, 'Energia': 0.0})
    df_carrelli = pd.DataFrame({'timestamp': timestamps, 'Carrelli_occupati': 0})
    risultati = []

    # --------------------------------------------------
    # 5) Setup SimPy e risorse
    # --------------------------------------------------
    env = simpy.Environment()
    persone_res = simpy.Resource(env, capacity=mp or 1)
    carrelli_res = simpy.Resource(env, capacity=mc or 1)
    risorse = {}
    for mac in df_tempi['Macchina'].unique():
        cap = machine_caps.get(mac, 1)
        risorse[mac] = simpy.Resource(env, capacity=cap)

    # --------------------------------------------------
    # 6) Pre-calcolo mappe tempi/equivalenze/ritardi
    # --------------------------------------------------
    tempo_col = 'Tempo_Minuti' if 'Tempo_Minuti' in df_tempi.columns else 'Tempo'
    tempo_map = df_tempi.set_index('Fase')[tempo_col].to_dict()
    eq_map = { (r['Formato'], r['Fase']): r['Equivalenza_Unita']
               for _, r in df_equivalenze.iterrows() }

    post_map = {}
    if include_post:
        for _, r in df_posticipi.iterrows():
            key = (r.get('Lotto', r.get('lotto')), r['Fase'])
            post_map[key] = post_map.get(key, 0) + r.iloc[-1]

    fisio_map = {}
    if include_fisio:
        for _, r in df_posticipi_fisiologici.iterrows():
            key = (r['FORMATO'], r['FASE'], r['QUANDO'])
            fisio_map[key] = fisio_map.get(key, 0) + r['TEMPO']

    # --------------------------------------------------
    # 7) Helper: turnazione
    # --------------------------------------------------
    def turnazione(fase, now):
        dt = primo + timedelta(minutes=now)
        base = work_ven if dt.weekday() == fri38 else work_std
        if fase in config.get('Turni_modificati', []):
            base += extension
        night = workday - base
        weekend = night + workday * 2
        return base, night, weekend

    # --------------------------------------------------
    # 8) Helper: durata e risorse di fase
    # --------------------------------------------------
    def time_and_resources(fase, row, qty, fmt):
        if fase != 'AUTOCLAVI':
            dur_base = (qty / float(row['Pezzi'])) * float(row['Tempo'])
        else:
            dur_base = float(row['Tempo'])
        dur = dur_base * (1 + margin) * (1 + random.uniform(-variability, variability))
        pers = int(row.get('Addetti', 1))
        en = float(row.get('EnergiaFase', 0))
        carr = int(row.get('Carrelli', 0))  # default a 0 se colonna mancante
        if fase == 'RAFFREDDAMENTO':
            dur = 0
            pers = en = carr = 0
        return int(dur), pers, en, carr

    # --------------------------------------------------
    # 9) Processo SimPy per ogni lotto
    # --------------------------------------------------
    def process_lotto(rec):
        yield env.timeout(int(rec.get('DifferenzaTempo', 0)) * workday)
        for _, fr in df_tempi.iterrows():
            fase = fr['Fase']
            t0 = tempo_map.get(fase, 0)
            eq = eq_map.get((rec['Formato'], fase), 1.0)
            dur = t0 * eq \
                  + post_map.get((rec['ID_Lotto'], fase), 0) \
                  + fisio_map.get((rec['Formato'], fase, 'INIZIO_FASE'), 0)

            remaining = int(dur)
            while remaining > 0:
                now = env.now
                work, night, weekend = turnazione(fase, now)
                avail = work - (now % workday)
                chunk = min(remaining, max(avail, 0))

                with risorse[fr['Macchina']].request() as rm, \
                     persone_res.request() as rp, \
                     carrelli_res.request() as rc:
                    yield rm & rp & rc
                    ist = env.now
                    yield env.timeout(chunk)
                    iend = env.now

                    risultati.append({
                        'ID_Lotto': rec['ID_Lotto'],
                        'Fase': fase,
                        'Start': ist,
                        'End': iend
                    })

                    ts = primo + timedelta(minutes=int(ist))
                    df_persone.loc[df_persone['timestamp'] == ts, 'Persone_occupate'] += len(persone_res.users)
                    df_carrelli.loc[df_carrelli['timestamp'] == ts, 'Carrelli_occupati'] += len(carrelli_res.users)
                    _, _, e, _ = time_and_resources(fase, fr, rec['Quantita'], rec['Formato'])
                    df_energia.loc[df_energia['timestamp'] == ts, 'Energia'] += e

                remaining -= chunk
                if remaining > 0:
                    pause = weekend if (primo + timedelta(minutes=now)).weekday() == fri38 else night
                    yield env.timeout(pause)

            late = fisio_map.get((rec['Formato'], fase, 'FINE_FASE'), 0)
            if late:
                yield env.timeout(late)

    # --------------------------------------------------
    # 10) Avvio processi e run
    # --------------------------------------------------
    for _, lot in lotti.iterrows():
        env.process(process_lotto(lot))
    env.run()

    # --------------------------------------------------
    # 11) Conversione risultati
    # --------------------------------------------------
    df_ris = pd.DataFrame(risultati)
    return df_ris, df_persone, df_energia, df_carrelli
