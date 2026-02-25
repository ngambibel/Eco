from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Q, Sum, Avg
from django.http import JsonResponse
from datetime import datetime, timedelta, date
import json

from .models import (
    CustomUser, CollectionRequest, Subscription, Tricycle, 
    Zone, ProgrammeTricycle, Notification, Payment, CollectionSchedule, Performence
)

# Decorator pour vérifier que l'utilisateur est un collecteur
def collector_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        if request.user.user_type != 'collecteur':
            messages.error(request, "Accès réservé aux collecteurs.")
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

@login_required(login_url='login')
@collector_required
def collector_dashboard(request):
    """Vue pour le tableau de bord du collecteur"""
    today = timezone.now().date()

    
        
    
    # Récupérer le tricycle du collecteur
    try:
        tricycle = Tricycle.objects.get(conducteur=request.user)

    except Tricycle.DoesNotExist:
        tricycle = None

    # creer la performance du collecteur pour ce jour
    note = Performence.objects.filter(Tricycle=tricycle, date=today).first()
    if not note:
        performance = Performence.objects.create(Tricycle=tricycle, note=0)
    else:
        performance = Performence.objects.get(Tricycle=tricycle, date=today)

    # recuperation des programmes de collecte associes au tricycle
    programmes = ProgrammeTricycle.objects.filter(tricycle=tricycle)
    # recupération des zones associées aux programmes
    zones = Zone.objects.filter(programmes_tricycle__in=programmes).distinct()
    # recupération des abonnements actifs dans ces zones
    active_subscriptions = Subscription.objects.filter(
        zone__in=zones,
        status='active'
    ).distinct()
    # recupération des programe collectes prévues pour aujourd'hui
    today_collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date=today,
        status__in=['completed', 'scheduled']
    ).order_by('scheduled_time')    
    # Statistiques du jour
    
    
    today_stats = {
        'total': today_collections.count(),
        'completed': today_collections.filter(status='completed').count(),
        'pending': today_collections.filter(status__in=['pending', 'scheduled']).count(),
        'in_progress': today_collections.filter(status='in_progress').count(),
    }
    
    # Statistiques de la semaine
    week_start = today 
    week_end = week_start + timedelta(days=6)
    
    week_collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date__range=[week_start, week_end],
        status__in=['completed', 'scheduled']
    ).order_by('scheduled_time')
    
    week_completed = week_collections.filter(status='completed').count()
    week_total = week_collections.count()
    week_stats = {
        'total': week_total,
        'completion_rate': round((week_completed / week_total * 100) if week_total > 0 else 0, 1)
    }
    
    # Collectes à venir (prochaines 4 heures)
    next_4_hours = timezone.now() + timedelta(hours=4)
    upcoming_collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date=today,
        scheduled_time__gte=timezone.now().time(),
        status__in=['pending', 'scheduled']
    ).order_by('scheduled_time')[:5]
    
    # Clients actifs et zones
    active_subscriptions = Subscription.objects.filter(
        status='active'
    ).distinct()
    
    active_clients_count = active_subscriptions.values('user').distinct().count()
    active_zones_count = active_subscriptions.values('zone').distinct().count()
    
    # Performance du collecteur (calcul simplifié)
    total_collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date=today,
        status__in=['completed', 'scheduled']
    ).order_by('scheduled_time')
    completed_collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date=today,
        status='completed'
    ).order_by('scheduled_time')
    
    # calcul de la performence journaliere du conducteur
    if len(total_collections) > 0:
        dif = len(total_collections)/len(completed_collections) if len(completed_collections) > 0 else 0
        performance_rating= 5*dif 
    else:
        performance_rating = 0

    # modifier la note de la performance
    performance.note=performance_rating 
    performance.save()

    
    
   
    
    # Notifications non lues
    unread_notifications_count = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).count()
    
    # Notifications récentes
    recent_notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    context = {
        'tricycle': tricycle,
        'today_stats': today_stats,
        'week_stats': week_stats,
        'upcoming_collections': upcoming_collections,
        'active_clients_count': active_clients_count,
        'active_zones_count': active_zones_count,
        'performance_rating': performance_rating,
        'unread_notifications_count': unread_notifications_count,
        'recent_notifications': recent_notifications,
        'today_collections_count': today_stats['pending'] + today_stats['in_progress'],
    }
    
    return render(request, 'collectors/dashboard.html', context)

