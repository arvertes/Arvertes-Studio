# Relatório da Sprint 4

A Sprint 4 parte da Sprint 3 em ambos os repositórios. A fundação combina um laboratório Web local com contratos de produção, qualidade e escala para os 26 agentes. As metas de longo prazo são propostas de arquitetura. A expansão de hardware, a ativação de serviços e as alterações em produção continuam sob controle do proprietário. Custo adicional de R$ 0.

## Resultados

| Ensaio real | Antes | Depois | Decisão |
| --- | --- | --- | --- |
| Manequim sintético | 87 triângulos, 3 faces duplicadas, 2.287 bytes de malha JSON | 84 triângulos, 0 duplicatas, 2.263 bytes de malha JSON | Revisão sintética 2 criada sob política explícita. A reversão restaurou a revisão 1 e reteve a 2 |
| Grade sintética | 3.203 triângulos, 3 faces duplicadas, 74.718 bytes de malha JSON | 3.200 triângulos, 0 duplicatas, 74.690 bytes de malha JSON | Resultado registrado, com revisão humana pendente. Uma tentativa interrompida foi retomada |
| Superfície de controle | 12 triângulos, 0 duplicatas | 12 triângulos, 0 duplicatas | Evidência de ausência de melhoria. Nenhuma revisão criada no teste |

O Chromium executou o worker de verdade para o manequim e a grade. A comparação preservou o conjunto de faces orientadas e as coordenadas. A duração por fixture e a decisão constam no diário exportado. O Blender 5.3.0 reimportou os GLBs exportados e verificou as contagens. Os dados não medem equivalência visual ou desempenho no Unreal.

Arquivos produzidos pelo navegador na suíte sintética.

- `arvertes-manequim-experimental.glb` e `arvertes-grade-experimental.glb`, derivados das fixtures.
- `arvertes-fixture.wav`, PCM mono de 16 kHz, 0,25 s.
- `arvertes-evidencias-laboratorio.json`, com medições, tentativas interrompidas, revisão, reversão e digests.

### Evidências de proteção

Uma reserva ocupada bloqueou o início de uma segunda execução. A interrupção por prioridade do AutoPipeline encerrou o worker, preservou a revisão anterior e evitou gravação de um resultado tardio. A recarga reabriu a fila e o teste retomou somente a fixture sem checkpoint concluído. A fila padrão do Studio foi comparada antes e depois e permaneceu idêntica. Os testes recusaram gasto, promoção sem política, autorização de código e alteração do alvo oficial.

O contador de seis horas cruzou dois limiares em teste com relógio controlado. O primeiro registrou uma melhora, o segundo registrou ausência de melhora. As execuções reais da demonstração duraram milissegundos. Os testes em escalas superiores usaram somente metadados, com contadores maiores que os inteiros exatos do JavaScript e verificação real por streaming em uma amostra de bytes.

### Testes

| Área | Verificação local |
| --- | --- |
| Agents | 100 testes com SQLite e PostgreSQL descartável |
| Studio Web | Build, 38 testes Node, dois scripts de verificação e oito cenários Chromium, incluindo viewport móvel |
| Integração autenticada | Chromium, API e PostgreSQL descartável com conta sintética |
| Studio Desktop | 20 testes unitários, 37 testes Desktop |
| Blender | Nove testes headless no Blender 5.3.0 `02f0899d78e3`, importação dos dois GLBs da sprint e produção e reimportação dos pacotes da Sprint 3 |

## Decisões e integração futura

- O laboratório usa a [política e o contrato locais](LABORATORIO_EXPERIMENTAL.md). A autorização experimental preserva código, dados oficiais e cânone.
- O catálogo do Agents mantém os oito departamentos, eixos gráficos independentes e verificação segmentada. A massa de dados que o protótipo manipula é pequena. Distribuição real, renderização, processamento fora da RAM, telemetria de GPU/VRAM, LODs deformáveis e integração no Unreal dependem de validação própria.
- A produção oficial de Sabaeu e Lídia e a curadoria da Biblioteca Mestra Lite aguardam as decisões do proprietário. Os assets e as licenças de teste são sintéticos.
- As branches `codex/sprint-4` comparam a Sprint 4 com `codex/sprint-3`. Os nove PRs pendentes mantêm suas branches e aprovações separadas. O encadeamento de Agents é #5 → #6 → #7 → Sprint 4. O de Studio é #9 → #10 → #11 → Sprint 4. OAuth (#4), recuperação de fichas (#7 Studio) e privacidade (#8 Studio) seguem trilhas independentes.
- Para integrar no futuro, revisar as trilhas independentes e os commits dependentes na ordem da pilha aprovada, refazer a verificação textual e executar a CI do commit exato em branch de revisão. O aceite requer testes de navegador e Desktop, testes das integrações habilitadas, Blender e validação do pacote no motor de destino. Aprovação e publicação são decisões separadas. A CI remota ficou dispensada nestes rascunhos em favor dos testes locais.
