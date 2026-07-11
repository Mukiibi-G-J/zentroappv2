from django.urls import path, include
from rest_framework.routers import DefaultRouter
from postings.views import (
    GeneralProductPostingGroupViewSet,
    GeneralBusinessPostingGroupViewSet,
)

app_name = "postings"

router = DefaultRouter()
router.register(r"general-product-posting-groups", GeneralProductPostingGroupViewSet)
router.register(r"general-business-posting-groups", GeneralBusinessPostingGroupViewSet)

urlpatterns = [
    path("api/postings/", include(router.urls)),
]
