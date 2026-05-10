# Estudo 2 — Exchanges, Routing Keys e Bindings

Notas dos tutoriais 4 e 5 do RabbitMQ ([direct](https://www.rabbitmq.com/tutorials/tutorial-four-python.html)
e [topic](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)),
adaptados pra simular o cenário do trabalho — promoções por categoria.

## Referências

- [RabbitMQ Tutorial 4 (direct)](https://www.rabbitmq.com/tutorials/tutorial-four-python.html)
- [RabbitMQ Tutorial 5 (topic)](https://www.rabbitmq.com/tutorials/tutorial-five-python.html)
- [Tipos de Exchange](https://www.rabbitmq.com/tutorials/amqp-concepts.html#exchanges)

## O que muda em relação ao Hello World

No Hello World a exchange era a `default` (sem nome) e o roteamento
era pelo nome da fila. Aqui as exchanges ganham nome e tipo, e aparece
um conceito novo: **binding** (a "amarração" entre exchange e fila).

```
produtor              EXCHANGE
publica com    ───▶   (nomeada, tipo:
routing_key           direct/topic/fanout)
                          │
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
           fila A       fila B      fila C
        binding:     binding:     binding:
        promocao.    promocao.    promocao.#
        livro        jogo
```

A mecânica:

1. Produtor publica numa exchange com uma routing key.
2. Exchange olha as bindings que tem com filas.
3. Pra cada binding cuja binding key casa com a routing key, copia a
   mensagem pra fila.
4. Consumer lê da sua fila — não sabe qual exchange roteou.

> **Insight**: o consumer (cliente) é dono da fila e cria o binding.
> O produtor não sabe quem está escutando — só joga na exchange. É
> isso que desacopla os microsserviços.

## direct vs topic

| Aspecto | direct | topic |
|---|---|---|
| Como casa | Igualdade exata | Padrão com `*` (uma palavra) e `#` (zero ou mais) |
| Exemplo binding | `promocao.livro` | `promocao.livro`, `promocao.*`, `promocao.#` |
| Quando vira igual ao direct | — | Quando não usa wildcard |
| Complexidade | nenhuma | nenhuma (escolho usar wildcard ou não) |

Pro trabalho escolhi **topic**:

1. O enunciado fala em "routing keys hierárquicas"
   (`promocao.livro`, `promocao.jogo`...) — convenção de topic.
2. Sem wildcard, topic se comporta igual a direct, então não pago
   complexidade.
3. Com wildcard, ganho flexibilidade se um cliente quiser
   `promocao.#` (todas) ou `promocao.livro.*` futuramente.

## Regras do topic

Routing keys e binding keys são strings com palavras separadas por ponto.

- `*` casa exatamente UMA palavra.
- `#` casa ZERO ou MAIS palavras.

| Binding key | Casa | Não casa |
|---|---|---|
| `promocao.livro` | `promocao.livro` | `promocao.jogo`, `promocao.livro.usado` |
| `promocao.*` | `promocao.livro`, `promocao.jogo`, `promocao.destaque` | `promocao.livro.usado`, `promocao` |
| `promocao.#` | `promocao`, `promocao.livro`, `promocao.livro.usado` | `noticia.x` |
| `*.destaque` | `promocao.destaque`, `oferta.destaque` | `destaque`, `promocao.livro.destaque` |

## Experimento — esqueleto do trabalho

Quatro arquivos no diretório `2_exchange_routingkeys_bindings/`:

- `emit_promocao.py` — publica
- `receive_cliente_a.py` — escuta `promocao.livro` e `promocao.destaque`
- `receive_cliente_b.py` — escuta só `promocao.jogo`
- `receive_cliente_curioso.py` — escuta `promocao.#` (tudo)

### emit_promocao.py

```python
import sys
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()

# Agora a exchange tem nome e tipo. exchange_declare é idempotente.
channel.exchange_declare(exchange='promocoes', exchange_type='topic')

# Lê routing key e mensagem da linha de comando.
routing_key = sys.argv[1] if len(sys.argv) > 1 else 'promocao.geral'
message = ' '.join(sys.argv[2:]) or 'Promocao sem descricao'

# Publica na exchange nomeada (não na default).
channel.basic_publish(
    exchange='promocoes',
    routing_key=routing_key,
    body=message
)
print(f" [x] Sent {routing_key!r}: {message!r}")
connection.close()
```

### receive_cliente_a.py

```python
import pika

connection = pika.BlockingConnection(
    pika.ConnectionParameters(host='localhost')
)
channel = connection.channel()
channel.exchange_declare(exchange='promocoes', exchange_type='topic')

# Fila ANÔNIMA (Rabbit gera nome) e EXCLUSIVA (sumir ao desconectar).
result = channel.queue_declare(queue='', exclusive=True)
queue_name = result.method.queue

# Cliente A quer livro E destaque -> 2 bindings na mesma fila.
binding_keys = ['promocao.livro', 'promocao.destaque']
for bk in binding_keys:
    channel.queue_bind(
        exchange='promocoes',
        queue=queue_name,
        routing_key=bk
    )

print(f' [*] Cliente A esperando em {queue_name}. Bindings: {binding_keys}.')

def callback(ch, method, properties, body):
    print(f" [x] Cliente A recebeu [{method.routing_key}]: {body!r}")

channel.basic_consume(
    queue=queue_name,
    on_message_callback=callback,
    auto_ack=True
)
channel.start_consuming()
```

`receive_cliente_b.py` é igual mas com `binding_keys = ['promocao.jogo']`.
`receive_cliente_curioso.py` com `binding_keys = ['promocao.#']`.

## Como rodar

4 terminais com venv ativado:

```bash
# Terminal 1
python receive_cliente_a.py

# Terminal 2
python receive_cliente_b.py

# Terminal 3
python receive_cliente_curioso.py

# Terminal 4 — publica
python emit_promocao.py promocao.livro "Don Quixote 50% off"
python emit_promocao.py promocao.jogo "Elden Ring 30% off"
python emit_promocao.py promocao.eletronico "Notebook 15% off"
python emit_promocao.py promocao.destaque "Geladeira 70% off"
```

Resultado esperado:

| Evento publicado | Cliente A (livro+destaque) | Cliente B (jogo) | Cliente Curioso (#) |
|---|---|---|---|
| `promocao.livro` | ✅ | ❌ | ✅ |
| `promocao.jogo` | ❌ | ✅ | ✅ |
| `promocao.eletronico` | ❌ | ❌ | ✅ |
| `promocao.destaque` | ✅ | ❌ | ✅ |

## Painel do Rabbit

<http://localhost:15672>:

- **Exchanges** → `promocoes` listada com tipo topic. Click → vê os bindings.
- **Queues** → 3 filas com nomes tipo `amq.gen-XXXXX` (anônimas).
- Click numa fila → seção "Bindings" mostra em quais routing keys ouve.
- Mata um consumer com Ctrl+C → fila some (era exclusive).

## O que aprendi

- `exchange_declare` é idempotente — pode chamar em todos os processos.
- `queue=''` + `exclusive=True` é o padrão pra "fila própria de cliente":
  criada na hora, descartada ao sair.
- Uma fila pode ter vários bindings na mesma exchange.
- O routing key da mensagem que chegou está em `method.routing_key`,
  útil pra distinguir origem.
