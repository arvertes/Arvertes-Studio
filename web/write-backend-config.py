"""Generate public-only build configuration for Studio Web."""
from pathlib import Path
from urllib.parse import urlsplit
import json
import os
import re
import sys


def origin(value):
    try:
        url = urlsplit(value)
        return (url.scheme == "https" and bool(url.hostname) and url.username is None and url.password is None
                and value == f"https://{url.netloc}" and not re.search(r"[\s\\]", value)
                and (url.port is None or 1 <= url.port <= 65535))
    except ValueError:
        return False


api = os.environ.get("ARVERTES_WEB_API_ORIGIN", "")
auth_url = os.environ.get("ARVERTES_WEB_SUPABASE_URL", "")
publishable = os.environ.get("ARVERTES_WEB_SUPABASE_PUBLISHABLE_KEY", "")
if (api and not origin(api)) or (auth_url and not origin(auth_url)):
    raise SystemExit("Use origens HTTPS sem caminhos nem credenciais.")
if (auth_url or publishable) and (
        not api or not auth_url or not re.fullmatch(r"sb_publishable_[a-zA-Z0-9_-]+", publishable)):
    raise SystemExit("A autenticação requer as duas origens e uma chave publicável do Supabase.")
config = {"api": api} if api else None
if auth_url:
    config.update(supabaseUrl=auth_url, supabaseKey=publishable)
Path(sys.argv[1]).write_text("export default " + json.dumps(config) + ";\n", encoding="utf-8")
