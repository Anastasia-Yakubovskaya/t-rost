from src.margin_derivation import margin_realization, post_promo_revenue, leakage_cost
from src.reward_engine import solo_reward


def calculate(cfg):
    # Экономика Т-Соло: доход только от incremental клиентов
    p = cfg.product['portfolio']
    s = cfg.product['solo']
    c = cfg.product['common_costs']
    real = margin_realization(cfg)

    contacts = int(round(p['contacts'] * p['solo_share']))
    takers = contacts * s['take_rate']
    converters = contacts * s['offer_conversion']
    incremental_clients = contacts * max(0.0, s['offer_conversion'] - s['organic_rate'])
    inframarginal = converters - incremental_clients
    causal_share = incremental_clients / converters if converters else 0.0

    bank_revenue = incremental_clients * s['delta_margin_per_incremental_client'] * real

    rewarded = converters if s.get('price_inframarginal_subsidy', False) else incremental_clients
    reward = solo_reward(
        s['reward_levels'],
        proxy_margin=s['delta_margin_per_incremental_client'] * real,
        incrementality=causal_share,
        subsidized_months=s['subsidized_months'],
        case_costs=cfg.case['telecom_costs'],
        safety=p['safety_threshold'],
    )
    free_months = 1 + s['subsidized_months'] if reward['enabled'] else 1
    post_promo = post_promo_revenue(cfg, rewarded, free_months)
    revenue = bank_revenue + post_promo

    telecom = takers * s['trial_month_cost'] + rewarded * reward['month_cost'] * s['subsidized_months']
    crm = contacts * c['crm_per_contact']
    onboarding = takers * (c['onboarding_per_activation'] + c['esim_activation'])
    cannibalization = leakage_cost(cfg, rewarded)
    cost = telecom + crm + onboarding + cannibalization

    return {
        'contacts': contacts, 'takers': takers, 'incremental_clients': incremental_clients,
        'inframarginal_clients': inframarginal, 'windfall_share': inframarginal / converters if converters else 0.0,
        'causal_share': causal_share, 'rewarded': rewarded, 'reward': reward,
        'bank_revenue': bank_revenue, 'post_promo': post_promo, 'revenue': revenue,
        'telecom': telecom, 'crm': crm, 'onboarding': onboarding, 'cannibalization': cannibalization,
        'cost': cost, 'net': revenue - cost, 'sf': revenue / cost if cost else 0,
        'uplift_pp': (s['offer_conversion'] - s['organic_rate']) * 100,
    }
