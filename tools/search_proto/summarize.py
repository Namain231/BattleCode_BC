"""Compact completed-game evidence summary; no replay parsing."""
import argparse,json,pathlib,math,statistics,hashlib

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('directory'); a=ap.parse_args()
    root=pathlib.Path(a.directory)
    fingerprint=hashlib.sha256((pathlib.Path(__file__).parent/'serve_search.py').read_bytes()).hexdigest()
    for mode in ('trivial','net','search','depth1','noqueen'):
        games=[json.loads(p.read_text()) for p in root.glob(mode+'_*.json') if not p.name.endswith('_summary.json')]
        games=[g for g in games if g.get('complete') and g.get('judge_exit')==0]
        if mode!='trivial':
            games=[g for g in games if g.get('queen_death_rounds_exact') and g.get('policy_sha256')==fingerprint]
        if not games: continue
        n=len(games); wins=sum(g['winner']==g['side'] for g in games); p=wins/n
        # Wilson95 interval avoids pretending zero wins means zero uncertainty.
        z=1.96; denom=1+z*z/n
        center=(p+z*z/(2*n))/denom; radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/denom
        ms=sum(g['turn_ms_mean']*g['turns'] for g in games)/sum(g['turns'] for g in games)
        permap={m:sum(g['winner']==g['side'] for g in games if g['map']==m) for m in sorted({g['map'] for g in games})}
        print(json.dumps(dict(mode=mode,wins=wins,games=n,SE=math.sqrt(p*(1-p)/n),Wilson95=[center-radius,center+radius],
                              turn_ms_mean=ms,wall_s=sum(g['wall_s'] for g in games),permap=permap,
                              queen_deaths={g['map']+'_'+g['side']:g['queen_death_rounds'] for g in games},
                              depth_histogram={str(d):sum(g.get('depth_histogram',{}).get(str(d),0) for g in games) for d in range(4)})))

if __name__=='__main__': main()
