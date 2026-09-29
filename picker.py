"""Owned native dialogs for desktop; isolated fallback for browser mode."""
import json
from pathlib import Path
import subprocess
import sys
import threading

WINDOW = None
_GATE = threading.Lock()
FILTERS = {
    'audio': ('Áudio (*.mp3;*.wav;*.m4a;*.aac;*.flac;*.ogg;*.opus)', 'Todos os arquivos (*.*)'),
    'srt': ('Legenda (*.srt)',),
    'media': ('Mídia (*.mp4;*.mov;*.mkv;*.webm;*.jpg;*.jpeg;*.png;*.webp)', 'Todos os arquivos (*.*)'),
}

def choose(kind):
    if kind not in ('folder', *FILTERS):
        raise ValueError('Tipo de seleção inválido.')
    if not _GATE.acquire(blocking=False):
        raise ValueError('Já existe uma janela de seleção aberta. Conclua ou cancele essa janela.')
    try:
        if kind=='folder' and sys.platform=='win32':
            try:p=subprocess.run([sys.executable,str(Path(__file__).with_name('folder_dialog.py'))],stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=120)
            except subprocess.TimeoutExpired:raise ValueError('A seleção não foi concluída em 2 minutos. Tente novamente.') from None
            if p.returncode:raise ValueError('Seletor de pasta: '+p.stderr.decode('utf-8','replace')[-500:])
            return json.loads(p.stdout.decode('utf-8-sig'))
        if WINDOW is not None:
            import webview
            # pywebview owns the dialog and dispatches it onto the GUI thread.
            result = WINDOW.create_file_dialog(
                webview.FOLDER_DIALOG if kind == 'folder' else webview.OPEN_DIALOG,
                allow_multiple=False, file_types=FILTERS.get(kind, ()))
            return {'path': result[0] if result else ''}
        if sys.platform != 'win32':
            raise ValueError('Seletor nativo disponível no Windows.')
        try:
            p = subprocess.run(['powershell', '-NoProfile', '-STA', '-ExecutionPolicy', 'Bypass',
                '-File', str(Path(__file__).with_name('selecionar.ps1')), '-Kind', kind],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=120)
        except subprocess.TimeoutExpired:
            raise ValueError('O seletor não respondeu em 2 minutos. Tente novamente ou abra pelo INICIAR.bat.') from None
        if p.returncode:
            raise ValueError('Não foi possível abrir o seletor. Tente abrir pelo INICIAR.bat.')
        return json.loads(p.stdout.decode('utf-8-sig'))
    finally:
        _GATE.release()
