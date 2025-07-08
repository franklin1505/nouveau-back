# test creation de reservation avec admin 

# import os
# import sys
# import django
# import argparse
# import uuid
# from django.utils import timezone
# from django.db import transaction
# from decimal import Decimal

# # Add parent directory to Python path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # Configure Django settings
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# django.setup()

# # Import models
# from courses.models import Booking, Estimate, EstimationLog, UserChoice, Passenger
# from configurations.models import Vehicle, MeetingPlace, PaymentMethod, VehicleType, Price
# from utilisateurs.models import CustomUser, Client, Business

# def create_booking(admin_id=1, client_id=9):
#     print("Création d'une réservation...")
    
#     try:
#         with transaction.atomic():
#             # Validate admin and client
#             admin = CustomUser.objects.get(id=admin_id, user_type='administrator')
#             client = Client.objects.get(id=client_id)
            
#             # Create or get necessary objects
#             vehicle = Vehicle.objects.first() or create_default_vehicle()
#             meeting_place = MeetingPlace.objects.first() or MeetingPlace.objects.create(
#                 address="Gare de Lyon Part-Dieu, 69003 Lyon, France"
#             )
#             payment_method = PaymentMethod.objects.first() or create_default_payment_method()

#             # Create EstimationLog with Lyon addresses
#             estimation_log = EstimationLog.objects.create(
#                 departure="Place Bellecour, 69002 Lyon, France",
#                 destination="Aéroport de Lyon-Saint Exupéry, 69125 Colombier-Saugnieu, France",
#                 pickup_date=timezone.now(),
#                 estimate_type='simple_transfer',
#                 user=admin,
#                 distance_travelled=24.5,
#                 duration_travelled="35 minutes"
#             )

#             # Create UserChoice
#             user_choice = UserChoice.objects.create(
#                 vehicle_id=vehicle.id,
#                 is_standard_cost=True
#             )

#             # Create Estimate
#             estimate = Estimate.objects.create(
#                 estimation_log=estimation_log,
#                 user_choice=user_choice,
#                 meeting_place=meeting_place,
#                 payment_method=payment_method,
#                 total_booking_cost=Decimal('100.00'),
#                 total_attributes_cost=Decimal('0.00'),
#                 number_of_luggages="2",
#                 number_of_passengers=1,
#                 is_payment_pending=True
#             )

#             # Create Passenger
#             passenger = Passenger.objects.create(
#                 name=client.get_full_name(),
#                 phone_number=client.phone_number or "0000000000",
#                 email=client.email,
#                 is_main_client=True,
#                 client=client
#             )
#             estimate.passengers.add(passenger)

#             # Create Booking
#             booking = Booking.objects.create(
#                 client=client,
#                 estimate=estimate,
#                 payment_timing='later',
#                 driver_sale_price=Decimal('80.00'),
#                 partner_sale_price=Decimal('80.00'),
#                 compensation=Decimal('0.00'),
#                 commission=Decimal('20.00'),
#                 booking_number=f"BK-{timezone.now().strftime('%y')}-{str(uuid.uuid4())[:6]}"
#             )

#             print(f"Réservation créée avec succès: {booking.booking_number}")
#             return booking

#     except CustomUser.DoesNotExist:
#         print(f"Erreur: Administrateur avec ID {admin_id} introuvable")
#         return None
#     except Client.DoesNotExist:
#         print(f"Erreur: Client avec ID {client_id} introuvable")
#         return None
#     except Exception as e:
#         print(f"Erreur lors de la création de la réservation: {str(e)}")
#         return None

# def create_default_vehicle():
#     print("Création d'un véhicule par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         vehicle_type = VehicleType.objects.filter(business=admin_business).first() or VehicleType.objects.create(
#             business=admin_business,
#             name="Private Sedan",
#             description="Berline standard économique"
#         )
#         price = Price.objects.create(
#             price_per_km=Decimal('1.50'),
#             price_per_duration=Decimal('30.00'),
#             booking_fee=Decimal('10.00'),
#             delivery_fee=Decimal('0.50'),
#             default_fee=Decimal('50.00')
#         )
#         vehicle = Vehicle.objects.create(
#             business=admin_business,
#             vehicle_type=vehicle_type,
#             brand="Renault",
#             model="Talisman",
#             manufacture_year=2022,
#             registration_number="AA-123-BB",
#             fuel_type="diesel",
#             engine="2.0 dCi",
#             interior_color="Noir",
#             exterior_color="Gris Métallisé",
#             power=160,
#             length=4.85,
#             transmission="automatic",
#             passenger_capacity=4,
#             luggage_capacity="2 grandes valises",
#             base_location="Lyon",
#             availability_type="immediate",
#             price=price,
#             validation=True
#         )
#         print("Véhicule par défaut créé avec succès.")
#         return vehicle
#     except Exception as e:
#         print(f"Erreur lors de la création du véhicule par défaut: {str(e)}")
#         raise

