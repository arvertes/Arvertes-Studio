# Sprint 8 — Ativação e primeira produção autorizada

## Sequência mínima para o proprietário

1. Em um ambiente de teste, alinhe os SHAs do Agents e do Studio e autentique a conta de teste. O aprovador habilita a branch OAuth do Agents e executa o configurador oficial do projeto. Selecione uma raiz e uma pasta privada `Personagens` destinadas ao teste. O procedimento OAuth está em `docs/DRIVE_SETUP.md` na candidata integrada dos Agents. A configuração disponibiliza as três variáveis do Drive na API de teste. Mantenha os valores no ambiente autorizado. O escopo `drive.file`, a validação de pastas e a cota existentes continuam em vigor.
2. No Desktop a partir do código-fonte, configure o executável do Blender e o checkout do Agents uma vez. No dossiê fictício salvo, escolha **Baixar vínculo para o Desktop**. O arquivo contém o UUID da ficha e a revisão corrente. Evite editar a ficha enquanto produz o pacote vinculado.
3. Em **Tarefas → Inspeções GLB → Produzir personagem localmente**, anexe as imagens e o vínculo, preencha nome e características e escolha o perfil. Selecione uma receita procedural para repetir o cenário imediatamente. Use **GLB fornecido** com um modelo adequado quando houver uma exigência de fidelidade específica. Se selecionar **Imagens → geometria**, Atlas exige um gerador elegível e apresenta as alternativas quando houver bloqueio.
4. Examine frente, perfil, costas, clipes, UV, mapas, rig, LOD e as diferenças em relação às referências. Confirme o parecer da revisão local e salve o ZIP. O estado oficial continua pendente até o aceite técnico e artístico.
5. No mesmo dossiê e na mesma revisão, selecione **Arquivar pacote de produção**. Essa opção atua no navegador autenticado. A API verifica o manifesto, a integridade, o UUID da ficha e a revisão. A confirmação de upload usa leitura de volta do mesmo arquivo pelo SHA-256. O anexo aceita ZIP de até 16 MiB e respeita a cota do dossiê. Reabra a ficha, baixe o pacote e confira o hash. O campo editorial da ficha permanece independente. Uma mudança prévia de revisão exige um novo vínculo.
6. Em um projeto descartável, execute a aceitação da Unreal abaixo com o mesmo pacote. Revise escala, eixo, aparência, contato e deformação. Só depois do cenário fictício completo decida iniciar o personagem oficial com imagens e licença fornecidas pelo proprietário.

O ensaio automatizado já executou sessão sintética, criação de dossiê via Chromium, vínculo, geração procedural, revisão, armazenamento local, arquivo no substituto Drive, nova leitura de metadados e recuperação byte a byte. Iniciar um projeto no editor Unreal, autorizar o OAuth real e aprovar fidelidade continuam ações humanas.

## Ativação de executores

A [matriz pesquisada na Sprint 7](EXECUTORES_3D.md) contém licenças, versões e formatos upstream. As reservas abaixo são critérios do Sentinel local, que incluem margem quando aplicável. Atlas filtra tarefa, número de vistas, formato, qualidade/complexidade, licença, custo zero e recursos observados. Entre opções válidas, prioriza a menor reserva. O catálogo informa expressamente que a seleção ainda exige autorização do operador.

