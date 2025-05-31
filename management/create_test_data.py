import os
import sys
import django
import random
from decimal import Decimal
from datetime import datetime, timedelta

# Ajouter le répertoire parent au chemin Python pour trouver les modules du projet
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Configuration Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
django.setup()

from django.utils import timezone

# Import des modèles
from utilisateurs.models import Administrator, Partner, Driver, Client, Business
from configurations.models import (
    VehicleType, Vehicle, Price, Adjustment, PromoCode, Package, TariffRule,
    PaymentMethod
)
from django.db import transaction

# Fonction principale
def create_test_data():
    print("Création des données de test...")
    
    # 1. Création des utilisateurs
    admin = create_administrator()
    partner = create_partner()
    
    # 2. Création des entreprises
    admin_business = create_admin_business(admin)
    partner_business = create_partner_business(partner)
    
    # 3. Création des types de véhicules
    vehicle_types = create_vehicle_types(admin_business, partner_business)
    
    # 4. Création des chauffeurs (après les entreprises)
    drivers = create_drivers(partner_business)
    
    # 5. Création des clients
    clients = create_clients()
    
    # 6. Création des véhicules
    vehicles = create_vehicles(admin_business, partner_business, vehicle_types)
    
    # 7. Création des règles tarifaires
    create_tariff_rules(vehicles, clients)
    
    print("Création des données de test terminée avec succès!")
    
    # Afficher un résumé des données créées
    print_summary(admin, partner, drivers, clients, vehicles)

# Fonctions de création des utilisateurs
def create_administrator():
    print("Création de l'administrateur...")
    try:
        admin = Administrator.objects.get(username="admin_manager")
        print("L'administrateur existe déjà.")
        return admin
    except Administrator.DoesNotExist:
        admin = Administrator.objects.create(
            username="admin_manager",
            email="dntessah@gmail.com",
            first_name="Admin",
            last_name="Manager",
            phone_number="+33123456789",
            user_type="administrator",
            role="manager"
        )
        admin.set_password("Admin@123")
        admin.save()
        print("Administrateur créé avec succès.")
        return admin

def create_partner():
    print("Création du partenaire...")
    try:
        partner = Partner.objects.get(username="partner_test")
        print("Le partenaire existe déjà.")
        return partner
    except Partner.DoesNotExist:
        partner = Partner.objects.create(
            username="partner_test",
            email="frntessah@gmail.com",
            first_name="Partner",
            last_name="Test",
            phone_number="+33987654321",
            user_type="partner"
        )
        partner.set_password("Partner@123")
        partner.save()
        print("Partenaire créé avec succès.")
        return partner

def create_drivers(partner_business):
    print("Création des chauffeurs...")
    drivers = []
    
    # Chauffeur indépendant
    try:
        driver1 = Driver.objects.get(username="driver_independent")
        print("Le chauffeur indépendant existe déjà.")
    except Driver.DoesNotExist:
        driver1 = Driver.objects.create(
            username="driver_independent",
            email="driver1@example.com",
            first_name="Driver",
            last_name="Independent",
            phone_number="+33123456790",
            user_type="driver",
            is_independent=True,
            years_experience=5,
            is_validated=True,
            spoken_languages=["french", "english"]
        )
        driver1.set_password("Driver1@123")
        driver1.save()
        print("Chauffeur indépendant créé avec succès.")
    drivers.append(driver1)
    
    # Chauffeur lié à l'entreprise partenaire
    try:
        driver2 = Driver.objects.get(username="driver_company")
        print("Le chauffeur d'entreprise existe déjà.")
    except Driver.DoesNotExist:
        driver2 = Driver.objects.create(
            username="driver_company",
            email="driver2@example.com",
            first_name="Driver",
            last_name="Company",
            phone_number="+33123456791",
            user_type="driver",
            is_independent=False,
            business=partner_business,
            years_experience=3,
            is_validated=True,
            spoken_languages=["french", "spanish"]
        )
        driver2.set_password("Driver2@123")
        driver2.save()
        print("Chauffeur d'entreprise créé avec succès.")
    drivers.append(driver2)
    
    return drivers

