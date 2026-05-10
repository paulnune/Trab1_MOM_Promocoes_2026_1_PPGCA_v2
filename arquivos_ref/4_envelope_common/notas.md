## Experimento A: adversário altera o payload

**Pergunta**: e se um homem-no-meio mexer no envelope?

**Ação**: edite o `demo.py` e adicione, **logo antes** do bloco `--- Promocao ---`, este código que simula um adversário:

```python
# ------------------------------------------------------------------
# ADVERSÁRIO altera o envelope no caminho
# ------------------------------------------------------------------
import json
envelope_adulterado = json.loads(envelope)
payload_orig = json.loads(envelope_adulterado['payload'])
payload_orig['desconto_pct'] = 99  # tentou mudar 50 pra 99
envelope_adulterado['payload'] = json.dumps(payload_orig, sort_keys=True)
envelope = json.dumps(envelope_adulterado).encode('utf-8')
print('\n!!! Envelope foi adulterado no caminho !!!')
```

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common$ python demo.py
--- Gateway ---
Payload original: {'id': 'promo-001', 'categoria': 'livro', 'titulo': 'Don Quixote', 'preco': 49.9, 'desconto_pct': 50}
Envelope (516 bytes) pronto pra publicar:
{"producer": "gateway", "payload": "{\"categoria\": \"livro\", \"desconto_pct\": 50, \"id\": \"promo-001\", \"preco\": 49.9, \"titulo\": \"Don Quixote\"}", "signature": "VlizOIM3PPpZdoVPoLXR1e5C+IPXKYVQ31KVpS7jBiK9NB9vdY1YThx6RsX56KynJ22VEm5e2GEdEAZXcXQqLnX9TT236tYs2C9lxZwfwm2KhUykqeVPAJ8EByXc4A0kX3k+S5ogo3Xw4CSMFrZuMeOTsmXH+2AFbA33G8J1juUE8ItRsLp3Z5TCfFjkgBZGrxwK7S/Ob7hYRCB5AEOsaky2xIUwjzDiOJF/LFHXQiVwiOYR3u3HqbSmezubIlvml2DxZdBEhIySamwXgywLxFxqmtaMhDjH390AARsegbTTQLbaS43PVxOQNK4lNuN9G6sqxhu+xGDg+VxHVxBrzA=="}

!!! Envelope foi adulterado no caminho !!!

--- Promocao ---
Recebeu envelope. Verificando assinatura...
FALHOU - assinatura inválida. Descartando.

**O que prova**: integridade. Mesmo que o adversário recalcule o payload pra ficar bem formado, ele não tem a privada do gateway, então a assinatura não bate. Mensagem descartada.

## Experimento B: adversário troca o producer

**Pergunta**: e se um adversário mudar só o campo `producer` pra fingir que mandou?

**Ação**: igual ao A, mas o adversário muda só o `producer`. Criado o arquivo demo_envelope_adulterado.py.

```python
# ------------------------------------------------------------------
# Lado do PRODUTOR (Gateway)
# ------------------------------------------------------------------

print('--- Gateway ---')
gateway_priv = common.carregar_chave_privada('gateway')

payload_gateway = {
    'id': 'promo-001',
    'categoria': 'livro',
    'titulo': 'Don Quixote',
    'preco': 49.90,
    'desconto_pct': 50,
}
envelope = common.envelopar(payload_gateway, 'gateway', gateway_priv)
envelope_adulterado = json.loads(envelope)
envelope_adulterado['producer'] = 'promocao'  # finge que veio do promocao
envelope = json.dumps(envelope_adulterado).encode('utf-8')
print('\n!!! Producer foi trocado pra promocao !!!')

```

**Rode:**
```bash
python demo.py
```

**Resultado esperado:**
```
FALHOU - assinatura inválida. Descartando.
```

Resultado:

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common$ python demo_envelope_adulterado.py 
--- Gateway ---

!!! Producer foi trocado pra promocao !!!

--- Promocao ---
Recebeu envelope. Verificando assinatura...
FALHOU - assinatura inválida. Descartando.

Resultado:

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common$ python demo_produtor_sem_chave.py 
--- Gateway ---

--- Promocao ---
Recebeu envelope. Verificando assinatura...
Traceback (most recent call last):
  File "/home/paulonunes/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common/demo_produtor_sem_chave.py", line 43, in <module>
    producer, payload_recebido = common.desenvelopar(envelope)
                                 ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/paulonunes/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common/common.py", line 214, in desenvelopar
    chave_publica = carregar_chave_publica(producer)
                    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/paulonunes/utfpr/sistemasdistribuidos/mom/arquivos_ref/4_envelope_common/common.py", line 82, in carregar_chave_publica
    with open(caminho, 'rb') as f:
         ^^^^^^^^^^^^^^^^^^^
FileNotFoundError: [Errno 2] No such file or directory: 'keys/hacker_pub.pem'


**O que prova**: autenticidade. O `desenvelopar` agora carrega `keys/promocao_pub.pem`, mas a assinatura foi feita pela privada do `gateway`. As chaves não casam. Falha.