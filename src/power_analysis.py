import numpy as np
from math import sqrt
from scipy.stats import norm

from src.margin_derivation import margin_realization, paid_margin_sum, survival
from src.reward_engine import solo_reward, circle_expected_reward


def z(p):
    return float(norm.ppf(p))


def mde_binary(n, p0, alpha=0.05, power=0.80):
    # MDE для долей
    za, zb = z(1 - alpha / 2), z(power)
    lo, hi = 0.0, 1 - p0
    for _ in range(60):
        d = (lo + hi) / 2
        p1 = p0 + d
        se = sqrt(p0 * (1 - p0) / n + p1 * (1 - p1) / n)
        if d / se >= za + zb:
            hi = d
        else:
            lo = d
    return hi


def _lognorm(rng, mean, cv, size):
    s2 = np.log(1 + cv ** 2)
    return rng.lognormal(np.log(max(mean, 1e-9)) - s2 / 2, sqrt(s2), size)


def simulate_arm_outcomes(cfg, arm, cv=None, n_sim=180_000, seed=7):
    # Симмуляция ITT
    p = cfg.product
    pilot = p['pilot']
    cv = pilot['margin_cv'] if cv is None else cv
    rng = np.random.default_rng(seed)
    cc = p['common_costs']
    real = margin_realization(cfg)

    base_sd = pilot['baseline_margin_sd']
    baseline_t = rng.normal(0.0, base_sd, n_sim)
    baseline_c = rng.normal(0.0, base_sd, n_sim)

    if arm == 'solo':
        s = p['solo']
        t = rng.random(n_sim) < s['offer_conversion']
        c = rng.random(n_sim) < s['organic_rate']
        mt = _lognorm(rng, s['delta_margin_per_incremental_client'] * real, cv, n_sim)
        mc = _lognorm(rng, s['delta_margin_per_incremental_client'] * real, cv, n_sim)
        # доля конверсий среди получивших оффер
        causal = max(0.0, s['offer_conversion'] - s['organic_rate']) / max(s['offer_conversion'], 1e-9)
        rw = solo_reward(
            s['reward_levels'], s['delta_margin_per_incremental_client'] * real, causal,
            s['subsidized_months'], cfg.case['telecom_costs'],
            p['portfolio']['safety_threshold'],
        )
        free_months = 1 + s['subsidized_months']
        pp_per_rewarded = (
            survival(cfg, free_months) * p['post_promo']['optin_rate']
            * paid_margin_sum(cfg, 12 - free_months)
        )
        leakage_per_rewarded = (
            p['cannibalization']['leakage_share'] * cfg.case['margins']['mvno_paid']
            * p['cannibalization']['lost_margin_months']
        )
        # затраты на одного рандомизированного
        tr_cost = (
            s['take_rate'] * s['trial_month_cost']
            + s['offer_conversion'] * rw['month_cost'] * s['subsidized_months']
            + cc['crm_per_contact']
            + s['take_rate'] * (cc['onboarding_per_activation'] + cc['esim_activation'])
            + s['offer_conversion'] * leakage_per_rewarded
        )
        return baseline_t + t * mt + t * pp_per_rewarded - tr_cost, baseline_c + c * mc

    # Круг
    x = p['circle']
    cr = rng.random(n_sim) < x['creation_rate']
    acts = np.where(cr, rng.binomial(int(x['max_members']) - 1, x['invite_activation_rate'], n_sim), 0)
    inc = rng.binomial(acts, x['incremental_share'])
    marg = _lognorm(rng, x['participant_margin'] * real, cv, int(inc.sum()))
    rev = np.bincount(np.repeat(np.arange(n_sim), inc), weights=marg, minlength=n_sim)
    head = cr * (rng.random(n_sim) < x['head_personal_uplift_share']) * x['head_personal_margin'] * real
    pp_per_creator = (
        survival(cfg, x['subsidized_months']) * p['post_promo']['optin_rate']
        * paid_margin_sum(cfg, 12 - x['subsidized_months'])
    )
    leakage_per_creator = (
        p['cannibalization']['leakage_share'] * cfg.case['margins']['mvno_paid']
        * p['cannibalization']['lost_margin_months']
    )
    rw = circle_expected_reward(cfg)
    cost = (
        cr * rw['period_cost']
        + acts * (x['invite_trial_cost'] + x['invite_onboarding_cost'])
        + cc['crm_per_contact']
        + cr * leakage_per_creator
    )
    return baseline_t + rev + head + cr * pp_per_creator - cost, baseline_c


def arm_power(cfg, arm, n, cv=None):
    # Мощность ветки
    pilot = cfg.product['pilot']
    y_t, y_c = simulate_arm_outcomes(cfg, arm, cv=cv)
    deff = pilot['design_effect_circle'] if arm == 'circle' else 1.0
    eff = float(y_t.mean() - y_c.mean())
    varsum = float(y_t.var() + y_c.var()) * deff * (pilot.get('run_rate_noise_inflation', 1.0) ** 2)
    se = sqrt(varsum / n)
    za, zb = z(1 - pilot['alpha']), z(pilot['power'])  # односторонний тест H0: ITT <= 0
    power = float(norm.cdf(eff / se - za))
    nreq = int(np.ceil((za + zb) ** 2 * varsum / eff ** 2)) if eff > 0 else None
    return {
        'arm': arm,
        'effect_per_client': eff,
        'se': se,
        'power_at_n': power,
        'n_required': nreq,
        'n': n,
        'cv': pilot['margin_cv'] if cv is None else cv,
    }


def design_power(cfg):
    # Свод для слайда
    n = cfg.product['pilot']['n_per_arm']
    rows = [arm_power(cfg, 'solo', n), arm_power(cfg, 'circle', n)]

    sens = []
    for cv in cfg.product['pilot'].get('cv_sensitivity', [1.0, 2.0, 3.0]):
        sr = arm_power(cfg, 'solo', n, cv)
        cr = arm_power(cfg, 'circle', n, cv)
        sens.append({
            'cv': cv,
            'solo_n_required': sr['n_required'],
            'circle_n_required': cr['n_required'],
            'solo_power': sr['power_at_n'],
            'circle_power': cr['power_at_n'],
        })

    x = cfg.product['circle']
    return {
        'rows': rows,
        'circles_in_arm': n * x['creation_rate'],
        'binary_mde': {
            'p0_5pct': mde_binary(n, 0.05),
            'p0_10pct': mde_binary(n, 0.10),
            'p0_20pct': mde_binary(n, 0.20),
        },
        'stage2_n_per_arm': max(r['n_required'] or 0 for r in rows),
        'stage2_is_planning_placeholder': True,
        'cv_sensitivity': sens,
        'baseline_margin_sd': cfg.product['pilot']['baseline_margin_sd'],
        'note': (
            'Каждый ITT имеет собственный matched control той же eligibility-страты. '
            'Control и treatment несут одинаковую BAU/pre-post variance; Stage 2 N — '
            'planning placeholder и пересчитывается по фактической variance Stage 1.'
        ),
    }