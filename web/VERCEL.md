# Publicação do Studio Web

O projeto existente `arvertes-studio` na Vercel hospeda o frontend em [arvertes-studio.vercel.app](https://arvertes-studio.vercel.app/). A branch de produção é `main` do repositório `arvertes/Arvertes-Studio`. A API continua no [Render](https://arvertes-agents.onrender.com/health), com PostgreSQL e autenticação GitHub via Supabase Auth. O Netlify é a hospedagem anterior e está suspenso.

## Build e configuração

- Use o plano Hobby, preset **Other**, raiz do repositório e Node.js 24.x.
- Preserve o comando `bash web/build-netlify.sh`, a instalação padrão e o diretório de saída `web/dist`. O script usa Bash, Git, Python 3, Node e npm. Ele instala dependências com os lockfiles e monta o cliente Habblaud de uma revisão fixa.
- Configure as três [variáveis públicas](INTEGRACAO.md#ativação-da-api-v1) no ambiente de produção da Vercel. O build publica somente `web/dist`. Credenciais do servidor e do banco ficam no backend.
- No Render, adicione `https://arvertes-studio.vercel.app` à lista `ARVERTES_STUDIO_ORIGINS`, separando as origens por vírgulas. Preserve as entradas existentes, inclusive `https://arvertes-studio.netlify.app`, e a lista de usuários em `ARVERTES_SUPABASE_SUBJECTS`.
- No Supabase Auth, use `https://arvertes-studio.vercel.app` como Site URL e acrescente `https://arvertes-studio.vercel.app/` à lista de redirecionamentos. Preserve os redirecionamentos anteriores e a configuração GitHub.

## Teste e publicação

1. Na raiz, execute `bash web/build-netlify.sh` e `python3 web/tests/browser.py`. A [integração](INTEGRACAO.md#ativação-da-api-v1) descreve a suíte com PostgreSQL e Auth descartáveis.
2. Agrupe alterações pequenas em uma branch de trabalho e valide-as localmente antes de enviar. Use a prévia apenas quando o teste exigir hospedagem. Preserve `main` para versões revisadas. Use `[skip netlify]` no commit de merge enquanto o projeto anterior estiver conectado.
3. Após o merge, acompanhe o deploy automático do SHA da `main` em **Deployments**. Confira o estado e os logs antes de considerar um novo deploy.
4. No domínio oficial, verifique a página inicial, `backend.mjs`, `backend-auth.mjs` e `backend-config.mjs`. Em **Configurações**, entre pelo GitHub com uma conta autorizada e confirme a conexão e o catálogo. Use dados sintéticos para testar gravação, recarga e exportação.