def create_clients():
    print("Création des clients...")
    clients = []
    
    # Client simple
    try:
        client1 = Client.objects.get(username="client_simple")
        print("Le client simple existe déjà.")
    except Client.DoesNotExist:
        client1 = Client.objects.create(
            username="client_simple",
            email="client1@example.com",
            first_name="Client",
            last_name="Simple",
            phone_number="+33123456792",
            user_type="client",
            client_type="simple"
        )
        client1.set_password("Client1@123")
        client1.save()
        print("Client simple créé avec succès.")
    clients.append(client1)
    
    # Client agence
    try:
        client2 = Client.objects.get(username="client_agency")
        print("Le client agence existe déjà.")
    except Client.DoesNotExist:
        client2 = Client.objects.create(
            username="client_agency",
            email="client2@example.com",
            first_name="Client",
            last_name="Agency",
            phone_number="+33123456793",
            user_type="client",
            client_type="agency"
        )
        client2.set_password("Client2@123")
        client2.save()
        print("Client agence créé avec succès.")
    clients.append(client2)
    
    # Client entreprise
    try:
        client3 = Client.objects.get(username="client_company")
        print("Le client entreprise existe déjà.")
    except Client.DoesNotExist:
        client3 = Client.objects.create(
            username="client_company",
            email="client3@example.com",
            first_name="Client",
            last_name="Company",
            phone_number="+33123456794",
            user_type="client",
            client_type="company"
        )
        client3.set_password("Client3@123")
        client3.save()
        print("Client entreprise créé avec succès.")
    clients.append(client3)
    
    # Client VIP
    try:
        client4 = Client.objects.get(username="client_vip")
        print("Le client VIP existe déjà.")
    except Client.DoesNotExist:
        client4 = Client.objects.create(
            username="client_vip",
            email="client4@example.com",
            first_name="Client",
            last_name="VIP",
            phone_number="+33123456795",
            user_type="client",
            client_type="simple"
        )
        client4.set_password("Client4@123")
        client4.save()
        print("Client VIP créé avec succès.")
    clients.append(client4)
    
    return clients

# Fonctions de création des entreprises
def create_admin_business(admin):
    print("Création de l'entreprise principale...")
    try:
        business = Business.objects.get(business_type="my_business")
        print("L'entreprise principale existe déjà.")
        return business
    except Business.DoesNotExist:
        business = Business.objects.create(
            name="NDJO Transport",
            address="123 Rue Principale, Paris",
            email="contact@ndjo.com",
            phone_number="+33123456789",
            website="https://ndjo.com",
            description="Entreprise principale de transport",
            operation_location="Paris",
            business_type="my_business",
            validation=True,
            main_user=admin
        )
        print("Entreprise principale créée avec succès.")
        
        # Création des méthodes de paiement par défaut
        PaymentMethod.add_default_payment_methods(business)
        
        return business

def create_partner_business(partner):
    print("Création de l'entreprise partenaire...")
    try:
        business = Business.objects.filter(partner=partner).first()
        if business:
            print("L'entreprise partenaire existe déjà.")
            return business
    except Exception:
        pass
    
    business = Business.objects.create(
        name="Partner Transport",
        address="456 Avenue Secondaire, Lyon",
        email="contact@partner.com",
        phone_number="+33987654321",
        website="https://partner.com",
        description="Entreprise partenaire de transport",
        operation_location="Lyon",
        business_type="partner_business",
        validation=True,
        partner=partner
    )
    print("Entreprise partenaire créée avec succès.")
    
    # Tentative de création des méthodes de paiement par défaut
    try:
        PaymentMethod.add_default_payment_methods(business)
        print("Méthodes de paiement créées pour l'entreprise partenaire.")
    except Exception as e:
        print(f"Impossible de créer les méthodes de paiement pour l'entreprise partenaire: {str(e)}")
        print("Cela n'empêchera pas le reste du script de fonctionner.")
    
    return business

