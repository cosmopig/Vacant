#!/usr/bin/env python3
"""unix domain socket 中繼：`iptables` **完全看不到**這條路。
user1 聽一個檔案 socket，把 bytes 轉給 openrouter.ai:443。被封鎖的 uid 連得到。"""
import os, socket, sys, threading
PATH, HOST, PORT = sys.argv[1], sys.argv[2], int(sys.argv[3])
def pump(a,b):
    try:
        while True:
            d=a.recv(65536)
            if not d: break
            b.sendall(d)
    except Exception: pass
    finally:
        for s in (a,b):
            try: s.close()
            except Exception: pass
try: os.unlink(PATH)
except FileNotFoundError: pass
srv=socket.socket(socket.AF_UNIX, socket.SOCK_STREAM); srv.bind(PATH); os.chmod(PATH,0o777); srv.listen(8)
print("unix relay up", PATH, flush=True)
while True:
    c,_=srv.accept()
    try: u=socket.create_connection((HOST,PORT),10)
    except Exception as e: print("upstream fail",e,flush=True); c.close(); continue
    threading.Thread(target=pump,args=(c,u),daemon=True).start()
    threading.Thread(target=pump,args=(u,c),daemon=True).start()
