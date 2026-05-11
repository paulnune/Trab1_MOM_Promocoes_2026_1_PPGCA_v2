import base64
import json

import pika


def main() -> None:
	conn = pika.BlockingConnection(pika.ConnectionParameters(host='localhost'))
	ch = conn.channel()

	# Envelope FALSO: producer='gateway', mas signature inválida
	envelope = {
		'producer': 'gateway',
		'payload': '{"id":"FALSA","categoria":"livro","titulo":"PROMO FALSA","preco":1,"desconto_pct":99}',
		'signature': base64.b64encode(b'assinatura_falsa_qualquer_coisa').decode(),
	}
	ch.basic_publish(
		exchange='promocoes',
		routing_key='promocao.recebida',
		body=json.dumps(envelope).encode(),
	)
	conn.close()
	print('Mensagem falsa publicada!')


if __name__ == '__main__':
	main()