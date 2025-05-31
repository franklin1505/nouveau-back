from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class CustomPagination(PageNumberPagination):
    page_size = 20  # Nombre d'éléments par page
    page_size_query_param = 'page_size'  # Permet de personnaliser le nombre par page via les paramètres
    max_page_size = 100  # Limite supérieure du nombre d'éléments par page

    def get_paginated_response(self, data):
        return Response({
            'status': 'success',
            'message': 'Liste paginée des véhicules récupérée avec succès.',
            'data': {
                'count': self.page.paginator.count,
                'next': self.get_next_link(),
                'previous': self.get_previous_link(),
                'results': data
            }
        })
