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
