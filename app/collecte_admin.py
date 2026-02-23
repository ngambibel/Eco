from django.http import JsonResponse
from django.views import View
from django.views.generic import TemplateView
from django.db import transaction
from django.db.models import Count, Q
import json

from app.views import generate_collection_schedule
from .models import (
    Zone, Tricycle, ProgrammeTricycle, CollectionDay, 
    City, CustomUser, Subscription, SubscriptionDay, CollectionSchedule
)

class GestionCollecteView(TemplateView):
    """Vue principale pour la gestion des zones, tricycles et programmes"""
    template_name = 'administrations/gestion_collecte.html'

# API Views pour les Zones
class ZoneListCreateAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Récupérer toutes les zones avec leurs statistiques"""
        try:
            zones = Zone.objects.select_related('ville').annotate(
                programmes_count=Count('programmes_tricycle', filter=Q(programmes_tricycle__is_active=True))
            ).order_by('ville__city', 'nom')
            
            zones_data = []
            for zone in zones:
                zones_data.append({
                    'id': str(zone.id),
                    'nom': zone.nom,
                    'description': zone.description,
                    'ville_id': zone.ville.id if zone.ville else None,
                    'ville_nom': zone.ville.city if zone.ville else 'Non spécifiée',
                    'couleur': zone.couleur,
                    'is_active': zone.is_active,
                    'programmes_count': zone.programmes_count,
                    'created_at': zone.created_at.strftime('%d/%m/%Y %H:%M')
                })
            
            return JsonResponse(zones_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
        
    
    def post(self, request):
        """Créer une nouvelle zone"""
        try:
            data = json.loads(request.body)
            
            # Validation des données requises
            if not data.get('nom'):
                return JsonResponse({'nom': ['Le nom de la zone est obligatoire']}, status=400)
            
            if not data.get('ville'):
                return JsonResponse({'ville': ['La ville est obligatoire']}, status=400)
            
            try:
                ville = City.objects.get(id=data['ville'])
            except City.DoesNotExist:
                return JsonResponse({'ville': ['Ville non trouvée']}, status=400)
            
            # Vérifier si une zone avec le même nom existe déjà
            if Zone.objects.filter(nom=data['nom']).exists():
                return JsonResponse({'nom': ['Une zone avec ce nom existe déjà']}, status=400)
            
            # Créer la zone
            zone = Zone.objects.create(
                nom=data['nom'],
                ville=ville,
                description=data.get('description', ''),
                couleur=data.get('couleur', '#27AE60'),
                is_active=data.get('is_active', True)
            )
            
            return JsonResponse({
                'id': str(zone.id),
                'message': 'Zone créée avec succès'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ZoneRetrieveUpdateDestroyAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, pk):
        """Récupérer une zone spécifique"""
        try:
            zone = Zone.objects.select_related('ville').get(id=pk)
            
            zone_data = {
                'id': str(zone.id),
                'nom': zone.nom,
                'description': zone.description,
                'ville_id': zone.ville.id,
                'ville_nom': zone.ville.city,
                'couleur': zone.couleur,
                'is_active': zone.is_active,
                'created_at': zone.created_at.strftime('%d/%m/%Y %H:%M')
            }
            
            return JsonResponse(zone_data, status=200)
            
        except Zone.DoesNotExist:
            return JsonResponse({'error': 'Zone non trouvée'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def put(self, request, pk):
        """Mettre à jour une zone"""
        try:
            zone = Zone.objects.get(id=pk)
            data = json.loads(request.body)
            
            # Validation
            if 'nom' in data and data['nom'] and zone.nom != data['nom']:
                if Zone.objects.filter(nom=data['nom']).exclude(id=pk).exists():
                    return JsonResponse({'nom': ['Une zone avec ce nom existe déjà']}, status=400)
            
            # Mise à jour
            if 'nom' in data:
                zone.nom = data['nom']
            if 'description' in data:
                zone.description = data['description']
            if 'ville' in data:
                try:
                    ville = City.objects.get(id=data['ville'])
                    zone.ville = ville
                except City.DoesNotExist:
                    return JsonResponse({'ville': ['Ville non trouvée']}, status=400)
            if 'couleur' in data:
                zone.couleur = data['couleur']
            if 'is_active' in data:
                zone.is_active = data['is_active']
            
            zone.save()
            
            return JsonResponse({
                'message': 'Zone mise à jour avec succès',
                'id': str(zone.id)
            }, status=200)
            
        except Zone.DoesNotExist:
            return JsonResponse({'error': 'Zone non trouvée'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete(self, request, pk):
        """Supprimer une zone"""
        try:
            zone = Zone.objects.get(id=pk)
            
            # Vérifier s'il y a des programmes associés
            if zone.programmes_tricycle.exists():
                return JsonResponse({
                    'error': 'Impossible de supprimer cette zone car elle a des programmes de collecte associés'
                }, status=400)
            
            # Vérifier s'il y a des adresses associées
            if zone.adresses.exists():
                return JsonResponse({
                    'error': 'Impossible de supprimer cette zone car elle a des adresses associées'
                }, status=400)
            
            zone.delete()
            
            return JsonResponse({'message': 'Zone supprimée avec succès'}, status=200)
            
        except Zone.DoesNotExist:
            return JsonResponse({'error': 'Zone non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ActiveZoneListAPIView(View):
    def get(self, request):
        """Récupérer seulement les zones actives"""
        try:
            zones = Zone.objects.filter(is_active=True).select_related('ville').order_by('nom')
            
            zones_data = []
            for zone in zones:
                zones_data.append({
                    'id': str(zone.id),
                    'nom': zone.nom,
                    'ville_nom': zone.ville.city if zone.ville else 'Non spécifiée'
                })
            
            return JsonResponse(zones_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# API Views pour les Tricycles
class TricycleListCreateAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Récupérer tous les tricycles"""
        try:
            tricycles = Tricycle.objects.select_related('conducteur').order_by('numero_immatriculation')
            
            tricycles_data = []
            for tricycle in tricycles:
                tricycles_data.append({
                    'id': str(tricycle.id),
                    'numero_immatriculation': tricycle.numero_immatriculation,
                    'nom': tricycle.nom,
                    'capacite_kg': float(tricycle.capacite_kg),
                    'couleur': tricycle.couleur,
                    'date_mise_en_service': tricycle.date_mise_en_service.strftime('%d/%m/%Y') if tricycle.date_mise_en_service else None,
                    'status': tricycle.status,
                    'conducteur_id': tricycle.conducteur.id if tricycle.conducteur else None,
                    'conducteur_nom': f"{tricycle.conducteur.first_name} {tricycle.conducteur.last_name}".strip() if tricycle.conducteur else None,
                    'notes': tricycle.notes,
                    'created_at': tricycle.created_at.strftime('%d/%m/%Y %H:%M')
                })
            
            return JsonResponse(tricycles_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request):
        """Créer un nouveau tricycle"""
        try:
            data = json.loads(request.body)
            
            # Validation
            required_fields = ['numero_immatriculation', 'nom', 'capacite_kg']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({field: ['Ce champ est obligatoire']}, status=400)
            
            # Vérifier l'unicité du numéro d'immatriculation
            if Tricycle.objects.filter(numero_immatriculation=data['numero_immatriculation']).exists():
                return JsonResponse({'numero_immatriculation': ['Un tricycle avec ce numéro existe déjà']}, status=400)
            
            # Gérer le conducteur
            conducteur = None
            if data.get('conducteur'):
                try:
                    conducteur = CustomUser.objects.get(
                        id=data['conducteur'], 
                        user_type='collecteur'
                    )
                except CustomUser.DoesNotExist:
                    return JsonResponse({'conducteur': ['Collecteur non trouvé']}, status=400)
            
            # Créer le tricycle
            tricycle = Tricycle.objects.create(
                numero_immatriculation=data['numero_immatriculation'],
                nom=data['nom'],
                capacite_kg=data['capacite_kg'],
                couleur=data.get('couleur', ''),
                date_mise_en_service=data.get('date_mise_en_service'),
                status=data.get('status', 'active'),
                conducteur=conducteur,
                notes=data.get('notes', '')
            )
            
            return JsonResponse({
                'id': str(tricycle.id),
                'message': 'Tricycle créé avec succès'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class TricycleRetrieveUpdateDestroyAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, pk):
        """Récupérer un tricycle spécifique"""
        try:
            tricycle = Tricycle.objects.select_related('conducteur').get(id=pk)
            
            tricycle_data = {
                'id': str(tricycle.id),
                'numero_immatriculation': tricycle.numero_immatriculation,
                'nom': tricycle.nom,
                'capacite_kg': float(tricycle.capacite_kg),
                'couleur': tricycle.couleur,
                'date_mise_en_service': tricycle.date_mise_en_service.strftime('%Y-%m-%d') if tricycle.date_mise_en_service else None,
                'status': tricycle.status,
                'conducteur_id': tricycle.conducteur.id if tricycle.conducteur else None,
                'notes': tricycle.notes
            }
            
            return JsonResponse(tricycle_data, status=200)
            
        except Tricycle.DoesNotExist:
            return JsonResponse({'error': 'Tricycle non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def put(self, request, pk):
        """Mettre à jour un tricycle"""
        try:
            tricycle = Tricycle.objects.get(id=pk)
            data = json.loads(request.body)
            
            # Vérifier l'unicité du numéro d'immatriculation
            if 'numero_immatriculation' in data and data['numero_immatriculation'] != tricycle.numero_immatriculation:
                if Tricycle.objects.filter(numero_immatriculation=data['numero_immatriculation']).exclude(id=pk).exists():
                    return JsonResponse({'numero_immatriculation': ['Un tricycle avec ce numéro existe déjà']}, status=400)
            
            # Mise à jour des champs
            if 'numero_immatriculation' in data:
                tricycle.numero_immatriculation = data['numero_immatriculation']
            if 'nom' in data:
                tricycle.nom = data['nom']
            if 'capacite_kg' in data:
                tricycle.capacite_kg = data['capacite_kg']
            if 'couleur' in data:
                tricycle.couleur = data['couleur']
            if 'date_mise_en_service' in data:
                tricycle.date_mise_en_service = data['date_mise_en_service']
            if 'status' in data:
                tricycle.status = data['status']
            if 'notes' in data:
                tricycle.notes = data['notes']
            
            # Gérer le conducteur
            if 'conducteur' in data:
                if data['conducteur']:
                    try:
                        conducteur = CustomUser.objects.get(
                            id=data['conducteur'], 
                            user_type='collecteur'
                        )
                        tricycle.conducteur = conducteur
                    except CustomUser.DoesNotExist:
                        return JsonResponse({'conducteur': ['Collecteur non trouvé']}, status=400)
                else:
                    tricycle.conducteur = None
            
            tricycle.save()
            
            return JsonResponse({
                'message': 'Tricycle mis à jour avec succès',
                'id': str(tricycle.id)
            }, status=200)
            
        except Tricycle.DoesNotExist:
            return JsonResponse({'error': 'Tricycle non trouvé'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete(self, request, pk):
        """Supprimer un tricycle"""
        try:
            tricycle = Tricycle.objects.get(id=pk)
            
            # Vérifier s'il y a des programmes associés
            if tricycle.programmes.exists():
                return JsonResponse({
                    'error': 'Impossible de supprimer ce tricycle car il a des programmes de collecte associés'
                }, status=400)
            
            tricycle.delete()
            
            return JsonResponse({'message': 'Tricycle supprimé avec succès'}, status=200)
            
        except Tricycle.DoesNotExist:
            return JsonResponse({'error': 'Tricycle non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ActiveTricycleListAPIView(View):
    def get(self, request):
        """Récupérer seulement les tricycles actifs"""
        try:
            tricycles = Tricycle.objects.filter(status='active').order_by('nom')
            
            tricycles_data = []
            for tricycle in tricycles:
                tricycles_data.append({
                    'id': str(tricycle.id),
                    'nom': tricycle.nom,
                    'numero_immatriculation': tricycle.numero_immatriculation
                })
            
            return JsonResponse(tricycles_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# API Views pour les Programmes de Tricycle
class ProgrammeTricycleListCreateAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Récupérer tous les programmes de tricycle"""
        try:
            programmes = ProgrammeTricycle.objects.select_related(
                'tricycle', 'zone', 'zone__ville'
            ).order_by('jour_semaine', 'heure_debut')
            
            programmes_data = []
            for programme in programmes:
                programmes_data.append({
                    'id': str(programme.id),
                    'tricycle_id': str(programme.tricycle.id),
                    'tricycle_nom': programme.tricycle.nom,
                    'zone_id': str(programme.zone.id),
                    'zone_nom': programme.zone.nom,
                    'jour_semaine': programme.jour_semaine,
                    'heure_debut': programme.heure_debut.strftime('%H:%M'),
                    'heure_fin': programme.heure_fin.strftime('%H:%M'),
                    'capacite_max_clients': programme.capacite_max_clients,
                    'clients_actuels': programme.clients_actuels,
                    'places_disponibles': programme.places_disponibles(),
                    'is_active': programme.is_active,
                    'date_debut': programme.date_debut.strftime('%d/%m/%Y') if programme.date_debut else None,
                    'date_fin': programme.date_fin.strftime('%d/%m/%Y') if programme.date_fin else None,
                    'created_at': programme.created_at.strftime('%d/%m/%Y %H:%M')
                })
            
            return JsonResponse(programmes_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request):
        """Créer un nouveau programme de tricycle"""
        try:
            data = json.loads(request.body)
            
            # Validation des champs requis
            required_fields = ['tricycle', 'zone', 'jour_semaine', 'heure_debut', 'heure_fin']
            for field in required_fields:
                if not data.get(field):
                    return JsonResponse({field: ['Ce champ est obligatoire']}, status=400)
            
            # Vérifier le tricycle
            try:
                tricycle = Tricycle.objects.get(id=data['tricycle'])
            except Tricycle.DoesNotExist:
                return JsonResponse({'tricycle': ['Tricycle non trouvé']}, status=400)
            
            # Vérifier la zone
            try:
                zone = Zone.objects.get(id=data['zone'])
            except Zone.DoesNotExist:
                return JsonResponse({'zone': ['Zone non trouvée']}, status=400)
            
            # Vérifier l'unicité (même tricycle, même zone, même jour)
            if ProgrammeTricycle.objects.filter(
                tricycle=tricycle, 
                zone=zone, 
                jour_semaine=data['jour_semaine']
            ).exists():
                return JsonResponse({
                    'error': 'Un programme existe déjà pour ce tricycle, cette zone et ce jour'
                }, status=400)
            
            # Créer le programme
            programme = ProgrammeTricycle.objects.create(
                tricycle=tricycle,
                zone=zone,
                jour_semaine=data['jour_semaine'],
                heure_debut=data['heure_debut'],
                heure_fin=data['heure_fin'],
                capacite_max_clients=data.get('capacite_max_clients', 50),
                is_active=data.get('is_active', True),
                date_debut=data.get('date_debut')
            )
            
            return JsonResponse({
                'id': str(programme.id),
                'message': 'Programme créé avec succès'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ProgrammeTricycleRetrieveUpdateDestroyAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request, pk):
        """Récupérer un programme spécifique"""
        try:
            programme = ProgrammeTricycle.objects.select_related('tricycle', 'zone').get(id=pk)
            
            programme_data = {
                'id': str(programme.id),
                'tricycle_id': str(programme.tricycle.id),
                'zone_id': str(programme.zone.id),
                'jour_semaine': programme.jour_semaine,
                'heure_debut': programme.heure_debut.strftime('%H:%M'),
                'heure_fin': programme.heure_fin.strftime('%H:%M'),
                'capacite_max_clients': programme.capacite_max_clients,
                'clients_actuels': programme.clients_actuels,
                'is_active': programme.is_active,
                'date_debut': programme.date_debut.strftime('%Y-%m-%d') if programme.date_debut else None,
                'date_fin': programme.date_fin.strftime('%Y-%m-%d') if programme.date_fin else None
            }
            
            return JsonResponse(programme_data, status=200)
            
        except ProgrammeTricycle.DoesNotExist:
            return JsonResponse({'error': 'Programme non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def put(self, request, pk):
        """Mettre à jour un programme - déclenche la mise à jour des abonnements"""
        try:
            with transaction.atomic():
                programme = ProgrammeTricycle.objects.select_related('zone').get(id=pk)
                data = json.loads(request.body)
                
                # Sauvegarder l'ancien état pour détecter les changements
                old_capacity = programme.capacite_max_clients
                old_is_active = programme.is_active
                
                # Mise à jour des champs
                if 'tricycle' in data:
                    try:
                        tricycle = Tricycle.objects.get(id=data['tricycle'])
                        programme.tricycle = tricycle
                    except Tricycle.DoesNotExist:
                        return JsonResponse({'tricycle': ['Tricycle non trouvé']}, status=400)
                
                if 'zone' in data:
                    try:
                        zone = Zone.objects.get(id=data['zone'])
                        programme.zone = zone
                    except Zone.DoesNotExist:
                        return JsonResponse({'zone': ['Zone non trouvée']}, status=400)
                
                if 'jour_semaine' in data:
                    programme.jour_semaine = data['jour_semaine']
                if 'heure_debut' in data:
                    programme.heure_debut = data['heure_debut']
                if 'heure_fin' in data:
                    programme.heure_fin = data['heure_fin']
                if 'capacite_max_clients' in data:
                    programme.capacite_max_clients = data['capacite_max_clients']
                if 'is_active' in data:
                    programme.is_active = data['is_active']
                if 'date_debut' in data:
                    programme.date_debut = data['date_debut']
                if 'date_fin' in data:
                    programme.date_fin = data['date_fin']
                
                programme.save()
                # Récupérer tous les abonnement liés à ce programme
                subscription = Subscription.objects.filter(
                    zone=programme.zone,  
                    )
                
                
                client = len(subscription)
                
                if programme.clients_actuels > client:
                    programme.clients_actuels = client
                    programme.save()
                if programme.clients_actuels > programme.capacite_max_clients:
                    return JsonResponse({
                        'error': 'Le nombre actuel de clients ne peut pas dépasser la capacité maximale.'
                    }, status=400)



                print(f"Abonnements affectés trouvés: {len(subscription)}")
                if len(subscription) < 2:
                    subscription= subscription.first()
                    # supprimer les jours de collecte pour cette abonement s'il existe deja
                    day = SubscriptionDay.objects.filter(
                        subscription=subscription
                    )
                    if day.exists():
                        day.delete()
                    # Réassigner les jours de collecte pour cet abonnement
                    subscription.assigner_jours_collecte_automatique()
                    # recuperer les programe de collecte associer au abonnement et les suprimer
                    collecte= CollectionSchedule.objects.filter(
                    subscription=subscription,
                    
                    )   
                    if collecte.exists():
                        collecte.delete()
                    generate_collection_schedule(subscription)

                    
                else:
                    

                    for sub in subscription:
                         # supprimer les jours de collecte pour cette abonement s'il existe deja
                        
                        day = SubscriptionDay.objects.filter(
                            subscription=sub
                        )
                        if day.exists():
                            day.delete()
                        # Réassigner les jours de collecte pour cet abonnement
                        sub.assigner_jours_collecte_automatique()
                        # recuperer les programe de collecte associer au abonnement et les suprimer
                        collecte= CollectionSchedule.objects.filter(
                        subscription=sub,
                        
                        ) 
                        if collecte.exists():
                            collecte.delete()

                        # Génération du planning de collecte
                        generate_collection_schedule(sub)
                 
                
                return JsonResponse({
                    'message': 'Programme mis à jour avec succès. Les abonnements concernés seront mis à jour.',
                    'id': str(programme.id)
                }, status=200)
                
        except ProgrammeTricycle.DoesNotExist:
            return JsonResponse({'error': 'Programme non trouvé'}, status=404)
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            print(f"Erreur lors de la mise à jour du programme: {e}")
            return JsonResponse({'error': str(e)}, status=500)
    
    def update_affected_subscriptions(self, programme):
        """Mettre à jour les abonnements affectés par un changement de programme"""
        try:
            # Récupérer tous les abonnement liés à ce programme
            subscription = Subscription.objects.filter(
                zone=programme.zone,
                
            )

            print(f"Abonnements affectés trouvés: {len(subscription)}")
            
            for sub_day in subscription:
                # Réassigner les jours de collecte pour cet abonnement
                sub_day.assigner_jours_collecte_automatique()
                # recuperer les programe de collecte associer au abonnement et les suprimer
                collecte= CollectionSchedule.objects.filter(
                    subscription=subscription,
                    is_active=True
                ) 
                if collecte.exists():
                    collecte.delete()

                # Génération du planning de collecte
                generate_collection_schedule(subscription)

                
            return len(subscription)
            
        except Exception as e:
            print(f"Erreur lors de la mise à jour des abonnements: {e}")
            return 0
    
    def delete(self, request, pk):
        """Supprimer un programme"""
        try:
            programme = ProgrammeTricycle.objects.get(id=pk)
            
            # Vérifier s'il y a des jours d'abonnement associés
            if programme.jours_abonnement.exists():
                return JsonResponse({
                    'error': 'Impossible de supprimer ce programme car il a des abonnements associés'
                }, status=400)
            
            programme.delete()
            
            return JsonResponse({'message': 'Programme supprimé avec succès'}, status=200)
            
        except ProgrammeTricycle.DoesNotExist:
            return JsonResponse({'error': 'Programme non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# API Views pour les Jours de Collecte
class CollectionDayListCreateAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        """Récupérer tous les jours de collecte"""
        try:
            days = CollectionDay.objects.all().order_by('order')
            
            days_data = []
            for day in days:
                days_data.append({
                    'id': day.id,
                    'name': day.name,
                    'name_display': day.get_name_display(),
                    'order': day.order
                })
            
            return JsonResponse(days_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request):
        """Créer un nouveau jour de collecte"""
        try:
            data = json.loads(request.body)
            
            if not data.get('name'):
                return JsonResponse({'name': ['Le nom du jour est obligatoire']}, status=400)
            
            # Vérifier l'unicité
            if CollectionDay.objects.filter(name=data['name']).exists():
                return JsonResponse({'name': ['Ce jour existe déjà']}, status=400)
            
            day = CollectionDay.objects.create(
                name=data['name'],
                order=data.get('order', 0)
            )
            
            return JsonResponse({
                'id': day.id,
                'message': 'Jour de collecte créé avec succès'
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Données JSON invalides'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class CollectionDayRetrieveUpdateDestroyAPIView(View):
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def put(self, request, pk):
        """Mettre à jour un jour de collecte"""
        try:
            day = CollectionDay.objects.get(id=pk)
            data = json.loads(request.body)
            
            if 'name' in data and data['name'] != day.name:
                if CollectionDay.objects.filter(name=data['name']).exclude(id=pk).exists():
                    return JsonResponse({'name': ['Ce jour existe déjà']}, status=400)
                day.name = data['name']
            
            if 'order' in data:
                day.order = data['order']
            
            day.save()
            
            return JsonResponse({'message': 'Jour de collecte mis à jour avec succès'}, status=200)
            
        except CollectionDay.DoesNotExist:
            return JsonResponse({'error': 'Jour de collecte non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def delete(self, request, pk):
        """Supprimer un jour de collecte"""
        try:
            day = CollectionDay.objects.get(id=pk)
            
            # Vérifier s'il est utilisé dans des abonnements
            if day.subscriptionday_set.exists():
                return JsonResponse({
                    'error': 'Impossible de supprimer ce jour car il est utilisé dans des abonnements'
                }, status=400)
            
            day.delete()
            
            return JsonResponse({'message': 'Jour de collecte supprimé avec succès'}, status=200)
            
        except CollectionDay.DoesNotExist:
            return JsonResponse({'error': 'Jour de collecte non trouvé'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# API Views pour les données de formulaire
class CityListAPIView(View):
    def get(self, request):
        """Récupérer toutes les villes"""
        try:
            cities = City.objects.all().order_by('city')
            
            cities_data = []
            for city in cities:
                cities_data.append({
                    'id': city.id,
                    'city': city.city,
                    'country': city.country,
                    'region': city.region
                })
            
            return JsonResponse(cities_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class CollectorListAPIView(View):
    def get(self, request):
        """Récupérer tous les collecteurs"""
        try:
            collectors = CustomUser.objects.filter(
                user_type='collecteur',
                is_active=True
            ).order_by('first_name', 'last_name')
            
            collectors_data = []
            for collector in collectors:
                collectors_data.append({
                    'id': collector.id,
                    'name': f"{collector.first_name} {collector.last_name}".strip() or collector.username,
                    'phone': collector.phone,
                    'email': collector.email
                })
            
            return JsonResponse(collectors_data, safe=False, status=200)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)