@login_required(login_url='login')
@collector_required
def daily_schedule(request):
    """Vue pour le programme de collecte du jour"""
    # Gérer la date (aujourd'hui par défaut ou date spécifiée)
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_date = timezone.now().date()
    else:
        current_date = timezone.now().date()
    
    # Calcul des dates précédente et suivante
    prev_date = current_date - timedelta(days=1)
    next_date = current_date + timedelta(days=1)

    # recuperer le tricycle du collecteur
    try:
        tricycle = Tricycle.objects.get(conducteur=request.user)
    except Tricycle.DoesNotExist:
        tricycle = None
    
    # recupereration des programmes de collecte associes au tricycle
    programmes = ProgrammeTricycle.objects.filter(tricycle=tricycle)
    # recupération des zones associées aux programmes
    zones = Zone.objects.filter(programmes_tricycle__in=programmes).distinct()
    # recupération des abonnements actifs dans ces zones
    active_subscriptions = Subscription.objects.filter(
        zone__in=zones,
        status='active'
    ).distinct()
    print("Active Subscriptions:", active_subscriptions)
    print("zones:", zones)

    
    # Récupérer les collectes du jour
    collections = CollectionSchedule.objects.filter(
        subscription__in=active_subscriptions,
        scheduled_date=current_date,
        status__in=['completed', 'scheduled']
    ).order_by('scheduled_time')

    print("Collections:", collections)
    
    # Statistiques du jour
    daily_stats = {
        'total': collections.count(),
        'completed': collections.filter(status='completed').count(),
        'in_progress': collections.filter(status='in_progress').count(),
        'pending': collections.filter(status__in=['pending', 'scheduled']).count(),
    }
    
    # Calcul du taux d'accomplissement
    if daily_stats['total'] > 0:
        daily_stats['completion_rate'] = round(
            (daily_stats['completed'] / daily_stats['total']) * 100, 1
        )
    else:
        daily_stats['completion_rate'] = 0
    
    
    
    
    # Instructions spéciales pour aujourd'hui
    special_instructions = CollectionRequest.objects.filter(
        collector=request.user,
        scheduled_date=current_date,
        subscription__special_instructions__isnull=False
    ).exclude(subscription__special_instructions='')
    
    context = {
        'collections': collections,
        'current_date': current_date,
        'prev_date': prev_date,
        'next_date': next_date,
        'daily_stats': daily_stats,
        'zones': zones,
        'special_instructions': special_instructions,
    }
    
    return render(request, 'collectors/daily_schedule.html', context)



# api de calcul de distance entre le collecteur et le client pour la collecte efficasse
import json
import requests
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from geopy.distance import geodesic
from math import radians, sin, cos, sqrt, atan2

