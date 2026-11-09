"""Bounded hypotheses for SNES graphics; not identified UMK3 proprietary formats."""
from __future__ import annotations
from dataclasses import dataclass
from math import log2
FORMATS=('raw','rle_count_value','rle_value_count','packbits')
@dataclass
class Decode:
    data:bytes
    consumed:int
    complete:bool
    error:str|None=None

def decode_stream(data:bytes,codec:str,target_length:int,max_input:int=8192)->Decode:
    if codec not in FORMATS:raise ValueError('Codec hipotético desconhecido')
    if not 1<=target_length<=8192:raise ValueError('Comprimento de saída deve estar entre 1 e 8192')
    if not 1<=max_input<=65536:raise ValueError('max_input inválido')
    source=memoryview(data)[:max_input];out=bytearray();p=0
    if codec=='raw':
        output=bytes(source[:target_length])
        return Decode(output,len(output),len(output)==target_length)
    while len(out)<target_length:
        if p>=len(source):return Decode(bytes(out),p,False,'Fonte esgotada')
        if codec=='packbits':
            control=source[p];p+=1
            if control<=127:
                count=control+1
                if p+count>len(source):return Decode(bytes(out),p,False,'Literal truncado')
                if len(out)+count>target_length:return Decode(bytes(out),p,False,'Bloco ultrapassa saída solicitada')
                out.extend(source[p:p+count]);p+=count
            elif control>=129:
                count=257-control
                if p>=len(source):return Decode(bytes(out),p,False,'Repetição truncada')
                if len(out)+count>target_length:return Decode(bytes(out),p,False,'Bloco ultrapassa saída solicitada')
                out.extend([source[p]]*count);p+=1
        else:
            if p+2>len(source):return Decode(bytes(out),p,False,'Par RLE truncado')
            if codec=='rle_count_value':count,value=source[p],source[p+1]
            else:value,count=source[p],source[p+1]
            p+=2
            if count==0:return Decode(bytes(out),p,False,'Contagem zero: semântica não definida nesta hipótese')
            if len(out)+count>target_length:return Decode(bytes(out),p,False,'Bloco ultrapassa saída solicitada')
            out.extend([value]*count)
    return Decode(bytes(out),p,True)

def compare_pair(rom:bytes,target:bytes,rom_offset:int,target_offset:int,length:int,
                 codec:str='raw',max_input:int=8192,preview_limit:int=128)->dict:
    if not 0<=rom_offset<len(rom):raise ValueError('Offset ROM fora do arquivo')
    if not 0<=target_offset<len(target):raise ValueError('Offset alvo fora da captura')
    if not 1<=length<=8192 or target_offset+length>len(target):raise ValueError('Janela alvo inválida')
    if not 1<=preview_limit<=256:raise ValueError('Limite de prévia inválido')
    output=decode_stream(rom[rom_offset:rom_offset+max_input],codec,length,max_input)
    expected=target[target_offset:target_offset+length]
    prefix=0
    for a,b in zip(output.data,expected):
        if a!=b:break
        prefix+=1
    exact=output.complete and output.data==expected
    return {'codec':codec,'source_offset':rom_offset,'target_offset':target_offset,
        'target_length':length,'input_consumed':output.consumed,'output_length':len(output.data),
        'decode_complete':output.complete,'decode_error':output.error,
        'matching_prefix':prefix,'matching_positions':sum(a==b for a,b in zip(output.data,expected)),
        'exact_match':exact,'expected_preview':expected[:preview_limit].hex(' '),
        'output_preview':output.data[:preview_limit].hex(' '),
        'classification':'exact_match_for_one_window_only' if exact else 'unverified_hypothesis',
        'caution':'Mesmo correspondência exata isolada não identifica o codec usado pelo jogo.'}

def scan_hypotheses(rom:bytes,target:bytes,rom_start:int,rom_length:int,target_offset:int,
                    target_length:int,step:int=1,codecs:tuple[str,...]=('rle_count_value','rle_value_count','packbits'),
                    max_input:int=1024,max_results:int=20)->dict:
    if not 0<=rom_start<len(rom) or not 1<=rom_length<=65536 or rom_start+rom_length>len(rom):
        raise ValueError('Intervalo de ROM inválido (até 64 KiB por varredura)')
    if not 0<=target_offset<len(target) or not 1<=target_length<=2048 or target_offset+target_length>len(target):
        raise ValueError('Intervalo alvo inválido (até 2048 bytes)')
    if not 1<=step<=256:raise ValueError('Passo inválido')
    if not 2<=max_input<=4096:raise ValueError('Limite de fonte inválido')
    if not 1<=max_results<=100:raise ValueError('Limite de resultados inválido')
    if not codecs or len(codecs)>4 or any(c not in FORMATS for c in codecs):raise ValueError('Codec inválido')
    expected=target[target_offset:target_offset+target_length]
    candidates=[];checked=0;exact_count=0
    for at in range(rom_start,rom_start+rom_length,step):
        segment=rom[at:min(len(rom),at+max_input)]
        for codec in codecs:
            result=decode_stream(segment,codec,target_length,max_input);checked+=1
            prefix=0
            for a,b in zip(result.data,expected):
                if a!=b:break
                prefix+=1
            match=result.complete and result.data==expected
            if match:exact_count+=1
            if prefix>=4 or match:
                candidates.append({'rom_offset':at,'codec':codec,'prefix':prefix,
                    'complete':result.complete,'exact_match':match,'input_consumed':result.consumed})
    candidates.sort(key=lambda x:(-int(x['exact_match']),-x['prefix'],x['rom_offset'],x['codec']))
    return {'checked':checked,'matches_exact':exact_count,'results':candidates[:max_results],
        'results_truncated':len(candidates)>max_results,'target_offset':target_offset,
        'target_length':target_length,'scanned_bytes':rom_length,
        'note':'Estes são formatos experimentais genéricos; nenhuma correspondência prova o formato UMK3.'}

def byte_entropy(data:bytes)->float:
    if not data:return 0.0
    hist=[0]*256
    for b in data:hist[b]+=1
    n=len(data)
    return round(-sum((v/n)*log2(v/n) for v in hist if v),4)

def region_profile(rom:bytes,start:int,length:int,window:int=256)->dict:
    if not 0<=start<len(rom) or not 1<=length<=65536 or start+length>len(rom):raise ValueError('Faixa ROM inválida')
    if not 32<=window<=4096:raise ValueError('Janela de entropia inválida')
    rows=[]
    for at in range(start,start+length,window):
        raw=rom[at:min(start+length,at+window)]
        rows.append({'offset':at,'bytes':len(raw),'entropy':byte_entropy(raw),
            'unique_values':len(set(raw)),'zero_bytes':raw.count(0),'ff_bytes':raw.count(255)})
    return {'windows':rows,'notice':'Entropia não classifica sozinha um bloco como comprimido.'}
