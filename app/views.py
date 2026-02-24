from django.shortcuts import render
from django.views.decorators.http import require_POST
# Create your views here.
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm, CustomAuthenticationForm
from .models import CustomUser as User
import re
from .models import *
import json
import math
from datetime import datetime, timedelta
from django.views.generic import ListView
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django.utils import timezone
import json
import logging
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from datetime import timedelta
from django.db import transaction

from .models import Subscription, SubscriptionPlan, Zone, Address
from .services.payment import PaymentService

logger = logging.getLogger(__name__)


def signup_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')  # Ajouter le champ phone
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        errors = []
        
        # Validation des champs
        if not username or len(username) < 3:
            errors.append("Le nom d'utilisateur doit contenir au moins 3 caractères.")
        
        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            errors.append("Veuillez entrer une adresse email valide.")
        
        # Validation du numéro de téléphone
        if phone:
            if not re.match(r'^\d{9}$', phone):  # Adaptez la regex selon votre format
                errors.append("Le numéro de téléphone doit contenir 10 chiffres.")
            elif User.objects.filter(phone=phone).exists():
                errors.append("Ce numéro de téléphone est déjà utilisé.")
        
        if not password1 or len(password1) < 8:
            errors.append("Le mot de passe doit contenir au moins 8 caractères.")
        
        if password1 != password2:
            errors.append("Les mots de passe ne correspondent pas.")
        
        # Vérifier si l'utilisateur existe déjà
        if User.objects.filter(username=username).exists():
            errors.append("Ce nom d'utilisateur est déjà pris.")
        
        if User.objects.filter(email=email).exists():
            errors.append("Cette adresse email est déjà utilisée.")
        
        if not errors:
            try:
                # Créer l'utilisateur avec le modèle CustomUser
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password1,
                    phone=phone  # Sauvegarder le numéro de téléphone
                )
                user.save()
                
                # Connecter l'utilisateur
                login(request, user)
                messages.success(request, f"Bienvenue sur Ecocity, {user.username}!")
                return redirect('dashboard')
                
            except Exception as e:
                errors.append("Une erreur est survenue lors de la création du compte.")
        
        if errors:
            for error in errors:
                messages.error(request, error)
            # Retourner les données pour pré-remplir le formulaire
            return render(request, 'signup.html', {
                'username': username,
                'email': email,
                'phone': phone
            })
    
    return render(request, 'signup.html')

def login_view(request):
    if request.method == 'POST':
        username_or_phone = request.POST.get('username')
        password = request.POST.get('password')
        
        # Vérifier si l'input est un numéro de téléphone
        if username_or_phone and re.match(r'^\d+$', username_or_phone):
            # C'est un numéro de téléphone, chercher l'utilisateur par phone
            try:
                user = User.objects.filter(phone=username_or_phone).first()
                try:
                    username = user.username
                except AttributeError:
                    username = None
            except User.DoesNotExist:
                user = None
                username = username_or_phone
        else:
            # C'est un nom d'utilisateur
            username = username_or_phone
        
        loger = authenticate(request, username=username, password=password)
        
        if loger is not None:
            login(request, loger)
            messages.success(request, f"Content de vous revoir, {loger.username}!")

            if loger.user_type == 'collecteur':
                return redirect('collector_dashboard')
            if loger.user_type == 'admin':
                return redirect('admin_dashboard')
            
            return redirect('dashboard')
        else:
            messages.error(request, "Identifiants invalides.")
            return render(request, 'login.html', {
                'username': username_or_phone
            })
    
    return render(request, 'login.html')

def logout_view(request):
    logout(request)
    messages.success(request, "Vous avez été déconnecté avec succès.")
    return redirect('login')


def accueil(request):
    # Récupérer les annonces actives
    annonces = AnnonceCarousel.objects.filter(
        actif=True,
        date_debut__lte=timezone.now(),
        date_fin__gte=timezone.now()
    ).order_by('ordre', '-date_creation')
    
    context = {
        'annonces': annonces
    }
    
    return render(request, 'home.html', context)






@login_required(login_url='login')
def subscription_page(request):
    plans = SubscriptionPlan.objects.filter(is_active=True)
    zones = Zone.objects.filter(is_active=True).select_related('ville')
    
    context = {
        'plans': plans,
        'zones': zones,
    }
    return render(request, 'subscription.html', context)

