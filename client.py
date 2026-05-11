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

# Identificador desse cliente (define quais categorias ele assina).
NOME_CLIENTE = os.environ.get('CLIENT_NAME', 'cliente_ambos')

# Mapa de perfil → categorias de interesse.
# Pra simular outros perfis, adicione entradas aqui e use CLIENT_NAME=...
PERFIS = {
    'cliente_jogo':  ['jogo'],
    'cliente_livro': ['livro'],
    'cliente_ambos': ['livro', 'jogo'],
}

# Se o nome não estiver no mapa, cai no padrão (assina tudo).
CATEGORIAS = PERFIS.get(NOME_CLIENTE, ['livro', 'jogo'])


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
