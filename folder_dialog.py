"""Windows Vista+ IFileOpenDialog folder picker, isolated STA process."""
import ctypes,sys,json
from ctypes import wintypes

def choose():
    ole=ctypes.OleDLL('ole32');user=ctypes.WinDLL('user32');HRESULT=ctypes.c_long
    class GUID(ctypes.Structure):_fields_=[('a',wintypes.DWORD),('b',wintypes.WORD),('c',wintypes.WORD),('d',ctypes.c_ubyte*8)]
    ole.CLSIDFromString.argtypes=[wintypes.LPCWSTR,ctypes.POINTER(GUID)];ole.CLSIDFromString.restype=HRESULT
    def guid(value):g=GUID();ole.CLSIDFromString(value,ctypes.byref(g));return g
    def method(obj,index,restype,*args):
        table=ctypes.cast(obj,ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        return ctypes.WINFUNCTYPE(restype,ctypes.c_void_p,*args)(table[index])
    ole.CoInitializeEx(None,2);dialog=ctypes.c_void_p();item=ctypes.c_void_p();name=ctypes.c_void_p();owner=None
    ole.CoCreateInstance.argtypes=[ctypes.POINTER(GUID),ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(GUID),ctypes.POINTER(ctypes.c_void_p)];ole.CoCreateInstance.restype=HRESULT
    ole.CoTaskMemFree.argtypes=[ctypes.c_void_p]
    try:
        clsid=guid('{DC1C5A9C-E88A-4DDE-A5A1-60F82A20AEF7}');iid=guid('{D57C7288-D4AD-4768-BE02-9D969532D960}')
        ole.CoCreateInstance(ctypes.byref(clsid),None,1,ctypes.byref(iid),ctypes.byref(dialog))
        method(dialog,9,HRESULT,wintypes.DWORD)(dialog,0x20|0x40|0x8|0x800)
        method(dialog,17,HRESULT,wintypes.LPCWSTR)(dialog,'MontaVideo — Escolha a pasta')
        user.GetForegroundWindow.restype=wintypes.HWND;owner=user.GetForegroundWindow()
        result=method(dialog,3,HRESULT,wintypes.HWND)(dialog,owner)
        if result==-2147023673:return '' # user cancelled
        if result<0:raise OSError('O seletor do Windows falhou: '+str(result))
        result=method(dialog,20,HRESULT,ctypes.POINTER(ctypes.c_void_p))(dialog,ctypes.byref(item))
        if result<0:raise OSError('Nenhuma pasta selecionada.')
        result=method(item,5,HRESULT,wintypes.DWORD,ctypes.POINTER(ctypes.c_void_p))(item,0x80058000,ctypes.byref(name))
        if result<0:raise OSError('Não foi possível obter o caminho da pasta.')
        return ctypes.wstring_at(name)
    finally:
        if name:ole.CoTaskMemFree(name)
        if item:method(item,2,wintypes.ULONG)(item)
        if dialog:method(dialog,2,wintypes.ULONG)(dialog)
        ole.CoUninitialize()
if __name__=='__main__':
    try:
        sys.stdout.reconfigure(encoding='utf-8');print(json.dumps({'path':choose()},ensure_ascii=False))
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
