# PC Engine Lab — roadmap nativo de combate e integração com HUD

**Status:** proposto. **Data:** 2026-11-17. Este documento não implica que `pc-engine/` esteja no GitHub. A engine de PC é independente da investigação de ROMs do SNES.

## Arquitetura alvo

```text
Keyboard/Gamepad → Input Adapter → tick input queue
                                   ↓
                                C++ Core
                       state machine / movement / collision / damage
                                   ↓
                           snapshots + native events
                      ┌────────────┴───────────┐
                      ↓                        ↓
            FastAPI replay/compare      runtime frame bridge
                      ↓                        ↓
              Visual Debugger            Playtest Arena
                               ↑
                    HUD project + sprite atlas
```

Definir protocolo de estado versionado e política de compatibilidade retroativa para `ng-state-1` / `ng-lab-view-1`. Se o modo interativo usar endpoint distinto, documentar e testar a coerência da representação de estado.

## V0.4.2 — Native Collision Bridge (primeiro marco)

### Auditoria

Localizar no C++: entidade e coordenadas nativas, volumes de colisão, origem/pivot, movimento Q8, facing, classificação de volumes, momento exato em que o motor resolve contato e dados de evento por tick. **Se não houver volumes, criar instrumentação derivada da lógica real de colisão em vez de atribuir dimensões arbitrárias.**

### Contrato proposto (não implementado)

```json
{
  "schema":"ng-collision-geometry-1",
  "tick":38,
  "coordinate_space":"world_q8",
  "axis":{"x":"right","y":"up"},
  "volumes":[
    {"entity_id":"fighter:0","kind":"hurtbox","x":0,"y":0,"width":256,"height":256,"active":true}
  ],
  "contacts":[
    {"attacker":"fighter:0","defender":"fighter:1","result":"hit","confirmed_by_engine":true}
  ]
}
```

**Todos os valores são ilustrativos**. A representação deve declarar: dimensão e unidade, origem do retângulo, regra de mirror por facing, active frame, ID e estabilidade dos IDs, espaço world/screen, bordas inclusivas/exclusivas e limite de volumes por tick. Eventos de `contacts` só devem vir da resolução de colisão do C++, não do desenho de interseções.

### Testes de aceite

1. Repetir os três cenários baseline de 100 frames e comparar estado e hashes; se instrumentação altera o protocolo de hash, versionar o novo contrato e explicar por que.
2. Validar hitbox/hurtbox com pelo menos um tick de ataque real, um miss e um guard.
3. Confirmar espelhamento por facing e escala Q8 com coordenadas brutas, separadas do canvas de HUD.
4. Confirmar reprodutibilidade entre runs e nenhum contato duplicado no mesmo tick.
5. Sem retângulos inferidos no frontend como se fossem geometria nativa.

## V0.5.0 — Sprite & Animation Studio

Formato de animação versionado: spritesheets e PNGs recortados, anchors de pés, FPS/duração em ticks, orientações, transições, camadas visuais e eventos gráficos. As hitboxes permanecem atributo do gameplay nativo; evitar casar automaticamente volume de colisão com bordas visíveis de PNG.

## V0.6.0 — Combat Runtime

Inputs remapeáveis e fila por tick, relógio de simulação fixo, idle/walk/jump/attack/block/hitstun, integridade de inputs e teste de deterministic replay. Separar debug de física do sincronismo de renderização. A API de replays deve aceitar sequências de inputs controladas e limitadas.

## V0.7.0 — Playtest Arena

Usar cena exportada do HUD como fundo e overlay, sem regravar projeto original. Renderizar sprites com snap/pivot, atualizar vida/timer com estado confirmado, permitir P1/P2, pausa, restart e captura de replay.

## Segurança e preservação

Não versionar ROMs, dumps e backups; não publicar serviço FastAPI em `0.0.0.0` sem autenticação. Preservar os testes de engenharia reversa do SNES. O plano não autoriza alterações nem refatoração de código de pesquisa existente.
