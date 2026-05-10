from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# 1. Carrega a chave privada do PEM.
with open('keys/teste_priv.pem', 'rb') as f:
    chave_privada = serialization.load_pem_private_key(
        f.read(),
        password=None,  # geramos sem senha
    )

# 2. A mensagem que vamos assinar.
#    Tem que ser bytes, não str -- por isso o b'...' (ou .encode()).
mensagem = b'Promocao: Don Quixote 50% off'

# 3. Assina.
#    - padding.PKCS1v15(): esquema de padding clássico.
#    - hashes.SHA256(): a função de hash usada antes de assinar.
#    A biblioteca calcula o hash e assina o hash, tudo num call.
assinatura = chave_privada.sign(
    mensagem,
    padding.PKCS1v15(),
    hashes.SHA256(),
)

# 4. Imprime em hex pra ficar legível no terminal.
print(f'Mensagem: {mensagem!r}')
print(f'Assinatura ({len(assinatura)} bytes em hex):')
print(assinatura.hex())

# 5. Salva a assinatura num arquivo pra usar no verificar.py
with open('assinatura.bin', 'wb') as f:
    f.write(assinatura)