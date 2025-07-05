from .services import BookingLogService

class BookingLogMiddleware:
    """Middleware pour capturer l'utilisateur courant dans les logs"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            BookingLogService.set_current_user(request.user)
        
        response = self.get_response(request)
        
        BookingLogService.clear_current_user()
        
        return response