| Executor | Caminho preparado | Condição indispensável |
| --- | --- | --- |
| Blender 5.3 | Processo local verificado. Receita Lite ou reuso de GLB, pacote, clipes e LOD compatíveis com a origem | Blender configurado, duas threads, reserva mínima de 1 GiB acima da reserva do sistema e espaço local |
| TripoSR | Sonda e execução Linux com sandbox sem rede, seguida de pré-validação GLB e pacote Blender | Checkout e runtime confiáveis, pesos locais, licença aprovada, Bubblewrap, CUDA NVIDIA, pelo menos 6.656 MiB de VRAM livre e 3 GiB de RAM acima da reserva |
| Stable Fast 3D | Handoff GLB de uma vista, com hashes e licença revisada | Instalação externa autorizada, cerca de 6 GB de VRAM segundo o upstream. Sem execução gerenciada nesta sprint |
| TRELLIS original | Handoff GLB, inclusive conjunto de vistas conforme a configuração upstream | Cerca de 16 GB de VRAM, versão instalada e revisão de dependências |
| TRELLIS.2 | Handoff GLB de uma vista com material compatível | Linux e NVIDIA com pelo menos 24 GB de VRAM no upstream. O preset de catálogo reserva 25.088 MiB |
| Hunyuan3D 2.1 | Handoff GLB de uma vista, sujeito à revisão de licença da versão e dos territórios | A execução combinada upstream exige cerca de 29 GB de VRAM. A versão 2/2mv tem requisitos e contrato multivista próprios |
| UniRig | Handoff de GLB com rig para inspeção da hierarquia, dos pesos e da compatibilidade | CUDA com pelo menos 8 GB de VRAM no upstream e revisão do pipeline e licenças |
| Ollama | Cliente multimodal loopback. Verifica tamanho, hash e capacidade vision da instalação e usa esquema JSON | Servidor local confiável em modo offline e modelo com tag explícita e licença aprovada, já instalado, até 4 GiB. Reservar no mínimo 4 GiB de RAM ou tamanho dos pesos mais 2 GiB; o Studio não gerencia o processo do daemon |

No Desktop, opcionalmente grave um `production-executors.json` ao lado de `settings.json` na pasta de configuração do Studio. Use caminhos absolutos e tags do instalador local. Esse arquivo guarda configuração e aceite de licença local. A caixa de análise multimodal autoriza o envio da imagem apenas ao daemon loopback confiável, nesse computador. O serviço Ollama ainda deve ser executado sem recursos de nuvem e sob os limites do ambiente do proprietário. No modo CLI, use `--executor-config /caminho/production-executors.json` e, se autorizado, `--analyze-visual`.

```json
{
  "triposr": {
    "checkout": "/caminho/TripoSR",
    "weights": "/caminho/pesos",
    "python": "/caminho/runtime/bin/python",
    "version": "identificador-da-revisao-local",
    "license_reviewed": false
  },
  "ollama": {
    "model": "modelo-local:tag-exata",
    "port": 11434,
    "license_reviewed": false
  }
}
```

Execute `python -m arvertes_desktop.production_tools --blender /caminho/blender --config /caminho/production-executors.json` para inspecionar o estado. A opção `--approved` permite sondas que exigem autorização. O arquivo externo do gerador usa o handoff da Sprint 7, agora aceito para todas as linhas da tabela. Trate nome de versão e licença declarada como evidência de origem e confirme ambos antes de uso oficial. A Sprint 8 continua sem provisionamento remoto. O formato de handoff permite troca de artefatos por uma estação autorizada posteriormente. Evite enviar referências privadas a demonstrações públicas.

Cada observação visual tem estado observado, hipótese ou ausente, hash da referência e hash/tag do modelo. O relatório guarda separadamente o que veio do proprietário. A revisão CLI pode incluir `confirmed_observations` com pares `reference` e `trait`; apenas observações efetivamente entregues pelo executor e vinculadas à revisão podem receber confirmação. Hipóteses permanecem hipóteses. A ausência do Ollama encaminha a leitura visual ao operador.

## Aceitação na Unreal 5.6

Extraia apenas o `asset.zip` de um pacote cuja revisão já foi conferida. Prepare uma pasta nova e guarde o SHA-256 do plano retornado.

```sh
python -m arvertes_desktop.unreal_staging ./asset.zip --output ./ensaio-unreal
export ARVERTES_UNREAL_ACCEPTANCE=DISPOSABLE_PROJECT
export ARVERTES_UNREAL_STAGING=/caminho/absoluto/ensaio-unreal
export ARVERTES_UNREAL_PLAN_SHA256=SHA256_RETORNADO
```

