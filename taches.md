
3- on va rajouter des views qui permet de faire des actions (qui vont faciliter le traitementent des reservations) : 

- view pour archiver desarchiver (archivage simple ou multiple )
- view pour annuler ou restaurer(simple ou multiple) 
- view pour changer le statut de la booking 

- view pour associer/dissocier ou assigner/desassigner le 1 ou plusieurs booking un chauffeur
- view pour qui retourne un reponse sous format text de recapitulant toute les informations du booking au moment ou on a lancer la requete 
- view pour creer une booking retour (on peux rajouter une logique pour lierpour conbiner les deux reservation on va discuter de la meilleur facon ou la facon la plus optimale de faire cet traitment )
- view pour creer  des bookings recurentes (on va parler de la meilleur facon de mettre sa en place ) 
- view pour dupliquer une booking (on va parler de la meilleur facon de mettre sa en place ) 
- view pour inporter/exporter des booking sous format excel; view pour exporter des booking sous format pdf (on va rajouter des modification pour que les exports soit ajustable avec des options sur une peride donnees; pour un client sur une adresse .... on va trouver le meilleur moyen de faire ca)

- pour toute les options disponible on va utiliser 

class BookingLog(models.Model):
    """
    Model for tracking actions performed on a booking.
    """
    booking = models.ForeignKey(
        Booking,
        on_delete=models.CASCADE,
        related_name="logs",
        help_text="Booking associated with this log entry."
    )
    user = models.ForeignKey(
        "utilisateurs.CustomUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="booking_logs",
        help_text="User who performed the action."
    )
    action = models.CharField(
        max_length=255,
        help_text="Description of the action performed."
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when the action was performed."
    )

    class Meta:
        verbose_name = "Booking Log"
        verbose_name_plural = "Booking Logs"
        ordering = ['-timestamp']

    def __str__(self):
        return f"Log for Booking {self.booking.id} - {self.action} at {self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}"

pour garder la tracabiliter sur chaque action


bien maintenant c'est bon 

prochaine étape on va discuter des nouvelles fonctions qui cont nous permettre d'effectuer les actions suivante sur un booking aller - retour : 

1- modifier les informations d'un segment ou du booking aller - retour en entier 

logique de traitement proposer : on fait la mise a jour partiel soit en fonction de la demande soit sur un segment soit sur l'ensemle du booking et on enregistrer un log et on envoi un mail de modification avec une notifiation en temps reel 

2- pour annuler un segment ou le booking aller - retour 

logique de traitement proposer :  on fait toujours une mise a jour et on annule le segment ou le booking demander en fonction des parametre on creer un log et on envoi un mail ici il faudra aussi gerer la logique de segment ou booking annuler mais facturable 

3 - valider le payement du chauffeur ou du partenaire sur un segment ou du booking 

logique de traitement proposer :  on fait toujours une update des donnees en fonction des paramettre passer on creer un log et on envoi et on envoi une notification en temps reel 

4- changer le statut d'un segment ou du booking aller - retour 