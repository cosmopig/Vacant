import ssl
import os
import hashlib

def task_func(client_socket, cert_file, key_file, buffer_size=1024):
    secure_socket = None
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        secure_socket = context.wrap_socket(client_socket, server_side=True)
        
        data = secure_socket.recv(buffer_size)
        if not data:
            return "Error: No data received"
        
        request = data.decode('utf-8').strip()
        
        if not os.path.exists(request):
            return "File not found"
        
        sha256_hash = hashlib.sha256()
        with open(request, "rb") as f:
            while True:
                byte_block = f.read(buffer_size)
                if not byte_block:
                    break
                sha256_hash.update(byte_block)
        
        digest = sha256_hash.hexdigest()
        secure_socket.send(digest.encode('utf-8'))
        return digest

    except Exception as e:
        return f"Error: {str(e)}"
    finally:
        if secure_socket:
            secure_socket.close()
