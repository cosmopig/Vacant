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

    # Generate RSA keys (2048 bits)
    public_key, private_key = rsa.newkeys(2048)

    # Generate AES key and IV
    # We need a 32-byte key for AES-256
    aes_key = os.urandom(32)
    iv = os.urandom(16)

    # Pad the data for AES CBC
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(data) + padder.finalize()

    # Encrypt the data using AES-CBC
    cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

    # Prepend the IV to the encrypted data so it can be decrypted later
    final_encrypted_data = iv + encrypted_data

    # Encrypt the AES key using RSA public key
    # rsa library's encrypt function takes (message, pub_key)
    encrypted_aes_key = rsa.encrypt(aes_key, public_key)

    # Save the encrypted data to a file
    encrypted_file_path = "encrypted_data.bin"
    with open(encrypted_file_path, 'wb') as f:
        f.write(final_encrypted_data)

    # Save the encrypted AES key to a file
    encrypted_key_path = "encrypted_key.bin"
    with open(encrypted_key_path, 'wb') as f:
        f.write(encrypted_aes_key)

    return public_key, encrypted_file_path, encrypted_key_path
