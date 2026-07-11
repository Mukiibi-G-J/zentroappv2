#!/usr/bin/env bash
# Send one transactional email via Mailtrap API (same as django-anymail when SANDBOX_ID is unset)
# Credentials from core/.env

curl -X POST 'https://send.api.mailtrap.io/api/send' \
  -H 'Authorization: Bearer 96a4ee224a15ac75dd48242119c34289' \
  -H 'Content-Type: application/json' \
  -d '{
    "from": {"email": "noreply@zentroapp.app"},
    "to": [{"email": "mukiibijoseph19@gmail.com"}],
    "subject": "Hello from Mailtrap",
    "text": "Welcome to Mailtrap!"
  }'
