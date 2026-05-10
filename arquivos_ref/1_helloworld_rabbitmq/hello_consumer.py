import pika  # pyright: ignore[reportMissingModuleSource]

# Mesma conexão e canal que o producer
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# Declara a MESMA fila. Como queue_declare é idempotente, não tem problema
# o producer e o consumer declararem ambos. Garante que a fila exista
# independente de quem rodar primeiro.
channel.queue_declare(queue='hello')

# Função que vai ser chamada toda vez que uma mensagem chegar.
# Os 4 parâmetros são padrão do pika; por enquanto só nos interessa o "body".
def callback(ch, method, properties, body):
    print(f" [x] Received {body!r}")

# Diz ao Rabbit: "consuma da fila 'hello' e chame essa função pra cada mensagem".
# auto_ack=True: o Rabbit considera entregue assim que mandar (sem confirmação explícita).
#                Vamos mudar isso depois, mas pro Hello World tá bom.
channel.basic_consume(
    queue='hello',
    on_message_callback=callback,
    auto_ack=True,
)

print(' [*] Waiting for messages. To exit press CTRL+C')
# Loop infinito que entrega mensagens conforme elas chegam.
channel.start_consuming()