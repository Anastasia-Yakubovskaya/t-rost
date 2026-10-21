# Методология

## Причинность

Qualified Δ — условие выплаты, не доказательство причинности. Эффект оценивается как ITT между заранее рандомизированными control/treatment внутри eligibility-страт. После масштабирования сохраняется holdout 10%.

## Т-Соло

Incremental clients = contacts × (offer conversion − organic conversion).

Банковская Δ-маржа = incremental clients × 4 200 ₽ × доля реализованного 12-месячного окна. Доля окна учитывает лаг квалификации 2 месяца и затухание поведения 2,5%/мес.

Инвестиционная база начисляет субсидию всем прошедшим Qualified Δ, включая inframarginal/windfall.

## Т-Круг

Единица рандомизации и анализа — глава. Treatment получает возможность создать круг; control — нет. Downstream-маржа приглашённых после consent атрибутируется главе по first-touch. Это не требует знать «будущих приглашённых» у контроля.

Incremental invitees = creators × invites × activation × incrementality.

## Gate

SCALE: ITT > 0, operating и full-cost coverage ≥ 1,3×, нижняя граница 80% CI ≥ 1,0×, guardrails в норме.

ITERATE: есть положительный сигнал, но full-cost <1,3× либо CI слишком широкий.

STOP: ITT <0, критический guardrail или full-cost <1,0× при верхней границе CI <1,3×.

## Основные риски

База full-cost ≈1,37×. Одно ухудшение крупного допущения часто уводит ниже 1,3×. Комбинированный стресс убыточен. Monte Carlo не трактуется как реальная вероятность успеха.
