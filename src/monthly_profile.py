from src.reward_engine import solo_reward_for_cfg, circle_expected_reward


def portfolio_monthly(cfg):
    """Monthly profile reconciles exactly to the 12m portfolio P&L."""
    # Помесячная развёртка
    p = cfg.product
    s = p['solo']
    x = p['circle']
    cc = p['common_costs']
    pp = p['post_promo']
    can = p['cannibalization']

    contacts = p['portfolio']['contacts']
    sc = contacts * p['portfolio']['solo_share']
    xc = contacts * p['portfolio']['circle_share']

    takers = sc * s['take_rate']
    converters = sc * s['offer_conversion']
    inc = sc * (s['offer_conversion'] - s['organic_rate'])
    creators = xc * x['creation_rate']
    activated = creators * x['avg_invites'] * x['invite_activation_rate']
    inc_inv = activated * x['incremental_share']

    # Годовая банковская маржа
    annual_bank = (
        inc * s['delta_margin_per_incremental_client']
        + inc_inv * x['participant_margin']
        + creators * x['head_personal_uplift_share'] * x['head_personal_margin']
    )

    lag = p['pilot']['qualification_lag_months']
    decay = p['pilot']['retention_decay_monthly']

    # Себестоимость платного пакета после льготы
    t = cfg.case['telecom_costs']
    pkg = pp['paid_package']
    pkg_cost = pkg['gb'] * t['per_gb'] + pkg['minutes'] * t['per_minute'] + pkg['sms'] * t['per_sms']

    sr = solo_reward_for_cfg(cfg)
    cr = circle_expected_reward(cfg)

    # Разовые затраты
    oneoff = (
        contacts * cc['crm_per_contact']
        + takers * (cc['onboarding_per_activation'] + cc['esim_activation'])
        + activated * x['invite_onboarding_cost']
    )
    # Утечка маржи от платящих MVNO, попавших в оффер
    leakage = (
        (converters + creators) * can['leakage_share']
        * cfg.case['margins']['mvno_paid'] * can['lost_margin_months']
    )

    rows = []
    cum = 0.0
    for m in range(1, 13):
        rev = 0.0
        cost = 0.0

        if m > lag:
            rev += annual_bank / 12 * ((1 - decay) ** (m - lag - 1))

        # Телеком
        if m == 1:
            cost += takers * s['trial_month_cost']
        if 2 <= m <= 1 + s['subsidized_months']:
            cost += converters * sr['month_cost']
        if m <= x['subsidized_months']:
            cost += creators * cr['expected_month_cost']
        if m == 1:
            cost += activated * x['invite_trial_cost']

        if m > 1 + s['subsidized_months']:
            k = m - (1 + s['subsidized_months']) - 1
            price = pp['price_intro'] if k < pp['intro_months'] else pp['price_list']
            rev += (
                converters
                * ((1 - decay) ** max(0, (1 + s['subsidized_months']) - lag))
                * pp['optin_rate'] * (price - pkg_cost)
            )
        if m > x['subsidized_months']:
            k = m - x['subsidized_months'] - 1
            price = pp['price_intro'] if k < pp['intro_months'] else pp['price_list']
            rev += (
                creators
                * ((1 - decay) ** max(0, x['subsidized_months'] - lag))
                * pp['optin_rate'] * (price - pkg_cost)
            )

        # Разработка, разовые затраты и утечка падают в первый месяц
        if m == 1:
            cost += oneoff + leakage + p['portfolio']['development_cost']

        net = rev - cost
        cum += net
        rows.append({'month': m, 'revenue': rev, 'cost': cost, 'net': net, 'cum_net': cum})

    return rows