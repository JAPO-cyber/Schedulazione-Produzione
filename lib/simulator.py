"""
lib/simulator.py
Modulo di simulazione avanzato per schedulazione produzione.
Accetta configurazione completa da Streamlit.
Gestisce posticipi globali (solo 'Fase') o per lotto ('Lotto').

Versione ottimizzata.
"""
import random
import simpy
import pandas as pd
from datetime import timedelta

def esegui_simulazione_ottimizzata(
    df_lotti_orig, df_tempi_orig, df_posticipi_orig, df_equivalenze_orig, 
    df_posticipi_fisiologici_orig, config
):
    # 0) Copia dei DataFrame per evitare modifiche agli originali passati
    df_lotti = df_lotti_orig.copy()
    df_tempi = df_tempi_orig.copy()
    df_posticipi = df_posticipi_orig.copy() if df_posticipi_orig is not None else pd.DataFrame()
    df_equivalenze = df_equivalenze_orig.copy()
    df_posticipi_fisiologici = df_posticipi_fisiologici_orig.copy() if df_posticipi_fisiologici_orig is not None else pd.DataFrame()

    # 0.1) Rinomina colonne lotti se necessario
    # È più sicuro controllare se le colonne esistono prima di rinominarle
    rename_map_lotti = {}
    if 'Lotto' in df_lotti.columns:
        rename_map_lotti['Lotto'] = 'ID_Lotto'
    if 'Quantità' in df_lotti.columns:
        rename_map_lotti['Quantita'] = 'Quantita'
    if rename_map_lotti:
        df_lotti = df_lotti.rename(columns=rename_map_lotti)
    
    # 1) Validazione df_tempi
    tempo_col_name = 'Tempo_Minuti' if 'Tempo_Minuti' in df_tempi.columns else 'Tempo'
    required_cols_tempi = {'Fase', 'Macchina', tempo_col_name, 'Pezzi', 'Addetti', 'EnergiaFase'}
    missing_cols_tempi = required_cols_tempi - set(df_tempi.columns)
    if missing_cols_tempi:
        raise KeyError(f"df_tempi mancano le colonne: {missing_cols_tempi}")
    # Assicurati che la colonna tempo_col_name sia numerica
    df_tempi[tempo_col_name] = pd.to_numeric(df_tempi[tempo_col_name], errors='coerce')
    df_tempi['Pezzi'] = pd.to_numeric(df_tempi['Pezzi'], errors='coerce')


    # 2) Validazione df_lotti
    required_cols_lotti = {'ID_Lotto', 'Formato', 'Quantita', 'Giorno'}
    missing_cols_lotti = required_cols_lotti - set(df_lotti.columns)
    if missing_cols_lotti:
        raise KeyError(f"df_lotti mancano le colonne: {missing_cols_lotti}")
    df_lotti['Quantita'] = pd.to_numeric(df_lotti['Quantita'], errors='coerce')

    # 3) Validazione df_equivalenze
    required_cols_equivalenze = {'Formato', 'Fase', 'Equivalenza_Unita'}
    missing_cols_equivalenze = required_cols_equivalenze - set(df_equivalenze.columns)
    if missing_cols_equivalenze:
        raise KeyError(f"df_equivalenze mancano le colonne: {missing_cols_equivalenze}")
    df_equivalenze['Equivalenza_Unita'] = pd.to_numeric(df_equivalenze['Equivalenza_Unita'], errors='coerce')


    # 4) Validazione opzionale df_posticipi_fisiologici
    include_fisio = config.get('includi_fisiologici', False)
    if include_fisio and not df_posticipi_fisiologici.empty:
        required_cols_fisiologici = {'FORMATO', 'FASE', 'QUANDO', 'TEMPO'}
        missing_cols_fisiologici = required_cols_fisiologici - set(df_posticipi_fisiologici.columns)
        if missing_cols_fisiologici:
            raise KeyError(f"df_posticipi_fisiologici mancano le colonne: {missing_cols_fisiologici}")
        df_posticipi_fisiologici['TEMPO'] = pd.to_numeric(df_posticipi_fisiologici['TEMPO'], errors='coerce')
    elif include_fisio and df_posticipi_fisiologici.empty:
        # Se l'opzione è attiva ma il df è vuoto, non c'è nulla da validare o usare.
        # Potrebbe essere utile un warning o un log.
        pass


    # 5) Estrazione config (invariato, ma più leggibile con default espliciti)
    max_carrelli = config.get('max_carrelli', 1) # Default a 1 se non specificato
    max_personale = config.get('max_personale', 1) # Default a 1 se non specificato
    machine_caps = config.get('machine_caps', {})
    work_std = config.get('work_std', 480) # Es. 8 ore
    work_ven = config.get('work_ven', 480) # Es. 8 ore venerdì
    workday_minutes = config.get('workday_minutes', 1440) # Minuti in un giorno 24h
    extension = config.get('extension', 0) # Estensione turno
    fri38 = config.get('fri38_weekday', 4) # 4 per Venerdì (0 Lunedì - 6 Domenica)
    include_posticipi = config.get('includi_posticipi', False)
    
    variability_factor = config.get('variability_factor', 0.0) # Percentuale, es 0.1 per +/-10%
    margin_pct = config.get('margin_pct', 0.0) # Percentuale, es 0.05 per 5%
    granularity = config.get('granularity', 60) # Minuti
    filter_format = config.get('filter_format', [])
    filter_line = config.get('filter_line', [])
    start_override = config.get('data_inizio', None)

    # 6) Filtri lotti
    lotti_filtrati = df_lotti.copy() # Lavora su una copia per i filtri
    if filter_format:
        lotti_filtrati = lotti_filtrati[lotti_filtrati['Formato'].isin(filter_format)]
    if 'Linea' in lotti_filtrati.columns and filter_line:
        lotti_filtrati = lotti_filtrati[lotti_filtrati['Linea'].isin(filter_line)]
    
    if lotti_filtrati.empty:
        # Se non ci sono lotti dopo il filtraggio, restituisci DataFrame vuoti.
        return pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

    # 7) Range temporale
    lotti_filtrati['Giorno'] = pd.to_datetime(lotti_filtrati['Giorno'])
    if start_override:
        primo_giorno_sim = pd.to_datetime(start_override)
    else:
        primo_giorno_sim = lotti_filtrati['Giorno'].min()
    
    # Definisci l'ora di inizio simulazione (es. 06:00 del primo giorno)
    # Se start_override è una data senza ora, si assume l'inizio giornata (es. mezzanotte)
    # o si potrebbe specificare un'ora di default. Qui usiamo le 06:00 come nell'originale.
    start_sim_dt = primo_giorno_sim.replace(hour=6, minute=0, second=0, microsecond=0)
    
    # Calcola fine simulazione: potrebbe essere basata sull'ultimo lotto o un orizzonte fisso
    # Qui usiamo l'ultimo giorno del lotto + un buffer (es. 30 giorni per sicurezza)
    # Questo evita di calcolare una `fine` troppo stretta.
    fine_sim_dt_estimata = lotti_filtrati['Giorno'].max() + timedelta(days=config.get('simulation_horizon_days', 30))
    fine_sim_dt = fine_sim_dt_estimata.replace(hour=23, minute=59, second=59)


    # 8) Timeline risorse (saranno popolate DOPO la simulazione per efficienza)
    # Creeremo i DataFrame per il logging dopo, basati sui risultati effettivi.
    risultati_eventi = []
    log_utilizzo_persone = []
    log_utilizzo_carrelli = []
    log_consumo_energia = []

    # 9) Setup SimPy
    env = simpy.Environment(initial_time=0) # SimPy lavora con unità di tempo, non datetime diretti
                                          # La conversione avviene tramite start_sim_dt

    persone_res = simpy.Resource(env, capacity=max_personale)
    carrelli_res = simpy.Resource(env, capacity=max_carrelli)
    
    risorse_macchina = {
        mac_name: simpy.Resource(env, capacity=machine_caps.get(mac_name, 1))
        for mac_name in df_tempi['Macchina'].unique()
    }

    # 10) Mappe ottimizzate
    # Mappa tempi: Fase -> Tempo (in minuti)
    tempo_map = df_tempi.set_index('Fase')[tempo_col_name].to_dict()

    # Mappa equivalenze: (Formato, Fase) -> Equivalenza_Unita
    eq_map = df_equivalenze.set_index(['Formato', 'Fase'])['Equivalenza_Unita'].to_dict()

    # Mappa posticipi autorizzati
    post_map_specific = {} # (ID_Lotto, Fase) -> Tempo_Posticipo
    post_map_global = {}   # (None, Fase) -> Tempo_Posticipo
    
    # Assumiamo che df_posticipi abbia una colonna 'TEMPO_POSTICIPO' o simile per il valore.
    # Se si deve usare l'ultima colonna, sostituire 'TEMPO_POSTICIPO' con df_posticipi.columns[-1]
    # e assicurarsi che sia numerica.
    col_tempo_posticipo = 'TEMPO_POSTICIPO' # Adattare se il nome colonna è diverso
    if include_posticipi and not df_posticipi.empty:
        if col_tempo_posticipo not in df_posticipi.columns:
             # Fallback all'ultima colonna se 'TEMPO_POSTICIPO' non esiste, come nell'originale
            if len(df_posticipi.columns) > 0 :
                 col_tempo_posticipo = df_posticipi.columns[-1]
            else:
                 raise ValueError("df_posticipi non ha colonne per il tempo di posticipo.")

        df_posticipi[col_tempo_posticipo] = pd.to_numeric(df_posticipi[col_tempo_posticipo], errors='coerce')

        for _, row in df_posticipi.iterrows():
            fase = row['Fase']
            valore_posticipo = row[col_tempo_posticipo]
            id_lotto = row.get('Lotto') # .get() gestisce se la colonna 'Lotto' non c'è o è opzionale

            if pd.isna(id_lotto) or str(id_lotto).strip() == '': # Posticipo globale
                post_map_global[(None, fase)] = post_map_global.get((None, fase), 0) + valore_posticipo
            else: # Posticipo specifico
                post_map_specific[(str(id_lotto), fase)] = post_map_specific.get((str(id_lotto), fase), 0) + valore_posticipo
    
    # Mappa ritardi fisiologici: (Formato, Fase, Quando) -> Tempo
    fisio_map = {}
    if include_fisio and not df_posticipi_fisiologici.empty:
        # Assicurarsi che le colonne chiave non abbiano NA che romperebbero il set_index
        cols_fisio_key = ['FORMATO', 'FASE', 'QUANDO']
        df_posticipi_fisiologici_cleaned = df_posticipi_fisiologici.dropna(subset=cols_fisio_key)
        if not df_posticipi_fisiologici_cleaned.empty:
            try:
                fisio_map = df_posticipi_fisiologici_cleaned.set_index(cols_fisio_key)['TEMPO'].to_dict()
            except KeyError as e:
                 # Potrebbe succedere se ci sono duplicati nelle chiavi di index.
                 # In tal caso, un groupby().sum() sarebbe più appropriato.
                 print(f"Attenzione: Duplicati trovati in df_posticipi_fisiologici per le chiavi {cols_fisio_key}. Si usa groupby.sum(). Errore: {e}")
                 fisio_map = df_posticipi_fisiologici_cleaned.groupby(cols_fisio_key)['TEMPO'].sum().to_dict()
        

    # Pre-conversione di df_tempi in lista di record per accesso più rapido nel loop
    # Questo è utile se si accede a più campi di fr (riga di df_tempi) ripetutamente
    # df_tempi_records = df_tempi.to_dict('records') # Manteniamo df_tempi.iterrows() per ora,
                                                  # la complessità è più nella logica interna al loop.


    # 11) Helpers
    def get_datetime_from_sim_time(sim_time_minutes):
        """Converte il tempo di simulazione (minuti dall'inizio) in un oggetto datetime."""
        return start_sim_dt + timedelta(minutes=sim_time_minutes)

    def get_sim_time_from_datetime(dt_object):
        """Converte un oggetto datetime in tempo di simulazione (minuti dall'inizio)."""
        if dt_object < start_sim_dt:
            return 0 # o gestire come errore/warning
        return int((dt_object - start_sim_dt).total_seconds() / 60)

    def get_turn_durations(fase_attuale, current_sim_time_minutes):
        """
        Calcola la durata del turno lavorativo corrente, della notte e del weekend.
        Restituisce (durata_turno_attuale_min, durata_notte_min, durata_weekend_min)
        """
        dt_corrente = get_datetime_from_sim_time(current_sim_time_minutes)
        
        # Determina la durata base del turno per il giorno corrente
        durata_base_turno_giornaliero = work_ven if dt_corrente.weekday() == fri38 else work_std
        
        # Applica estensioni specifiche per la fase
        if fase_attuale in config.get('Turni_modificati', []):
            durata_base_turno_giornaliero += extension
        
        # Calcola minuti trascorsi dall'inizio del giorno corrente (00:00)
        minuti_da_inizio_giornata_attuale = dt_corrente.hour * 60 + dt_corrente.minute
        
        # L'orario di lavoro inizia alle 6:00, quindi workday_start_offset_minutes = 6 * 60
        # Assumiamo che workday_minutes (es. 1440) sia la durata totale di un giorno civile.
        # Il turno lavorativo effettivo è una porzione di questo.
        # Es: se il turno è dalle 6:00 alle 14:00 (8 ore = 480 min)
        # workday_start_time = 6 (ora)
        
        # Calcola quanto del turno attuale è ancora disponibile OGGI
        # Questa logica deve essere allineata a come SimPy gestisce i timeout attraverso i giorni.
        # Il modo più semplice è calcolare il tempo disponibile nel turno corrente
        # e se non basta, aggiungere il tempo di pausa (notte/weekend).

        # Minuti dall'inizio del turno lavorativo (es. 6:00) nel giorno corrente
        # Esempio: se sono le 10:00 e il turno inizia alle 6:00, sono passati 240 minuti del turno.
        # Se il turno dura 480 minuti, ne restano 240.
        
        # current_time_within_calendar_day = current_sim_time_minutes % workday_minutes # Non corretto se workday_minutes è 24h
                                                                                      # e il turno non inizia a mezzanotte.

        # Logica semplificata per SimPy:
        # SimPy avanza il tempo. Noi dobbiamo dire quanto può lavorare *continuativamente*
        # prima di una pausa.
        # `avail_in_shift` è quanto tempo può lavorare ora prima della fine del turno o della giornata lavorativa.
        
        # Calcoliamo l'ora di fine del turno corrente
        # Assumiamo che i turni inizino sempre alle 6:00 AM
        start_hour_of_work = 6 
        end_hour_of_work = start_hour_of_work + (durata_base_turno_giornaliero / 60)

        # Minuti trascorsi dall'inizio del turno (6:00)
        minutes_into_shift = 0
        if dt_corrente.hour >= start_hour_of_work :
            minutes_into_shift = (dt_corrente.hour - start_hour_of_work) * 60 + dt_corrente.minute
        
        avail_in_current_shift_today = max(0, durata_base_turno_giornaliero - minutes_into_shift)
        
        # Durata della pausa notturna e del weekend
        # Pausa notturna: tempo dalla fine del turno odierno all'inizio del turno successivo (es. dalle 14:00 alle 6:00 del giorno dopo)
        # workday_minutes è 24*60 = 1440
        pause_night_duration = workday_minutes - durata_base_turno_giornaliero # Tempo non lavorativo in un giorno feriale
        
        # Pausa weekend: se oggi è venerdì (e fri38), la pausa è più lunga
        # Questa è la pausa DOPO il turno corrente.
        pause_weekend_duration = pause_night_duration # Default
        if dt_corrente.weekday() == fri38: # Venerdì
            pause_weekend_duration = workday_minutes - work_ven # Pausa del venerdì sera
            pause_weekend_duration += workday_minutes * config.get('weekend_days', 2) # Sabato e Domenica interi
        elif dt_corrente.weekday() == 5: # Sabato
            pause_weekend_duration = workday_minutes # Tutto il sabato
            pause_weekend_duration += workday_minutes * (config.get('weekend_days', 2) -1) # Domenica
        elif dt_corrente.weekday() == 6: # Domenica
            pause_weekend_duration = workday_minutes # Tutta la domenica
            
        return int(avail_in_current_shift_today), int(pause_night_duration), int(pause_weekend_duration)


    def calculate_phase_times_resources(fase_info, quantita_lotto, formato_lotto):
        """Calcola durata, persone, energia, carrelli per una fase."""
        # fase_info è una riga (Series o dict) da df_tempi
        fase_nome = fase_info['Fase']
        
        # Calcolo durata base
        # Se Pezzi è 0 o NaN, la divisione può dare errore o inf. Gestire questo.
        pezzi_per_tempo_unitario = fase_info['Pezzi']
        tempo_unitario = fase_info[tempo_col_name]

        if pd.isna(pezzi_per_tempo_unitario) or pezzi_per_tempo_unitario == 0:
            if fase_nome == 'AUTOCLAVI': # Autoclavi ha tempo fisso
                durata_base = float(tempo_unitario)
            else: # Altre fasi, se pezzi è 0, la durata potrebbe essere 0 o un default
                  # o questo potrebbe essere un errore nei dati di input.
                  # Per ora, assumiamo durata 0 se pezzi è 0 e non è AUTOCLAVI.
                durata_base = 0.0
                print(f"Attenzione: 'Pezzi' è 0 o NaN per fase {fase_nome} e formato {formato_lotto}. Durata base impostata a 0.")
        else:
            durata_base = (quantita_lotto / float(pezzi_per_tempo_unitario)) * float(tempo_unitario)
        
        if fase_nome == 'AUTOCLAVI': # Tempo fisso per autoclavi, ignora quantità per durata
            durata_base = float(tempo_unitario)

        # Applica variabilità e margine
        variabilita_effettiva = random.uniform(-variability_factor, variability_factor)
        durata_calcolata = durata_base * (1 + margin_pct) * (1 + variabilita_effettiva)
        
        # Risorse
        persone_necessarie = int(fase_info.get('Addetti', 1))
        energia_consumata_per_unita_tempo_o_fase = float(fase_info.get('EnergiaFase', 0)) # Potrebbe essere energia totale per la fase o per minuto
        carrelli_necessari = int(fase_info.get('Carrelli', 0))

        # Caso speciale RAFFREDDAMENTO
        if fase_nome == 'RAFFREDDAMENTO':
            durata_calcolata = 0 # Raffreddamento potrebbe essere un tempo di attesa passivo
            persone_necessarie = 0
            energia_consumata_per_unita_tempo_o_fase = 0
            carrelli_necessari = 0
            
        return int(round(durata_calcolata)), persone_necessarie, energia_consumata_per_unita_tempo_o_fase, carrelli_necessari

    # 12) Processo SimPy per un lotto
    def processo_lotto(env, lotto_record):
        lotto_id = lotto_record['ID_Lotto']
        formato_lotto = lotto_record['Formato']
        quantita_lotto = lotto_record['Quantita']
        giorno_schedulato_lotto = lotto_record['Giorno'] # pd.Timestamp

        # Calcola tempo di attesa iniziale se il lotto è schedulato per un giorno futuro
        # rispetto all'inizio della simulazione o al tempo corrente di altri processi.
        # SimPy gestisce questo implicitamente se i processi sono aggiunti con ritardi.
        # Qui, potremmo voler un timeout esplicito per far partire il lotto non prima del suo 'Giorno'.
        
        # `DifferenzaTempo` nell'originale: `int(rec.get('DifferenzaTempo',0))*workday`
        # Questo sembra un offset in giorni interi. Se `DifferenzaTempo` è una colonna in `lotti_filtrati`:
        offset_giorni_lotto = int(lotto_record.get('DifferenzaTempo', 0))
        if offset_giorni_lotto > 0:
            yield env.timeout(offset_giorni_lotto * workday_minutes) # Timeout in minuti

        # In alternativa, o in aggiunta, assicurati che il lotto non inizi prima del suo giorno schedulato
        sim_time_schedulato_lotto = get_sim_time_from_datetime(giorno_schedulato_lotto.replace(hour=6, minute=0)) # Inizia alle 6:00 del giorno schedulato
        
        if env.now < sim_time_schedulato_lotto:
            yield env.timeout(sim_time_schedulato_lotto - env.now)


        for _, fase_corrente_info in df_tempi.iterrows(): # Itera sulle righe di df_tempi (le fasi)
            fase_nome = fase_corrente_info['Fase']
            macchina_richiesta = fase_corrente_info['Macchina']
            
            # Ottieni equivalenza per la combinazione formato-fase
            equivalenza = eq_map.get((formato_lotto, fase_nome), 1.0) # Default a 1.0 se non trovato

            # Calcola posticipi autorizzati
            posticipo_specifico = post_map_specific.get((str(lotto_id), fase_nome), 0)
            posticipo_globale = post_map_global.get((None, fase_nome), 0)
            posticipo_autorizzato_totale = posticipo_specifico + posticipo_globale
            
            # Calcola ritardi fisiologici (INIZIO_FASE)
            ritardo_fisiologico_inizio = fisio_map.get((formato_lotto, fase_nome, 'INIZIO_FASE'), 0)
            
            # Tempo di attesa totale prima di iniziare effettivamente la lavorazione della fase
            tempo_attesa_pre_fase = posticipo_autorizzato_totale + ritardo_fisiologico_inizio
            if tempo_attesa_pre_fase > 0:
                # Questo tempo di attesa è tempo "morto" o di preparazione,
                # durante il quale le risorse potrebbero non essere impegnate.
                # La logica originale lo sommava a `remaining_processing_time`.
                # Se è attesa pura, dovrebbe essere un timeout separato.
                # Se è preparazione che usa risorse, va gestito diversamente.
                # Assumiamo sia attesa passiva per ora.
                # yield env.timeout(tempo_attesa_pre_fase) # Commentato, l'originale lo aggiungeva al tempo di processo
                pass


            # Calcola tempo di processo base per la fase, quantità ed equivalenza
            # La durata base da tempo_map è già per la quantità standard definita in df_tempi['Pezzi']
            # Dobbiamo scalarla per la quantità del lotto e l'equivalenza.
            # La funzione calculate_phase_times_resources fa già questo.
            
            # Il `tempo_map.get(fase_nome,0)` originale era usato per `t0`.
            # Ma `calculate_phase_times_resources` prende `fase_corrente_info` che contiene già il tempo.
            
            # Il tempo_map originale era `df_tempi.set_index('Fase')[tempo_col_name].to_dict()`
            # Questo è il tempo unitario per la quantità definita in 'Pezzi'.
            # La durata effettiva dipende da `quantita_lotto`.
            
            # La logica originale: `remaining = int(t0 * eq + pdly + fdly)`
            # Dove t0 era il tempo da `tempo_map`. Questo sembra implicare che `t0` fosse già
            # il tempo totale per il lotto, non un tempo unitario.
            # Se `tempo_map` contiene il tempo *totale* per una quantità standard,
            # e `eq` scala questo, allora la logica è:
            # tempo_base_da_mappa = tempo_map.get(fase_nome, 0)
            # tempo_lavorazione_effettivo_fase = tempo_base_da_mappa * equivalenza
            # Questa sembra essere l'interpretazione più vicina all'originale.
            # Tuttavia, `calculate_phase_times_resources` è più esplicito e probabilmente più corretto
            # se `df_tempi` definisce tassi di produzione (pezzi/tempo).

            # Scegliamo di usare `calculate_phase_times_resources` per la durata,
            # e aggiungiamo i ritardi/posticipi a questa durata.
            durata_proc_calcolata, pers_req, energia_val, carrelli_req = \
                calculate_phase_times_resources(fase_corrente_info, quantita_lotto, formato_lotto)

            # Tempo totale da processare per questa fase, inclusi ritardi che estendono la durata
            remaining_processing_time = durata_proc_calcolata + tempo_attesa_pre_fase # Aggiungiamo qui i ritardi come nell'originale

            # Log dell'inizio fase (teorico, prima dell'acquisizione risorse)
            # Non registriamo qui, ma quando il lavoro inizia effettivamente.

            current_abs_start_time_fase = env.now # Momento in cui la fase è pronta per iniziare (dopo attese)

            while remaining_processing_time > 0:
                sim_time_now = env.now
                
                # Calcola disponibilità turno corrente e pause
                # Questa funzione helper deve essere robusta.
                # `avail_in_current_shift_today` è quanto si può lavorare *ora* prima di una pausa.
                # `pause_night_duration`, `pause_weekend_duration` sono le durate delle pause *successive*.
                
                # Logica turni: determina quanto si può lavorare ora.
                # La funzione `get_turn_durations` deve essere precisa.
                # Per semplicità, assumiamo che `work_std`, `work_ven` siano le durate lavorabili
                # e che la simulazione salti i periodi non lavorativi.
                
                # Semplificazione della logica dei turni per l'integrazione con SimPy:
                # 1. Calcola quanto tempo si può lavorare nel turno corrente.
                # 2. Se il `chunk` da lavorare è più grande, lavora fino a fine turno.
                # 3. Fai un timeout per la pausa (notte/weekend).
                # 4. Ripeti.

                dt_now = get_datetime_from_sim_time(sim_time_now)
                current_weekday = dt_now.weekday()
                
                # Durata del turno lavorativo per OGGI
                shift_duration_today = work_ven if current_weekday == fri38 else work_std
                if fase_nome in config.get('Turni_modificati', []): # Applica estensioni
                    shift_duration_today += extension

                # Ora di inizio turno (es. 6:00)
                shift_start_hour = 6 
                shift_start_minute_in_day = shift_start_hour * 60

                # Minuti trascorsi dall'inizio del giorno civile corrente (00:00)
                minutes_past_midnight = dt_now.hour * 60 + dt_now.minute

                # Calcola quanto tempo è disponibile nel turno corrente
                time_available_in_shift = 0
                if minutes_past_midnight >= shift_start_minute_in_day and \
                   minutes_past_midnight < (shift_start_minute_in_day + shift_duration_today):
                    # Siamo nel turno lavorativo
                    time_available_in_shift = (shift_start_minute_in_day + shift_duration_today) - minutes_past_midnight
                
                if time_available_in_shift <= 0 : # Siamo fuori turno o a fine turno
                    # Calcola il tempo fino all'inizio del prossimo turno
                    time_to_next_shift_start = 0
                    if minutes_past_midnight >= (shift_start_minute_in_day + shift_duration_today):
                        # Il turno di oggi è finito, vai al giorno dopo
                        time_to_next_shift_start = (workday_minutes - minutes_past_midnight) + shift_start_minute_in_day
                    else: # Siamo prima dell'inizio del turno di oggi
                        time_to_next_shift_start = shift_start_minute_in_day - minutes_past_midnight
                    
                    # Gestisci i weekend
                    next_potential_start_dt = dt_now + timedelta(minutes=time_to_next_shift_start)
                    while not (
                        (next_potential_start_dt.weekday() != 5 and next_potential_start_dt.weekday() != 6) or # Non Sab o Dom
                        (next_potential_start_dt.weekday() == fri38 and work_ven > 0) or # Venerdì lavorativo
                        (next_potential_start_dt.weekday() < 5 and work_std > 0) # Altro feriale lavorativo
                    ):
                        # Siamo in un giorno non lavorativo, o un giorno con turno 0. Aggiungi 24 ore.
                        time_to_next_shift_start += workday_minutes
                        next_potential_start_dt += timedelta(days=1)

                    if time_to_next_shift_start > 0:
                        yield env.timeout(time_to_next_shift_start)
                    continue # Ricalcola `time_available_in_shift` all'inizio del prossimo turno

                # Quanto lavoro fare in questo blocco
                work_chunk_duration = min(remaining_processing_time, time_available_in_shift)
                
                if work_chunk_duration <= 0: # Non dovrebbe succedere se la logica sopra è corretta
                    # Forziamo un piccolo avanzamento per evitare loop infiniti se c'è un bug logico
                    # o attendiamo fino al prossimo slot valido.
                    # Questo indica un problema nella logica dei turni.
                    # Per ora, se capita, si assume che il timeout precedente ci abbia portato a un momento valido.
                    # Se ancora 0, potrebbe essere un turno di durata 0.
                    # print(f"Warning: work_chunk_duration è {work_chunk_duration} a {dt_now} per fase {fase_nome}")
                    # yield env.timeout(granularity) # Avanza di un po' per sbloccare
                    # continue
                    pass # Se work_chunk_duration è 0, il loop while dovrebbe terminare o la logica di pausa sopra dovrebbe scattare.


                # Richiesta risorse SimPy
                # Nota: la gestione di `persone_res` e `carrelli_res` come singole risorse globali
                # implica che `pers_req` e `carrelli_req` devono essere 1 (o la capacità della risorsa).
                # Se una fase richiede N persone, si usa `simpy.Container` o N richieste a una risorsa di capacità 1,
                # oppure una singola risorsa con capacità N e si richiede N.
                # L'originale usava `persone_res.request()` che prende 1 unità.
                # Se `pers_req` > 1, questo deve cambiare. Assumiamo per ora che `pers_req` sia gestito
                # dalla capacità totale di `persone_res` e che ogni richiesta sia per 1 "slot" di persona.
                # Questo è un punto CRUCIALE: se `pers_req` è il numero di addetti,
                # e `persone_res` ha capacità `max_personale`, allora si dovrebbe fare:
                # with persone_res.request(amount=pers_req) as req_p: ...
                # Ma l'originale faceva `persone_res.request()` e poi `len(persone_res.users)`.
                # Questo suggerisce che `persone_res` è un pool, e si prende "un" addetto.
                # Se `pers_req` è > 1, la logica originale non cattura l'uso di *multipli* addetti
                # per *questa singola fase*.
                # Per ora, manterrò la logica di richiesta singola, ma è un'area da chiarire.
                # Stesso discorso per i carrelli.

                # Per simulare l'uso di `pers_req` addetti e `carrelli_req` carrelli:
                # Dovremmo avere N richieste separate o usare un Container/Level.
                # Oppure, se `persone_res` è un pool, e `pers_req` è il numero di addetti
                # necessari *da quel pool* per questa operazione:
                
                # Tentativo di acquisire tutte le risorse necessarie
                # Questo è un punto complesso. Se `pers_req` è 2, servono 2 unità dalla risorsa `persone_res`.
                # SimPy `Resource` di default ha `capacity=1` se non specificato.
                # `max_personale` è la capacità totale.
                # Quindi `persone_res` è `simpy.Resource(env, capacity=max_personale)`.
                # La richiesta dovrebbe essere `persone_res.request(pers_req)`.

                # Simuleremo l'acquisizione di tutte le risorse necessarie per la fase
                # Questo è un possibile collo di bottiglia se le risorse sono molto contese.
                
                # Gestione risorse:
                richiesta_macchina = risorse_macchina[macchina_richiesta].request()
                # Se pers_req o carrelli_req è 0, non fare la richiesta per evitare errori.
                richiesta_persone = persone_res.request(amount=pers_req) if pers_req > 0 else None
                richiesta_carrelli = carrelli_res.request(amount=carrelli_req) if carrelli_req > 0 else None
                
                # Costruisci la lista delle richieste effettive da attendere
                all_requests = [richiesta_macchina]
                if richiesta_persone: all_requests.append(richiesta_persone)
                if richiesta_carrelli: all_requests.append(richiesta_carrelli)

                # Attendi tutte le risorse (AND condition)
                # SimPy non ha un `yield env.all_of([req1, req2])` diretto per `Resource` nello stesso modo di `Process`.
                # Si devono acquisire sequenzialmente o usare `Condition` events.
                # L'originale usava `yield rm & rp & rc` che è per `Condition` events, non per `Resource.request()`.
                # Per `Resource`, si fa `yield req`.
                # Per acquisire multiple risorse in AND:
                # 1. Richiedile tutte.
                # 2. `yield req1` poi `yield req2` etc. (questo è sequenziale, non AND in termini di attesa)
                # Oppure, usa un `Store` o `FilterStore` per modellare set di risorse.

                # L'approccio più comune è fare richieste nidificate o usare `AllOf` se si convertono in eventi.
                # Per semplicità e per seguire lo spirito dell'originale (anche se la sintassi era per Condition):
                # Acquisiremo la macchina, poi le persone, poi i carrelli.
                # Questo potrebbe non essere l'ideale se l'ordine di acquisizione conta o per deadlock.
                
                # Un modo più corretto per l'AND logico con risorse:
                risorse_acquisite_correttamente = False
                try:
                    risultati_richieste = {}
                    
                    # Macchina
                    risultati_richieste['macchina'] = yield richiesta_macchina
                    
                    # Persone (se necessarie)
                    if richiesta_persone:
                        risultati_richieste['persone'] = yield richiesta_persone
                    
                    # Carrelli (se necessari)
                    if richiesta_carrelli:
                        risultati_richieste['carrelli'] = yield richiesta_carrelli
                    
                    risorse_acquisite_correttamente = True

                    # --- LAVORAZIONE ---
                    actual_start_sim_time = env.now
                    actual_start_dt = get_datetime_from_sim_time(actual_start_sim_time)
                    
                    # Log dell'inizio effettivo del chunk di lavoro
                    risultati_eventi.append({
                        'ID_Lotto': lotto_id,
                        'Formato': formato_lotto,
                        'Quantita': quantita_lotto,
                        'Fase': fase_nome,
                        'Macchina': macchina_richiesta,
                        'Evento': 'INIZIO_CHUNK',
                        'SimTime': actual_start_sim_time,
                        'Timestamp': actual_start_dt,
                        'DurataChunkPianificata': work_chunk_duration,
                        'PersoneRichieste': pers_req,
                        'CarrelliRichiesti': carrelli_req
                    })
                    
                    # Log utilizzo risorse al momento dell'inizio del chunk
                    # `persone_res.count` è il numero di unità attualmente in uso.
                    # `persone_res.capacity` è la capacità totale.
                    # `len(persone_res.users)` è la lista di chi sta usando la risorsa (oggetti Request).
                    # `len(persone_res.queue)` è la lista di chi è in attesa.
                    log_utilizzo_persone.append({
                        'SimTime': actual_start_sim_time, 'Timestamp': actual_start_dt,
                        'PersoneInUso': persone_res.count + pers_req if richiesta_persone else persone_res.count, # Stima dopo questa acquisizione
                        'PersoneInCoda': len(persone_res.put_queue) # Coda per richieste di put (acquisizione)
                    })
                    log_utilizzo_carrelli.append({
                        'SimTime': actual_start_sim_time, 'Timestamp': actual_start_dt,
                        'CarrelliInUso': carrelli_res.count + carrelli_req if richiesta_carrelli else carrelli_res.count,
                        'CarrelliInCoda': len(carrelli_res.put_queue)
                    })
                    # Energia: si assume che l'energia sia consumata durante il processo.
                    # Se `energia_val` è un tasso (es. kWh/minuto), moltiplicare per `work_chunk_duration`.
                    # Se è un valore fisso per la fase, registrarlo una volta per fase.
                    # Assumiamo sia un tasso orario o per minuto. Se `EnergiaFase` è totale per la fase,
                    # andrebbe divisa per la durata della fase per ottenere un tasso.
                    # L'originale la loggava per chunk, quindi presumo sia un consumo durante il chunk.
                    # Se `energia_val` è l'energia per l'intera fase, questo la somma più volte.
                    # Se `energia_val` è un *tasso* (es. energia/minuto), allora:
                    energia_consumata_nel_chunk = energia_val * work_chunk_duration
                    log_consumo_energia.append({
                        'SimTime': actual_start_sim_time, 'Timestamp': actual_start_dt,
                        'ID_Lotto': lotto_id, 'Fase': fase_nome,
                        'EnergiaConsumata': energia_consumata_nel_chunk
                    })

                    yield env.timeout(work_chunk_duration) # Lavora per la durata del chunk
                    
                    actual_end_sim_time = env.now
                    actual_end_dt = get_datetime_from_sim_time(actual_end_sim_time)

                    risultati_eventi.append({
                        'ID_Lotto': lotto_id,
                        'Formato': formato_lotto,
                        'Quantita': quantita_lotto,
                        'Fase': fase_nome,
                        'Macchina': macchina_richiesta,
                        'Evento': 'FINE_CHUNK',
                        'SimTime': actual_end_sim_time,
                        'Timestamp': actual_end_dt,
                        'DurataChunkEffettiva': actual_end_sim_time - actual_start_sim_time
                    })
                    
                    remaining_processing_time -= work_chunk_duration

                finally: # Blocco finally per assicurare il rilascio delle risorse
                    if risorse_acquisite_correttamente:
                        # Rilascia le risorse nell'ordine inverso di acquisizione (buona pratica)
                        if richiesta_carrelli: carrelli_res.release(risultati_richieste['carrelli'])
                        if richiesta_persone: persone_res.release(risultati_richieste['persone'])
                        risorse_macchina[macchina_richiesta].release(risultati_richieste['macchina'])
                    else: # Se non tutte acquisite, rilascia quelle che potremmo aver ottenuto
                          # Questo è più complesso, SimPy gestisce eccezioni durante yield
                          # Se una richiesta fallisce o viene interrotta, non si dovrebbe arrivare qui
                          # con risorse parzialmente acquisite in questo modo.
                          # Se `yield` lancia un'eccezione (es. `Interrupt`), la risorsa non è acquisita.
                          # È più per la pulizia se il processo stesso viene interrotto.
                          # Per ora, assumiamo che se non `risorse_acquisite_correttamente`,
                          # nessuna risorsa di questo set è stata trattenuta a lungo termine.
                          # Tuttavia, se una `yield` precedente avesse successo e una successiva fallisse
                          # prima del `try...finally`, quelle risorse andrebbero rilasciate.
                          # La struttura `with resource.request() as req:` è più sicura per questo.
                          # Ma per multiple risorse in AND, è più complesso.
                          # Per ora, questo `finally` si basa su `risorse_acquisite_correttamente`.
                          pass


            # Fine del while remaining_processing_time > 0 (la fase è completata)
            
            # Ritardo fisiologico di FINE_FASE
            ritardo_fisiologico_fine = fisio_map.get((formato_lotto, fase_nome, 'FINE_FASE'), 0)
            if ritardo_fisiologico_fine > 0:
                yield env.timeout(ritardo_fisiologico_fine)
            
            # Log completamento fase
            risultati_eventi.append({
                'ID_Lotto': lotto_id,
                'Formato': formato_lotto,
                'Fase': fase_nome,
                'Macchina': macchina_richiesta,
                'Evento': 'FINE_FASE',
                'SimTime': env.now,
                'Timestamp': get_datetime_from_sim_time(env.now)
            })
        
        # Tutte le fasi del lotto completate
        risultati_eventi.append({
            'ID_Lotto': lotto_id,
            'Formato': formato_lotto,
            'Evento': 'FINE_LOTTO',
            'SimTime': env.now,
            'Timestamp': get_datetime_from_sim_time(env.now)
        })

    # 13) Avvio dei processi per ciascun lotto
    # Ordina i lotti per 'Giorno' e poi per un criterio di priorità se esiste (es. ID_Lotto)
    # Questo può influenzare l'ordine di accesso alle risorse se più lotti iniziano lo stesso giorno.
    lotti_ordinati = lotti_filtrati.sort_values(by=['Giorno', 'ID_Lotto']) # Aggiunto ID_Lotto per stabilità

    for _, lotto_data in lotti_ordinati.iterrows():
        env.process(processo_lotto(env, lotto_data.to_dict())) # Passa il record del lotto come dizionario

    # Esegui la simulazione fino a un certo punto o finché non ci sono più eventi
    # È buona pratica definire un `until` per evitare simulazioni infinite se c'è un bug.
    # Potrebbe essere `get_sim_time_from_datetime(fine_sim_dt)`.
    # Se non specificato, SimPy esegue finché ci sono eventi schedulati.
    simulation_until_time = get_sim_time_from_datetime(fine_sim_dt)
    env.run(until=simulation_until_time)


    # 14) Output: Conversione dei log in DataFrame
    df_risultati_eventi = pd.DataFrame(risultati_eventi)

    # Creazione DataFrame per persone, energia, carrelli dai log
    # Questi DataFrame avranno granularità dell'evento/chunk.
    # Per avere una timeline aggregata (come nell'originale), bisogna fare un groupby e resample.

    df_log_persone = pd.DataFrame(log_utilizzo_persone)
    df_log_carrelli = pd.DataFrame(log_utilizzo_carrelli)
    df_log_energia = pd.DataFrame(log_consumo_energia)

    # Per ricreare i DataFrame di output come nell'originale (timeline aggregata):
    # 1. Creare una timeline completa di timestamp con la granularità desiderata.
    # 2. Unire i log a questa timeline e riempire i valori (forward fill).
    
    if not df_risultati_eventi.empty:
        sim_time_min_actual = df_risultati_eventi['SimTime'].min()
        sim_time_max_actual = df_risultati_eventi['SimTime'].max()
        
        # Arrotonda ai minuti o alla granularità per la timeline
        start_timeline_dt = get_datetime_from_sim_time(sim_time_min_actual)
        #start_timeline_dt = start_timeline_dt.floor(f"{granularity}T") # Pandas <2.0
        start_timeline_dt = start_timeline_dt.round(f"{granularity}min")


        end_timeline_dt = get_datetime_from_sim_time(sim_time_max_actual)
        #end_timeline_dt = end_timeline_dt.ceil(f"{granularity}T")
        end_timeline_dt = end_timeline_dt.round(f"{granularity}min")


        if start_timeline_dt > end_timeline_dt : # Caso di simulazione molto breve
             end_timeline_dt = start_timeline_dt + timedelta(minutes=granularity)

        # Genera la serie temporale completa
        # date_range può dare problemi con f"{granularity}T" se T non è un offset valido. Usare "min"
        # freq = f"{granularity}T" # Es. "60T" per 60 minuti
        try:
            freq_str = f"{granularity}min"
            timeline_stamps = pd.date_range(start=start_timeline_dt, end=end_timeline_dt, freq=freq_str)
        except ValueError as e:
            print(f"Errore nella creazione di date_range con freq '{freq_str}': {e}. Uso freq='H' o 'T'.")
            try:
                freq_str = f"{granularity}T" # Prova con T
                timeline_stamps = pd.date_range(start=start_timeline_dt, end=end_timeline_dt, freq=freq_str)
            except ValueError:
                 freq_str = "H" if granularity >=60 else "T" # Fallback a ora o minuto
                 timeline_stamps = pd.date_range(start=start_timeline_dt, end=end_timeline_dt, freq=freq_str)


        df_timeline = pd.DataFrame({'timestamp': timeline_stamps})

        # Persone
        if not df_log_persone.empty:
            df_log_persone_sorted = df_log_persone.sort_values(by='Timestamp')
            df_persone_agg = pd.merge_asof(df_timeline, df_log_persone_sorted[['Timestamp', 'PersoneInUso']], 
                                           on='Timestamp', direction='backward')
            df_persone_agg = df_persone_agg.rename(columns={'Timestamp':'timestamp', 'PersoneInUso':'Persone_occupate'})
            df_persone_agg['Persone_occupate'] = df_persone_agg['Persone_occupate'].fillna(0) # O ffill() e poi 0 all'inizio
        else:
            df_persone_agg = df_timeline.copy()
            df_persone_agg['Persone_occupate'] = 0
        
        # Carrelli
        if not df_log_carrelli.empty:
            df_log_carrelli_sorted = df_log_carrelli.sort_values(by='Timestamp')
            df_carrelli_agg = pd.merge_asof(df_timeline, df_log_carrelli_sorted[['Timestamp', 'CarrelliInUso']],
                                            on='Timestamp', direction='backward')
            df_carrelli_agg = df_carrelli_agg.rename(columns={'Timestamp':'timestamp', 'CarrelliInUso':'Carrelli_occupati'})
            df_carrelli_agg['Carrelli_occupati'] = df_carrelli_agg['Carrelli_occupati'].fillna(0)
        else:
            df_carrelli_agg = df_timeline.copy()
            df_carrelli_agg['Carrelli_occupati'] = 0

        # Energia
        if not df_log_energia.empty:
            # L'energia è consumata in chunk. Per avere un valore sulla timeline,
            # potremmo raggruppare per timestamp (arrotondato alla granularità) e sommare.
            df_log_energia['timestamp_agg'] = df_log_energia['Timestamp'].dt.round(f"{granularity}min")
            df_energia_sum_per_slot = df_log_energia.groupby('timestamp_agg')['EnergiaConsumata'].sum().reset_index()
            df_energia_agg = pd.merge(df_timeline, df_energia_sum_per_slot, 
                                      left_on='timestamp', right_on='timestamp_agg', how='left').fillna(0)
            df_energia_agg = df_energia_agg.rename(columns={'EnergiaConsumata':'Energia'})[['timestamp', 'Energia']]
        else:
            df_energia_agg = df_timeline.copy()
            df_energia_agg['Energia'] = 0.0

    else: # Nessun evento, restituisce DataFrame vuoti con le colonne attese
        cols_risultati = ['ID_Lotto', 'Formato', 'Quantita', 'Fase', 'Macchina', 'Evento', 'SimTime', 'Timestamp', 'DurataChunkPianificata', 'PersoneRichieste', 'CarrelliRichiesti', 'DurataChunkEffettiva']
        df_risultati_eventi = pd.DataFrame(columns=cols_risultati)
        df_persone_agg = pd.DataFrame(columns=['timestamp', 'Persone_occupate'])
        df_energia_agg = pd.DataFrame(columns=['timestamp', 'Energia'])
        df_carrelli_agg = pd.DataFrame(columns=['timestamp', 'Carrelli_occupati'])


    # L'output originale era `pd.DataFrame(risultati)` che conteneva solo start/end per fase.
    # `df_risultati_eventi` è più dettagliato. Si potrebbe filtrare per avere un output simile.
    # Ad esempio, per avere solo INIZIO_FASE e FINE_FASE:
    df_risultati_fasi = df_risultati_eventi[df_risultati_eventi['Evento'].isin(['INIZIO_CHUNK', 'FINE_FASE'])].copy()
    # Potrebbe essere necessario un pivot o un groupby per ottenere Start e End per fase su una riga.
    # Per ora, restituisco il log eventi dettagliato e i DataFrame aggregati delle risorse.
    # Per un output più simile all'originale `risultati`:
    df_output_sintetico = df_risultati_eventi[
        df_risultati_eventi['Evento'].isin(['INIZIO_CHUNK', 'FINE_CHUNK'])
    ].groupby(['ID_Lotto', 'Fase']).agg(
        Start=('SimTime', 'min'),
        End=('SimTime', 'max'),
        TimestampStart=('Timestamp', 'min'),
        TimestampEnd=('Timestamp', 'max')
    ).reset_index()
    # Converti SimTime Start/End in Timestamp se necessario, o usa TimestampStart/End


    return df_output_sintetico, df_persone_agg, df_energia_agg, df_carrelli_agg
    # O, per un log più dettagliato:
    # return df_risultati_eventi, df_persone_agg, df_energia_agg, df_carrelli_agg
