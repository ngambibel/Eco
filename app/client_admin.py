from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Count, Sum
import json
import qrcode
from io import BytesIO
from django.core.files.base import ContentFile

from django.contrib.admin.views.decorators import staff_member_required
import xlwt
from datetime import timedelta

from io import StringIO

from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
from datetime import datetime
from io import BytesIO


from .models import (
    CustomUser, Subscription, SubscriptionPlan, City, Zone,
    SubscriptionQRCode, CollectionRequest, Payment, Tricycle
)

# Vérifier si l'utilisateur est admin
def is_admin(user):
    return user.is_authenticated and user.user_type == 'admin'

@login_required(login_url='login')
@user_passes_test(is_admin)
def gestion_abonnements(request):
    """Page principale de gestion des abonnements et utilisateurs"""
    # Récupérer les paramètres de filtrage
    statut_filter = request.GET.get('statut', 'all')
    search_query = request.GET.get('q', '')
    page_number = request.GET.get('page', 1)
    
    # Filtrage des abonnements
    subscriptions = Subscription.objects.select_related(
        'user', 'plan', 'zone', 'address'
    ).prefetch_related('collection_days')
    
    if statut_filter != 'all':
        subscriptions = subscriptions.filter(status=statut_filter)
    
    if search_query:
        subscriptions = subscriptions.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__phone__icontains=search_query) |
            Q(plan__name__icontains=search_query)
        )
    
    # Filtrage des utilisateurs
    users = CustomUser.objects.select_related('city')
    if search_query:
        users = users.filter(
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone__icontains=search_query)
        )
    
    # Pagination
    subscription_paginator = Paginator(subscriptions.order_by('-created_at'), 10)
    users_paginator = Paginator(users.order_by('-date_joined'), 10)
    
    subscriptions_page = subscription_paginator.get_page(page_number)
    users_page = users_paginator.get_page(page_number)
    
    # Statistiques
    total_subscriptions = subscriptions.count()
    active_subscriptions = subscriptions.filter(status='active').count()
    suspended_subscriptions = subscriptions.filter(status='suspended').count()
    total_users = users.count()
    
    context = {
        'users': users_page,
        'subscriptions': subscriptions_page,
        'subscription_plans': SubscriptionPlan.objects.filter(is_active=True),
        'cities': City.objects.all(),
        'zones': Zone.objects.filter(is_active=True),
        'total_subscriptions': total_subscriptions,
        'active_subscriptions': active_subscriptions,
        'suspended_subscriptions': suspended_subscriptions,
        'total_users': total_users,
        'current_filter': statut_filter,
        'search_query': search_query,
    }
    
    return render(request, 'administrations/gestion_abonnements.html', context)

@login_required(login_url='login')
@user_passes_test(is_admin)
def ajouter_utilisateur(request):
    """Ajouter un nouvel utilisateur"""
    if request.method == 'POST':
        try:
            first_name = request.POST.get('first_name')
            last_name = request.POST.get('last_name')
            email = request.POST.get('email')
            phone = request.POST.get('phone')
            user_type = request.POST.get('user_type')
            city_id = request.POST.get('city')
            password = request.POST.get('password')
            confirm_password = request.POST.get('confirm_password')
            
            # Validation
            if not all([first_name, last_name, email, user_type]):
                messages.error(request, "Tous les champs obligatoires doivent être remplis.")
                return redirect('gestion_abonnements')
            
            if password != confirm_password:
                messages.error(request, "Les mots de passe ne correspondent pas.")
                return redirect('gestion_abonnements')
            
            if CustomUser.objects.filter(email=email).exists():
                messages.error(request, "Un utilisateur avec cet email existe déjà.")
                return redirect('gestion_abonnements')
            
            # Création de l'utilisateur
            user = CustomUser(
                first_name=first_name,
                last_name=last_name,
                email=email,
                phone=phone,
                user_type=user_type,
                username=email  # Utiliser l'email comme nom d'utilisateur
            )
            
            if city_id:
                user.city_id = city_id
            
            user.set_password(password)
            user.save()
            
            messages.success(request, f"Utilisateur {user.get_full_name()} créé avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création de l'utilisateur: {str(e)}")
    
    return redirect('gestion_abonnements')

