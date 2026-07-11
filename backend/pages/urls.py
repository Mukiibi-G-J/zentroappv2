"""
Page engine URL routes.

Full API reference (params, responses, MODEL_REGISTRY, frontend mapping):
  backend/pages/PAGE_ENGINE_URLS.md

Mounted from:
  - core/urls.py        (tenant requests)
  - core/urls-public.py (public schema)

Auth: JWT Bearer + schema_name claim on every endpoint.
"""
from django.urls import path
from .views import (
    PagesListView,
    PageDetailView,
    PageDataView,
    PageDataRecordView,
    TableRelationsView,
    PageActionView,
    RoleCentreView,
    ListCuesView,
    SetupSoloView,
)

app_name = 'pages'

urlpatterns = [
    # GET — all page definitions (sidebar PageId resolution)
    path('api/pages/', PagesListView.as_view(), name='pages-list'),

    # GET — single page metadata (?PageId=)
    path('api/pages/page/', PageDetailView.as_view(), name='page-detail'),

    # GET list / POST create records (?PageId= &ControlId= &search= &limit= &offset= + drill-down filters)
    path('api/pages/data/', PageDataView.as_view(), name='page-data'),

    # GET / PATCH / DELETE single record by system_id
    path('api/pages/data/<str:system_id>/', PageDataRecordView.as_view(), name='page-data-record'),

    # POST — table-relation dropdown options
    path('api/pages/relations/', TableRelationsView.as_view(), name='page-relations'),

    # POST — invoke page action on a record
    path('api/pages/action/', PageActionView.as_view(), name='page-action'),

    # GET — Role Centre aggregate data (?PageId=)
    path('api/pages/rolecentre/', RoleCentreView.as_view(), name='rolecentre-data'),

    # GET — List page cue tiles (?PageId=)
    path('api/pages/list-cues/', ListCuesView.as_view(), name='list-cues'),

    # GET — singleton setup record SystemId (?PageId=)
    path('api/pages/setup-solo/', SetupSoloView.as_view(), name='setup-solo'),
]