# def create_default_payment_method():
#     print("Création d'une méthode de paiement par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         payment_method = PaymentMethod.objects.create(
#             business=admin_business,
#             name="bank_transfer"
#         )
#         print("Méthode de paiement par défaut créée avec succès.")
#         return payment_method
#     except Exception as e:
#         print(f"Erreur lors de la création de la méthode de paiement par défaut: {str(e)}")
#         raise

# def print_summary(booking):
#     print("\n" + "="*50)
#     print("RÉSUMÉ DE LA RÉSERVATION CRÉÉE")
#     print("="*50)
    
#     if booking:
#         vehicle = Vehicle.objects.get(id=booking.estimate.user_choice.vehicle_id)
#         print("\nRéservation:")
#         print(f"   - Numéro de réservation: {booking.booking_number}")
#         print(f"   - Client: {booking.client.get_full_name()} (ID: {booking.client.id})")
#         print(f"   - Départ: {booking.estimate.estimation_log.departure}")
#         print(f"   - Destination: {booking.estimate.estimation_log.destination}")
#         print(f"   - Coût total: {booking.estimate.total_booking_cost} EUR")
#         print(f"   - Véhicule: {vehicle.brand} {vehicle.model}")
#     else:
#         print("\nAucune réservation créée en raison d'une erreur.")

#     print("\n" + "="*50)
#     print("FIN DU RÉSUMÉ")
#     print("="*50)

# def main():
#     parser = argparse.ArgumentParser(description="Create a test booking")
#     parser.add_argument('--admin_id', type=int, default=1, help='ID of the administrator')
#     parser.add_argument('--client_id', type=int, default=9, help='ID of the client')
#     args = parser.parse_args()

#     booking = create_booking(admin_id=args.admin_id, client_id=args.client_id)
#     print_summary(booking)

# if __name__ == "__main__":
#     main()


# test avec compte utilisateur client pour reserver 

# import os
# import sys
# import django
# import argparse
# import uuid
# from django.utils import timezone
# from django.db import transaction
# from decimal import Decimal

# # Add parent directory to Python path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # Configure Django settings
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# django.setup()

# # Import models
# from courses.models import Booking, Estimate, EstimationLog, UserChoice, Passenger
# from configurations.models import Vehicle, MeetingPlace, PaymentMethod, VehicleType, Price
# from utilisateurs.models import CustomUser, Client, Business

# def create_booking(client_id=9):
#     print("Création d'une réservation...")
    
#     try:
#         with transaction.atomic():
#             # Validate client and get their CustomUser instance
#             client = Client.objects.get(id=client_id)
#             client_user = CustomUser.objects.get(id=client.id, user_type='client')
            
#             # Create or get necessary objects
#             vehicle = Vehicle.objects.first() or create_default_vehicle()
#             meeting_place = MeetingPlace.objects.first() or MeetingPlace.objects.create(
#                 address="Gare de Lyon Part-Dieu, 69003 Lyon, France"
#             )
#             payment_method = PaymentMethod.objects.first() or create_default_payment_method()

#             # Create EstimationLog with client as user and Lyon addresses
#             estimation_log = EstimationLog.objects.create(
#                 departure="Place Bellecour, 69002 Lyon, France",
#                 destination="Aéroport de Lyon-Saint Exupéry, 69125 Colombier-Saugnieu, France",
#                 pickup_date=timezone.now(),
#                 estimate_type='simple_transfer',
#                 user=client_user,  # Use client's CustomUser instance
#                 distance_travelled=24.5,
#                 duration_travelled="35 minutes"
#             )

#             # Create UserChoice
#             user_choice = UserChoice.objects.create(
#                 vehicle_id=vehicle.id,
#                 is_standard_cost=True
#             )