@login_required(login_url='login')
@user_passes_test(is_admin)
def editer_utilisateur(request):
    """Éditer un utilisateur existant"""
    if request.method == 'POST':
        try:
            user_id = request.POST.get('user_id')
            user = get_object_or_404(CustomUser, id=user_id)
            
            user.first_name = request.POST.get('first_name')
            user.last_name = request.POST.get('last_name')
            user.email = request.POST.get('email')
            user.phone = request.POST.get('phone')
            user.user_type = request.POST.get('user_type')
            user.city_id = request.POST.get('city') or None
            user.is_verified = request.POST.get('is_verified') == 'on'
            
            # Gestion du mot de passe
            password = request.POST.get('password')
            if password:
                user.set_password(password)
            
            user.save()
            
            messages.success(request, f"Utilisateur {user.get_full_name()} mis à jour avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la mise à jour de l'utilisateur: {str(e)}")
    
    return redirect('gestion_abonnements')

@login_required(login_url='login')
@user_passes_test(is_admin)
def supprimer_utilisateur(request, user_id):
    """Supprimer un utilisateur"""
    if request.method == 'POST':
        try:
            user = get_object_or_404(CustomUser, id=user_id)
            
            # Vérifier s'il y a des abonnements associés
            if user.subscriptions.exists():
                messages.error(request, "Impossible de supprimer cet utilisateur car il a des abonnements actifs.")
                return redirect('gestion_abonnements')
            
            user_name = user.get_full_name()
            user.delete()
            
            messages.success(request, f"Utilisateur {user_name} supprimé avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression de l'utilisateur: {str(e)}")
    
    return redirect('gestion_abonnements')

@login_required(login_url='login')
@user_passes_test(is_admin)
def editer_abonnement(request):
    """Éditer un abonnement existant"""
    if request.method == 'POST':
        try:
            subscription_id = request.POST.get('subscription_id')
            subscription = get_object_or_404(Subscription, id=subscription_id)
            
            subscription.user_id = request.POST.get('user')
            subscription.plan_id = request.POST.get('plan')
            subscription.status = request.POST.get('status')
            subscription.start_date = request.POST.get('start_date')
            subscription.end_date = request.POST.get('end_date') or None
            subscription.custom_price = request.POST.get('custom_price') or None
            subscription.special_instructions = request.POST.get('special_instructions', '')
            
            subscription.save()
            
            messages.success(request, f"Abonnement {subscription.plan.name} mis à jour avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la mise à jour de l'abonnement: {str(e)}")
    
    return redirect('gestion_abonnements')

@login_required(login_url='login')
@user_passes_test(is_admin)
def supprimer_abonnement(request, subscription_id):
    """Supprimer un abonnement"""
    if request.method == 'POST':
        try:
            subscription = get_object_or_404(Subscription, id=subscription_id)
            subscription_name = f"{subscription.plan.name} - {subscription.user.get_full_name()}"
            subscription.delete()
            
            messages.success(request, f"Abonnement {subscription_name} supprimé avec succès.")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression de l'abonnement: {str(e)}")
    
    return redirect('gestion_abonnements')

