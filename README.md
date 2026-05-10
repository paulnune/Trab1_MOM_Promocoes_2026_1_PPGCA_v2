# Sistema de Promoções — MOM com RabbitMQ e Assinatura Digital

Sistema distribuído baseado em **microsserviços** para gerenciamento e divulgação de promoções de produtos. Os serviços comunicam-se exclusivamente por **eventos** publicados em um broker **RabbitMQ**, e cada evento é protegido por **assinatura digital com criptografia assimétrica (RSA-2048)**.

> Trabalho da disciplina **Sistemas Distribuídos** — UTFPR, Profa. Ana Cristina Barreiras Kochem Vendramin (DAINF). Avaliação 2 — valor 1,5.

---

## Arquitetura

```
                          ┌───────────────────────┐
                          │       RabbitMQ        │
                          │  exchange: "promocoes"│
                          │       (topic)         │
                          └───────────┬───────────┘
                                      │
       ┌──────────────┬────────────┬──┴─────────┬──────────────┐
       │              │            │            │              │
  ┌────▼────┐   ┌─────▼────┐  ┌────▼────┐  ┌────▼─────┐  ┌─────▼────┐
  │ Gateway │   │ Promocao │  │ Ranking │  │Notificação│  │ Clientes │
  └─────────┘   └──────────┘  └─────────┘  └──────────┘  └──────────┘
```

Cada microsserviço atua de forma **independente e desacoplada** — não há chamadas diretas entre eles. Toda comunicação passa pelo broker.

### Microsserviços

| Serviço | Responsabilidade |
|---|---|
| **Gateway** | Interface CLI com usuários (clientes e lojas). Cadastra promoções, registra votos e lista promoções publicadas. |
| **Promocao** | Valida e registra promoções recebidas; publica evento de promoção disponibilizada. |
| **Ranking** | Processa votos, calcula score de popularidade e marca promoções como *hot deal* quando atingem o limite. |
| **Notificação** | Distribui notificações por categoria aos clientes inscritos, incluindo destaques. |

### Eventos

| Routing key | Produtor | Consumidor(es) |
|---|---|---|
| `promocao.recebida` | Gateway | Promocao |
| `promocao.publicada` | Promocao | Gateway, Notificação |
| `promocao.voto` | Gateway | Ranking |
| `promocao.destaque` | Ranking | Notificação |
| `promocao.<categoria>` | Notificação | Clientes |

### Envelope dos eventos

Todos os eventos publicados (exceto pela Notificação) trafegam **assinados digitalmente**. Formato:

```json
{
  "producer": "gateway",
  "payload": "{\"id\":\"promo-001\",\"categoria\":\"livro\",...}",
  "signature": "<base64 da assinatura RSA-PKCS1v15-SHA256>"
}
```

- O produtor assina os bytes UTF-8 do `payload` (string JSON) com sua chave privada.
- O consumidor identifica o produtor pelo campo `producer`, carrega a chave pública correspondente e verifica.
- Mensagens com assinatura inválida (ou produtor sem chave registrada) são **descartadas**.

---

## Tecnologias

- **Python 3.12+**
- **pika** — cliente AMQP para RabbitMQ
- **cryptography** — RSA-2048, padding PKCS#1 v1.5, hash SHA-256
- **RabbitMQ 3** (imagem `rabbitmq:3-management`)
- **Docker Compose** — orquestração local

---

## Pré-requisitos

- Docker + Docker Compose
- Python 3.12+ com `venv`
- `openssl` (para gerar as chaves)

---

## Como rodar

```bash
# 1. Clonar o repositório e entrar nele
cd mom

# 2. Gerar os pares de chaves dos 4 microsserviços
bash gerar_chaves.sh

# 3. Subir o RabbitMQ
docker compose up -d rabbitmq

# 4. Instalar dependências Python (em venv)
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 5. Em terminais separados, subir cada microsserviço
python promocao.py
python ranking.py
python notificacao.py
python gateway.py     # interface CLI

# 6. (opcional) Em outro terminal, um cliente assinante
python client.py
```

Painel de administração do Rabbit em <http://localhost:15672> (login padrão `guest`/`guest`).

---

## Estrutura do projeto

```
mom/
├── docker-compose.yml
├── requirements.txt
├── gerar_chaves.sh         # bash + openssl, gera 4 pares RSA-2048
├── common.py               # envelopar/desenvelopar (compartilhado)
├── gateway.py              # MS Gateway (CLI)
├── promocao.py             # MS Promocao
├── ranking.py              # MS Ranking
├── notificacao.py          # MS Notificação
├── client.py               # cliente consumidor
├── keys/                   # chaves PEM (gitignored)
│   ├── gateway_priv.pem
│   ├── gateway_pub.pem
│   └── ...
└── arquivos_ref/           # estudos exploratórios (referência)
```

---

## Segurança

- **Chaves privadas nunca são commitadas** (`keys/*.pem` está no `.gitignore`).
- Cada execução em ambiente novo regenera as chaves localmente via `gerar_chaves.sh`.
- Algoritmo: RSA-2048 + padding PKCS#1 v1.5 + SHA-256.
- A confiança vem da posse da chave privada, não do campo `producer` — adulteração e falsificação são detectadas pela verificação da assinatura.

---

## Autor

Paulo Nunes — UTFPR, Sistemas Distribuídos (2026/1)