#             # Create Estimate
#             estimate = Estimate.objects.create(
#                 estimation_log=estimation_log,
#                 user_choice=user_choice,
#                 meeting_place=meeting_place,
#                 payment_method=payment_method,
#                 total_booking_cost=Decimal('100.00'),
#                 total_attributes_cost=Decimal('0.00'),
#                 number_of_luggages="2",
#                 number_of_passengers=1,
#                 is_payment_pending=True
#             )

#             # Create Passenger
#             passenger = Passenger.objects.create(
#                 name=client.get_full_name(),
#                 phone_number=client.phone_number or "0000000000",
#                 email=client.email,
#                 is_main_client=True,
#                 client=client
#             )
#             estimate.passengers.add(passenger)

#             # Create Booking
#             booking = Booking.objects.create(
#                 client=client,
#                 estimate=estimate,
#                 payment_timing='later',
#                 driver_sale_price=Decimal('80.00'),
#                 partner_sale_price=Decimal('80.00'),
#                 compensation=Decimal('0.00'),
#                 commission=Decimal('20.00'),
#                 booking_number=f"BK-{timezone.now().strftime('%y')}-{str(uuid.uuid4())[:6]}"
#             )

#             print(f"Réservation créée avec succès: {booking.booking_number}")
#             return booking

#     except Client.DoesNotExist:
#         print(f"Erreur: Client avec ID {client_id} introuvable")
#         return None
#     except CustomUser.DoesNotExist:
#         print(f"Erreur: Utilisateur CustomUser associé au client ID {client_id} introuvable")
#         return None
#     except Exception as e:
#         print(f"Erreur lors de la création de la réservation: {str(e)}")
#         return None

# def create_default_vehicle():
#     print("Création d'un véhicule par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         vehicle_type = VehicleType.objects.filter(business=admin_business).first() or VehicleType.objects.create(
#             business=admin_business,
#             name="Private Sedan",
#             description="Berline standard économique"
#         )
#         price = Price.objects.create(
#             price_per_km=Decimal('1.50'),
#             price_per_duration=Decimal('30.00'),
#             booking_fee=Decimal('10.00'),
#             delivery_fee=Decimal('0.50'),
#             default_fee=Decimal('50.00')
#         )
#         vehicle = Vehicle.objects.create(
#             business=admin_business,
#             vehicle_type=vehicle_type,
#             brand="Renault",
#             model="Talisman",
#             manufacture_year=2022,
#             registration_number="AA-123-BB",
#             fuel_type="diesel",
#             engine="2.0 dCi",
#             interior_color="Noir",
#             exterior_color="Gris Métallisé",
#             power=160,
#             length=4.85,
#             transmission="automatic",
#             passenger_capacity=4,
#             luggage_capacity="2 grandes valises",
#             base_location="Lyon",
#             availability_type="immediate",
#             price=price,
#             validation=True
#         )
#         print("Véhicule par défaut créé avec succès.")
#         return vehicle
#     except Exception as e:
#         print(f"Erreur lors de la création du véhicule par défaut: {str(e)}")
#         raise

# def create_default_payment_method():
#     print("Création d'une méthode de paiement par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         payment_method = PaymentMethod.objects.create(
#             business=admin_business,
#             name="bank_transfer"
#         )
#         print("Méthode de paiement par défaut créée avec succès.")
#         return payment_method
#     except Exception as e:
#         print(f"Erreur lors de la création de la méthode de paiement par défaut: {str(e)}")
#         raise

# def print_summary(booking):
#     print("\n" + "="*50)
#     print("RÉSUMÉ DE LA RÉSERVATION CRÉÉE")
#     print("="*50)
    
#     if booking:
#         vehicle = Vehicle.objects.get(id=booking.estimate.user_choice.vehicle_id)
#         print("\nRéservation:")
#         print(f"   - Numéro de réservation: {booking.booking_number}")
#         print(f"   - Client: {booking.client.get_full_name()} (ID: {booking.client.id})")
#         print(f"   - Départ: {booking.estimate.estimation_log.departure}")
#         print(f"   - Destination: {booking.estimate.estimation_log.destination}")
#         print(f"   - Coût total: {booking.estimate.total_booking_cost} EUR")
#         print(f"   - Véhicule: {vehicle.brand} {vehicle.model}")
#     else:
#         print("\nAucune réservation créée en raison d'une erreur.")

