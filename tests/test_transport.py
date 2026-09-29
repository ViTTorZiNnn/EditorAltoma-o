import json,sys,threading,unittest
from http.server import BaseHTTPRequestHandler,HTTPServer
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from drift_client import Drift

class TransportTests(unittest.TestCase):
    def test_initialize_auth_and_text_tool_response(self):
        seen=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*a):pass
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                seen.append((self.headers.get('Authorization'),body))
                if body['method']=='notifications/initialized':
                    self.send_response(202);self.end_headers();return
                result={'protocolVersion':'2025-03-26'} if body['method']=='initialize' else {'content':[{'type':'text','text':'{"ok":true,"clips":0}'}]}
                raw=json.dumps({'jsonrpc':'2.0','id':body['id'],'result':result}).encode()
                self.send_response(200);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
        server=HTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            d=Drift(f'http://127.0.0.1:{server.server_port}/mcp','test-secret')
            self.assertEqual(d.call('inspect'),{'ok':True,'clips':0})
            self.assertTrue(all(x[0]=='Bearer test-secret' for x in seen))
            self.assertEqual(seen[-1][1]['params']['name'],'inspect')
        finally:server.shutdown();server.server_close();thread.join()
    def test_reject_remote_token_destination(self):
        with self.assertRaises(ValueError):Drift('http://example.com/mcp','secret')

if __name__=='__main__':unittest.main()
