"""Read completed self-play episodes; never modify the source run.

Requires bridge_harness.core on PYTHONPATH. Positions use actual dealt hands,
not a reconstruction of the bot's sampled worlds. Deduplicate original deals
before selecting families or splitting related positions.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
from bridge_harness.core import Board, Game, card, SEATS
from pipeline import split_families


def deal_identity(board):
    # Group hand permutations and different contracts on the same deal.
    hands=sorted(tuple(sorted(h)) for h in board.hands)
    return hashlib.sha256(json.dumps(hands,separators=(',',':')).encode()).hexdigest()


def extract(episode, plies):
    if episode.get('status')!='ok':raise ValueError('Unfinished episode')
    board=Board.from_dict(episode['board'])
    if board.contract is None:return []
    table=episode['focal']['tables'][0]
    if table.get('status')!='ok':raise ValueError('Unfinished table')
    game=Game(board); rows=[];family=deal_identity(board)
    for ply,action in enumerate(table['actions']):
        if SEATS[game.actor]!=action['seat']:raise ValueError('Recorded actor mismatch')
        if ply in plies:
            key=[0]*26
            for seat,hand in enumerate(game.hands):
                for c in hand:key[4*seat+c//13]|=1<<(c%13)
            key[17:21]=[game.leader,len(game.trick),board.contract.trump,1]
            for i,(_,c) in enumerate(game.trick):key[21+i]=16*(c//13)+c%13+2
            key[24]=sum(map(len,game.hands))-4
            rows.append(dict(family=family,source_family=episode.get('family'),ply=ply,key=key))
        game.play(card(action['card']))
        if ply>=max(plies):break
    if len(rows)!=len(plies):raise ValueError('Insufficient recorded play')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('episodes');p.add_argument('output');p.add_argument('--deals',type=int,default=1500)
    p.add_argument('--exclude-source',help='Original pilot roots.json')
    args=p.parse_args();out=Path(args.output);out.mkdir(parents=True,exist_ok=True)
    excluded=set()
    if args.exclude_source:
        original=json.loads(Path(args.exclude_source).read_text())
        excluded={r['family'] for r in original}
    families={};rejected=Counter();duplicates=0
    paths=sorted(Path(args.episodes).glob('*.json.gz'))
    for path in paths:
        try:
            raw=path.read_bytes();episode=json.loads(gzip.decompress(raw))
            if episode.get('family') in excluded:
                rejected['pilot_family']+=1;continue
            # Two large roots per independent deal; after one and three tricks.
            rows=extract(episode,[4,12])
            if not rows:rejected['passed_out']+=1;continue
            family=rows[0]['family']
            if family in families:duplicates+=1;continue
            families[family]=dict(rows=rows,source=str(path),sha256=hashlib.sha256(raw).hexdigest())
        except (ValueError,KeyError,IndexError,EOFError) as e:
            rejected[type(e).__name__]+=1
    selected=sorted(families,key=lambda f:hashlib.sha256(('dds-scale-v1:'+f).encode()).digest())[:args.deals]
    if len(selected)<args.deals:raise ValueError(f'Only {len(selected)} independent playable deals')
    splits=split_families(selected);rows=[]
    for family in selected:
        for row in families[family]['rows']:
            rows.append(dict(row,root=len(rows),split=splits[family]))
    def lines(rs):return ''.join(' '.join(map(str,[r['family'],r['root'],*r['key']]))+'\n' for r in rs)
    (out/'all.roots').write_text(lines(rows))
    for s in ['train','validation','test']:(out/(s+'.roots')).write_text(lines(r for r in rows if r['split']==s))
    (out/'roots.json').write_text(json.dumps(rows))
    manifest=dict(schema='dds-selfplay-scale-v1',source_kind='actual_selfplay_hands',source_files=len(paths),
        available_independent_deals=len(families),selected_deals=len(selected),roots=len(rows),
        split_deals=dict(Counter(splits.values())),strains=dict(Counter(r['key'][19] for r in rows)),
        duplicate_deals=duplicates,rejected=dict(rejected),family_splits=splits,
        sources={f:{k:v for k,v in families[f].items() if k!='rows'} for f in selected})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2))
    print(json.dumps({k:v for k,v in manifest.items() if k not in ['sources','family_splits']},indent=2))


if __name__=='__main__':main()
