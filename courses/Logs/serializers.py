from rest_framework import serializers
from courses.models import BookingLog

class BookingLogSerializer(serializers.ModelSerializer):
    user_display = serializers.SerializerMethodField()
    formatted_date = serializers.SerializerMethodField()
    formatted_time = serializers.SerializerMethodField()
    
    class Meta:
        model = BookingLog
        fields = ['id', 'action', 'timestamp', 'formatted_date', 'formatted_time', 'user', 'user_display']
        read_only_fields = fields
    
    def get_user_display(self, obj):
        if not obj.user:
            return "Système"
        user_name = obj.user.get_full_name() or obj.user.username
        if hasattr(obj.user, 'is_superuser') and obj.user.is_superuser:
            return f"{user_name} (Admin)"
        elif hasattr(obj.user, 'user_type'):
            user_type_map = {
                'client': 'Client',
                'driver': 'Chauffeur', 
                'admin': 'Admin',
                'administrator': 'Admin',
                'partner': 'Partenaire'
            }
            type_name = user_type_map.get(obj.user.user_type, 'Utilisateur')
            return f"{user_name} ({type_name})"
        return user_name
    
    def get_formatted_date(self, obj):
        return obj.timestamp.strftime("%d/%m/%Y")
    
    def get_formatted_time(self, obj):
        return obj.timestamp.strftime("%H:%M:%S")