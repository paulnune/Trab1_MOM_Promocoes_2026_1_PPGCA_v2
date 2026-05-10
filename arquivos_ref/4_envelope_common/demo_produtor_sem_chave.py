"""
demo.py - prova que common.py funciona.

Simula:
  Gateway monta um payload, envelopa, "envia" (variável local),
  Promocao "recebe", desenvelopa, processa.
"""

from cryptography.exceptions import InvalidSignature

import common

import json


# ------------------------------------------------------------------
# Lado do PRODUTOR (Gateway)
# ------------------------------------------------------------------

print('--- Gateway ---')
gateway_priv = common.carregar_chave_privada('gateway')

payload_gateway = {
    'id': 'promo-001',
    'categoria': 'livro',
    'titulo': 'Don Quixote',
    'preco': 49.90,
    'desconto_pct': 50,
}
envelope = common.envelopar(payload_gateway, 'gateway', gateway_priv)
envelope_adulterado = json.loads(envelope)
envelope_adulterado['producer'] = 'hacker'
envelope = json.dumps(envelope_adulterado).encode('utf-8')

# ------------------------------------------------------------------
# Lado do CONSUMIDOR (Promocao)
# ------------------------------------------------------------------

print('\n--- Promocao ---')
print('Recebeu envelope. Verificando assinatura...')

try:
    producer, payload_recebido = common.desenvelopar(envelope)
    print(f'OK - assinatura válida. Producer: {producer}')
    print(f'Payload extraído: {payload_recebido}')
except InvalidSignature:
    print('FALHOU - assinatura inválida. Descartando.')