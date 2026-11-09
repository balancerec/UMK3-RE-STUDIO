from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .core import Rom, CDL, parse_mlb, to_mlb, cpu_to_file, file_to_cpu, disassemble, basic_block
from .storage import Store
from .analysis import build_xrefs, query_xrefs, seed_roots

app=FastAPI(title='UMK3 RE Studio',version='0.2.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])
class Session:
    def __init__(self):
        self.rom=None; self.comparison=None;self.cdl=None;self.symbols=[];self.project_id=None;self.xrefs=None
session=Session()
store=Store()

def persist(field,raw,filename):
    if session.project_id:
        store.save_artifact(session.project_id,field,raw,filename)

def load_project(pid):
    p=store.get(pid)
    if not p:raise HTTPException(404,'Projeto não encontrado')
    session.project_id=pid
    data=store.load_artifact(p['rom_sha']);session.rom=Rom(data,'ROM do projeto') if data else None
    data=store.load_artifact(p['comparison_sha']);session.comparison=Rom(data,'ROM original') if data else None
    data=store.load_artifact(p['cdl_sha']);session.cdl=CDL(data,len(session.rom.data)) if data and session.rom else None
    session.symbols=store.symbols(pid,limit=2000);session.xrefs=None
    return p

class ProjectCreate(BaseModel):
    name:str

@app.get('/api/projects')
def projects():return store.projects()

@app.post('/api/projects')
def create_project(data:ProjectCreate):
    if not data.name.strip():raise HTTPException(422,'Nome obrigatório')
    p=store.create(data.name);load_project(p['id']);return p

@app.post('/api/projects/{pid}/open')
def open_project(pid:str):return load_project(pid)

@app.get('/api/project/current')
def current_project():return store.get(session.project_id) if session.project_id else None

MAX_ROM=16*1024*1024+512
async def content(file,max_size):
    out=await file.read(max_size+1)
    if len(out)>max_size:raise HTTPException(413,'Arquivo excede o limite')
    return out

@app.get('/api/status')
def status():
    return {'ready':session.rom is not None,'rom':session.rom.metadata() if session.rom else None,'comparison':session.comparison.metadata() if session.comparison else None,'cdl':session.cdl.stats() if session.cdl else None,'symbol_count':len(session.symbols),'project_id':session.project_id,'xref_count':len(session.xrefs['references']) if session.xrefs else 0}

@app.post('/api/rom')
async def rom(file:UploadFile=File(...)):
    data=await content(file,MAX_ROM)
    if len(data)<32768 or (len(data)%32768 not in (0,512)):raise HTTPException(422,'Tamanho incompatível com ROM SNES')
    session.rom=Rom(data,file.filename or 'ROM');session.cdl=None;session.xrefs=None;persist('rom_sha',data,file.filename or 'ROM')
    return session.rom.metadata()

@app.post('/api/compare')
async def compare(file:UploadFile=File(...)):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    raw=await content(file,MAX_ROM);session.comparison=Rom(raw,file.filename or 'Comparação');persist('comparison_sha',raw,file.filename or 'Comparação')
    return session.comparison.metadata()

@app.post('/api/cdl')
async def cdl(file:UploadFile=File(...)):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    try:
        raw=await content(file,MAX_ROM+1024);session.cdl=CDL(raw,len(session.rom.data));persist('cdl_sha',raw,file.filename or 'CDL')
    except ValueError as e:raise HTTPException(422,str(e))
    return session.cdl.stats()

@app.post('/api/mlb')
async def mlb(file:UploadFile=File(...)):
    imported=parse_mlb(await content(file,4*1024*1024));
    if session.project_id:
        store.replace_imported_symbols(session.project_id,imported);session.symbols=store.symbols(session.project_id,limit=2000)
    else:session.symbols=imported
    return {'count':len(session.symbols)}

@app.get('/api/mlb/export')
def export_mlb():return PlainTextResponse(to_mlb(session.symbols),headers={'Content-Disposition':'attachment; filename="umk3_symbols.mlb"'})

class NewSymbol(BaseModel):
    type:str='SnesPrgRom';address:int;label:str;comment:str=''
@app.post('/api/symbols')
def symbol(s:NewSymbol):
    if s.type not in ('SnesPrgRom','SnesWorkRam','SnesRegister','SpcRam'):raise HTTPException(422,'Tipo inválido')
    if not s.label.strip() or not 0<=s.address<=0xffffff:raise HTTPException(422,'Endereço ou label inválido')
    v=s.model_dump();
    if session.project_id:
        store.add_symbol(session.project_id,v['type'],v['address'],v['label'],v['comment']);session.symbols=store.symbols(session.project_id,limit=2000)
    else:session.symbols.append(v)
    return v

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


@app.get('/api/entrypoints')
def entrypoints():
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    return seed_roots(session.rom)

class AnalyzeParams(BaseModel):
    roots:list[int]=[]
    max_instructions:int=15000

@app.post('/api/xrefs/analyze')
def analyze_xrefs(params:AnalyzeParams):
    if not session.rom:raise HTTPException(400,'Abra uma ROM primeiro')
    roots=params.roots or [x['offset'] for x in seed_roots(session.rom) if x['name']=='reset']
    if not roots:raise HTTPException(422,'Nenhum ponto de entrada conhecido')
    if len(roots)>32 or any(x<0 or x>=len(session.rom.data) for x in roots):raise HTTPException(422,'Raízes inválidas')
    session.xrefs=build_xrefs(session.rom,roots,session.cdl,min(max(1,params.max_instructions),100000))
    return {k:v for k,v in session.xrefs.items() if k!='references'}|{'reference_count':len(session.xrefs['references'])}

@app.get('/api/xrefs')
def xrefs(to_offset:int|None=None,from_offset:int|None=None,limit:int=250):
    if not session.xrefs:return {'references':[],'ready':False}
    return {'references':query_xrefs(session.xrefs,to_offset,from_offset,min(max(limit,1),1000)), 'ready':True,'count':len(session.xrefs['references'])}

@app.get('/api/characters')
def characters():
    if not session.project_id:return {'observations':[],'ready':False}
    return {'observations':store.observations(session.project_id),'ready':True}

@app.post('/api/characters/seed')
def seed_characters():
    if not session.project_id:raise HTTPException(400,'Crie um projeto primeiro')
    import csv
    from pathlib import Path
    filepath=Path(__file__).parent/'reference'/'characters.csv'
    if not filepath.exists():raise HTTPException(404,'Catálogo não encontrado')
    with filepath.open(encoding='utf-8-sig',newline='') as f:
        for item in csv.DictReader(f):
            for addr in (0x7e36d0,0x7e52c8):
                store.observe(session.project_id,int(item['id_decimal']),item['name'],addr,int(item['id_decimal']),item['arquivo'],confidence='probable' if 'provavel' in item['name'].lower() else 'observed')
    return {'count':len(store.observations(session.project_id))}
