def routing_policy():
    return [
      '1) S5 paid MVNO → no offer (firewall).',
      '2) S2 salary elsewhere → Solo; if also S1, S2 wins to keep one treatment.',
      '3) Remaining S1 low wallet share → Solo.',
      '4) S3 dormant → Circle head; S4 new-to-bank appears only downstream after consent.',
      '5) Everyone else → business as usual / control pool.'
    ]

def estimate(cfg):
    cb=cfg.case['client_base']; sg=cfg.product['segmentation']; active=cb['active_clients']; inactive=cb['total_clients']-active
    s2=active*sg['salary_elsewhere_share_of_active']; s1=active*sg['low_wallet_share_of_active']; s3=inactive*sg['reactivable_share_of_inactive']; paid=cb['mvno_paid_subscribers']
    return {'S2':{'name':'Зарплата в другом банке','size':s2,'route':'Т-Соло','data':'зарплатные зачисления, переводы, средний остаток, MNP, намерение','priority':1},'S1':{'name':'Низкая доля кошелька / высокий потенциал','size':s1,'route':'Т-Соло','data':'остатки, карточные траты, доля кошелька, продукты, доход','priority':2},'S3':{'name':'Dormant / реактивация','size':s3,'route':'Т-Круг','data':'давность активности, коммуникации, отклики, сеть переводов','priority':3},'S4':{'name':'New-to-bank в окружении клиентов','size':None,'route':'Т-Круг downstream','data':'приглашения, согласия, KYC, first-touch атрибуция','priority':4},'S5':{'name':'Платящие абоненты MVNO','size':paid,'route':'не предлагать','data':'тариф, платежи, маржа, семейные/доп. SIM','priority':99},'routing_policy':routing_policy(),'note':'S1/S2 пересекаются и не суммируются как TAM; при конфликте S2 имеет приоритет. S4 не является pre-consent сегментом для таргетинга.'}
