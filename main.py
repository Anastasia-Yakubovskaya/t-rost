import argparse
import json
import sys

from src.config_loader import Config
from src.portfolio_economics import calculate
from src.monte_carlo import simulate
from src.robustness import breakeven_table, stress_scenarios, tornado, with_overrides
from src.power_analysis import design_power
from src.pilot_design import design
from src.cannibalization import firewall_coverage
from src.reward_engine import circle_ladder, start_option_exposure
from src.margin_derivation import solo_margin, circle_participant_margin, threshold_check, margin_realization
from src.unit_economics import solo_per_incremental, circle_per_incremental_invitee
from src.segments import estimate as segment_estimate
from src.monthly_profile import portfolio_monthly

try:
    sys.stdout.reconfigure(encoding='utf-8')
except Exception:
    pass


def rub(x):
    return f"{x:,.0f}".replace(',', ' ')


def mln(x):
    return f"{x/1e6:+.1f}".replace('.', ',')


def _clean(o):
    # numpy-скаляры превращаем в обычные числа, чтобы json сериализовался без ошибок
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_clean(v) for v in o]
    if hasattr(o, 'item'):
        return o.item()
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--optimistic', action='store_true',
                    help='не начислять полную субсидию inframarginal-клиентам; только sensitivity')
    a = ap.parse_args()

    cfg = Config()
    if a.optimistic:
        cfg = with_overrides(cfg, {('solo', 'price_inframarginal_subsidy'): False})

    # Все расчётные блоки 
    r = calculate(cfg)
    mc = simulate(cfg)
    st = stress_scenarios(cfg)
    be = breakeven_table(cfg)
    pw = design_power(cfg)
    fw = firewall_coverage(cfg)

    # Вывод Δ-маржи из компонентов и юнит-экономика на клиента
    deriv = {
        'solo': solo_margin(cfg),
        'circle': circle_participant_margin(cfg),
        'threshold': threshold_check(cfg),
        'realization': margin_realization(cfg),
    }
    unit = {
        'solo': solo_per_incremental(cfg),
        'circle': circle_per_incremental_invitee(cfg),
    }
    seg = segment_estimate(cfg)
    monthly = portfolio_monthly(cfg)

    x = cfg.product['circle']
    cc = cfg.case['telecom_costs']
    ladder = [
        circle_ladder(x['reward_levels'], k, x['participant_margin'] * deriv['realization'],
                      x['incremental_share'], cc, subsidized_months=x['subsidized_months'])
        for k in range(4)
    ]
    ladder_low = [
        circle_ladder(x['reward_levels'], k, x['participant_margin'] * deriv['realization'],
                      0.5, cc, subsidized_months=x['subsidized_months'])
        for k in range(4)
    ]
    exposure = start_option_exposure(x['reward_levels'], cc, x['start_option_months'])

    pilot = design(cfg)
    pilot['stage1_budget'] = cfg.product['pilot']['stop_loss']

    # Единый артефакт
    out = {
        'portfolio': r,
        'mc': mc,
        'robustness': {'breakeven': be, 'stress': st, 'tornado': tornado(cfg)},
        'firewall': fw,
        'derivation': deriv,
        'unit': unit,
        'segments': seg,
        'monthly': monthly,
        'ladder': {
            'incrementality_70': ladder,
            'incrementality_50': ladder_low,
            'start_exposure_per_circle': exposure,
        },
        'power': pw,
        'pilot': pilot,
        'assumptions': {
            'solo': {
                'offer_conversion': cfg.product['solo']['offer_conversion'],
                'organic_rate': cfg.product['solo']['organic_rate'],
                'subsidized_months': cfg.product['solo']['subsidized_months'],
                'reward': r['solo']['reward'],
            },
            'circle': {
                'creation_rate': cfg.product['circle']['creation_rate'],
                'invite_activation_rate': cfg.product['circle']['invite_activation_rate'],
                'incremental_share': cfg.product['circle']['incremental_share'],
                'avg_invites': cfg.product['circle']['avg_invites'],
                'max_members': cfg.product['circle']['max_members'],
            },
            'qualified_delta': cfg.product['qualified_delta'],
            'pilot': {
                'margin_cv': cfg.product['pilot']['margin_cv'],
                'run_rate_noise_inflation': cfg.product['pilot']['run_rate_noise_inflation'],
            },
        },
        'meta': {
            'model_version': 'v10-shortlist',
            'source_of_truth': 'config/product_paths.yml',
            'optimistic': a.optimistic,
        },
    }

    # Консольная сводка
    print(f"Т-Соло: {r['solo']['contacts']:,} контактов | net {rub(r['solo']['net'])} ₽ | coverage {r['solo']['sf']:.2f}x")
    print(f"Т-Круг: {r['circle']['contacts']:,} контактов | net {rub(r['circle']['net'])} ₽ | coverage {r['circle']['sf']:.2f}x")
    print(f"Группа: доход {rub(r['revenue'])} ₽ | op cost {rub(r['operating_cost'])} ₽ | dev {rub(r['development'])} ₽")
    print(f"Net {rub(r['group_net'])} ₽ | operating {r['operating_sf']:.2f}x | full-cost {r['full_cost_sf']:.2f}x")
    print(f"Банк / MVNO: {rub(r['bank'])} / {rub(r['mvno'])} ₽")
    print(f"Δ-маржа Соло: {deriv['solo']['total']:.0f} ₽ = остатки {deriv['solo']['balance']:.0f} + карты {deriv['solo']['card']:.0f} + cross-sell {deriv['solo']['cross_sell']:.0f}")
    print(f"Qualified Δ: +{rub(deriv['threshold']['threshold_rub'])} ₽ остатка → {deriv['threshold']['ratio']:.2f}x к субсидии до учета CRM/onboarding")
    print(f"MC: P(net>0)={mc['p_net_pos']:.0%}; P(full-cost>=1.3x)={mc['p_full13']:.0%}; P5/P50/P95={mln(mc['p5'])}/{mln(mc['p50'])}/{mln(mc['p95'])} млн ₽")
    print('Стрессы:')
    for z in st:
        print(f"  {z['label']:<40} net {mln(z['group_net']):>6} млн | full {z['full_cost_sf']:.2f}x")
    print(f"Power Stage 1 (n=800): Solo {pw['rows'][0]['power_at_n']:.0%}, Circle {pw['rows'][1]['power_at_n']:.0%}; Stage 2 base ≈ {pw['stage2_n_per_arm']} на ветку")

    # В основной артефакт пишем только инвестиционную базу; optimistic — сравнительный режим
    path = cfg.root / 'output' / 'model_out.json'
    path.parent.mkdir(exist_ok=True)
    if not a.optimistic:
        path.write_text(json.dumps(_clean(out), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"\nОбновлено: {path}")
    return out


if __name__ == '__main__':
    main()