# Fonctions de création des véhicules
def create_vehicle_types(admin_business, partner_business):
    print("Création des types de véhicules...")
    vehicle_types = {}
    
    # Types pour l'entreprise principale
    for business, prefix in [(admin_business, "admin"), (partner_business, "partner")]:
        # Private Sedan
        try:
            private_sedan = VehicleType.objects.get(business=business, name="Private Sedan")
            print(f"Le type 'Private Sedan' existe déjà pour {business.name}.")
        except VehicleType.DoesNotExist:
            private_sedan = VehicleType.objects.create(
                business=business,
                name="Private Sedan",
                description="Berline standard économique"
            )
            print(f"Type 'Private Sedan' créé pour {business.name}.")
        
        # Executive Sedan
        try:
            executive_sedan = VehicleType.objects.get(business=business, name="Executive Sedan")
            print(f"Le type 'Executive Sedan' existe déjà pour {business.name}.")
        except VehicleType.DoesNotExist:
            executive_sedan = VehicleType.objects.create(
                business=business,
                name="Executive Sedan",
                description="Berline de prestige classe S"
            )
            print(f"Type 'Executive Sedan' créé pour {business.name}.")
        
        # Van
        try:
            van = VehicleType.objects.get(business=business, name="Van")
            print(f"Le type 'Van' existe déjà pour {business.name}.")
        except VehicleType.DoesNotExist:
            van = VehicleType.objects.create(
                business=business,
                name="Van",
                description="Mini Van et Van économique"
            )
            print(f"Type 'Van' créé pour {business.name}.")
        
        # Business Van
        try:
            business_van = VehicleType.objects.get(business=business, name="Business Van")
            print(f"Le type 'Business Van' existe déjà pour {business.name}.")
        except VehicleType.DoesNotExist:
            business_van = VehicleType.objects.create(
                business=business,
                name="Business Van",
                description="Van de prestige classe V"
            )
            print(f"Type 'Business Van' créé pour {business.name}.")
        
        vehicle_types[f"{prefix}_private_sedan"] = private_sedan
        vehicle_types[f"{prefix}_executive_sedan"] = executive_sedan
        vehicle_types[f"{prefix}_van"] = van
        vehicle_types[f"{prefix}_business_van"] = business_van
    
    return vehicle_types

