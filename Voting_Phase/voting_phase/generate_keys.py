# Voting_Phase/voting_phase/generate_keys.py
import os
from cryptography.hazmat.primitives.asymmetric import rsa, ec
from cryptography.hazmat.primitives import serialization

def generate_votes_keys():
    """
    Generates RSA-4096 keys for Encrypting/Decrypting Votes.
    Target: Confidentiality
    """
    print("Generating Privacy Keys (RSA-4096)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537, # Industry Standard
        key_size=4096,         
    )

    # Saves Private Key
    with open("votes_private.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Saves Public Key
    public_key = private_key.public_key()
    with open("votes_public.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

def generate_poa_keys():
    """
    Generates ECC (SECP256R1) keys for Signing Blocks.
    Target: Integrity & Performance (Smaller signatures)
    """
    print("Generating Authority Keys (ECC SECP256R1)...")
    # Elliptic Curve is faster and has smaller keys than RSA
    private_key = ec.generate_private_key(ec.SECP256R1())

    # Saves Private Key (For Voting Server)
    with open("poa_private.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Saves Public Key
    public_key = private_key.public_key()
    with open("poa_public.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

def generate_uidai_keys():
    """
    Generates RSA-4096 keys for Encrypting/Decrypting Fingerprints.
    Target: Confidentiality
    """
    print("Generating UIDAI Keys (RSA-4096)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537, # Industry Standard
        key_size=4096,         
    )

    # Saves Private Key
    with open("uidai_private.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Saves Public Key
    public_key = private_key.public_key()
    with open("uidai_public.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

def generate_bank_keys():
    """
    Generates RSA-4096 keys for Encrypting/Decrypting Bank data.
    Target: Confidentiality
    """
    print("Generating BANK Keys (RSA-4096)...")
    private_key = rsa.generate_private_key(
        public_exponent=65537, # Industry Standard
        key_size=4096,         
    )

    # Saves Private Key
    with open("bank_private.pem", "wb") as f:
        f.write(private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ))

    # Saves Public Key
    public_key = private_key.public_key()
    with open("bank_public.pem", "wb") as f:
        f.write(public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ))

if __name__ == "__main__":
    generate_votes_keys()
    print("✔ Votes Keys Generated (RSA-4096)")
    
    generate_poa_keys()
    print("✔ POA Keys Generated (ECC P-256)")

    generate_uidai_keys()
    print("✔ UIDAI Keys Generated (RSA-4096)")

    generate_bank_keys()
    print("✔ BANK Keys Generated (RSA-4096)")
    
    print(f"\nKeys saved in: {os.getcwd()}")