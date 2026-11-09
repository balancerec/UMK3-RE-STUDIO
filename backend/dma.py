"""Static DMA register references and WRAM/VRAM staging checks.

This is a *candidate* scanner: bytes resembling opcodes may be ordinary data.
The CDL code bit increases confidence but is neither execution trace nor proof
that this particular instruction is on the correct instruction boundary.
"""
from __future__ import annotations
from collections import Counter
from .core import file_to_cpu
from .extraction import match_vram_windows

DMA_REGISTERS = {0x420B:'MDMAEN',0x420C:'HDMAEN',0x2115:'VMAIN',
                 0x2116:'VMADDL',0x2117:'VMADDH',0x2118:'VMDATAL',
                 0x2119:'VMDATAH',0x2121:'CGADD',0x2122:'CGDATA'}
# 65C816 absolute store instructions; effective register address depends on DBR.
ABS_WRITES={0x8D:'STA abs',0x8E:'STX abs',0x8C:'STY abs',0x9C:'STZ abs'}
# Absolute long accesses specify full 24-bit destination.
LONG_WRITES={0x8F:'STA long'}

def scan_register_writes(rom:bytes, cdl=None, *,start:int=0,length:int|None=None,
                         code_only:bool=False,limit:int=250)->dict:
    if not 0<=start<len(rom):raise ValueError('Início fora da ROM')
    if length is None:length=len(rom)-start
    if not 1<=length<=len(rom)-start:raise ValueError('Comprimento inválido')
    if not 1<=limit<=5000:raise ValueError('Limite inválido')
    results=[]; totals=Counter(); scanned=0; end=start+length
    for i in range(start,max(start,end-2)):
        op=rom[i]
        if op in ABS_WRITES and i+3<=end:
            reg=rom[i+1]|(rom[i+2]<<8)
            if reg not in DMA_REGISTERS:continue
            mode=ABS_WRITES[op];basis='absolute (DBR não conhecido)';width=3
        elif op in LONG_WRITES and i+4<=end:
            reg=rom[i+1]|(rom[i+2]<<8)|(rom[i+3]<<16)
            if reg>>16 != 0 or (reg&0xffff) not in DMA_REGISTERS:continue
            reg &= 0xffff;mode=LONG_WRITES[op];basis='absolute long ($00 bank explicit)';width=4
        else:continue
        observed=bool(cdl and i<len(cdl.flags) and (cdl.flags[i]&1))
        if code_only and not observed:continue
        totals[DMA_REGISTERS[reg]]+=1;scanned+=1
        if len(results)<limit:
            results.append({'rom_offset':i,'cpu':file_to_cpu(i,'exhirom' if len(rom)>0x400000 else 'hirom'),
                            'register':f'${reg:04X}','name':DMA_REGISTERS[reg],
                            'instruction':mode,'bytes':rom[i:i+width].hex(' ').upper(),
                            'cdl_code_bit':observed,'addressing':basis,
                            'confidence':'candidato com CDL' if observed else 'candidato por assinatura'})
    return {'candidates':results,'counts':dict(totals),'total':scanned,
            'truncated':scanned>len(results),'code_only':code_only,
            'notice':'Não é trace DMA. Stores absolutos exigem DBR correto; assinaturas dentro de dados são falsos positivos possíveis. Confirmar PC e registradores no Mesen.'}

def match_staging(wram:bytes,vram:bytes,*,chunk_size:int=32,vram_offset:int=0,
                  vram_length:int=4096,minimum_unique:int=12,max_matches:int=100):
    if len(wram)!=0x20000:raise ValueError('WRAM deve ter 128 KiB')
    if len(vram)!=0x10000:raise ValueError('VRAM deve ter 64 KiB')
    matches=match_vram_windows(wram,vram,chunk_size=chunk_size,vram_offset=vram_offset,
                               vram_length=vram_length,step=chunk_size,
                               minimum_unique=minimum_unique,max_matches=max_matches)
    for hit in matches['matches']:
        offset=hit.pop('rom_offset')
        hit['wram_offset']=offset
        hit['wram_address']=f'${0x7e+(offset>>16):02X}:{offset&0xffff:04X}'
    matches['note']='Comparações exatas WRAM→VRAM do mesmo instante. Não confirmam DMA, origem ROM ou codec de compressão.'
    return matches


def dma_observation_plan():
    return {'steps':[
        'No Mesen 2, faça uma captura ao carregar a tela de seleção e registre o momento do jogo.',
        'Inspecione as escritas em $420B (MDMAEN), e as configurações $4300–$437F dos oito canais.',
        'Registre PC, DBR, A/X/Y, endereço de origem A1B:A1T, BBAD, DMAP, tamanho DAS e destino PPU.',
        'Para VRAM, observe $2115–$2119; registre também OBSEL $2101 e BGMODE $2105.',
        'Capture WRAM, VRAM, CGRAM e OAM no MESMO frame e anote os valores dos registradores.',
        'Compare dados de origem e destino e teste codecs somente com pares de entrada/saída identificados.'
    ],'registers':{'DMA enable':'$420B','DMA channels':'$4300–$437F','VRAM':'$2115–$2119','OBSEL':'$2101','BGMODE':'$2105'}}
