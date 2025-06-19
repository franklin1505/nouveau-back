from django.db.models.signals import post_save
from django.dispatch import receiver
from utilisateurs.models import Client
from courses.models import Passenger

@receiver(post_save, sender=Client)
def create_auto_passenger_for_client(sender, instance, created, **kwargs):
    """
    Crée automatiquement un passager "Moi-même" quand un client est créé
    """
    if created and not instance.is_partial:  # Seulement pour clients complets
        # Vérifier qu'il n'existe pas déjà un passager auto pour ce client
        if not Passenger.objects.filter(client=instance, name="Moi-même").exists():
            Passenger.objects.create(
                name="Moi-même",
                phone_number=instance.phone_number,
                email=instance.email,
                is_main_client=True,  # ✅ Marquer comme client principal
                client=instance
            )
