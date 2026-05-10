import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# Declara a MESMA exchange (idempotente).
channel.exchange_declare(exchange='promocoes', exchange_type='topic')

# Cria uma fila ANÔNIMA (nome gerado pelo Rabbit)
# e EXCLUSIVA (some quando este consumer desconectar).
# É o padrão pra "fila própria de cliente":
# cada cliente tem a sua, criada na hora, descartada ao sair.
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

# AGORA O CONCEITO CHAVE: binding.
# A gente diz pro Rabbit: "esta minha fila quer receber tudo da exchange
# 'promocoes' cuja routing_key bata com a binding key abaixo".
# Cliente A quer livro E destaque -> faz 2 bindings na mesma fila.
binding_keys = ['promocao.livro', 'promocao.destaque']
for bk in binding_keys:
    channel.queue_bind(
        exchange='promocoes',
        queue=queue_name,
        routing_key=bk  # esse é o binding key
    )

print(f' [*] Cliente A esperando em {queue_name}. Bindings: {binding_keys}. CTRL+C para sair.')


def callback(ch, method, properties, body):
    # method.routing_key te diz qual key veio (útil pra log/debug)
    print(f" [x] Cliente A recebeu [{method.routing_key}]: {body!r}")


channel.basic_consume(
    queue=queue_name,
    on_message_callback=callback,
    auto_ack=True
)
channel.start_consuming()