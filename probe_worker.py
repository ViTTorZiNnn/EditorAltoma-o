import sys,json
from pathlib import Path
import core
if __name__=='__main__':Path(sys.argv[2]).write_text(json.dumps(core.probe(sys.argv[1])),encoding='utf-8')
