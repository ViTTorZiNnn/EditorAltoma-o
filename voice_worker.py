"""Isolated HTTP call, cancellable by the parent without freezing the interface."""
import sys
from pathlib import Path
import core,narration
if __name__=='__main__':
 try:
  req=core.read_json(sys.argv[1])
  if req.get('operation')=='resolve':
   core.write_json(req['path'],narration.resolve_voice(req['config']));sys.exit(0)
  raw=narration.request(req['config'],'/generate',req['payload'],timeout=1800)
  if len(raw)<44 or raw[:4] not in (b'RIFF',b'RF64'):raise ValueError('VoiceStudio não retornou áudio WAV válido.')
  path=Path(req['path']);tmp=path.with_suffix('.partial');tmp.write_bytes(raw);tmp.replace(path)
 except Exception as e:print(str(e),flush=True);sys.exit(1)