@csrf_exempt
@require_http_methods(["POST"])
@login_required(login_url='login')
def create_subscription(request):
    try:
        data = json.loads(request.body)
        
        # Récupération des données du formulaire
        plan_id = data.get('plan_id')
        zone_id = data.get('zone_id')
        selected_days = data.get('selected_days', [])
        address_data = data.get('address', {})
        special_instructions = data.get('special_instructions', '')
        
        # Validation des données
        if not plan_id or not zone_id:
            return JsonResponse({'success': False, 'error': 'Plan et zone de collecte requis'})
        
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        zone = get_object_or_404(Zone, id=zone_id, is_active=True)
        
        # Création de l'adresse
        address = Address.objects.create(
            user=request.user,
            title=address_data.get('title', 'Adresse principale'),
            street=address_data.get('street', ''),
            city=address_data.get('city', ''),
            postal_code=address_data.get('postal_code', ''),
            country=address_data.get('country', 'Cameroun'),
            zone=zone,
            is_primary=True
        )

        

        
        # Création de l'abonnement
        subscription = Subscription.objects.create(
            user=request.user,
            address=address,
            plan=plan,
            special_instructions=special_instructions,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30)  # Abonnement d'un mois
        )
        
        
            
    

        # Assignation automatique des jours de collecte
        assigned_days = subscription.assigner_jours_collecte_automatique()
        generate_collection_schedule(subscription)

        
        
        return JsonResponse({
            'success': True,
            'subscription_id': str(subscription.id),
            'assigned_days': [str(day.day) for day in assigned_days],
            'message': 'Abonnement créé avec succès'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    

@csrf_exempt
@require_http_methods(["POST"])
@login_required(login_url='login')
def process_subscription_payment(request):
    """Process payment before creating subscription"""
    try:
        data = json.loads(request.body)
        
        # Récupération des données
        plan_id = data.get('plan_id')
        zone_id = data.get('zone_id')
        phone_number = data.get('phone_number')
        payment_method = data.get('payment_method')
        address_data = data.get('address', {})
        selected_days = data.get('selected_days', [])
        special_instructions = data.get('special_instructions', '')
        
        # Validation des données
        if not all([plan_id, zone_id, phone_number, payment_method]):
            return JsonResponse({
                'success': False, 
                'error': 'Tous les champs obligatoires doivent être remplis'
            })

        # Vérification du format du numéro
        if not phone_number.isdigit() or len(phone_number) != 9:
            return JsonResponse({
                'success': False,
                'error': 'Numéro de téléphone invalide. Format: 6XXXXXXX ou 2XXXXXXX'
            })
        
        from .models import SubscriptionPlan, Zone
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        zone = get_object_or_404(Zone, id=zone_id, is_active=True)

        address = Address.objects.create(
        user=request.user,
        title=address_data.get('title', 'Adresse principale'),
        street=address_data.get('street', ''),
        city=address_data.get('city', ''),
        postal_code=address_data.get('postal_code', ''),
        country=address_data.get('country', 'Cameroun'),
        zone=zone,
        latitude=address_data.get('latitude'),
        longitude=address_data.get('longitude'),
        is_primary=True
    )

        # Création de l'abonnement
        subscription = Subscription.objects.create(
        user=request.user,
        status='inactive',
        zone=zone,
        address=address,
        plan=plan,
        special_instructions=special_instructions,
        start_date=timezone.now().date(),
        end_date=timezone.now().date() + timedelta(days=30)  # Abonnement d'un mois
        
    )
        # Assignation automatique des jours de collecte
        assigned_days = subscription.assigner_jours_collecte_automatique()
           
        
        # Traitement du paiement
        
        payment_service = PaymentService()
        payment_result = payment_service.process_subscription_payment_first(
            user=request.user,
            amount= 10, #float(plan.price),  # Utiliser le prix réel du plan
            service_name=payment_method,
            phone_number=phone_number,
            subscription_data={
                'plan_name': plan.name,
                'zone_name': zone.nom
            },
            subscription=subscription
        )
        
        
        if not payment_result['success']:
            
            return JsonResponse({
                'success': False,
                'error': payment_result['message']
            })

        # Si le paiement est réussi, créer l'abonnement
        subscription = create_subscription_after_payment(
            subscription=subscription,
        )
        
        return JsonResponse({
            'success': True,
            'subscription_id': str(subscription.id),
            'transaction_id': payment_result.get('transaction_id'),
            'message': 'Paiement effectué et abonnement créé avec succès',
            'payment_reference': payment_result.get('reference')
        })
        
    except Exception as e:
        logger.error(f"Subscription payment error: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False, 
            'error': f'Erreur lors du traitement: {str(e)}'
        })

@transaction.atomic
def create_subscription_after_payment(subscription):
    """Create subscription after successful payment"""
    
    subscription.status = 'active'
    subscription.start_date = timezone.now().date()
    subscription.end_date = timezone.now().date() + timedelta(days=30)  # Abonnement d'un mois
    subscription.save()

    # Assignation automatique des jours de collecte
    
    
    # Génération du planning de collecte
    generate_collection_schedule(subscription)
    
    return subscription

def generate_collection_schedule(subscription):
    """Generate collection schedule for subscription"""
    from .models import CollectionSchedule, SubscriptionDay
    from datetime import datetime, timedelta
    
    # Récupérer les jours assignés
    subscription_days = SubscriptionDay.objects.filter(subscription=subscription, is_active=True)
    
    # Générer le planning pour les 4 prochaines semaines
    for i in range(4):  # 4 semaines
        for sub_day in subscription_days:
            scheduled_date = timezone.now().date() + timedelta(days=(i * 7 + get_day_offset(sub_day.day.name)))
            
            CollectionSchedule.objects.create(
                subscription=subscription,
                scheduled_date=scheduled_date,
                scheduled_day=sub_day.day,
                scheduled_time=sub_day.time_slot,
                status='scheduled'
            )

def get_day_offset(day_name):
    """Get day offset from current date"""
    days_mapping = {
        'lundi': 0,
        'mardi': 1,
        'mercredi': 2,
        'jeudi': 3,
        'vendredi': 4,
        'samedi': 5,
        'dimanche': 6
    }
    current_weekday = timezone.now().weekday()
    target_weekday = days_mapping.get(day_name, 0)
    
    # Calculer le décalage pour le prochain jour cible
    if target_weekday >= current_weekday:
        return target_weekday - current_weekday
    else:
        return 7 - current_weekday + target_weekday

@csrf_exempt
@require_http_methods(["POST"])
@login_required(login_url='login')
def verify_payment_status(request):
    """Verify payment status for a transaction"""
    try:
        data = json.loads(request.body)
        reference = data.get('reference')
        
        if not reference:
            return JsonResponse({
                'success': False,
                'error': 'Reference de transaction manquante'
            })
        
        from services.payment import PaymentService
        payment_service = PaymentService()
        status_result = payment_service.check_transaction_status(reference)
        
        return JsonResponse(status_result)
        
    except Exception as e:
        logger.error(f"Payment verification error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': str(e)
        })


