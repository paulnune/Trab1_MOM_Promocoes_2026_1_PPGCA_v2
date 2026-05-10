"""
ranking.py - Microsserviço Ranking.

Consome mensagens de 'promocao.voto', valida a assinatura digital,
atualiza o contador de votos da promoção. Quando uma promoção atinge
o limite de votos positivos, publica 'promocao.destaque' (hot deal),
assinada com a chave privada do ranking.

Mensagens com assinatura inválida são descartadas.
"""

import os
import pika

from cryptography.exceptions import InvalidSignature

import common


# ====================================================================
# CONFIGURAÇÃO
# ====================================================================
RABBIT_HOST = os.environ.get('RABBIT_HOST', 'localhost')
EXCHANGE = 'promocoes'
FILA = 'fila_ranking'

# Quantidade de votos positivos pra promoção virar hot deal.
LIMITE_HOT_DEAL = 5

# Estado em memória.
votos_por_promocao = {}    # dict: id_promo -> contador (int)
ja_destacadas = set()      # set: ids que já foram publicadas como destaque


# ====================================================================
# CARREGAR CHAVE PRÓPRIA
# ====================================================================
priv = common.carregar_chave_privada('ranking')


# ====================================================================
# CALLBACK
# ====================================================================
def callback(ch, method, properties, body):
    """Processa um voto recebido."""
    # 1. Valida assinatura.
    try:
        producer, payload = common.desenvelopar(body)
    except (InvalidSignature, FileNotFoundError):
        print('[ranking] assinatura inválida — descartando mensagem')
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # 2. Extrai dados do voto.
    id_promo = payload['id']
    tipo_voto = payload['voto']      # 'positivo' ou 'negativo'

    # 3. Atualiza contador.
    # dict.get(chave, default) retorna o valor se existir, senão o default.
    contador_atual = votos_por_promocao.get(id_promo, 0)
    if tipo_voto == 'positivo':
        contador_atual += 1
    elif tipo_voto == 'negativo':
        contador_atual -= 1
    votos_por_promocao[id_promo] = contador_atual

    print(f'[ranking] voto {tipo_voto} em {id_promo} — total: {contador_atual}')

    # 4. Verifica se virou hot deal.
    # Idempotência: só publica destaque UMA vez por promoção.
    if contador_atual >= LIMITE_HOT_DEAL and id_promo not in ja_destacadas:
        payload_destaque = dict(payload)
        payload_destaque['marcador'] = 'hot deal'
        payload_destaque['votos'] = contador_atual

        envelope = common.envelopar(payload_destaque, 'ranking', priv)

        ch.basic_publish(
            exchange=EXCHANGE,
            routing_key='promocao.destaque',
            body=envelope,
        )
        ja_destacadas.add(id_promo)
        print(f'[ranking] *** {id_promo} virou HOT DEAL ***')

    # 5. Ack.
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ====================================================================
# MAIN
# ====================================================================
if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()

    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
    channel.queue_declare(queue=FILA, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=FILA, routing_key='promocao.voto')

    channel.basic_consume(queue=FILA, on_message_callback=callback, auto_ack=False)

    print(f'[ranking] aguardando votos em {FILA} (rabbit={RABBIT_HOST}, limite={LIMITE_HOT_DEAL})...')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('\n[ranking] encerrando.')
        connection.close()
