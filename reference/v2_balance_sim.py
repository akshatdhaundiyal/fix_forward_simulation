import itertools, sys

SEG = ['W', 'M', 'S']
# id, name, cost, pitch ARR, segment, hidden U, risk pts, trust effects, flags
MENU = {
 1: [('A1','AI Copilot',35,6.0,'M',15,8,{},{}),
     ('A2','Self-serve onboarding revamp',20,2.0,'S',80,3,{'S':5},{}),
     ('A3','Bulk import & integrations',25,2.5,'M',75,5,{},{}),
     ('A4','Enterprise SSO & audit logs',30,3.0,'W',70,6,{'W':5},{}),
     ('A5','Mobile app refresh',20,2.5,'S',35,4,{},{}),
     ('A6','Usage-based pricing tier',15,1.5,'S',60,4,{},{})],
 2: [('B1','Bespoke compliance dashboard (Whale Alpha)',30,5.0,'W',100,9,{'W':10},{'bespoke':1}),
     ('B2','Enterprise data isolation',30,2.0,'W',60,5,{},{'alpha':1}),
     ('B3','Mid-market reporting suite',25,3.0,'M',80,5,{},{'mmgap':1}),
     ('B4','Partner marketplace API',35,5.0,'M',30,10,{},{}),
     ('B5','SMB referral loops',15,1.5,'S',70,3,{},{}),
     ('B6','Workflow automation',25,3.0,'S',55,6,{},{})],
 3: [('C1','Bespoke integration (Whale Beta)',25,4.0,'W',100,8,{'W':5},{'bespoke':1}),
     ('C2','Advanced analytics add-on',30,4.0,'W',75,6,{},{}),
     ('C3','AI meeting summaries',25,4.0,'M',25,7,{},{}),
     ('C4','Annual-plan pricing',15,2.0,'S',85,2,{},{}),
     ('C5','Localization pack',25,3.0,'M',65,5,{},{})],
 4: [('D1','Enterprise expansion pack',30,4.0,'W',70,7,{},{}),
     ('D2','Quick-win promo campaign',20,3.0,'S',40,6,{},{}),
     ('D3','Mid-market upsell bundle',25,3.0,'M',75,5,{},{}),
     ('D4','Audit readiness sprint',20,0,None,0,0,{},{'uod':-20}),
     ('D5','Executive customer summit',20,0,None,0,0,{'W':5,'M':5,'S':5},{})],
}
CARRY = {3: ['B2', 'B3']}
STANDING = [('P1','Platform hardening',15,0,None,0,0,{},{'uod':-12}),
            ('P2','Customer success program',15,0,None,0,0,{'W':3,'M':3,'S':3},{})]

P = dict(survey_cost=4, mq={0:1.6,10:1.0,20:0.35}, patch_debt=15, deep_cost=25, deep_uod=-10,
         patch_cost=10, deflect_trust=-10, melt_thresh=40, melt_floor=30, melt_cap=50,
         melt_pen=3.0, melt_trust=-35, safe_trust=5, tax=10, bespoke_mult=2.0,
         m0=2.0, m1=0.03, audit=0.25, churn_thresh=40, churn_pct=0.15,
         alpha_arr=3.0, alpha_trust=-10, mm_trust=-15)