def get_zone_schedule(request, zone_id):
    """API pour récupérer le programme d'une zone"""
    try:
        zone = get_object_or_404(Zone, id=zone_id)
        
        # Récupérer les programmes disponibles pour la zone
        programmes = ProgrammeTricycle.objects.filter(
            zone=zone,
            is_active=True
        ).select_related('tricycle')
        
        schedule = []
        for programme in programmes:
            if programme.peut_ajouter_client():
                schedule.append({
                    'jour': programme.jour_semaine,
                    'jour_display': programme.get_jour_semaine_display(),
                    'heure_debut': programme.heure_debut.strftime('%H:%M'),
                    'heure_fin': programme.heure_fin.strftime('%H:%M'),
                    'tricycle': programme.tricycle.nom,
                    'places_restantes': programme.places_disponibles()
                })
        
        return JsonResponse({
            'success': True,
            'zone': {
                'id': str(zone.id),
                'nom': zone.nom,
                'ville': zone.ville.city,
                'description': zone.description
            },
            'schedule': schedule
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



@login_required(login_url='login')
def get_subscription_schedule(request, subscription_id):
    """Récupère le programme de collecte d'un abonnement"""
    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)
    schedules = CollectionSchedule.objects.filter(subscription=subscription).order_by('scheduled_date')
    
    schedule_data = []
    for schedule in schedules:
        schedule_data.append({
            'date': schedule.scheduled_date.strftime('%d/%m/%Y'),
            'day': schedule.scheduled_day.get_name_display(),
            'time': schedule.scheduled_time.strftime('%H:%M'),
            'status': schedule.get_status_display(),
            'status_code': schedule.status
        })
    
    return JsonResponse({'schedules': schedule_data})




@login_required(login_url='login')
def subscriptions_dashboard(request):
    subscriptions = Subscription.objects.filter(
        user=request.user
    ).select_related('plan', 'address').prefetch_related('collection_days__day')
    
    # Prochaine collecte
    next_collection = CollectionRequest.objects.filter(
        subscription__user=request.user,
        scheduled_date__gte=timezone.now().date(),
        status__in=['pending', 'scheduled']
    ).select_related('subscription', 'subscription__address').first()
    
    context = {
        'subscriptions': subscriptions,
        'next_collection': next_collection,
        'active_subscriptions_count': subscriptions.filter(status='active').count(),
    }
    return render(request, 'subscriptions_dashboard.html', context)

@login_required(login_url='login')
def edit_subscription(request, subscription_id):
    subscription = get_object_or_404(
        Subscription, 
        id=subscription_id, 
        user=request.user
    )
    
    # Jours actuels de collecte
    current_days = [sd.day for sd in subscription.collection_days.all()]
    
    context = {
        'subscription': subscription,
        'days': CollectionDay.objects.all(),
        'current_days': current_days,
        'available_plans': SubscriptionPlan.objects.filter(is_active=True),
        'time_slots': ['08:00', '10:00', '14:00', '16:00'],
        'current_time_slot': subscription.collection_days.first().time_slot if subscription.collection_days.exists() else '08:00'
    }
    return render(request, 'edit_subscription.html', context)

from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
import json
from django.utils import timezone
from datetime import timedelta

@login_required(login_url='login')
def update_subscription(request, subscription_id):
    if request.method == 'POST':
        subscription = get_object_or_404(
            Subscription, 
            id=subscription_id, 
            user=request.user
        )
        
        try:
            # Récupérer toutes les données du formulaire
            address_title = request.POST.get('address_title')
            street = request.POST.get('street')
            city = request.POST.get('city')
            postal_code = request.POST.get('postal_code')
            latitude = request.POST.get('latitude')
            longitude = request.POST.get('longitude')
            selected_days = request.POST.get('selected_days')
            time_slot = request.POST.get('time_slot')
            new_plan_id = request.POST.get('new_plan_id')
            special_instructions = request.POST.get('special_instructions')
            
            # 1. Mise à jour de l'adresse
            if address_title and street and city and postal_code:
                subscription.address.title = address_title
                subscription.address.street = street
                subscription.address.city = city
                subscription.address.postal_code = postal_code
                if latitude and longitude:
                    subscription.address.latitude = latitude
                    subscription.address.longitude = longitude
                subscription.address.save()
            
            # 2. Mise à jour du plan si fourni
            if new_plan_id and new_plan_id != str(subscription.plan.id):
                new_plan = get_object_or_404(SubscriptionPlan, id=new_plan_id, is_active=True)
                subscription.plan = new_plan
            
            # 3. Mise à jour des instructions spéciales
            if special_instructions is not None:
                subscription.special_instructions = special_instructions
            
            subscription.updated_at = timezone.now()
            subscription.save()
            
            # 4. Mise à jour des jours de collecte
            if selected_days:
                try:
                    selected_days_list = json.loads(selected_days)
                    
                    # Supprimer les anciens jours
                    subscription.collection_days.all().delete()
                    
                    # Ajouter les nouveaux jours
                    for day_name in selected_days_list:
                        day = get_object_or_404(CollectionDay, name=day_name)
                        SubscriptionDay.objects.create(
                            subscription=subscription,
                            day=day,
                            time_slot=time_slot or '08:00'
                        )
                    
                    # Mettre à jour le programme de collecte
                    update_collection_schedule(subscription, selected_days_list, time_slot)
                    
                except json.JSONDecodeError as e:
                    return JsonResponse({
                        'success': False, 
                        'error': f'Erreur décodage JSON jours: {str(e)}'
                    })
            
            return JsonResponse({
                'success': True,
                'message': 'Abonnement modifié avec succès!'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False, 
                'error': f'Erreur lors de la modification: {str(e)}'
            }, status=400)
    
    return JsonResponse({
        'success': False, 
        'error': 'Méthode non autorisée'
    }, status=405)

def update_collection_schedule(subscription, new_days, time_slot):
    """
    Met à jour le programme de collecte en fonction des nouveaux jours
    """
    day_mapping = {
        'lundi': 0, 'mardi': 1, 'mercredi': 2, 'jeudi': 3,
        'vendredi': 4, 'samedi': 5, 'dimanche': 6
    }
    
    new_collection_days = CollectionDay.objects.filter(name__in=new_days)
    today = timezone.now().date()
    
    # Supprimer les collectes futures programmées
    future_schedules = CollectionSchedule.objects.filter(
        subscription=subscription,
        scheduled_date__gte=today,
        status__in=['scheduled', 'pending']
    ).delete()
    
    # Créer de nouvelles collectes pour les 4 prochaines semaines
    for week in range(4):
        for collection_day in new_collection_days:
            target_weekday = day_mapping[collection_day.name]
            days_ahead = (target_weekday - today.weekday() + 7) % 7
            if days_ahead == 0:
                days_ahead = 7
            
            scheduled_date = today + timedelta(days=days_ahead + (week * 7))
            
            CollectionSchedule.objects.create(
                subscription=subscription,
                scheduled_date=scheduled_date,
                scheduled_day=collection_day,
                scheduled_time=time_slot or '08:00',
                status='scheduled'
            )


@login_required(login_url='login')
def subscription_detail(request, subscription_id):
    """
    Vue pour afficher le détail complet d'un abonnement
    """
    subscription = get_object_or_404(
        Subscription.objects.select_related(
            'plan', 'address'
        ).prefetch_related(
            'collection_days__day',
            'collections',
            'payments'
        ),
        id=subscription_id,
        user=request.user  # Sécurité: l'utilisateur ne voit que ses abonnements
    )
    
    # Collectes récentes
    recent_collections = CollectionRequest.objects.filter(
        subscription=subscription
    ).order_by('-scheduled_date')[:10]
    
    # Paiements récents
    recent_payments = Payment.objects.filter(
        subscription=subscription
    ).order_by('-payment_date')[:10]
    
    context = {
        'subscription': subscription,
        'recent_collections': recent_collections,
        'recent_payments': recent_payments,
    }
    
    return render(request, 'subscription_detail.html', context)


@login_required(login_url='login')
def suspend_subscription(request, subscription_id):
    """
    Vue pour suspendre ou réactiver un abonnement
    """
    subscription = get_object_or_404(
        Subscription,
        id=subscription_id,
        user=request.user  # Sécurité: l'utilisateur ne peut modifier que ses abonnements
    )
    
    if request.method == 'POST':
        # Vérifier si l'action est une suspension ou une réactivation
        action = request.POST.get('action', 'suspend')
        
        if action == 'suspend' and subscription.status == 'active':
            # Suspendre l'abonnement
            subscription.status = 'suspended'
            subscription.updated_at = timezone.now()
            subscription.save()
            
            messages.success(request, '✅ Votre abonnement a été suspendu avec succès.')
            
        elif action == 'reactivate' and subscription.status == 'suspended':
            # Réactiver l'abonnement
            subscription.status = 'active'
            subscription.updated_at = timezone.now()
            
            # Si la date de fin est passée, ajuster les dates
            if subscription.end_date and subscription.end_date < timezone.now().date():
                subscription.start_date = timezone.now().date()
                subscription.end_date = None
            
            subscription.save()
            messages.success(request, '✅ Votre abonnement a été réactivé avec succès.')
            
        else:
            messages.error(request, '❌ Action non autorisée ou statut invalide.')
        
        return redirect('subscriptions_dashboard')
    
    # Si méthode GET, afficher la page de confirmation
    context = {
        'subscription': subscription,
        'page_title': 'Suspendre un abonnement' if subscription.status == 'active' else 'Réactiver un abonnement'
    }
    
    return render(request, 'subscriptions/confirm_suspend.html', context)





@csrf_exempt
@require_http_methods(["POST"])
def renew_subscription_with_payment(request, subscription_id):
    """Démarrer le processus de réabonnement avec paiement"""
    try:
        # Vérifier que l'utilisateur est authentifié
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': "Utilisateur non authentifié."
            }, status=401)

        subscription = Subscription.objects.get(id=subscription_id, user=request.user)
        
        if subscription.status != 'inactive':
            return JsonResponse({
                'success': False,
                'message': "Cet abonnement ne peut pas être renouvelé."
            })

        # Récupérer les données du formulaire
        phone_number = request.POST.get('phone_number')
        payment_method = request.POST.get('payment_method')
        if not phone_number:
            return JsonResponse({
                'success': False,
                'message': "Le numéro de téléphone est requis."
            })

        # Préparer les données de paiement
        amount = subscription.custom_price or subscription.plan.price
        subscription_data = {
            'plan_name': subscription.plan.name,
            'plan_type': subscription.plan.get_plan_type_display(),
            'renewal': True,
            'subscription_id': str(subscription_id)
        }
        
        # Initier le paiement
        payment_service = PaymentService()
        payment_result = payment_service.process_subscription_payment(
            user=request.user,
            amount= int(amount),
            service_name= payment_method,  # Vous pouvez le récupérer du formulaire si nécessaire
            phone_number=phone_number,
            subscription_data=subscription_data,
            subscription=subscription
        )

        logger.info(f"Payment initiation result for {subscription_id}: {payment_result}")

        if payment_result['success']:
            
            return JsonResponse({
                'success': True,
                'message': payment_result.get('message', "Paiement initié avec succès. Veuillez confirmer sur votre téléphone."),
                'transaction_id': payment_result.get('transaction_id'),
                'reference': payment_result.get('reference'),
                'requires_status_check': True
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f"Erreur de paiement: {payment_result.get('message', 'Erreur inconnue')}"
            })
            
    except Subscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': "Abonnement non trouvé."
        }, status=404)
    except Exception as e:
        logger.error(f"Erreur lors du renouvellement avec paiement: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': "Une erreur est survenue lors du traitement du paiement."
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def process_renewal_after_payment(request):
    """Traiter le renouvellement après paiement confirmé"""
    try:
        # Vérifier que l'utilisateur est authentifié
        if not request.user.is_authenticated:
            return JsonResponse({
                'success': False,
                'message': "Utilisateur non authentifié."
            }, status=401)

        data = json.loads(request.body) if request.body else {}
        transaction_reference = data.get('transaction_reference')
        
        if not transaction_reference:
            return JsonResponse({
                'success': False,
                'message': "Référence de transaction manquante."
            })

        # Vérifier une dernière fois le statut de la transaction
        payment_service = PaymentService()
        status_result = payment_service.check_transaction_status(transaction_reference)
        
        logger.info(f"Final status check for {transaction_reference}: {status_result}")
        
        if status_result['success'] and status_result['status'] == 'SUCCESSFUL':
            # Récupérer les infos de la session
            renewal_data = request.session.get('renewal_transaction')
            if not renewal_data:
                return JsonResponse({
                    'success': False,
                    'message': "Session de renouvellement expirée. Veuillez rafraîchir la page."
                })

            subscription_id = renewal_data['subscription_id']
            
            try:
                # Convertir le string UUID en objet UUID pour la requête
                subscription = Subscription.objects.get(id=subscription_id, user=request.user)
            except Subscription.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': "Abonnement non trouvé."
                })
            except Exception as e:
                logger.error(f"Error retrieving subscription {subscription_id}: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'message': "Erreur lors de la récupération de l'abonnement."
                })
            
            # Vérifier que l'abonnement est toujours inactif
            if subscription.status != 'inactive':
                return JsonResponse({
                    'success': False,
                    'message': "Cet abonnement ne peut pas être renouvelé (déjà actif ou suspendu)."
                })
            
            # Calculer les nouvelles dates
            current_date = timezone.now().date()
            end_date = calculate_end_date(current_date, subscription.plan.plan_type)
            
            # Mettre à jour l'abonnement
            subscription.start_date = current_date
            subscription.end_date = end_date
            subscription.status = 'active'
            subscription.save()
            
            # Générer le nouveau programme de collecte
            try:
                schedules_created = generate_collection_schedule(subscription)
                schedule_message = f"{schedules_created} collectes programmées."
            except Exception as e:
                logger.error(f"Error generating collection schedule for {subscription.id}: {str(e)}")
                schedule_message = "Programme de collecte généré avec quelques avertissements."
                schedules_created = 0
            
            # Nettoyer la session
            if 'renewal_transaction' in request.session:
                del request.session['renewal_transaction']
                request.session.modified = True
            
            # Envoyer une notification (optionnel)
            try:
                # Vous pouvez ajouter ici l'envoi d'email ou de notification
                logger.info(f"Subscription {subscription.id} renewed successfully for user {request.user.id}")
            except Exception as e:
                logger.warning(f"Could not send renewal notification: {str(e)}")
            
            return JsonResponse({
                'success': True,
                'message': f"✅ Paiement confirmé ! Votre abonnement {subscription.plan.name} a été renouvelé avec succès. {schedule_message}",
                'subscription_id': str(subscription.id),
                'schedules_created': schedules_created
            })
            
        elif status_result['success'] and status_result['status'] == 'PENDING':
            return JsonResponse({
                'success': False,
                'message': "Le paiement est toujours en attente de confirmation. Veuillez patienter quelques instants de plus.",
                'status': 'PENDING'
            })
            
        else:
            error_message = status_result.get('message', 'Statut de paiement inconnu')
            status = status_result.get('status', 'UNKNOWN')
            
            # Nettoyer la session en cas d'échec
            if 'renewal_transaction' in request.session:
                del request.session['renewal_transaction']
                request.session.modified = True
            
            return JsonResponse({
                'success': False,
                'message': f"❌ Paiement échoué : {error_message}",
                'status': status
            })
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': "Données de requête invalides."
        }, status=400)
        
    except Exception as e:
        logger.error(f"Erreur traitement renouvellement après paiement: {str(e)}", exc_info=True)
        
        # Nettoyer la session en cas d'erreur
        if 'renewal_transaction' in request.session:
            del request.session['renewal_transaction']
            request.session.modified = True
            
        return JsonResponse({
            'success': False,
            'message': "Une erreur technique est survenue lors de l'activation de l'abonnement. Veuillez contacter le support."
        }, status=500)



    
