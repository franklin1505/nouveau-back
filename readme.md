# Processus d'Estimation et de Réservation

## Vue d'ensemble

Le système gère le processus complet depuis l'estimation d'un trajet jusqu'à sa réservation (booking) en suivant un flux logique bien défini. Ce document explique la logique et les étapes de ce processus.

## 1. Création d'une Estimation

### Étapes du processus d'estimation:

1. **Saisie des informations de base**
   - Lieu de départ
   - Lieu de destination
   - Date et heure de prise en charge
   - Points d'étape (waypoints) optionnels
   - Type d'estimation (transfert simple ou mise à disposition)

2. **Calcul des distances et durées**
   - Utilisation de l'API Google Maps pour calculer:
     - Distance entre la base et le point de départ
     - Distance du parcours principal (départ → waypoints → destination)
     - Distance de retour à la base
     - Durée du trajet

3. **Filtrage et groupement des véhicules**
   - Récupération des véhicules disponibles
   - Filtrage selon la disponibilité et la proximité avec le lieu de départ

4. **Calcul des coûts standard**
   - Pour chaque véhicule, calcul du coût standard basé sur:
     - Frais de réservation
     - Frais de livraison (distance base → départ)
     - Prix par kilomètre (pour le parcours principal)
     - Prix par durée (pour le temps de trajet)
     - Frais de retour (distance destination → base)
     - Application de la TVA

5. **Application des règles tarifaires**
   - Filtrage des règles tarifaires applicables selon:
     - Dates et heures de validité
     - Jours de la semaine
     - Plages horaires spécifiques
     - Forfaits (packages) correspondant au trajet
   - Types de règles:
     - Ajustements (réductions ou majorations)
     - Forfaits (packages)
     - Codes promo

6. **Création de l'EstimationLog et des EstimationTariff**
   - Enregistrement des détails de l'estimation
   - Stockage des tarifs calculés pour chaque véhicule
   - Liaison avec les règles tarifaires appliquées

## 2. Validation de la Réservation

### Étapes de validation:

1. **Validation des données de la requête**
   - Vérification des champs obligatoires
   - Validation des formats et types de données

2. **Traitement des données client**
   - Trois cas possibles:
     - Utilisateur existant (ID fourni)
     - Connexion d'un utilisateur (username/password)
     - Création d'un nouvel utilisateur

3. **Gestion des passagers**
   - Association des passagers existants
   - Création de nouveaux passagers

4. **Traitement des attributs d'estimation**
   - Vérification des attributs existants
   - Création de nouveaux attributs si nécessaire
   - Calcul du coût total des attributs

5. **Calcul du coût final**
   - Sélection du tarif (standard ou avec règle tarifaire)
   - Application du code promo si fourni
   - Calcul du coût total incluant les attributs
   - Application de la commission ou compensation

6. **Mise à jour de l'EstimationLog**
   - Marquage comme "réservé" (is_booked = True)
   - Liaison avec l'utilisateur

7. **Création de l'Estimate**
   - Enregistrement des détails finaux de l'estimation
   - Association avec les passagers et attributs

## 3. Création de la Réservation (Booking)

### Étapes de création:

1. **Création de l'objet Booking**
   - Liaison avec l'Estimate
   - Liaison avec le Client
   - Enregistrement des informations financières:
     - Compensation
     - Commission
     - Prix de vente chauffeur
     - Prix de vente partenaire

2. **Génération du numéro de réservation**
   - Format: "BK-YY-XXXXXX" (YY = année courte, XXXXXX = numéro séquentiel)

3. **Enregistrement dans les logs**
   - Création d'une entrée BookingLog pour tracer l'action

4. **Envoi des notifications**
   - Envoi d'emails au client et au manager
   - Génération du PDF de réservation

## 4. Statuts et Suivi de la Réservation

### Statuts possibles:

- **Statut principal**:
  - Pending (En attente)
  - In Process (En cours de traitement)
  - Assigned to Driver (Assigné à un chauffeur)
  - Assigned to Partner (Assigné à un partenaire)
  - Not Assigned (Non assigné)
  - Driver Notified (Chauffeur notifié)
  - Approaching (En approche)
  - In Progress (En cours)
  - Completed (Terminé)

