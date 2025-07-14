from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class BookingPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data, sub_stats=None, filter_context=None):
        """✅ CORRIGÉ : Réponse paginée étendue pour les statistiques de booking avec contexte de filtrage"""
        return Response({
            'status': 'success',
            'message': self._get_context_message(filter_context),
            'data': {
                'bookings': data,
                'sub_stats': sub_stats or {},
                'pagination': {
                    'page': self.page.number,
                    'page_size': self.page_size,  # ✅ CORRECTION : Utilise la vraie page_size
                    'total_pages': self.page.paginator.num_pages,
                    'total_count': self.page.paginator.count,
                    'has_next': self.page.has_next(),
                    'has_previous': self.page.has_previous(),
                    'next': self.get_next_link(),
                    'previous': self.get_previous_link()
                },
                'filter_context': filter_context or {}
            }
        })
    
    def _get_context_message(self, filter_context=None):
        """Génère un message contextualisé selon le type de filtrage actif"""
        if not filter_context:
            return 'Réservations filtrées récupérées avec succès'
        
        filter_type = filter_context.get('filter_type', 'standard')
        current_scope = filter_context.get('current_scope', 'total')
        filter_level = filter_context.get('filter_level', 1)
        
        if filter_type == 'recurring':
            if filter_level == 1:
                return 'Réservations récurrentes récupérées avec succès'
            elif filter_level == 2:
                return 'Réservations récurrentes par type récupérées avec succès'
            elif filter_level == 3:
                return 'Réservations récurrentes détaillées récupérées avec succès'
        
        elif filter_type == 'booking_type':
            return 'Réservations par type récupérées avec succès'
        
        elif filter_type == 'status':
            return 'Réservations par statut récupérées avec succès'
        
        elif current_scope in ['today', 'past', 'future']:
            scope_messages = {
                'today': "Réservations du jour récupérées avec succès",
                'past': "Réservations passées récupérées avec succès",
                'future': "Réservations futures récupérées avec succès"
            }
            return scope_messages.get(current_scope, 'Réservations filtrées récupérées avec succès')
        
        elif current_scope == 'cancelled':
            return 'Réservations annulées récupérées avec succès'
        
        elif current_scope == 'archived':
            return 'Réservations archivées récupérées avec succès'
        
        return 'Réservations filtrées récupérées avec succès'