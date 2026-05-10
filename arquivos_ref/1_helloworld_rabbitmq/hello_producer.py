import pika

# 1. Abre conexão TCP com o RabbitMQ que está rodando em localhost:5672
#    ConnectionParameters define onde se conectar (host, porta, credenciais)
#    BlockingConnection é a versão síncrona/simples do pika (suficiente pra esse trabalho)
connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)

# 2. Cria um canal dentro da conexão. Quase tudo a partir daqui é feito no channel.
channel = connection.channel()

# 3. Declara a fila "hello".
#    queue_declare é IDEMPOTENTE: se a fila já existir, não faz nada;
#    se não existir, cria. Por isso a gente declara sempre, no producer E no consumer.
channel.queue_declare(queue='hello')

# 4. Publica a mensagem.
#    exchange='' significa "exchange default" (a sem nome).
#    Quando se usa a exchange default, a routing_key é tratada como nome da fila.
#    body é o conteúdo da mensagem (sempre bytes/str).
channel.basic_publish(
    exchange='',
    routing_key='hello',
    body='Hello World!'
)

print(" [x] Sent 'Hello World!'")

# Fecha a conexão
connection.close()