- **Statut de facturation**:
  - Not Invoiced (Non facturé)
  - Invoice Requested (Facture demandée)
  - Invoiced (Facturé)

- **Statut d'annulation**:
  - Not Cancelled (Non annulé)
  - Cancellation Requested (Annulation demandée)
  - Cancelled (Annulé)

## 5. Modèles de Données Clés

- **EstimationLog**: Enregistre les détails de base de l'estimation
- **EstimationTariff**: Stocke les tarifs calculés pour chaque véhicule
- **AppliedTariff**: Représente un tarif appliqué après calcul des règles
- **UserChoice**: Enregistre le choix de véhicule et de tarif par l'utilisateur
- **Estimate**: Contient les détails complets de l'estimation validée
- **Booking**: Représente la réservation finale
- **BookingLog**: Trace les actions effectuées sur une réservation

## 6. Flux de Données

1. L'utilisateur saisit les détails du trajet
2. Le système calcule les estimations pour différents véhicules
3. L'utilisateur choisit un véhicule et un tarif
4. L'utilisateur complète les informations de réservation
5. Le système valide les données et crée l'Estimate
6. Le système crée la réservation (Booking)
7. Des notifications sont envoyées au client et au manager
8. La réservation peut être suivie et mise à jour selon son statut



### Analyse de la logique de fonctionnement du système d'estimation et de réservation d'un trajet

Le système décrit dans le code fourni est une application Django utilisant Django REST Framework pour gérer l'estimation et la réservation de trajets, principalement pour un service de transport (comme un VTC). L'objectif est de permettre à un utilisateur (client) de demander une estimation pour un trajet, de valider cette estimation avec des choix spécifiques (véhicule, tarif, passagers, etc.), et enfin de créer une réservation confirmée. Voici une analyse détaillée de la logique, suivie d'une simulation textuelle avec des exemples de données JSON à chaque étape.

---

### Vue d'ensemble de la logique

Le processus peut être décomposé en trois grandes étapes :
1. **Estimation du trajet** : Calcul des distances, durées, et coûts pour différents véhicules disponibles, en tenant compte des règles tarifaires (forfaits, réductions, majorations, codes promo).
2. **Validation de l'estimation** : L'utilisateur choisit un véhicule, un tarif, ajoute des passagers, des attributs (options supplémentaires comme sièges bébé), et fournit des informations client. Cette étape valide les données et calcule le coût final.
3. **Création de la réservation** : Une fois l'estimation validée, une réservation est créée, des e-mails de confirmation sont envoyés, et un PDF récapitulatif peut être généré.

---

### Étape 1 : Estimation du trajet (`EstimateView`)

#### Logique
- **Entrée** : L'utilisateur soumet une demande avec les informations du trajet (lieu de départ, destination, date de prise en charge, points d'arrêt éventuels, type d'estimation).
- **Processus** :
  1. Vérification des champs obligatoires (départ, destination, date).
  2. Récupération de la clé API Google Maps pour le géocodage et le calcul des distances.
  3. Filtrage des véhicules validés (`Vehicle.validation=True`) et regroupement par base la plus proche du lieu de départ.
  4. Calcul des distances et durées via Google Maps (base → départ → arrêts → destination → base).
  5. Calcul des coûts pour chaque véhicule disponible :
     - Coût standard basé sur les frais (réservation, livraison, par km, par durée).
     - Application des règles tarifaires (forfaits, ajustements) selon les conditions (jours, heures, localisation, client spécifique).
  6. Enregistrement des données dans `EstimationLog` et `EstimationTariff` pour tracer l'estimation.
  7. Construction d'une réponse structurée avec les informations du trajet, les véhicules disponibles, et leurs coûts.
- **Sortie** : Une réponse JSON contenant les détails du trajet, les véhicules disponibles avec leurs coûts, et un identifiant d'estimation.

#### Simulation
**Requête envoyée** :
```json
{
  "departure_location": "Gare de Lyon, Paris",
  "destination_location": "Aéroport Charles de Gaulle, Paris",
  "pickup_date": "2025-06-01T10:00:00Z",
  "destinationInputs": ["Hôtel Pullman, Paris"],
  "estimate_type": "simple_transfer"
}
```

