from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .core import Rom, CDL, parse_mlb, to_mlb, cpu_to_file, file_to_cpu, disassemble, basic_block

app=FastAPI(title='UMK3 RE Studio',version='0.1.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])
class Session:
    rom=None; comparison=None; cdl=None; symbols=[]
session=Session()

MAX_ROM=16*1024*1024+512
async def content(file,max_size):
    out=await file.read(max_size+1)
    if len(out)>max_size:raise HTTPException(413,'Arquivo excede o limite')
    return out

@app.get('/api/status')
def status():
    return {'ready':session.rom is not None,'rom':session.rom.metadata() if session.rom else None,'comparison':session.comparison.metadata() if session.comparison else None,'cdl':session.cdl.stats() if session.cdl else None,'symbol_count':len(session.symbols)}

@app.post('/api/rom')
async def rom(file:UploadFile=File(...)):
    data=await content(file,MAX_ROM)
    if len(data)<32768 or (len(data)%32768 not in (0,512)):raise HTTPException(422,'Tamanho incompatível com ROM SNES')
    session.rom=Rom(data,file.filename or 'ROM');session.cdl=None
    return session.rom.metadata()

@app.post('/api/compare')
async def compare(file:UploadFile=File(...)):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    session.comparison=Rom(await content(file,MAX_ROM),file.filename or 'Comparação')
    return session.comparison.metadata()

@app.post('/api/cdl')
async def cdl(file:UploadFile=File(...)):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    try:session.cdl=CDL(await content(file,MAX_ROM+1024),len(session.rom.data))
    except ValueError as e:raise HTTPException(422,str(e))
    return session.cdl.stats()

@app.post('/api/mlb')
async def mlb(file:UploadFile=File(...)):
    session.symbols=parse_mlb(await content(file,4*1024*1024));return {'count':len(session.symbols)}

@app.get('/api/mlb/export')
def export_mlb():return PlainTextResponse(to_mlb(session.symbols),headers={'Content-Disposition':'attachment; filename="umk3_symbols.mlb"'})

class NewSymbol(BaseModel):
    type:str='SnesPrgRom';address:int;label:str;comment:str=''
@app.post('/api/symbols')
def symbol(s:NewSymbol):
    if s.type not in ('SnesPrgRom','SnesWorkRam','SnesRegister','SpcRam'):raise HTTPException(422,'Tipo inválido')
    if not s.label.strip() or not 0<=s.address<=0xffffff:raise HTTPException(422,'Endereço ou label inválido')
    v=s.model_dump();session.symbols.append(v);return v

@app.get('/api/symbols')
def symbols(q:str='',limit:int=150):
    return [v for v in session.symbols if q.lower() in v['label'].lower() or q.lower() in f"{v['address']:X}".lower()][:min(limit,500)]

@app.get('/api/banks')
def banks():
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    return session.rom.banks(session.comparison,session.cdl)

@app.get('/api/hex')
def hexview(offset:int=0,length:int=256):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    if length<1 or length>4096:raise HTTPException(422,'Comprimento 1-4096')
    chunk=session.rom.read(offset,length)
    return {'offset':offset,'length':len(chunk),'bytes':list(chunk),'cpu':file_to_cpu(offset,session.rom.mapping),'comparison':list(session.comparison.read(offset,length)) if session.comparison else None}

@app.get('/api/disasm')
def disasm(offset:int=0,count:int=64,e:int=0,m:int=1,x:int=1):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    if offset<0 or offset>=len(session.rom.data):raise HTTPException(422,'Offset fora da ROM')
    return disassemble(session.rom,offset,count, bool(e),bool(m),bool(x),session.cdl)

@app.get('/api/block')
def block(offset:int=0,e:int=0,m:int=1,x:int=1):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    return basic_block(session.rom,offset,bool(e),bool(m),bool(x))

@app.get('/api/translate')
def translate(cpu:str|None=None,offset:int|None=None):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    if cpu is not None:
        try:addr=int(cpu.replace('$','').replace(':',''),16)
        except ValueError:raise HTTPException(422,'Endereço hexadecimal inválido')
        ofs=cpu_to_file(addr,session.rom.mapping)
        return {'cpu':f'{addr:06X}','offset':ofs if ofs is not None and ofs<len(session.rom.data) else None}
    if offset is not None:return {'offset':offset,'cpu':f'{file_to_cpu(offset,session.rom.mapping):06X}' if file_to_cpu(offset,session.rom.mapping) is not None else None}
    raise HTTPException(422,'Informe cpu ou offset')

@app.get('/')
def index():return FileResponse(Path(__file__).parent/'static'/'index.html')

@app.get('/api/graph')
def graph(offset:int=0,e:int=0,m:int=1,x:int=1,max_blocks:int=50):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    if offset<0 or offset>=len(session.rom.data):raise HTTPException(422,'Offset fora da ROM')
    from .core import control_flow
    return control_flow(session.rom,offset,bool(e),bool(m),bool(x),min(100,max(1,max_blocks)))
