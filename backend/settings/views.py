from django.db import connection
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication

from settings.services import MobileAppUserSettingsService


class MobileAppSettingsView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = MobileAppUserSettingsService()

    def get(self, request):
        tenant_schema_name = getattr(connection.tenant, "schema_name", "public")
        payload = self.service.get_settings(request.user, tenant_schema_name)
        response = Response(payload, status=status.HTTP_200_OK)
        for key, value in self.service.build_cache_headers(payload).items():
            response[key] = value
        return response

    def patch(self, request):
        # Per-user mobile preferences (scanner, printer, search mode). Any authenticated
        # user may update their own row; MobileAppUserSettingsService scopes by request.user.
        tenant_schema_name = getattr(connection.tenant, "schema_name", "public")
        payload, error = self.service.patch_settings(
            user=request.user,
            tenant_schema_name=tenant_schema_name,
            data=request.data,
            if_unmodified_since=request.headers.get("If-Unmodified-Since"),
        )
        if error:
            return error

        response = Response(payload, status=status.HTTP_200_OK)
        for key, value in self.service.build_cache_headers(payload).items():
            response[key] = value
        return response
