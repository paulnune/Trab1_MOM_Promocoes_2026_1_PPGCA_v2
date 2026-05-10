set -e

mkdir -p keys

# Chaves por serviço
for nome in gateway promocao ranking notificacao; do
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "keys/${nome}_priv.pem"
  openssl rsa -in "keys/${nome}_priv.pem" -pubout -out "keys/${nome}_pub.pem"
  chmod 600 "keys/${nome}_priv.pem"
done