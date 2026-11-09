from io import BytesIO
import tempfile
from PIL import Image
from fastapi.testclient import TestClient
from backend.graphics import decode_tile,decode_cgram,decode_oam,tile_sheet,render_oam,png_bytes
from backend.storage import Store


def test_tile_planar_2_4_8():
    for bpp in (2,4,8):
        data=bytearray(8*bpp)
        for plane in range(bpp):
            byte_offset=(plane//2)*16+(plane%2)
            data[byte_offset]=0x80
        px=decode_tile(data,0,bpp)
        assert px[0][0]==(1<<bpp)-1
        assert px[0][1]==0
        assert px[1][0]==0


def test_cgram_color_and_png():
    raw=bytearray(512)
    raw[2:4]=(0x001f).to_bytes(2,'little')
    raw[4:6]=(0x03e0).to_bytes(2,'little')
    raw[6:8]=(0x7c00).to_bytes(2,'little')
    cols=decode_cgram(bytes(raw))
    assert cols[1]==(255,0,0) and cols[2]==(0,255,0) and cols[3]==(0,0,255)
    vram=bytearray(65536);vram[0]=128
    img=tile_sheet(bytes(vram),bytes(raw),bpp=2,columns=1,rows=1,scale=2)
    assert img.getpixel((0,0))==(255,0,0)
    assert Image.open(BytesIO(png_bytes(img))).size==(16,16)


def test_oam_9bit_x_and_flip():
    raw=bytearray(544)
    raw[:4]=bytes([250,20,0x31,0b11011111])
    raw[512]=3 # obj 0 high x=1 and large=1
    obj=decode_oam(bytes(raw),0)[0]
    assert obj['x']==-6 and obj['y']==20 and obj['size']==16
    assert obj['flip_x'] and obj['flip_y'] and obj['priority']==1
    assert obj['palette']==7 and obj['nameselect']==1


def test_render_sprite_simple():
    vram=bytearray(65536);vram[0]=128 # first pixel palette color 1
    cgram=bytearray(512);cgram[2*(128+1):2*(128+2)]=(0x001f).to_bytes(2,'little')
    oam=bytearray([0]*544)
    # other objects at y=240, i.e offscreen
    for i in range(128):oam[i*4+1]=240
    oam[0:4]=bytes([8,10,0,0])
    pic=render_oam(bytes(vram),bytes(cgram),bytes(oam),scale=1)
    assert pic.getpixel((8,10))==(255,0,0,255)
    assert pic.getpixel((9,10))[3]==0


def test_api_import_persist(monkeypatch):
    import backend.server as s
    with tempfile.TemporaryDirectory() as d:
        monkeypatch.setattr(s,'store',Store(d));monkeypatch.setattr(s,'session',s.Session())
        cli=TestClient(s.app)
        pid=cli.post('/api/projects',json={'name':'graficos'}).json()['id']
        for kind,raw in [('vram',bytes(65536)),('cgram',bytes(512)),('oam',bytes(544))]:
            r=cli.post(f'/api/graphics/{kind}',files={'file':(kind+'.dmp',raw)})
            assert r.status_code==200,r.text
        assert len(cli.get('/api/graphics/palette').json()['colors'])==256
        pic=cli.get('/api/graphics/tiles.png',params={'bpp':4,'columns':3,'rows':2,'scale':2})
        assert pic.status_code==200 and Image.open(BytesIO(pic.content)).size==(48,32)
        pic=cli.get('/api/graphics/sprites.png',params={'scale':1})
        assert pic.status_code==200 and Image.open(BytesIO(pic.content)).size==(256,224)
        assert len(cli.get('/api/graphics/oam').json()['objects'])==128
        assert cli.post('/api/graphics/vram',files={'file':('bad.dmp',bytes(100))}).status_code==422
        assert cli.post('/api/projects/'+pid+'/open').status_code==200
        assert set(cli.get('/api/graphics/status').json()['sources'])=={'vram','cgram','oam'}


def test_actual_dumps_if_available():
    from pathlib import Path
    root=Path('/mnt/data')
    files={k:next(iter(root.glob('*'+suffix)),None) for k,suffix in [('vram','SnesVideoRam.dmp'),('cgram','SnesCgRam.dmp'),('oam','SnesSpriteRam.dmp')]}
    if not all(files.values()):return
    raw={k:f.read_bytes() for k,f in files.items()}
    img=tile_sheet(raw['vram'],raw['cgram'],bpp=4,palette=0,columns=16,rows=16)
    assert img.size==(256,256)
    assert len(decode_oam(raw['oam']))==128
    assert len(png_bytes(render_oam(raw['vram'],raw['cgram'],raw['oam'])))>100