No projeto descartável, habilite Python Editor Script Plugin, selecione o importador FBX legado quando o projeto usar Interchange e execute `scripts/unreal_acceptance.py` no Editor. O projeto deve receber as variáveis de ambiente na inicialização. A integração usa AssetImportTask e FbxImportUI com conversão de unidade e cena. Importa os LODs pelo subsistema de malha esquelética. O resultado registra altura em centímetros, esqueleto, presença dos clipes, contagem de materiais, LODs e mapas. Os mapas externos entram numa pasta separada, com sRGB para Base Color e configuração linear para Normal e ORM. Revise as ligações PBR nos materiais, a orientação, a aparência e os movimentos no nível. A execução prepara objetos em memória num caminho novo e usa `save=False`. O recibo `unreal-result.json` guarda os achados. A ausência da Unreal mantém `unreal_import_pending`. [AssetImportTask](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AssetImportTask?application_version=5.6) · [SkeletalMeshEditorSubsystem](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SkeletalMeshEditorSubsystem?application_version=5.6) · [FbxSkeletalMeshImportData](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/FbxSkeletalMeshImportData?application_version=5.6) · [Ollama Chat API](https://docs.ollama.com/api/chat)

## Laboratório e evidências

`lab_queue enqueue-style ANTES.zip DEPOIS.zip` guarda duas cópias imutáveis de pacotes procedurais locais no laboratório autorizado. `serve --max-seconds N` executa modelagem, rig, PBR, movimento e LOD em ordem, com checkpoint entre métodos e proteção da geração de autorização. Depois de um erro de entrada, duas tentativas bloqueiam o lote. A fila permite quatro pares de até 32 MiB cada. Os métodos registram evidência por hash e atualizam somente o ciclo experimental de seis horas. O modo autônomo compara resultados existentes. As receitas Blender foram produzidas sob autorização local independente e as políticas A/B/C continuam aplicadas.

A marcha do Coral usava juntas e pés ajustados com base na fase, mantendo a raiz praticamente sem translação no plano. O novo Blender mede o pé de apoio no mundo, ajusta o deslocamento do rig e limita a correção em altura. Na mesma geometria, Coral passou de 136,76 para 2,71 mm de arraste amostrado na caminhada, e de 241,89 para 4,53 mm na corrida. A amplitude medida de alguns deslocamentos de junta aumentou. O teste mantém fechamento, pesos e LOD e expõe os valores para revisão de equilíbrio e naturalidade. Não há IK genérico nem contato validado em terrenos reais.

## Integração e reversão

As candidatas locais `integracao/candidata-sprint-8` integram a Sprint 8 sobre as linhas da Sprint 7, incluindo OAuth, recuperação de fichas e privacidade. Valide primeiro Agents #4 e a cadeia #5 a #11 mais a Sprint 8. Valide Studio #7 e #8 e a cadeia #9 a #15 mais a Sprint 8. Preserve os 17 PRs e compare os SHAs. Após revisão explícita, faça uma homologação coordenada da API e do Web com o Desktop da mesma revisão. A alteração de dossiê usa anexos existentes e dispensa migração SQL de produção. O laboratório cria uma tabela SQLite local aditiva. Para reversão, retenha os binários/SHAs homologados, os manifests e a pasta de controle. Reverta a interface antes de desabilitar seu suporte na API e mantenha os pacotes e registros de produção na origem. Ajustes de Drive e deploy são etapas autorizadas à parte. Custo adicional da sprint de R$ 0.

Os testes de aceitação podem ser repetidos com `tests/integration/check_styled_character.py` e `web/tests/backend_browser.py`. Defina `ARVERTES_TEST_CHARACTER_ACCEPTANCE` com objeto JSON contendo `agents`, `python` do Studio e `blender`, além do PostgreSQL local e Chromium indicados em `docs/TESTES.md`. A opção conecta somente o substituto de Drive gerado pelo teste.
