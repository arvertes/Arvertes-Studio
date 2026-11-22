# Atualizar para a segunda etapa

## Windows

1. Feche o Studio. Copie toda a pasta local de configuração do aplicativo, indicada em **Configurações**, para um backup privado. Inclua `settings.json`, `workspace.sqlite3`, `devices.sqlite3` e eventuais arquivos acompanhantes do SQLite. Trate a pasta como dados privados, pois ela inclui a identidade TLS e as referências dos projetos.
2. Extraia o novo ZIP em outra pasta, mantendo `ArvertesStudio.exe` junto de `_internal`. Abra a nova edição com sua conta habitual. O Studio procura a mesma configuração, preserva os rascunhos e acrescenta tabelas da etapa 2.
3. Verifique **Projetos**, **Tarefas** e **Dispositivos** antes de remover a pasta portátil antiga. Para voltar, feche o aplicativo mais novo e abra o executável anterior. Guarde a pasta de dados e o backup. As tabelas novas continuam disponíveis ao retornar à etapa 2.

## Android

- Se o APK foi assinado com a mesma chave da aplicação instalada, instale como atualização. O Android preserva o pareamento no armazenamento do aplicativo.
- Se o Android recusar a atualização por assinatura, mantenha a edição anterior instalada. Use o APK **Etapa 2 — instalação paralela** e faça um novo pareamento apenas para ele. A edição anterior e sua credencial local continuam disponíveis. Os APKs de diagnóstico dos runners podem usar chaves de depuração diferentes.
- O Studio continua reconhecendo o pareamento anterior para mensagens. Para testar o cálculo leve, use o Mobile atualizado ou a instalação paralela.

## Agents

Atualize o checkout privado pela branch de trabalho existente e reconecte-o em **Agentes IA**. O pacote Windows funciona desconectado e não inclui o código ou as dependências do checkout privado.

## Verificação manual na terceira etapa

Descarregue o ZIP e o `UpdateManifest.json` do mesmo workflow **Desktop checks**. Em **Configurações → Atualização manual**, selecione os dois arquivos. O Studio compara SHA-256, versão, revisão e metadados embutidos. A verificação lê o ZIP sem extrair nem executar arquivos. O manifesto é uma evidência de integridade vinculada à origem confiável da CI, sem assinatura de distribuição própria.

Após conferir, faça backup do perfil local e extraia em outra pasta. Preserve a edição anterior para retornar com o mesmo perfil depois de fechar a nova. As tabelas da etapa 3 são aditivas. O Android continua sujeito à verificação de assinatura do sistema e dispõe da instalação paralela para preservar a edição antiga.
