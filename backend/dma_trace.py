"""Import register-write event logs and infer possible SNES DMA transfers.

Evidence levels:
  observed_write: a CSV/JSONL record explicitly states address+written value
  inferred_transfer: derived from previous register writes + MDMAEN write
  verified_bytes: source and VRAM snapshot bytes match at inferred destination

No CPU trace line is considered a bus write without an explicit write event.
"""
from __future__ import annotations
import csv, io, json, re
from dataclasses import dataclass

MAX_EVENTS=250_000
MAX_LINE=4096
DMA_MODE_OFFSETS={0:(0,),1:(0,1),2:(0,0),3:(0,0,1,1),4:(0,1,2,3),5:(0,1,0,1),6:(0,0),7:(0,0,1,1)}
RECORD_COLUMNS=('cycle','pc','address','value','operation')

def number(value, *, required=False):
    if value is None or str(value).strip()=='':
        if required:raise ValueError('Campo numérico obrigatório')
        return None
    s=str(value).strip().replace('_','').replace('$','').replace(':','')
    if s.lower().startswith('0x'):return int(s,16)
    if s.lower().startswith('0d'):return int(s[2:],10)
    # Addresses, register values, and PC are hexadecimal by default.
    return int(s,16)

def _read_events(raw:bytes,limit=MAX_EVENTS):
    if len(raw)>16*1024*1024:raise ValueError('Trace excede 16 MiB')
    try:t=raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:raise ValueError('Trace deve ser UTF-8') from e
    if any(len(line)>MAX_LINE for line in t.splitlines()):raise ValueError('Linha maior que 4096 caracteres')
    if not t.strip():raise ValueError('Trace vazio')
    lines=[x for x in t.splitlines() if x.strip() and not x.lstrip().startswith('#')]
    if not lines:raise ValueError('Trace vazio')
    if lines[0].lstrip().startswith('{'):
        rows=[]
        for line in lines:
            try:record=json.loads(line)
            except (json.JSONDecodeError,ValueError) as e:raise ValueError('Linha JSONL inválida') from e
            if not isinstance(record,dict):raise ValueError('Cada evento deve ser objeto JSON')
            rows.append(record)
    elif ',' in lines[0] and 'address' in lines[0].lower():
        rows=list(csv.DictReader(io.StringIO('\n'.join(lines))))
    else:
        # Mesen CPU trace logs vary by version; do not falsely interpret a
        # mnemonic "STA $420B" as an actual observed bus transaction.
        count=len(lines)
        return [], {'format':'cpu_trace_text','lines':count,'observed_writes':0,
                    'warning':'Log textual de instruções não demonstra escritas efetivas. Exporte eventos bus-write em CSV/JSONL com address, value e operation=write.'}
    if len(rows)>limit:raise ValueError(f'Número de eventos excede {limit}')
    events=[];skipped=0
    for n,row in enumerate(rows,1):
        row={str(k).lower().strip():v for k,v in row.items() if k is not None}
        op=str(row.get('operation',row.get('type',row.get('access','')))).lower().strip()
        if op not in ('write','w','store','cpu_write','bus_write'):
            skipped+=1;continue
        try:
            addr=number(row.get('address',row.get('addr')),required=True)
            val=number(row.get('value',row.get('data')),required=True)
            pc=number(row.get('pc'))
            cycle=number(row.get('cycle'))
        except ValueError as e:raise ValueError(f'Evento {n}: {e}') from e
        if not 0<=addr<=0xffffff or not 0<=val<=255:raise ValueError(f'Evento {n}: endereço ou byte inválido')
        if pc is not None and not 0<=pc<=0xffffff:raise ValueError(f'Evento {n}: PC inválido')
        events.append({'index':n,'address':addr,'value':val,'pc':pc,'cycle':cycle})
    return events,{'format':'jsonl' if lines[0].lstrip().startswith('{') else 'csv','lines':len(rows),
                   'observed_writes':len(events),'skipped_non_writes':skipped}

def _hw(addr):
    bank=(addr>>16)&0xff;low=addr&0xffff
    # $00-$3F and $80-$BF map low I/O registers; $7E:420B is WRAM, not I/O.
    return low if bank in (*range(0x00,0x40),*range(0x80,0xc0)) and 0x2000<=low<=0x5fff else None

