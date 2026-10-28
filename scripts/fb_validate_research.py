"""Quick validation of the market research files before merging."""
import glob
import json
import os

qs = json.load(open('data/benchmarks/2026-10-25-llm.json', encoding='utf-8'))['questions']
mkt = {str(q['id']) for q in qs
       if q['source'] in ('kalshi', 'polymarket', 'metaculus') and not isinstance(q['id'], list)}
banned = ['polymarket.com', 'kalshi.com', 'manifold.markets', 'predictit.org',
          'metaculus.com', 'gjopen.com', 'goodjudgment.com', 'infer-pub.com',
          'betfair.', 'oddschecker.', 'oddsportal.', 'smarkets.', 'pinnacle.',
          'bet365.', 'williamhill.', 'ladbrokes.', 'paddypower.', 'skybet.',
          'betway.', 'unibet.', 'draftkings.', 'fanduel.', 'bovada.', 'betmgm.',
          'olbg.com', 'covers.com', 'vegasinsider.']
got = {}
for f in sorted(glob.glob('data/benchmarks/research/*.research.json')):
    name = os.path.basename(f)
    d = json.load(open(f, encoding='utf-8'))
    txt = json.dumps(d).lower()
    hits = sorted({b for b in banned if b in txt})
    bad_p = [k for k, v in d.items()
             if not isinstance(v.get('p'), (int, float)) or not (0 < v['p'] < 1)]
    missf = [k for k, v in d.items()
             if not v.get('reasoning_summary') or not v.get('strongest_opposing_case')
             or not v.get('base_rate') or len(v.get('key_sources') or []) < 2]
    for k in d:
        got.setdefault(str(k), []).append(name)
    print(f"{name:42s} n={len(d):3d} banned={hits or 'none'} bad_p={bad_p or 'none'} thin={missf[:3] or 'none'}")

missing = mkt - set(got)
dupes = {k: v for k, v in got.items() if len(v) > 1}
extra = set(got) - mkt
print('MISSING market ids:', len(missing), sorted(missing)[:10])
print('DUPED ids:', len(dupes), list(dupes.items())[:6])
print('EXTRA ids:', len(extra), sorted(extra)[:6])
