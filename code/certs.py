#https://www.hubject.com/download-pki

import os
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption


from OpenSSL import crypto

def generate_ecdsa_key():
    key = ec.generate_private_key(ec.SECP256R1(), default_backend())
    
    key_pem = key.private_bytes(encoding=Encoding.PEM, format=PrivateFormat.TraditionalOpenSSL, encryption_algorithm=NoEncryption())
    return crypto.load_privatekey(crypto.FILETYPE_PEM, key_pem)

def generate_self_signed_certificate(valid_days=365):
    # Create a new key pair
    key = generate_ecdsa_key()

    # Create a new self-signed certificate
    cert = crypto.X509()
    #cert.get_subject().CN = common_name
    cert.set_serial_number(1000)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(valid_days * 24 * 60 * 60)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(key)
    cert.sign(key, 'sha256')

    return ([cert], key)

def split_pem_cert_chain(pem_data: str):
    """
    Split a PEM-encoded certificate chain into individual certificates.

    Args:
    - pem_data (str): PEM-encoded certificate chain

    Returns:
    - list of str: List of PEM-encoded individual certificates
    """
    pem_certificates = []
    current_certificate = []

    # Split PEM data into lines
    lines = pem_data.strip().split("\n")

    for line in lines:
        if line.startswith("-----BEGIN CERTIFICATE-----"):
            if current_certificate:
                # Join lines to form the current certificate
                pem_certificates.append("\n".join(current_certificate))
                current_certificate = []
        # Add line to the current certificate
        current_certificate.append(line)
    
    # Append the last certificate
    if current_certificate:
        pem_certificates.append("\n".join(current_certificate))
    
    return pem_certificates

def load_cert_chain():
    folder = os.path.join(os.path.dirname(os.path.realpath(__file__)), "certs/oem")

    with open(folder +  "_chain.pem") as f:
        data = f.read()
        data_certs = split_pem_cert_chain(data)

        certs = [crypto.load_certificate(crypto.FILETYPE_PEM, cert) for cert in data_certs]

    with open(folder +  "_leaf.key") as f:
        key = crypto.load_privatekey(crypto.FILETYPE_PEM, f.read(), b"12345")

    return (certs, key)