**Traitement** :
- La clé API Google Maps est récupérée.
- Les véhicules validés sont filtrés, et la base la plus proche (par exemple, "Base Paris Nord") est identifiée.
- Les distances et durées sont calculées :
  - Base → Gare de Lyon : 5 km, 10 min.
  - Gare de Lyon → Hôtel Pullman : 3 km, 8 min.
  - Hôtel Pullman → Aéroport CDG : 25 km, 30 min.
  - Aéroport CDG → Base : 20 km, 25 min.
- Les coûts sont calculés pour chaque véhicule (exemple : Berline, Van) :
  - Berline : Frais de réservation (10€), livraison (2€/km), par km (1.5€), par durée (0.5€/min).
  - Coût standard = 10 + (2×5) + (1.5×28) + (2×20) + (0.5×48) = 87€.
  - TVA (10%) = 8.7€, Total = 95.7€.
  - Règle tarifaire "Forfait Aéroport" appliquée : coût fixe de 80€.
- Un `EstimationLog` (ID: 123) et des `EstimationTariff` sont créés.

**Réponse reçue** :
```json
{
  "status": "success",
  "message": "Estimation calculée avec succès.",
  "data": {
    "trip_informations": {
      "pickup_date": "2025-06-01T10:00:00Z",
      "departure_address": "Gare de Lyon, Paris",
      "destination_address": "Aéroport Charles de Gaulle, Paris",
      "waypoints": ["Hôtel Pullman, Paris"]
    },
    "distances_and_durations": {
      "dist_parcourt_km": 28,
      "dur_parcourt_minutes": 48
    },
    "vehicles_informations": [
      {
        "id": 1,
        "availability_type": "immediate",
        "passenger_capacity": 4,
        "luggage_capacity": "2 valises",
        "vehicle_type": "Berline",
        "vehicle_name": "Mercedes Classe E",
        "pricing": {
          "standard_cost": {
            "coutBrute": 87,
            "tva": 8.7,
            "total_cost": 95.7
          },
          "applied_rules": [
            {
              "rule_id": 5,
              "rule_name": "Forfait Aéroport",
              "calculated_cost": 80
            }
          ]
        }
      }
    ],
    "user_informations": {},
    "estimation_data": {
      "estimation_log_id": 123,
      "estimation_tariff_ids": [456, 457]
    }
  },
  "http_status": 200
}
```

---

### Étape 2 : Validation de l'estimation (`BookingValidateView`)

#### Logique
- **Entrée** : L'utilisateur soumet des données pour valider l'estimation, incluant l'ID de l'estimation, le choix du véhicule/tarif, les informations client, les passagers, les attributs, et des options comme le code promo.
- **Processus** :
  1. Validation des données via des sérialiseurs (`EstimationLogIdSerializer`, `UserChoiceSerializer`, `PassengerSerializer`, `ClientInfoSerializer`, `EstimateAttributeSerializer`).
  2. Gestion des informations client :
     - Si ID fourni : récupération de l'utilisateur existant.
     - Si identifiants fournis : connexion via `LoginView`.
     - Si nouveau client : création via `UserCreationView`.
  3. Création/association des passagers (existants ou nouveaux).
  4. Traitement des attributs (ex. siège bébé) avec calcul du coût total.
  5. Calcul du coût final :
     - Sélection du tarif (standard ou appliqué via règle).
     - Application d'un code promo si valide.
     - Ajout du coût des attributs.
     - Application de la compensation (bonus) ou commission (déduction).
  6. Mise à jour de `EstimationLog` (`is_booked=True`) et création d'un `Estimate`.
  7. Formatage de la réponse avec les données validées.
- **Sortie** : Une réponse JSON avec les détails validés, le coût final, et l'ID de l'estimation.

#### Simulation
**Requête envoyée** :
```json
{
  "estimation_log": 123,
  "user_choice": {
    "vehicle_id": 1,
    "selected_tariff": null,
    "is_standard_cost": false
  },
  "user": {
    "new_user": {
      "user_type": "client",
      "email": "jean.dupont@example.com",
      "first_name": "Jean",
      "last_name": "Dupont",
      "phone_number": "+33612345678",
      "client_type": "particulier",
      "is_partial": false
    }
  },
  "passengers": {
    "existing": [10],
    "new": [
      {"name": "Marie Dupont", "phone_number": "+33687654321"}
    ]
  },
  "estimate_attribute": [
    {"attribute": 3, "quantity": 1} // Siège bébé
  ],
  "payment_method": 1,
  "meeting_place": 2,
  "number_of_luggages": "2",
  "number_of_passengers": 2,
  "code_promo": "PROMO10",
  "compensation": 5,
  "commission": null
}
```

