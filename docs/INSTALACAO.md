# Instalar o Arvertes Studio no Blender

Use o [Blender 5.3.0](https://download.blender.org/release/Blender5.3/) e uma cópia do repositório. Você pode gerar um ZIP de desenvolvimento ou ativar o código direto pelo console do Blender. Ambos os caminhos funcionam offline após obter esses arquivos.

## Instalação local pelo ZIP de desenvolvimento

1. No terminal, entre na raiz do repositório e gere o pacote com o Python disponível no sistema.

   ```sh
   python scripts/empacotar_desenvolvimento.py
   ```

2. No Blender, abra **Editar → Preferências → Add-ons**. Abra o menu do canto superior direito e escolha **Instalar do disco**. Selecione `dist/arvertes_studio-0.1.0-dev.zip`.
3. Procure **Arvertes Studio** na lista de add-ons e habilite-o. Salve as preferências para manter a ativação em sessões futuras se o salvamento automático das preferências estiver desativado.
4. Na **Vista 3D**, pressione `N` para abrir a barra lateral e selecione a aba **Arvertes Studio**.

Os nomes de menus do Blender seguem o idioma configurado no aplicativo. A aba da ferramenta exibe os controles em português brasileiro.

## Ativação temporária a partir do código-fonte

No Blender, abra o **Console Python** com `Shift+F4`. Substitua o caminho do exemplo pela raiz do seu repositório e execute o comando.

```python
import sys; sys.path.insert(0, r'/caminho/Arvertes-Studio'); import arvertes_studio; arvertes_studio.register()
```

Volte à Vista 3D com `Shift+F5` e abra a barra lateral com `N`. Execute `arvertes_studio.unregister()` no console caso queira desativar a ferramenta durante a sessão.

## Primeira importação

Use o **Modo Objeto** na Vista 3D.

1. Entre no **Modo Objeto** e, na aba **Arvertes Studio**, clique em **Importar GLB**. Escolha um arquivo local. A coleção da importação aparecerá no seletor **Asset**.
2. Em **Organização**, clique na linha da malha e use **Selecionar** ou **Renomear**. Defina a categoria no menu **Categoria** ou consulte uma sugestão em **Sugerir categoria**. Examine a justificativa antes de clicar em **Aplicar categoria**. Use **Organizar por categoria** para distribuir as peças em subcoleções. Salve o `.blend` para manter as classificações e as alterações feitas no Blender.
3. Em **Análise e relatório**, escolha se quer **Incluir geometria avaliada** e clique em **Analisar asset**. A aba exibe o resultado da última análise. Use **Exportar JSON** para analisar o estado atual e salvar o inventário e seus avisos em um arquivo local.

## Pacote nativo de extensão

O manifesto-modelo em `arvertes_studio/blender_manifest.toml.example` reúne os metadados iniciais. O campo obrigatório `license` depende da decisão do responsável pelo projeto. O empacotador nativo valida o campo antes de produzir o ZIP de extensão. A plataforma oficial ainda aplica sua própria política de licenciamento para add-ons. [Manual do manifesto](https://docs.blender.org/manual/en/5.3/advanced/extensions/getting_started.html#manifest) · [Licenças da plataforma](https://docs.blender.org/manual/en/5.3/advanced/extensions/licenses.html)
