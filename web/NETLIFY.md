# Publicação da prévia Web
- Plano Free. Sem contratação de adicionais, sem domínio pago, sem conectar o repositório privado dos agentes.
- Importar exclusivamente arvertes/Arvertes-Studio. Selecionar feat/v0.3-web como branch de produção desta prévia, sem mesclar na main.
- Base web, comando bash build-netlify.sh, diretório de publicação dist relativo à base; Node 24. O netlify.toml na raiz define esses valores.
- O build usa Habblaud na revisão MIT já autorizada e executa o leitor GLB antes de publicar. Desativa a sondagem periódica de estado que não existe no frontend estático.
- Somente a saída estática é publicada. Não fornecer credenciais, arquivos de jogo, segredos, tokens Drive ou URLs privadas. Noindex não é autenticação. A prévia não contém backend, GPU ou conexão real ao Drive.
- Conferir orçamento Free e cota; usar domínio gratuito netlify.app. Verificar visual e console do navegador após a publicação.
- Usar previews para mudanças frequentes em vez de publicar toda alteração em produção. Preservar o PR para revisão.
