from rest_framework import serializers
from .models import VAT, APIKey, AccessCode, EmailSettings, InvoiceConfiguration, QuoteConfiguration, StaticContent, Urls

class EmailSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailSettings
        fields = '__all__'
        
class APIKeySerializer(serializers.ModelSerializer):
    class Meta:
        model = APIKey
        fields = '__all__'


class BaseConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        fields = '__all__'

class InvoiceConfigurationSerializer(BaseConfigurationSerializer):
    class Meta(BaseConfigurationSerializer.Meta):
        model = InvoiceConfiguration

class QuoteConfigurationSerializer(BaseConfigurationSerializer):
    class Meta(BaseConfigurationSerializer.Meta):
        model = QuoteConfiguration
        
class UrlsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Urls
        fields = '__all__'
        
class AccessCodeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessCode
        fields = '__all__'

    def validate_standard_password(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Le mot de passe standard doit contenir exactement 6 chiffres.")
        return value

    def validate_admin_password(self, value):
        if not value.isdigit() or len(value) != 6:
            raise serializers.ValidationError("Le mot de passe admin doit contenir exactement 6 chiffres.")
        return value
    
class VATSerializer(serializers.ModelSerializer):
    class Meta:
        model = VAT
        fields = '__all__'
        
class StaticContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StaticContent
        fields = '__all__'