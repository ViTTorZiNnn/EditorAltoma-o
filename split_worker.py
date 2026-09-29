"""Same detect-content / split-video sequence as the user's batch."""
import os,sys,subprocess,shutil
from pathlib import Path
import core
if __name__=='__main__':
    source,folder=sys.argv[1:3]
    tools=Path(__file__).resolve().parent/'runtime'/'ffmpeg_tools';tools.mkdir(parents=True,exist_ok=True)
    target=tools/('ffmpeg.exe' if os.name=='nt' else 'ffmpeg')
    if not target.exists():shutil.copy2(core.ffmpeg(),target)
    env=os.environ.copy();env['PATH']=str(tools)+os.pathsep+env.get('PATH','')
    os.environ.update(env)
    from scenedetect.__main__ import main
    sys.argv=['scenedetect','-i',source,'-o',folder,'detect-content','split-video']
    main()
