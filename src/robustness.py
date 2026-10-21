import copy
from src.portfolio_economics import calculate

def with_overrides(cfg, overrides):
    c=copy.deepcopy(cfg)
    for path,val in overrides.items():
        d=c.product
        for k in path[:-1]: d=d[k]
        d[path[-1]]=val
    return c

def scale_telecom(cfg,k):
    # Масштабируем первичные CASE-ставки
    c=copy.deepcopy(cfg); s,x=c.product['solo'],c.product['circle']
    for key in ('per_gb','per_minute','per_sms'):
        c.case['telecom_costs'][key] *= k
    s['trial_month_cost'] *= k
    x['head_month_cost'] *= k
    x['invite_trial_cost'] *= k
    return c

def find_crossing(f,target,lo,hi,steps=240):
    # Находим значение x, при котором f(x) = target
    xs=[lo+(hi-lo)*i/steps for i in range(steps+1)]
    vals=[f(x)-target for x in xs]
    for i in range(steps):
        if vals[i]==0: return xs[i]
        if vals[i]*vals[i+1] < 0:
            a,b=xs[i],xs[i+1]; fa=vals[i]
            for _ in range(70):
                m=(a+b)/2; fm=f(m)-target
                if fm*fa<=0: b=m
                else: a,fa=m,fm
            return (a+b)/2
    return None

PARAMS={
 'circle_incremental_share':(('circle','incremental_share'),(0.0,1.0),'Круг · incrementality','pct'),
 'circle_invite_activation':(('circle','invite_activation_rate'),(0.02,1.0),'Круг · активация','pct'),
 'circle_participant_margin':(('circle','participant_margin'),(200,7000),'Круг · маржа участника','rub'),
 'solo_margin':(('solo','delta_margin_per_incremental_client'),(800,9000),'Соло · Δ-маржа','rub'),
}

def breakeven_table(cfg):
    # Находим для каждого параметра значение, при котором SF портфеля = 1.3 и Net портфеля = 0
    out=[]
    for key,(path,(lo,hi),label,fmt) in PARAMS.items():
        d=cfg.product
        for k in path: d=d[k]
        f13=find_crossing(lambda v: calculate(with_overrides(cfg,{path:v}))['full_cost_sf'],1.3,lo,hi)
        net0=find_crossing(lambda v: calculate(with_overrides(cfg,{path:v}))['group_net'],0,lo,hi)
        c13=None; c10=None
        if key.startswith('circle_'):
            c13=find_crossing(lambda v: calculate(with_overrides(cfg,{path:v}))['circle']['sf'],1.3,lo,hi)
            c10=find_crossing(lambda v: calculate(with_overrides(cfg,{path:v}))['circle']['sf'],1.0,lo,hi)
        out.append({'key':key,'label':label,'fmt':fmt,'base':d,'portfolio_full_ge_1_3':f13,'portfolio_net_zero':net0,'circle_ge_1_0':c10,'circle_ge_1_3':c13})
    s=cfg.product['solo']; org=s['organic_rate']
    out.append({'key':'solo_uplift_pp','label':'Соло · uplift, п.п.','fmt':'pp','base':(s['offer_conversion']-org)*100,
                'portfolio_full_ge_1_3':(lambda x: None if x is None else 100*x)(find_crossing(lambda u: calculate(with_overrides(cfg,{('solo','offer_conversion'):org+u}))['full_cost_sf'],1.3,0,0.4)),
                'portfolio_net_zero':(lambda x: None if x is None else 100*x)(find_crossing(lambda u: calculate(with_overrides(cfg,{('solo','offer_conversion'):org+u}))['group_net'],0,0,0.4)),
                'circle_ge_1_0':None,'circle_ge_1_3':None})
    out.append({'key':'telecom_cost_mult','label':'Себестоимость связи, ×','fmt':'x','base':1.0,
                'portfolio_full_ge_1_3':find_crossing(lambda k: calculate(scale_telecom(cfg,k))['full_cost_sf'],1.3,0.5,2.5),
                'portfolio_net_zero':find_crossing(lambda k: calculate(scale_telecom(cfg,k))['group_net'],0,0.5,3.0),
                'circle_ge_1_0':None,'circle_ge_1_3':None})
    return out

def _summ(r):
    return {'group_net':r['group_net'],'operating_sf':r['operating_sf'],'full_cost_sf':r['full_cost_sf'],'solo_sf':r['solo']['sf'],'circle_sf':r['circle']['sf']}

def stress_scenarios(cfg):
    g=cfg.product['guardrails']; s=cfg.product['solo']; p=cfg.product['pilot']
    scenarios=[
      ('base','База (лаг + затухание учтены)',{}),
      ('no_decay','Без затухания и лага — верхняя граница',{('portfolio','apply_decay'):False}),
      ('fill','Круг: 2 приглашённых',{('circle','avg_invites'):g['stress_invites_per_circle']}),
      ('decay_fast','Затухание Δ 5%/мес',{('pilot','retention_decay_monthly'):g['stress_decay_monthly']}),
      ('uplift_low','Соло: uplift 8 п.п.',{('solo','offer_conversion'):s['organic_rate']+g['stress_solo_uplift_pp']/100}),
      ('leak','Утечка firewall 8%',{('cannibalization','leakage_share'):g['stress_leakage_share']}),
      ('incr50','Круг: incrementality 50%',{('circle','incremental_share'):g['stress_incremental_share']}),
      ('combined','Комбинированный стресс',{('circle','avg_invites'):g['stress_invites_per_circle'],('pilot','retention_decay_monthly'):g['stress_decay_monthly'],('solo','offer_conversion'):s['organic_rate']+g['stress_solo_uplift_pp']/100,('cannibalization','leakage_share'):g['stress_leakage_share'],('circle','incremental_share'):g['stress_incremental_share']}),
    ]
    return [{'id':i,'label':lab,**_summ(calculate(with_overrides(cfg,o)))} for i,lab,o in scenarios]

def tornado(cfg,swing=.20):
    base=calculate(cfg)['group_net']; rows=[]
    for key,(path,_,label,_) in PARAMS.items():
        d=cfg.product
        for k in path:d=d[k]
        lo=calculate(with_overrides(cfg,{path:d*(1-swing)}))['group_net']
        hi=calculate(with_overrides(cfg,{path:d*(1+swing)}))['group_net']
        rows.append({'label':label,'down':lo-base,'up':hi-base,'span':abs(hi-lo)})
    lo=calculate(scale_telecom(cfg,1+swing))['group_net']; hi=calculate(scale_telecom(cfg,1-swing))['group_net']
    rows.append({'label':'Себестоимость связи','down':lo-base,'up':hi-base,'span':abs(hi-lo)})
    return sorted(rows,key=lambda r:-r['span'])
