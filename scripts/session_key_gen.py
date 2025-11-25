
import secrets

# Generate a 32-byte secure random key and convert it to a hex string
secret_key = secrets.token_hex(32)
print(secret_key)

