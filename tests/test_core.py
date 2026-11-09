import pytest
from backend.core import Rom, CDL, parse_mlb, to_mlb, cpu_to_file, file_to_cpu, decode_one, disassemble, CpuState, OPCODES

def test_all_opcodes():
    assert len(OPCODES)==256
    assert OPCODES[0x5c]==('JML','long')
    assert OPCODES[0xc2]==('REP','imm8')
    assert OPCODES[0xe2]==('SEP','imm8')
    assert OPCODES[0x22]==('JSL','long')

def test_mapping_exhirom():
    tests={0x000000:0xc00000,0x008000:0xc08000,0x3fffff:0xffffff,0x400000:0x008000,0x5fffff:0x3fffff,0x600000:0x808000,0x7fffff:0xbfffff}
    for f,c in tests.items():
        assert file_to_cpu(f,'exhirom')==c,(hex(f),hex(c))
        assert cpu_to_file(c,'exhirom')==f,(hex(c),hex(f))
    for c in (0x7e0000,0x7f1234,0x002100,0x804200):assert cpu_to_file(c,'exhirom') is None

def test_rom_title():
    b=bytearray(8*1024*1024);p=0x40ffc0;b[p:p+21]=b'TEST GAME'.ljust(21,b' ');b[p+0x15]=0x35;b[p+0x1c:p+0x20]=bytes([0x34,0x12,0xcb,0xed]);r=Rom(bytes(b));assert r.mapping=='exhirom';assert r.metadata()['title']=='TEST GAME'

def test_immediate_state():
    data=bytes.fromhex('C2 30 A9 34 12 A2 78 56 E2 20 A9 99 5C 43 87 80')
    st=CpuState(e=False,m=True,x=True);ofs=0;ops=[]
    while ofs<len(data):
        r=decode_one(data,ofs,st,'hirom');ops.append(r);ofs+=r['size'];st=CpuState(**r['state_after'])
    assert [r['size'] for r in ops]==[2,3,3,2,2,4]
    assert ops[-1]['target']==0x808743

def test_unknown_state():
    r=decode_one(bytes.fromhex('A9 FF 12'),0,CpuState(e=None,m=None,x=None));assert r['ambiguous'] and r['size'] is None

def test_cdl_mesen():
    r=CDL(b'CDLv2SPe\x0d'+b'\x00'*64+bytes([1,2,3,0]),4)
    assert r.stats()['code']==2 and r.stats()['data']==2

def test_mlb_roundtrip():
    b=b'\xef\xbb\xbfSnesRegister:2100:INIDISP:Screen Display Register\n'
    s=parse_mlb(b);assert len(s)==1 and s[0]['address']==0x2100
    assert 'SnesRegister:2100:INIDISP' in to_mlb(s)