@require_http_methods(["GET"])
def check_renewal_status(request):
    """Vérifier le statut d'un renouvellement en cours"""
    try:
        transaction_reference = request.GET.get('transaction_reference')
        
        if not transaction_reference:
            return JsonResponse({
                'success': False,
                'message': "Référence de transaction manquante"
            })

        payment_service = PaymentService()
        status_result = payment_service.check_transaction_status(transaction_reference)
        
        logger.info(f"Status check for {transaction_reference}: {status_result}")
        
        return JsonResponse(status_result)
        
    except Exception as e:
        logger.error(f"Erreur vérification statut: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': "Erreur lors de la vérification du statut."
        }, status=500)

def calculate_end_date(start_date, plan_type):
    """Calculer la date de fin en fonction du type de plan"""
    if plan_type == 'monthly':
        return start_date + timedelta(days=30)
    elif plan_type == 'quarterly':
        return start_date + timedelta(days=90)
    elif plan_type == 'yearly':
        return start_date + timedelta(days=365)
    else:
        return start_date + timedelta(days=30)



from django.shortcuts import get_object_or_404
from django.http import JsonResponse
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile
from django.utils import timezone
from datetime import timedelta

def generate_qr_code_view(request, subscription_id):
    """Générer et afficher le QR code pour un abonnement"""
    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)
    qr_code, created = SubscriptionQRCode.objects.get_or_create(subscription=subscription)
    
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
        filename = f"subscription_{subscription_id}_qr.png"
        qr_code.qr_code_image.save(filename, ContentFile(buffer.getvalue()), save=True)
    
    context = {
        'subscription': subscription,
        'qr_code': qr_code,
        'renewal_url': qr_code.get_renewal_url(),
    }
    return render(request, 'subscription_qr_code.html', context)

