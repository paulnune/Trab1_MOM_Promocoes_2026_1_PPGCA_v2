"""
common.py - funções compartilhadas pelos microsserviços.

Esta string entre três aspas no topo do arquivo é uma "docstring de módulo".
Serve como descrição de tudo que o módulo faz. É opcional, mas é boa prática.

Responsabilidades:
- Carregar chaves PEM do diretório keys/.
- Empacotar payloads em envelope assinado (produtor).
- Verificar e extrair payloads de envelope recebido (consumidor).
"""

# ====================================================================
# IMPORTS
# ====================================================================
# Carrega bibliotecas. As duas primeiras (base64, json) já vêm com Python.
# As três de cryptography são da lib que instalamos via pip.

import base64       # codifica/decodifica binário em texto ASCII
import json         # serializa/parseia JSON
import os

# 'from X import a, b' = carrega só os módulos a e b de dentro de X,
# pra escrever 'hashes.SHA256()' em vez de 'cryptography.hazmat.primitives.hashes.SHA256()'.
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.exceptions import InvalidSignature


# ====================================================================
# CONFIGURAÇÃO
# ====================================================================
# Variável "constante" do módulo. Por convenção em Python, NOMES_EM_MAIUSCULO
# significam "constante, não mexer". O caminho 'keys' é relativo ao diretório
# de onde você roda o python -- por isso o demo precisa ser rodado do diretório
# que tem keys/ dentro.

KEYS_DIR = 'keys'
RABBIT_HOST = os.environ.get('RABBIT_HOST', 'localhost')


# ====================================================================
# CARREGAR CHAVES
# ====================================================================
# Duas funções quase idênticas: uma lê privada, outra lê pública.
# Cada microsserviço carrega a SUA privada uma vez no início e usa pra assinar.
# E carrega a pública DO PRODUTOR a cada mensagem recebida pra verificar.

def carregar_chave_privada(servico):
    """Lê e retorna a chave privada do microsserviço informado.

    A docstring explica o que a função faz. Convenção:
    - 1ª linha: resumo curto.
    - Args/Returns: descrição dos parâmetros e retorno.

    Args:
        servico: string com o nome do serviço, ex: "gateway".

    Returns:
        Objeto chave privada da biblioteca cryptography (não é texto, não é
        bytes -- é um objeto Python que sabe assinar).
    """
    # f-string: monta o caminho substituindo {KEYS_DIR} por 'keys' e
    # {servico} pelo valor do parâmetro. Resultado: 'keys/gateway_priv.pem'.
    caminho = f'{KEYS_DIR}/{servico}_priv.pem'

    # 'with open(...) as f' abre o arquivo e GARANTE que fecha quando
    # sai do bloco (mesmo se der erro). 'rb' = read binary -- PEM é tratado
    # como bytes mesmo sendo texto, porque a lib espera bytes.
    with open(caminho, 'rb') as f:
        # f.read() lê todo conteúdo do arquivo como bytes.
        # load_pem_private_key parseia o PEM e retorna o objeto chave.
        # password=None porque geramos sem senha protegendo.
        return serialization.load_pem_private_key(f.read(), password=None)


def carregar_chave_publica(servico):
    """Lê e retorna a chave pública do microsserviço informado.

    Note que essa função tem só a docstring de 1 linha. Quando a função é
    super simples, basta o resumo.
    """
    caminho = f'{KEYS_DIR}/{servico}_pub.pem'
    with open(caminho, 'rb') as f:
        return serialization.load_pem_public_key(f.read())


# ====================================================================
# ENVELOPAR (lado do PRODUTOR)
# ====================================================================
# Recebe um dict Python com o payload do evento, retorna bytes prontos pra
# publicar no RabbitMQ. A função faz 4 coisas em sequência: serializar,
# assinar, montar envelope, serializar envelope.

