from datetime import date, timedelta
import datetime
from io import BytesIO
from django.conf import settings
from django.db import models, transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

# Create your models here.

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid

import qrcode

# models pour la ville des utilisateurs
class City(models.Model):
    city = models.CharField(max_length=100, unique=True)
    country = models.CharField(max_length=100, blank=True)
    region = models.CharField(max_length=100, blank=True)
    

    def __str__(self):
        return self.city

class CustomUser(AbstractUser):
    USER_TYPE_CHOICES = (
        ('client', 'Client'),
        ('collecteur', 'Collecteur'),
        ('admin', 'Administrateur'),
    )
    

    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)    
    user_type = models.CharField(max_length=20, choices=USER_TYPE_CHOICES, default='client')
    phone = models.IntegerField(blank=True, null=True)
    date_joined = models.DateTimeField(default=timezone.now)
    is_verified = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = "Utilisateur"
        verbose_name_plural = "Utilisateurs"


    
    def __str__(self):
        return f"{self.phone} - {self.city}"

class SubscriptionPlan(models.Model):
    PLAN_TYPE_CHOICES = (
        ('standard', 'Standard'),
        ('premium', 'Premium'),
        ('entreprise', 'Entreprise'),
    )
    
    FREQUENCY_CHOICES = (
        ('quotidien', 'Quotidien'),
        ('hebdomadaire', 'Hebdomadaire'),
        ('mensuel', 'Mensuel'),
    )
    
    name = models.CharField(max_length=100, verbose_name="Nom du plan")
    plan_type = models.CharField(max_length=20, choices=PLAN_TYPE_CHOICES)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Prix")
    description = models.TextField(blank=True)
    max_collections_per_week = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Plan d'abonnement"
        verbose_name_plural = "Plans d'abonnement"
    
    def __str__(self):
        return f"{self.name} - {self.get_frequency_display()}"

class CollectionDay(models.Model):
    DAY_CHOICES = (
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'Jeudi'),
        ('vendredi', 'Vendredi'),
        ('samedi', 'Samedi'),
        ('dimanche', 'Dimanche'),
    )
    
    name = models.CharField(max_length=10, choices=DAY_CHOICES, unique=True)
    order = models.PositiveIntegerField(default=0)
    
    class Meta:
        verbose_name = "Jour de collecte"
        verbose_name_plural = "Jours de collecte"
        ordering = ['order']
    
    def __str__(self):
        return self.get_name_display()