def _source(a1b,a1t):
    if a1b is None or a1t is None:return None
    return (a1b<<16)|a1t

def _memory_source(src,size,rom=None,wram=None):
    if src is None or size<=0:return None
    bank=src>>16;off=src&0xffff
    if bank in (0x7e,0x7f) and wram is not None and off+size<=65536 and len(wram)==131072:
        pos=(bank-0x7e)*65536+off
        return wram[pos:pos+size]
    if rom is not None:
        from .core import cpu_to_file
        pos=cpu_to_file(src,'exhirom' if len(rom)>0x400000 else 'hirom')
        if pos is not None and 0<=pos and pos+size<=len(rom):return rom[pos:pos+size]
    return None

def analyze_trace(raw:bytes,*,rom=None,wram=None,vram=None,max_results=100):
    if not 1<=max_results<=1000:raise ValueError('max_results deve estar entre 1 e 1000')
    events,meta=_read_events(raw)
    # 8 DMA channels; reset and gaps are unknown if capture started mid-session.
    channels=[{} for _ in range(8)]
    ppu={};transfers=[];register_writes=0;dma_triggers=0
    for event in events:
        reg=_hw(event['address']);value=event['value']
        if reg is None:continue
        if 0x4300<=reg<=0x437f:
            ch=(reg-0x4300)//16;key=(reg-0x4300)%16
            channels[ch][key]=value;register_writes+=1
        elif reg in (0x2115,0x2116,0x2117,0x2101,0x2105,0x2118,0x2119):
            ppu[reg]=value;register_writes+=1
        elif reg==0x420b:
            register_writes+=1;dma_triggers+=1
            for ch in range(8):
                if not (value&(1<<ch)):continue
                r=channels[ch];missing=[k for k in (0,1,2,3,4,5,6) if k not in r]
                source=_source(r.get(4), (r.get(3,0)<<8)|r.get(2,0) if 2 in r and 3 in r else None)
                count=((r[6]<<8)|r[5]) if 5 in r and 6 in r else None
                if count==0:count=65536
                dmap=r.get(0);bbad=r.get(1)
                mode=(dmap&7) if dmap is not None else None
                direction=(dmap>>7)&1 if dmap is not None else None
                fixed=bool(dmap&8) if dmap is not None else None
                decrement=bool(dmap&16) if dmap is not None else None
                vaddr=(ppu.get(0x2116,0)|ppu.get(0x2117,0)<<8)*2 if 0x2116 in ppu and 0x2117 in ppu else None
                # Only direct 1-register/2-register VRAM DMA, simplest mode 1.
                # Full PPU VMAIN remapping and multiple DMA writes require emulation.
                inferred_dest=(bbad==0x18 and mode==1 and direction==0 and vaddr is not None and ppu.get(0x2115)==0x80)
                verification='not_checked';match_bytes=None
                if inferred_dest and count is not None and count<=4096 and vram is not None and vaddr+count<=len(vram) and not fixed and not decrement:
                    srcbytes=_memory_source(source,count,rom,wram)
                    if srcbytes is not None:
                        match_bytes=(srcbytes==vram[vaddr:vaddr+count]);verification='snapshot_exact_match' if match_bytes else 'snapshot_mismatch'
                if len(transfers)<max_results:
                    transfers.append({'trigger_index':event['index'],'trigger_pc':event['pc'],'channel':ch,
                                      'source':source,'source_hex':f'${source:06X}' if source is not None else None,
                                      'size':count,'bbad':bbad,'mode':mode,'direction':'B_to_A' if direction else 'A_to_B' if direction is not None else None,
                                      'fixed':fixed,'decrement':decrement,'vram_byte_address':vaddr if bbad==0x18 else None,
                                      'vram_address_inferred':bool(inferred_dest),'registers_missing':missing,
                                      'evidence':'inferred_transfer_from_observed_register_writes',
                                      'verification':verification,'match_bytes':match_bytes})
    return {'meta':meta,'register_writes':register_writes,'dma_triggers':dma_triggers,
            'transfers':transfers,'truncated':sum((event['value']&255).bit_count() for event in events if _hw(event['address'])==0x420b)>len(transfers),
            'notice':'Somente eventos explícitos de escrita são observados; transferências são inferidas. Comparação com VRAM exige captura sincronizada e configuração VMAIN apropriada. Não há descompressão inferida.'}