def envelopar(payload, producer, chave_privada):
    """Cria um envelope JSON assinado.

    Args:
        payload: dict Python com os dados do evento. Ex:
            {"id": "promo-1", "categoria": "livro", "titulo": "..."}
        producer: string com o nome do microsserviço que está publicando,
            ex: "gateway". Vai dentro do envelope pra o consumidor saber
            qual chave pública usar pra verificar.
        chave_privada: objeto chave já carregado (com carregar_chave_privada).

    Returns:
        bytes prontos pra publicar no RabbitMQ. O destinatário receberá
        exatamente esses bytes.
    """
    # ----------------------------------------------------------------
    # 1. SERIALIZAR o payload em string JSON.
    # ----------------------------------------------------------------
    # json.dumps converte um dict Python em uma string JSON.
    # Por exemplo: {"a": 1, "b": 2}  →  '{"a": 1, "b": 2}'
    #
    # sort_keys=True garante que as chaves saem sempre em ordem alfabética.
    # Não é estritamente necessário aqui (porque vamos enviar a string como
    # está), mas é boa prática -- facilita debug e consistência.
    payload_str = json.dumps(payload, sort_keys=True)

    # .encode('utf-8') converte string Python em bytes.
    # Esses bytes são o que vai ser HASHEADO e ASSINADO.
    # Importante: o que assinamos aqui é exatamente o que o consumidor
    # vai verificar lá no outro lado.
    payload_bytes = payload_str.encode('utf-8')

    # ----------------------------------------------------------------
    # 2. ASSINAR os bytes do payload.
    # ----------------------------------------------------------------
    # A privada produz a assinatura. A lib calcula o hash SHA-256 dos
    # payload_bytes internamente e assina o hash com PKCS#1 v1.5.
    # O resultado é binário (256 bytes pra chave de 2048 bits).
    assinatura = chave_privada.sign(
        payload_bytes,
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    # ----------------------------------------------------------------
    # 3. MONTAR o envelope (dict Python).
    # ----------------------------------------------------------------
    # Três campos:
    # - producer: o nome do serviço (string).
    # - payload: a STRING JSON do payload (não o dict! Veja Passo 4 do conceito).
    # - signature: a assinatura em base64.
    #
    # base64.b64encode(bytes) → bytes em base64 (ainda bytes!).
    # .decode('ascii') → converte esses bytes em string (texto ASCII).
    # Tem que ser string porque dict que vai virar JSON precisa de strings.
    envelope = {
        'producer': producer,
        'payload': payload_str,
        'signature': base64.b64encode(assinatura).decode('ascii'),
    }

    # ----------------------------------------------------------------
    # 4. SERIALIZAR o envelope inteiro em bytes.
    # ----------------------------------------------------------------
    # json.dumps(envelope)  →  string JSON do envelope inteiro.
    # .encode('utf-8')      →  bytes (porque o RabbitMQ lida com bytes).
    return json.dumps(envelope).encode('utf-8')


# ====================================================================
# DESENVELOPAR (lado do CONSUMIDOR)
# ====================================================================
# Recebe bytes do RabbitMQ, verifica a assinatura, retorna o payload como dict.
# Se a assinatura não bater, levanta exceção InvalidSignature -- quem chama
# captura e descarta a mensagem.

def desenvelopar(envelope_bytes):
    """Verifica a assinatura e extrai o payload do envelope.

    Args:
        envelope_bytes: bytes recebidos do RabbitMQ.

    Returns:
        Tupla (producer, payload_dict). 'producer' é string, 'payload_dict'
        é um dict Python pronto pra usar.

        Exemplo de uso pelo chamador:
            producer, payload = desenvelopar(envelope_bytes)
            # agora producer é uma string, payload é um dict.

    Raises:
        InvalidSignature: se a assinatura não bater (mensagem adulterada
        ou forjada). O microsserviço deve capturar e descartar a mensagem.
        FileNotFoundError: se o producer indicado não tiver chave em keys/.
        Tratar igual ao InvalidSignature -- também é descarte.
    """
    # ----------------------------------------------------------------
    # 1. PARSE do envelope.
    # ----------------------------------------------------------------
    # json.loads aceita string OU bytes -- aqui passamos bytes diretamente.
    # Resultado: um dict com producer, payload, signature.
    envelope = json.loads(envelope_bytes)

    # ----------------------------------------------------------------
    # 2. EXTRAIR os 3 campos do envelope.
    # ----------------------------------------------------------------
    # envelope[chave] acessa um valor do dict pela chave.
    producer = envelope['producer']
    payload_str = envelope['payload']

    # signature está em base64 (texto). Decodificamos pra recuperar
    # os bytes originais da assinatura.
    assinatura = base64.b64decode(envelope['signature'])

    # ----------------------------------------------------------------
    # 3. CARREGAR a chave pública do producer.
    # ----------------------------------------------------------------
    # Importante: confiamos no campo 'producer' SÓ pra escolher qual
    # chave usar. A confiança real vem do verify() abaixo: se a
    # assinatura bate com essa pública, então só o dono da privada
    # correspondente poderia ter assinado.
    chave_publica = carregar_chave_publica(producer)

    # ----------------------------------------------------------------
    # 4. VERIFICAR a assinatura.
    # ----------------------------------------------------------------
    # verify() não retorna nada -- LEVANTA EXCEÇÃO se inválido.
    # Os bytes que verificamos são exatamente os mesmos que foram
    # assinados: payload_str.encode('utf-8'). Como o payload_str
    # veio do envelope sem modificação, qualquer alteração ao longo
    # do caminho causa a verificação a falhar.
    chave_publica.verify(
        assinatura,
        payload_str.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )

    # ----------------------------------------------------------------
    # 5. PARSE do payload (agora que sabemos que é confiável).
    # ----------------------------------------------------------------
    # Só convertemos a string JSON pra dict DEPOIS da verificação.
    # Boa prática: nunca processe dados não-verificados.
    payload = json.loads(payload_str)

    # 'return a, b' devolve uma tupla com dois valores. Quem chamou
    # pode desempacotar com 'producer, payload = desenvelopar(...)'.
    return producer, payload