#     print("\n" + "="*50)
#     print("FIN DU RÉSUMÉ")
#     print("="*50)

# def main():
#     parser = argparse.ArgumentParser(description="Create a test booking")
#     parser.add_argument('--client_id', type=int, default=9, help='ID of the client')
#     args = parser.parse_args()

#     booking = create_booking(client_id=args.client_id)
#     print_summary(booking)

# if __name__ == "__main__":
#     main()


# reservation au nom d'u passagers ponctuelle 

# import os
# import sys
# import django
# import argparse
# import uuid
# from django.utils import timezone
# from django.db import transaction
# from decimal import Decimal

# # Add parent directory to Python path
# sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# # Configure Django settings
# os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
# django.setup()

# # Import models
# from courses.models import Booking, Estimate, EstimationLog, UserChoice, Passenger
# from configurations.models import Vehicle, MeetingPlace, PaymentMethod, VehicleType, Price
# from utilisateurs.models import CustomUser, Business

# def create_booking(admin_id=1, passenger1_name="John Doe", passenger1_email="john.doe@example.com", passenger1_phone="+33612345678", 
#                   passenger2_name="Jane Smith", passenger2_email="jane.smith@example.com", passenger2_phone="+33687654321"):
#     print("Création d'une réservation pour deux passagers ponctuels...")
    
#     try:
#         with transaction.atomic():
#             # Validate admin
#             admin = CustomUser.objects.get(id=admin_id, user_type='administrator')
            
#             # Create or get necessary objects
#             vehicle = Vehicle.objects.first() or create_default_vehicle()
#             meeting_place = MeetingPlace.objects.first() or MeetingPlace.objects.create(
#                 address="Gare de Lyon Part-Dieu, 69003 Lyon, France"
#             )
#             payment_method = PaymentMethod.objects.first() or create_default_payment_method()

#             # Create EstimationLog with admin as user and Lyon addresses
#             estimation_log = EstimationLog.objects.create(
#                 departure="Place Bellecour, 69002 Lyon, France",
#                 destination="Aéroport de Lyon-Saint Exupéry, 69125 Colombier-Saugnieu, France",
#                 pickup_date=timezone.now(),
#                 estimate_type='simple_transfer',
#                 user=admin,
#                 distance_travelled=24.5,
#                 duration_travelled="35 minutes"
#             )

#             # Create UserChoice
#             user_choice = UserChoice.objects.create(
#                 vehicle_id=vehicle.id,
#                 is_standard_cost=True
#             )

#             # Create Estimate
#             estimate = Estimate.objects.create(
#                 estimation_log=estimation_log,
#                 user_choice=user_choice,
#                 meeting_place=meeting_place,
#                 payment_method=payment_method,
#                 total_booking_cost=Decimal('100.00'),
#                 total_attributes_cost=Decimal('0.00'),
#                 number_of_luggages="2",
#                 number_of_passengers=2,  # Two passengers
#                 is_payment_pending=True
#             )

#             # Create Passenger 1 (occasional, no Client link)
#             passenger1 = Passenger.objects.create(
#                 name=passenger1_name,
#                 phone_number=passenger1_phone,
#                 email=passenger1_email,
#                 is_main_client=True,
#                 client=None  # No Client account
#             )

#             # Create Passenger 2 (occasional, no Client link)
#             passenger2 = Passenger.objects.create(
#                 name=passenger2_name,
#                 phone_number=passenger2_phone,
#                 email=passenger2_email,
#                 is_main_client=False,
#                 client=None  # No Client account
#             )

#             # Add passengers to estimate
#             estimate.passengers.add(passenger1, passenger2)

#             # Create Booking (no Client association)
#             booking = Booking.objects.create(
#                 client=None,  # No Client for occasional passengers
#                 estimate=estimate,
#                 payment_timing='later',
#                 driver_sale_price=Decimal('80.00'),
#                 partner_sale_price=Decimal('80.00'),
#                 compensation=Decimal('0.00'),
#                 commission=Decimal('20.00'),
#                 booking_number=f"BK-{timezone.now().strftime('%y')}-{str(uuid.uuid4())[:6]}"
#             )

#             print(f"Réservation créée avec succès: {booking.booking_number}")
#             return booking

