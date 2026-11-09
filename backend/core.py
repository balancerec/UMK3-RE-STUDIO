"""UMK3 RE Studio: read-only SNES ROM analysis, no copyrighted game data bundled."""
from __future__ import annotations
import hashlib, zlib, struct, math, json
from dataclasses import dataclass
from pathlib import Path

BANK=65536

def cpu_to_file(address:int, mapping='exhirom', header=0):
    """CPU bus address to headered file offset; None if not ROM (or not backed)."""
    if not 0<=address<=0xffffff: return None
    b=(address>>16)&255; a=address&65535
    if mapping=='lorom':
        if a<0x8000 or b in (0x7e,0x7f):return None
        return (((b&0x7f)<<15)|(a&0x7fff))+header
    if b in (0x7e,0x7f):return None
    if (b&0x7f)<0x40 and a<0x8000:return None
    if mapping=='hirom':
        return (((b&0x3f)<<16)|a)+header
    if mapping=='exhirom':
        # ExHiROM: 40-7D => low 4MB; C0-FF => low 4MB mirror
        # 00-3F upper halves and 80-BF upper halves => upper 4MB.
        if 0x40<=b<=0x7d or 0xc0<=b<=0xff:
            return (((b&0x3f)<<16)|a)+header
        if a>=0x8000 and (0x00<=b<=0x3f or 0x80<=b<=0xbf):
            return (0x400000 + (0x200000 if b>=0x80 else 0) + ((b&0x3f)<<15) + (a&0x7fff))+header
    return None

def file_to_cpu(offset:int, mapping='exhirom',header=0):
    offset-=header
    if offset<0:return None
    if mapping=='lorom':
        if offset>=0x400000:return None
        return (0x80|(offset>>15))<<16|0x8000|(offset&0x7fff)
    if mapping=='hirom':
        if offset>=0x400000:return None
        return (0xc0|(offset>>16))<<16|(offset&0xffff)
    if mapping=='exhirom':
        if offset>=0x800000:return None
        if offset<0x400000:return (0xc0|(offset>>16))<<16|(offset&0xffff)
        return (((0x80 if offset>=0x600000 else 0x00)|(((offset-0x400000)%0x200000)>>15))<<16)|0x8000|(offset&0x7fff)
    return None

def checksum_snes(data):
    # Headerless bytes simple checksum; mirrored handling is not equivalent for non-power-of-two ROMs.
    return sum(data)&0xffff

