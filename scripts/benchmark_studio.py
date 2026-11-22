import json
from tempfile import TemporaryDirectory
import time
import sys

start=time.perf_counter()
import psutil
from PySide6.QtWidgets import QApplication
from arvertes_desktop.window import StudioWindow
app=QApplication([])
process=psutil.Process()
with TemporaryDirectory() as path:
    w=StudioWindow(config_dir=path)
    w.show()
    app.processEvents()
    def measure():
        children=[p for p in process.children(recursive=True) if p.is_running()]
        return round(sum(p.memory_info().rss for p in [process,*children])/1048576, 2)
    start_ms=round(1000*(time.perf_counter()-start),2)
    cold=measure()
    begin=time.perf_counter()
    w._navigate("office")
    app.processEvents()
    office=measure()
    print(json.dumps(dict(start_ms=start_ms,home_mib=cold,office_mib=office,office_ms=round(1000*(time.perf_counter()-begin),2),
          tls_loaded="arvertes_desktop.network" in sys.modules,renderer_loaded="PySide6.QtWebEngineWidgets" in sys.modules)))
    w.close()
