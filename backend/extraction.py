"""Conservative read-only ROM-vs-VRAM investigation tools.

This module does NOT claim to decode UMK3's proprietary graphics compression.
Matches are exact byte-identical windows, and heuristic scores are never
labelled as decoded sprites. All offsets refer to headerless ROM bytes.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import math

BANK_SIZE = 0x10000


def raw_entropy(data: bytes) -> float:
    if not data:return 0.0
    counts=Counter(data)
    return -sum((n/len(data))*math.log2(n/len(data)) for n in counts.values())


def bank_inventory(data:bytes, *, base:int=0, bank_size:int=BANK_SIZE)->list[dict]:
    """Descriptive statistics, no free-space or compression assertions."""
    if bank_size<=0:raise ValueError('bank_size deve ser positivo')
    result=[]
    for start in range(0,len(data),bank_size):
        block=data[start:start+bank_size]
        zero=block.count(0); ff=block.count(255)
        longest=0; run=0; prev=-1
        for x in block:
            if x==prev:run+=1
            else:run=1;prev=x
            longest=max(longest,run)
        result.append({'bank':start//bank_size,'rom_offset':base+start,
                       'size':len(block),'entropy':round(raw_entropy(block),4),
                       'zero_percent':round(zero*100/len(block),2),
                       'ff_percent':round(ff*100/len(block),2),
                       'longest_same_byte_run':longest,
                       'unique_bytes':len(set(block))})
    return result


def search_exact(data:bytes,needle:bytes, *,start:int=0,end:int|None=None,max_hits:int=100)->list[int]:
    if not needle or len(needle)>4096:raise ValueError('Janela vazia ou maior que 4096 bytes')
    if max_hits<1 or max_hits>1000:raise ValueError('max_hits fora do intervalo')
    end=len(data) if end is None else end
    if not(0<=start<=end<=len(data)):raise ValueError('Intervalo inválido')
    hits=[];position=start
    while len(hits)<max_hits:
        position=data.find(needle,position,end)
        if position<0:break
        hits.append(position);position+=1
    return hits


def match_vram_windows(rom:bytes,vram:bytes,*,chunk_size:int=64,
                       vram_offset:int=0,vram_length:int=4096,
                       step:int|None=None,minimum_unique:int=12,
                       max_matches:int=150)->dict:
    """Search raw VRAM chunks in ROM; suppress low-complexity patterns.

    Non-matches do not rule out compressed/relocated/reformatted graphics.
    """
    if chunk_size not in (16,32,64,128,256,512):raise ValueError('Tamanho de bloco inválido')
    if step is None:step=chunk_size
    if not 1<=step<=chunk_size:raise ValueError('Passo inválido')
    if not(0<=vram_offset<len(vram)) or not(1<=vram_length<=65536):raise ValueError('Intervalo VRAM inválido')
    if not(1<=minimum_unique<=256):raise ValueError('Diversidade inválida')
    if not(1<=max_matches<=500):raise ValueError('Limite inválido')
    finish=min(len(vram),vram_offset+vram_length)
    stats=Counter();matches=[]
    for pos in range(vram_offset,finish-chunk_size+1,step):
        window=vram[pos:pos+chunk_size]
        stats['scanned']+=1
        if len(set(window))<minimum_unique:
            stats['skipped_low_diversity']+=1;continue
        stats['eligible']+=1
        # Return a bounded number of exact matches per VRAM chunk; excess is flagged.
        hits=search_exact(rom,window,max_hits=4)
        if hits:
            stats['matched_windows']+=1
            for hit in hits:
                if len(matches)<max_matches:
                    matches.append({'vram_offset':pos,'rom_offset':hit,
                                    'length':chunk_size,'unique_bytes':len(set(window)),
                                    'entropy':round(raw_entropy(window),3),
                                    'sha256':sha256(window).hexdigest()[:16]})
                else:stats['truncated']+=1
    return {'parameters':{'chunk_size':chunk_size,'vram_offset':vram_offset,
                          'vram_length':vram_length,'step':step,
                          'minimum_unique':minimum_unique},
            'statistics':dict(stats),'matches':matches,
            'note':'Correspondências exatas de bytes. Não provam origem gráfica nem descompressão.'}


def run_candidates(data:bytes,*,start:int=0,length:int=65536,min_run:int=16,
                   limit:int=100)->list[dict]:
    """Display long repeated-byte sequences for compression/free-space investigation."""
    if not(0<=start<len(data)) or not (1<=length<=len(data)-start):raise ValueError('Intervalo inválido')
    if not(4<=min_run<=65536) or not(1<=limit<=500):raise ValueError('Parâmetros inválidos')
    results=[];end=start+length;i=start
    while i<end:
        j=i+1
        while j<end and data[j]==data[i]:j+=1
        if j-i>=min_run:
            results.append({'rom_offset':i,'length':j-i,'byte':f'{data[i]:02X}'})
        i=j
    return sorted(results,key=lambda x:(-x['length'],x['rom_offset']))[:limit]


def preview_raw(rom:bytes,*,offset:int,bpp:int,columns:int,rows:int,palette:int,
                scale:int=2,cgram:bytes|None=None):
    from .graphics import tile_sheet
    if not 0<=offset<len(rom):raise ValueError('Offset fora da ROM')
    if not 0<=rows<=32 or not 0<=columns<=32 or rows*columns==0 or rows*columns>512:
        raise ValueError('Grade inválida')
    if bpp not in (2,4,8):raise ValueError('bpp permitido: 2, 4 ou 8')
    if offset%(bpp*8):raise ValueError('Offset desalinhado ao tamanho do tile')
    if offset+rows*columns*bpp*8>len(rom):raise ValueError('Grade excede final da ROM')
    return tile_sheet(rom,cgram,offset=offset,bpp=bpp,columns=columns,rows=rows,
                      palette=palette,scale=scale)
