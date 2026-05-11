"""
notificacao.py - Microsserviço Notificação.

Consome mensagens de 'promocao.publicada' (do MS Promocao) e
'promocao.destaque' (do MS Ranking). Valida a assinatura digital de
ambos os eventos e republica como 'promocao.<categoria>' direcionado
aos clientes consumidores.

Diferente dos outros microsserviços, Notificação NÃO assina os eventos
que publica — conforme o enunciado, é o único caso assim.
"""

import json
import os
import pika

from cryptography.exceptions import InvalidSignature

import common


# ====================================================================
# CONFIGURAÇÃO
# ====================================================================
RABBIT_HOST = os.environ.get('RABBIT_HOST', 'localhost')
EXCHANGE = 'promocoes'
FILA = 'fila_notificacao'

# Cache em memória das promoções já publicadas.
# Usado pra enriquecer o hot deal (que vem do ranking só com {id, categoria, voto})
# com os dados originais da promoção (titulo, preco, desconto_pct).
# Limitação: se esse processo reiniciar, perde o cache. Promoções publicadas
# antes do restart terão hot deal sem título/preço.
promocoes_conhecidas = {}    # id_promo -> payload original


# ====================================================================
# CALLBACK
# ====================================================================
# Não precisa carregar chave privada — Notificação não assina nada.
# Só precisa carregar chaves PÚBLICAS pra validar (e isso o common.py
# já faz internamente no desenvelopar).

def callback(ch, method, properties, body):
    """Processa publicada/destaque e publica notificação por categoria."""
    # 1. Valida assinatura.
    try:
        producer, payload = common.desenvelopar(body)
    except (InvalidSignature, FileNotFoundError):
        print('[notificacao] assinatura inválida — descartando mensagem')
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    # 2. Identifica origem pela routing key da mensagem que chegou.
    routing_origem = method.routing_key

    # Valida campos obrigatórios. Se faltar, descarta sem crashar.
    if 'categoria' not in payload or 'id' not in payload:
        print(f'[notificacao] payload malformado (sem categoria/id) — descartando: {payload}')
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    categoria = payload['categoria']
    id_promo = payload['id']

    # 3. Tratamento por tipo de evento.
    if routing_origem == 'promocao.publicada':
        # Cacheia o payload da promoção pra usar depois no hot deal.
        promocoes_conhecidas[id_promo] = dict(payload)
    elif routing_origem == 'promocao.destaque':
        # Enriquece o payload do destaque com os dados originais da promoção
        # (que o ranking não conhece). Começa do payload cacheado e sobrepõe
        # com o que veio do ranking, pra manter marcador/votos.
        original = promocoes_conhecidas.get(id_promo, {})
        payload = {**original, **payload}
        payload['marcador'] = 'hot deal'

    # 4. Monta a routing key de saída pros clientes.
    #    Ex: categoria='livro' -> 'promocao.livro'
    routing_destino = f'promocao.{categoria}'

    # 5. Publica SEM ASSINAR — JSON puro.
    body_saida = json.dumps(payload).encode('utf-8')

    ch.basic_publish(
        exchange=EXCHANGE,
        routing_key=routing_destino,
        body=body_saida,
    )

    tag = '[HOT DEAL]' if routing_origem == 'promocao.destaque' else ''
    print(f'[notificacao] {id_promo} -> {routing_destino} {tag}')

    # 6. Ack.
    ch.basic_ack(delivery_tag=method.delivery_tag)


# ====================================================================
# MAIN
# ====================================================================
if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()

    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
    channel.queue_declare(queue=FILA, durable=True)

    # DUAS bindings na MESMA fila — esse serviço quer ambos os eventos.
    channel.queue_bind(exchange=EXCHANGE, queue=FILA, routing_key='promocao.publicada')
    channel.queue_bind(exchange=EXCHANGE, queue=FILA, routing_key='promocao.destaque')

    channel.basic_consume(queue=FILA, on_message_callback=callback, auto_ack=False)

    print(f'[notificacao] aguardando publicada/destaque em {FILA} (rabbit={RABBIT_HOST})...')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print('\n[notificacao] encerrando.')
        connection.close()