def download_qr_code(request, subscription_id):
    """Télécharger le QR code"""
    subscription = get_object_or_404(Subscription, id=subscription_id, user=request.user)
    qr_code = get_object_or_404(SubscriptionQRCode, subscription=subscription)
    
    if qr_code.qr_code_image:
        response = HttpResponse(qr_code.qr_code_image.read(), content_type='image/png')
        response['Content-Disposition'] = f'attachment; filename="qr_abonnement_{subscription_id}.png"'
        return response
    else:
        messages.error(request, "QR code non disponible")
        return redirect('subscriptions_dashboard')

def qr_renewal_gateway(request, token):
    """Passerelle de réabonnement via QR code - accessible sans authentification"""
    qr_code = get_object_or_404(SubscriptionQRCode, token=token, is_active=True)
    subscription = qr_code.subscription
    
    # Vérifier si l'abonnement peut être renouvelé
    if subscription.status != 'inactive':
        return render(request, 'qr_renewal_info.html', {
            'qr_code': qr_code,
            'subscription': subscription,
            'error': "Cet abonnement ne peut pas être renouvelé (déjà actif ou suspendu)."
        })
    
    if request.method == 'POST':
        return process_qr_renewal_payment(request, qr_code)
    
    # Afficher le formulaire de réabonnement
    context = {
        'qr_code': qr_code,
        'subscription': subscription,
        'plan': subscription.plan,
        'amount': subscription.custom_price or subscription.plan.price,
        'address': subscription.address,
    }
    return render(request, 'qr_renewal_gateway.html', context)


