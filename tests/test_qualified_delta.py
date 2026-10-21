from src.config_loader import Config
from src.qualified_delta import (Rules, qualifies_balance, qualifies_salary, invitee_kind, qualifies_referral,
                                 fraud_flags, exclude_intra_circle, can_invite, can_create_circle, clawback_due)
from src.reward_engine import circle_ladder, start_option_exposure, calibrated_margin

R = Rules()


def test_one_day_balance_spike_is_not_qualified():
    # Перевод 500к на один день не должен считаться ростом
    spike = [20_000] * 29 + [500_000]
    assert not qualifies_balance(spike, baseline=20_000, rules=R)


def test_sustained_balance_growth_is_qualified():
    # Проверка на истинный рост, если остаток стабильно держится выше baseline
    assert qualifies_balance([50_000] * 30, baseline=20_000, rules=R)


def test_balance_needs_full_window():
    # Нужно полное окно наблюдений, иначе данных недостаточно для решения
    assert not qualifies_balance([40_000] * 10, baseline=20_000, rules=R)


def test_salary_needs_two_regular_receipts():
    # Одно поступление — мало, два с разрывом — ок, два в один день — не считается
    one = [{'day': 10, 'amount': 90_000, 'payer_id': 'employer-A', 'salary_signal': True}]
    two = one + [{'day': 40, 'amount': 92_000, 'payer_id': 'employer-A', 'salary_signal': True}]
    same_day_split = [{'day': 10, 'amount': 45_000, 'payer_id': 'employer-A', 'salary_signal': True}, {'day': 10, 'amount': 45_000, 'payer_id': 'employer-A', 'salary_signal': True}]
    assert not qualifies_salary(one, R) and qualifies_salary(two, R) and not qualifies_salary(same_day_split, R)


def test_salary_from_own_account_or_circle_not_counted():
    # Переводы от себя или от участников круга не считаются зарплатой
    own = [{'day': 5, 'amount': 90_000, 'payer_id': 'x', 'salary_signal': True, 'own_account': True}, {'day': 40, 'amount': 90_000, 'payer_id': 'x', 'salary_signal': True, 'own_account': True}]
    circ = [{'day': 5, 'amount': 90_000, 'payer_id': 'x', 'salary_signal': True, 'from_circle_member': True}, {'day': 40, 'amount': 90_000, 'payer_id': 'x', 'salary_signal': True, 'from_circle_member': True}]
    assert not qualifies_salary(own, R) and not qualifies_salary(circ, R)



def test_arbitrary_p2p_transfers_do_not_qualify_salary():
    # Два обычных внешних P2P больше не маскируются под зарплату.
    p2p = [
        {'day': 5, 'amount': 90_000, 'payer_id': 'friend-1', 'salary_signal': False},
        {'day': 35, 'amount': 90_000, 'payer_id': 'friend-1', 'salary_signal': False},
    ]
    different_payers = [
        {'day': 5, 'amount': 90_000, 'payer_id': 'payer-A', 'salary_signal': True},
        {'day': 35, 'amount': 90_000, 'payer_id': 'payer-B', 'salary_signal': True},
    ]
    unstable_amounts = [
        {'day': 5, 'amount': 35_000, 'payer_id': 'employer-A', 'salary_signal': True},
        {'day': 35, 'amount': 90_000, 'payer_id': 'employer-A', 'salary_signal': True},
    ]
    assert not qualifies_salary(p2p, R)
    assert not qualifies_salary(different_payers, R)
    assert not qualifies_salary(unstable_amounts, R)


def test_referral_rules():
    # Проверяем классификацию
    assert invitee_kind(0, False, R) == 'new_to_bank'
    assert invitee_kind(120, True, R) == 'reactivated'
    assert invitee_kind(10, True, R) == 'existing'
    assert qualifies_referral('new_to_bank', 30, (), R)
    assert not qualifies_referral('new_to_bank', 29, (), R)
    assert not qualifies_referral('existing', 60, (), R)
    assert not qualifies_referral('new_to_bank', 60, ('shared_device',), R)


def test_fraud_flags_and_intra_circle_exclusion():
    # Общее устройство/адрес/телефон = fraud-флаг
    assert fraud_flags({'device_id': 'd1'}, {'device_id': 'd1'}) == ['shared_device']
    assert fraud_flags({'device_id': 'd1'}, {'device_id': 'd2'}) == []
    assert 'circular_inflow' in fraud_flags({}, {'share_of_inflow_from_circle': 0.8})
    tx = [{'from': 'a', 'to': 'b', 'amt': 1}, {'from': 'x', 'to': 'a', 'amt': 2}]
    assert exclude_intra_circle(tx, {'a', 'b', 'c'}) == [tx[1]]


def test_spam_invitations_are_bounded_and_free():
    # Лимит приглашений работает
    assert can_invite(2, 1, R) and not can_invite(3, 1, R) and not can_invite(0, 2, R)
    assert can_create_circle(0, R) and not can_create_circle(1, R)
    cfg = Config(); x = cfg.product['circle']; cc = cfg.case['telecom_costs']
    assert start_option_exposure(x['reward_levels'], cc, x['start_option_months']) <= 200


def test_rules_from_config_match_defaults():
    # Если в конфиге нет кастомных правил, должны использоваться дефолтные значения
    assert Rules.from_config(Config()) == Rules()


def test_clawback():
    # Если Δ не удержан после разблокировки — уровень пакета снижается 
    assert clawback_due(False) and not clawback_due(True)


def test_ladder_is_monotonic_and_degrades_when_incrementality_falls():
    # Лестница монотонна
    cfg = Config(); x = cfg.product['circle']; cc = cfg.case['telecom_costs']
    hi = [circle_ladder(x['reward_levels'], k, x['participant_margin'], 0.7, cc)['gb'] for k in range(4)]
    lo = [circle_ladder(x['reward_levels'], k, x['participant_margin'], 0.2, cc)['gb'] for k in range(4)]
    assert hi == sorted(hi) and lo == sorted(lo)
    assert hi == [5, 10, 15, 20]
    assert all(l <= h for l, h in zip(lo, hi)) and lo[1] < hi[1]


def test_calibrated_margin_is_capped_by_proxy():
    # Калиброванная маржа = proxy × incrementality
    assert calibrated_margin(1000, 0.7) == 700 and calibrated_margin(1000, 1.5) == 1000