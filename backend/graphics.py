"""Read-only, deterministic SNES PPU graphics decoders.

VRAM is a 64KiB raw byte snapshot (not a ROM sprite archive).
CGRAM 512 bytes, 256 15-bit BGR entries. OAM 544 bytes (512 low + 32 high).
"""
from __future__ import annotations
from io import BytesIO
from PIL import Image

VRAM_LEN = 0x10000
CGRAM_LEN = 0x200
OAM_LEN = 0x220


def validate_dump(kind: str, data: bytes):
    lengths = {'vram': VRAM_LEN, 'cgram': CGRAM_LEN, 'oam': OAM_LEN}
    if kind not in lengths or len(data) != lengths[kind]:
        raise ValueError(f'{kind}: tamanho inválido; esperado {lengths.get(kind, "desconhecido")} bytes')
    return data


def bgr555_to_rgb(word: int) -> tuple[int,int,int]:
    r=word & 31; g=(word >> 5) & 31; b=(word >> 10) & 31
    return (r << 3 | r >> 2, g << 3 | g >> 2, b << 3 | b >> 2)


def decode_cgram(data: bytes) -> list[tuple[int,int,int]]:
    validate_dump('cgram', data)
    return [bgr555_to_rgb(data[i] | data[i+1]<<8) for i in range(0,512,2)]


def decode_tile(vram: bytes, offset: int, bpp: int = 4) -> list[list[int]]:
    """Decode standard SNES planar tile. offset is byte offset (not VMADD word)."""
    if bpp not in (2,4,8):raise ValueError('bpp suportados: 2, 4, 8')
    tile_len=bpp*8
    if offset<0 or offset+tile_len>len(vram):raise ValueError('Tile ultrapassa região disponível')
    pixels=[]
    for y in range(8):
        line=[]
        for x in range(8):
            bit=7-x; val=0
            for pair in range(bpp//2):
                i=offset+pair*16+y*2
                val|=((vram[i]>>bit)&1)<<(pair*2)
                val|=((vram[i+1]>>bit)&1)<<(pair*2+1)
            line.append(val)
        pixels.append(line)
    return pixels


def tile_sheet(vram: bytes, cgram: bytes|None=None, *, offset: int=0, bpp:int=4,
               columns:int=16, rows:int=16, palette:int=0, scale:int=2, grid:bool=False) -> Image.Image:
    if bpp not in (2,4,8) or columns<1 or rows<1 or columns*rows>1024 or scale<1 or scale>8:
        raise ValueError('Parâmetros de tiles fora dos limites')
    if offset<0 or offset>=len(vram) or offset%(bpp*8):raise ValueError('Offset inválido ou desalinhado')
    maxcolors=1<<bpp; groups=256//maxcolors
    if not 0<=palette<groups:raise ValueError('Subpaleta inválida')
    colors=decode_cgram(cgram) if cgram else [(i,i,i) for i in range(256)]
    img=Image.new('RGB',(columns*8,rows*8),(18,20,27)); px=img.load()
    for n in range(columns*rows):
        start=offset+n*bpp*8
        if start+bpp*8>len(vram):break
        pixels=decode_tile(vram,start,bpp)
        x0=n%columns*8; y0=n//columns*8
        for y in range(8):
            for x in range(8):
                px[x0+x,y0+y]=colors[palette*maxcolors+pixels[y][x]]
    if scale!=1:img=img.resize((img.width*scale,img.height*scale),Image.Resampling.NEAREST)
    if grid:
        from PIL import ImageDraw
        draw=ImageDraw.Draw(img)
        for x in range(0,img.width,8*scale):draw.line((x,0,x,img.height-1),fill=(65,65,72))
        for y in range(0,img.height,8*scale):draw.line((0,y,img.width-1,y),fill=(65,65,72))
    return img

# SNES OBSEL sizes, small/large in pixels (configuration 0..7)
OBJ_SIZES=((8,16),(8,32),(8,64),(16,32),(16,64),(32,64),(16,32),(16,32))


def decode_oam(raw: bytes, size_mode:int=0) -> list[dict]:
    validate_dump('oam',raw)
    if not 0<=size_mode<8:raise ValueError('OBSEL size mode inválido')
    entries=[]
    for n in range(128):
        i=n*4;x, y, tile, attr=raw[i:i+4]
        high=raw[512+n//4] >> ((n%4)*2) & 3
        xx=x|((high&1)<<8)
        if xx>=256:xx-=512
        large=bool(high&2); size=OBJ_SIZES[size_mode][int(large)]
        entries.append({'index':n,'x':xx,'y':y,'tile':tile,'nameselect':attr&1,
                        'palette':(attr>>1)&7,'priority':(attr>>4)&3,
                        'flip_x':bool(attr&0x40),'flip_y':bool(attr&0x80),
                        'large':large,'size':size,'raw':list(raw[i:i+4]),'high':high})
    return entries


def render_oam(vram:bytes,cgram:bytes,oam:bytes,*, size_mode:int=0,base:int=0,
               name_select:int=0,scale:int=2,visible_only:bool=True)->Image.Image:
    """Approximate OBJ composition; OBSEL base/nameSelect passed explicitly, not recovered from dumps.
    base/name_select are byte offsets aligned to 0x2000 / 0x1000 respectively.
    Typical OBJ palette range is CGRAM 128..255 and always 4bpp.
    """
    if not 0<=base<VRAM_LEN or not 0<=name_select<VRAM_LEN:raise ValueError('VRAM base inválida')
    if scale<1 or scale>6:raise ValueError('Escala inválida')
    colors=decode_cgram(cgram)
    out=Image.new('RGBA',(256,224),(0,0,0,0));dst=out.load()
    objs=decode_oam(oam,size_mode)
    # index 0 has highest OBJ priority on SNES; draw in reverse order within a priority level
    for obj in sorted(objs,key=lambda o:(o['priority'],-o['index'])):
        if visible_only and (obj['x']<=-obj['size'] or obj['x']>=256 or obj['y']>=224):continue
        count=obj['size']//8
        for ty in range(count):
            for tx in range(count):
                # Tile-number increment: tilemap uses row stride of 16 tiles.
                source_x=count-1-tx if obj['flip_x'] else tx
                source_y=count-1-ty if obj['flip_y'] else ty
                tile_num=(obj['tile']+(source_y*16)+source_x)&255
                tile_addr=(base+(name_select if obj['nameselect'] else 0)+tile_num*32)%VRAM_LEN
                if tile_addr+32>len(vram):continue
                pixels=decode_tile(vram,tile_addr,4)
                for py in range(8):
                    for px in range(8):
                        pix=pixels[7-py if obj['flip_y'] else py][7-px if obj['flip_x'] else px]
                        if pix==0:continue
                        dx=obj['x']+tx*8+px;dy=(obj['y']+ty*8+py)&255
                        if 0<=dx<256 and 0<=dy<224:
                            dst[dx,dy]=(*colors[128+obj['palette']*16+pix],255)
    if scale>1:out=out.resize((256*scale,224*scale),Image.Resampling.NEAREST)
    return out


def png_bytes(img:Image.Image)->bytes:
    output=BytesIO();img.save(output,format='PNG');return output.getvalue()
