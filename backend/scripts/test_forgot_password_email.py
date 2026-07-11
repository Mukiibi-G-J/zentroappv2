#!/usr/bin/env python
"""
Test forgot-password email sending. Run from project root with your settings:

  cd zentro-backend
  python manage.py shell --settings=core.settingsprod < scripts/test_forgot_password_email.py

Or with default settings (core.settings):

  python manage.py shell < scripts/test_forgot_password_email.py

Or paste the code below into: python manage.py shell --settings=core.settingsprod
"""
# Paste this in Django shell:
if False:  # set True to actually send
    from django.core.mail import send_mail
    from django.conf import settings
    from django_tenants.utils import schema_context
    from authentication.models import CustomUser as User
    from helpers.helpers import send_forgot_password_link_email

    email = "kalideveloper865@gmail.com"
    schema_name = "kakooza"  # or "primewise", etc.

    with schema_context(schema_name):
        user = User.objects.get(email=email)
        reset_url = "https://kakooza.zentroapp.app/reset-password?token=test-token-replace-me"
        sent = send_forgot_password_link_email(email, user, schema_name, reset_url)
        print("Email link helper returned:", sent)
else:
    # Just test config and dry-run (no send)
    from django.conf import settings
    print("EMAIL_BACKEND:", settings.EMAIL_BACKEND)
    print("DEFAULT_FROM_EMAIL:", settings.DEFAULT_FROM_EMAIL)
    if getattr(settings, "ANYMAIL", None):
        _mt = settings.ANYMAIL.get("MAILTRAP_API_TOKEN")
        print("ANYMAIL MAILTRAP configured:", bool(_mt))
    else:
        print("EMAIL_HOST:", getattr(settings, "EMAIL_HOST", None))
    print("-- To actually send, run in shell:")
    print("  from django.core.mail import send_mail; from django.conf import settings")
    print("  send_mail('Test', 'Body', settings.DEFAULT_FROM_EMAIL, ['your@email.com'])")