@login_required(login_url='login')
@user_passes_test(is_admin)
def generer_qr_code(request, subscription_id):
    """Générer ou récupérer un QR Code pour un abonnement"""
    try:
        subscription = get_object_or_404(Subscription, id=subscription_id)
        
        # Vérifier si un QR Code existe déjà
        qr_code, created = SubscriptionQRCode.objects.get_or_create(
            subscription=subscription
        )
        
        # Si le QR Code existe déjà et a une image, on le retourne directement
        if not created and qr_code.qr_code_image:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'qr_code_url': qr_code.qr_code_image.url,
                    'user_name': subscription.user.get_full_name(),
                    'user_phone': subscription.user.phone,
                    'plan_name': subscription.plan.name,
                    'start_date': subscription.start_date.strftime('%d/%m/%Y'),
                    'is_new': False  # Indique que c'est un QR existant
                })
            else:
                messages.info(request, f"QR Code déjà existant pour {subscription.user.get_full_name()}.")
                return redirect('gestion_abonnements')
        
        # Générer un nouveau QR Code seulement si il n'existe pas
        qr_data = {
            'subscription_id': str(subscription.id),
            'user_name': subscription.user.get_full_name(),
            'user_phone': subscription.user.phone,
            'plan_name': subscription.plan.name,
            'start_date': subscription.start_date.isoformat(),
            'company': 'ECOCITY'
        }
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(json.dumps(qr_data))
        qr.make(fit=True)
        
        # Créer l'image
        img = qr.make_image(fill_color="#2E8B57", back_color="white")
        
        # Sauvegarder l'image
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        # Sauvegarder dans le modèle
        filename = f"qr_code_{subscription.id}.png"
        qr_code.qr_code_image.save(filename, ContentFile(buffer.read()), save=True)
        qr_code.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'qr_code_url': qr_code.qr_code_image.url,
                'user_name': subscription.user.get_full_name(),
                'user_phone': subscription.user.phone,
                'plan_name': subscription.plan.name,
                'start_date': subscription.start_date.strftime('%d/%m/%Y'),
                'is_new': True  # Indique que c'est un nouveau QR
            })
        else:
            messages.success(request, f"QR Code généré avec succès pour {subscription.user.get_full_name()}.")
            return redirect('gestion_abonnements')
            
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            print('ici la faute est la')
            return JsonResponse({'success': False, 'error': str(e)})
        else:
            print(e)
            messages.error(request, f"Erreur lors de la génération du QR Code: {str(e)}")
            return redirect('gestion_abonnements')
        

@login_required(login_url='login')
@user_passes_test(is_admin)
def telecharger_qr_code(request, subscription_id):
    """Télécharger le QR Code"""
    try:
        subscription = get_object_or_404(Subscription, id=subscription_id)
        qr_code = get_object_or_404(SubscriptionQRCode, subscription=subscription)
        
        if qr_code.qr_code_image:
            response = HttpResponse(qr_code.qr_code_image.read(), content_type='image/png')
            response['Content-Disposition'] = f'attachment; filename="QRCode_ECOCITY_{subscription.user.get_full_name().replace(" ", "_")}.png"'
            return response
        else:
            messages.error(request, "Aucun QR Code trouvé pour cet abonnement.")
            return redirect('gestion_abonnements')
            
    except Exception as e:
        messages.error(request, f"Erreur lors du téléchargement: {str(e)}")
        return redirect('gestion_abonnements')
    

@login_required(login_url='login')
@user_passes_test(is_admin)
def recuperer_qr_code(request, subscription_id):
    """Récupérer un QR Code existant depuis la base de données"""
    try:
        subscription = get_object_or_404(Subscription, id=subscription_id)
        
        # Vérifier si un QR Code existe
        try:
            qr_code = SubscriptionQRCode.objects.get(subscription=subscription)
            
            if qr_code.qr_code_image :
                return JsonResponse({
                    'success': True,
                    'qr_code_url': qr_code.qr_code_image.url,
                    'user_name': subscription.user.get_full_name(),
                    'user_phone': subscription.user.phone,
                    'plan_name': subscription.plan.name,
                    'start_date': subscription.start_date.strftime('%d/%m/%Y'),
                    'exists': True
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': 'QR Code existe mais aucune image trouvée',
                    'exists': True
                })
                
        except SubscriptionQRCode.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Aucun QR Code trouvé pour cet abonnement',
                'exists': False
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e),
            'exists': False
        })

@login_required(login_url='login')
@user_passes_test(is_admin)
def detail_utilisateur(request, user_id):
    """Page de détail d'un utilisateur"""
    user = get_object_or_404(CustomUser, id=user_id)
    subscriptions = user.subscriptions.select_related('plan', 'zone').prefetch_related('collection_days')
    payments = Payment.objects.filter(subscription__user=user).order_by('-payment_date')
    
    context = {
        'user_detail': user,
        'subscriptions': subscriptions,
        'payments': payments,
    }
    
    return render(request, 'administrations/detail_utilisateur.html', context)

@login_required(login_url='login')
@user_passes_test(is_admin)
def detail_abonnement(request, subscription_id):
    """Page de détail d'un abonnement"""
    subscription = get_object_or_404(
        Subscription.objects.select_related('user', 'plan', 'zone', 'address'),
        id=subscription_id
    )
    
    # Précharger le QR Code s'il existe
    try:
        qr_code = subscription.qr_code
    except SubscriptionQRCode.DoesNotExist:
        qr_code = None
    
    collection_days = subscription.collection_days.select_related('day')
    collection_requests = subscription.collections.order_by('-scheduled_date')
    payments = subscription.payments.order_by('-payment_date')
    
    context = {
        'subscription_detail': subscription,
        'qr_code': qr_code,
        'collection_days': collection_days,
        'collection_requests': collection_requests,
        'payments': payments,
    }
    
    return render(request, 'administrations/detail_abonnement.html', context)

