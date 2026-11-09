"""Conservative evidence-aware xref and CFG analysis; no speculative function naming."""
from __future__ import annotations
from collections import deque
from .core import CpuState, decode_one, cpu_to_file, file_to_cpu, next_instruction_offset


def build_xrefs(rom,roots,cdl=None,max_instructions=60000,max_entries=250000):
    """Follow direct static control transfers; indirect transfers and unknown widths remain unresolved.

    Calls are recorded and followed while their return-site fallthrough is explored.
    A conditional branch contributes both successors. Byte-level visited state prevents runaway.
    """
    pending=deque((int(root),CpuState(False,True,True)) for root in roots)
    seen=set(); refs=[]; ambiguous=[]; count=0
    while pending and count<max_instructions and len(refs)<max_entries:
        start,state=pending.popleft()
        if not 0<=start<len(rom.data):continue
        current=start
        for _ in range(2048):
            key=(current,state.e,state.m,state.x)
            if key in seen:break
            seen.add(key)
            ins=decode_one(rom.data,current,state,rom.mapping)
            if not ins:break
            count+=1
            if ins['size'] is None:
                ambiguous.append({'offset':current,'reason':'M/X unknown'});break
            nxt=next_instruction_offset(current,ins['size'],rom.mapping)
            state=CpuState(**ins['state_after'])
            if ins['target'] is not None and ins['flow'] in ('branch','jump','call'):
                dest=cpu_to_file(ins['target'],rom.mapping)
                refs.append({'from_offset':current,'from_cpu':ins['cpu'],'to_cpu':ins['target'], 'to_offset':dest if dest is not None and dest<len(rom.data) else None, 'kind':ins['flow'],'mnemonic':ins['mnemonic'], 'cdl_code':cdl.status(current)['code'] if cdl else None})
                if dest is not None and 0<=dest<len(rom.data):pending.append((dest,CpuState(state.e,state.m,state.x)))
            if ins['flow'] in ('branch','call'):
                if nxt is not None:pending.append((nxt,CpuState(state.e,state.m,state.x)))
                break
            if ins['flow'] in ('jump','stop','unknown'):break
            if nxt is None:break
            current=nxt
            if count>=max_instructions:break
    return {'roots':list(roots),'instructions':count,'references':refs,'ambiguous':ambiguous[:500], 'truncated':bool(pending) or count>=max_instructions, 'limitations':'Direct static transfers only; indirect jumps, call targets under uncertain PBR and unknown CPU M/X states require debugging.'}


def seed_roots(rom):
    roots=[]
    if rom.header_offset is not None:
        h=rom.data[rom.header_offset:rom.header_offset+64]
        for label,ofs in [('native_cop',0x24),('native_brk',0x26),('native_abort',0x28),('native_nmi',0x2a),('native_irq',0x2e),('emu_cop',0x34),('emu_abort',0x38),('emu_nmi',0x3a),('reset',0x3c),('emu_irq',0x3e)]:
            vector=int.from_bytes(h[ofs:ofs+2],'little')
            if vector<0x8000:continue
            src=cpu_to_file(0x008000|vector,rom.mapping)
            if src is not None and src<len(rom.data):roots.append({'name':label,'cpu':0x008000|vector,'offset':src})
    return roots


def query_xrefs(analysis,target_offset=None,source_offset=None,limit=250):
    refs=analysis['references']
    if target_offset is not None:refs=[r for r in refs if r['to_offset']==target_offset]
    if source_offset is not None:refs=[r for r in refs if r['from_offset']==source_offset]
    return refs[:limit]
