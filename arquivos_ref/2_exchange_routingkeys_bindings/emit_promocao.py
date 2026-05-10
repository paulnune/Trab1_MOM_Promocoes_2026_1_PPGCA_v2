import sys
import pika


# 1. Conexão e canal (igual o exemplo do hello world)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# 2. Declara a exchange.
#    - exchange: nome da exchange
#    - exchange_type: tipo, no nosso caso 'topic'
channel.exchange_declare(exchange='promocoes', exchange_type='topic')

# 3. Lê a routing_key e o body da linha de comando.
#    Uso: python emit_promocao.py promocao.livro "50% off em livros"
routing_key = sys.argv[1] if len(sys.argv) > 1 else 'promocao.geral'
message = ' '.join(sys.argv[2:]) or 'Promocao sem descricao'

# 4. Publica na exchange (não vai mais pela default).
channel.basic_publish(
    exchange='promocoes',
    routing_key=routing_key,
    body=message,
)
print(f" [x] Sent {routing_key!r}: {message!r}")
connection.close()