# API endpoints pour AJAX
@login_required(login_url='login')
@user_passes_test(is_admin)
def api_utilisateurs(request):
    """API pour les données utilisateurs"""
    search = request.GET.get('search', '')
    user_type = request.GET.get('user_type', '')
    
    users = CustomUser.objects.all()
    
    if search:
        users = users.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search) |
            Q(email__icontains=search) |
            Q(phone__icontains=search)
        )
    
    if user_type:
        users = users.filter(user_type=user_type)
    
    users_data = []
    for user in users[:50]:  # Limiter à 50 résultats
        users_data.append({
            'id': str(user.id),
            'full_name': user.get_full_name(),
            'email': user.email,
            'phone': user.phone,
            'user_type': user.get_user_type_display(),
            'city': user.city.city if user.city else '',
            'date_joined': user.date_joined.strftime('%d/%m/%Y'),
            'is_verified': user.is_verified,
        })
    
    return JsonResponse({'users': users_data})

@login_required(login_url='login')
@user_passes_test(is_admin)
def api_abonnements(request):
    """API pour les données abonnements"""
    status = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    subscriptions = Subscription.objects.select_related('user', 'plan', 'zone')
    
    if status:
        subscriptions = subscriptions.filter(status=status)
    
    if search:
        subscriptions = subscriptions.filter(
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search) |
            Q(plan__name__icontains=search)
        )
    
    subscriptions_data = []
    for subscription in subscriptions[:50]:  # Limiter à 50 résultats
        subscriptions_data.append({
            'id': str(subscription.id),
            'user_name': subscription.user.get_full_name(),
            'user_phone': subscription.user.phone,
            'plan_name': subscription.plan.name,
            'plan_type': subscription.plan.get_plan_type_display(),
            'status': subscription.get_status_display(),
            'start_date': subscription.start_date.strftime('%d/%m/%Y'),
            'end_date': subscription.end_date.strftime('%d/%m/%Y') if subscription.end_date else '',
            'zone': subscription.zone.nom if subscription.zone else '',
            'price': float(subscription.custom_price or subscription.plan.price),
        })
    
    return JsonResponse({'subscriptions': subscriptions_data})

