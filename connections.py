"""Credentials persist for this Windows user, independently of program updates."""
import base64,ctypes,json,os
from pathlib import Path
HOME=Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'.local/share')))/'MontaVideo'
FILE=HOME/'conexoes.dpapi'

def _protect(raw,decrypt=False):
    if os.name!='nt':raise ValueError('Guardar chaves com proteção está disponível no Windows.')
    from ctypes import wintypes
    class Blob(ctypes.Structure):_fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]
    buf=ctypes.create_string_buffer(raw);source=Blob(len(raw),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));dest=Blob()
    fn=ctypes.windll.crypt32.CryptUnprotectData if decrypt else ctypes.windll.crypt32.CryptProtectData
    fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
    fn.restype=wintypes.BOOL
    if not fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(dest)):raise ctypes.WinError()
    try:return ctypes.string_at(dest.data,dest.size)
    finally:
        ctypes.windll.kernel32.LocalFree.argtypes=[ctypes.c_void_p]
        ctypes.windll.kernel32.LocalFree(ctypes.cast(dest.data,ctypes.c_void_p))

def load():
    if not FILE.exists():return {}
    return json.loads(_protect(FILE.read_bytes(),True))

def save(values):
    current=load()
    for k in ('token','groq_key','url','pexels_key','pixabay_key','serper_key'):
        value=str(values.get(k,'')).strip()
        if value:current[k]=value
    HOME.mkdir(parents=True,exist_ok=True);tmp=FILE.with_suffix('.tmp')
    tmp.write_bytes(_protect(json.dumps(current).encode()));tmp.replace(FILE)
    return status()

def status():
    try:
        c=load();return {**{k+'_saved':bool(c.get(k+'_key')) for k in ('pexels','pixabay','serper')},'token_saved':bool(c.get('token')),'groq_saved':bool(c.get('groq_key')),'url':c.get('url','http://127.0.0.1:4731/mcp')}
    except Exception:return {'token_saved':False,'groq_saved':False,'warning':'Não foi possível ler as chaves protegidas deste usuário.'}