#     except CustomUser.DoesNotExist:
#         print(f"Erreur: Administrateur avec ID {admin_id} introuvable")
#         return None
#     except Exception as e:
#         print(f"Erreur lors de la création de la réservation: {str(e)}")
#         return None

# def create_default_vehicle():
#     print("Création d'un véhicule par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         vehicle_type = VehicleType.objects.filter(business=admin_business).first() or VehicleType.objects.create(
#             business=admin_business,
#             name="Private Sedan",
#             description="Berline standard économique"
#         )
#         price = Price.objects.create(
#             price_per_km=Decimal('1.50'),
#             price_per_duration=Decimal('30.00'),
#             booking_fee=Decimal('10.00'),
#             delivery_fee=Decimal('0.50'),
#             default_fee=Decimal('50.00')
#         )
#         vehicle = Vehicle.objects.create(
#             business=admin_business,
#             vehicle_type=vehicle_type,
#             brand="Renault",
#             model="Talisman",
#             manufacture_year=2022,
#             registration_number="AA-123-BB",
#             fuel_type="diesel",
#             engine="2.0 dCi",
#             interior_color="Noir",
#             exterior_color="Gris Métallisé",
#             power=160,
#             length=4.85,
#             transmission="automatic",
#             passenger_capacity=4,
#             luggage_capacity="2 grandes valises",
#             base_location="Lyon",
#             availability_type="immediate",
#             price=price,
#             validation=True
#         )
#         print("Véhicule par défaut créé avec succès.")
#         return vehicle
#     except Exception as e:
#         print(f"Erreur lors de la création du véhicule par défaut: {str(e)}")
#         raise

# def create_default_payment_method():
#     print("Création d'une méthode de paiement par défaut...")
#     try:
#         admin_business = Business.objects.get(business_type="my_business")
#         payment_method = PaymentMethod.objects.create(
#             business=admin_business,
#             name="bank_transfer"
#         )
#         print("Méthode de paiement par défaut créée avec succès.")
#         return payment_method
#     except Exception as e:
#         print(f"Erreur lors de la création de la méthode de paiement par défaut: {str(e)}")
#         raise

# def print_summary(booking):
#     print("\n" + "="*50)
#     print("RÉSUMÉ DE LA RÉSERVATION CRÉÉE")
#     print("="*50)
    
#     if booking:
#         vehicle = Vehicle.objects.get(id=booking.estimate.user_choice.vehicle_id)
#         passengers = booking.estimate.passengers.all()
#         print("\nRéservation:")
#         print(f"   - Numéro de réservation: {booking.booking_number}")
#         print(f"   - Passagers:")
#         for passenger in passengers:
#             print(f"      - {passenger.name} (Email: {passenger.email}, Téléphone: {passenger.phone_number})")
#         print(f"   - Départ: {booking.estimate.estimation_log.departure}")
#         print(f"   - Destination: {booking.estimate.estimation_log.destination}")
#         print(f"   - Coût total: {booking.estimate.total_booking_cost} EUR")
#         print(f"   - Véhicule: {vehicle.brand} {vehicle.model}")
#     else:
#         print("\nAucune réservation créée en raison d'une erreur.")

#     print("\n" + "="*50)
#     print("FIN DU RÉSUMÉ")
#     print("="*50)

# def main():
#     parser = argparse.ArgumentParser(description="Create a test booking for two occasional passengers")
#     parser.add_argument('--admin_id', type=int, default=1, help='ID of the administrator')
#     parser.add_argument('--passenger1_name', type=str, default="John Doe", help='Name of the first passenger')
#     parser.add_argument('--passenger1_email', type=str, default="john.doe@example.com", help='Email of the first passenger')
#     parser.add_argument('--passenger1_phone', type=str, default="+33612345678", help='Phone number of the first passenger')
#     parser.add_argument('--passenger2_name', type=str, default="Jane Smith", help='Name of the second passenger')
#     parser.add_argument('--passenger2_email', type=str, default="jane.smith@example.com", help='Email of the second passenger')
#     parser.add_argument('--passenger2_phone', type=str, default="+33687654321", help='Phone number of the second passenger')
#     args = parser.parse_args()

#     booking = create_booking(
#         admin_id=args.admin_id,
#         passenger1_name=args.passenger1_name,
#         passenger1_email=args.passenger1_email,
#         passenger1_phone=args.passenger1_phone,
#         passenger2_name=args.passenger2_name,
#         passenger2_email=args.passenger2_email,
#         passenger2_phone=args.passenger2_phone
#     )
#     print_summary(booking)

