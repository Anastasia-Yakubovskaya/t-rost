def signals():
    # Три метода быстрых сигналов до RCT: ретро-анализ, fake-door и micro-pilot с оценкой надёжности
    return [
        {
            'method': 'ретро-анализ графа приглашений/MNP/реактиваций',
            'weeks': '1-2',
            'purpose': 'baseline, variance, network potential',
            'reliability': 'medium',
        },
        {
            'method': 'fake-door Т-Круга',
            'weeks': '1-2',
            'purpose': 'CTR, creation intent, invitations per head',
            'reliability': 'low-medium',
        },
        {
            'method': 'micro-pilot без полного биллинга',
            'weeks': '3-4',
            'purpose': 'invite activation и первые Δ-события',
            'reliability': 'medium-high',
        },
    ]