# Modèle Tricycle
class Tricycle(models.Model):
    STATUS_CHOICES = (
        ('active', 'Actif'),
        ('maintenance', 'En maintenance'),
        ('inactive', 'Inactif'),
        ('broken', 'En panne'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    numero_immatriculation = models.CharField(max_length=50, unique=True, verbose_name="Numéro d'immatriculation")
    nom = models.CharField(max_length=100, verbose_name="Nom du tricycle")
    capacite_kg = models.DecimalField(max_digits=6, decimal_places=2, verbose_name="Capacité (kg)")
    couleur = models.CharField(max_length=50, blank=True)
    date_mise_en_service = models.DateField(default=timezone.now)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    conducteur = models.ForeignKey(
        CustomUser, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'user_type': 'collecteur'},
        verbose_name="Conducteur assigné"
    )
    notes = models.TextField(blank=True, verbose_name="Notes techniques")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Tricycle"
        verbose_name_plural = "Tricycles"
        ordering = ['numero_immatriculation']
    
    def __str__(self):
        return f"{self.nom} ({self.numero_immatriculation})"

class Zone(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    nom = models.CharField(max_length=100, unique=True, verbose_name="Nom de la zone")
    ville = models.ForeignKey(City, on_delete=models.CASCADE, related_name='zones')
    description = models.TextField(blank=True)
    polygone_coordinates = models.TextField(blank=True, help_text="Coordonnées géographiques pour définir la zone")
    couleur = models.CharField(max_length=20, blank=True, help_text="Couleur pour l'affichage sur la carte")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Zone géographique"
        verbose_name_plural = "Zones géographiques"
        ordering = ['ville', 'nom']
    
    def __str__(self):
        return f"{self.nom} - {self.ville}"

class ProgrammeTricycle(models.Model):
    JOUR_SEMAINE_CHOICES = (
        ('lundi', 'Lundi'),
        ('mardi', 'Mardi'),
        ('mercredi', 'Mercredi'),
        ('jeudi', 'jeudi'),
        ('vendredi', 'Vendredi'),
        ('samedi', 'Samedi'),
        ('dimanche', 'Dimanche'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tricycle = models.ForeignKey(Tricycle, on_delete=models.CASCADE, related_name='programmes')
    zone = models.ForeignKey(Zone, on_delete=models.CASCADE, related_name='programmes_tricycle')
    jour_semaine = models.CharField(max_length=10, choices=JOUR_SEMAINE_CHOICES)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    capacite_max_clients = models.PositiveIntegerField(default=50, verbose_name="Capacité maximale de clients")
    clients_actuels = models.PositiveIntegerField(default=0, verbose_name="Nombre de clients actuels")
    is_active = models.BooleanField(default=True)
    date_debut = models.DateField(default=timezone.now)
    date_fin = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Programme tricycle"
        verbose_name_plural = "Programmes tricycle"
        ordering = ['jour_semaine', 'heure_debut']
        unique_together = ['tricycle', 'zone', 'jour_semaine']
    
    def __str__(self):
        return f"{self.tricycle} - {self.zone} - {self.get_jour_semaine_display()}"
    
    def places_disponibles(self):
        return self.capacite_max_clients - self.clients_actuels
    
    def peut_ajouter_client(self):
        return self.places_disponibles() > 0 and self.is_active


# signal pour mettre à jour le programme de collecte lorsque le programme des tricycles est modifié
# Signal pour mettre à jour les collectes quand le programme des tricycles change
@receiver(post_save, sender=ProgrammeTricycle)
@receiver(post_delete, sender=ProgrammeTricycle)
def mettre_a_jour_collectes_zone(sender, instance, **kwargs):
    """
    Signal pour refaire le programme de collecte des ordures pour les abonnements
    qui sont dans une zone à chaque fois que le programme des tricycles change dans cette zone.
    """
    from django.db import transaction
    from .views import generate_collection_schedule
    
    zone = instance.zone
    
    # Récupérer tous les abonnements actifs dans cette zone
    abonnements_zone = Subscription.objects.filter(
        zone=zone,
        status='active',
         # S'assurer que l'adresse est bien dans cette zone
    ).select_related('plan', 'user')
    
    if not abonnements_zone.exists():
        return
    
    # verifier s'il ya un programe des tricycles qui à ete modifier il ya moint de 2 min pour eviter les mise à jour unitile du programme de collecte
    if instance.created_at and timezone.now() - instance.created_at < timedelta(minutes=2):
        



        with transaction.atomic():
            for subscription in abonnements_zone:
            # Supprimer les anciens jours de collecte pour cet abonnement
                anciens_jours = SubscriptionDay.objects.filter(
                subscription=subscription
                )
            
            # Mettre à jour les compteurs des programmes tricycles
                for jour in anciens_jours:
                    if jour.programme_tricycle:
                        programme = jour.programme_tricycle
                        programme.clients_actuels = max(0, programme.clients_actuels - 1)
                        programme.save()
            
            
            
            
            # Supprimer les anciens programmes de collecte
                CollectionSchedule.objects.filter(
                    subscription=subscription,
                    status='scheduled'
                ).delete()
            
            # Réassigner automatiquement les nouveaux jours de collecte
                nouveaux_jours = subscription.assigner_jours_collecte_automatique()
                print(f"Nouvelle assignation de jours pour l'abonnement {subscription.id}: {[str(jour.day) for jour in nouveaux_jours]}")
            
            # Générer le nouveau programme de collecte
                a = generate_collection_schedule(subscription)
            
            

            
            # Créer une notification pour informer l'utilisateur
            if nouveaux_jours:
                jours_formates = [jour.day.get_name_display() for jour in nouveaux_jours]
                message = (
                    f"Le programme de collecte dans votre zone ({zone.nom}) a été modifié. "
                    f"Vos nouveaux jours de collecte sont : {', '.join(jours_formates)}. "
                    f"Veuillez consulter votre programme mis à jour."
                )
                
                Notification.create_notification(
                    user=subscription.user,
                    title="Programme de collecte mis à jour",
                    message=message,
                    notification_type='info',
                    related_object=subscription,
                    action_url=f'/subscriptions/{subscription.id}/'
                )
            else:
                # Si aucun jour n'est disponible, notifier l'utilisateur
                Notification.create_notification(
                    user=subscription.user,
                    title="Attention : Programme de collecte",
                    message=(
                        f"Suite à la modification du programme dans votre zone ({zone.nom}), "
                        f"aucun créneau n'est actuellement disponible pour votre abonnement. "
                        f"Notre équipe vous contactera sous peu pour régulariser votre situation."
                    ),
                    notification_type='warning',
                    related_object=subscription,
                    action_url=f'/subscriptions/{subscription.id}/'
                )


# Signal supplémentaire pour gérer les cas où une zone est désactivée
@receiver(post_save, sender=Zone)
def gerer_changement_zone(sender, instance, created, **kwargs):
    """
    Gérer les changements de zone (désactivation, modification)
    """
    if not created and not instance.is_active:
        # Si la zone est désactivée, mettre à jour les abonnements concernés
        abonnements_zone = Subscription.objects.filter(
            zone=instance,
            status='active'
        )
        
        with transaction.atomic():
            for subscription in abonnements_zone:
                # Mettre à jour le statut de l'abonnement
                subscription.status = 'suspended'
                subscription.save()
                
                # Supprimer les programmes de collecte
                CollectionSchedule.objects.filter(
                    subscription=subscription,
                    status='scheduled'
                ).delete()
                
                # Notifier l'utilisateur
                Notification.create_notification(
                    user=subscription.user,
                    title="Zone de collecte désactivée",
                    message=(
                        f"La zone de collecte {instance.nom} a été temporairement désactivée. "
                        f"Votre abonnement a été suspendu. Vous serez notifié dès sa réactivation."
                    ),
                    notification_type='warning',
                    related_object=subscription,
                    action_url=f'/subscriptions/{subscription.id}/'
                )


# Fonction utilitaire pour vérifier la cohérence des programmes
def verifier_coherence_programmes(zone):
    """
    Vérifier que tous les abonnements dans une zone ont des jours de collecte valides
    par rapport aux programmes tricycles actuels
    """
    from django.db.models import Count
    
    programmes = ProgrammeTricycle.objects.filter(
        zone=zone,
        is_active=True
    ).values('jour_semaine').annotate(
        places_total=models.Sum('capacite_max_clients'),
        places_utilisees=models.Sum('clients_actuels')
    )
    
    abonnements = Subscription.objects.filter(
        zone=zone,
        status='active'
    ).annotate(
        nb_jours=Count('collection_days')
    )
    
    rapport = {
        'zone': zone.nom,
        'programmes': list(programmes),
        'total_abonnements': abonnements.count(),
        'abonnements_sans_jours': abonnements.filter(nb_jours=0).count(),
        'date_verification': timezone.now()
    }
    
    return rapport



# Ajout du champ zone à l'adresse
class Address(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='addresses')
    title = models.CharField(max_length=100, verbose_name="Titre de l'adresse")
    street = models.CharField(max_length=255, verbose_name="Rue")
    city = models.CharField(max_length=100, verbose_name="Ville")
    postal_code = models.CharField(max_length=20, verbose_name="Code postal")
    country = models.CharField(max_length=100, verbose_name="Pays", default="France")
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='adresses', verbose_name="Zone géographique")
    latitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, blank=True, null=True)
    is_primary = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    lien = models.URLField(blank=True, verbose_name="Lien Google Maps")
    
    class Meta:
        verbose_name = "Adresse"
        verbose_name_plural = "Adresses"
        ordering = ['-is_primary', 'created_at']
    
    def __str__(self):
        return f"{self.title} - {self.city}"

class Subscription(models.Model):
    STATUS_CHOICES = (
        ('active', 'Actif'),
        ('inactive', 'Inactif'),
        ('suspended', 'Suspendu'),
        ('cancelled', 'Annulé'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='subscriptions')
    address = models.ForeignKey(Address, on_delete=models.CASCADE, related_name='subscriptions')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(blank=True, null=True)
    custom_price = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    special_instructions = models.TextField(blank=True, verbose_name="Instructions spéciales")
    # Suppression du choix manuel des jours - ils seront assignés automatiquement
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    
    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        indexes = [
            models.Index(fields=['status', 'start_date']),
            models.Index(fields=['user', 'status']),
        ]
    
    def __str__(self):
        return f"Abonnement {self.plan.name} - {self.user.username}"
    
    def assigner_jours_collecte_automatique(self):
        """
        Assigner automatiquement les jours de collecte basés sur la zone et la disponibilité des tricycles
        """
        from django.db import transaction
        
        
        
        zone = self.zone
        programmes_disponibles = ProgrammeTricycle.objects.filter(
            zone=zone,
            is_active=True
        ).order_by('jour_semaine')
        
        jours_assignes = []

        # on ajoute automatique du tricycle à un abonement
        
        
        with transaction.atomic():
            for programme in programmes_disponibles:
                if programme.peut_ajouter_client():
                    # Créer le jour de collecte pour cet abonnement
                    jour_collecte, created = SubscriptionDay.objects.get_or_create(
                        subscription=self,
                        day=CollectionDay.objects.get(name=programme.jour_semaine),
                        defaults={
                            'time_slot': programme.heure_debut,
                            'is_active': True
                        }
                    )
                    
                    if created:
                        # Mettre à jour le compteur de clients du programme
                        programme.clients_actuels += 1
                        programme.save()
                        jours_assignes.append(jour_collecte)
                        
                        # S'arrêter si on a atteint le nombre maximum de collectes par semaine
                        if len(jours_assignes) >= self.plan.max_collections_per_week:
                            break
        
        return jours_assignes

class SubscriptionDay(models.Model):
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='collection_days')
    day = models.ForeignKey(CollectionDay, on_delete=models.CASCADE)
    time_slot = models.TimeField(default='08:00', verbose_name="Créneau horaire")
    is_active = models.BooleanField(default=True)
    programme_tricycle = models.ForeignKey(ProgrammeTricycle, on_delete=models.CASCADE, null=True, blank=True, related_name='jours_abonnement')
    
    class Meta:
        verbose_name = "Jour d'abonnement"
        verbose_name_plural = "Jours d'abonnement"
        unique_together = ['subscription', 'day']
    
    def __str__(self):
        return f"{self.subscription} - {self.day}"





class CollectionRequest(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('scheduled', 'Programmée'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
        ('missed', 'Manquée'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='collections')
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    collector = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, blank=True, 
                                 limit_choices_to={'user_type': 'collecteur'})
    actual_collection_time = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Demande de collecte"
        verbose_name_plural = "Demandes de collecte"
        indexes = [
            models.Index(fields=['scheduled_date', 'status']),
            models.Index(fields=['subscription', 'scheduled_date']),
        ]
        ordering = ['scheduled_date', 'scheduled_time']
    
    def __str__(self):
        return f"Collecte {self.scheduled_date} - {self.subscription}"

class Payment(models.Model):
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
        ('refunded', 'Remboursé'),
    )
    
    
    subscription = models.CharField(max_length=100, blank=True, null=True)   
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(default=timezone.now)
    due_date = models.DateField()
    payment_method = models.CharField(max_length=50, blank=True)
    transaction_id = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Paiement"
        verbose_name_plural = "Paiements"
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Paiement {self.amount} - {self.subscription}"
    

class AnnonceCarousel(models.Model):
    titre = models.CharField(max_length=200, verbose_name="Titre de l'annonce")
    description = models.TextField(blank=True, verbose_name="Description")
    image = models.ImageField(upload_to='carousel/', verbose_name="Image du carousel")
    lien = models.URLField(blank=True, verbose_name="Lien optionnel")
    date_creation = models.DateTimeField(default=timezone.now)
    date_debut = models.DateTimeField(default=timezone.now, verbose_name="Date de début d'affichage")
    date_fin = models.DateTimeField(verbose_name="Date de fin d'affichage")
    actif = models.BooleanField(default=True, verbose_name="Actif")
    ordre = models.IntegerField(default=0, verbose_name="Ordre d'affichage")
    
    class Meta:
        verbose_name = "Annonce Carousel"
        verbose_name_plural = "Annonces Carousel"
        ordering = ['ordre', '-date_creation']
    
    def __str__(self):
        return self.titre
    
    def est_actif(self):
        maintenant = timezone.now()
        return self.actif and self.date_debut <= maintenant <= self.date_fin
    

class CollectionSchedule(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Programmée'),
        ('completed', 'Terminée'),
        ('cancelled', 'Annulée'),
        ('missed', 'Manquée'),
    )
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE, related_name='schedules')
    scheduled_date = models.DateField()
    scheduled_day = models.ForeignKey(CollectionDay, on_delete=models.CASCADE)
    scheduled_time = models.TimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    collector_notes = models.TextField(blank=True)
    customer_notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Programme de collecte"
        verbose_name_plural = "Programmes de collecte"
        ordering = ['scheduled_date', 'scheduled_time']
        indexes = [
            models.Index(fields=['subscription', 'scheduled_date']),
            models.Index(fields=['scheduled_date', 'status']),
        ]
    
    def __str__(self):
        return f"Collecte {self.scheduled_date} - {self.subscription}"
    
# signal pour creer un programme de collecte automatiquement après la création d'un abonnement


# SIGNAL POUR SUPPRIMER LES PROGRAMMES DE COLLECTES LIÉS AUX ABONNEMENTS INACTIFS
@receiver(post_save, sender=Subscription)
def supprimer_programmes_collecte_abonnement_inactif(sender, instance, **kwargs):
    """
    Signal pour supprimer automatiquement les programmes de collecte
    lorsqu'un abonnement devient inactif
    """
    # Vérifier si le statut de l'abonnement n'est pas 'active'
    if instance.status != 'active':
        

        
        
        # Créer une notification pour informer l'utilisateur
        if instance.user:
            Notification.create_notification(
                user=instance.user,
                title="Abonnement désactivé",
                message=f"Votre abonnement {instance.plan.name} a été désactivé. Les collectes programmées ont été annulées.",
                notification_type='warning',
                related_object=instance,
                action_url=f'/subscriptions/{instance.id}/'
            )
    
    if instance.status == 'active':
       from .views import generate_collection_schedule

       #generation automatique du qr code de paiement après réabonnement
       qr_code, created = SubscriptionQRCode.objects.get_or_create(subscription=instance)
       # Générer l'image QR code si elle n'existe pas
       if not qr_code.qr_code_image:
        # Générer le QR code
            qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        
            renewal_url = qr_code.get_renewal_url()
            qr.add_data(renewal_url)
            qr.make(fit=True)
        
        # Créer l'image
            img = qr.make_image(fill_color="black", back_color="white")
        
        # Sauvegarder l'image
            buffer = BytesIO()
            img.save(buffer, format='PNG')
        
        # Sauvegarder dans le modèle
            filename = f"subscription_{instance.id}_qr.png"
            qr_code.qr_code_image.save(filename, buffer, save=True)



       if CollectionSchedule.objects.filter(subscription=instance).count() == 0:
            instance.assigner_jours_collecte_automatique()
            generate_collection_schedule(instance)
    
       else:
            # Si des programmes de collecte existent déjà, les supprimer et les recréer
            CollectionSchedule.objects.filter(subscription=instance).delete()
            instance.assigner_jours_collecte_automatique()
            generate_collection_schedule(instance)







# Fonctions utilitaires
def get_jours_disponibles_zone(zone):
    """
    Retourne les jours disponibles pour une zone donnée
    """
    programmes = ProgrammeTricycle.objects.filter(
        zone=zone,
        is_active=True
    ).select_related('tricycle')
    
    jours_disponibles = []
    for programme in programmes:
        if programme.peut_ajouter_client():
            jours_disponibles.append({
                'jour': programme.jour_semaine,
                'jour_display': programme.get_jour_semaine_display(),
                'heure_debut': programme.heure_debut,
                'heure_fin': programme.heure_fin,
                'tricycle': programme.tricycle.nom,
                'places_restantes': programme.places_disponibles()
            })
    
    return jours_disponibles

def creer_programme_collecte_automatique(subscription):
    """
    Fonction pour créer automatiquement le programme de collecte après la création d'un abonnement
    """
    return subscription.assigner_jours_collecte_automatique()

# Signal pour assigner automatiquement les jours de collecte après la création d'un abonnement


@receiver(post_save, sender=Subscription)
def assigner_jours_collecte(sender, instance, created, **kwargs):
    if created and instance.status == 'active':
        creer_programme_collecte_automatique(instance)





class SubscriptionQRCode(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.OneToOneField(Subscription, on_delete=models.CASCADE, related_name='qr_code')
    token = models.CharField(max_length=100, unique=True, editable=False)
    qr_code_image = models.ImageField(upload_to='qr_codes/subscriptions/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "QR Code d'abonnement"
        verbose_name_plural = "QR Codes d'abonnement"
    
    def __str__(self):
        return f"QR Code - {self.subscription}"
    
    def save(self, *args, **kwargs):
        if not self.token:
            self.token = self._generate_token()
        super().save(*args, **kwargs)
    
    def _generate_token(self):
        import secrets
        return secrets.token_urlsafe(32)
    
    def get_renewal_url(self):
        return f"{settings.SITE_URL}/subscription/qr-renew/{self.token}/"
    


# signal pour creer des qrcode automatiquement apres reabonnement 
@receiver(post_save, sender=Subscription)
def create_subscription_qr_code(sender, instance, created, **kwargs):
    if created:
        SubscriptionQRCode.objects.get_or_create(subscription=instance)



# Ajouter à la fin de models.py
class Notification(models.Model):
    NOTIFICATION_TYPES = (
        ('info', 'Information'),
        ('success', 'Succès'),
        ('warning', 'Avertissement'),
        ('error', 'Erreur'),
        ('collection', 'Collecte'),
        ('payment', 'Paiement'),
        ('system', 'Système'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200, verbose_name="Titre de la notification")
    message = models.TextField(verbose_name="Message de la notification")
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='info')
    is_read = models.BooleanField(default=False)
    related_object_id = models.UUIDField(blank=True, null=True)
    related_object_type = models.CharField(max_length=100, blank=True)
    action_url = models.URLField(blank=True, verbose_name="URL d'action")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self):
        self.is_read = True
        self.save()
    
    @classmethod
    def create_notification(cls, user, title, message, notification_type='info', 
                          related_object=None, action_url=''):
        """
        Méthode utilitaire pour créer facilement des notifications
        """
        notification = cls(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            action_url=action_url
        )
        
        if related_object:
            notification.related_object_id = related_object.id
            notification.related_object_type = related_object.__class__.__name__
        
        notification.save()
        return notification

# Signaux pour les notifications automatiques
@receiver(post_save, sender=CollectionRequest)
def notify_collection_status_change(sender, instance, created, **kwargs):
    if not created:  # Seulement pour les mises à jour
        if instance.status == 'scheduled':
            Notification.create_notification(
                user=instance.subscription.user,
                title="Collecte programmée",
                message=f"Votre collecte a été programmée pour le {instance.scheduled_date} à {instance.scheduled_time}",
                notification_type='collection',
                related_object=instance,
                action_url=f'/collections/{instance.id}/'
            )
        elif instance.status == 'completed':
            Notification.create_notification(
                user=instance.subscription.user,
                title="Collecte terminée",
                message=f"Votre collecte du {instance.scheduled_date} a été effectuée avec succès",
                notification_type='success',
                related_object=instance,
                action_url=f'/collections/{instance.id}/'
            )

@receiver(post_save, sender=Payment)
def notify_payment_status(sender, instance, created, **kwargs):
    if instance.status == 'completed':
        Notification.create_notification(
            user=instance.subscription.user,
            title="Paiement confirmé",
            message=f"Votre paiement de {instance.amount}€ a été confirmé",
            notification_type='payment',
            related_object=instance,
            action_url=f'/payments/{instance.id}/'
        )
    elif instance.status == 'failed':
        Notification.create_notification(
            user=instance.subscription.user,
            title="Échec du paiement",
            message=f"Votre paiement de {instance.amount}FCFA a échoué. Veuillez réessayer.",
            notification_type='error',
            related_object=instance,
            action_url=f'/payments/{instance.id}/'
        )

@receiver(post_save, sender=Subscription)
def notify_subscription_status(sender, instance, created, **kwargs):
    if created:
        Notification.create_notification(
            user=instance.user,
            title="Abonnement créé",
            message=f"Votre abonnement {instance.plan.name} a été créé avec succès",
            notification_type='success',
            related_object=instance,
            action_url=f'/subscriptions/{instance.id}/'
        )



# model django pour les reabonnement


class Abonnement(models.Model):
    """Modèle de base pour les abonnements"""
    TYPE_SERVICE = (
        ('CANAL', 'Canal+'),
        ('ENEO', 'Eneo'),
        ('CAMWATER', 'Cam Water'),
    )
    
    client = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name='abonnements')
    type_service = models.CharField(max_length=10, choices=TYPE_SERVICE)
    identifiant_abonne = models.CharField(max_length=50, verbose_name="Identifiant abonné")
    est_actif = models.BooleanField(default=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_type_service_display()} - {self.identifiant_abonne}"

    class Meta:
        verbose_name = "Abonnement"
        verbose_name_plural = "Abonnements"
        ordering = ['-date_creation']
        unique_together = ('type_service', 'identifiant_abonne') 


class DemandeReabonnement(models.Model):
    """Modèle pour les demandes de réabonnement"""
    STATUT_CHOICES = (
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours de traitement'),
        ('TRAITEE', 'Traitée'),
        ('REJETEE', 'Rejetée'),
    )
    
    
    abonnement = models.ForeignKey(Abonnement, on_delete=models.CASCADE, related_name='demandes_reabonnement')
    montant = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0)])
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_demande = models.DateTimeField(auto_now_add=True)
    date_traitement = models.DateTimeField(null=True, blank=True)
    commentaires = models.TextField(blank=True)
    offre_choisie = models.CharField(max_length=100, blank=True, null=True, verbose_name="Offre choisie")

    def __str__(self):
        return f"Demande #{self.id} - {self.abonnement}"

    def save(self, *args, **kwargs):
        if self.statut == 'TRAITEE' and not self.date_traitement:
            self.date_traitement = timezone.now()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Demande de réabonnement"
        verbose_name_plural = "Demandes de réabonnement"
        ordering = ['-date_demande']


    