@login_required(login_url='login')
@user_passes_test(is_admin)
def api_statistiques(request):
    """API pour les statistiques en temps réel"""
    # Statistiques des abonnements
    subscription_stats = Subscription.objects.aggregate(
        total=Count('id'),
        active=Count('id', filter=Q(status='active')),
        suspended=Count('id', filter=Q(status='suspended')),
        inactive=Count('id', filter=Q(status='inactive'))
    )
    
    # Statistiques des utilisateurs
    user_stats = CustomUser.objects.aggregate(
        total=Count('id'),
        clients=Count('id', filter=Q(user_type='client')),
        collecteurs=Count('id', filter=Q(user_type='collecteur')),
        admins=Count('id', filter=Q(user_type='admin'))
    )
    
    # Chiffre d'affaires du mois
    current_month_revenue = Payment.objects.filter(
        status='completed',
        payment_date__month=timezone.now().month,
        payment_date__year=timezone.now().year
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    return JsonResponse({
        'subscriptions': subscription_stats,
        'users': user_stats,
        'current_month_revenue': float(current_month_revenue),
        'last_updated': timezone.now().strftime('%d/%m/%Y %H:%M:%S')
    })

@login_required(login_url='login')
@user_passes_test(is_admin)
def gestion_collecte(request):
    """Gestion de la collecte des déchets"""
    # Implémentation de la gestion de collecte
    return render(request, 'administrations/gestion_collecte.html')


# les vues pour recuperer les informations des client dont l'abonnement expire dans 8 jour





@staff_member_required
def export_abonnements_expirant(request):
    """
    Vue AJAX pour exporter les utilisateurs avec abonnements actifs
    dont la date de fin est dans moins de 8 jours
    """
    try:
        # Calculer la date limite (aujourd'hui + 8 jours)
        date_limite = timezone.now().date() + timedelta(days=8)
        aujourd_hui = timezone.now().date()
        
        print(f"Recherche des abonnements expirant entre {aujourd_hui} et {date_limite}")
        
        # Récupérer les abonnements inactifs dont la date de fin est inférieure ou égale à hier
        hier = timezone.now().date() - timedelta(days=1)

        abonnements = Subscription.objects.filter(
            status='inactive',
            end_date__lte=hier
        ).select_related('user', 'plan', 'zone').order_by('end_date')
        
        
        # Créer le fichier XLS
        response = HttpResponse(content_type='application/ms-excel')
        filename = f"abonnements_expirant_{hier.strftime('%Y%m%d')}.xls"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        
        # Créer le classeur Excel
        wb = xlwt.Workbook(encoding='utf-8')
        ws = wb.add_sheet('Abonnements')
        
        # Style pour les cellules
        style_nom = xlwt.XFStyle()
        style_nom.font.bold = False
        
        # Remplir les données (sans entête)
        row_num = 0
        for abonnement in abonnements:
            user = abonnement.user
            
            # Colonne A : Nom complet
            nom = user.username or f"{user.first_name} {user.last_name}"
            ws.write(row_num, 0, nom, style_nom)
            
            # Colonne B : Téléphone
            telephone = user.phone if user.phone else ''
            ws.write(row_num, 1, telephone, style_nom)
            
            row_num += 1
        
        # Statistiques (pour la réponse JSON si demandé)
        stats = {
            'total': abonnements.count(),
            'date_recherche': aujourd_hui.strftime('%d/%m/%Y'),
            'date_limite': date_limite.strftime('%d/%m/%Y')
        }
        
        # Si c'est une requête AJAX avec paramètre 'json', retourner les données en JSON
        if request.GET.get('format') == 'json':
            data = []
            for abonnement in abonnements:
                user = abonnement.user
                jours_restants = (abonnement.end_date - aujourd_hui).days
                data.append({
                    'nom': user.get_full_name() or f"{user.first_name} {user.last_name}",
                    'telephone': user.phone if user.phone else 'Non renseigné',
                    'email': user.email or 'Non renseigné',
                    'plan': abonnement.plan.name if abonnement.plan else 'Non défini',
                    'date_debut': abonnement.start_date.strftime('%d/%m/%Y'),
                    'date_fin': abonnement.end_date.strftime('%d/%m/%Y'),
                    'jours_restants': jours_restants,
                    'zone': abonnement.zone.nom if abonnement.zone else 'Non assigné'
                })
            
            return JsonResponse({
                'success': True,
                'data': data,
                'stats': stats
            })
        
        # Sauvegarder le classeur dans la réponse
        wb.save(response)
        return response
        
    except Exception as e:
        print(f"Erreur lors de l'export : {str(e)}")
        if request.GET.get('format') == 'json':
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)
        else:
            return HttpResponse(f"Erreur : {str(e)}", status=500)
        

@staff_member_required
def get_abonnements_expirant_stats(request):
    """
    Vue AJAX pour récupérer les statistiques des abonnements expirant
    """
    try:
        date_limite = timezone.now().date() + timedelta(days=8)
        aujourd_hui = timezone.now().date()
        
        # Statistiques générales
        total_expirant = Subscription.objects.filter(
            status='active',
            end_date__isnull=False,
            end_date__gte=aujourd_hui,
            end_date__lte=date_limite
        ).count()
        
        # Statistiques par jour
        jours_stats = []
        for i in range(1, 9):
            date = aujourd_hui + timedelta(days=i)
            count = Subscription.objects.filter(
                status='active',
                end_date=date
            ).count()
            
            if count > 0:
                jours_stats.append({
                    'date': date.strftime('%d/%m/%Y'),
                    'count': count,
                    'jour_semaine': date.strftime('%A')
                })
        
        return JsonResponse({
            'success': True,
            'total': total_expirant,
            'date_limite': date_limite.strftime('%d/%m/%Y'),
            'date_aujourd_hui': aujourd_hui.strftime('%d/%m/%Y'),
            'par_jour': jours_stats
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

