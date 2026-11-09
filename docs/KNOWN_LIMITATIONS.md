# Limitações conhecidas

## Segurança e arquitetura
Sessão única global, sem autenticação ou isolamento multiusuário; utilizar **somente em localhost**. Não é seguro transformar a aplicação atual num serviço público.

## Disassembler
A evolução do PC na fronteira dos bancos foi corrigida na v1.0.1. Ainda falta modelar carry para XCE, estados completos em saltos indiretos e uma análise 65C816 exaustiva.

## Gráficos
A reprodução de OAM depende de registradores PPU, como OBSEL, não presentes em todas as capturas. Sprites podem aparecer fragmentados. Não há codec proprietário confirmado, nem editor com reinserção na ROM.

## Captura
`emu.getState()` pode retornar campos diferentes entre versões Mesen; o PC capturado é contexto, não prova de instrução. A integração Lua precisa de teste com emulador real.

## Validação
Passar na suíte Pytest não comprova execução no Windows nem decodificação total da ROM. Os IDs de personagens não confirmados permanecem candidatos.
