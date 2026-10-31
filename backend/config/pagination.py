from rest_framework.pagination import PageNumberPagination


class StandardPagination(PageNumberPagination):
    page_size = 25  # rule 9
    page_size_query_param = "page_size"  # dropdowns ask for more; capped
    max_page_size = 200
