from src.solo_economics import calculate as solo_calc
from src.circle_economics import calculate as circle_calc


def calculate(cfg):
    # Сводит Т-Соло и Т-Круг в групповой P&L, вычитает разработку, распределяет результат между Банком и MVNO 
    s = solo_calc(cfg)
    c = circle_calc(cfg)
    p = cfg.product['portfolio']

    bank_revenue = s['bank_revenue'] + c['bank_revenue']
    post_promo = s['post_promo'] + c['post_promo']          # маржа MVNO на платных месяцах после льготы
    revenue = bank_revenue + post_promo
    telecom = s['telecom'] + c['telecom']
    other = s['crm'] + s['onboarding'] + c['crm'] + c['onboarding']
    cannibalization = s['cannibalization'] + c['cannibalization']   # потеря маржи MVNO от платящих абонентов
    dev = p['development_cost']

    op_cost = telecom + other + cannibalization
    group_net = revenue - op_cost - dev

    fee = p['mvno_transfer_fee']
    # Правило распределения: банк оплачивает связь по себестоимости +10% и компенсирует каннибализацию
    mvno = telecom * fee + post_promo
    bank = bank_revenue - telecom * (1 + fee) - other - cannibalization - dev
    # Результат «каждый сам за себя» 
    bank_standalone = bank_revenue - other - dev
    mvno_standalone = post_promo - telecom - cannibalization

    return {
        'solo': s,
        'circle': c,
        'bank_revenue': bank_revenue,
        'post_promo': post_promo,
        'revenue': revenue,
        'telecom': telecom,
        'other_cost': other,
        'cannibalization': cannibalization,
        'development': dev,
        'operating_cost': op_cost,
        'group_net': group_net,
        'operating_sf': revenue / op_cost if op_cost else 0,
        'full_cost_sf': revenue / (op_cost + dev) if op_cost + dev else 0,
        'bank': bank,
        'mvno': mvno,
        'bank_standalone': bank_standalone,
        'mvno_standalone': mvno_standalone,
    }