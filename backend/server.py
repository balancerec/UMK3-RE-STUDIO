from __future__ import annotations
from pathlib import Path
from fastapi import FastAPI, UploadFile, File, HTTPException, Query
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from .core import Rom, CDL, parse_mlb, to_mlb, cpu_to_file, file_to_cpu, disassemble, basic_block
from .storage import Store
from .analysis import build_xrefs, query_xrefs, seed_roots
from .memory import extract_wram, pair_compare, candidate_report, breakpoint_plan, WRAM_SIZE, MAPPED_SIZE, CANDIDATES
from fastapi import Form
from .graphics import validate_dump, decode_cgram, decode_oam, tile_sheet, render_oam, png_bytes
from .extraction import bank_inventory, match_vram_windows, run_candidates, preview_raw
from .dma import scan_register_writes, match_staging, dma_observation_plan
from .dma_trace import analyze_trace
from .capture import convert_capture, capture_audit, capture_plan

app=FastAPI(title='UMK3 RE Studio',version='0.8.0')
app.add_middleware(CORSMiddleware,allow_origins=['http://localhost:5173','http://127.0.0.1:5173'],allow_methods=['*'],allow_headers=['*'])
class Session:
    def __init__(self):
        self.rom=None; self.comparison=None;self.cdl=None;self.symbols=[];self.project_id=None;self.xrefs=None;self.graphics={};self.dma_trace=None
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
    session.graphics={};session.dma_trace=None
    for kind,sha in store.graphics_assets(pid).items():
        raw=store.load_artifact(sha)
        if raw is not None:
            if kind=="dma_trace":session.dma_trace=raw
            else:session.graphics[kind]=raw
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


@app.get('/api/captures')
def captures():
    if not session.project_id:return []
    return store.captures(session.project_id)

@app.post('/api/captures')
async def upload_capture(file:UploadFile=File(...),character:str=Form(...),expected_id:str=Form('')):
    if not session.project_id:raise HTTPException(400,'Crie ou abra um projeto antes')
    if not character.strip() or len(character)>80:raise HTTPException(422,'Personagem inválido')
    raw=await content(file,MAPPED_SIZE)
    try:normalized=extract_wram(raw)
    except ValueError as exc:raise HTTPException(422,str(exc))
    if expected_id.strip():
        try:
            eid=int(expected_id.strip().removeprefix('0x'),16)
        except ValueError:raise HTTPException(422,'ID esperado em hexadecimal inválido')
        if not 0<=eid<=255:raise HTTPException(422,'ID deve estar entre 00 e FF')
    else:eid=None
    return store.add_capture(session.project_id,normalized,file.filename or 'WRAM',character.strip(),eid)

@app.delete('/api/captures/{cap}')
def delete_capture(cap:str):
    if not session.project_id or not store.remove_capture(session.project_id,cap):raise HTTPException(404,'Captura não encontrada')
    return {'deleted':True}

def require_capture(cap:str)->bytes:
    if not session.project_id:raise HTTPException(400,'Abra um projeto')
    item=store.capture(session.project_id,cap)
    if not item:raise HTTPException(404,'Captura não encontrada')
    raw=store.load_artifact(item['sha'])
    if raw is None or len(raw)!=WRAM_SIZE:raise HTTPException(500,'Arquivo armazenado inválido')
    return raw

@app.get('/api/captures/compare')
def compare_captures(left:str,right:str,offset:int=0,length:int=512,width:int=1,limit:int=150):
    try:return pair_compare(require_capture(left),require_capture(right),offset,length,min(max(1,limit),1000),width)
    except ValueError as exc:raise HTTPException(422,str(exc))

class CandidateQuery(BaseModel):
    ids:list[str]
    max_results:int=250

@app.post('/api/captures/candidates')
def candidates(q:CandidateQuery):
    if not session.project_id:raise HTTPException(400,'Abra um projeto')
    if not 2<=len(q.ids)<=40:raise HTTPException(422,'Selecione 2 a 40 capturas')
    if len(set(q.ids))!=len(q.ids):raise HTTPException(422,'Capturas duplicadas')
    shots=[]
    for cap in q.ids:
        item=store.capture(session.project_id,cap)
        if not item:raise HTTPException(404,'Captura não encontrada')
        shots.append(item|{'data':require_capture(cap)})
    try:return candidate_report(shots,min(max(1,q.max_results),1000))
    except ValueError as exc:raise HTTPException(422,str(exc))

@app.get('/api/captures/breakpoints')
def breakpoints(addresses:str='36D0,52C8'):
    try:
        parts=[x.strip().replace('$','').replace('7E:','').replace('7F:','') for x in addresses.upper().split(',') if x.strip()]
        if not 1<=len(parts)<=30:raise ValueError('Informe até 30 endereços')
        vals=[]
        for original,part in zip([x.strip().upper() for x in addresses.split(',') if x.strip()],parts):
            value=int(part,16)
            if original.startswith(('7F:','$7F:')):value+=0x10000
            vals.append(value)
        return {'breakpoints':breakpoint_plan(vals)}
    except ValueError as exc:raise HTTPException(422,str(exc))


