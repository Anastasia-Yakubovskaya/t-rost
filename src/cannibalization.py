from src.margin_derivation import margin_realization


def required_incremental_margin(base_cost: float, paid_mvno_margin_month: float = 250, threshold: float = 1.3):
    lost = paid_mvno_margin_month * 12
    return threshold * (base_cost + lost)


def firewall_coverage(cfg):
    # Coverage Т-Соло для платящего MVNO: к стоимости субсидии добавляем потерю 250×12=3000 ₽/год
    from src.solo_economics import calculate as solo_calc
    s = solo_calc(cfg)
    inc = s['incremental_clients']
    cost_per = (s['cost'] - s['cannibalization']) / inc
    lost = cfg.case['margins']['mvno_paid'] * 12
    margin = cfg.product['solo']['delta_margin_per_incremental_client'] * margin_realization(cfg)
    thr = cfg.product['portfolio']['safety_threshold']
    return {
        'cost_per_incremental': cost_per,
        'lost_margin_year': lost,
        'coverage_without_firewall': margin / cost_per,
        'coverage_paid_mvno': margin / (cost_per + lost),
        'margin_required_for_threshold': required_incremental_margin(cost_per, cfg.case['margins']['mvno_paid'], thr),
        'margin_assumed': margin,
    }