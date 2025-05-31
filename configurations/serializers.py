
from rest_framework import serializers
from configurations.models import Notification

class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['id', 'title', 'message', 'type', 'status', 'created_at']

class NotificationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ['status']
        extra_kwargs = {
            'status': {'required': True, 'choices': ['unread', 'archived']}
        }