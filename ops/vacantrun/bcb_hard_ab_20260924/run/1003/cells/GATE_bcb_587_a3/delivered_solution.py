import rsa
import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives import padding
from base64 import b64encode

def task_func(file_path):
    # Read the content of the file to be encrypted
    with open(file_path, 'rb') as f:
        data = f.read()

    # Generate RSA keys using the rsa library
    private_key = rsa.newkeys(2048)
    public_key = private_key.get_publickey()

    # Generate AES key and IV for CBC mode
    aes_key = os.urandom(32)
    iv = os.urandom(16)

    # Pad the data for AES block size (128 bits = 16 bytes)
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()

    # Encrypt the data using AES-CBC from cryptography library
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

    # Save the encrypted data (including IV at the beginning) to a file
    encrypted_file_path = "encrypted_file.bin"
    with open(encrypted_file_path, 'wb') as f:
        f.write(iv + encrypted_data)

    # Encrypt the AES key using the RSA public key from rsa library
    # Note: The rsa library's encrypt method takes bytes and returns bytes
    encrypted_aes_key = public_key.encrypt(aes_key)

    # Save the encrypted AES key to a file
    encrypted_key_path = "encrypted_key.bin"
    with open(encrypted_key_path, 'wb') as f:
        f.write(encrypted_aes_key)

    return public_key, encrypted_file_path, encrypted_key_path
