from dataclasses import dataclass
from math import comb

@dataclass(frozen=True)
class RewardLevel:
    name: str
    value_threshold: float
    gb: int
    minutes: int

def max_subsidy(expected_incremental_margin: float, safety_threshold: float = 1.3) -> float:
    return max(0.0, expected_incremental_margin / safety_threshold)

def calibrated_margin(proxy_margin: float, incrementality: float) -> float:
    return proxy_margin * max(0.0, min(1.0, incrementality))

def package_cost_month(level, case_costs):
    return level['gb']*case_costs['per_gb'] + level['minutes']*case_costs['per_minute'] + level.get('sms',50)*case_costs['per_sms']

def solo_reward(levels, proxy_margin, incrementality, subsidized_months, case_costs, safety=1.3):
    # Выбирает уровень вознаграждения для Solo по ожидаемой марже на одного клиента
    budget=max_subsidy(calibrated_margin(proxy_margin,incrementality),safety)
    for level in reversed(levels):
        cost=package_cost_month(level,case_costs)*subsidized_months
        if cost<=budget:
            return {'level':level['name'],'gb':level['gb'],'minutes':level['minutes'],'sms':level.get('sms',50),'month_cost':package_cost_month(level,case_costs),'period_cost':cost,'budget':budget,'enabled':True}
    return {'level':'OFF','gb':0,'minutes':0,'sms':0,'month_cost':0.0,'period_cost':0.0,'budget':budget,'enabled':False}

def solo_reward_for_cfg(cfg, incrementality=None):
    s=cfg.product['solo']
    if incrementality is None:
        incrementality=max(0.0,s['offer_conversion']-s['organic_rate'])/max(s['offer_conversion'],1e-9)
    from src.margin_derivation import margin_realization
    return solo_reward(s['reward_levels'],s['delta_margin_per_incremental_client']*margin_realization(cfg),incrementality,s['subsidized_months'],cfg.case['telecom_costs'],cfg.product['portfolio']['safety_threshold'])

def choose_circle_reward(expected_incremental_margin: float, levels):
    eligible=[x for x in levels if expected_incremental_margin>=float(x['value_threshold'])]
    return eligible[-1] if eligible else levels[0]

def circle_ladder(levels, qualified_invitees, participant_margin, incrementality, case_costs,
                  head_personal_uplift=False, head_personal_margin=0.0, safety=1.3, subsidized_months=6):
    # Уровень круга выбирается по ожидаемой марже на одного квалифицированного участника, интегрированной по распределению числа квалифицированных участников
    proxy=qualified_invitees*participant_margin+(head_personal_margin if head_personal_uplift else 0.0)
    chosen=choose_circle_reward(proxy,levels)
    budget=max_subsidy(calibrated_margin(proxy,incrementality),safety)
    idx=list(levels).index(chosen)
    while idx>0 and package_cost_month(levels[idx],case_costs)*subsidized_months>budget:
        idx-=1
    level=levels[idx]
    return {'qualified':qualified_invitees,'proxy_margin':proxy,'budget':budget,'level':level['name'],'gb':level['gb'],'minutes':level['minutes'],'month_cost':package_cost_month(level,case_costs),'period_cost':package_cost_month(level,case_costs)*subsidized_months,'downgraded':idx!=list(levels).index(chosen)}

def circle_expected_reward(cfg, invite_activation_rate=None, qualified_share=None, incrementality=None,
                           participant_margin=None, avg_invites=None):
    # Ожидаемая стоимость льготного периода на одного создателя Круга, интегрированная по распределению числа квалифицированных участников
    x=cfg.product['circle']; real=None
    from src.margin_derivation import margin_realization
    real=margin_realization(cfg)
    act=x['invite_activation_rate'] if invite_activation_rate is None else invite_activation_rate
    qual=x['qualified_share_of_activated'] if qualified_share is None else qualified_share
    inc=x['incremental_share'] if incrementality is None else incrementality
    pm=x['participant_margin'] if participant_margin is None else participant_margin
    av=x['avg_invites'] if avg_invites is None else avg_invites
    n=int(x['max_members'])-1
    invite_fill=max(0.0,min(1.0,av/max(n,1)))
    pq=max(0.0,min(1.0,invite_fill*act*qual))
    exp_month=0.0; dist=[]
    for k in range(n+1):
        pk=comb(n,k)*(pq**k)*((1-pq)**(n-k))
        # head uplift is itself uncertain; integrate its two states rather than pretending it is always present.
        e=0.0
        for hu,ph in ((False,1-x['head_personal_uplift_share']),(True,x['head_personal_uplift_share'])):
            r=circle_ladder(x['reward_levels'],k,pm*real,inc,cfg.case['telecom_costs'],hu,x['head_personal_margin']*real,cfg.product['portfolio']['safety_threshold'],x['subsidized_months'])
            e += ph*r['month_cost']
        exp_month += pk*e
        dist.append({'qualified':k,'probability':pk,'expected_month_cost':e})
    return {'expected_month_cost':exp_month,'period_cost':exp_month*x['subsidized_months'],'qualified_probability_per_slot':pq,'distribution':dist}

def start_option_exposure(levels, case_costs, months, sms=50):
    return package_cost_month({**levels[0],'sms':sms},case_costs)*months
