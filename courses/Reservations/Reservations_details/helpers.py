from rest_framework.response import Response
from rest_framework import status

from courses.Reservations.helpers import create_response

def get_query_params(request):
    """Get query parameters compatible with Django and DRF"""
    if hasattr(request, 'query_params'):
        return request.query_params
    elif hasattr(request, 'GET'):
        return request.GET
    else:
        return getattr(request, 'query_params', getattr(request, 'GET', {}))

def extract_booking_filters(request):
    """Extract booking filters from query parameters"""
    query_params = get_query_params(request)
    filters = {}
    if query_params.get('billing_status'):
        filters['billing_status'] = query_params.get('billing_status')
    if query_params.get('cancellation_status'):
        filters['cancellation_status'] = query_params.get('cancellation_status')
    if query_params.get('payment_timing'):
        filters['payment_timing'] = query_params.get('payment_timing')
    return filters

def extract_scope_and_search_key(request):
    """Extract scope and search_key from request"""
    query_params = get_query_params(request)
    return {
        'scope': query_params.get('scope'),
        'search_key': query_params.get('search_key')
    }

def build_empty_stats_response(model_class):
    """Build empty sub-stats when no data found"""
    return {
        'total': 0,
        'billing_status': {code: 0 for code, _ in model_class.BILLING_STATUS_CHOICES},
        'cancellation_status': {code: 0 for code, _ in model_class.CANCELLATION_STATUS_CHOICES},
        'payment_timing': {code: 0 for code, _ in model_class.PAYMENT_TIMING_CHOICES}
    }

def build_empty_pagination_response():
    """Build empty pagination when no data found"""
    return {
        'page': 1,
        'page_size': 20,
        'total_pages': 0,
        'total_count': 0,
        'has_next': False,
        'has_previous': False,
        'next': None,
        'previous': None
    }

def validate_search_key(search_key):
    """Validate search_key parameter"""
    if not search_key:
        return False, "Clé de recherche manquante"
    return True, None

def validate_booking_id(booking_id):
    """Validate booking ID parameter"""
    if not booking_id:
        return False, "ID de réservation manquant"
    try:
        int(booking_id)
        return True, None
    except (ValueError, TypeError):
        return False, "ID de réservation invalide"

def build_global_stats_response(main_stats, serialized_data):
    """Build response for global statistics"""
    return create_response(
        status_type="success",
        message="Statistiques des réservations récupérées avec succès",
        data=serialized_data
    )

def build_detail_response(serialized_data):
    """Build response for booking detail"""
    return create_response(
        status_type="success",
        message="Détails de la réservation récupérés avec succès",
        data=serialized_data
    )

def build_update_response(serialized_data):
    """Build response for booking update"""
    return create_response(
        status_type="success",
        message="Réservation mise à jour avec succès",
        data=serialized_data
    )

def build_empty_detail_response(model_class):
    """Build empty response for detail statistics"""
    return create_response(
        status_type="success",
        message="Aucune réservation trouvée pour les critères spécifiés",
        data={
            'bookings': [],
            'sub_stats': build_empty_stats_response(model_class),
            'pagination': build_empty_pagination_response()
        }
    )

def validate_detail_request(request):
    """Validate request parameters for detail view"""
    params = extract_scope_and_search_key(request)
    search_key = params['search_key']
    
    is_valid, error_message = validate_search_key(search_key)
    if not is_valid:
        return False, create_response(
            status_type="error",
            message=error_message,
            http_status=status.HTTP_400_BAD_REQUEST
        ), None
    
    return True, None, params

def validate_booking_detail_request(booking_id):
    """Validate request parameters for booking detail by ID"""
    is_valid, error_message = validate_booking_id(booking_id)
    if not is_valid:
        return False, create_response(
            status_type="error",
            message=error_message,
            http_status=status.HTTP_400_BAD_REQUEST
        )
    
    return True, None