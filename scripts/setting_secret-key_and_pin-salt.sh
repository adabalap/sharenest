
# 32 bytes hex (64 chars): great for SECRET_KEY
openssl rand -hex 32
# 16 bytes hex (32 chars): fine for PIN_SALT
openssl rand -hex 16

# Alternative method
python3 - <<'PY'
import secrets
print("SECRET_KEY=", secrets.token_hex(32))
print("PIN_SALT   =", secrets.token_hex(16))
PY

Notes:

SECRET_KEY secures Flask session cookies and CSRF (if enabled later).
PIN_SALT is a constant salt for the SHA‑256 PIN hash. Changing it later will invalidate all stored hashes (i.e., existing shares would break). Keep it stable.
