import ssl
import os
import hashlib

def task_func(client_socket, cert_file, key_file, buffer_size=1024):
    secure_socket = None
    try:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS)
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
        secure_socket = context.wrap_socket(client_socket, server_side=True)
        
        request_bytes = secure_socket.recv(buffer_size)
        if not request_bytes:
            return "Error: No data received"
        
        request = request_bytes.decode('utf-8')
        
        if not os.path.exists(request):
            result = 'File not found'
        else:
            sha256_hash = hashlib.sha256()
            with open(request, "rb") as f:
                for byte_block in iter(lambda: f.read(4096), b""):
                    sha256_hash.update(byte_block)
            result = sha256_hash.hexdigest()
            
        secure_socket.send(result.encode('utf-8'))
        return result
        
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        if secure_socket:
            try:
                secure_socket.send(error_msg.encode('utf-8'))
            except:
                pass
        return error_msg
    finally:
        if secure_socket:
            secure_socket.close()
