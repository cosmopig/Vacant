import ssl
import os
import hashlib

def task_func(client_socket, cert_file, key_file, buffer_size=1024):
    secure_socket = None
    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        secure_socket = context.wrap_socket(client_socket, server_side=True)
        
        data = secure_socket.recv(buffer_size)
        if not data:
            return "Error: No data received"
        
        request = data.decode('utf-8')
        
        if not os.path.exists(request):
            return 'File not found'
        
        sha256_hash = hashlib.sha256()
        with open(request, 'rb') as f:
            while True:
                chunk = f.read(buffer_size)
                if not chunk:
                    break
                sha256_hash.update(chunk)
        
        result = sha256_hash.hexdigest()
        secure_socket.send(result.encode('utf-8'))
        return result
        
    except Exception as e:
        return f"Error: {e}"
    finally:
        if secure_socket:
            secure_socket.close()
