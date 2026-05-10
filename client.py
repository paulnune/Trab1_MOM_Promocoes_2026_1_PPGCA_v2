"""
client.py - Cliente consumidor de promoções.

Assina (via binding) categorias de interesse hard-coded e imprime no
terminal as notificações que chegam do MS Notificação.

NÃO precisa validar assinatura — Notificação não assina (enunciado).
"""

import json
import os
import pika


# ====================================================================
# CONFIGURAÇÃO
# ====================================================================
RABBIT_HOST = os.environ.get('RABBIT_HOST', 'localhost')
EXCHANGE = 'promocoes'

# Categorias de interesse — hard-coded conforme enunciado permite.
# Pode mudar pra simular outros perfis de cliente.
CATEGORIAS = ['livro', 'jogo']

# Identificador desse cliente (só pra log).
NOME_CLIENTE = os.environ.get('CLIENT_NAME', 'cliente_A')


# ====================================================================
# CALLBACK
# ====================================================================
def callback(ch, method, properties, body):
    """Recebe e imprime uma notificação."""
    payload = json.loads(body)

    routing = method.routing_key
    id_promo = payload.get('id', '?')
    titulo = payload.get('titulo', '?')
    marcador = payload.get('marcador', '')

    # Destaque visual se for hot deal.
    if marcador == 'hot deal':
        print(f'\n  🔥 HOT DEAL  [{routing}]')
    else:
        print(f'\n  📢 promoção  [{routing}]')

    print(f'     id:        {id_promo}')
    print(f'     título:    {titulo}')
    if 'preco' in payload:
        print(f'     preço:     R$ {payload["preco"]}')
    if 'desconto_pct' in payload:
        print(f'     desconto:  {payload["desconto_pct"]}%')

    ch.basic_ack(delivery_tag=method.delivery_tag)


# ====================================================================
# MAIN
# ====================================================================
if __name__ == '__main__':
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBIT_HOST))
    channel = connection.channel()

    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)

    # Fila exclusiva e temporária — cada cliente tem a sua.
    # queue='' faz o Rabbit gerar um nome aleatório.
    # exclusive=True faz a fila ser deletada quando esse cliente desconecta.
    result = channel.queue_declare(queue='', exclusive=True)
    fila_cliente = result.method.queue

    # Binda em cada categoria de interesse.
    for categoria in CATEGORIAS:
        routing = f'promocao.{categoria}'
        channel.queue_bind(exchange=EXCHANGE, queue=fila_cliente, routing_key=routing)
        print(f'[{NOME_CLIENTE}] inscrito em {routing}')

    channel.basic_consume(queue=fila_cliente, on_message_callback=callback, auto_ack=False)

    print(f'[{NOME_CLIENTE}] aguardando notificações... (Ctrl+C pra sair)')
    try:
        channel.start_consuming()
    except KeyboardInterrupt:
        print(f'\n[{NOME_CLIENTE}] encerrando.')
        connection.close()
