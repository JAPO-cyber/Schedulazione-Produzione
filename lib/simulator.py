"""
simulator.py
Moduli di simulazione per schedulazione produzione.
Questa versione assume che i DataFrame (df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici)
siano già caricati esternamente (es. in Streamlit) e passati come argomenti.
"""
import simpy
import pandas as pd
from datetime import timedelta

# --- Parametri di turno e configurazione globale ---
tempo_lavoro_giornaliero_std = 480 * 2       # due turni da 8h
tempo_lavoro_giornaliero_ven = 480 * 2 - 120 # venerdì fine anticipato di 2h
tempo_dellagiornata = 480 * 3               # tre turni da 8h
tempo_allungamento_turno = 0                # minuti di estensione dopo le 20:00
turnazione_38 = 10                           # indice weekday per turno 38h
Turni_modificati = ['RIP-RIPARTIZIONE', 'PULIZIA', 'AUTOCLAVI']


def Turnazione(fase, inizio_dt):
    """
    Restituisce i minuti di lavoro disponibili,
    minuti di pausa notturna e pause weekend per la fase.
    """
    # calcola minuti lavorativi base
    if inizio_dt.weekday() == turnazione_38:
        base = tempo_lavoro_giornaliero_ven + (tempo_allungamento_turno if fase in Turni_modificati else 0)
    else:
        base = tempo_lavoro_giornaliero_std + (tempo_allungamento_turno if fase in Turni_modificati else 0)
    night = tempo_dellagiornata - base
    weekend = night + 480 * 3 * 2
    return base, night, weekend


def Tempo_fase(fase, riga, quantita):
    """
    Calcola durata teorica, addetti, energia e carrelli per la fase.
    """
    # durata in minuti
    if fase != 'AUTOCLAVI':
        tt = float(riga['Tempo'])
        pu = float(riga['Pezzi'])
        durata = int((quantita / pu) * tt)
    else:
        durata = int(float(riga['Tempo']))
    persone = int(riga.get('Addetti', 1))
    energia = float(riga.get('EnergiaFase', 0))
    carrelli = int(riga.get('Carrelli', 0))
    # eccezione raffreddamento
    if fase == 'RAFFREDDAMENTO':
        persone = energia = carrelli = 0
        durata = 0
    return durata, persone, energia, carrelli


