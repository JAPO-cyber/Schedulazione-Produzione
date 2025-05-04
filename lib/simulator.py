import simpy
import pandas as pd

def esegui_simulazione(df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici,
                       data_inizio, includi_posticipi, includi_fisiologici, max_carrelli, max_personale):
    """
    Esegui la simulazione di schedulazione produzione.
    Restituisce:
      df_risultati: colonne ['ID_Lotto','Fase','Start','End']
      df_risorse: colonne ['Time','Persone_occupate','Carrelli_occupati']
    """
    # Ambiente di simulazione
    env = simpy.Environment()
    # Risorse
    persone = simpy.Resource(env, capacity=max_personale or 1)
    carrelli = simpy.Resource(env, capacity=max_carrelli or 1)

    # Mappe tempi
    tempi_map = dict(zip(df_tempi['Fase'], df_tempi['Tempo_Minuti']))
    
    results = []
    usage = []

    def process_lotto(record):
        id_lotto = record['ID_Lotto']
        formato = record.get('Formato', None)
        for _, row in df_tempi.iterrows():
            fase = row['Fase']
            durata = tempi_map.get(fase, 0)
            # Applicazione equivalenza
            eq = 1.0
            mask_eq = (df_equivalenze['Formato']==formato) & (df_equivalenze['Fase']==fase)
            if not df_equivalenze[mask_eq].empty:
                eq = df_equivalenze[mask_eq]['Equivalenza_Unita'].iloc[0]
            actual_time = durata * eq

            # Posticipi autorizzati
            if includi_posticipi:
                mask_p = df_posticipi['Fase']==fase
                if not df_posticipi[mask_p].empty:
                    actual_time += df_posticipi[mask_p]['Ritardo_Minuti'].sum()
            # Posticipi fisiologici
            if includi_fisiologici:
                mask_pf = df_posticipi_fisiologici['Fase']==fase
                if not df_posticipi_fisiologici[mask_pf].empty:
                    actual_time += df_posticipi_fisiologici[mask_pf]['Ritardo_Fisiologico_Min'].sum()

            # Richiesta risorse
            with persone.request() as req_p:
                yield req_p
                with carrelli.request() as req_c:
                    yield req_c
                    start = env.now
                    yield env.timeout(actual_time)
                    end = env.now
                    results.append({
                        'ID_Lotto': id_lotto,
                        'Fase': fase,
                        'Start': start,
                        'End': end
                    })
                    usage.append({
                        'Time': start,
                        'Persone_occupate': len(persone.users),
                        'Carrelli_occupati': len(carrelli.users)
                    })

    # Avvio dei processi per ogni lotto
    for _, lot in df_lotti.iterrows():
        env.process(process_lotto(lot))

    # Esecuzione simulazione
    env.run()

    df_risultati = pd.DataFrame(results)
    df_risorse = pd.DataFrame(usage)
    return df_risultati, df_risorse
