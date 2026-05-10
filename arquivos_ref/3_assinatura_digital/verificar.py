from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

# 1. Carrega a chave PÚBLICA.
with open('keys/teste_pub.pem', 'rb') as f:
    chave_publica = serialization.load_pem_public_key(f.read())

# 2. Carrega a assinatura.
with open('assinatura.bin', 'rb') as f:
    assinatura = f.read()

# 3. A mensagem que esperamos. PRECISA SER EXATAMENTE A MESMA do assinar.py.
mensagem = b'Promocao: Don Quixote 50% off'

# 4. verify() NÃO retorna True/False -- ele LEVANTA EXCEÇÃO se inválido.
#    Esse é o jeito da biblioteca cryptography.
try:
    chave_publica.verify(
        assinatura,
        mensagem,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    print('OK - assinatura válida.')
except InvalidSignature:
    print('FALHOU - assinatura inválida ou mensagem alterada.')