def esegui_simulazione(
    df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici,
    data_inizio, includi_posticipi=True, includi_fisiologici=False,
    max_carrelli=None, max_personale=None
):
    """
    Argomenti:
      df_lotti: DataFrame con colonne ID_Lotto, Formato, Quantita, Giorno, DifferenzaTempo
      df_tempi: DataFrame con colonne Fase, Macchina, Tempo, Tempo_Minuti, etc.
      df_posticipi: DataFrame con ritardi autorizzati
      df_equivalenze: DataFrame con mapping Formato+Fase -> Equivalenza_Unita
      df_posticipi_fisiologici: DataFrame con ritardi fisiologici
      data_inizio: data di partenza (stringa o datetime)
      includi_posticipi/fisiologici: flag booleani
      max_carrelli/max_personale: capacità massime
    Restituisce:
      df_risultati, df_persone, df_energia, df_carrelli
    """

    # pre-elaborazioni e mapping per ottimizzazione
    lotti = df_lotti.copy()
    tempi = df_tempi.copy()
    posticipi = df_posticipi.copy()
    equiv = df_equivalenze.copy()
    fisio = df_posticipi_fisiologici.copy()

    # data di start in minuti
    start_dt = pd.to_datetime(data_inizio)
    # ricava range temporale da lotti.Giorno
    if 'Giorno' in lotti:
        lotti['Giorno'] = pd.to_datetime(lotti['Giorno'])
        primo = lotti['Giorno'].min()
        lotti['DifferenzaTempo'] = (lotti['Giorno'] - primo).dt.days
        fine = lotti['Giorno'].max() + timedelta(days=1)
    else:
        primo = start_dt
        fine = start_dt + timedelta(days=1)

    # timeline minutata per output time-series
    total_minutes = int((fine - primo).total_seconds() // 60)
    timestamps = [primo + timedelta(minutes=m) for m in range(total_minutes)]

    # inizializza DataFrame vuoti per risorse
    df_persone = pd.DataFrame({'timestamp': timestamps, 'Persone_occupate': 0})
    df_energia = pd.DataFrame({'timestamp': timestamps, 'Energia': 0.0})
    df_carrelli = pd.DataFrame({'timestamp': timestamps, 'Carrelli_occupati': 0})
    risultati = []  # lista di dict per tempi di fase

    # crea ambiente SimPy e risorse
    env = simpy.Environment()
    persone_res = simpy.Resource(env, capacity=max_personale or 1)
    carrelli_res = simpy.Resource(env, capacity=max_carrelli or 1)

    # pre-calcola dict per tempi e equivalenze
    tempo_map = tempi.set_index('Fase')['Tempo_Minuti'].to_dict()
    eq_map = {(f, fase): u for (_, f, fase, u) in zip(equiv.index, equiv['Formato'], equiv['Fase'], equiv['Equivalenza_Unita'])}

    # costruisci dizionari di ritardi per lookup O(1)
    post_map = {}
    if includi_posticipi:
        for _, row in posticipi.iterrows():
            key = (row.get('Lotto', row.get('lotto')), row['Fase'])
            post_map.setdefault(key, 0)
            post_map[key] += row.iloc[-1]  # assume ultima colonna Minuti
    fisio_map = {}
    if includi_fisiologici:
        for _, row in fisio.iterrows():
            key = (row['FORMATO'], row['FASE'], row['QUANDO'])
            fisio_map.setdefault(key, 0)
            fisio_map[key] += row['TEMPO']

    def process_lotto(rec):
        """Processo SimPy per un singolo lotto e tutte le sue fasi."""
        # attendi eventuale ritardo iniziale (DifferenzaTempo * giorni lavorativi)
        yield env.timeout(int(rec.get('DifferenzaTempo', 0)) * tempo_dellagiornata)
        for _, fase_row in tempi.iterrows():
            fase = fase_row['Fase']
            # tempo base * equivalenza
            t0 = tempo_map.get(fase, 0)
            eq = eq_map.get((rec['Formato'], fase), 1.0)
            durata = t0 * eq
            # aggiungi posticipi autorizzati
            durata += post_map.get((rec['ID_Lotto'], fase), 0)
            # aggiungi ritardi fisiologici INIZIO_FASE
            durata += fisio_map.get((rec['Formato'], fase, 'INIZIO_FASE'), 0)

            remaining = int(durata)
            # scomponi su turni
            while remaining > 0:
                now = env.now
                current_dt = primo + timedelta(minutes=now)
                work, night, weekend = Turnazione(fase, current_dt)
                available = work - (now % tempo_dellagiornata)
                chunk = min(remaining, max(0, available))

                # acquisisci risorse
                with persone_res.request() as rp, carrelli_res.request() as rc:
                    yield rp & rc
                    start = env.now
                    yield env.timeout(chunk)
                    end = env.now
                    # registra risultato di fase
                    risultati.append({'ID_Lotto': rec['ID_Lotto'], 'Fase': fase,
                                       'Start': start, 'End': end})
                    # timestamp effettivo
                    ts = primo + timedelta(minutes=int(start))
                    # aggiorna time-series (ottimizzabile in bulk)
                    df_persone.loc[df_persone['timestamp']==ts, 'Persone_occupate'] += len(persone_res.users)
                    df_carrelli.loc[df_carrelli['timestamp']==ts, 'Carrelli_occupati'] += len(carrelli_res.users)
                    dur_fase, pers, en, carr = Tempo_fase(fase, fase_row, rec['Quantita'])
                    df_energia.loc[df_energia['timestamp']==ts, 'Energia'] += en

                remaining -= chunk
                # pausa tra turni
                if remaining > 0:
                    pause = weekend if current_dt.weekday()==4 else night
                    yield env.timeout(pause)
            # ritardi fisiologici FINE_FASE
            fine_delay = fisio_map.get((rec['Formato'], fase, 'FINE_FASE'), 0)
            if fine_delay:
                yield env.timeout(fine_delay)

    # avvia tutti i processi in parallelo
    for _, lotto in lotti.iterrows():
        env.process(process_lotto(lotto))

    env.run()

    # converte risultati
    df_risultati = pd.DataFrame(risultati)
    return df_risultati, df_persone, df_energia, df_carrelli

# --- Fine simulator.py ---

# Ottimizzazioni suggerite:
# 1. Raccogli aggiornamenti time-series in array e trasferiscili a DataFrame solo alla fine.
# 2. Valuta l'uso di SimPy Monitor per tracciare occupancy anziché .loc ogni evento.
# 3. Pre-alloca liste per risultati anziché append su dict, se volumi molto grandi.
# 4. Considera algoritmi più vettoriali per ritardi e equivalenze.

