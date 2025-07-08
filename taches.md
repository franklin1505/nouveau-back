
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