# Estudo comparativo — UMK3 Deluxe 2.2 × Arcade Edition beta 71

Data da pesquisa: 2026-11-10. Fontes: README público do autor e documentação estática do nosso projeto.

## Referência externa confirmada

- Autor: **VrepliroidV / Gabriel Calmon (Repliroid do Futuro)**.
- Repositório público: https://github.com/VrepliroidV/UMK3-SNES---Arcade-Edition
- Distribuição: arquivo `UMK3_arcade_edition.zip` com patch **IPS**, changelog e instruções. Não há código-fonte 65C816 ou tabelas ASM separadas na árvore pública inspecionada.
- Base declarada: **UMK3 (USA), 4 MiB, sem copier header**, MD5 `0644da71f79d405a22934daa1474cefc`.
- Saída beta 71: **8 MiB ExHiROM**, MD5 `b04388eef6071792d85f97dab46c471c`.
- Incorporou trabalho da Deluxe com autorização de Lucas Dext5r. Referência metodológica adicional: hack Genesis UMK3 Arcade por Nemesis_C.

## Mudanças anunciadas e impacto na pesquisa

| Área | Arcade Edition | O que investigar |
|---|---|---|
| Grade | 7/7/5/5/5 (29 casas) | Comprimento, ponteiros e movimentação das tabelas |
| Especiais | Sheeva, Motaro, Shao Kahn, Chameleon, Khameleon com retratos | Se IDs estão associados diretamente a slots ou por camada |
| Human Smoke | SELECT no slot Smoke (desde beta 66) | Separar índice cursor, ID e retrato; não presumir slot próprio |
| Random | Casa `?` | Branch de sorteio e exclusões |
| Trajes | X seleciona segunda cor | Input de seleção e rotinas do cursor |
| Beta 71 | Correção de colisão de variáveis e travamento na torre | Investigar alocação WRAM e compatibilidade com estados |

## Deluxe 2.2 — referência já mapeada

- Índices 0..23, com slot especial `0A` na tabela `86:A207` e valor `FF`.
- Tabelas em `86:A6C6`, `86:A6DE`, `86:A6F6`, `86:A70E`.
- Tratamento do `0A` em `86:A73A`, redirecionamentos para Jax `0003` e Ermac `0010`.
- Caminho especial através de `$7E:1C59`.
- Os endereços acima são **da Deluxe**; não foram verificados na Arcade Edition.

## Protocolo diferencial necessário

1. Preservar a ROM original e conferir seu MD5.
2. Aplicar cada IPS à **mesma ROM de base**, em cópias separadas, quando o patch Deluxe correspondente estiver disponível. A ROM Deluxe 2.2 de 8 MiB já documentada também pode servir de entrada da comparação, desde que seu SHA-256 seja confirmado.
3. Conferir MD5 da Arcade Edition resultante. Registrar SHA-256 das três imagens.
4. Analisar cabeçalho e mapeamento, depois comparar diferenças físicas por banco e produzir um mapa de regiões.
5. Buscar sequências de assinaturas das rotinas da Deluxe no código da Arcade; não presumir endereços CPU idênticos.
6. Localizar o novo leitor de índices e tabelas direcionais; verificar tamanho real, quantidade de posições e tratamento do slot aleatório.
7. Capturar traces Mesen dos dois jogos para as mesmas ações: Jax→Dragão, Ermac→Dragão, Motaro, Shao Kahn, Smoke→Human Smoke e seleção aleatória.
8. Comparar separadamente identidade lógica, índice gráfico do retrato, animações, confirmação e P1/P2.
9. Qualquer patch experimental: gerar backup, manifesto com hashes, patch reversível e regressões em jogo.

**Atenção:** o `tools/rom_patch_lab.py` atual exige arquivos do mesmo tamanho e **não aplica expansão IPS**; não usá-lo para aplicar o patch publicado de 4→8 MiB sem ampliar e testar sua implementação. 

## Situação

**Confirmado por fonte pública:** características, distribuição IPS, hashes e mudanças beta 66/71.

**Confirmado por estudo anterior da Deluxe:** tabela de 24 índices e rotinas `86:A73A` etc.

**Não verificado:** comparação binária da Arcade Edition, posição real de tabelas na ROM nova, código ASM responsável por novos slots, existência de compatibilidade direta com nossos offsets.

**Bloqueio atual:** ROM-base e IPS não estão anexados para processamento no ambiente de análise. A tentativa de buscar o ZIP binário diretamente falhou por indisponibilidade de rede no ambiente de execução; o README do autor foi auditado por GitHub.
