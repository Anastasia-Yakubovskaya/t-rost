def _margin(cfg, c):
    # Годовой run-rate маржи клиента
    m = cfg.case['margins']
    balance = c['incremental_avg_balance'] * (
        c['share_new_money'] * m['debit_balance']
        + (1 - c['share_new_money']) * c['rate_diff_substituted']
    )
    card = c['incremental_card_spend_month'] * 12 * m['debit_interchange']
    cross = c['cross_sell_prob'] * c['cross_sell_margin']
    return {'balance': balance, 'card': card, 'cross_sell': cross, 'total': balance + card + cross}


def solo_margin(cfg):
    return _margin(cfg, cfg.product['solo']['margin_components'])


def circle_participant_margin(cfg):
    return _margin(cfg, cfg.product['circle']['participant_margin_components'])


def avg_retention(monthly_decay, months=12, lag=0):
    # Доля годового run-rate, реально попадающая в окно: лаг квалификации + затухание Δ-поведения
    live = max(0, months - lag)
    return sum((1 - monthly_decay) ** k for k in range(live)) / months


def margin_realization(cfg):
    if not cfg.product['portfolio'].get('apply_decay', True):
        return 1.0
    p = cfg.product['pilot']
    return avg_retention(p['retention_decay_monthly'], 12, p['qualification_lag_months'])


def survival(cfg, month):
    # Доля клиентов, сохранивших Δ-поведение к концу указанного месяца
    p = cfg.product['pilot']
    return (1 - p['retention_decay_monthly']) ** max(0, month - p['qualification_lag_months'])


def package_cost(cfg, pkg):
    t = cfg.case['telecom_costs']
    return pkg['gb'] * t['per_gb'] + pkg['minutes'] * t['per_minute'] + pkg['sms'] * t['per_sms']


def paid_margin_sum(cfg, paid_months):
    # Маржа платного тарифа за paid_months
    pp = cfg.product['post_promo']
    cost = package_cost(cfg, pp['paid_package'])
    total = 0.0
    for k in range(max(0, paid_months)):
        price = pp['price_intro'] if k < pp['intro_months'] else pp['price_list']
        total += price - cost
    return total


def post_promo_revenue(cfg, clients, free_months):
    # Маржа MVNO в оставшихся месяцах 12-мес. горизонта
    pp = cfg.product['post_promo']
    paid_months = 12 - free_months
    return clients * survival(cfg, free_months) * pp['optin_rate'] * paid_margin_sum(cfg, paid_months)


def leakage_cost(cfg, clients):
    # Потерянная маржа платящих абонентов MVNO, прошедших firewall
    c = cfg.product['cannibalization']
    return clients * c['leakage_share'] * cfg.case['margins']['mvno_paid'] * c['lost_margin_months']


def threshold_check(cfg):
    # Клиент «на границе» Qualified Δ должен окупать субсидию с запасом safety_threshold
    s, q = cfg.product['solo'], cfg.product['qualified_delta']
    c = s['margin_components']
    net_rate = c['share_new_money'] * cfg.case['margins']['debit_balance'] + (1 - c['share_new_money']) * c['rate_diff_substituted']
    marginal_margin = q['balance_min_delta'] * net_rate
    from src.reward_engine import solo_reward_for_cfg
    subsidy = solo_reward_for_cfg(cfg)['month_cost'] * s['subsidized_months']
    return {
        'threshold_rub': q['balance_min_delta'],
        'marginal_margin': marginal_margin,
        'subsidy_per_rewarded': subsidy,
        'ratio': marginal_margin / subsidy,
        'required_ratio': cfg.product['portfolio']['safety_threshold'],
    }