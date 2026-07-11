"""
Custom pagination classes for the API
"""

from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """
    Standard pagination with configurable page size.
    Allows clients to request up to 1000 items per page.
    """
    page_size = 10  # Default page size
    page_size_query_param = 'page_size'  # Allow client to override
    max_page_size = 1000  # Maximum allowed page size


