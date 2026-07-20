"""Public, unauthenticated digital menu API (separate from POS Menu)."""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import models
from .permissions import IsTenantSchema


class PublicDigitalMenuView(APIView):
    """
    GET /api/restaurant/public-menu/<slug>/
    Tenant resolved from subdomain — no auth required.
    """

    permission_classes = [AllowAny, IsTenantSchema]
    authentication_classes = []

    def get(self, request, slug="main"):
        publication = (
            models.DigitalMenuPublication.objects.filter(slug=slug, is_published=True)
            .prefetch_related("sections__lines")
            .first()
        )
        if not publication:
            return Response(
                {"error": "Menu not found or not published."},
                status=404,
            )

        sections = []
        for section in publication.sections.all().order_by("display_order", "name"):
            lines = []
            for line in section.lines.all().order_by("display_order", "name"):
                lines.append(
                    {
                        "name": line.name,
                        "description": line.description,
                        "price": str(line.price),
                        "price_note": line.price_note,
                        "is_featured": line.is_featured,
                    }
                )
            sections.append(
                {
                    "name": section.name,
                    "subtitle": section.subtitle,
                    "accent_color": section.accent_color,
                    "image_url": section.image_url or "",
                    "lines": lines,
                }
            )

        return Response(
            {
                "slug": publication.slug,
                "title": publication.title,
                "tagline": publication.tagline,
                "phones": publication.phones or [],
                "social_links": publication.social_links or {},
                "brand_primary": publication.brand_primary,
                "brand_accent": publication.brand_accent,
                "currency_code": publication.currency_code,
                "logo_url": publication.logo_url or "",
                "cover_image_url": publication.cover_image_url or "",
                "gallery_images": publication.gallery_images or [],
                "sections": sections,
            }
        )