def run(bot, verbose=False):
    arr = {'W':10.0,'M':9.0,'S':6.0}; besp = 0.0; nb = 0
    trust = {s:60.0 for s in SEG}; uod = 0.0; pen = 0.0; built = set(); hist = []
    for r in range(1,5):
        avail = 100 - P['tax']*nb
        if r == 3:
            if uod > P['melt_thresh']:
                drain = min(P['melt_cap'], uod - P['melt_floor'])
                avail -= drain; pen += P['melt_pen']; trust['W'] += P['melt_trust']; uod -= drain
            else:
                for s in SEG: trust[s] += P['safe_trust']
        items = list(MENU[r]) + [i for rr in range(1,r) for i in MENU[rr] if i[0] in CARRY.get(r,[])] + STANDING
        items = [i for i in items if i[0] not in built or i[0].startswith('P')]
        nsurv = bot['survey'](r); Q = bot['Q'](r); path = bot['crisis'](r) if r < 4 else None
        ccost = {None:0,'deep':P['deep_cost'],'patch':P['patch_cost'],'deflect':0}[path]
        budget = avail - nsurv*P['survey_cost'] - Q
        plan_budget = budget - (ccost if bot.get('reserve',True) else 0)
        informed = nsurv > 0
        def val(i):
            a = i[3]*i[5]/100 if (informed or i[8].get('bespoke')) else i[3]*bot.get('blind_disc',0.6)
            v = a*(P['bespoke_mult'] if i[8].get('bespoke') else 4.0)
            v += sum(i[7].values())/3*1.05*bot.get('w_trust',1)
            v += -i[8].get('uod',0)*0.3*bot.get('w_uod',1) - i[6]*P['mq'][Q]*0.3*bot.get('w_uod',1)
            if i[8].get('bespoke'): v += bot.get('bespoke_bias',0) - (4-r)*P['tax']*0.3
            if informed and i[8].get('alpha'): v += 14
            if informed and i[8].get('mmgap'): v += 7
            return v
        best = (0, ())
        for n in range(len(items)+1):
            for c in itertools.combinations(items, n):
                cost = sum(i[2] for i in c)
                if cost <= plan_budget:
                    v = sum(val(i) for i in c)
                    if v > best[0]: best = (v, c)
        ranked = sorted(best[1], key=lambda i: -val(i)/i[2])
        reserve = budget - sum(i[2] for i in ranked)
        need = ccost - reserve
        while need > 0 and ranked:
            need -= ranked.pop()[2]
        risk = 0
        for i in ranked:
            built.add(i[0])
            a = i[3]*i[5]/100
            if i[8].get('bespoke'): besp += a; nb += 1
            elif i[4]: arr[i[4]] += a
            for s,d in i[7].items(): trust[s] += d
            risk += i[6]; uod += i[8].get('uod',0)
        uod += risk*P['mq'][Q]
        if path == 'patch': uod += P['patch_debt']
        if path == 'deep': uod += P['deep_uod']
        if path == 'deflect':
            for s in SEG: trust[s] += P['deflect_trust']
        uod = max(0, uod)
        if r == 3:
            if 'B2' not in built: arr['W'] -= P['alpha_arr']; trust['W'] += P['alpha_trust']
            if 'B3' not in built: trust['M'] += P['mm_trust']
        for s in SEG:
            trust[s] = max(0, min(100, trust[s]))
            if trust[s] < P['churn_thresh']: arr[s] *= (1-P['churn_pct'])
        tot = sum(arr.values()) + besp
        hist.append((r, round(tot,2), round(sum(trust.values())/3,1), round(uod,1), [i[0] for i in ranked]))
    mult = P['m0'] + P['m1']*sum(trust.values())/3
    nev = sum(arr.values())*mult + besp*P['bespoke_mult'] - P['audit']*uod - pen
    return nev, hist

c = lambda v: (lambda r: v)
BOTS = {
 'Disciplined':     dict(survey=c(3), Q=c(20), crisis=c('deep')),
 'Balanced':        dict(survey=c(3), Q=c(10), crisis=lambda r: 'deep' if r<3 else 'patch'),
 'Corner-cutter':   dict(survey=c(3), Q=c(0), crisis=c('patch')),
 'Blind reckless':  dict(survey=c(0), Q=c(0), crisis=c('patch')),
 'Blind careful':   dict(survey=c(0), Q=c(20), crisis=c('deep')),
 'Deflector':       dict(survey=c(3), Q=c(20), crisis=c('deflect')),
 'Whale-chaser':    dict(survey=c(3), Q=c(10), crisis=c('deep'), bespoke_bias=30),
 'Late sprinter':   dict(survey=c(3), Q=lambda r: 20 if r<4 else 0, crisis=lambda r: 'deep' if r<3 else 'patch'),
}
if __name__ == '__main__':
    for kv in sys.argv[1:]:
        k,v = kv.split('='); P[k] = float(v)
    res = {n: run(b) for n,b in BOTS.items()}
    top = max(v[0] for v in res.values())
    for n,(nev,h) in sorted(res.items(), key=lambda x:-x[1][0]):
        print(f"{n:15s} NEV {nev:6.1f} ({nev/top*100:5.1f}%)  ARR by Q: {[x[1] for x in h]}  trust: {[x[2] for x in h]}  UOD: {[x[3] for x in h]}")
        if '-v' in sys.argv or True: print('    ', [x[4] for x in h])
