import rsa
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from base64 import b64encode

def task_func(file_path):
    # 1. Generate RSA keys using the rsa library
    pub, priv = rsa.newkeys(2048)
    
    # 2. Read the file content
    with open(file_path, 'rb') as f:
        data = f.read()
    
    # 3. AES encryption using cryptography library
    aes_key = os.urandom(32) # 256 bits
    iv = os.urandom(16)       # 128 bits block size
    
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()
    
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()
    
    # Prepend IV to the encrypted data so it can be decrypted later
    final_encrypted_data = iv + encrypted_data
    
    # 4. Save the encrypted file
    encrypted_file_name = "encrypted_file.bin"
    with open(encrypted_file_name, 'wb') as f:
        f.write(final_encrypted_data)
    
    # 5. Encrypt the AES key with RSA public key using rsa library
    # The rsa library's pub.encrypt uses PKCS1 v1.5 by default
    encrypted_aes_key = pub.encrypt(aes_key)
    
    # 6. Save the encrypted AES key
    encrypted_key_name = "encrypted_key.bin"
    with open(encrypted_key_name, 'wb') as f:
        f.write(encrypted_aes_key)
    
    return pub, encrypted_file_name, encrypted_key_name
