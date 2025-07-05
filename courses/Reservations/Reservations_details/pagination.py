from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class BookingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data, sub_stats=None):
        """
        Custom paginated response for booking statistics
        """
        return Response({
            'status': 'success',
            'message': 'Réservations filtrées récupérées avec succès',
            'data': {
                'bookings': data,
                'sub_stats': sub_stats or {},
                'pagination': {
                    'page': self.page.number,
                    'page_size': self.page_size,
                    'total_pages': self.page.paginator.num_pages,
                    'total_count': self.page.paginator.count,
                    'has_next': self.page.has_next(),
                    'has_previous': self.page.has_previous(),
                    'next': self.get_next_link(),
                    'previous': self.get_previous_link()
                }
            }
        })