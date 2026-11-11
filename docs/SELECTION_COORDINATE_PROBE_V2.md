# SEL-002 — Sonda de coordenadas do cursor (Arcade Edition beta 71)

**Status:** Extração estática autenticada e testes sintéticos. **Não** há confirmação dinâmica por trace Mesen.

## Achado verificado contra o IPS oficial

ROM original (MD5 `0644da71f79d405a22934daa1474cefc`) + 7.161 registros IPS resulta em ROM Arcade Edition beta 71 MD5 `b04388eef6071792d85f97dab46c471c`, SHA-256 `60b948a785ed86d927b02ce862c0f37dfbed09ba725ab57902dfd34d1c832d6e`.

A sequência completa de 31 bytes da rotina `47:CF4D` foi verificada. O fluxo estático, assumindo A e X de 16 bits, é:

```asm
47:CF4D PHX
47:CF4E PHY
47:CF4F LDA ($94)         ; cursor (associação ao slot ainda requer trace)
47:CF51 ASL A             ; candidato slot * 2
47:CF52 TAY
47:CF53 LDX $2A          ; valor a observar
47:CF55 PHX
47:CF56 TYX
47:CF57 LDA $47B63B,X   ; tabela B, 29 palavras
47:CF5B PHA
47:CF5C LDA $47B601,X   ; tabela A, 29 palavras
47:CF60 PLY
47:CF61 PLX
47:CF62 STA $3DA8,X     ; destino de memória depende do DBR real
47:CF65 TYA
47:CF66 STA $3F18,X     ; idem
47:CF69 PLY
47:CF6A PLX
47:CF6B RTL
```

A tabela `47:B601` tem X candidatos `18, 68, 118, 168, 218, 268, 318` nas primeiras sete entradas; a tabela `47:B63B` tem valor assinado -157 nas sete primeiras e segue -103, -50, 4, 58 por linhas.

Conclusão **estática**: há 29 pares de palavras, indexados por `slot × 2`, gravados através de `$3DA8,X` e `$3F18,X`. É uma interpretação muito plausível de coordenadas horizontais/verticais, mas deve ser confirmada por dados de execução. Os números não são necessariamente pixels diretos.

## Ferramenta

```powershell
python -m backend.selection_coordinate_probe "arcade-beta71.sfc" --out "coordinates_beta71.json"
```

A ferramenta autentica a ROM e exige que a rotina tenha a assinatura esperada, extraindo as 29 duplas de palavras com valores sem sinal e assinados. Não altera ROM.

## Experimento Mesen SEL-002A

1. No Mesen 2, abrir **Arcade Edition beta 71 autenticada** e entrar na tela de seleção.
2. Breakpoint de execução em `47:CF4D` e nas duas escritas `47:CF62`, `47:CF66`.
3. Quando alcançar `47:CF4F`, registrar **D, DBR, A, X, Y, P e PC**; conferir endereço efetivo de `LDA ($94)`.
4. Em `47:CF57` e `47:CF5C`, conferir acesso à tabela, deslocamento `slot×2` e valores retornados.
5. Em `47:CF62` e `47:CF66`, registrar endereço efetivo de destino, DBR, X, A, largura M e valor anterior e posterior. Não presumir que `$3DA8,X` seja WRAM sem DBR.
6. Capturar WRAM antes e depois de mover cursor de Ermac (índice 10) para Jax (índice 3); exportar dumps **RAW de 131072 bytes** desde `7E:0000`. Registrar o valor efetivo de X no momento de `STA`.

Exemplo de comparação — `--x-register` deve ser o valor **observado**, não estimado:

```powershell
python -m backend.selection_coordinate_probe "arcade-beta71.sfc" `
  --before "sel_before_wram.dmp" --after "sel_after_wram.dmp" `
  --slot 3 --x-register 0x00 --out "sel_002a.json"
```

Se o Mesen mostrar DBR diferente de `7E`, não aplicar a hipótese de comparação com `7E:3DA8` e `7E:3F18` sem estudar o mapeamento de memória do banco efetivo.

## Evidência produzida

- `confirmed`: identidade do arquivo e bytes das estruturas.
- `static inference`: associações entre as tabelas e destinos `STA`.
- `snapshot correlation`: coincidência entre valores antes/depois e os previstos, sem prova de causalidade.
- `execution confirmation`: **pendente**, precisa de trace ou registros do Mesen.

## Segurança / limites

Não inclui ROM, IPS, sprites ou dados binários proprietários. Nunca sobrescreve o JSON de saída. Esta versão não modifica jogo, menu nem gráficos. Capturas do Mesen precisam ser feitas no computador que executa o emulador.

## Execução dos testes

```powershell
python -m pytest -q tests/test_selection_coordinate_probe.py
python -m pytest -q
```

Os cinco testes são sintéticos. Validação adicional independente foi executada localmente usando a ROM beta 71 reconstruída do IPS; os testes da branch publicada ainda dependem da CI.
