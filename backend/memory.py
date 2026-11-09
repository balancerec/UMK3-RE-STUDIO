"""Non-destructive SNES WRAM snapshot comparison, no semantic guesses."""
from collections import Counter
from itertools import combinations
from pathlib import Path

WRAM_SIZE=0x20000
MAPPED_SIZE=0x1000000
# Full CPU address-space dumps: physical WRAM banks $7E/$7F
WRAM_OFFSET=0x7e0000
CANDIDATES=(0x36d0,0x52c8,0x1c59)

def extract_wram(raw:bytes)->bytes:
    if len(raw)==WRAM_SIZE:return raw
    if len(raw)==MAPPED_SIZE:return raw[WRAM_OFFSET:WRAM_OFFSET+WRAM_SIZE]
    raise ValueError('Esperado dump WRAM de 131072 bytes ou SnesMemory de 16777216 bytes')

def read_value(data:bytes,offset:int,width:int=1)->int:
    if width not in (1,2,3,4) or offset<0 or offset+width>len(data):
        raise ValueError('Offset/width inválido')
    return int.from_bytes(data[offset:offset+width],'little')

def pair_compare(left:bytes,right:bytes,offset:int=0,length:int=0x20000,limit:int=500,width:int=1):
    if len(left)!=WRAM_SIZE or len(right)!=WRAM_SIZE:raise ValueError('WRAM incorreta')
    if width not in (1,2,3,4) or offset<0 or length<1 or offset+length>WRAM_SIZE:
        raise ValueError('Intervalo inválido')
    changed=sum(a!=b for a,b in zip(left[offset:offset+length],right[offset:offset+length]))
    entries=[]; end=offset+length-width+1
    for i in range(offset,end,width):
        a=read_value(left,i,width);b=read_value(right,i,width)
        if a!=b and len(entries)<limit:
            entries.append({'offset':i,'address':f'7E:{i:04X}' if i<65536 else f'7F:{i-65536:04X}', 'left':a,'right':b,'left_hex':f'{a:0{2*width}X}','right_hex':f'{b:0{2*width}X}'})
    pages=[{'page':p,'address':f'7E:{p*256:04X}' if p<256 else f'7F:{(p-256)*256:04X}', 'different':sum(a!=b for a,b in zip(left[p*256:(p+1)*256],right[p*256:(p+1)*256]))} for p in range(offset//256,(offset+length-1)//256+1)]
    return {'different_bytes':changed,'total_bytes':length,'different_percent':round(changed/length*100,3),'entries':entries,'truncated':changed>len(entries) if width==1 else None,'pages':pages}

def candidate_report(snapshots:list[dict],max_results:int=500):
    """Only report raw address patterns. IDs are a *labelled comparison*, not proof."""
    if len(snapshots)<2:raise ValueError('Duas capturas são necessárias')
    if any(len(s['data'])!=WRAM_SIZE for s in snapshots):raise ValueError('WRAM inválida')
    items=[]
    distinct_labels=len({s['character'] for s in snapshots if s.get('character')})
    for ofs in range(WRAM_SIZE):
        vals=[s['data'][ofs] for s in snapshots]
        if len(set(vals))<2:continue
        groups={}
        for s,v in zip(snapshots,vals):
            label=s.get('character','').strip().lower()
            if label:groups.setdefault(label,set()).add(v)
        stable=bool(groups) and all(len(v)==1 for v in groups.values())
        discriminating=stable and len({next(iter(v)) for v in groups.values()})==len(groups)
        if not discriminating and ofs not in CANDIDATES:continue
        expected=[s.get('expected_id') for s in snapshots]
        comparable=[i for i,e in enumerate(expected) if e is not None]
        matches=sum(vals[i]==expected[i] for i in comparable)
        items.append({'offset':ofs,'address':f'7E:{ofs:04X}' if ofs<65536 else f'7F:{ofs-65536:04X}', 'values':[f'{v:02X}' for v in vals], 'distinct':len(set(vals)),'stable_per_character':stable,'separates_characters':discriminating,'matches_expected':matches,'expected_count':len(comparable),'known_candidate':ofs in CANDIDATES})
    items.sort(key=lambda x:(not x['known_candidate'],-x['matches_expected'],not x['separates_characters'],-x['distinct'],x['offset']))
    return {'snapshots':[{'id':s['id'],'character':s.get('character'),'expected_id':s.get('expected_id'),'filename':s.get('filename')} for s in snapshots], 'distinct_characters':distinct_labels,'count':len(items),'results':items[:max_results],'truncated':len(items)>max_results, 'warning':'Coincidência de bytes não comprova função. Testar escrita via breakpoint e repetir capturas.'}

def breakpoint_plan(addresses:list[int]):
    out=[]
    for ofs in addresses:
        if not 0<=ofs<WRAM_SIZE:raise ValueError('Endereço fora da WRAM')
        addr=f'7E:{ofs:04X}' if ofs<65536 else f'7F:{ofs-65536:04X}'
        out.append({'offset':ofs,'address':addr,'access':'write','size':1,'instructions':'Pausar no Memory Viewer/Debugger, configurar breakpoint de escrita, alternar personagem e registrar PC, opcode, A/X/Y, E/M/X e valor gravado.'})
    return out
