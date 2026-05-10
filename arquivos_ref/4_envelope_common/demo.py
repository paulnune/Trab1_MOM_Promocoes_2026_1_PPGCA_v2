"""
demo.py - prova que common.py funciona.

Simula:
  Gateway monta um payload, envelopa, "envia" (variável local),
  Promocao "recebe", desenvelopa, processa.
"""

from cryptography.exceptions import InvalidSignature

import common


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

print(f'Payload original: {payload_gateway}')
print(f'Envelope ({len(envelope)} bytes) pronto pra publicar:')
print(envelope.decode('utf-8'))

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