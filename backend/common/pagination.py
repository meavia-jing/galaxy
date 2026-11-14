"""Page pagination capped at 100 items, shaped as items/page/page_size/total."""
from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

MAX_PAGE_SIZE = 100


class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = MAX_PAGE_SIZE

    def get_paginated_response(self, data):
        return Response(
            OrderedDict(
                [
                    ("items", data),
                    ("page", self.page.number),
                    ("page_size", self.get_page_size(self.request)),
                    ("total", self.page.paginator.count),
                ]
            )
        )

    def get_paginated_response_schema(self, schema):
        return {
            "type": "object",
            "properties": {
                "items": schema,
                "page": {"type": "integer"},
                "page_size": {"type": "integer"},
                "total": {"type": "integer"},
            },
        }
