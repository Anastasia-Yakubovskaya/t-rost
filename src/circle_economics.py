from src.margin_derivation import margin_realization, post_promo_revenue, leakage_cost
from src.reward_engine import circle_expected_reward


def calculate(cfg):
    # Воронка Т-Круг
    p = cfg.product['portfolio']
    x = cfg.product['circle']
    c = cfg.product['common_costs']
    real = margin_realization(cfg)  # доля маржи, которая реально реализуется 

    contacts = int(round(p['contacts'] * p['circle_share']))
    creators = contacts * x['creation_rate']
    invites = creators * x['avg_invites']
    activated_invitees = invites * x['invite_activation_rate']
    qualified_invitees = activated_invitees * x['qualified_share_of_activated']
    incremental_invitees = activated_invitees * x['incremental_share']

    # Доход банка
    participant_margin = incremental_invitees * x['participant_margin'] * real
    heads_with_uplift = creators * x['head_personal_uplift_share']
    head_margin = heads_with_uplift * x['head_personal_margin'] * real
    bank_revenue = participant_margin + head_margin

    post_promo = post_promo_revenue(cfg, creators, x['subsidized_months'])
    revenue = bank_revenue + post_promo

    # Затраты
    reward = circle_expected_reward(cfg)
    telecom = creators * reward['period_cost'] + activated_invitees * x['invite_trial_cost']
    crm = contacts * c['crm_per_contact']
    onboarding = activated_invitees * x['invite_onboarding_cost']
    cannibalization = leakage_cost(cfg, creators)  # утечка маржи от платящих MVNO

    cost = telecom + crm + onboarding + cannibalization

    return {
        'contacts': contacts,
        'creators': creators,
        'invites': invites,
        'activated_invitees': activated_invitees,
        'qualified_invitees': qualified_invitees,
        'incremental_invitees': incremental_invitees,
        'participant_margin': participant_margin,
        'head_margin': head_margin,
        'bank_revenue': bank_revenue,
        'post_promo': post_promo,
        'revenue': revenue,
        'reward': reward,
        'telecom': telecom,
        'crm': crm,
        'onboarding': onboarding,
        'cannibalization': cannibalization,
        'cost': cost,
        'net': revenue - cost,
        'sf': revenue / cost if cost else 0,
        'incremental_per_circle': incremental_invitees / creators if creators else 0,
    }