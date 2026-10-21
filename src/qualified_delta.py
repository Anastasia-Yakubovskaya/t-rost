from dataclasses import dataclass
from statistics import mean, median
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Rules:
    balance_window_days: int = 30
    balance_min_delta: float = 25_000
    salary_min_receipts: int = 2
    salary_window_days: int = 60
    salary_min_gap_days: int = 14
    salary_min_amount: float = 30_000
    salary_max_amount_ratio: float = 1.5
    salary_require_same_payer: bool = True
    salary_require_salary_signal: bool = True
    referral_active_days: int = 30
    new_to_bank_lookback_days: int = 180
    reactivation_dormant_days: int = 90
    vesting_days: int = 60
    clawback_days: int = 90
    max_circles_per_client: int = 1
    max_open_invitations: int = 3

    @classmethod
    def from_config(cls, cfg):
        d = cfg.product['qualified_delta']
        return cls(**{k: d[k] for k in cls.__dataclass_fields__ if k in d})


def qualifies_balance(daily_balances: Sequence[float], baseline: float, rules: Rules = Rules()) -> bool:
    # Прирост остатка: и 30-дневное среднее, и медиана выше baseline на порог
    w = list(daily_balances)[-rules.balance_window_days:]
    if len(w) < rules.balance_window_days:
        return False
    return mean(w) - baseline >= rules.balance_min_delta and median(w) - baseline >= rules.balance_min_delta


def _salary_candidate(r: dict, rules: Rules) -> bool:
    if r.get('own_account') or r.get('from_circle_member'):
        return False
    if r.get('day', rules.salary_window_days + 1) > rules.salary_window_days:
        return False
    if float(r.get('amount', 0.0)) < rules.salary_min_amount:
        return False
    # В проде этот флаг приходит из классификатора типа поступления / payroll-реестра.
    if rules.salary_require_salary_signal and not bool(r.get('salary_signal')):
        return False
    if rules.salary_require_same_payer and not r.get('payer_id'):
        return False
    return True


def qualifies_salary(receipts: Iterable[dict], rules: Rules = Rules()) -> bool:
    # Квалифицирующиеся зарплатные поступления: не меньше минимального числа, с подходящим разрывом и стабильной суммой.
    rows = [r for r in receipts if _salary_candidate(r, rules)]
    if len(rows) < rules.salary_min_receipts:
        return False

    groups = {}
    for r in rows:
        key = r.get('payer_id') if rules.salary_require_same_payer else '__all__'
        groups.setdefault(key, []).append(r)

    for grp in groups.values():
        grp = sorted(grp, key=lambda r: r['day'])
        if len(grp) < rules.salary_min_receipts:
            continue
        # Ищем любую пару с подходящим временным разрывом и стабильной суммой.
        for i, a in enumerate(grp):
            for b in grp[i + 1:]:
                if b['day'] - a['day'] < rules.salary_min_gap_days:
                    continue
                lo, hi = sorted((float(a['amount']), float(b['amount'])))
                if lo <= 0:
                    continue
                if hi / lo <= rules.salary_max_amount_ratio:
                    return True
    return False


def invitee_kind(days_since_last_product_activity: int, has_prior_product_in_lookback: bool, rules: Rules = Rules()) -> str:
    # Классификация приглашённого: new_to_bank / reactivated / existing.
    if not has_prior_product_in_lookback:
        return 'new_to_bank'
    if days_since_last_product_activity >= rules.reactivation_dormant_days:
        return 'reactivated'
    return 'existing'


def qualifies_referral(kind: str, active_days: int, flags: Iterable[str] = (), rules: Rules = Rules()) -> bool:
    return kind in ('new_to_bank', 'reactivated') and active_days >= rules.referral_active_days and not list(flags)


def fraud_flags(head: dict, invitee: dict) -> list:
    flags = []
    for key, name in (('device_id', 'shared_device'), ('address_hash', 'shared_address'), ('phone_hash', 'shared_phone')):
        if head.get(key) and head.get(key) == invitee.get(key):
            flags.append(name)
    if invitee.get('share_of_inflow_from_circle', 0.0) > 0.5:
        flags.append('circular_inflow')
    return flags


def exclude_intra_circle(transactions: Iterable[dict], member_ids: set) -> list:
    return [t for t in transactions if not (t['from'] in member_ids and t['to'] in member_ids)]


def reward_unlock_day(rules: Rules = Rules()) -> int:
    return rules.vesting_days


def clawback_due(delta_kept_after_unlock: bool) -> bool:
    return not delta_kept_after_unlock


def can_create_circle(circles_owned: int, rules: Rules = Rules()) -> bool:
    # Создать новый круг можно только пока число уже созданных кругов строго меньше лимита.
    return circles_owned < rules.max_circles_per_client


def can_invite(open_invitations: int, circles_owned: int, rules: Rules = Rules()) -> bool:
    # Приглашать можно только в уже существующий допустимый круг
    return (
        1 <= circles_owned <= rules.max_circles_per_client
        and open_invitations < rules.max_open_invitations
    )
