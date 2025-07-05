from rest_framework import serializers
from courses.models import BookingLog

class BookingLogSerializer(serializers.ModelSerializer):
    """Serializer pour les logs de booking"""
    user_display = serializers.SerializerMethodField()
    timestamp_display = serializers.SerializerMethodField()
    
    class Meta:
        model = BookingLog
        fields = ['id', 'action', 'timestamp', 'timestamp_display', 'user', 'user_display']
        read_only_fields = ['id', 'action', 'timestamp', 'user']
    
    def get_user_display(self, obj):
        """Affichage formaté de l'utilisateur"""
        if not obj.user:
            return "Système"
        return obj.user.get_full_name() or obj.user.username
    
    def get_timestamp_display(self, obj):
        """Affichage formaté du timestamp"""
        return obj.timestamp.strftime("%d/%m/%Y à %H:%M:%S")