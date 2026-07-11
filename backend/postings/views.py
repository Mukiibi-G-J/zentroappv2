from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from authentication.authentication import JWTAuthenticationWithRevocationChecks as JWTAuthentication
from postings.models import GeneralProductPostingGroup, GeneralBusinessPostingGroup
from postings.serializers import (
    GeneralProductPostingGroupSerializer,
    GeneralBusinessPostingGroupSerializer,
)

# Create your views here.


class GeneralProductPostingGroupViewSet(viewsets.ModelViewSet):
    queryset = GeneralProductPostingGroup.objects.all()
    serializer_class = GeneralProductPostingGroupSerializer
    permission_classes = [IsAuthenticated]
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    lookup_field = "system_id"

    def get_queryset(self):
        queryset = GeneralProductPostingGroup.objects.all()
        code = self.request.query_params.get("code", None)
        if code is not None:
            queryset = queryset.filter(code__icontains=code)
        return queryset


class GeneralBusinessPostingGroupViewSet(viewsets.ModelViewSet):
    queryset = GeneralBusinessPostingGroup.objects.all()
    serializer_class = GeneralBusinessPostingGroupSerializer
    authentication_classes = [SessionAuthentication, JWTAuthentication]
    permission_classes = [IsAuthenticated]
    lookup_field = "system_id"

    def get_queryset(self):
        queryset = GeneralBusinessPostingGroup.objects.all()
        code = self.request.query_params.get("code", None)
        if code is not None:
            queryset = queryset.filter(code__icontains=code)
        return queryset
