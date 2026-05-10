# Estudo 4 — Envelope assinado e common.py

Junção dos estudos 1-3: o que vai trafegar no Rabbit precisa de um
formato que carregue **conteúdo + identidade do produtor + assinatura**
num único pacote. Aqui crio o `common.py` que os 4 microsserviços do
trabalho vão importar.

## Referências

- [Documentação cryptography (sign/verify)](https://cryptography.io/en/latest/hazmat/primitives/asymmetric/rsa/#signing)
- [Python `json` module](https://docs.python.org/3/library/json.html)
- [Python `base64` module](https://docs.python.org/3/library/base64.html)

## O envelope

Toda mensagem que trafega no Rabbit tem este formato:

```json
{
  "producer": "gateway",
  "payload": "{\"id\":\"abc\",\"categoria\":\"livro\",\"titulo\":\"Don Quixote\"}",
  "signature": "MEYCIQDx...base64..."
}
```

| Campo | Função |
|---|---|
| `producer` | Identifica quem assinou. Consumidor usa pra escolher qual chave pública carregar. |
| `payload` | Conteúdo do evento, **como string JSON**. É o que foi assinado. |
| `signature` | Assinatura RSA dos bytes do `payload`, em base64 pra caber em JSON. |

## Por que payload é string e não objeto aninhado?

**Pra evitar problemas de serialização canônica.** Se o payload fosse
um objeto JSON aninhado, o produtor precisaria serializá-lo de forma
**idêntica** à que o consumidor serializa pra verificar. Qualquer
diferença (chave fora de ordem, espaço extra, vírgula trailing)
quebraria a assinatura.

Com payload como **string**, o que viaja é exatamente o que foi assinado:

```
PRODUTOR:
  payload_dict = {"id": "abc", "titulo": "..."}
  payload_str  = json.dumps(payload_dict)
  signature    = privada.sign(payload_str.encode())
  envelope     = { "producer": ..., "payload": payload_str, "signature": ... }

CONSUMIDOR:
  envelope recebido
  payload_str = envelope["payload"]              # string idêntica
  publica.verify(signature, payload_str.encode())  # bate
  payload_dict = json.loads(payload_str)         # só agora vira dict
```

## Por que ter um common.py?

Os 4 microsserviços e o cliente fazem operações repetidas:
- Carregar a privada do próprio serviço.
- Carregar a pública do serviço que mandou.
- Assinar payloads.
- Verificar envelopes recebidos.

5 arquivos com a mesma cripto = bug garantido. Um `common.py` que todos
importam = código limpo, fácil de explicar na defesa.

## Setup

```bash
mkdir -p keys

# Gera 2 pares — gateway e promocao — pra simular dois MS.
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/gateway_priv.pem
openssl rsa -in keys/gateway_priv.pem -pubout -out keys/gateway_pub.pem
chmod 600 keys/gateway_priv.pem

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out keys/promocao_priv.pem
openssl rsa -in keys/promocao_priv.pem -pubout -out keys/promocao_pub.pem
chmod 600 keys/promocao_priv.pem
```

## common.py

Quatro funções: 2 pra carregar chaves, 1 pra envelopar (produtor), 1 pra
desenvelopar (consumidor).

```python
import base64
import json

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature

KEYS_DIR = 'keys'


def carregar_chave_privada(servico):
    caminho = f'{KEYS_DIR}/{servico}_priv.pem'
    with open(caminho, 'rb') as f:
        return serialization.load_pem_private_key(f.read(), password=None)


def carregar_chave_publica(servico):
    caminho = f'{KEYS_DIR}/{servico}_pub.pem'
    with open(caminho, 'rb') as f:
        return serialization.load_pem_public_key(f.read())


def envelopar(payload, producer, chave_privada):
    # 1. Serializa o payload como string JSON (sort_keys=True garante consistência).
    payload_str = json.dumps(payload, sort_keys=True)

    # 2. Bytes UTF-8 dessa string — é o que vai ser assinado.
    payload_bytes = payload_str.encode('utf-8')

    # 3. Assina (RSA-2048 + PKCS#1 v1.5 + SHA-256).
    assinatura = chave_privada.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    # 4. Monta o envelope (producer, payload string, signature em base64).
    envelope = {
        'producer': producer,
        'payload': payload_str,
        'signature': base64.b64encode(assinatura).decode('ascii'),
    }

    # 5. Serializa o envelope inteiro em bytes pra publicar.
    return json.dumps(envelope).encode('utf-8')


def desenvelopar(envelope_bytes):
    # 1. Parse do envelope.
    envelope = json.loads(envelope_bytes)

    # 2. Extrai os 3 campos.
    producer = envelope['producer']
    payload_str = envelope['payload']
    assinatura = base64.b64decode(envelope['signature'])

    # 3. Carrega a pública do producer.
    chave_publica = carregar_chave_publica(producer)

    # 4. Verifica. Lança InvalidSignature se inválido.
    chave_publica.verify(
        assinatura,
        payload_str.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    # 5. Parse do payload (só DEPOIS de validar).
    payload = json.loads(payload_str)

    return producer, payload
```

Toda a cripto cabe em ~30 linhas úteis. Se ficou maior, algo está errado.

## demo.py — caso feliz

Simula um Gateway envelopando e um Promocao desenvelopando no mesmo
processo:

```python
from cryptography.exceptions import InvalidSignature
import common

# --- Gateway (produtor) ---
print('--- Gateway ---')
gateway_priv = common.carregar_chave_privada('gateway')

payload = {
    'id': 'promo-001',
    'categoria': 'livro',
    'titulo': 'Don Quixote',
    'preco': 49.90,
    'desconto_pct': 50,
}

envelope = common.envelopar(payload, 'gateway', gateway_priv)
print(f'Envelope ({len(envelope)} bytes):')
print(envelope.decode('utf-8'))

# --- Promocao (consumidor) ---
print('\n--- Promocao ---')
print('Recebeu envelope. Verificando...')

try:
    producer, payload_recebido = common.desenvelopar(envelope)
    print(f'OK - producer: {producer}')
    print(f'Payload: {payload_recebido}')
except InvalidSignature:
    print('FALHOU - assinatura inválida.')
```

Resultado:
```
--- Gateway ---
Envelope (516 bytes):
{"producer": "gateway", "payload": "{...}", "signature": "..."}

--- Promocao ---
Recebeu envelope. Verificando...
OK - producer: gateway
Payload: {...}
```

## Experimento A — adulteração do payload

E se um homem-no-meio mexer no envelope?

```python
import json
envelope_dict = json.loads(envelope)
payload_orig = json.loads(envelope_dict['payload'])
payload_orig['desconto_pct'] = 99   # tentou mudar 50 pra 99
envelope_dict['payload'] = json.dumps(payload_orig, sort_keys=True)
envelope = json.dumps(envelope_dict).encode('utf-8')
```

Resultado: `FALHOU - assinatura inválida.`

**Integridade**. O adversário até reformatou o payload, mas não tem a
privada do gateway, então a assinatura não bate.

## Experimento B — troca do producer

E se o adversário só mudar o campo `producer` pra fingir que mandou?

```python
envelope_dict = json.loads(envelope)
envelope_dict['producer'] = 'promocao'   # finge ser o promocao
envelope = json.dumps(envelope_dict).encode('utf-8')
```

Resultado: `FALHOU`.

**Autenticidade**. O `desenvelopar` agora carrega `keys/promocao_pub.pem`,
mas a assinatura foi feita com a privada do gateway. Chaves não casam.

> A defesa NÃO é o campo `producer` — é a **assinatura**. O producer só
> aponta qual pública usar.

## Experimento C — producer inexistente

```python
envelope_dict['producer'] = 'hacker'   # nome inventado
```

Resultado: `FileNotFoundError: keys/hacker_pub.pem`.

Tentativa de fabricar identidade falsa também é detectada — não existe
chave pública pra esse nome, nem chega a verificar.

> Na implementação, capturo `FileNotFoundError` junto com
> `InvalidSignature` e trato como descarte silencioso.

## Pontos de defesa

| Pergunta | Resposta |
|---|---|
| Por que payload string e não objeto JSON aninhado? | Evita problema de serialização canônica. O que viaja é o que foi assinado. |
| Por que `signature` em base64? | Assinatura é binária (256 bytes). JSON só aceita texto. |
| Por que tem o campo `producer`? | Pra escolher qual chave pública carregar. |
| Pode-se confiar no `producer` por si só? | Não — confiança vem da verificação. Producer falso falha porque chaves não casam. |
| O que acontece se assinatura inválida? | Descarta silenciosamente. |
| Por que `desenvelopar` levanta exceção? | Convenção da `cryptography` — força tratamento explícito. |

## Estado final

```
4_envelope_common/
├── readme.md
├── common.py              (~30 linhas úteis)
├── demo.py
├── demo_envelope_adulterado.py
├── demo_produtor_sem_chave.py
├── notas.md
└── keys/
    ├── gateway_priv.pem
    ├── gateway_pub.pem
    ├── promocao_priv.pem
    └── promocao_pub.pem
```

## O que aprendi

- O envelope é um padrão clássico — `{producer, payload, signature}`.
- Payload string evita problema de serialização — é o detalhe que faz
  toda a diferença na hora de verificar.
- `common.py` ganha de longe sobre código duplicado nos serviços.
- Capturar `(InvalidSignature, FileNotFoundError)` cobre adulteração E
  forjar identidade.
- Próximo passo: aplicar tudo isso nos 4 microsserviços do trabalho.
