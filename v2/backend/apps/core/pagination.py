"""Shared DRF pagination.

The default PageNumberPagination has no `page_size_query_param`, so a client's
`?page_size=` is silently ignored and every list is capped at PAGE_SIZE (50).
That truncated charts/lists that legitimately need more rows (e.g. the daily
production chart, the kassa transactions list). This class honours `page_size`
up to a sane ceiling.
"""
from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 2000
