"""
lib/simulator.py
Modulo di simulazione avanzato per schedulazione produzione.
Accetta configurazione completa da Streamlit.
Gestisce posticipi globali (solo 'Fase') o per lotto ('Lotto').
"""
import random
import simpy
import pandas as pd
from datetime import timedelta

def esegui_simulazione(
    df_lotti, df_tempi, df_posticipi, df_equivalenze, df_posticipi_fisiologici,
    config
):
    # 0) Rinomina colonne lotti se necessario
    df_lotti = df_lotti.rename(columns={
        'Lotto': 'ID_Lotto',
        'Quantità': 'Quantita'
    })
    
    # 1) Validazione df_tempi
    req = {'Fase','Macchina'}
    tempo_col = 'Tempo_Minuti' if 'Tempo_Minuti' in df_tempi.columns else 'Tempo'
    req.add(tempo_col)
    for col in ('Pezzi','Addetti','EnergiaFase'):
        if col not in df_tempi.columns:
            raise KeyError(f"df_tempi manca la colonna '{col}'")
    missing = req - set(df_tempi.columns)
    if missing:
        raise KeyError(f"df_tempi manca le colonne: {missing}")

    # 2) Validazione df_lotti
    for col in ('ID_Lotto','Formato','Quantita','Giorno'):
        if col not in df_lotti.columns:
            raise KeyError(f"df_lotti manca la colonna '{col}'")

    # 3) Validazione df_equivalenze
    for col in ('Formato','Fase','Equivalenza_Unita'):
        if col not in df_equivalenze.columns:
            raise KeyError(f"df_equivalenze manca la colonna '{col}'")

    # 4) Validazione opzionale df_posticipi_fisiologici
    if config.get('includi_fisiologici'):
        for col in ('FORMATO','FASE','QUANDO','TEMPO'):
            if col not in df_posticipi_fisiologici.columns:
                raise KeyError(f"df_posticipi_fisiologici manca la colonna '{col}'")

    # 5) Estrazione config
    mc = config.get('max_carrelli'); mp = config.get('max_personale')
    machine_caps = config.get('machine_caps', {})
    work_std = config.get('work_std'); work_ven = config.get('work_ven')
    workday = config.get('workday_minutes'); extension = config.get('extension')
    fri38 = config.get('fri38'); include_post = config.get('includi_posticipi')
    include_fisio = config.get('includi_fisiologici'); variability = config.get('variability_factor')
    margin = config.get('margin_pct'); gran = config.get('granularity')
    filt_fmt = config.get('filter_format'); filt_line = config.get('filter_line')
    start_override = config.get('data_inizio')

    # 6) Filtri lotti
    lotti = df_lotti.copy()
    if filt_fmt: lotti = lotti[lotti['Formato'].isin(filt_fmt)]
    if 'Linea' in lotti.columns and filt_line:
        lotti = lotti[lotti['Linea'].isin(filt_line)]

    # 7) Range temporale
    if start_override:
        primo = pd.to_datetime(start_override)
    else:
        lotti['Giorno'] = pd.to_datetime(lotti['Giorno'])
        primo = lotti['Giorno'].min().replace(hour=6,minute=0)
    fine = lotti['Giorno'].max() + timedelta(days=1)

    # 8) Timeline risorse
    total_min = int((fine-primo).total_seconds()//60)
    timestamps = [primo+timedelta(minutes=i*gran) for i in range(total_min//gran)]
    df_persone = pd.DataFrame({'timestamp':timestamps,'Persone_occupate':0})
    df_energia = pd.DataFrame({'timestamp':timestamps,'Energia':0.0})
    df_carrelli= pd.DataFrame({'timestamp':timestamps,'Carrelli_occupati':0})
    risultati=[]

    # 9) Setup SimPy
    env=simpy.Environment()
    persone_res=simpy.Resource(env,capacity=mp or 1)
    carrelli_res=simpy.Resource(env,capacity=mc or 1)
    risorse={mac:simpy.Resource(env,capacity=machine_caps.get(mac,1)) 
             for mac in df_tempi['Macchina'].unique()}

    # 10) Mappe
    tempo_map = df_tempi.set_index('Fase')[tempo_col].to_dict()
    eq_map = {(r['Formato'],r['Fase']):r['Equivalenza_Unita'] 
              for _,r in df_equivalenze.iterrows()}
    # Posticipi autorizzati: per lotto se presente, altrimenti globali (None)
    post_map={}
    if include_post:
        for _,r in df_posticipi.iterrows():
            key=(r.get('Lotto'),r['Fase'])
            post_map[key]=post_map.get(key,0)+r.iloc[-1]
            post_map[(None,r['Fase'])]=post_map.get((None,r['Fase']),0)+r.iloc[-1]
    # Ritardi fisiologici
    fisio_map={}
    if include_fisio:
        for _,r in df_posticipi_fisiologici.iterrows():
            key=(r['FORMATO'],r['FASE'],r['QUANDO'])
            fisio_map[key]=fisio_map.get(key,0)+r['TEMPO']

    # 11) Helpers
    def turn(fase,now):
        dt=primo+timedelta(minutes=now)
        base=work_ven if dt.weekday()==fri38 else work_std
        if fase in config.get('Turni_modificati',[]): base+=extension
        night=workday-base; weekend=night+workday*2
        return base,night,weekend

    def time_res(fase,row,qty,fmt):
        dur=qty/float(row['Pezzi'])*float(row['Tempo']) if fase!='AUTOCLAVI' else float(row['Tempo'])
        dur*= (1+margin)*(1+random.uniform(-variability,variability))
        pers=int(row.get('Addetti',1)); en=float(row.get('EnergiaFase',0));
        carr=int(row.get('Carrelli',0))
        if fase=='RAFFREDDAMENTO': dur=0; pers=en=carr=0
        return int(dur),pers,en,carr

    # 12) Processo
    def proc(rec):
        yield env.timeout(int(rec.get('DifferenzaTempo',0))*workday)
        for _,fr in df_tempi.iterrows():
            fase=fr['Fase']; t0=tempo_map.get(fase,0)
            eq=eq_map.get((rec['Formato'],fase),1.0)
            # somma posticipi lotto e globali
            pdly=post_map.get((rec['ID_Lotto'],fase),0)
            pdly+=post_map.get((None,fase),0)
            fdly=fisio_map.get((rec['Formato'],fase,'INIZIO_FASE'),0)
            remaining=int(t0*eq+pdly+fdly)
            while remaining>0:
                now=env.now; w,n,wk=turn(fase,now)
                avail=max(w-(now%workday),0)
                chunk=min(remaining,avail)
                with risorse[fr['Macchina']].request() as rm, persone_res.request() as rp, carrelli_res.request() as rc:
                    yield rm&rp&rc; ist=env.now; yield env.timeout(chunk); iend=env.now
                    risultati.append({'ID_Lotto':rec['ID_Lotto'],'Fase':fase,'Start':ist,'End':iend})
                    ts=primo+timedelta(minutes=int(ist))
                    df_persone.loc[df_persone.timestamp==ts,'Persone_occupate']+=len(persone_res.users)
                    df_carrelli.loc[df_carrelli.timestamp==ts,'Carrelli_occupati']+=len(carrelli_res.users)
                    _,_,e,_=time_res(fase,fr,rec['Quantita'],rec['Formato'])
                    df_energia.loc[df_energia.timestamp==ts,'Energia']+=e
                remaining-=chunk
                if remaining>0: yield env.timeout(wk if (primo+timedelta(minutes=now)).weekday()==fri38 else n)
            flate=fisio_map.get((rec['Formato'],fase,'FINE_FASE'),0)
            if flate: yield env.timeout(flate)

    # 13) Run
    for _,lot in lotti.iterrows(): env.process(proc(lot))
    env.run()

    # 14) Output
    return pd.DataFrame(risultati), df_persone, df_energia, df_carrelli


