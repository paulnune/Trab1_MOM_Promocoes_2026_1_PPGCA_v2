# Estudo 3 — Assinatura digital com chaves assimétricas

Notas sobre criptografia assimétrica aplicada a assinatura digital.
Aqui o objetivo é provar **integridade** e **autenticidade** de mensagens
com seus próprios arquivos, antes de juntar com o RabbitMQ.

## Referências

- [Documentação cryptography](https://cryptography.io/en/latest/)
- [Hazmat — assimétrica RSA](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/)
- [PKCS#1 (RFC 8017)](https://datatracker.ietf.org/doc/html/rfc8017) — RSA
- [openssl genpkey](https://www.openssl.org/docs/man3.0/man1/openssl-genpkey.html)
- [Java Tutorial — Signature](https://docs.oracle.com/javase/tutorial/security/apisign/)

## Conceito em 2 minutos

**Par de chaves**: duas chaves matematicamente ligadas. **Privada** fica
em segredo. **Pública** distribui livremente.

**Assinatura digital**:

```
Quem manda (produtor):
  mensagem ──[hash SHA-256]──▶ hash ──[RSA com PRIVADA]──▶ assinatura
  Envia: { mensagem, assinatura }

Quem recebe (consumidor):
  1. Pega a mensagem do envelope.
  2. Pega a assinatura do envelope.
  3. Usa a chave PÚBLICA do produtor pra verificar:
     "essa assinatura bate com o hash dessa mensagem?"
  4. Se sim → autêntica e íntegra. Se não → descarta.
```

A mensagem viaja em texto puro. A assinatura prova **quem mandou** e que
**ninguém alterou**, mas qualquer um pode ler. **Isso não é criptografia,
é prova de origem.**

| Operação | Chave usada | O que protege |
|---|---|---|
| Criptografar | pública | Confidencialidade — só o dono da privada lê |
| Assinar | privada | Autenticidade + integridade |

> Analogia SSH: a privada do `~/.ssh/id_rsa` prova que sou eu. Aqui a
> privada do microsserviço prova que **ele** mandou aquela mensagem.

No projeto cada microsserviço tem o seu próprio par. O Gateway assina
com a privada dele, o Promocao verifica com a pública do Gateway, etc.

## Setup

Subdiretório `keys/`:

```bash
mkdir -p keys
```

## Gerar par de chaves com openssl

A geração é **operação**, não código de aplicação. `openssl` é a
ferramenta padrão da indústria.

```bash
# Privada RSA-2048 em PKCS#8
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/teste_priv.pem

# Pública correspondente
openssl rsa -in keys/teste_priv.pem -pubout -out keys/teste_pub.pem

# Privada não pode ser legível pelos outros
chmod 600 keys/teste_priv.pem
```

Resultado:

```bash
ls -la keys/
# -rw-------  teste_priv.pem
# -rw-r--r--  teste_pub.pem

cat keys/teste_priv.pem
# -----BEGIN PRIVATE KEY-----
# ...base64...
# -----END PRIVATE KEY-----
```

A privada está em PKCS#8 (`-----BEGIN PRIVATE KEY-----`). A pública em
SubjectPublicKeyInfo (`-----BEGIN PUBLIC KEY-----`). Formatos modernos
compatíveis com a lib `cryptography` do Python.

## assinar.py

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

# 1. Carrega a privada do PEM.
with open('keys/teste_priv.pem', 'rb') as f:
    chave_privada = serialization.load_pem_private_key(
        f.read(),
        password=None,  # geramos sem senha
    )

# 2. Mensagem que vamos assinar (precisa ser bytes).
mensagem = b'Promocao: Don Quixote 50% off'

# 3. Assina.
#    - padding.PKCS1v15(): esquema de padding clássico.
#    - hashes.SHA256(): hash usado antes de assinar.
#    A lib calcula o hash internamente e assina o hash.
assinatura = chave_privada.sign(
    mensagem,
    padding.PKCS1v15(),
    hashes.SHA256(),
)

print(f'Mensagem: {mensagem!r}')
print(f'Assinatura ({len(assinatura)} bytes em hex):')
print(assinatura.hex())

# Salva em arquivo pra usar no verificar.py
with open('assinatura.bin', 'wb') as f:
    f.write(assinatura)
```

Rodar:

```bash
python assinar.py
```

Resultado:
- Imprime a mensagem.
- Imprime hex de **512 caracteres** (256 bytes — chave de 2048 bits).
- Cria `assinatura.bin` de 256 bytes.

## verificar.py

```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

with open('keys/teste_pub.pem', 'rb') as f:
    chave_publica = serialization.load_pem_public_key(f.read())

with open('assinatura.bin', 'rb') as f:
    assinatura = f.read()

mensagem = b'Promocao: Don Quixote 50% off'   # mesma do assinar.py

# verify() levanta exceção se inválido (não retorna False).
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
```

Rodar:

```bash
python verificar.py
# OK - assinatura válida.
```

## Experimento A — Integridade

E se um adversário alterar a mensagem no caminho?

No `verificar.py`:

```python
mensagem = b'Promocao: Don Quixote 90% off'   # adversário trocou 50 por 90
```

Roda → `FALHOU - assinatura inválida ou mensagem alterada.`

A assinatura foi calculada sobre o hash de `50% off`. Mudar pra `90% off`
muda o hash, e a assinatura não bate mais. **Qualquer byte alterado**
invalida a assinatura — efeito avalanche do SHA-256.

## Experimento B — Autenticidade

E se um impostor tentar forjar uma mensagem com outra chave?

```bash
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/outro_priv.pem
openssl rsa -in keys/outro_priv.pem -pubout -out keys/outro_pub.pem
```

No `verificar.py`, troca a pública lida pra `keys/outro_pub.pem`. Roda
→ `FALHOU`.

A assinatura foi gerada com `teste_priv.pem`. Só `teste_pub.pem`
verifica. `outro_pub.pem` não casa.

## Pontos de defesa

| Pergunta | Resposta curta |
|---|---|
| Por que assinar e não criptografar? | Enunciado pede prova de origem, não sigilo. Criptografar custa sem agregar. |
| Por que tem hash antes da assinatura? | RSA tem limite de tamanho e é lento. Assinar 32 bytes (hash) é padrão. |
| Como cada serviço sabe a pública dos outros? | Diretório `keys/` com todas as públicas. Em produção seria KMS (Vault, AWS KMS). |
| O que acontece se a assinatura falhar? | Evento descartado. Em produção daria pra logar/alertar. |
| Por que `verify()` lança exceção? | Convenção da `cryptography` — força tratamento explícito. |
| Trocar mensagem por outra de mesmo tamanho ainda detecta? | Sim — efeito avalanche do SHA-256. |
| Por que RSA-2048? | Padrão da indústria, equilíbrio segurança × performance. 4096 seria overkill. |

## Cheatsheet de API

| Call | Pra que serve |
|---|---|
| `serialization.load_pem_private_key(pem, password=None)` | Carrega privada do PEM |
| `serialization.load_pem_public_key(pem)` | Carrega pública do PEM |
| `chave_privada.sign(msg, padding.PKCS1v15(), hashes.SHA256())` | Assina (hash interno) |
| `chave_publica.verify(sig, msg, padding.PKCS1v15(), hashes.SHA256())` | Verifica (exceção se falha) |

Constantes que sempre repetem:
- **Algoritmo**: RSA 2048-bit
- **Padding**: PKCS#1 v1.5
- **Hash**: SHA-256

Imports padrão:
```python
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature
```

## O que aprendi

- A privada assina, a pública verifica.
- Assinar é diferente de criptografar — não dá sigilo, dá prova de origem.
- O hash é fundamental: dá tamanho fixo e detecta qualquer alteração.
- `verify()` levanta exceção em vez de retornar False — força capturar
  com `try/except`.
- No próximo estudo, vou juntar com JSON pra criar um envelope assinado
  que vai trafegar no Rabbit.
