"""
promocao.py - Microsserviço Promocao.

Consome mensagens de 'promocao.recebida', valida a assinatura digital,
registra a promoção localmente e publica 'promocao.publicada' (assinada
com a chave privada do promocao).

Mensagens com assinatura inválida ou produtor desconhecido são descartadas.
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
FILA = 'fila_promocao'

# Estado em memória — dict id -> payload da promoção registrada.
# Em produção seria um banco; pra trabalho acadêmico, dict basta.
promocoes_registradas = {}


# ====================================================================
# CARREGAR CHAVE PRÓPRIA (uma vez só, na inicialização)
# ====================================================================
# Carregar do disco é caro. Faz UMA vez aqui e reusa em toda assinatura.
priv = common.carregar_chave_privada('promocao')


# ====================================================================
# CALLBACK — chamado a cada mensagem que chega na fila_promocao
# ====================================================================
def callback(ch, method, properties, body):
    """Processa uma mensagem que chegou na fila_promocao.

    ch         - canal pika (pra dar ack ou publicar)
    method     - metadados da entrega (routing key, delivery tag, etc.)
    properties - propriedades AMQP da mensagem
    body       - bytes da mensagem (o envelope assinado)
    """
    # ----------------------------------------------------------------
    # 1. Validar assinatura.
    # ----------------------------------------------------------------
    # Se falhar (adulteração ou produtor desconhecido), descartamos a
    # mensagem dando ack pra ela sair da fila e retornamos sem processar.
    try:
        producer, payload = common.desenvelopar(body)
    except (InvalidSignature, FileNotFoundError):
        print('[promocao] assinatura inválida — descartando mensagem')
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # ----------------------------------------------------------------
    # 2. Registrar a promoção localmente.
    # ----------------------------------------------------------------
    id_promo = payload['id']
    promocoes_registradas[id_promo] = payload
    print(f'[promocao] promoção {id_promo} registrada (de {producer})')

    # ----------------------------------------------------------------
    # 3. Montar payload de promocao.publicada.
    # ----------------------------------------------------------------
    # Cópia rasa do payload original + marca de status.
    payload_publicada = dict(payload)
    payload_publicada['status'] = 'publicada'

    # ----------------------------------------------------------------
    # 4. Assinar e publicar.
    # ----------------------------------------------------------------
    envelope = common.envelopar(payload_publicada, 'promocao', priv)

    ch.basic_publish(
        exchange=EXCHANGE,
        routing_key='promocao.publicada',
        body=envelope,
    )
    print(f'[promocao] promoção {id_promo} publicada')

    # ----------------------------------------------------------------
    # 5. Ack — confirma processamento bem-sucedido.
    # ----------------------------------------------------------------
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ====================================================================
# MAIN
# ====================================================================
if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()

    # Exchange topic, durable pra sobreviver a restart do Rabbit.
    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)

    # Fila do promocao, durable pelo mesmo motivo.
    channel.queue_declare(queue=FILA, durable=True)

    # Liga a fila à routing key que esse serviço escuta.
    channel.queue_bind(exchange=EXCHANGE, queue=FILA, routing_key='promocao.recebida')

    # auto_ack=False: vamos dar ack manualmente no fim do processamento,
    # pra garantir reentrega caso o serviço caia no meio.
    channel.basic_consume(queue=FILA, on_message_callback=callback, auto_ack=False)

    print(f'[promocao] aguardando mensagens em {FILA} (rabbit={RABBIT_HOST})...')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('\n[promocao] encerrando.')
        connection.close()
