import pytest
from src.config_loader import Config
from src.portfolio_economics import calculate
from src.robustness import with_overrides, breakeven_table, stress_scenarios, find_crossing, scale_telecom
from src.cannibalization import firewall_coverage
from src.monte_carlo import simulate

def test_overrides_do_not_mutate_base():
    # точечные правки не меняют базовый конфиг
    cfg=Config(); before=cfg.product['circle']['incremental_share']
    with_overrides(cfg,{('circle','incremental_share'):.1})
    assert cfg.product['circle']['incremental_share']==before

def test_investment_base_is_positive_but_not_overconfident():
    # база положительна, но без переоценки: субсидию получают и пришедшие бы сами
    r=calculate(Config())
    assert r['group_net']>0 and r['full_cost_sf']>1.3
    assert r['solo']['windfall_share']>0

def test_breakeven_full_cost_is_consistent():
    # порог полной окупаемости сходится с 1,3
    cfg=Config(); row=next(x for x in breakeven_table(cfg) if x['key']=='circle_incremental_share')
    r=calculate(with_overrides(cfg,{('circle','incremental_share'):row['portfolio_full_ge_1_3']}))
    assert r['full_cost_sf']==pytest.approx(1.3,abs=1e-3)

def test_circle_alone_needs_material_incrementality():
    # Кругу в одиночку нужна высокая инкрементальность
    row=next(x for x in breakeven_table(Config()) if x['key']=='circle_incremental_share')
    assert .3<row['circle_ge_1_0']<.4 and .4<row['circle_ge_1_3']<.55

def test_find_crossing_none_when_absent():
    # пересечения нет — результата тоже нет
    assert find_crossing(lambda x:x,5,0,1) is None

def test_stress_scenarios_include_negative_combined():
    # комбинированный стресс ломает экономику
    st={s['id']:s for s in stress_scenarios(Config())}
    assert st['no_decay']['group_net']>st['base']['group_net']>st['combined']['group_net']
    assert st['combined']['group_net']<0 and st['combined']['full_cost_sf']<1

def test_firewall_makes_paid_mvno_bad():
    # платящий абонент убыточен — ограничитель оправдан
    fw=firewall_coverage(Config())
    assert fw['coverage_paid_mvno']<1.0<fw['coverage_without_firewall']

def test_monte_carlo_includes_full_cost_gate():
    # порог полной окупаемости строже порога прибыли
    mc=simulate(Config())
    assert 0<mc['p_full13']<mc['p_net_pos']<1
    assert mc['p5']<mc['p50']<mc['p95']

def test_telecom_scale_raises_cost():
    # рост себестоимости связи поднимает затраты
    cfg=Config()
    assert calculate(scale_telecom(cfg,1.2))['operating_cost']>calculate(cfg)['operating_cost']