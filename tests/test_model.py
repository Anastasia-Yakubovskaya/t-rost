from src.reward_engine import solo_reward
import pytest
from src.config_loader import Config
from src.portfolio_economics import calculate
from src.reward_engine import max_subsidy, choose_circle_reward
from src.margin_derivation import solo_margin, circle_participant_margin, threshold_check

def test_group_equals_bank_plus_mvno():
    # трансферт нейтрален для группы
    r=calculate(Config())
    assert r['group_net'] == pytest.approx(r['bank']+r['mvno'])

def test_base_passes_both_coverage_gates():
    # база проходит оба порога 1.3×
    r=calculate(Config())
    assert r['operating_sf']>=1.3 and r['full_cost_sf']>=1.3

def test_circle_incrementality_is_not_full_activation():
    # incremental не больше activated
    r=calculate(Config())['circle']
    assert r['incremental_invitees'] <= r['activated_invitees']

def test_reward_budget_has_safety_buffer():
    # субсидия = маржа / 1.3
    assert max_subsidy(1300,1.3)==1000

def test_reward_is_monotonic():
    # лестница не убывает
    levels=Config().product['circle']['reward_levels']
    assert choose_circle_reward(7000,levels)['gb'] >= choose_circle_reward(3000,levels)['gb']

def test_six_month_cap_is_in_costs():
    # cap 6 месяцев реально в затратах
    cfg=Config(); r=calculate(cfg); s,c=r['solo'],r['circle']
    assert 1+cfg.product['solo']['subsidized_months']==6
    assert cfg.product['circle']['subsidized_months']==6
    assert s['telecom']==pytest.approx(s['takers']*65+s['rewarded']*185*5)
    assert c['telecom']==pytest.approx(c['creators']*c['reward']['period_cost']+c['activated_invitees']*65)

def test_margin_derivation_matches_config():
    # вывод маржи сходится с конфигом
    cfg=Config()
    assert solo_margin(cfg)['total']==pytest.approx(cfg.product['solo']['delta_margin_per_incremental_client'])
    assert circle_participant_margin(cfg)['total']==pytest.approx(cfg.product['circle']['participant_margin'])

def test_qualified_balance_threshold_covers_subsidy():
    # порог Qualified Δ окупает субсидию
    t=threshold_check(Config())
    assert t['ratio']>=t['required_ratio']

def test_solo_budget_guard_downgrades_when_causal_share_falls():
    # guard снижает пакет при падении причинности
    cfg=Config(); s=cfg.product['solo']; cc=cfg.case['telecom_costs']
    hi=solo_reward(s['reward_levels'], s['delta_margin_per_incremental_client'], 0.75, s['subsidized_months'], cc, cfg.product['portfolio']['safety_threshold'])
    lo=solo_reward(s['reward_levels'], s['delta_margin_per_incremental_client'], 0.20, s['subsidized_months'], cc, cfg.product['portfolio']['safety_threshold'])
    assert hi['gb'] == 15
    assert lo['gb'] < hi['gb']

def test_circle_reward_engine_drives_pnl_cost():
    # reward engine управляет затратами Круга
    from src.robustness import with_overrides
    base=calculate(Config())['circle']
    low=calculate(with_overrides(Config(),{('circle','incremental_share'):0.20}))['circle']
    assert low['reward']['expected_month_cost'] <= base['reward']['expected_month_cost']
    assert low['telecom'] <= base['telecom']

def test_monthly_profile_reconciles_to_portfolio_pnl():
    # помесячный профиль сходится с P&L
    from src.monthly_profile import portfolio_monthly
    cfg=Config(); r=calculate(cfg); rows=portfolio_monthly(cfg)
    assert rows[-1]['cum_net'] == pytest.approx(r['group_net'])