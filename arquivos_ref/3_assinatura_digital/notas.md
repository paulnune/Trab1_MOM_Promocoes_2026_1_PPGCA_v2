### Saída Validada

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/3_assinatura_digital$ python verificar.py
OK - assinatura válida.

### Experimento A — "E se eu alterar a mensagem?"

Ação: Ajustar no verificar.py:

De: 
mensagem = b'Promocao: Don Quixote 50% off'

Para:
mensagem = b'Promocao: Don Quixote 90% off'

Resultado:

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/3_assinatura_digital$ python verificar.py
FALHOU - assinatura inválida ou mensagem alterada.

**O que isso prova: integridade**. A assinatura foi calculada sobre o hash do texto `50% off`. Quando a mensagem mudou pra `90% off`, o hash mudou, e a assinatura não bate mais. **Qualquer byte alterado** invalida a assinatura — efeito avalanche do SHA-256.

### Experimento B — "E se outro produtor tentar forjar?"

Ação: Gerado um par de chaves simulando outro microsserviço. 

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out outro_priv.pem
openssl rsa -in outro_priv.pem -pubout -out outro_pub.pem

De:
with open('keys/teste_pub.pem', 'rb') as f:
    chave_publica = serialization.load_pem_public_key(f.read())

Para:
with open('keys/outro_pub.pem', 'rb') as f:
    chave_publica = serialization.load_pem_public_key(f.read())



Resultado: 

paulonunes@ubuntu2402-pm:~/utfpr/sistemasdistribuidos/mom/arquivos_ref/3_assinatura_digital$ python verificar.py
FALHOU - assinatura inválida ou mensagem alterada.

**O que isso prova: autenticidade**. A assinatura foi gerada com `teste_priv.pem`. Só `teste_pub.pem` consegue verificá-la. Se você tentar verificar com `outro_pub.pem` (de um produtor diferente), falha. Isso é o que impede um microsserviço de forjar mensagens em nome de outro.
