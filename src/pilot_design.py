from scipy.stats import norm
from math import sqrt


def design(cfg):
    # Два параллельных RCT
    p = cfg.product['pilot']
    n = p['n_per_arm']
    return {
        'arms': p['arms'],
        'n_per_arm': n,
        'total_n': n * len(p['arms']),
        'comparisons': [
            {
                'name': 'Solo ITT',
                'eligible': 'S1/S2 после firewall',
                'control': 'solo_control',
                'treatment': 'solo_treatment',
                'n_control': n,
                'n_treatment': n,
            },
            {
                'name': 'Circle ITT',
                'eligible': 'S3/S4/eligible heads после firewall',
                'control': 'circle_control',
                'treatment': 'circle_treatment',
                'n_control': n,
                'n_treatment': n,
            },
        ],
        'duration_days': p['duration_days'],
        'extended_observation_days': p['extended_observation_days'],
        'primary_metric': p['primary_metric'],
        'stop_loss': p['stop_loss'],
        'estimand': (
            'ITT: разность среднего 12-месячного run-rate group margin '
            'на randomized eligible-клиента внутри каждой страты'
        ),
        'randomization': (
            'Два параллельных RCT, а не один общий control. Eligibility фиксируется до эксперимента. '
            'Solo: control-S vs treatment-S; Circle: control-C vs treatment-C, по 800 в ячейке. '
            'Блокировка по сегменту, региону, baseline-марже и активности.'
        ),
        'circle_design': (
            'В Т-Круге единица рандомизации и анализа — глава круга. Treatment получает механику приглашений; control-C — нет. '
            'Downstream-маржа приглашённых после consent атрибутируется главе по first-touch.'
        ),
        'interference': (
            'Повторные приглашения дедуплицируются; overlap фиксируется после consent. Для известных pre-period связей — cluster-robust SE и sensitivity. '
            'Рандомизация не требует графа будущих приглашений; основной анализ остаётся ITT по randomized head.'
        ),
        'analysis': (
            'Отдельный ITT и 80% CI для Solo и Circle; one-sided alpha=5% только для заранее заданного investment-gate. '
            'Множественные вторичные метрики не используются для SCALE; missing downstream = 0 в ITT, per-protocol — только sensitivity.'
        ),
        'guardrails': ['complaints', 'bank_churn', 'mvno_cannibalization', 'support_load', 'fraud_flags'],
        'post_scale': f"постоянный holdout {p['holdout_share_scale']:.0%} для калибровки incrementality",
    }


def decide(operating_coverage, full_cost_coverage, ci_low, ci_high, itt, guardrails_ok=True, threshold=1.3):
    # Решение по результатам пилота: SCALE, ITERATE или STOP
    if not guardrails_ok:
        return 'STOP'
    if itt > 0 and operating_coverage >= threshold and full_cost_coverage >= threshold and ci_low >= 1.0:
        return 'SCALE'
    if itt < 0 or (full_cost_coverage < 1.0 and ci_high < threshold):
        return 'STOP'
    return 'ITERATE'


def coverage_ci(revenue, cost, se_revenue_per_client, n, ci_level=0.80):
    # Приближённый CI для coverage через delta-метод
    zz = float(norm.ppf(0.5 + ci_level / 2))
    se = se_revenue_per_client / sqrt(n)
    cov = revenue / cost
    return cov, (revenue - zz * se) / cost, (revenue + zz * se) / cost