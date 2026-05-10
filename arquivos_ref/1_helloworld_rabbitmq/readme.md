# Estudo 1 — Hello World RabbitMQ

Notas do tutorial oficial 1 do RabbitMQ ([Python](https://www.rabbitmq.com/tutorials/tutorial-one-python.html)),
adaptado como ponto de partida pro trabalho. Aqui o objetivo é só
provar que consigo conectar e trocar uma mensagem.

São dois arquivos descartáveis (`hello_producer.py` e `hello_consumer.py`).
Não fazem parte do trabalho final.

## Referências

- [RabbitMQ Tutorial 1 (Python)](https://www.rabbitmq.com/tutorials/tutorial-one-python.html)
- [Documentação do pika](https://pika.readthedocs.io/en/stable/)
- [Painel de gerenciamento](https://www.rabbitmq.com/management.html)

## Conceitos

Quatro abstrações aparecem em qualquer programa pika:

- **Connection** — conexão TCP com o broker. Análogo a uma sessão SSH.
- **Channel** — sub-conexão lógica dentro da connection. Quase tudo é
  feito via channel.
- **Queue** — fila onde as mensagens ficam esperando consumidor.
- **Exchange** — quem decide pra qual fila a mensagem vai. No Hello
  World a gente usa a default (sem nome), que entrega pelo nome da fila.

Por que tem exchange se a mensagem vai direto pra fila? Porque toda
mensagem no RabbitMQ passa por uma exchange. Quando se "publica numa
fila", na verdade se publica na default informando o nome da fila como
routing key. A default tem binding automático com toda fila pelo nome.

## hello_producer.py

```python
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# queue_declare é idempotente: cria se não existe, ignora se existe.
channel.queue_declare(queue='hello')

# exchange='' = default; routing_key vira nome da fila.
channel.basic_publish(
    exchange='',
    routing_key='hello',
    body='Hello World!'
)
print(" [x] Sent 'Hello World!'")
connection.close()
```

## hello_consumer.py

```python
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()
channel.queue_declare(queue='hello')

def callback(ch, method, properties, body):
    print(f" [x] Received {body!r}")

channel.basic_consume(
    queue='hello',
    on_message_callback=callback,
    auto_ack=True
)

print(' [*] Waiting for messages. To exit press CTRL+C')
channel.start_consuming()
```

## Como rodar

Em dois terminais com o venv ativado:

```bash
# Terminal 1
python hello_consumer.py

# Terminal 2
python hello_producer.py
```

O consumer imprime `[x] Received b'Hello World!'`. Rodar o producer
várias vezes e ver o consumer pegar cada uma.

## Painel do Rabbit

Com o consumer rodando, abrir <http://localhost:15672> (login
`guest`/`guest`):

- **Queues and Streams** → fila `hello` aparece com 1 consumer.
- **Connections** → 1 conexão.
- **Channels** → 1 canal.

## Experimentos

1. Mata o consumer, roda o producer 3 vezes, sobe o consumer →
   ele pega as 3 mensagens. (A fila guarda.)
2. Para o consumer com Ctrl+C → a conexão some do painel.
3. `docker compose restart rabbitmq` → a fila `hello` some, e
   mensagens não consumidas também. A fila default não é durável e
   as mensagens não foram publicadas como persistentes.

## O que aprendi

- O ciclo básico: `BlockingConnection` → `channel()` → `queue_declare` →
  `basic_publish` ou `basic_consume`.
- `queue_declare` é idempotente — pode rodar tanto no producer quanto
  no consumer.
- `auto_ack=True` é simples mas perigoso em produção (mensagem perdida
  se o consumer cair antes de processar). Vou trocar pra `auto_ack=False`
  no projeto real.
- Painel é minha melhor ferramenta de debug.
