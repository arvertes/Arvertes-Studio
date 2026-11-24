"""Generate public-only build configuration for Studio Web."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import sys

names = {"api": "ARVERTES_WEB_API_ORIGIN", "supabaseUrl": "ARVERTES_WEB_SUPABASE_URL",
         "supabaseKey": "ARVERTES_WEB_SUPABASE_PUBLISHABLE_KEY"}
config = {key: os.environ.get(name, "") for key, name in names.items()}
if any(config.values()):
    if not all(config.values()) or not config["supabaseKey"].startswith("sb_publishable_"):
        raise SystemExit("A integração requer duas origens HTTPS e uma chave publicável do Supabase.")
    for key in ("api", "supabaseUrl"):
        value = config[key]
        url = urlsplit(value)
        if url.scheme != "https" or not url.hostname or url.username or url.password or value != f"https://{url.netloc}":
            raise SystemExit("Use origens HTTPS sem caminhos nem credenciais.")
else:
    config = None
Path(sys.argv[1]).write_text("export default " + json.dumps(config) + ";\n", encoding="utf-8")
