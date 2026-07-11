from django.urls import path
from . import views

app_name = "common"

urlpatterns = [
    # Global search endpoint
    path("api/search/global/", views.global_search, name="global-search"),
    # Activity / notification endpoints
    path("api/common/activity/recent/", views.activity_recent, name="activity-recent"),
    path("api/common/activity/count/", views.activity_count, name="activity-count"),
    path("api/common/activity/", views.activity_list, name="activity-list"),
]
