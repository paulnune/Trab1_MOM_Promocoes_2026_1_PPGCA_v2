"""
gateway.py - Microsserviço Gateway (interface CLI).

Ponto de entrada do sistema pra usuários (clientes e lojas). Apresenta
um menu no terminal e transforma ações do usuário em eventos:

- Cadastrar promoção  -> publica 'promocao.recebida' (assinado)
- Votar em promoção   -> publica 'promocao.voto' (assinado)
- Listar promoções    -> mostra lista local de 'promocao.publicada' recebidas

O gateway consome 'promocao.publicada' (validando assinatura) e mantém
uma lista local de promoções aprovadas pelo MS Promocao.

Implementação single-thread: usa connection.process_data_events() ao
listar pra drenar mensagens pendentes da fila — atende o enunciado
sem precisar de threads.
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
FILA = 'fila_gateway'

# Estado em memória — promoções validadas pelo Promocao.
# Dict id -> payload (pra busca rápida ao votar).
promocoes_publicadas = {}

# Chave privada do gateway, carregada uma vez.
priv = common.carregar_chave_privada('gateway')


# ====================================================================
# CALLBACK — chamado por process_data_events ao drenar a fila
# ====================================================================
def callback_publicada(ch, method, properties, body):
    """Recebe uma promocao.publicada e adiciona à lista local."""
    try:
        producer, payload = common.desenvelopar(body)
    except (InvalidSignature, FileNotFoundError):
        print('[gateway] promocao.publicada com assinatura inválida — descartando')
        ch.basic_ack(delivery_tag=method.delivery_tag)
        return

    id_promo = payload.get('id')
    if id_promo:
        promocoes_publicadas[id_promo] = payload

    ch.basic_ack(delivery_tag=method.delivery_tag)


# ====================================================================
# AÇÕES DO MENU
# ====================================================================
def cadastrar_promocao(channel):
    """Lê dados via input() e publica promocao.recebida assinada."""
    print('\n--- Cadastrar nova promoção ---')
    id_promo = input('id da promoção (ex: promo-001): ').strip()
    # .lower() porque a categoria vira parte da routing key 'promocao.<categoria>',
    # e topic exchange é case-sensitive — clientes bindam em 'promocao.livro'.
    categoria = input('categoria (ex: livro, jogo): ').strip().lower()
    titulo = input('título: ').strip()

    try:
        preco = float(input('preço (ex: 49,90 ou 49.90): ').strip().replace(',', '.'))
        desconto = int(input('desconto % (ex: 50): ').strip())
    except ValueError:
        print('preço/desconto inválido. operação cancelada.')
        return

    payload = {
        'id': id_promo,
        'categoria': categoria,
        'titulo': titulo,
        'preco': preco,
        'desconto_pct': desconto,
    }

    envelope = common.envelopar(payload, 'gateway', priv)

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key='promocao.recebida',
        body=envelope,
    )
    print(f'  -> publicado promocao.recebida ({id_promo})')


def votar_promocao(channel, connection):
    """Lê id e tipo do voto, publica promocao.voto assinado."""
    # Drena pendências antes de listar, pra mostrar tudo que já foi publicado.
    connection.process_data_events(time_limit=0.5)

    if not promocoes_publicadas:
        print('\n  (nenhuma promoção publicada disponível pra votar — tente listar primeiro)')
        return

    print('\n--- Votar em promoção ---')
    print('Promoções disponíveis:')
    for pid, p in promocoes_publicadas.items():
        print(f'  {pid}  -  {p.get("titulo", "?")} ({p.get("categoria", "?")})')

    id_promo = input('id da promoção: ').strip()
    if id_promo not in promocoes_publicadas:
        print(f'  promoção {id_promo} não está na lista local. cancelado.')
        return

    print('1. positivo')
    print('2. negativo')
    escolha = input('voto: ').strip()
    if escolha == '1':
        voto = 'positivo'
    elif escolha == '2':
        voto = 'negativo'
    else:
        print('  voto inválido. cancelado.')
        return

    # Inclui categoria pra o notificacao saber pra onde rotear o destaque.
    categoria = promocoes_publicadas[id_promo].get('categoria', '')

    payload = {
        'id': id_promo,
        'categoria': categoria,
        'voto': voto,
    }

    envelope = common.envelopar(payload, 'gateway', priv)

    channel.basic_publish(
        exchange=EXCHANGE,
        routing_key='promocao.voto',
        body=envelope,
    )
    print(f'  -> publicado promocao.voto ({id_promo}, {voto})')


def listar_promocoes(connection):
    """Drena mensagens pendentes e imprime a lista local atualizada."""
    # Drena promocao.publicada que chegaram enquanto estávamos no menu.
    connection.process_data_events(time_limit=0.5)

    print('\n--- Promoções publicadas ---')
    if not promocoes_publicadas:
        print('  (nenhuma ainda)')
        return

    for i, (pid, p) in enumerate(promocoes_publicadas.items(), start=1):
        titulo = p.get('titulo', '?')
        categoria = p.get('categoria', '?')
        preco = p.get('preco', '?')
        desconto = p.get('desconto_pct', '?')
        print(f'  {i}. [{pid}] {titulo} ({categoria}) - R$ {preco} ({desconto}% off)')


# ====================================================================
# MAIN
# ====================================================================
if __name__ == '__main__':
    # heartbeat=0 desativa o heartbeat do AMQP. Necessário porque a CLI fica
    # bloqueada em input() entre operações — sem isso, o broker corta a
    # conexão por "missed heartbeats" depois de ~60s parado no menu.
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBIT_HOST, heartbeat=0)
    )
    channel = connection.channel()

    channel.exchange_declare(exchange=EXCHANGE, exchange_type='topic', durable=True)
    channel.queue_declare(queue=FILA, durable=True)
    channel.queue_bind(exchange=EXCHANGE, queue=FILA, routing_key='promocao.publicada')

    # Registra o callback mas NÃO chama start_consuming.
    # process_data_events() vai disparar o callback quando chamado.
    channel.basic_consume(queue=FILA, on_message_callback=callback_publicada, auto_ack=False)

    print(f'[gateway] conectado em {RABBIT_HOST}')

    while True:
        print('\n' + '=' * 40)
        print('   Sistema de Promoções — Gateway')
        print('=' * 40)
        print('1. Cadastrar promoção')
        print('2. Votar em promoção')
        print('3. Listar promoções publicadas')
        print('0. Sair')
        opcao = input('> ').strip()

        if opcao == '1':
            cadastrar_promocao(channel)
        elif opcao == '2':
            votar_promocao(channel, connection)
        elif opcao == '3':
            listar_promocoes(connection)
        elif opcao == '0':
            print('encerrando...')
            break
        else:
            print('opção inválida.')

    connection.close()