@login_required(login_url='login')
@collector_required
@require_GET
def get_sorted_collections_by_distance(request):
    """
    API endpoint qui retourne les collectes triées par distance 
    par rapport à la position actuelle du collecteur
    """
    # Récupérer la latitude et longitude de l'utilisateur depuis la requête
    user_lat = request.GET.get('lat')
    user_lon = request.GET.get('lon')
    
    # Récupérer la date (aujourd'hui par défaut)
    date_str = request.GET.get('date')
    if date_str:
        try:
            current_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            current_date = timezone.now().date()
    else:
        current_date = timezone.now().date()
    
    if not user_lat or not user_lon:
        return JsonResponse({
            'success': False,
            'error': 'Position de l\'utilisateur non fournie'
        }, status=400)
    
    try:
        user_lat = float(user_lat)
        user_lon = float(user_lon)
        
        # Récupérer le tricycle du collecteur
        try:
            tricycle = Tricycle.objects.get(conducteur=request.user)
        except Tricycle.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Aucun tricycle assigné'
            }, status=404)
        
        # Récupérer les programmes de collecte
        programmes = ProgrammeTricycle.objects.filter(tricycle=tricycle)
        zones = Zone.objects.filter(programmes_tricycle__in=programmes).distinct()
        
        # Récupérer les abonnements actifs
        active_subscriptions = Subscription.objects.filter(
            zone__in=zones,
            status='active'
        ).distinct()
        
        # Récupérer les collectes du jour
        collections = CollectionSchedule.objects.filter(
            subscription__in=active_subscriptions,
            scheduled_date=current_date,
            status__in=['scheduled', 'pending']
        ).select_related(
            'subscription__user',
            'subscription__address',
            'subscription__plan'
        )
        
        # Préparer les données avec calcul des distances
        collections_with_distance = []
        
        for collection in collections:
            address = collection.subscription.address
            
            # Si l'adresse n'a pas de coordonnées, essayer de les géocoder
            if not address.latitude or not address.longitude:
                lat, lon = geocode_address(address)
                if lat and lon:
                    address.latitude = lat
                    address.longitude = lon
                    address.save()
            
            # Calculer la distance si les coordonnées sont disponibles
            if address.latitude and address.longitude:
                # Calculer la distance en kilomètres
                distance = calculate_distance(
                    user_lat, user_lon,
                    float(address.latitude), float(address.longitude)
                )
                
                # Optionnel: utiliser OSRM pour un calcul plus précis (temps de trajet)
                route_info = get_route_info_osrm(
                    user_lat, user_lon,
                    float(address.latitude), float(address.longitude)
                )
                
                collections_with_distance.append({
                    'id': str(collection.id),
                    'subscription_id': str(collection.subscription.id),
                    'client_name': collection.subscription.user.get_full_name() or collection.subscription.user.username,
                    'client_phone': str(collection.subscription.user.phone) if collection.subscription.user.phone else '',
                    'address': {
                        'street': address.street,
                        'city': address.city,
                        'postal_code': address.postal_code,
                        'latitude': float(address.latitude),
                        'longitude': float(address.longitude),
                    },
                    'plan_name': collection.subscription.plan.name,
                    'scheduled_time': collection.scheduled_time.strftime('%H:%M'),
                    'scheduled_date': collection.scheduled_date.strftime('%Y-%m-%d'),
                    'status': collection.status,
                    'status_display': collection.get_status_display(),
                    'distance_km': round(distance, 2),
                    'distance_text': format_distance(distance),
                    'duration_text': route_info.get('duration_text', 'N/A'),
                    'route_distance_text': route_info.get('distance_text', 'N/A'),
                    'special_instructions': collection.subscription.special_instructions,
                    'zone_name': collection.subscription.zone.nom if collection.subscription.zone else 'N/A',
                })
        
        # Trier par distance (plus proche au plus éloigné)
        collections_with_distance.sort(key=lambda x: x['distance_km'])
        
        # Ajouter le rang
        for idx, item in enumerate(collections_with_distance, 1):
            item['rank'] = idx
        
        # Statistiques
        stats = {
            'total': len(collections_with_distance),
            'closest': collections_with_distance[0]['client_name'] if collections_with_distance else None,
            'closest_distance': collections_with_distance[0]['distance_km'] if collections_with_distance else None,
            'farthest': collections_with_distance[-1]['client_name'] if collections_with_distance else None,
            'farthest_distance': collections_with_distance[-1]['distance_km'] if collections_with_distance else None,
        }
        
        return JsonResponse({
            'success': True,
            'collections': collections_with_distance,
            'stats': stats,
            'user_position': {
                'lat': user_lat,
                'lon': user_lon
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

def geocode_address(address):
    """
    Géocoder une adresse avec Nominatim (OpenStreetMap)
    """
    try:
        # Construire l'adresse complète
        full_address = f"{address.street}, {address.postal_code} {address.city}, {address.country}"
        
        # Appel à l'API Nominatim
        url = "https://nominatim.openstreetmap.org/search"
        params = {
            'q': full_address,
            'format': 'json',
            'limit': 1
        }
        
        # Important: ajouter un User-Agent pour respecter les conditions d'utilisation
        headers = {
            'User-Agent': 'WasteCollectionApp/1.0'
        }
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            if data:
                lat = float(data[0]['lat'])
                lon = float(data[0]['lon'])
                return lat, lon
    except Exception as e:
        print(f"Erreur de géocodage: {e}")
    
    return None, None

def get_route_info_osrm(lat1, lon1, lat2, lon2):
    """
    Obtenir des informations de routage avec OSRM
    """
    try:
        # Utiliser le serveur OSRM public
        url = f"http://router.project-osrm.org/route/v1/driving/{lon1},{lat1};{lon2},{lat2}"
        params = {
            'overview': 'false',
            'alternatives': 'false',
            'steps': 'false'
        }
        
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            if data['code'] == 'Ok' and data['routes']:
                route = data['routes'][0]
                duration = route['duration']  # en secondes
                distance = route['distance']  # en mètres
                
                return {
                    'duration': duration,
                    'duration_text': format_duration(duration),
                    'distance': distance,
                    'distance_text': format_distance(distance / 1000)  # convertir en km
                }
    except Exception as e:
        print(f"Erreur OSRM: {e}")
    
    return {
        'duration': None,
        'duration_text': 'N/A',
        'distance': None,
        'distance_text': 'N/A'
    }

def calculate_distance(lat1, lon1, lat2, lon2):
    """
    Calculer la distance entre deux points (formule de Haversine)
    """
    R = 6371  # Rayon de la Terre en kilomètres
    
    lat1_rad = radians(lat1)
    lat2_rad = radians(lat2)
    delta_lat = radians(lat2 - lat1)
    delta_lon = radians(lon2 - lon1)
    
    a = sin(delta_lat/2)**2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon/2)**2
    c = 2 * atan2(sqrt(a), sqrt(1-a))
    
    return R * c

def format_distance(km):
    """
    Formater la distance de manière lisible
    """
    if km < 1:
        return f"{int(km * 1000)} m"
    elif km < 10:
        return f"{km:.1f} km"
    else:
        return f"{int(km)} km"

def format_duration(seconds):
    """
    Formater la durée de manière lisible
    """
    if seconds < 60:
        return f"{int(seconds)} sec"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} min"
    else:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h{minutes:02d}"






@login_required(login_url='login')
@collector_required
def weekly_schedule(request):
    """Vue pour le programme de la semaine"""
    today = timezone.now().date()
    week_start = today - timedelta(days=today.weekday())
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    
    # Récupérer les collectes de la semaine
    weekly_collections = CollectionRequest.objects.filter(
        collector=request.user,
        scheduled_date__range=[week_start, week_start + timedelta(days=6)]
    ).order_by('scheduled_date', 'scheduled_time')
    
    # Organiser par jour
    collections_by_day = {}
    for day in week_dates:
        day_collections = weekly_collections.filter(scheduled_date=day)
        collections_by_day[day] = day_collections
    
    # Statistiques de la semaine
    week_stats = {
        'total': weekly_collections.count(),
        'completed': weekly_collections.filter(status='completed').count(),
        'scheduled': weekly_collections.filter(status='scheduled').count(),
        'in_progress': weekly_collections.filter(status='in_progress').count(),
    }
    
    context = {
        'week_dates': week_dates,
        'collections_by_day': collections_by_day,
        'week_start': week_start,
        'week_stats': week_stats,
    }
    
    return render(request, 'collectors/weekly_schedule.html', context)

@login_required(login_url='login')
@collector_required
def process_collection(request, collection_id):
    """Vue pour traiter une collecte spécifique"""
    collection = get_object_or_404(
        CollectionRequest, 
        id=collection_id, 
        collector=request.user
    )
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'start' and collection.status in ['pending', 'scheduled']:
            # Démarrer la collecte
            collection.status = 'in_progress'
            collection.actual_collection_time = timezone.now()
            collection.save()
            
            # Créer une notification
            Notification.create_notification(
                user=collection.subscription.user,
                title="Collecte en cours",
                message=f"Votre collecte a été démarrée par le collecteur {request.user.get_full_name()}",
                notification_type='collection',
                related_object=collection,
                action_url=f'/collections/{collection.id}/'
            )
            
            messages.success(request, "Collecte démarrée avec succès.")
            return redirect('daily_schedule')
            
        elif action == 'complete' and collection.status == 'in_progress':
            # Terminer la collecte
            collection.status = 'completed'
            collection.notes = request.POST.get('notes', '')
            collection.save()
            
            # Créer une notification
            Notification.create_notification(
                user=collection.subscription.user,
                title="Collecte terminée",
                message=f"Votre collecte a été effectuée avec succès",
                notification_type='success',
                related_object=collection,
                action_url=f'/collections/{collection.id}/'
            )
            
            messages.success(request, "Collecte terminée avec succès.")
            return redirect('daily_schedule')
    
    # Récupérer les collectes récentes pour ce client
    recent_collections = CollectionRequest.objects.filter(
        subscription=collection.subscription
    ).exclude(id=collection.id).order_by('-scheduled_date')[:5]
    
    context = {
        'collection': collection,
        'recent_collections': recent_collections,
    }
    
    return render(request, 'collectors/collection_form.html', context)

@login_required(login_url='login')
@collector_required
def complete_collection(request):
    """Vue pour terminer une collecte (version simplifiée)"""
    collection_id = request.GET.get('collection_id')
    collection = get_object_or_404(
        CollectionSchedule, 
        id=collection_id, 
        
    )
    collection.status = 'completed'
    collection.save()

    
    if request.method == 'POST':
        collection.status = 'completed'
        collection.notes = request.POST.get('notes', '')
        collection.save()
        
        messages.success(request, "Collecte marquée comme terminée.")
        return redirect('daily_schedule')
    
    context = {
        'collection': collection,
    }
    
    return render(request, 'collectors/daily_schedule.html', context)

@login_required(login_url='login')
@collector_required
def collection_details(request):
    """Vue pour voir les détails d'une collecte"""
    collection_id = request.GET.get('collection_id')
    collection = get_object_or_404(
        CollectionSchedule, 
        id=collection_id, 
    )

    # recuperer l'adresse du client
    sub = collection.subscription
    adress = sub.address


    
    context = {
        'collection': collection,
        'address': adress,
    }
    
    return render(request, 'collectors/collection_details.html', context)

@login_required(login_url='login')
@collector_required
def collector_tricycle(request):
    """Vue pour les informations du tricycle"""
    try:
        tricycle = Tricycle.objects.get(conducteur=request.user)
        
        # Statistiques d'utilisation
        today = timezone.now().date()
        
        total_collections = CollectionRequest.objects.filter(
            collector=request.user,
            status='completed'
        ).count()
        
        monthly_collections = CollectionRequest.objects.filter(
            collector=request.user,
            status='completed',
            scheduled_date__month=today.month,
            scheduled_date__year=today.year
        ).count()
        
        weekly_collections = CollectionRequest.objects.filter(
            collector=request.user,
            status='completed',
            scheduled_date__week=today.isocalendar()[1],
            scheduled_date__year=today.year
        ).count()
        
        daily_collections = CollectionRequest.objects.filter(
            collector=request.user,
            status='completed',
            scheduled_date=today
        ).count()
        
        # Performance du tricycle (calcul simplifié)
        performance = {
            'uptime': 95,  # Pourcentage de disponibilité
            'utilization': 78,  # Pourcentage d'utilisation
            'efficiency': 88,  # Efficacité
        }
        
    except Tricycle.DoesNotExist:
        tricycle = None
        total_collections = 0
        monthly_collections = 0
        weekly_collections = 0
        daily_collections = 0
        performance = {'uptime': 0, 'utilization': 0, 'efficiency': 0}
    
    context = {
        'tricycle': tricycle,
        'total_collections': total_collections,
        'monthly_collections': monthly_collections,
        'weekly_collections': weekly_collections,
        'daily_collections': daily_collections,
        'performance': performance,
    }
    
    return render(request, 'collectors/tricycle_info.html', context)

@login_required(login_url='login')
@collector_required
def collector_profile(request):
    """Vue pour le profil du collecteur"""
    user = request.user
    
    # Statistiques du collecteur
    today = timezone.now().date()
    
    total_collections = CollectionRequest.objects.filter(
        collector=user,
        status='completed'
    ).count()
    
    monthly_collections = CollectionRequest.objects.filter(
        collector=user,
        status='completed',
        scheduled_date__month=today.month,
        scheduled_date__year=today.year
    ).count()
    
    weekly_collections = CollectionRequest.objects.filter(
        collector=user,
        status='completed',
        scheduled_date__week=today.isocalendar()[1],
        scheduled_date__year=today.year
    ).count()
    
    # Calcul des métriques de performance
    all_collections = CollectionRequest.objects.filter(collector=user)
    completed_count = all_collections.filter(status='completed').count()
    total_count = all_collections.count()
    
    completion_rate = round((completed_count / total_count * 100) if total_count > 0 else 0, 1)
    avg_daily_collections = round(total_collections / 30, 1) if total_collections > 0 else 0  # Sur 30 jours
    
    # Autres métriques
    months_active = max(1, (timezone.now().date() - user.date_joined.date()).days // 30)
    performance_rating = 4.5  # À calculer selon votre logique
    monthly_performance = 85  # Pourcentage
    customer_satisfaction = 92  # Pourcentage
    
    # Villes disponibles pour le formulaire
    from .models import City
    cities = City.objects.all()
    
    context = {
        'user': user,
        'total_collections': total_collections,
        'monthly_collections': monthly_collections,
        'weekly_collections': weekly_collections,
        'completion_rate': completion_rate,
        'avg_daily_collections': avg_daily_collections,
        'months_active': months_active,
        'performance_rating': performance_rating,
        'monthly_performance': monthly_performance,
        'customer_satisfaction': customer_satisfaction,
        'cities': cities,
    }
    
    return render(request, 'collectors/profile.html', context)

@login_required(login_url='login')
@collector_required
def collection_history(request):
    """Vue pour l'historique des collectes"""
    # Filtres
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    # Base queryset
    collections = CollectionRequest.objects.filter(collector=request.user)
    
    # Appliquer les filtres
    if status_filter:
        collections = collections.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            collections = collections.filter(scheduled_date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            collections = collections.filter(scheduled_date__lte=date_to_obj)
        except ValueError:
            pass
    
    # Ordonner par date
    collections = collections.order_by('-scheduled_date', '-scheduled_time')
    
    # Pagination (simplifiée)
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1
    
    items_per_page = 20
    start_idx = (page - 1) * items_per_page
    end_idx = start_idx + items_per_page
    
    paginated_collections = collections[start_idx:end_idx]
    
    # Statistiques pour les filtres
    total_collections = collections.count()
    status_counts = CollectionRequest.objects.filter(
        collector=request.user
    ).values('status').annotate(count=Count('id'))
    
    context = {
        'collections': paginated_collections,
        'total_collections': total_collections,
        'status_counts': status_counts,
        'current_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'current_page': page,
        'has_next': end_idx < total_collections,
        'has_previous': page > 1,
    }
    
    return render(request, 'collectors/collection_history.html', context)

@login_required(login_url='login')
@collector_required
def update_profile(request):
    """Vue pour mettre à jour le profil"""
    if request.method == 'POST':
        user = request.user
        
        # Mettre à jour les informations de base
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.phone = request.POST.get('phone', '') or None
        
        # Mettre à jour la ville
        city_id = request.POST.get('city')
        if city_id:
            from .models import City
            try:
                city = City.objects.get(id=city_id)
                user.city = city
            except City.DoesNotExist:
                pass
        
        user.save()
        
        messages.success(request, "Profil mis à jour avec succès.")
        return redirect('collector_profile')
    
    messages.error(request, "Méthode non autorisée.")
    return redirect('collector_profile')

@login_required(login_url='login')
@collector_required
def change_password(request):
    """Vue pour changer le mot de passe"""
    if request.method == 'POST':
        user = request.user
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Vérifier le mot de passe actuel
        if not user.check_password(current_password):
            messages.error(request, "Le mot de passe actuel est incorrect.")
            return redirect('collector_profile')
        
        # Vérifier que les nouveaux mots de passe correspondent
        if new_password != confirm_password:
            messages.error(request, "Les nouveaux mots de passe ne correspondent pas.")
            return redirect('collector_profile')
        
        # Vérifier la force du mot de passe
        if len(new_password) < 8:
            messages.error(request, "Le mot de passe doit contenir au moins 8 caractères.")
            return redirect('collector_profile')
        
        # Changer le mot de passe
        user.set_password(new_password)
        user.save()
        
        # Mettre à jour la session pour éviter la déconnexion
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        
        messages.success(request, "Mot de passe changé avec succès.")
        return redirect('collector_profile')
    
    messages.error(request, "Méthode non autorisée.")
    return redirect('collector_profile')

@login_required(login_url='login')
@collector_required
def update_preferences(request):
    """Vue pour mettre à jour les préférences"""
    if request.method == 'POST':
        # Ici, vous pouvez sauvegarder les préférences dans le modèle User
        # ou dans un modèle de préférences séparé
        
        # Exemple de sauvegarde simplifiée
        language = request.POST.get('language', 'fr')
        timezone = request.POST.get('timezone', 'UTC+1')
        theme = request.POST.get('theme', 'light')
        
        # Sauvegarder dans la session (temporaire)
        request.session['user_language'] = language
        request.session['user_timezone'] = timezone
        request.session['user_theme'] = theme
        
        messages.success(request, "Préférences mises à jour avec succès.")
        return redirect('collector_profile')
    
    messages.error(request, "Méthode non autorisée.")
    return redirect('collector_profile')

# Vues API pour AJAX
@login_required(login_url='login')
@collector_required
def api_collection_stats(request):
    """API pour les statistiques des collectes (AJAX)"""
    today = timezone.now().date()
    
    # Statistiques du jour
    today_stats = CollectionRequest.objects.filter(
        collector=request.user,
        scheduled_date=today
    ).aggregate(
        total=Count('id'),
        completed=Count('id', filter=Q(status='completed')),
        in_progress=Count('id', filter=Q(status='in_progress')),
        pending=Count('id', filter=Q(status__in=['pending', 'scheduled']))
    )
    
    return JsonResponse({
        'today': today_stats,
        'timestamp': timezone.now().isoformat()
    })

@login_required(login_url='login')
@collector_required
def api_start_collection(request, collection_id):
    """API pour démarrer une collecte (AJAX)"""
    if request.method == 'POST':
        collection = get_object_or_404(
            CollectionRequest, 
            id=collection_id, 
            collector=request.user
        )
        
        if collection.status in ['pending', 'scheduled']:
            collection.status = 'in_progress'
            collection.actual_collection_time = timezone.now()
            collection.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Collecte démarrée avec succès',
                'new_status': 'in_progress'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Statut de collecte invalide'
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)

@login_required(login_url='login')
@collector_required
def api_complete_collection(request, collection_id):
    """API pour terminer une collecte (AJAX)"""
    if request.method == 'POST':
        collection = get_object_or_404(
            CollectionRequest, 
            id=collection_id, 
            collector=request.user
        )
        
        if collection.status == 'in_progress':
            collection.status = 'completed'
            collection.notes = request.POST.get('notes', '')
            collection.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Collecte terminée avec succès',
                'new_status': 'completed'
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'La collecte doit être en cours pour être terminée'
            }, status=400)
    
    return JsonResponse({'success': False, 'message': 'Méthode non autorisée'}, status=405)