# if __name__ == "__main__":
#     main()


#test pour update une reservation /api/reservations/booking/
import os
import sys
import django
import json
from django.test import Client

# Adjust path to project root
sys.path.append('/Users/thedon/Documents/nouvelle_version_projet/Nouveau_back')

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

# Import models and other Django components *after* django.setup()
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from courses.models import Booking, Passenger
from utilisateurs.models import CustomUser

def test_update_bookings(username="admin_manager", password="Admin@123"):
    print("Test de mise à jour des réservations...")
    
    try:
        # Initialize Django test client
        client = Client()
        
        # Authenticate as admin and get JWT token
        CustomUser = get_user_model()
        admin = CustomUser.objects.get(username=username)
        
        # Verify password (optional, for debugging)
        if not admin.check_password(password):
            print(f"Erreur: Mot de passe incorrect pour {username}")
            return None
        
        # Get JWT token
        refresh = RefreshToken.for_user(admin)
        access_token = str(refresh.access_token)
        
        # Test case 1: Update booking ID 10
        booking_id_10 = 10
        update_data_10 = {
            "status": "confirmed",
            "billing_status": "invoiced",
            "payment_timing": "now"
        }
        print(f"\nMise à jour de la réservation ID {booking_id_10}...")
        response_10 = client.patch(
            f"/api/reservations/booking/{booking_id_10}/update/",
            data=json.dumps(update_data_10),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        
        # Test case 2: Update booking ID 11 with new passenger
        booking_id_11 = 11
        update_data_11 = {
            "status": "completed",
            "billing_status": "paid",
            "estimate": {
                "passengers": [
                    {"name": "New Passenger", "email": "new.passenger@example.com", "phone_number": "+33699998888"}
                ]
            }
        }
        print(f"\nMise à jour de la réservation ID {booking_id_11}...")
        response_11 = client.patch(
            f"/api/reservations/booking/{booking_id_11}/update/",
            data=json.dumps(update_data_11),
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {access_token}"
        )
        
        # Collect results
        results = [
            {"booking_id": booking_id_10, "response": response_10},
            {"booking_id": booking_id_11, "response": response_11}
        ]
        
        return results
    
    except CustomUser.DoesNotExist:
        print(f"Erreur: Administrateur avec username {username} introuvable")
        return None
    except Exception as e:
        print(f"Erreur lors du test de mise à jour: {str(e)}")
        return None

def print_summary(results):
    print("\n" + "="*50)
    print("RÉSUMÉ DES TESTS DE MISE À JOUR")
    print("="*50)
    
    if not results:
        print("\nAucun test effectué en raison d'une erreur.")
        return
    
    for result in results:
        booking_id = result["booking_id"]
        response = result["response"]
        print(f"\nRéservation ID {booking_id}:")
        
        if response.status_code == 200:
            try:
                booking = Booking.objects.get(id=booking_id)
                print(f"   - Statut HTTP: {response.status_code} (Succès)")
                print(f"   - Numéro de réservation: {booking.booking_number}")
                print(f"   - Statut: {booking.status} ({booking.get_status_display()})")
                print(f"   - Statut de facturation: {booking.billing_status} ({booking.get_billing_status_display()})")
                print(f"   - Moment du paiement: {booking.payment_timing} ({booking.get_payment_timing_display()})")
                if booking_id == 11:
                    passengers = booking.estimate.passengers.all()
                    print(f"   - Passagers:")
                    for passenger in passengers:
                        print(f"      - {passenger.name} (Email: {passenger.email}, Téléphone: {passenger.phone_number})")
            except Booking.DoesNotExist:
                print(f"   - Erreur: Réservation ID {booking_id} non trouvée dans la base de données")
        else:
            print(f"   - Statut HTTP: {response.status_code} (Échec)")
            try:
                print(f"   - Message: {json.loads(response.content).get('message', 'Erreur inconnue')}")
            except json.JSONDecodeError:
                print(f"   - Message: Contenu de la réponse non JSON: {response.content}")
    
    print("\n" + "="*50)
    print("FIN DU RÉSUMÉ")
    print("="*50)

def main():
    results = test_update_bookings()
    print_summary(results)

if __name__ == "__main__":
    main()