def process_qr_renewal_payment(request, qr_code):
    """Traiter le paiement pour le réabonnement QR code"""
    try:
        subscription = qr_code.subscription
        phone_number = request.POST.get('phone_number', '').strip()
        network = request.POST.get('network', '').strip()
        
        # Validation des champs requis
        if not phone_number:
            return render(request, 'qr_renewal_gateway.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'error': "Le numéro de téléphone est requis."
            })
        
        if not network:
            return render(request, 'qr_renewal_gateway.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'error': "Veuillez sélectionner votre opérateur mobile."
            })
        
        # Validation du format du numéro
        if not re.match(r'^6[0-9]{8}$', phone_number):
            return render(request, 'qr_renewal_gateway.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'error': "Format de numéro invalide. Utilisez: 6XXXXXXXX (9 chiffres)"
            })
        
        # Vérifier que l'abonnement peut être renouvelé
        if subscription.status != 'inactive':
            return render(request, 'qr_renewal_gateway.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'error': "Cet abonnement ne peut pas être renouvelé (déjà actif ou suspendu)."
            })
        
        # Préparer les données de paiement
        amount = subscription.custom_price or subscription.plan.price
        subscription_data = {
            'plan_name': subscription.plan.name,
            'plan_type': subscription.plan.get_plan_type_display(),
            'renewal': True,
            'subscription_id': str(subscription.id),
            'qr_token': qr_code.token
        }
        
        logger.info(f"Processing QR renewal payment: subscription={subscription.id}, phone={phone_number}, amount={amount}")
        
        # Initier le paiement
        payment_service = PaymentService()
        payment_result = payment_service.process_subscription_payment(
            user=subscription.user,
            amount= 10, #int(amount),
            service_name=network,
            phone_number=phone_number,
            subscription_data=subscription_data,
            subscription= subscription
        )
        
        logger.info(f"Payment result: {payment_result}")
        
        if payment_result.get('success'):
            # Stocker les infos de transaction en session
            request.session['qr_renewal_transaction'] = {
                'transaction_id': payment_result.get('transaction_id'),
                'subscription_id': str(subscription.id),
                'qr_token': qr_code.token,
                'phone_number': phone_number,
                'amount': float(amount)
            }
            request.session.modified = True
            
            return render(request, 'qr_renewal_processing.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'transaction_id': payment_result.get('transaction_id'),
                'amount': amount,
                'phone_number': phone_number
            })
        else:
            error_message = payment_result.get('message', 'Erreur inconnue lors du paiement')
            logger.error(f"Payment failed: {error_message}")
            
            return render(request, 'qr_renewal_gateway.html', {
                'qr_code': qr_code,
                'subscription': subscription,
                'error': f"Erreur de paiement: {error_message}"
            })
            
    except Exception as e:
        logger.error(f"Erreur réabonnement QR code: {str(e)}", exc_info=True)
        return render(request, 'qr_renewal_gateway.html', {
            'qr_code': qr_code,
            'subscription': subscription,
            'error': f"Une erreur technique est survenue: {str(e)}"
        })

