from rest_framework import serializers
from configurations.models import BankTransferPayment, PayPalPayment, PaymentMethod, StripePayment


class PaymentMethodSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentMethod
        fields = '__all__'
        

class BankTransferPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = BankTransferPayment
        fields = '__all__'

class PayPalPaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = PayPalPayment
        fields = '__all__'

class StripePaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StripePayment
        fields = '__all__'
