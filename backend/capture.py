"""Mesen 2 DMA capture assistant: parse logged bus writes, audit coverage and normalize.

Only lines marked by the companion Lua script (UMK3_DMA,) are accepted as
observed writes. Never promote CPU instruction logs to bus transactions.
"""
from __future__ import annotations
import csv
import io
from collections import Counter
from .dma_trace import _read_events, _hw, analyze_trace

PREFIX='UMK3_DMA,'
MAX_CAPTURE_BYTES=16*1024*1024


def convert_capture(raw:bytes):
    if len(raw)>MAX_CAPTURE_BYTES:raise ValueError('Arquivo acima do limite de 16 MiB')
    try:s=raw.decode('utf-8-sig')
    except UnicodeDecodeError as e:raise ValueError('Arquivo deve ser UTF-8') from e
    extracted=[]
    for line in s.splitlines():
        at=line.find(PREFIX)
        if at<0:continue
        record=line[at+len(PREFIX):].strip()
        fields=next(csv.reader([record]))
        # seq, pc, address, value, operation
        if len(fields)!=5:raise ValueError('Registro UMK3_DMA incompleto: esperado seq,pc,address,value,operation')
        seq,pc,addr,val,op=[p.strip() for p in fields]
        if not seq.startswith('0d') or not seq[2:].isdigit():raise ValueError('Sequência deve ser 0dN')
        if op.lower()!='write':raise ValueError('Somente eventos de escrita são aceitos')
        extracted.append((seq,pc,addr,val,'write'))
    if not extracted:raise ValueError('Não há registros UMK3_DMA no arquivo')
    if len(extracted)>250000:raise ValueError('Mais de 250000 eventos')
    buf=io.StringIO(newline='')
    w=csv.writer(buf,lineterminator='\n')
    w.writerow(('cycle','pc','address','value','operation'))
    w.writerows(extracted)
    result=buf.getvalue().encode('utf-8')
    events,meta=_read_events(result)
    if meta['observed_writes']!=len(extracted):raise ValueError('Conversão inconsistente')
    return result


def capture_audit(raw:bytes):
    events,meta=_read_events(raw)
    dma=analyze_trace(raw,max_results=1000)
    counts=Counter()
    seen=set(); triggers=[]
    for ev in events:
        reg=_hw(ev['address'])
        if reg is not None:
            if 0x4300<=reg<=0x437f:
                ch=(reg-0x4300)//16
                seen.add((ch,(reg-0x4300)%16));counts['dma_register_writes']+=1
            elif reg in (0x2115,0x2116,0x2117):counts['vram_port_setup']+=1
            elif reg==0x420b:
                triggers.append({'seq':ev['index'],'mask':ev['value']})
    issues=[]
    if not events:issues.append('Não há eventos explícitos de escrita.')
    if not triggers:issues.append('Nenhuma ativação MDMAEN ($420B) observada; capture uma transição que carregue gráficos.')
    if len(triggers)>0 and not any((ch,k) in seen for ch in range(8) for k in (2,3,4,5,6)):
        issues.append('Não foram capturados A1T/A1B/DAS; a origem ou tamanho de transferência ficará desconhecido.')
    if not counts['vram_port_setup']:issues.append('VMAIN/VMADD não observados; não é possível validar o endereço VRAM dessa captura.')
    incomplete=sum(bool(x['registers_missing']) for x in dma['transfers'])
    if incomplete:issues.append(f'{incomplete} transferência(s) possuem configurações incompletas.')
    return {'meta':meta,'observed_events':len(events),'dma_triggers':len(triggers),
            'candidate_transfers':len(dma['transfers']),'transfer_count_limited':dma['truncated'],
            'register_writes':dict(counts),'unique_channel_fields':len(seen),
            'issues':issues,'evidence':'observed_register_writes; inferred_dma_transfers',
            'ready_for_codec_identification':False,
            'note':'Mesmo um trace completo de DMA não comprova sozinho o codec gráfico. É necessário rastrear a rotina que produz os bytes transferidos.'}


def capture_plan():
    return {
      'title':'Mesen 2 — Assistente de captura DMA / PPU',
      'targets':[
        {'address':'$00:420B','name':'MDMAEN','purpose':'Ativação DMA (máscara dos canais)'},
        {'address':'$00:4300–$00:437F','name':'DMA channels 0–7','purpose':'DMAP, BBAD, A1T, A1B e DAS'},
        {'address':'$00:2115–$00:2117','name':'VMAIN / VMADD','purpose':'Incremento e posição de VRAM'}],
      'steps':[
        'Abra Ultimate Mortal Kombat 3 Deluxe 2.2 no Mesen 2 e faça um save state antes de abrir a tela de seleção ou iniciar uma luta.',
        'Em Debug → Script Window, abra examples/mesen_dma_capture.lua (script experimental) e execute pelo controle de execução da janela.',
        'Retorne ao jogo e provoque UMA transição que carregue novos gráficos: entrar na seleção, trocar o lutador ou iniciar combate.',
        'Pause a emulação e copie/salve o texto da janela de log do script em um arquivo UTF-8 .txt. Linhas úteis têm o prefixo UMK3_DMA,.',
        'Use o painel v0.8 para converter esse log para CSV e confira a auditoria de cobertura; em seguida analise o CSV na aba DMA Trace v0.7.',
        'Se o script não funcionar na sua versão do Mesen, utilize breakpoints de escrita nos registradores e preencha examples/dma_trace_manual.csv. Não confunda log de instruções com bus writes.',
        'Para correlação com os gráficos, capture WRAM, VRAM, CGRAM e OAM no mesmo estado, sem avançar quadros entre dumps.'
      ],
      'limits':['Lua não foi validado em uma instância Mesen nesta entrega.',
                'O script registra escritas de registradores, não bytes completos da transferência nem algoritmo de descompressão.',
                'A gravação do log depende da interface do Mesen; o Studio não controla o emulador.']}
