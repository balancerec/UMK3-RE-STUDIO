"""v0.9 — Correlate explicitly observed DMA writes with PC, ROM/CDL and sources.

No inference of a compression algorithm or emulation of DMA timing. CPU PC provenance
may be approximate in captures; static opcode context is not a bus-write proof.
"""
from __future__ import annotations
from .dma_trace import analyze_trace, _read_events, _hw, _memory_source
from .core import cpu_to_file, disassemble

DMA_REGIONS = ((0x4300,0x437f),(0x420b,0x420b),(0x2115,0x2119))

def _pc_context(pc, rom, cdl):
    if pc is None:return {'pc':None,'rom_offset':None,'instruction':None,'cdl':None,'note':'PC ausente'}
    if rom is None:return {'pc':f'${pc:06X}','rom_offset':None,'instruction':None,'cdl':None,'note':'ROM não importada'}
    offset=cpu_to_file(pc,rom.mapping)
    if offset is None or not 0<=offset<len(rom.data):
        return {'pc':f'${pc:06X}','rom_offset':None,'instruction':None,'cdl':None,'note':'PC não mapeável como ROM'}
    inst=disassemble(rom,offset,count=1,e=False,m=True,x=True,cdl=cdl)
    first=inst[0] if inst else None
    return {'pc':f'${pc:06X}','rom_offset':offset,'instruction':
            {'mnemonic':first['mnemonic'],'operand':first['operand'],'bytes':first['bytes']} if first else None,
            'cdl':cdl.status(offset) if cdl else None,
            'note':'Decodificação local com E=0/M=1/X=1 hipotéticos; valide modo real e PC em breakpoint.'}

def correlate_trace(raw,*,rom=None,cdl=None,wram=None,vram=None,max_results=100):
    if not 1<=max_results<=500:raise ValueError('max_results deve estar entre 1 e 500')
    dma=analyze_trace(raw,rom=rom.data if rom else None,wram=wram,vram=vram,max_results=max_results)
    events,meta=_read_events(raw)
    trigger_events={ev['index']:ev for ev in events if _hw(ev['address'])==0x420b}
    out=[]
    for t in dma['transfers']:
        trigger=trigger_events.get(t['trigger_index'])
        pc=trigger['pc'] if trigger else None
        context=_pc_context(pc,rom,cdl)
        src=t['source'];src_kind='unknown'
        if src is not None:
            bank=src>>16
            if bank in (0x7e,0x7f):src_kind='WRAM'
            elif rom and cpu_to_file(src,rom.mapping) is not None:src_kind='ROM_candidate'
            else:src_kind='other_or_unmapped'
        producer_events=[]
        if src_kind=='WRAM' and src is not None and t['size'] is not None:
            # Trace is restricted to DMA/PPU writes in the companion Lua capture.
            # Only explicit captured WRAM writes can establish producers.
            size=min(t['size'],0x10000)
            for ev in events:
                if ev['index']>=t['trigger_index']:break
                if src<=ev['address']<src+size and (ev['address']>>16) in (0x7e,0x7f):
                    producer_events.append({'event':ev['index'],'address':f"${ev['address']:06X}",'pc':f"${ev['pc']:06X}" if ev['pc'] is not None else None})
            producer_events=producer_events[-8:]
        issues=[]
        if t['registers_missing']:issues.append('Configuração DMA incompleta')
        if t['source'] is None:issues.append('Origem desconhecida')
        if context['rom_offset'] is None:issues.append('PC sem correspondência na ROM')
        if not producer_events and src_kind=='WRAM':issues.append('Rotina que preenche WRAM não identificada no trace')
        if t['verification']=='snapshot_mismatch':issues.append('Snapshot de VRAM não coincide; sincronização/configuração não comprovada')
        if t['verification']=='snapshot_exact_match':issues.append('Coincidência de snapshot não comprova temporalidade nem codec')
        if not t['vram_address_inferred']:issues.append('Endereço efetivo de destino VRAM não validado')
        out.append({'transfer':t,'trigger':context,'source_kind':src_kind,
                    'source_producers_observed':producer_events,
                    'warnings':issues,'classification':'observed_trigger_inferred_transfer'})
    return {'meta':meta,'dma_triggers':dma['dma_triggers'],'transfers':out,
            'truncated':dma['truncated'],
            'evidence_policy':{'observed':'Escrita de registrador declarada no log de eventos',
                               'inferred':'Configuração DMA reconstruída a partir de escritas observadas',
                               'unverified':'Algoritmo de descompressão, buffer produtor e destino temporal ainda não confirmados'},
            'next_steps':['Capturar valores de PC e registradores no ponto de escrita em $420B.',
                          'Para origem WRAM, rastrear quem escreve no buffer antes do DMA.',
                          'Salvar snapshots sincronizados e registrar VMAIN/OBSEL/VMADD.',
                          'Documentar pares ROM de entrada / WRAM descomprimida antes de implementar codec.']}
