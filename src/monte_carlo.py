import numpy as np
from scipy.stats import norm


def _tri_from_u(u, lo, mode, hi):
    # Обратный CDF треугольного распределения
    c = (mode - lo) / (hi - lo)
    return np.where(
        u < c,
        lo + np.sqrt(u * (hi - lo) * (mode - lo)),
        hi - np.sqrt((1 - u) * (hi - lo) * (hi - mode)),
    )


def _retention(decay, lag=2, months=12):
    # Средняя доля сохранённой Δ-маржи за год с учётом лага квалификации
    live = max(0, months - lag)
    ks = np.arange(live)
    return np.sum((1 - decay[:, None]) ** ks, axis=1) / months


def simulate(cfg, strict=None, invite_cap=None):
    # Прогоны с общим шоком
    mc = cfg.product['monte_carlo']
    p = cfg.product['portfolio']
    s = cfg.product['solo']
    x = cfg.product['circle']
    cc = cfg.product['common_costs']
    pp = cfg.product['post_promo']
    can = cfg.product['cannibalization']
    q = cfg.product['pilot']

    if strict is None:
        strict = s.get('price_inframarginal_subsidy', True)

    rng = np.random.default_rng(mc['seed'])
    n = mc['draws']
    rho = mc.get('correlation', 0.0)
    z0 = rng.normal(size=n)

    def corr_u():
        # Однофакторная копула
        z = rho * z0 + np.sqrt(max(0, 1 - rho ** 2)) * rng.normal(size=n)
        return norm.cdf(z)

    solo_contacts = p['contacts'] * p['solo_share']
    circle_contacts = p['contacts'] * p['circle_share']

    # Коррелированные через общий шок: органика, uplift, создание круга, активация, incrementality
    organic = _tri_from_u(corr_u(), 0.02, s['organic_rate'], 0.10)
    uplift = _tri_from_u(corr_u(), 0.06, s['offer_conversion'] - s['organic_rate'], 0.22)
    offer = np.clip(organic + uplift, organic, 0.5)
    solo_margin = _tri_from_u(rng.random(n), 3000, s['delta_margin_per_incremental_client'], 5600)
    circle_create = _tri_from_u(corr_u(), 0.08, x['creation_rate'], 0.23)
    invites = _tri_from_u(rng.random(n), 1.5, x['avg_invites'], float(x['max_members'] - 1))
    if invite_cap is not None:
        invites = np.minimum(invites, invite_cap)
    invite_act = _tri_from_u(corr_u(), 0.40, x['invite_activation_rate'], 0.72)
    incr_share = _tri_from_u(corr_u(), 0.35, x['incremental_share'], 0.88)
    qual_share = _tri_from_u(corr_u(), 0.45, x['qualified_share_of_activated'], 0.90)
    part_margin = _tri_from_u(rng.random(n), 1800, x['participant_margin'], 3600)
    tel_mult = _tri_from_u(rng.random(n), 0.9, 1.0, 1.3)
    decay = _tri_from_u(rng.random(n), 0.0, q['retention_decay_monthly'], 0.06)
    realization = (
        _retention(decay, q['qualification_lag_months'])
        if p.get('apply_decay', True) else np.ones(n)
    )
    optin = _tri_from_u(rng.random(n), 0.10, pp['optin_rate'], 0.45)
    leakage = _tri_from_u(
        rng.random(n), 0.005, can['leakage_share'],
        can.get('stress_leakage_share', 0.08) if isinstance(can, dict) else 0.08,
    )
    leakage = np.minimum(leakage, 0.08)

    # Платный пакет после льготы
    pkg = pp['paid_package']
    t = cfg.case['telecom_costs']
    pkg_cost = pkg['gb'] * t['per_gb'] + pkg['minutes'] * t['per_minute'] + pkg['sms'] * t['per_sms']

    def paid_margin(months):
        return sum(
            (pp['price_intro'] if k < pp['intro_months'] else pp['price_list']) - pkg_cost
            for k in range(max(0, months))
        )

    # Соло
    solo_inc = solo_contacts * (offer - organic)
    solo_bank = solo_inc * solo_margin * realization
    solo_rewarded = solo_contacts * offer if strict else solo_inc
    solo_free = 1 + s['subsidized_months']
    solo_surv = (1 - decay) ** np.maximum(0, solo_free - q['qualification_lag_months'])
    solo_post = solo_rewarded * solo_surv * optin * paid_margin(12 - solo_free)

    # Адаптивная лестница: пакет не дороже причинной маржи, делённой на порог безопасности
    causal = np.divide(uplift, offer, out=np.zeros_like(uplift), where=offer > 0)
    budget = solo_margin * realization * causal / p['safety_threshold']
    level_costs = np.array([
        (lvl['gb'] * t['per_gb'] + lvl['minutes'] * t['per_minute'] + lvl.get('sms', 50) * t['per_sms'])
        for lvl in s['reward_levels']
    ])
    solo_month_cost = np.zeros(n)
    for lc in level_costs:
        solo_month_cost = np.where(lc * s['subsidized_months'] <= budget, lc, solo_month_cost)

    solo_tel = (
        solo_contacts * s['take_rate'] * s['trial_month_cost']
        + solo_rewarded * solo_month_cost * s['subsidized_months']
    ) * tel_mult
    solo_other = (
        solo_contacts * cc['crm_per_contact']
        + solo_contacts * s['take_rate'] * (cc['onboarding_per_activation'] + cc['esim_activation'])
    )
    solo_leak = solo_rewarded * leakage * cfg.case['margins']['mvno_paid'] * can['lost_margin_months']

    # Круг
    creators = circle_contacts * circle_create
    activated = creators * invites * invite_act
    inc_inv = activated * incr_share
    circ_bank = (
        inc_inv * part_margin
        + creators * x['head_personal_uplift_share'] * x['head_personal_margin']
    ) * realization
    circ_surv = (1 - decay) ** np.maximum(0, x['subsidized_months'] - q['qualification_lag_months'])
    circ_post = creators * circ_surv * optin * paid_margin(12 - x['subsidized_months'])

    # Same adaptive ladder as deterministic P&L, integrated over K=0..3 qualified members.
    nslots = int(x['max_members']) - 1
    pqual = np.clip((invites / max(nslots, 1)) * invite_act * qual_share, 0, 1)
    circ_month = np.zeros(n)
    costs = np.array([
        lvl['gb'] * t['per_gb'] + lvl['minutes'] * t['per_minute'] + lvl.get('sms', 50) * t['per_sms']
        for lvl in x['reward_levels']
    ])
    thresholds = np.array([lvl['value_threshold'] for lvl in x['reward_levels']])
    for k in range(nslots + 1):
        # Вероятность ровно k участников
        prob = (
            __import__('math').comb(nslots, k)
            * (pqual ** k)
            * ((1 - pqual) ** (nslots - k))
        )
        proxy = (
            k * part_margin * realization
            + x['head_personal_uplift_share'] * x['head_personal_margin'] * realization
        )
        b = proxy * incr_share / p['safety_threshold']
        chosen = np.zeros(n)
        for th, lc in zip(thresholds, costs):
            chosen = np.where((proxy >= th) & (lc * x['subsidized_months'] <= b), lc, chosen)
        chosen = np.where(chosen == 0, costs[0], chosen)
        circ_month += prob * chosen

    circ_tel = (
        creators * circ_month * x['subsidized_months']
        + activated * x['invite_trial_cost']
    ) * tel_mult
    circ_other = circle_contacts * cc['crm_per_contact'] + activated * x['invite_onboarding_cost']
    circ_leak = creators * leakage * cfg.case['margins']['mvno_paid'] * can['lost_margin_months']

    rev = solo_bank + solo_post + circ_bank + circ_post
    op = solo_tel + solo_other + solo_leak + circ_tel + circ_other + circ_leak
    net = rev - op - p['development_cost']
    op_sf = rev / op
    full_sf = rev / (op + p['development_cost'])

    return {
        'draws': n,
        'p_net_pos': float(np.mean(net > 0)),
        'p_sf13': float(np.mean(op_sf >= p['safety_threshold'])),
        'p_full13': float(np.mean(full_sf >= p['safety_threshold'])),
        'p_sf10': float(np.mean(op_sf >= 1.0)),
        'p5': float(np.percentile(net, 5)),
        'p50': float(np.percentile(net, 50)),
        'p95': float(np.percentile(net, 95)),
        'mean': float(np.mean(net)),
        'uncertain_inputs': [
            'uplift/organic',
            'solo & circle margin',
            'creation/activation/incrementality/qualification',
            'telecom cost',
            'decay',
            'post-promo opt-in',
            'MVNO leakage',
        ],
    }