# Graphics Explorer v0.4 (read-only)
@app.get('/api/graphics/status')
def graphics_status():
    return {'sources':{kind:{'bytes':len(raw)} for kind,raw in session.graphics.items()},
            'vram_required':65536,'cgram_required':512,'oam_required':544,
            'project_id':session.project_id}

@app.post('/api/graphics/{kind}')
async def graphics_import(kind:str,file:UploadFile=File(...)):
    if kind not in ('vram','cgram','oam'):raise HTTPException(422,'Tipo inválido')
    raw=await content(file,65536)
    try:validate_dump(kind,raw)
    except ValueError as e:raise HTTPException(422,str(e))
    session.graphics[kind]=raw
    if session.project_id:store.save_graphics_asset(session.project_id,kind,raw,file.filename or kind)
    return {'type':kind,'bytes':len(raw),'persisted':bool(session.project_id)}

@app.get('/api/graphics/palette')
def graphics_palette():
    raw=session.graphics.get('cgram')
    if raw is None:raise HTTPException(400,'Importe a CGRAM')
    colors=decode_cgram(raw)
    return {'colors':[{'index':i,'rgb':list(c),'hex':'#%02X%02X%02X'%c} for i,c in enumerate(colors)]}

@app.get('/api/graphics/oam')
def graphics_oam(size_mode:int=0,active_only:bool=False):
    raw=session.graphics.get('oam')
    if raw is None:raise HTTPException(400,'Importe a OAM')
    try:objs=decode_oam(raw,size_mode)
    except ValueError as e:raise HTTPException(422,str(e))
    if active_only:objs=[o for o in objs if -o['size'] < o['x'] < 256 and o['y']<224]
    return {'objects':objs,'count':len(objs),'note':'OAM não possui um bit confiável de invisibilidade; a lista por posição é heurística.'}

@app.get('/api/graphics/tiles.png')
def graphics_tiles(offset:int=0,bpp:int=4,columns:int=16,rows:int=16,palette:int=0,scale:int=2,grid:bool=False,download:bool=False):
    raw=session.graphics.get('vram')
    if raw is None:raise HTTPException(400,'Importe a VRAM')
    if rows*columns>1024 or rows>64 or columns>64:raise HTTPException(422,'Máximo de 1024 tiles')
    try:img=tile_sheet(raw,session.graphics.get('cgram'),offset=offset,bpp=bpp,columns=columns,rows=rows,palette=palette,scale=scale,grid=grid)
    except ValueError as e:raise HTTPException(422,str(e))
    headers={'Content-Disposition':'attachment; filename="umk3_tiles.png"'} if download else {}
    return Response(png_bytes(img),media_type='image/png',headers=headers)

@app.get('/api/graphics/sprites.png')
def graphics_sprites(size_mode:int=0,base:int=0,name_select:int=0,scale:int=2,download:bool=False):
    absent=[x for x in ('vram','cgram','oam') if x not in session.graphics]
    if absent:raise HTTPException(400,'Importe: '+', '.join(absent))
    try:img=render_oam(session.graphics['vram'],session.graphics['cgram'],session.graphics['oam'],size_mode=size_mode,base=base,name_select=name_select,scale=scale)
    except ValueError as e:raise HTTPException(422,str(e))
    headers={'Content-Disposition':'attachment; filename="umk3_oam_sprites.png"'} if download else {}
    return Response(png_bytes(img),media_type='image/png',headers=headers)


# v0.5 — Sprite Extraction research tools (read-only, no compression claims)
@app.get('/api/extract/banks')
def extract_banks():
    if not session.rom:raise HTTPException(400,'Importe uma ROM primeiro')
    return {'banks':bank_inventory(session.rom.data),'note':'Entropia e repetição não comprovam compressão nem espaço livre.'}

@app.get('/api/extract/match')
def extract_match(chunk_size:int=64,vram_offset:int=0,vram_length:int=4096,
                  step:int=64,minimum_unique:int=12,max_matches:int=150):
    if not session.rom:raise HTTPException(400,'Importe uma ROM primeiro')
    if 'vram' not in session.graphics:raise HTTPException(400,'Importe SnesVideoRam.dmp no Graphics Explorer')
    try:return match_vram_windows(session.rom.data,session.graphics['vram'],
                   chunk_size=chunk_size,vram_offset=vram_offset,vram_length=vram_length,
                   step=step,minimum_unique=minimum_unique,max_matches=max_matches)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/extract/runs')
