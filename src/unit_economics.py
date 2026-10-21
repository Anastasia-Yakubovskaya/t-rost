from src.margin_derivation import margin_realization, paid_margin_sum, survival
from src.reward_engine import solo_reward_for_cfg, circle_expected_reward


def solo_per_incremental(cfg):
    # Все показатели — на одного клиента Т-Соло
    s = cfg.product['solo']
    c = cfg.product['common_costs']
    real = margin_realization(cfg)

    free_months = 1 + s['subsidized_months'] 
    uplift = max(1e-9, s['offer_conversion'] - s['organic_rate'])
    # На одного  приходится столько конверсий и активаций
    converters_per_inc = s['offer_conversion'] / uplift
    takers_per_inc = s['take_rate'] / uplift

    # Доход
    bank = s['delta_margin_per_incremental_client'] * real
    post = (
        converters_per_inc
        * survival(cfg, free_months)
        * cfg.product['post_promo']['optin_rate']
        * paid_margin_sum(cfg, 12 - free_months)
    )

    # Затраты
    reward = solo_reward_for_cfg(cfg)
    telecom = (
        takers_per_inc * s['trial_month_cost']
        + converters_per_inc * reward['month_cost'] * s['subsidized_months']
    )
    onboarding = takers_per_inc * (c['onboarding_per_activation'] + c['esim_activation'])
    crm = c['crm_per_contact'] / uplift
    leak = (
        converters_per_inc
        * cfg.product['cannibalization']['leakage_share']
        * cfg.case['margins']['mvno_paid']
        * cfg.product['cannibalization']['lost_margin_months']
    )

    cost = telecom + onboarding + crm + leak
    return {
        'bank_margin': bank,
        'post_promo': post,
        'revenue': bank + post,
        'telecom': telecom,
        'onboarding_crm': onboarding + crm,
        'cannibalization': leak,
        'cost': cost,
        'net': bank + post - cost,
        'coverage': (bank + post) / cost,
    }


def circle_per_incremental_invitee(cfg):
    # То же для Т-Круга, но в пересчёте на одного приглашённого
    x = cfg.product['circle']
    c = cfg.product['common_costs']
    real = margin_realization(cfg)

    inc_per_creator = max(
        1e-9,
        x['avg_invites'] * x['invite_activation_rate'] * x['incremental_share'],
    )

    bank = (
        x['participant_margin'] * real
        + (x['head_personal_uplift_share'] * x['head_personal_margin'] * real) / inc_per_creator
    )
    post = (
        survival(cfg, x['subsidized_months'])
        * cfg.product['post_promo']['optin_rate']
        * paid_margin_sum(cfg, 12 - x['subsidized_months'])
        / inc_per_creator
    )

    # Затраты круга и CRM делятся на число приглашённых
    reward = circle_expected_reward(cfg)
    telecom = (
        reward['period_cost'] / inc_per_creator
        + x['invite_trial_cost'] / x['incremental_share']
    )
    onboard = x['invite_onboarding_cost'] / x['incremental_share']
    crm = c['crm_per_contact'] / (x['creation_rate'] * inc_per_creator)
    leak = (
        cfg.product['cannibalization']['leakage_share']
        * cfg.case['margins']['mvno_paid']
        * cfg.product['cannibalization']['lost_margin_months']
        / inc_per_creator
    )

    cost = telecom + onboard + crm + leak
    return {
        'bank_margin': bank,
        'post_promo': post,
        'revenue': bank + post,
        'telecom': telecom,
        'onboarding_crm': onboard + crm,
        'cannibalization': leak,
        'cost': cost,
        'net': bank + post - cost,
        'coverage': (bank + post) / cost,
    }