class Facture(models.Model):
    """Modèle pour stocker les factures générées"""
    demande = models.OneToOneField(Abonnement, on_delete=models.CASCADE, related_name='facture')
    fichier = models.FileField(upload_to='factures/%Y/%m/%d/')
    numero_facture = models.CharField(max_length=20, unique=True)
    date_emission = models.DateTimeField(auto_now_add=True)
    date_echeance = models.DateTimeField()
    est_payee = models.BooleanField(default=False)

    def __str__(self):
        return f"Facture {self.numero_facture}"

    class Meta:
        verbose_name = "Facture"
        verbose_name_plural = "Factures"
        ordering = ['-date_emission']

class HistoriqueAbonnement(models.Model):
    """Modèle pour tracer l'historique des abonnements"""
    abonnement = models.ForeignKey(Abonnement, on_delete=models.CASCADE, related_name='historique')
    action = models.CharField(max_length=100)
    details = models.JSONField()
    date_action = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.abonnement}"

    class Meta:
        verbose_name = "Historique d'abonnement"
        verbose_name_plural = "Historiques d'abonnement"
        ordering = ['-date_action']


# les models pour la contabilité et le chiffre d'aafaires 
# Ajoutez ces modèles à la fin de votre fichier models.py

class RevenueRecord(models.Model):
    """
    Modèle pour enregistrer le chiffre d'affaires avec différents niveaux de détail
    """
    REVENUE_TYPE_CHOICES = (
        ('subscription', 'Abonnement'),
        ('one_time', 'Paiement unique'),
        ('renewal', 'Réabonnement'),
        ('penalty', 'Pénalité'),
        ('refund', 'Remboursement'),
        ('other', 'Autre'),
    )
    
    PAYMENT_METHOD_CHOICES = (
        ('mobile_money', 'Mobile Money'),
        ('credit_card', 'Carte de crédit'),
        ('bank_transfer', 'Virement bancaire'),
        ('cash', 'Espèces'),
        ('other', 'Autre'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'En attente'),
        ('completed', 'Complété'),
        ('failed', 'Échoué'),
        ('refunded', 'Remboursé'),
        ('cancelled', 'Annulé'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, null=True, blank=True, related_name='revenue_records')
    payment = models.OneToOneField(Payment, on_delete=models.SET_NULL, null=True, blank=True, related_name='revenue_record')
    demande_reabonnement = models.ForeignKey(DemandeReabonnement, on_delete=models.SET_NULL, null=True, blank=True, related_name='revenue_records')
    
    # Informations sur le revenu
    revenue_type = models.CharField(max_length=20, choices=REVENUE_TYPE_CHOICES)
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant")
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Montant des taxes")
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Montant net")
    
    # Méthode de paiement et statut
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='completed')
    
    # Dates importantes
    transaction_date = models.DateTimeField(default=timezone.now, verbose_name="Date de transaction")
    recording_date = models.DateTimeField(auto_now_add=True, verbose_name="Date d'enregistrement")
    period_start = models.DateField(verbose_name="Début de période")
    period_end = models.DateField(verbose_name="Fin de période")
    
    # Métadonnées
    description = models.TextField(blank=True, verbose_name="Description")
    invoice_number = models.CharField(max_length=50, blank=True, verbose_name="Numéro de facture")
    customer = models.ForeignKey(CustomUser, on_delete=models.SET_NULL, null=True, related_name='revenue_transactions')
    zone = models.ForeignKey(Zone, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Zone géographique")
    
    # Champs pour le suivi
    is_recurring = models.BooleanField(default=False, verbose_name="Recurrent")
    related_revenue = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='child_transactions')
    
    class Meta:
        verbose_name = "Enregistrement de revenu"
        verbose_name_plural = "Enregistrements de revenus"
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['transaction_date', 'status']),
            models.Index(fields=['revenue_type', 'status']),
            models.Index(fields=['customer', 'transaction_date']),
            models.Index(fields=['zone', 'transaction_date']),
        ]
    
    def __str__(self):
        return f"Revenu {self.amount} - {self.get_revenue_type_display()} - {self.transaction_date.strftime('%Y-%m-%d')}"
    
    def save(self, *args, **kwargs):
        """Calcul automatique du montant net avant sauvegarde"""
        if not self.net_amount:
            self.net_amount = int(self.amount) - int(self.tax_amount)
        super().save(*args, **kwargs)