**Traitement** :
- Validation des données :
  - `estimation_log` (123) existe.
  - Véhicule (ID: 1) et tarif (forfait aéroport, 80€) sont valides.
  - Nouveau client créé (ID: 789).
  - Passager existant (ID: 10) associé, nouveau passager "Marie" créé (ID: 11).
  - Attribut "Siège bébé" (ID: 3, prix unitaire: 15€) ajouté, coût total = 15€.
- Gestion du client : Création d'un utilisateur (`CustomUser` et `Client`).
- Calcul du coût :
  - Tarif sélectionné : 80€ (forfait).
  - Code promo "PROMO10" : 10% de réduction → 80 × 0.9 = 72€.
  - Coût des attributs : 15€.
  - Total = 72 + 15 = 87€.
  - Compensation (5€) : `driver_sale_price` = 87 + 5 = 92€, `partner_sale_price` = 92€.
- Création d'un `Estimate` (ID: 200) et mise à jour de `EstimationLog`.

**Réponse reçue** :
```json
{
  "status": "success",
  "message": "Validation and processing successful",
  "data": {
    "display_data": {
      "user": {
        "user_type": "client (particulier)",
        "name": "Jean Dupont",
        "email": "jean.dupont@example.com",
        "phone_number": "+33612345678",
        "address": "Non renseigné"
      },
      "passengers": [
        {"name": "Paul Martin", "phone_number": "+33655555555"},
        {"name": "Marie Dupont", "phone_number": "+33687654321"}
      ],
      "estimate_attribute": [
        {
          "attribute_name": "Siège bébé",
          "unit_price": 15,
          "quantity": 1,
          "total": 15
        }
      ],
      "vehicle": {
        "brand": "Mercedes",
        "model": "Classe E",
        "vehicle_type": "Berline"
      },
      "total_booking_cost": 87,
      "total_attributes_cost": 15,
      "promotion_message": "Le code promo « PROMO10 » a permis d'appliquer une réduction de 10% sur le tarif de votre réservation.",
      "driver_sale_price": 92,
      "partner_sale_price": 92,
      "meeting_place": "Entrée principale Gare de Lyon",
      "payment_method": "Paiement à bord",
      "estimation_log": {
        "departure": "Gare de Lyon, Paris",
        "destination": "Aéroport Charles de Gaulle, Paris",
        "pickup_date": "2025-06-01T10:00:00Z",
        "waypoints": ["Hôtel Pullman, Paris"],
        "estimate_type": "Transfert Simple",
        "distance_travelled": 28,
        "duration_travelled": "48"
      },
      "number_of_luggages": "2",
      "number_of_passengers": 2
    },
    "request_data": {
      "user_id": 789,
      "passengers": [10, 11],
      "estimate_attribute": [100],
      "user_choice": 300,
      "total_booking_cost": 87,
      "total_attributes_cost": 15,
      "driver_sale_price": 92,
      "partner_sale_price": 92,
      "meeting_place": 2,
      "payment_method": 1,
      "estimation_log": 123,
      "compensation": 5,
      "commission": null,
      "estimate": 200,
      "client": 789
    }
  },
  "http_status": 200
}
```

---

### Étape 3 : Création de la réservation (`BookingCreateView`)

#### Logique
- **Entrée** : Les données validées de l'étape précédente, incluant l'ID de l'estimation et les informations de coût.
- **Processus** :
  1. Validation des champs obligatoires (compensation, commission, coûts, estimation, client).
  2. Création d'une réservation (`Booking`) avec un numéro unique (ex. BK-25-000001).
  3. Enregistrement d'un log d'action (`BookingLog`) pour l'action "created".
  4. Envoi d'e-mails de confirmation au client et au manager avec un lien pour télécharger un PDF récapitulatif.
  5. Formatage des données pour la réponse (uniquement `display_data`).
