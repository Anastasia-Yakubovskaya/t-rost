from src.config_loader import Config
from src.power_analysis import mde_binary, design_power
from src.pilot_design import decide, design

def test_mde_binary_800_is_a_few_pp():
    # MDE на 800 — единицы п.п.
    assert .03<mde_binary(800,.05)<.045
    assert mde_binary(800,.10)>mde_binary(800,.05)
    assert mde_binary(3200,.10)<mde_binary(800,.10)

def test_800_is_stage1_not_proof_for_solo():
    # 800 — kill-switch, не доказательство
    p=design_power(Config())
    solo=next(r for r in p['rows'] if r['arm']=='solo')
    circle=next(r for r in p['rows'] if r['arm']=='circle')
    assert solo['power_at_n']<.80
    assert p['stage2_n_per_arm']>800
    assert p['circles_in_arm']==120
    assert circle['power_at_n']>solo['power_at_n']

def test_cv_sensitivity_increases_required_n():
    # выше cv — больше нужная выборка
    s=design_power(Config())['cv_sensitivity']
    assert s[0]['solo_n_required']<s[1]['solo_n_required']<s[2]['solo_n_required']

def test_decision_rules_require_both_coverages():
    # SCALE только при обоих покрытиях
    assert decide(1.5,1.4,1.1,1.8,itt=200)=='SCALE'
    assert decide(1.5,1.2,1.1,1.8,itt=200)=='ITERATE'
    assert decide(.9,.8,.4,1.2,itt=-50)=='STOP'
    assert decide(1.6,1.5,1.3,1.9,itt=300,guardrails_ok=False)=='STOP'

def test_circle_randomization_does_not_require_future_invite_graph():
    # рандомизация без графа будущих приглашений
    d=design(Config())
    assert 'глава' in d['circle_design']
    assert 'после consent' in d['circle_design']
    assert 'будущих приглашений' in d['interference']
    assert d['extended_observation_days']==180


def test_pilot_has_matched_control_per_eligibility_stratum():
    # свой контроль в каждой страте
    d=design(Config())
    assert d['total_n']==3200
    assert len(d['comparisons'])==2
    assert all(x['n_control']==800 and x['n_treatment']==800 for x in d['comparisons'])

def test_circle_control_has_nonzero_variance():
    # контроль Круга 
    from src.power_analysis import simulate_arm_outcomes
    import numpy as np
    _,yc=simulate_arm_outcomes(Config(),'circle',n_sim=20000)
    assert np.var(yc)>0