def create_vehicles(admin_business, partner_business, vehicle_types):
    print("Création des véhicules...")
    vehicles = []
    
    # Données des véhicules
    vehicle_data = [
        # Véhicules basés à Lyon (6)
        {
            "business": admin_business,
            "vehicle_type": vehicle_types["admin_private_sedan"],
            "brand": "Renault",
            "model": "Talisman",
            "manufacture_year": 2022,
            "registration_number": "AA-123-BB",
            "fuel_type": "diesel",
            "engine": "2.0 dCi",
            "interior_color": "Noir",
            "exterior_color": "Gris Métallisé",
            "power": 160,
            "length": 4.85,
            "transmission": "automatic",
            "passenger_capacity": 4,
            "luggage_capacity": "2 grandes valises",
            "base_location": "Lyon",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "1.50",
                "price_per_duration": "30.00",
                "booking_fee": "10.00",
                "delivery_fee": "0.50",
                "default_fee": "50.00"
            }
        },
        {
            "business": partner_business,
            "vehicle_type": vehicle_types["partner_private_sedan"],
            "brand": "Peugeot",
            "model": "508",
            "manufacture_year": 2021,
            "registration_number": "CC-456-DD",
            "fuel_type": "hybrid",
            "engine": "1.6 Hybrid",
            "interior_color": "Beige",
            "exterior_color": "Noir",
            "power": 180,
            "length": 4.75,
            "transmission": "automatic",
            "passenger_capacity": 4,
            "luggage_capacity": "2 grandes valises",
            "base_location": "Lyon",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "1.60",
                "price_per_duration": "32.00",
                "booking_fee": "12.00",
                "delivery_fee": "0.60",
                "default_fee": "55.00"
            }
        },
        {
            "business": admin_business,
            "vehicle_type": vehicle_types["admin_executive_sedan"],
            "brand": "Mercedes",
            "model": "Classe S",
            "manufacture_year": 2023,
            "registration_number": "EE-789-FF",
            "fuel_type": "petrol",
            "engine": "3.0 V6",
            "interior_color": "Cuir Beige",
            "exterior_color": "Noir Métallisé",
            "power": 320,
            "length": 5.2,
            "transmission": "automatic",
            "passenger_capacity": 4,
            "luggage_capacity": "3 grandes valises",
            "base_location": "Lyon",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "2.50",
                "price_per_duration": "60.00",
                "booking_fee": "20.00",
                "delivery_fee": "1.00",
                "default_fee": "100.00"
            }
        },
        {
            "business": partner_business,
            "vehicle_type": vehicle_types["partner_executive_sedan"],
            "brand": "BMW",
            "model": "Série 7",
            "manufacture_year": 2022,
            "registration_number": "GG-012-HH",
            "fuel_type": "electric",
            "engine": "Electric",
            "interior_color": "Cuir Noir",
            "exterior_color": "Blanc",
            "power": 340,
            "length": 5.1,
            "transmission": "automatic",
            "passenger_capacity": 4,
            "luggage_capacity": "3 grandes valises",
            "base_location": "Lyon",
            "availability_type": "delayed",
            "availability_time": 2,
            "price_data": {
                "price_per_km": "2.70",
                "price_per_duration": "65.00",
                "booking_fee": "25.00",
                "delivery_fee": "1.20",
                "default_fee": "110.00"
            }
        },
        {
            "business": admin_business,
            "vehicle_type": vehicle_types["admin_van"],
            "brand": "Volkswagen",
            "model": "Caravelle",
            "manufacture_year": 2021,
            "registration_number": "II-345-JJ",
            "fuel_type": "diesel",
            "engine": "2.0 TDI",
            "interior_color": "Gris",
            "exterior_color": "Bleu",
            "power": 150,
            "length": 5.3,
            "transmission": "manual",
            "passenger_capacity": 8,
            "luggage_capacity": "8 valises",
            "base_location": "Lyon",
            "availability_type": "on_demand",
            "price_data": {
                "price_per_km": "2.00",
                "price_per_duration": "45.00",
                "booking_fee": "15.00",
                "delivery_fee": "0.80",
                "default_fee": "80.00"
            }
        },
        {
            "business": partner_business,
            "vehicle_type": vehicle_types["partner_business_van"],
            "brand": "Mercedes",
            "model": "Classe V",
            "manufacture_year": 2023,
            "registration_number": "KK-678-LL",
            "fuel_type": "diesel",
            "engine": "2.2 CDI",
            "interior_color": "Cuir Marron",
            "exterior_color": "Gris Anthracite",
            "power": 190,
            "length": 5.4,
            "transmission": "automatic",
            "passenger_capacity": 7,
            "luggage_capacity": "7 valises",
            "base_location": "Lyon",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "2.80",
                "price_per_duration": "70.00",
                "booking_fee": "30.00",
                "delivery_fee": "1.50",
                "default_fee": "120.00"
            }
        },
        
        # Véhicules basés ailleurs (4)
        {
            "business": admin_business,
            "vehicle_type": vehicle_types["admin_private_sedan"],
            "brand": "Citroën",
            "model": "C5",
            "manufacture_year": 2021,
            "registration_number": "MM-901-NN",
            "fuel_type": "diesel",
            "engine": "1.5 BlueHDi",
            "interior_color": "Gris",
            "exterior_color": "Rouge",
            "power": 130,
            "length": 4.7,
            "transmission": "automatic",
            "passenger_capacity": 5,
            "luggage_capacity": "2 grandes valises",
            "base_location": "Paris",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "1.40",
                "price_per_duration": "28.00",
                "booking_fee": "8.00",
                "delivery_fee": "0.40",
                "default_fee": "45.00"
            }
        },
        {
            "business": partner_business,
            "vehicle_type": vehicle_types["partner_executive_sedan"],
            "brand": "Audi",
            "model": "A8",
            "manufacture_year": 2022,
            "registration_number": "OO-234-PP",
            "fuel_type": "hybrid",
            "engine": "3.0 TFSI e-tron",
            "interior_color": "Cuir Blanc",
            "exterior_color": "Noir",
            "power": 380,
            "length": 5.3,
            "transmission": "automatic",
            "passenger_capacity": 4,
            "luggage_capacity": "3 grandes valises",
            "base_location": "Paris",
            "availability_type": "delayed",
            "availability_time": 3,
            "price_data": {
                "price_per_km": "3.00",
                "price_per_duration": "75.00",
                "booking_fee": "35.00",
                "delivery_fee": "1.80",
                "default_fee": "150.00"
            }
        },
        {
            "business": admin_business,
            "vehicle_type": vehicle_types["admin_van"],
            "brand": "Renault",
            "model": "Trafic",
            "manufacture_year": 2020,
            "registration_number": "QQ-567-RR",
            "fuel_type": "diesel",
            "engine": "2.0 dCi",
            "interior_color": "Noir",
            "exterior_color": "Blanc",
            "power": 145,
            "length": 5.1,
            "transmission": "manual",
            "passenger_capacity": 9,
            "luggage_capacity": "9 valises",
            "base_location": "Marseille",
            "availability_type": "on_demand",
            "price_data": {
                "price_per_km": "1.90",
                "price_per_duration": "40.00",
                "booking_fee": "12.00",
                "delivery_fee": "0.70",
                "default_fee": "75.00"
            }
        },
        {
            "business": partner_business,
            "vehicle_type": vehicle_types["partner_business_van"],
            "brand": "Mercedes",
            "model": "Sprinter",
            "manufacture_year": 2022,
            "registration_number": "SS-890-TT",
            "fuel_type": "diesel",
            "engine": "2.2 CDI",
            "interior_color": "Cuir Noir",
            "exterior_color": "Gris",
            "power": 170,
            "length": 5.9,
            "transmission": "automatic",
            "passenger_capacity": 8,
            "luggage_capacity": "10 valises",
            "base_location": "Bordeaux",
            "availability_type": "immediate",
            "price_data": {
                "price_per_km": "2.60",
                "price_per_duration": "65.00",
                "booking_fee": "25.00",
                "delivery_fee": "1.30",
                "default_fee": "110.00"
            }
        }
    ]
    
    # Création des véhicules
    for data in vehicle_data:
        try:
            vehicle = Vehicle.objects.filter(
                business=data["business"],
                brand=data["brand"],
                model=data["model"],
                registration_number=data["registration_number"]
            ).first()
            
            if vehicle:
                print(f"Le véhicule {data['brand']} {data['model']} existe déjà.")
                vehicles.append(vehicle)
                continue
                
            # Création du prix
            price = Price.objects.create(
                price_per_km=data["price_data"]["price_per_km"],
                price_per_duration=data["price_data"]["price_per_duration"],
                booking_fee=data["price_data"]["booking_fee"],
                delivery_fee=data["price_data"]["delivery_fee"],
                default_fee=data["price_data"]["default_fee"]
            )
            
            # Création du véhicule
            vehicle = Vehicle.objects.create(
                business=data["business"],
                vehicle_type=data["vehicle_type"],
                brand=data["brand"],
                model=data["model"],
                manufacture_year=data["manufacture_year"],
                registration_number=data["registration_number"],
                fuel_type=data["fuel_type"],
                engine=data["engine"],
                interior_color=data["interior_color"],
                exterior_color=data["exterior_color"],
                power=data["power"],
                length=data["length"],
                transmission=data["transmission"],
                passenger_capacity=data["passenger_capacity"],
                luggage_capacity=data["luggage_capacity"],
                base_location=data["base_location"],
                availability_type=data["availability_type"],
                availability_time=data.get("availability_time"),
                price=price,
                validation=True
            )
            
            print(f"Véhicule {data['brand']} {data['model']} créé avec succès.")
            vehicles.append(vehicle)
            
        except Exception as e:
            print(f"Erreur lors de la création du véhicule {data['brand']} {data['model']}: {str(e)}")
    
    return vehicles