class Rom:
    def __init__(self,data:bytes,name:str='ROM'):
        self.raw=data;self.name=name
        self.header=512 if len(data)%0x8000==512 else 0
        self.data=data[self.header:]
        self.mapping,self.header_offset=self.detect()
    def detect(self):
        candidates=[]
        for ofs,kind in [(0x7fc0,'lorom'),(0xffc0,'hirom'),(0x40ffc0,'exhirom')]:
            if ofs+0x40>len(self.data):continue
            h=self.data[ofs:ofs+0x40]
            mode=h[0x15]
            score=0
            if (h[0x1c]^h[0x1e])==0xff and (h[0x1d]^h[0x1f])==0xff:score+=3
            if all(32<=c<127 for c in h[:21]):score+=2
            if kind=='lorom' and mode&0x0f==0:score+=3
            if kind=='hirom' and mode&0x0f==1:score+=3
            if kind=='exhirom' and mode&0x0f==5:score+=5
            if kind=='exhirom' and len(self.data)>0x400000:score+=2
            if mode in (0x20,0x21,0x30,0x31,0x35,0x25):score+=1
            candidates.append((score,kind,ofs))
        if not candidates:return ('unknown',None)
        _,kind,ofs=max(candidates)
        return kind,ofs
    def metadata(self):
        sha=hashlib.sha256(self.data).hexdigest()
        d={'name':self.name,'bytes':len(self.data),'copier_header':self.header,'mapping':self.mapping,'sha256':sha,'crc32':f'{zlib.crc32(self.data):08X}','bank_count':math.ceil(len(self.data)/BANK)}
        if self.header_offset is not None:
            h=self.data[self.header_offset:self.header_offset+0x40]
            stored=h[0x1e]|h[0x1f]<<8;comp=h[0x1c]|h[0x1d]<<8
            d.update(title=h[:21].decode('ascii','replace').strip(),map_byte=f'0x{h[0x15]:02X}',checksum=f'{stored:04X}',complement=f'{comp:04X}',checksum_calculated=f'{checksum_snes(self.data):04X}',checksum_pair_valid=(stored^comp)==0xffff,reset_vector=f'{h[0x3c]|h[0x3d]<<8:04X}')
        return d
    def read(self,offset,size):
        if offset<0 or size<0 or offset>=len(self.data):return b''
        return self.data[offset:offset+size]
    def banks(self,other=None,cdl=None):
        out=[]
        for offset in range(0,len(self.data),BANK):
            chunk=self.data[offset:offset+BANK]; different=None
            if other is not None:
                otherchunk=other.data[offset:offset+BANK];different=sum(x!=y for x,y in zip(chunk,otherchunk))+max(0,len(chunk)-len(otherchunk))
            mark=cdl.flags[offset:offset+len(chunk)] if cdl else b''
            counts=[0,0,0]
            if mark:
                counts=[sum(x!=0 for x in mark),sum(bool(x&1) for x in mark),sum(bool(x&2) for x in mark)]
            out.append({'index':offset//BANK,'offset':offset,'cpu':f'{file_to_cpu(offset,self.mapping) or 0:06X}' if file_to_cpu(offset,self.mapping) is not None else None,'filled':sum(x not in (0,255) for x in chunk),'zero':chunk.count(0),'ff':chunk.count(255),'different':different,'marked':counts[0],'code':counts[1],'data':counts[2]})
        return out

class CDL:
    def __init__(self,data:bytes,rom_size:int):
        self.header=b''
        if len(data)==rom_size:self.flags=data
        elif data.startswith(b'CDLv2') and len(data)>rom_size:
            self.header=data[:-rom_size];self.flags=data[-rom_size:]
        else:raise ValueError(f'Unexpected CDL length {len(data)} for ROM {rom_size}')
    def status(self,offset):
        if not 0<=offset<len(self.flags):return {'flag':None,'code':False,'data':False}
        v=self.flags[offset]
        return {'flag':v,'code':bool(v&1),'data':bool(v&2),'unknown_bits':v&~3}
    def stats(self):
        return {'bytes':len(self.flags),'header_bytes':len(self.header),'marked':sum(bool(b) for b in self.flags),'code':sum(bool(b&1) for b in self.flags),'data':sum(bool(b&2) for b in self.flags)}

def parse_mlb(blob:bytes):
    result=[]
    for lineno,line in enumerate(blob.decode('utf-8-sig','replace').splitlines(),1):
        parts=line.split(':',3)
        if len(parts)<3:continue
        typ,addr,label=parts[:3]
        try: n=int(addr,16)
        except ValueError:continue
        result.append({'type':typ,'address':n,'label':label,'comment':parts[3] if len(parts)==4 else '', 'source_line':lineno})
    return result

def to_mlb(entries):
    lines=[]
    for e in entries:
        label=e['label'].replace(':','_').replace('\n',' ')
        comment=e.get('comment','').replace(':',';').replace('\n',' ')
        lines.append(f"{e['type']}:{e['address']:X}:{label}:{comment}")
    return '\n'.join(lines)+'\n'

# 65C816 opcode matrix. Symbols: imp, acc, imm8, immM, immX, dp, dpx, dpy,
# abs, absx, absy, long, longx, ind, indx, indy, dpind, dpindy, dpindl,
# dpindly, sr, sriy, absind, absindx, abslind, rel8, rel16, block, pei, per, pea.
ROWS=[
'BRK:imm8 ORA:indx COP:imm8 ORA:sr TSB:dp ORA:dp ASL:dp ORA:dpindl PHP:imp ORA:immM ASL:acc PHD:imp TSB:abs ORA:abs ASL:abs ORA:long',
'BPL:rel8 ORA:indy ORA:dpind ORA:sriy TRB:dp ORA:dpx ASL:dpx ORA:dpindly CLC:imp ORA:absy INC:acc TCS:imp TRB:abs ORA:absx ASL:absx ORA:longx',
'JSR:abs AND:indx JSL:long AND:sr BIT:dp AND:dp ROL:dp AND:dpindl PLP:imp AND:immM ROL:acc PLD:imp BIT:abs AND:abs ROL:abs AND:long',
'BMI:rel8 AND:indy AND:dpind AND:sriy BIT:dpx AND:dpx ROL:dpx AND:dpindly SEC:imp AND:absy DEC:acc TSC:imp BIT:absx AND:absx ROL:absx AND:longx',
'RTI:imp EOR:indx WDM:imm8 EOR:sr MVP:block EOR:dp LSR:dp EOR:dpindl PHA:imp EOR:immM LSR:acc PHK:imp JMP:abs EOR:abs LSR:abs EOR:long',
'BVC:rel8 EOR:indy EOR:dpind EOR:sriy MVN:block EOR:dpx LSR:dpx EOR:dpindly CLI:imp EOR:absy PHY:imp TCD:imp JML:long EOR:absx LSR:absx EOR:longx',
'RTS:imp ADC:indx PER:per ADC:sr STZ:dp ADC:dp ROR:dp ADC:dpindl PLA:imp ADC:immM ROR:acc RTL:imp JMP:absind ADC:abs ROR:abs ADC:long',
'BVS:rel8 ADC:indy ADC:dpind ADC:sriy STZ:dpx ADC:dpx ROR:dpx ADC:dpindly SEI:imp ADC:absy PLY:imp TDC:imp JMP:absindx ADC:absx ROR:absx ADC:longx',
'BRA:rel8 STA:indx BRL:rel16 STA:sr STY:dp STA:dp STX:dp STA:dpindl DEY:imp BIT:immM TXA:imp PHB:imp STY:abs STA:abs STX:abs STA:long',
'BCC:rel8 STA:indy STA:dpind STA:sriy STY:dpx STA:dpx STX:dpy STA:dpindly TYA:imp STA:absy TXS:imp TXY:imp STZ:abs STA:absx STZ:absx STA:longx',
'LDY:immX LDA:indx LDX:immX LDA:sr LDY:dp LDA:dp LDX:dp LDA:dpindl TAY:imp LDA:immM TAX:imp PLB:imp LDY:abs LDA:abs LDX:abs LDA:long',
'BCS:rel8 LDA:indy LDA:dpind LDA:sriy LDY:dpx LDA:dpx LDX:dpy LDA:dpindly CLV:imp LDA:absy TSX:imp TYX:imp LDY:absx LDA:absx LDX:absy LDA:longx',
'CPY:immX CMP:indx REP:imm8 CMP:sr CPY:dp CMP:dp DEC:dp CMP:dpindl INY:imp CMP:immM DEX:imp WAI:imp CPY:abs CMP:abs DEC:abs CMP:long',
'BNE:rel8 CMP:indy CMP:dpind CMP:sriy PEI:pei CMP:dpx DEC:dpx CMP:dpindly CLD:imp CMP:absy PHX:imp STP:imp JML:abslind CMP:absx DEC:absx CMP:longx',
'CPX:immX SBC:indx SEP:imm8 SBC:sr CPX:dp SBC:dp INC:dp SBC:dpindl INX:imp SBC:immM NOP:imp XBA:imp CPX:abs SBC:abs INC:abs SBC:long',
'BEQ:rel8 SBC:indy SBC:dpind SBC:sriy PEA:pea SBC:dpx INC:dpx SBC:dpindly SED:imp SBC:absy PLX:imp XCE:imp JSR:absindx SBC:absx INC:absx SBC:longx'
]
OPCODES=[tuple(x.split(':')) for row in ROWS for x in row.split()]
assert len(OPCODES)==256
WIDTH={'imp':0,'acc':0,'imm8':1,'dp':1,'dpx':1,'dpy':1,'indx':1,'indy':1,'dpind':1,'dpindy':1,'dpindl':1,'dpindly':1,'sr':1,'sriy':1,'pei':1,'abs':2,'absx':2,'absy':2,'absind':2,'absindx':2,'abslind':2,'rel8':1,'rel16':2,'block':2,'per':2,'pea':2,'long':3,'longx':3}
@dataclass
class CpuState:
    e:bool|None=False
    m:bool|None=True
    x:bool|None=True
    def width(self,mode):
        if mode=='immM':return 1 if self.e or self.m else 2 if self.m is False and self.e is False else None
        if mode=='immX':return 1 if self.e or self.x else 2 if self.x is False and self.e is False else None
        return WIDTH.get(mode)
    def update(self,name,operand):
        if name=='REP' and operand is not None:
            if operand&0x20:self.m=False if self.e is False else True if self.e else None
            if operand&0x10:self.x=False if self.e is False else True if self.e else None
        elif name=='SEP' and operand is not None:
            if operand&0x20:self.m=True
            if operand&0x10:self.x=True
        elif name in ('PLP','RTI','XCE'):
            self.e=None;self.m=None;self.x=None

def decode_one(data:bytes,offset:int,state:CpuState,mapping='exhirom'):
    if offset>=len(data):return None
    opcode=data[offset];name,mode=OPCODES[opcode];w=state.width(mode)
    if w is None:
        return {'offset':offset,'cpu':file_to_cpu(offset,mapping),'opcode':f'{opcode:02X}','mnemonic':name,'mode':mode,'bytes':f'{opcode:02X}','size':None,'operand':'? (M/X desconhecido)','ambiguous':True,'flow':'unknown'}
    size=1+w
    if offset+size>len(data):return None
    raw=data[offset:offset+size];v=int.from_bytes(raw[1:],'little') if w else 0
    cpu=file_to_cpu(offset,mapping)
    bank=(cpu>>16) if cpu is not None else 0
    operand=''
    formats={'imm8':f'#$%02X'%v,'immM':f'#$%0*X'%(w*2,v),'immX':f'#$%0*X'%(w*2,v),'dp':f'$%02X'%v,'dpx':f'$%02X,X'%v,'dpy':f'$%02X,Y'%v,'abs':f'$%04X'%v,'absx':f'$%04X,X'%v,'absy':f'$%04X,Y'%v,'long':f'$%06X'%v,'longx':f'$%06X,X'%v,'indx':f'($%02X,X)'%v,'indy':f'($%02X),Y'%v,'dpind':f'($%02X)'%v,'dpindy':f'($%02X),Y'%v,'dpindl':f'[$%02X]'%v,'dpindly':f'[$%02X],Y'%v,'sr':f'$%02X,S'%v,'sriy':f'($%02X,S),Y'%v,'absind':f'($%04X)'%v,'absindx':f'($%04X,X)'%v,'abslind':f'[$%04X]'%v,'pei':f'($%02X)'%v,'pea':f'$%04X'%v,'per':f'$%04X'%v}
    operand=formats.get(mode,'')
    if mode=='block':operand=f'${raw[1]:02X},${raw[2]:02X}'
    target=None
    if mode in ('rel8','rel16','per') and cpu is not None:
        disp=v-(1<<(w*8)) if v&(1<<(w*8-1)) else v
        target=bank<<16|((cpu+size+disp)&0xffff)
        operand=f'${target:06X}'
    elif mode=='abs' and name in ('JMP','JSR') and cpu is not None:
        target=(bank<<16)|v
    elif mode=='long' and name in ('JSL','JML'):
        target=v
    flow='linear'
    if name in ('JMP','JML','BRA','BRL'):flow='jump'
    elif name in ('JSR','JSL'):flow='call'
    elif name in ('RTS','RTL','RTI','STP','BRK','COP'):flow='stop'
    elif mode=='rel8' and name not in ('BRA',):flow='branch'
    st=CpuState(state.e,state.m,state.x);st.update(name,v if w else None)
    return {'offset':offset,'cpu':cpu,'opcode':f'{opcode:02X}','mnemonic':name,'mode':mode,'operand':operand,'bytes':raw.hex(' ').upper(),'size':size,'target':target,'flow':flow,'ambiguous':False,'state_after':{'e':st.e,'m':st.m,'x':st.x}}

def disassemble(rom:Rom,offset:int,count=64,e=False,m=True,x=True,cdl=None):
    state=CpuState(e,m,x);out=[]
    for _ in range(min(count,512)):
        item=decode_one(rom.data,offset,state,rom.mapping)
        if not item:break
        item['cdl']=cdl.status(offset) if cdl else None
        out.append(item)
        if item['size'] is None:break
        state=CpuState(**item['state_after']);offset+=item['size']
    return out

def basic_block(rom,offset,e=False,m=True,x=True,limit=512):
    results=disassemble(rom,offset,limit,e,m,x)
    block=[]
    for item in results:
        block.append(item)
        if item['flow'] in ('branch','jump','stop','unknown'):break
    return block

def control_flow(rom:Rom,start:int,e=False,m=True,x=True,max_blocks=80):
    """Conservative same-function CFG: no indirect recovery; state propagated along direct edges."""
    visited=set();pending=[(start,CpuState(e,m,x))];nodes=[];edges=[]
    while pending and len(nodes)<max_blocks:
        ofs,state=pending.pop(0)
        statekey=(ofs,state.e,state.m,state.x)
        if statekey in visited or ofs<0 or ofs>=len(rom.data):continue
        visited.add(statekey)
        block=[];position=ofs
        for i in range(256):
            inst=decode_one(rom.data,position,state,rom.mapping)
            if not inst:break
            block.append(inst)
            if inst['size'] is None:break
            state=CpuState(**inst['state_after']);position+=inst['size']
            if inst['flow'] in ('branch','jump','stop','unknown','call'):break
        if not block:continue
        last=block[-1]
        nodes.append({'offset':ofs,'cpu':file_to_cpu(ofs,rom.mapping),'instructions':len(block),'end_offset':position,'last_mnemonic':last['mnemonic'],'state':{'e':state.e,'m':state.m,'x':state.x}})
        if last['flow']=='stop' or last['size'] is None:continue
        def edge(next_ofs,kind):
            if next_ofs is None:return
            edges.append({'from':ofs,'to':next_ofs,'kind':kind})
            if 0<=next_ofs<len(rom.data):pending.append((next_ofs,CpuState(state.e,state.m,state.x)))
        if last['target'] is not None and last['flow'] in ('jump','branch','call'):
            target=cpu_to_file(last['target'],rom.mapping)
            edge(target,'call' if last['flow']=='call' else 'branch')
        if last['flow'] in ('branch','call','linear'):
            edge(position,'fallthrough')
    return {'nodes':nodes,'edges':edges,'truncated':bool(pending),'warning':'CFG estático conservador; saltos indiretos e estados desconhecidos exigem validação'}