class RevenueSummary(models.Model):
    """
    Modèle pour les résumés de revenus par période (quotidien, mensuel, annuel)
    """
    PERIOD_CHOICES = (
        ('daily', 'Quotidien'),
        ('weekly', 'Hebdomadaire'),
        ('monthly', 'Mensuel'),
        ('quarterly', 'Trimestriel'),
        ('yearly', 'Annuel'),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    
    # Chiffre d'affaires total
    total_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_tax = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_net_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Répartition par type
    subscription_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    one_time_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    renewal_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    penalty_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    other_revenue = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Métriques
    active_subscriptions = models.PositiveIntegerField(default=0)
    new_subscriptions = models.PositiveIntegerField(default=0)
    cancelled_subscriptions = models.PositiveIntegerField(default=0)
    average_revenue_per_user = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Répartition géographique (JSON pour flexibilité)
    revenue_by_zone = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Résumé des revenus"
        verbose_name_plural = "Résumés des revenus"
        unique_together = ['period_type', 'period_start']
        ordering = ['-period_start']
    
    def __str__(self):
        return f"Résumé {self.get_period_type_display()} - {self.period_start} au {self.period_end}"

class RevenueSettings(models.Model):
    """
    Paramètres pour la configuration du suivi des revenus
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name="Taux de taxe (%)")
    currency = models.CharField(max_length=3, default='EUR', verbose_name="Devise")
    fiscal_year_start = models.DateField(default=timezone.now, verbose_name="Début d'année fiscale")
    auto_generate_summaries = models.BooleanField(default=True, verbose_name="Générer automatiquement les résumés")
    summary_generation_time = models.TimeField(default=timezone.now, verbose_name="Heure de génération des résumés")
    
    class Meta:
        verbose_name = "Paramètre de revenu"
        verbose_name_plural = "Paramètres de revenus"
    
    def __str__(self):
        return f"Paramètres revenus - Taxe: {self.tax_rate}%"

# Signaux pour automatiser le suivi des revenus
@receiver(post_save, sender=Payment)
def create_revenue_from_payment(sender, instance, created, **kwargs):
    """
    Créer automatiquement un enregistrement de revenu lorsqu'un paiement est marqué comme complété
    """
    if instance.status == 'completed':
        # Calculer la période (mois en cours)
        today = timezone.now().date()
        period_start = today.replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        period_end = next_month - timezone.timedelta(days=1)
        
        # Créer l'enregistrement de revenu
        RevenueRecord.objects.get_or_create(
            payment=instance,
            defaults={
                'subscription': instance.subscription,
                'revenue_type': 'subscription',
                'amount': instance.amount,
                'tax_amount': instance.amount*0.1 ,  # À adapter selon votre logique fiscale
                'net_amount': instance.amount - (instance.amount*0.1),
                'payment_method': 'mobile_money',  # À adapter
                'status': 'completed',
                'transaction_date': instance.payment_date,
                'period_start': period_start,
                'period_end': period_end,
                'description': f"Paiement abonnement {instance.subscription.plan.name}",
                'customer': instance.subscription.user,
                'zone':  None,
                'is_recurring': True,
            }
        )

@receiver(post_save, sender=DemandeReabonnement)
def create_revenue_from_reabonnement(sender, instance, created, **kwargs):
    """
    Créer automatiquement un enregistrement de revenu lorsqu'un réabonnement est traité
    """
    if instance.statut == 'TRAITEE':
        today = timezone.now().date()
        period_start = today.replace(day=1)
        next_month = period_start.replace(month=period_start.month + 1) if period_start.month < 12 else period_start.replace(year=period_start.year + 1, month=1)
        period_end = next_month - timezone.timedelta(days=1)
        
        RevenueRecord.objects.get_or_create(
            demande_reabonnement=instance,
            defaults={
                'revenue_type': 'renewal',
                'amount': instance.montant,
                'tax_amount': int(instance.montant)*0.1,  
                'net_amount': int(instance.montant) - int(instance.montant),
                'payment_method': 'mobile_money',
                'status': 'completed',
                'transaction_date': instance.date_traitement or timezone.now(),
                'period_start': period_start,
                'period_end': period_end,
                'description': f"Réabonnement {instance.abonnement.get_type_service_display()}",
                'customer': instance.abonnement.client,
                'is_recurring': False,
            }
        )

# Fonctions utilitaires pour les rapports
def get_daily_revenue(date=None):
    """Obtenir le chiffre d'affaires pour une date spécifique"""
    if date is None:
        date = timezone.now().date()
    
    records = RevenueRecord.objects.filter(
        transaction_date__date=date,
        status='completed'
    )
    
    return {
        'date': date,
        'total_revenue': records.aggregate(total=models.Sum('amount'))['total'] or 0,
        'total_net_revenue': records.aggregate(total=models.Sum('net_amount'))['total'] or 0,
        'transaction_count': records.count(),
        'breakdown': records.values('revenue_type').annotate(
            total=models.Sum('amount'),
            count=models.Count('id')
        )
    }

def generate_revenue_summary(period_type, start_date, end_date):
    """Générer un résumé des revenus pour une période donnée"""
    records = RevenueRecord.objects.filter(
        transaction_date__date__gte=start_date,
        transaction_date__date__lte=end_date,
        status='completed'
    )
    
    if not records.exists():
        return None
    
    # Calcul des totaux
    aggregation = records.aggregate(
        total_revenue=models.Sum('amount'),
        total_tax=models.Sum('tax_amount'),
        total_net=models.Sum('net_amount')
    )
    
    # Répartition par type
    revenue_by_type = records.values('revenue_type').annotate(
        total=models.Sum('amount')
    )
    
    # Répartition par zone
    revenue_by_zone = records.values('zone__nom').annotate(
        total=models.Sum('amount')
    )
    
    summary_data = {
        'subscription_revenue': 0,
        'one_time_revenue': 0,
        'renewal_revenue': 0,
        'penalty_revenue': 0,
        'other_revenue': 0,
    }
    
    for item in revenue_by_type:
        revenue_type = item['revenue_type']
        if revenue_type in summary_data:
            summary_data[f"{revenue_type}_revenue"] = item['total']
    
    # Créer le résumé
    summary, created = RevenueSummary.objects.update_or_create(
        period_type=period_type,
        period_start=start_date,
        period_end=end_date,
        defaults={
            'total_revenue': aggregation['total_revenue'] or 0,
            'total_tax': aggregation['total_tax'] or 0,
            'total_net_revenue': aggregation['total_net'] or 0,
            **summary_data,
            'revenue_by_zone': {item['zone__nom']: item['total'] for item in revenue_by_zone if item['zone__nom']},
            'active_subscriptions': Subscription.objects.filter(
                status='active',
                start_date__lte=end_date,
                end_date__gte=start_date
            ).count(),
            'new_subscriptions': Subscription.objects.filter(
                start_date__gte=start_date,
                start_date__lte=end_date
            ).count(),
        }
    )
    
    return summary

# Tâche périodique pour générer les résumés (à appeler via Celery ou cron)
def generate_periodic_summaries():
    """Générer les résumés quotidiens, mensuels et annuels"""
    today = timezone.now().date()
    
    # Résumé quotidien (hier)
    yesterday = today - timezone.timedelta(days=1)
    generate_revenue_summary('daily', yesterday, yesterday)
    
    # Résumé mensuel (mois précédent)
    first_day_prev_month = today.replace(day=1) - timezone.timedelta(days=1)
    first_day_prev_month = first_day_prev_month.replace(day=1)
    last_day_prev_month = today.replace(day=1) - timezone.timedelta(days=1)
    generate_revenue_summary('monthly', first_day_prev_month, last_day_prev_month)
    
    # Résumé annuel (année précédente)
    if today.month == 1 and today.day == 1:
        prev_year = today.year - 1
        generate_revenue_summary('yearly', 
                               date(prev_year, 1, 1), 
                               date(prev_year, 12, 31))


class Performence(models.Model):
    Tricycle = models.ForeignKey(Tricycle, on_delete=models.CASCADE, related_name='responsables')
    note = models.FloatField(max_length=2)
    date = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.Tricycle.conducteur