def extract_runs(start:int=0,length:int=65536,min_run:int=64,limit:int=100):
    if not session.rom:raise HTTPException(400,'Importe uma ROM primeiro')
    try:return {'runs':run_candidates(session.rom.data,start=start,length=length,min_run=min_run,limit=limit),
                'note':'Repetições de bytes; não são automaticamente regiões livres.'}
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/extract/preview.png')
def extract_preview(offset:int=0,bpp:int=4,columns:int=16,rows:int=8,
                    palette:int=0,scale:int=2,download:bool=False):
    if not session.rom:raise HTTPException(400,'Importe uma ROM primeiro')
    try:img=preview_raw(session.rom.data,offset=offset,bpp=bpp,columns=columns,rows=rows,
                       palette=palette,scale=scale,cgram=session.graphics.get('cgram'))
    except ValueError as e:raise HTTPException(422,str(e))
    headers={'Content-Disposition':'attachment; filename="rom_raw_tiles.png"'} if download else {}
    return Response(png_bytes(img),media_type='image/png',headers=headers)


# v0.6 — Graphics Compression / DMA Research
@app.get('/api/dma/registers')
def dma_registers(start:int=0,length:int|None=None,code_only:bool=False,limit:int=250):
    if not session.rom:raise HTTPException(400,'Importe uma ROM primeiro')
    try:return scan_register_writes(session.rom.data,session.cdl,start=start,length=length,
                                     code_only=code_only,limit=limit)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/dma/staging')
def dma_staging(capture_id:str,chunk_size:int=32,vram_offset:int=0,
                vram_length:int=4096,minimum_unique:int=12,max_matches:int=100):
    vram=session.graphics.get('vram')
    if vram is None:raise HTTPException(400,'Importe uma VRAM no Graphics Explorer')
    try:
        wram=require_capture(capture_id)
        return match_staging(wram,vram,chunk_size=chunk_size,vram_offset=vram_offset,
                            vram_length=vram_length,minimum_unique=minimum_unique,
                            max_matches=max_matches)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/dma/plan')
def dma_plan():return dma_observation_plan()


# v0.7 — observed bus writes + inferred DMA transfer reconstruction
@app.get('/api/dma/trace/status')
def dma_trace_status():
    return {'loaded':session.dma_trace is not None,
            'bytes':len(session.dma_trace) if session.dma_trace else 0,
            'project_id':session.project_id}

@app.post('/api/dma/trace')
async def dma_trace_upload(file:UploadFile=File(...)):
    raw=await content(file,16*1024*1024)
    try:result=analyze_trace(raw,max_results=20)
    except ValueError as e:raise HTTPException(422,str(e))
    session.dma_trace=raw
    if session.project_id:
        store.save_graphics_asset(session.project_id,'dma_trace',raw,file.filename or 'trace.csv')
    return {'meta':result['meta'],'dma_triggers':result['dma_triggers'],
            'register_writes':result['register_writes'],'saved':bool(session.project_id)}

@app.get('/api/dma/trace/analyze')
def dma_trace_analyze(capture_id:str|None=None,max_results:int=100):
    if session.dma_trace is None:raise HTTPException(400,'Importe um trace CSV/JSONL')
    wram=require_capture(capture_id) if capture_id else None
    try:return analyze_trace(session.dma_trace,
        rom=session.rom.data if session.rom else None,wram=wram,
        vram=session.graphics.get('vram'),max_results=max_results)
    except ValueError as e:raise HTTPException(422,str(e))


# v0.8 — Mesen Capture Assistant. Raw imports are never executed as scripts.
@app.get('/api/capture/plan')
def mesen_capture_plan():return capture_plan()

@app.post('/api/capture/convert')
async def mesen_capture_convert(file:UploadFile=File(...)):
    raw=await content(file,16*1024*1024)
    try:
        converted=convert_capture(raw)
        audit=capture_audit(converted)
    except ValueError as e:raise HTTPException(422,str(e))
    session.dma_trace=converted
    if session.project_id:
        store.save_graphics_asset(session.project_id,'dma_trace',converted,'mesen_dma_normalizado.csv')
    return {'audit':audit,'saved':bool(session.project_id),'csv':converted.decode('utf-8')}

@app.get('/api/capture/audit')
def mesen_capture_audit():
    if session.dma_trace is None:raise HTTPException(400,'Importe um trace antes')
    try:return capture_audit(session.dma_trace)
    except ValueError as e:raise HTTPException(422,str(e))

@app.get('/api/capture/script.lua')
def mesen_capture_script():
    return FileResponse(Path(__file__).resolve().parent.parent/'examples'/'mesen_dma_capture.lua',
                        media_type='text/plain',filename='mesen_dma_capture.lua')

@app.get('/api/capture/template.csv')
def mesen_capture_template():
    return FileResponse(Path(__file__).resolve().parent.parent/'examples'/'dma_trace_manual.csv',
                        media_type='text/csv',filename='dma_trace_manual.csv')
