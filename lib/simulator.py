import simpy
import pandas as pd
import numpy as np
import random
from datetime import datetime, timedelta

# Parametri manuali della simulazione e schedulazione
tempo_lavoro_giornaliero_std = 480 * 2  # due turni da 8h
tempo_lavoro_giornaliero_ven = 480 * 2 - 120  # venerdì fine anticipato di 2h
tempo_dellagiornata = 480 * 3  # tre turni da 8h
tempo_allungamento_turno = 0    # minuti di estensione dopo le 20:00 (opzionale)
turnazione_38 = 10              # venerdì considerato giorno di 38h
Turni_modificati = ['RIP-RIPARTIZIONE', 'PULIZIA', 'AUTOCLAVI']

# Helper: calcola risorse per turno
def Turnazione(fase, inizio_dt):
    if inizio_dt.weekday() == turnazione_38:
        base = tempo_lavoro_giornaliero_ven + (tempo_allungamento_turno if fase in Turni_modificati else 0)
    else:
        base = tempo_lavoro_giornaliero_std + (tempo_allungamento_turno if fase in Turni_modificati else 0)
    night = tempo_dellagiornata - base
    weekend = night + 480 * 3 * 2
    return base, night, weekend

# Helper: tempo, persone, energia, carrelli per fase
def Tempo_fase(fase, riga_fase, lotto, quantita, formato):
    if fase != 'AUTOCLAVI':
        tt = float(riga_fase['Tempo'])
        pu = float(riga_fase['Pezzi'])
        dur = int((quantita / pu) * tt)
    else:
        dur = int(float(riga_fase['Tempo']))
    persone = int(riga_fase.get('Addetti', 1))
    energia = float(riga_fase.get('EnergiaFase', 0))
    carrelli = int(riga_fase.get('Carrelli', 0))
    if fase == 'RAFFREDDAMENTO':
        persone = energia = 0
        carrelli = 0
    return dur, persone, energia, carrelli

# Helper: aggiorna dati tempo-serie
def aggiorna(df_time, timestamp, valore, colonna):
    if timestamp in df_time['timestamp'].values:
        df_time.loc[df_time['timestamp'] == timestamp, colonna] += valore

# Funzione principale

def esegui_simulazione(df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici,
                       data_inizio, includi_posticipi=True, includi_fisiologici=False,
                       max_carrelli=None, max_personale=None):
    # Prepara dati di input
    lotti = df_lotti.copy()
    tempi = df_tempi.copy()
    posticipi = df_posticipi.copy()
    equiv = df_equivalenze.copy()
    fisio = df_posticipi_fisiologici.copy()

    # Imposta date di simulazione
a    inizio_sim = pd.to_datetime(data_inizio)
    # Calcola ritardi in giorni
a    if 'Giorno' in lotti.columns:
        lotti['Giorno'] = pd.to_datetime(lotti['Giorno'])
        primo = lotti['Giorno'].min()
        lotti['DifferenzaTempo'] = (lotti['Giorno'] - primo).dt.days
        fine = lotti['Giorno'].max() + timedelta(days=1)
    else:
        primo = inizio_sim
        fine = inizio_sim + timedelta(days=1)

    # Serie temporale per output
    date_list = [inizio_sim + timedelta(minutes=x) for x in range(int((fine - inizio_sim).total_seconds() // 60))]
    df_persone = pd.DataFrame({'timestamp': date_list, 'Persone_occupate': 0})
    df_energia = pd.DataFrame({'timestamp': date_list, 'Energia': 0.0})
    df_carrelli = pd.DataFrame({'timestamp': date_list, 'Carrelli_occupati': 0})

    # Risultati di produzione
    risultati = []

    # Setup simpy
env = simpy.Environment()
    persone_res = simpy.Resource(env, capacity=max_personale or 1)
    carrelli_res = simpy.Resource(env, capacity=max_carrelli or 1)

    # Mappa tempi
    tempo_map = dict(zip(tempi['Fase'], tempi['Tempo_Minuti'] if 'Tempo_Minuti' in tempi.columns else tempi['Tempo']))

    def process_lotto(rec):
        id_l = rec['ID_Lotto']
        formato = rec.get('Formato', None)
        # ritardo iniziale
        if 'DifferenzaTempo' in rec:
            yield env.timeout(int(rec['DifferenzaTempo']) * tempo_dellagiornata)
        for _, r in tempi.iterrows():
            fase = r['Fase']
            dur0 = tempo_map.get(fase, 0)
            # equivalenze
            mask_e = (equiv['Formato'] == formato) & (equiv['Fase'] == fase)
            eq = equiv.loc[mask_e, 'Equivalenza_Unita'].iloc[0] if not equiv[mask_e].empty else 1.0
            dur = dur0 * eq
            # posticipi autorizzati
            if includi_posticipi:
                m = (posticipi.get('Lotto', posticipi.get('lotto',None)) == id_l) & (posticipi['Fase'] == fase)
                dur += posticipi.loc[m, posticipi.columns[-1]].sum() if not posticipi[m].empty else 0
            # posticipi fisiologici
            if includi_fisiologici:
                m2 = (fisio['FASE'] == fase) & (fisio['FORMATO'] == formato)
                dur += fisio.loc[m2, 'Ritardo_Fisiologico_Min'].sum() if not fisio[m2].empty else 0
            # risorse
            with persone_res.request() as rp:
                yield rp
                with carrelli_res.request() as rc:
                    yield rc
                    start = env.now
                    yield env.timeout(dur)
                    end = env.now
                    # registra produzione
                    risultati.append({'ID_Lotto': id_l, 'Fase': fase, 'Start': start, 'End': end})
                    # registra utilizzo
                    tstamp_start = (inizio_sim + timedelta(minutes=int(start)))
                    aggiorna(df_persone, tstamp_start, len(persone_res.users), 'Persone_occupate')
                    aggiorna(df_carrelli, tstamp_start, len(carrelli_res.users), 'Carrelli_occupati')
                    # energia
                    tempo_f, pers_u, en_u, _, _, _ = Tempo_fase(fase, r, id_l, rec.get('Quantita',0), formato)
                    aggiorna(df_energia, tstamp_start, en_u, 'Energia')
    # lancia processi
    for _, lot in lotti.iterrows():
        env.process(process_lotto(lot))

    env.run()

    df_ris = pd.DataFrame(risultati)
    return df_ris, df_persone, df_energia, df_carrelli