- **Sortie** : Une réponse JSON avec les détails de la réservation.

#### Simulation
**Requête envoyée** :
```json
{
  "compensation": 5,
  "commission": null,
  "driver_sale_price": 92,
  "partner_sale_price": 92,
  "estimate": 200,
  "client": 789
}
```

**Traitement** :
- Validation : Tous les champs requis sont présents.
- Création d'une réservation (ID: 500, numéro: BK-25-000001).
- Log créé : "La réservation a été créée avec succès."
- E-mails envoyés à `jean.dupont@example.com` et au manager avec un lien vers `/api/reservations/booking/500/pdf/`.
- Données formatées pour la réponse.

**Réponse reçue** :
```json
{
  "status": "success",
  "message": "Réservation créée avec succès.",
  "data": {
    "user": {
      "email": "jean.dupont@example.com",
      "first_name": "Jean",
      "last_name": "Dupont",
      "phone_number": "+33612345678",
      "address": "Non renseigné",
      "client_type": "Particulier"
    },
    "passengers": [
      {"name": "Paul Martin", "phone_number": "+33655555555"},
      {"name": "Marie Dupont", "phone_number": "+33687654321"}
    ],
    "estimate_attribute": [
      {
        "attribute_name": "Siège bébé",
        "unit_price": 15,
        "quantity": 1,
        "total": 15
      }
    ],
    "vehicle": {
      "brand": "Mercedes",
      "model": "Classe E",
      "vehicle_type": "Berline"
    },
    "total_booking_cost": 87,
    "total_attributes_cost": 15,
    "total_trajet": 72,
    "driver_sale_price": 92,
    "partner_sale_price": 92,
    "compensation": 5,
    "commission": null,
    "booking_number": "BK-25-000001",
    "meeting_place": "Entrée principale Gare de Lyon",
    "payment_method": "Paiement à bord",
    "estimation_log": {
      "departure": "Gare de Lyon, Paris",
      "destination": "Aéroport Charles de Gaulle, Paris",
      "pickup_date": "2025-06-01T10:00:00Z",
      "waypoints": ["Hôtel Pullman, Paris"],
      "estimate_type": "Transfert Simple",
      "distance_travelled": 28,
      "duration_travelled": "48"
    },
    "number_of_luggages": "2",
    "number_of_passengers": 2
  },
  "http_status": 201
}
```

---

### Points forts et axes d'amélioration

#### Points forts
- **Modularité** : Les fonctions dans `helpers.py` sont réutilisables et bien segmentées (calcul de distance, gestion des règles tarifaires, validation client).
- **Validation robuste** : Les sérialiseurs assurent une validation stricte des données à chaque étape.
- **Traçabilité** : Les modèles `EstimationLog`, `BookingLog`, et `Estimate` permettent de suivre chaque étape.
- **Flexibilité tarifaire** : Les règles tarifaires (`TariffRule`) gèrent divers cas (forfaits, ajustements, codes promo).

#### Axes d'amélioration
- **Performance** : Les appels répétés à l'API Google Maps pour chaque véhicule/base peuvent être coûteux. Une mise en cache des résultats pourrait être envisagée.
- **Gestion des erreurs** : Certaines erreurs (ex. absence de clé API) pourraient être mieux gérées avec des messages plus spécifiques.
- **Complexité des règles tarifaires** : La logique d'application des règles pourrait être simplifiée ou mieux documentée pour faciliter la maintenance.
- **Internationalisation** : Les messages d'erreur et les e-mails sont en français. Ajouter un support multilingue pourrait être utile.
- **Tests unitaires** : Le code ne montre pas de tests explicites, ce qui est crucial pour garantir la fiabilité.

---

### Conclusion
Le système est bien structuré pour gérer l'estimation et la réservation de trajets, avec une logique claire et modulaire. La simulation montre comment les données circulent entre les étapes, avec des validations rigoureuses et des réponses détaillées. Pour apporter des modifications, un développeur pourrait se concentrer sur l'optimisation des performances, l'amélioration de la gestion des erreurs, ou l'ajout de fonctionnalités comme la gestion des paiements en ligne ou des notifications push.


# **Récapitulatif complet : Fonctionnalité Booking Aller-Retour**

