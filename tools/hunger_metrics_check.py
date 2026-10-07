"""Small synthetic replay fixture: sprint crossings, prior-turn retraces, meal/streak."""
import sys
sys.dont_write_bytecode=True
import json
from pathlib import Path
import hunger_metrics as hm

def main():
    events=[dict(kind='roundStart',round=0),dict(kind='turnStart',id=2),
        dict(kind='tileChange',tile=(6,5),pearl=True),dict(kind='tileChange',tile=(6,5),pearl=False)]
    old=(5,5)
    for head in [(6,5),(6,4),(5,4),(5,5)]:
        events.append(dict(kind='dragonUpdate',id=2,head=head,tail=old));old=head
    events.extend([dict(kind='roundStart',round=1),dict(kind='turnStart',id=2),
        dict(kind='dragonUpdate',id=2,head=(6,5),tail=(5,5))])
    rep=dict(map='MAP 16 16\nDRAGON 0 2 2 2 1 2\nDRAGON 1 2 12 12 13 12\nDRAGON 0 2 5 5 4 5\n',events=events,result={'winner':0})
    hm.decode_lite=lambda *args:rep
    path=Path('F:/BC_hunger_20261008/metric_fixture_1_A.replay')
    path.parent.mkdir(parents=True,exist_ok=True)
    cpu=Path(str(path)+'.cpu.json');cpu.write_text(json.dumps({'A':12,'B':11}),encoding='utf-8')
    r=hm.measure(path)
    assert (r['turns'],r['moves'],r['retrace'],r['eats'])==(2,5,1,1),r
    assert r['unique']==[4] and r['streak']==[1],r
    cpu.unlink()
    print('PASS: five sprint steps, four unique cells, only preceding-turn retrace counted, meal + one-turn streak attributed.')

if __name__=='__main__':main()