@csrf_exempt  
@require_http_methods(["POST"])
def check_qr_renewal_status(request):
    """Vérifier le statut d'un réabonnement QR code (AJAX)"""
    try:
        logger.info(f"Check QR renewal status called with: {request.POST}")
        
        transaction_id = request.POST.get('transaction_id')
        qr_token = request.POST.get('qr_token')
        
        if not transaction_id:
            logger.error("Transaction ID manquant")
            return JsonResponse({
                'success': False,
                'message': "Transaction ID manquant"
            }, status=400)

        if not qr_token:
            logger.error("QR token manquant")
            return JsonResponse({
                'success': False,
                'message': "QR token manquant"
            }, status=400)
        
        qr_code = get_object_or_404(SubscriptionQRCode, token=qr_token)
        payment_service = PaymentService()
        
        logger.info(f"Checking transaction status: {transaction_id}")
        status_result = payment_service.check_transaction_status(transaction_id)
        
        logger.info(f"Transaction status result: {status_result}")
        
        if status_result.get('success') and status_result.get('status') == 'SUCCESSFUL':
            # Paiement réussi, renouveler l'abonnement
            subscription = qr_code.subscription
            
            # Vérifier une dernière fois que l'abonnement peut être renouvelé
            if subscription.status != 'inactive':
                logger.warning(f"Subscription {subscription.id} cannot be renewed, status: {subscription.status}")
                return JsonResponse({
                    'success': False,
                    'message': "L'abonnement ne peut pas être renouvelé dans son état actuel."
                })
            
            # Calculer les nouvelles dates
            current_date = timezone.now().date()
            end_date = calculate_end_date(current_date, subscription.plan.plan_type)
            
            # Mettre à jour l'abonnement
            subscription.start_date = current_date
            subscription.end_date = end_date
            subscription.status = 'active'
            subscription.save()
            
            # Générer le nouveau programme de collecte
            try:
                schedules_created = generate_collection_schedule(subscription)
                schedule_message = f"{schedules_created} collectes programmées."
            except Exception as e:
                logger.error(f"Error generating collection schedule: {str(e)}")
                schedule_message = "Programme de collecte généré avec quelques avertissements."
            
            # Nettoyer la session
            if 'qr_renewal_transaction' in request.session:
                del request.session['qr_renewal_transaction']
                request.session.modified = True
            
            logger.info(f"Subscription {subscription.id} renewed successfully via QR code")
            
            return JsonResponse({
                'success': True,
                'message': f"✅ Paiement confirmé ! Votre abonnement {subscription.plan.name} a été renouvelé avec succès. {schedule_message}",
                'redirect_url': f"/subscription/qr-renew/success/{qr_token}/"
            })
        
        elif status_result.get('success') and status_result.get('status') in ['FAILED', 'ERROR']:
            error_message = status_result.get('message', 'Paiement échoué')
            logger.error(f"Payment failed: {error_message}")
            return JsonResponse({
                'success': False,
                'message': f"❌ Paiement échoué : {error_message}"
            })
        else:
            # Statut PENDING ou autre
            logger.info(f"Payment still pending for transaction {transaction_id}")
            return JsonResponse({
                'success': False,
                'message': "Paiement en attente de confirmation...",
                'status': 'PENDING'
            })
            
    except Exception as e:
        logger.error(f"Erreur vérification statut QR: {str(e)}", exc_info=True)
        return JsonResponse({
            'success': False,
            'message': f"Erreur lors de la vérification du statut: {str(e)}"
        }, status=500)