## **🎯 Objectif principal**
Permettre de transformer un booking simple existant en booking aller-retour avec :
- **Un seul booking** affiché dans les listes
- **Actions indépendantes** sur chaque segment (aller/retour)
- **Gestion unifiée** de la facturation et des statuts

## **🏗️ Architecture retenue**

### **Structure de données :**
```
Booking (Container principal - inchangé)
├── Métadonnées globales : booking_number, client, created_at
├── Nouveau champ : booking_type ('one_way' | 'round_trip')
└── BookingSegment (nouveau modèle)
    ├── Segment aller : estimate, status, compensation, commission
    └── Segment retour : estimate, status, compensation, commission
```

### **Principe clé :**
- **Modèles existants conservés** → Pas de rupture
- **Extension par segments** → Modularité parfaite
- **Calculs automatiques** → Agrégation depuis les segments

## **⚡ Workflow utilisateur**

### **Étape 1 : GET Preview**
```
→ Retourne les données par défaut du retour calculées automatiquement
```

**Calculs par défaut :**
- **Adresses inversées** : departure ↔ destination
- **Date/heure** : Date et heure actuelles de la requête
- **Tarif** : `total_booking_cost - total_attributes_cost` de l'aller
- **Véhicule** : Même que l'aller
- **Passagers** : Copiés de l'aller
- **Attributs** : Aucun par défaut

### **Étape 2 : POST Transformation**
```
→ Confirme ou modifie les données, puis transforme le booking
```

**Traitement atomique :**
1. Créer segment aller avec données existantes
2. Créer estimate + segment retour avec données fournies
3. Marquer booking comme `round_trip`
4. Enregistrer logs + envoyer notifications

## **📊 Règles métier validées**

### **Données globales (non-dupliquées) :**
- `booking_number`, `client`, `created_at`
- `assigned_driver`, `assigned_partner` (même pour les 2)
- `is_archived` (appliqué aux 2 segments)

### **Données par segment :**
- **Estimate complet** (trajets, coûts, passagers, attributs)
- **Status indépendant** (aller peut être "completed", retour "pending")
- **Compensation/Commission** par segment

### **Calculs automatiques :**
- **Coût total** = Somme des segments non-annulés
- **Paiement chauffeur** = TRUE si TOUS segments payés
- **Statut global** = Logique d'agrégation intelligente

### **Logique de statuts :**
- **Booking completed** = Aller completed + (Retour completed OU cancelled)
- **Booking cancelled** = LES DEUX segments cancelled
- **Annulation partielle** = Recalcul automatique des coûts

## **🔧 Avantages de l'approche**

### **✅ Performance :**
- Pas de champs NULL inutiles dans Booking
- Modèles existants inchangés
- Requêtes optimisées par segment

### **✅ Flexibilité :**
- Modification libre des données avant confirmation
- Actions indépendantes sur chaque segment
- Partage ou duplication selon les besoins

### **✅ UX optimale :**
- Preview immédiat sans sauvegarde
- Un booking = une ligne dans les listes
- Facturation unifiée naturelle

### **✅ Maintenabilité :**
- Code simple et lisible
- Pas de sur-ingénierie
- Extension naturelle de l'existant

## **🚀 Points clés de l'implémentation**