# Fonctions de création des règles tarifaires
def create_tariff_rules(vehicles, clients):
    print("Création des règles tarifaires...")
    
    # Récupération des clients spécifiques
    client_vip = next((c for c in clients if c.username == "client_vip"), None)
    client_agency = next((c for c in clients if c.username == "client_agency"), None)
    
    # Règles pour les véhicules basés à Lyon
    lyon_vehicles = [v for v in vehicles if v.base_location == "Lyon"]
    
    # 1. Règle générale: Réduction de 10% le week-end (samedi, dimanche)
    for vehicle in lyon_vehicles[:3]:  # Appliquer à 3 véhicules de Lyon
        try:
            # Vérifier si la règle existe déjà
            existing_rule = TariffRule.objects.filter(
                vehicle=vehicle,
                name="Réduction Week-end"
            ).first()
            
            if existing_rule:
                print(f"La règle 'Réduction Week-end' existe déjà pour {vehicle}.")
                continue
            
            # Créer l'ajustement
            adjustment = Adjustment.objects.create(
                adjustment_type="discount",
                percentage=10.00
            )
            
            # Créer la règle
            rule = TariffRule.objects.create(
                vehicle=vehicle,
                name="Réduction Week-end",
                description="Réduction de 10% pour les réservations le week-end",
                rule_type="adjustment",
                action_type="scheduled_adjustment",
                days_of_week=["saturday", "sunday"],
                active=True,
                priority=2,
                available_to_all=True,
                adjustment=adjustment
            )
            
            print(f"Règle 'Réduction Week-end' créée pour {vehicle}.")
        except Exception as e:
            print(f"Erreur lors de la création de la règle 'Réduction Week-end' pour {vehicle}: {str(e)}")
    
    # 2. Règle générale: Majoration de 15% aux heures de pointe
    for vehicle in lyon_vehicles[3:6]:  # Appliquer aux 3 autres véhicules de Lyon
        try:
            # Vérifier si la règle existe déjà
            existing_rule = TariffRule.objects.filter(
                vehicle=vehicle,
                name="Majoration Heures de Pointe"
            ).first()
            
            if existing_rule:
                print(f"La règle 'Majoration Heures de Pointe' existe déjà pour {vehicle}.")
                continue
            
            # Créer l'ajustement
            adjustment = Adjustment.objects.create(
                adjustment_type="increase",
                percentage=15.00
            )
            
            # Créer la règle
            rule = TariffRule.objects.create(
                vehicle=vehicle,
                name="Majoration Heures de Pointe",
                description="Majoration de 15% pour les réservations aux heures de pointe",
                rule_type="adjustment",
                action_type="scheduled_adjustment",
                specific_hours=[
                    {"start": "08:00", "end": "10:00"},
                    {"start": "17:00", "end": "19:00"}
                ],
                active=True,
                priority=2,
                available_to_all=True,
                adjustment=adjustment
            )
            
            print(f"Règle 'Majoration Heures de Pointe' créée pour {vehicle}.")
        except Exception as e:
            print(f"Erreur lors de la création de la règle 'Majoration Heures de Pointe' pour {vehicle}: {str(e)}")
    
    # 3. Règle spécifique: Réduction de 20% pour le client VIP
    if client_vip:
        for vehicle in vehicles[:4]:  # Appliquer aux 4 premiers véhicules
            try:
                # Vérifier si la règle existe déjà
                existing_rule = TariffRule.objects.filter(
                    vehicle=vehicle,
                    name="Réduction Client VIP"
                ).first()
                
                if existing_rule:
                    print(f"La règle 'Réduction Client VIP' existe déjà pour {vehicle}.")
                    continue
                
                # Créer l'ajustement
                adjustment = Adjustment.objects.create(
                    adjustment_type="discount",
                    percentage=20.00
                )
                
                # Créer la règle
                rule = TariffRule.objects.create(
                    vehicle=vehicle,
                    name="Réduction Client VIP",
                    description="Réduction de 20% pour le client VIP",
                    rule_type="adjustment",
                    action_type="fixed_adjustment",
                    active=True,
                    priority=3,  # Priorité plus élevée que les règles générales
                    available_to_all=False,
                    adjustment=adjustment
                )
                
                # Ajouter le client VIP aux clients spécifiques
                rule.specific_clients.add(client_vip)
                
                print(f"Règle 'Réduction Client VIP' créée pour {vehicle}.")
            except Exception as e:
                print(f"Erreur lors de la création de la règle 'Réduction Client VIP' pour {vehicle}: {str(e)}")
    
    # 4. Règle spécifique: Forfait spécial pour le client agence
    if client_agency:
        # Choisir un véhicule de type Van basé à Lyon
        van_lyon = next((v for v in lyon_vehicles if "Van" in v.vehicle_type.name), None)
        
        if van_lyon:
            try:
                # Vérifier si la règle existe déjà
                existing_rule = TariffRule.objects.filter(
                    vehicle=van_lyon,
                    name="Forfait Agence Lyon"
                ).first()
                
                if existing_rule:
                    print(f"La règle 'Forfait Agence Lyon' existe déjà pour {van_lyon}.")
                else:
                    # Créer le package
                    package = Package.objects.create(
                        package_type="classic",
                        price=150.00,
                        departure_latitude=45.7640,  # Coordonnées de Lyon
                        departure_longitude=4.8357,
                        arrival_latitude=45.7484,  # Autre point à Lyon
                        arrival_longitude=4.8467
                    )
                    
                    # Créer la règle
                    rule = TariffRule.objects.create(
                        vehicle=van_lyon,
                        name="Forfait Agence Lyon",
                        description="Forfait spécial pour les agences à Lyon",
                        rule_type="package",
                        action_type="classic_package",
                        active=True,
                        priority=3,
                        available_to_all=False,
                        package=package
                    )
                    
                    # Ajouter le client agence aux clients spécifiques
                    rule.specific_clients.add(client_agency)
                    
                    print(f"Règle 'Forfait Agence Lyon' créée pour {van_lyon}.")
            except Exception as e:
                print(f"Erreur lors de la création de la règle 'Forfait Agence Lyon': {str(e)}")
    
    # 5. Codes promo
    try:
        # Récupérer l'entreprise principale
        admin_business = Business.objects.get(business_type="my_business")
        
        # Code promo WELCOME10
        welcome_promo = PromoCode.objects.filter(code="WELCOME10").first()
        if not welcome_promo:
            welcome_promo = PromoCode.objects.create(
                business=admin_business,
                code="WELCOME10",
                percentage=10.00,
                usage_limit=100
            )
            print("Code promo WELCOME10 créé avec succès.")
        else:
            print("Le code promo WELCOME10 existe déjà.")
        
        # Code promo SUMMER2025
        summer_promo = PromoCode.objects.filter(code="SUMMER2025").first()
        if not summer_promo:
            summer_promo = PromoCode.objects.create(
                business=admin_business,
                code="SUMMER2025",
                percentage=15.00,
                usage_limit=50
            )
            print("Code promo SUMMER2025 créé avec succès.")
        else:
            print("Le code promo SUMMER2025 existe déjà.")
        
        # Associer les codes promo à des règles tarifaires
        for i, vehicle in enumerate(vehicles):
            if i >= 2:  # Limiter à 2 véhicules
                break
                
            # Règle pour WELCOME10
            existing_rule = TariffRule.objects.filter(
                vehicle=vehicle,
                name="Code Promo WELCOME10"
            ).first()
            
            if not existing_rule:
                rule = TariffRule.objects.create(
                    vehicle=vehicle,
                    name="Code Promo WELCOME10",
                    description="Code promo de bienvenue 10%",
                    rule_type="promo_code",
                    action_type="promo_code",
                    active=True,
                    priority=1,
                    available_to_all=True,
                    promo_code=welcome_promo
                )
                print(f"Règle 'Code Promo WELCOME10' créée pour {vehicle}.")
            
            # Règle pour SUMMER2025
            existing_rule = TariffRule.objects.filter(
                vehicle=vehicle,
                name="Code Promo SUMMER2025"
            ).first()
            
            if not existing_rule:
                rule = TariffRule.objects.create(
                    vehicle=vehicle,
                    name="Code Promo SUMMER2025",
                    description="Code promo été 2025 15%",
                    rule_type="promo_code",
                    action_type="promo_code",
                    active=True,
                    priority=1,
                    available_to_all=True,
                    promo_code=summer_promo
                )
                print(f"Règle 'Code Promo SUMMER2025' créée pour {vehicle}.")
    except Exception as e:
        print(f"Erreur lors de la création des codes promo: {str(e)}")