def qr_renewal_success(request, token):
    """Page de succès après réabonnement QR code"""
    qr_code = get_object_or_404(SubscriptionQRCode, token=token)
    subscription = qr_code.subscription
    
    return render(request, 'qr_renewal_success.html', {
        'qr_code': qr_code,
        'subscription': subscription
    })


# la vue des zones de disponibilitées
class ZonesProgrammesView(ListView):
    model = Zone
    template_name = 'zones_programmes.html'
    context_object_name = 'zones'
    
    def get_queryset(self):
        # Récupérer uniquement les zones actives avec leurs programmes
        return Zone.objects.filter(
            is_active=True
        ).prefetch_related(
            'programmes_tricycle__tricycle'
        ).select_related('ville')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Ajouter les tricycles actifs
        context['tricycles'] = Tricycle.objects.filter(
            status='active'
        ).select_related('conducteur')
        
        # Ajouter la liste des villes pour le filtre
        context['cities'] = City.objects.all()
        
        return context
    




# les vues pour les notifications

@login_required(login_url='login')
def notification_list(request):
    """Page listant toutes les notifications de l'utilisateur"""
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')
    
    # Marquer comme lues lorsque l'utilisateur consulte la page
    unread_notifications = notifications.filter(is_read=False)
    unread_notifications.update(is_read=True)
    
    context = {
        'notifications': notifications,
        'active_tab': 'notifications'
    }
    return render(request, 'notification_list.html', context)

@login_required(login_url='login')
@require_http_methods(["POST"])
def mark_all_as_read(request):
    """Marquer toutes les notifications comme lues"""
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return JsonResponse({'success': True})

@login_required(login_url='login')
@require_http_methods(["POST"])
def mark_as_read(request, notification_id):
    """Marquer une notification spécifique comme lue"""
    notification = get_object_or_404(Notification, id=notification_id, user=request.user)
    notification.mark_as_read()
    return JsonResponse({'success': True})

@login_required(login_url='login')
def get_unread_count(request):
    """API pour récupérer le nombre de notifications non lues"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'unread_count': count})

@login_required(login_url='login')
def get_recent_notifications(request):
    """API pour récupérer les notifications récentes"""
    notifications = Notification.objects.filter(
        user=request.user
    ).order_by('-created_at')[:5]
    
    notifications_data = []
    for notification in notifications:
        notifications_data.append({
            'id': str(notification.id),
            'title': notification.title,
            'message': notification.message,
            'type': notification.notification_type,
            'is_read': notification.is_read,
            'created_at': notification.created_at.strftime('%d/%m/%Y %H:%M'),
            'action_url': notification.action_url,
        })
    
    return JsonResponse({'notifications': notifications_data})
# fin des vues pour les notifications 