### **Validations GET :**
- Booking existe ?
- Pas déjà aller-retour ?
- Client fourni (hérité de l'aller) ✓

### **Gestion des conflits :**
- **Simplicité** : L'utilisateur modifie manuellement
- **Pas de validation complexe** : Flexibilité maximale
- **Recalculs automatiques** : Coûts, statuts, paiements

### **Notifications et logs :**
- **BookingLog** : Traçabilité par segment
- **Notifications temps réel** : Intégration existante
- **Emails** : Manager + client informés

## **📝 Prochaines étapes**
1. **Créer le modèle BookingSegment**
2. **Implémenter les services GET/POST**
3. **Adapter les APIs existantes**
4. **Tester la transformation**
5. **Intégrer notifications/logs**

**Cette approche est optimale, pragmatique et évolutive !** 🎯


# 🎯 Récapitulatif Logique : Fonctionnalité Duplication de Booking

## **💡 Concept Central**

**Utiliser une course existante comme modèle** pour créer rapidement une nouvelle course similaire, en personnalisant seulement ce qui diffère.

## **🎪 Cas d'Usage Réels**

### **Scénario 1 : Même trajet, autre client**
- Course Lyon → Paris existe pour Client A
- Client B veut le même trajet, même véhicule
- **Solution :** Dupliquer + changer client + passagers

### **Scénario 2 : Course récurrente**
- Client fait Lyon → Aéroport tous les lundis
- **Solution :** Dupliquer + changer date

### **Scénario 3 : Adaptation de service**
- Course berline existe, mais nouveau client a 5 passagers
- **Solution :** Dupliquer + changer véhicule (van) + ajuster prix

## **🔄 Principe de Fonctionnement**

### **1. Sélection du modèle**
L'admin choisit une course existante qui ressemble à ce qu'il veut créer

### **2. Template automatique**
Le système pré-remplit toutes les informations :
- ✅ **Trajet, véhicule, tarifs** copiés
- ❌ **Client vide** (obligé de choisir)
- ❌ **Services supplémentaires vides** (besoins spécifiques)

### **3. Personnalisation libre**
L'admin modifie ce qu'il veut :
- Nouveau client et ses passagers
- Autre date/heure
- Véhicule différent si besoin
- Tarifs adaptés
- Services additionnels

### **4. Création automatique**
Le système crée la nouvelle course complètement indépendante

## **🎯 Types de Courses Supportés**

### **Course Simple (Aller)**
- Un trajet A → B
- Template direct avec toutes les infos

### **Course Aller-Retour**
- Deux trajets A → B puis B → A
- Template avec les deux segments
- Possibilité de modifier chaque trajet indépendamment

## **💰 Logique Tarifaire**

### **Prix de base**
Le coût du trajet original est repris comme point de départ

### **Recalcul automatique**
Si on ajoute des services (siège bébé, bagage extra...) :
- Coût services calculé automatiquement
- Prix total = Prix base + Services
- Prix chauffeur recalculé selon commission/compensation

### **Flexibilité totale**
L'admin peut ajuster manuellement tous les prix si besoin

## **🛡️ Règles Métier**

### **Obligatoire**
- **Nouveau client** doit être choisi (pas de duplication à l'identique)

### **Intelligent**
- **Services vides** par défaut (évite frais cachés)
- **Assignations remises à zéro** (chauffeur/partenaire à redéfinir)
- **Nouvelle date suggérée** (pas la même que l'original)

### **Flexible**
- **Tout peut être modifié** (trajet, véhicule, prix, détails...)
- **Aucune contrainte rigide** sur les modifications

## **⚡ Avantages Utilisateur**

### **Gain de temps énorme**
- 90% des infos déjà remplies
- Juste personnaliser ce qui diffère
- Pas de ressaisie manuelle

### **Moins d'erreurs**
- Configurations éprouvées réutilisées
- Détails techniques préservés
- Standards de service maintenus

### **Flexibilité maximale**
- Adaptation libre selon besoins
- De simple (changer client) à complexe (tout modifier)
- Support de tous types de courses

## **🎪 Workflow Utilisateur**

### **Étape 1 : "Utiliser comme modèle"**
L'admin clique sur une course existante et choisit "Dupliquer"

### **Étape 2 : Aperçu du template**
Le système montre toutes les données pré-remplies avec :
- Ce qui est copié (trajet, véhicule, prix...)
- Ce qui est vide (client, services supplémentaires...)
- Ce qui était assigné avant (chauffeur, pour info)

### **Étape 3 : Personnalisation**
L'admin modifie librement :
- **Minimum :** Choisir le nouveau client
- **Courant :** Client + date + quelques détails
- **Complet :** Client + véhicule + prix + trajet + services

### **Étape 4 : Validation**
Le système crée la nouvelle course indépendante avec :
- Nouveau numéro de réservation
- Calculs automatiques des prix
- Statut "En attente" par défaut

## **🎁 Valeur Ajoutée**

### **Pour l'efficacité**
Création de course **5x plus rapide** pour les cas similaires

### **Pour la qualité**
Réutilisation de **configurations éprouvées** et **standards établis**

### **Pour la flexibilité**
**Aucune limitation** sur les adaptations possibles

---

**En résumé : Prendre une course qui marche, changer ce qui diffère, créer du neuf ! 🚀**