# Fonction d'affichage du résumé
def print_summary(admin, partner, drivers, clients, vehicles):
    print("\n" + "="*50)
    print("RÉSUMÉ DES DONNÉES DE TEST CRÉÉES")
    print("="*50)
    
    print("\n1. UTILISATEURS:")
    print(f"   - Administrateur: {admin.username} (email: {admin.email})")
    print(f"   - Partenaire: {partner.username} (email: {partner.email})")
    
    print("\n   Chauffeurs:")
    for i, driver in enumerate(drivers, 1):
        print(f"   - Chauffeur {i}: {driver.username} (email: {driver.email}, indépendant: {driver.is_independent})")
    
    print("\n   Clients:")
    for i, client in enumerate(clients, 1):
        print(f"   - Client {i}: {client.username} (email: {client.email}, type: {client.client_type})")
    
    print("\n2. ENTREPRISES:")
    try:
        admin_business = Business.objects.get(business_type="my_business")
        print(f"   - Entreprise principale: {admin_business.name} (email: {admin_business.email})")
    except:
        print("   - Entreprise principale: Non créée")
    
    try:
        partner_business = Business.objects.filter(partner=partner).first()
        if partner_business:
            print(f"   - Entreprise partenaire: {partner_business.name} (email: {partner_business.email})")
        else:
            print("   - Entreprise partenaire: Non créée")
    except:
        print("   - Entreprise partenaire: Non créée")
    
    print("\n3. VÉHICULES:")
    lyon_vehicles = [v for v in vehicles if v.base_location == "Lyon"]
    print(f"   - Nombre total de véhicules: {len(vehicles)}")
    print(f"   - Véhicules basés à Lyon: {len(lyon_vehicles)}")
    
    vehicle_types = {}
    for vehicle in vehicles:
        vtype = vehicle.vehicle_type.name
        if vtype not in vehicle_types:
            vehicle_types[vtype] = 0
        vehicle_types[vtype] += 1
    
    print("\n   Types de véhicules:")
    for vtype, count in vehicle_types.items():
        print(f"   - {vtype}: {count} véhicule(s)")
    
    print("\n4. RÈGLES TARIFAIRES:")
    rules_count = TariffRule.objects.count()
    adjustment_rules = TariffRule.objects.filter(rule_type="adjustment").count()
    package_rules = TariffRule.objects.filter(rule_type="package").count()
    promo_rules = TariffRule.objects.filter(rule_type="promo_code").count()
    
    print(f"   - Nombre total de règles: {rules_count}")
    print(f"   - Règles d'ajustement: {adjustment_rules}")
    print(f"   - Règles de forfait: {package_rules}")
    print(f"   - Codes promo: {promo_rules}")
    
    print("\n" + "="*50)
    print("INFORMATIONS DE CONNEXION")
    print("="*50)
    
    print("\nAdministrateur:")
    print(f"   - Username: {admin.username}")
    print(f"   - Password: Admin@123")
    
    print("\nPartenaire:")
    print(f"   - Username: {partner.username}")
    print(f"   - Password: Partner@123")
    
    print("\nChauffeurs:")
    print(f"   - Username: driver_independent")
    print(f"   - Password: Driver1@123")
    print(f"   - Username: driver_company")
    print(f"   - Password: Driver2@123")
    
    print("\nClients:")
    print(f"   - Username: client_simple")
    print(f"   - Password: Client1@123")
    print(f"   - Username: client_agency")
    print(f"   - Password: Client2@123")
    print(f"   - Username: client_company")
    print(f"   - Password: Client3@123")
    print(f"   - Username: client_vip")
    print(f"   - Password: Client4@123")
    
    print("\n" + "="*50)
    print("FIN DU RÉSUMÉ")
    print("="*50)


# Exécution du script si lancé directement
if __name__ == "__main__":
    create_test_data()
