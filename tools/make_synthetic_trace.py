"""Gera examples/hidden_roster_trace_sintetico.txt — trace SINTÉTICO (não é captura real).

Os PCs e instruções seguem o código estático lido da ROM (docs/EVIDENCIAS.md); os valores de registradores
e de memória são inventados para demonstrar o analisador. Uso: python -m tools.make_synthetic_trace [saida]
"""
import sys
from backend.trace65816 import parse_line

OUT = []
PC = [0]


def at(pc):
    PC[0] = pc


def ins(asm, A=0, X=0, Y=0, S=0x01F3, D=0, DB=0x7E, P='nvmxdIzc', ea=None, val=None, pc=None):
    if pc is not None:
        PC[0] = pc
    mn, _, operand = asm.partition(' ')
    mid = ''
    if ea is not None:
        mid += f' [${ea:06X}]'
    if val is not None:
        mid += f' = ${val:04X}'   # 16 bits (M=0): o trace mostra o conteúdo na largura do acesso
    line = f'{PC[0]:06X} {asm}{mid} A:{A:04X} X:{X:04X} Y:{Y:04X} S:{S:04X} D:{D:04X} DB:{DB:02X} P:{P}'
    OUT.append(line)
    n = parse_line(line, 1)
    PC[0] = (PC[0] & 0xFF0000) | ((PC[0] + n.length) & 0xFFFF)


def main(argv):
    OUT.append('# TRACE SINTETICO — gerado por tools/make_synthetic_trace.py; NAO e uma captura do Mesen.')
    OUT.append('# PCs/instrucoes seguem o codigo estatico da ROM; valores de registradores e memoria sao ficticios.')
    # 1) limpeza geral de WRAM ($80:83F2): STA $7E0000 + MVN colapsado numa linha
    ins('lda #$0000', pc=0x8083F2); ins('tax'); ins('sta $7e0000', A=0)
    ins('lda #$fffe'); ins('txy'); ins('iny', Y=0)
    ins('mvn $7e,$7e', A=0xFFFE, X=0, Y=1)
    ins('lda #$0000', pc=0x808402); ins('tax'); ins('sta $7f0000', A=0)
    ins('lda #$fffe'); ins('txy'); ins('iny', Y=0)
    ins('mvn $7f,$7f', A=0xFFFE, X=0, Y=1)
    ins('jml $8086b1')
    # 2) inicialização em $80:86B1: INC dos dois campos (valor anterior 0)
    ins('inc $3bae', pc=0x8086B1, A=0, ea=0x7E3BAE, val=0x0000)
    ins('inc $3bb0', A=0, ea=0x7E3BB0, val=0x0000)
    # 2b) inicializações fictícias (sem elas, os valores lidos adiante contradiriam a limpeza: o analisador acusaria desvio)
    ins('lda #$0003', pc=0x808700); ins('sta $3a50', A=0x0003, ea=0x7E3A50, val=0x0000)
    ins('lda #$0019'); ins('sta $1c59', A=0x0019, ea=0x7E1C59, val=0x0000)
    ins('lda #$0002'); ins('sta $36d0', A=0x0002, ea=0x7E36D0, val=0x0000)
    # 3) SPC700 intercalado (não é CPU principal)
    OUT.append('0210 mov a,#$00')
    # 4) navegação: cursor 3 (Jax) -> 0x0A (oculto)
    ins('lda ($94)', pc=0x86A383, A=0, ea=0x7E3A50, val=0x0003, D=0x0C00)
    ins('sta $0e', A=0x0003, D=0x0C00, ea=None)
    ins('lda #$000a', pc=0x86A7A6)
    ins('sta ($94)', A=0x000A, ea=0x7E3A50, val=0x0003, D=0x0C00, pc=0x86A7A8)
    ins('rtl')
    # 5) resolução (por tabela) e propagação
    ins('lda $3a50', pc=0x86A164, A=0x000A, ea=0x7E3A50, val=0x000A)
    ins('jsl $86a1f6', A=0x000A)
    ins('tax', A=0x000A, pc=0x86A1F6)
    ins('lda $86a207,x', A=0x000A, X=0x000A, ea=0x86A211, val=0x00FF)
    ins('and #$00ff', A=0x00FF); ins('cmp #$00ff', A=0x00FF); ins('bne $86a206', A=0x00FF)
    ins('lda $1c59', A=0x00FF, ea=0x7E1C59, val=0x0019)
    ins('rtl', A=0x0019)
    ins('sta $36d0', A=0x0019, ea=0x7E36D0, val=0x0002, pc=0x86A16B)
    ins('lda $36d0', pc=0x8894EC, A=0x0019, ea=0x7E36D0, val=0x0019)
    ins('ldx $2a', X=0, ea=0x7E002A, val=0x0000, D=0)
    ins('lda $0a', A=0x0019, D=0)
    ins('sta $52c8,x', pc=0x88980F + 0, A=0x0019, X=0, ea=0x7E52C8, val=0x0000)
    # 6) rotina dos ocultos: $C4:A328 (lê as duas condições), Shao Kahn, depois Motaro
    ins('lda $3bae', pc=0xC4A328, ea=0x7E3BAE, val=0x0001)
    ins('ora $3bb0', A=0x0001, ea=0x7E3BB0, val=0x0001)
    ins('beq $c4a385', A=0x0001, pc=0xC4A32E)
    ins('lda $3bae', pc=0xC4A341, A=0x0001, ea=0x7E3BAE, val=0x0001)
    ins('beq $c4a362', A=0x0001)
    ins('lda #$001b', A=0x0001, pc=0xC4A346)
    ins('sta $1c59', A=0x001B, ea=0x7E1C59, val=0x0019)           # valor anterior 0x19 (Idels)
    ins('lda $3bb0', pc=0xC4A362, A=0x001B, ea=0x7E3BB0, val=0x0001)
    ins('beq $c4a383', A=0x0001)
    ins('lda #$001a', A=0x0001)
    ins('sta $1c59', A=0x001A, ea=0x7E1C59, val=0x001B)           # confirma a escrita anterior (0x1B)
    # 7) Sheeva, Human Smoke, Idels em $FF:FE3E/FE64/FE8A
    ins('lda #$000b', pc=0xFFFE3E, A=0x001A)
    ins('sta $1c59', A=0x000B, ea=0x7E1C59, val=0x001A)
    ins('lda #$0016', pc=0xFFFE64, A=0x000B)
    ins('sta $1c59', A=0x0016, ea=0x7E1C59, val=0x000B)
    ins('lda #$0019', pc=0xFFFE8A, A=0x0016)
    ins('sta $1c59', A=0x0019, ea=0x7E1C59, val=0x0016)
    ins('jsl $88c7b6', A=0x0019)
    ins('rtl', pc=0x88C7B6)
    ins('lda $1c59', pc=0x84A3F4, A=0x0019, ea=0x7E1C59, val=0x0019)   # retorno NÃO volta a $FF:FE95 (redirecionamento)
    open(argv[0] if argv else 'examples/hidden_roster_trace_sintetico.txt', 'w', newline='\n').write('\n'.join(OUT) + '\n')


if __name__ == '__main__':
    main(sys.argv[1:])
