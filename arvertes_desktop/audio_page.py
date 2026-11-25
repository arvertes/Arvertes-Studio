"""Medição leve de metadados WAV para consulta ao Pulse."""
from pathlib import Path
import json
import wave

from PySide6.QtWidgets import QFileDialog, QPlainTextEdit

from .pages import button, plain


def read_wav(path):
    source = Path(path)
    if source.suffix.casefold() != ".wav" or not source.is_file() or source.drive.startswith("\\"):
        raise ValueError("Selecione um arquivo WAV PCM local.")
    try:
        with wave.open(str(source), "rb") as handle:
            return {"channels": handle.getnchannels(), "rate_hz": handle.getframerate(),
                    "sample_width": handle.getsampwidth(), "frames": handle.getnframes()}
    except (wave.Error, EOFError) as error:
        raise ValueError("Cabeçalho WAV PCM inválido.") from error


def build_audio(layout, bridge):
    layout.addWidget(plain("Pulse lê o cabeçalho WAV e verifica taxa, canais e profundidade."))
    output = QPlainTextEdit()
    output.setReadOnly(True)

    def inspect():
        source, _ = QFileDialog.getOpenFileName(output, "Selecionar áudio", "", "WAV (*.wav)")
        if source:
            try:
                metadata = read_wav(source)
                output.setPlainText(json.dumps(metadata, ensure_ascii=False, indent=2))
                if bridge.connected:
                    bridge.call("inspect_audio", {"metadata": metadata},
                                lambda result: output.setPlainText(json.dumps(result, ensure_ascii=False, indent=2)),
                                failed=output.setPlainText, quiet=True)
            except (OSError, ValueError) as error:
                output.setPlainText(str(error))

    layout.addWidget(button("Medir WAV local", inspect))
    layout.addWidget(output, 1)
