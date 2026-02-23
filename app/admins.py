from django.views.generic import TemplateView
from django.db.models import Count, Sum, Q
from django.utils import timezone
from django.db.models.functions import TruncMonth, TruncYear

import json
from .models import (
    Payment, Subscription, CollectionRequest, DemandeReabonnement, 
    RevenueRecord, Notification, SubscriptionDay, Abonnement, CustomUser, Facture, CollectionSchedule
)
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.core.paginator import Paginator

from django.http import FileResponse, JsonResponse

from datetime import datetime, timedelta
import os
from django.conf import settings



def is_admin_user(user):
    return user.is_authenticated and user.user_type in ['admin', 'SUPER_ADMIN']

class DashboardView(TemplateView):
    template_name = 'administrations/dashboard.html'
    
    def get_weekly_collection_stats(self, selected_date=None):
        """Récupère les statistiques réelles des collectes avec filtre par date"""
        if selected_date:
            # Convertir la date string en objet date
            try:
                filter_date = datetime.strptime(selected_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                filter_date = timezone.now().date()
        else:
            filter_date = timezone.now().date()
        
        # Déterminer la période (7 jours incluant la date sélectionnée)
        start_date = filter_date - timedelta(days=filter_date.weekday())
        end_date = start_date + timedelta(days=6)
        
        # Initialiser les données pour chaque jour
        jours_semaine = ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim']
        dates_semaine = [start_date + timedelta(days=i) for i in range(7)]
        labels_semaine = []
        
        programmees = [0] * 7
        terminees = [0] * 7
        en_attente = [0] * 7
        
        try:
            # Récupérer toutes les collectes de la semaine
            collections = CollectionSchedule.objects.filter(
                scheduled_date__gte=start_date,
                scheduled_date__lte=end_date
            )
            
            # Organiser les données par jour
            for i, current_date in enumerate(dates_semaine):
                # Formater le label avec indication du jour actuel
                date_label = jours_semaine[i]
                if current_date == timezone.now().date():
                    date_label += " (Auj)"
                elif current_date == filter_date:
                    date_label += " (Sél)"
                
                labels_semaine.append(date_label)
                
                # Filtrer les collectes pour ce jour spécifique
                day_collections = collections.filter(scheduled_date=current_date)
                
                # Compter par statut
                programmees[i] = day_collections.filter(
                    status__in=['scheduled', 'in_progress', 'pending', 'completed']
                ).count()
                
                terminees[i] = day_collections.filter(
                    status='completed'
                ).count()
                
                en_attente[i] = day_collections.filter(
                    status__in=['scheduled', 'pending']
                ).count()
                
        except Exception as e:
            print(f"Erreur dans get_weekly_collection_stats: {e}")
            # Données de démonstration en cas d'erreur
            labels_semaine = jours_semaine
            programmees = [25, 30, 22, 35, 28, 15, 8]
            terminees = [20, 25, 18, 30, 24, 12, 5]
            en_attente = [5, 5, 4, 5, 4, 3, 3]
        
        return {
            'labels': labels_semaine,
            'dates_semaine': [date.strftime('%Y-%m-%d') for date in dates_semaine],
            'programmees': programmees,
            'terminees': terminees,
            'en_attente': en_attente,
            'total_programmees': sum(programmees),
            'total_terminees': sum(terminees),
            'total_en_attente': sum(en_attente),
            'date_debut': start_date.strftime('%Y-%m-%d'),
            'date_fin': end_date.strftime('%Y-%m-%d'),
            'date_selectionnee': filter_date.strftime('%Y-%m-%d'),
            'date_selectionnee_display': filter_date.strftime('%d/%m/%Y')
        }
    
    def get_today_collections_data(self):
        """Récupère les données des collectes d'aujourd'hui"""
        today = timezone.now().date()
        
        today_collections_count = CollectionSchedule.objects.filter(
            scheduled_date=today,
            status__in=['scheduled', 'in_progress', 'pending']
        ).count()
        
        today_collections_list = CollectionSchedule.objects.filter(
            scheduled_date=today
        ).select_related(
            'subscription__user', 
            'subscription__address__zone'
        ).order_by('scheduled_time')[:10]
        
        return today_collections_count, today_collections_list
    
    def get_monthly_revenue(self):
        """Calcule le chiffre d'affaires du mois en cours"""
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        monthly_revenue = RevenueRecord.objects.filter(
            transaction_date__gte=month_start,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        return monthly_revenue
    
    def get_recent_activities(self):
        """Récupère les activités récentes"""
        activities = []
        
        # Notifications récentes
        recent_notifications = Notification.objects.filter(
            created_at__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-created_at')[:6]
        
        for notification in recent_notifications:
            activities.append({
                'icon': self.get_activity_icon(notification.notification_type),
                'color': self.get_activity_color(notification.notification_type),
                'message': notification.message,
                'timestamp': notification.created_at
            })
        
        return activities
    
    def get_activity_icon(self, notification_type):
        icons = {
            'info': 'info-circle',
            'success': 'check-circle',
            'warning': 'exclamation-triangle',
            'error': 'times-circle',
            'collection': 'truck-loading',
            'payment': 'money-bill-wave',
            'system': 'cog'
        }
        return icons.get(notification_type, 'bell')
    
    def get_activity_color(self, notification_type):
        colors = {
            'info': 'info',
            'success': 'success',
            'warning': 'warning',
            'error': 'danger',
            'collection': 'primary',
            'payment': 'success',
            'system': 'secondary'
        }
        return colors.get(notification_type, 'info')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Récupérer la date de filtre depuis les paramètres GET
        selected_date = self.request.GET.get('date_filtre')
        
        # Statistiques principales
        context['active_subscriptions'] = Subscription.objects.filter(
            status='active'
        ).count()
        
        # Collectes d'aujourd'hui
        today_collections_count, today_collections_list = self.get_today_collections_data()
        context['today_collections'] = today_collections_count
        context['today_collections_list'] = today_collections_list
        
        # Chiffre d'affaires du mois
        context['monthly_revenue'] = self.get_monthly_revenue()
        
        # Réabonnements en attente
        context['pending_renewals'] = DemandeReabonnement.objects.filter(
            statut='EN_ATTENTE'
        ).count()
        
        context['pending_renewals_list'] = DemandeReabonnement.objects.filter(
            statut='EN_ATTENTE'
        ).select_related('abonnement__client')[:10]
        
        # Données hebdomadaires pour le graphique avec filtre
        weekly_stats = self.get_weekly_collection_stats(selected_date)
        context['weekly_collections'] = weekly_stats
        
        # Convertir en JSON pour JavaScript de manière sécurisée
        context['weekly_collections_json'] = json.dumps(weekly_stats)
        
        # Date pour le formulaire de filtre
        context['date_filtre'] = selected_date or timezone.now().date().strftime('%Y-%m-%d')
        
        # Activités récentes
        context['recent_activities'] = self.get_recent_activities()
        
        # Notifications non lues
        if self.request.user.is_authenticated:
            context['unread_notifications'] = Notification.objects.filter(
                user=self.request.user,
                is_read=False
            ).count()
        else:
            context['unread_notifications'] = 0
        
        return context
    


@login_required
@user_passes_test(is_admin_user)
def gestion_reabonnements_canal(request):
    """Vue principale pour la gestion des réabonnements Canal+"""
    # Récupérer les paramètres de filtrage
    statut_filter = request.GET.get('statut', '')
    date_debut = request.GET.get('date_debut', '')
    date_fin = request.GET.get('date_fin', '')
    search_query = request.GET.get('search', '')
    
    # Construire la queryset de base
    demandes = DemandeReabonnement.objects.filter(
        abonnement__type_service='CANAL'
    ).select_related('abonnement', 'abonnement__client').order_by('-date_demande')
    
    # Appliquer les filtres
    if statut_filter:
        demandes = demandes.filter(statut=statut_filter)
    
    if date_debut:
        try:
            date_debut_obj = datetime.strptime(date_debut, '%Y-%m-%d').date()
            demandes = demandes.filter(date_demande__date__gte=date_debut_obj)
        except ValueError:
            pass
    
    if date_fin:
        try:
            date_fin_obj = datetime.strptime(date_fin, '%Y-%m-%d').date()
            demandes = demandes.filter(date_demande__date__lte=date_fin_obj)
        except ValueError:
            pass
    
    if search_query:
        demandes = demandes.filter(
            Q(abonnement__identifiant_abonne__icontains=search_query) |
            Q(abonnement__client__first_name__icontains=search_query) |
            Q(abonnement__client__last_name__icontains=search_query) |
            Q(abonnement__client__email__icontains=search_query) |
            Q(id__icontains=search_query)
        )
    
    # Statistiques
    total_demandes = DemandeReabonnement.objects.filter(abonnement__type_service='CANAL').count()
    demandes_en_attente = DemandeReabonnement.objects.filter(
        abonnement__type_service='CANAL', 
        statut='EN_ATTENTE'
    ).count()
    demandes_traitees = DemandeReabonnement.objects.filter(
        abonnement__type_service='CANAL', 
        statut='TRAITEE'
    ).count()
    demandes_rejetees = DemandeReabonnement.objects.filter(
        abonnement__type_service='CANAL', 
        statut='REJETEE'
    ).count()
    
    # Clients pour le formulaire
    clients = CustomUser.objects.filter(
        Q(user_type='CLIENT') | Q(abonnements__type_service='CANAL')
    ).distinct()
    
    # Pagination
    items_per_page = int(request.GET.get('items', 10))
    paginator = Paginator(demandes, items_per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'demandes': page_obj,
        'total_demandes': total_demandes,
        'demandes_en_attente': demandes_en_attente,
        'demandes_traitees': demandes_traitees,
        'demandes_rejetees': demandes_rejetees,
        'clients': clients,
        'filter_statut': statut_filter,
        'filter_date_debut': date_debut,
        'filter_date_fin': date_fin,
        'filter_search': search_query,
        'items_per_page': items_per_page,
    }
    
    return render(request, 'administrations/gestion_reabonnements.html', context)

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def details_demande_reabonnement(request, demande_id):
    """Vue pour afficher les détails d'une demande (AJAX)"""
    demande = get_object_or_404(
        DemandeReabonnement.objects.select_related(
            'abonnement', 'abonnement__client'
        ), 
        id=demande_id
    )
    
    # Vérifier si une facture existe pour cette demande
    facture_exists = Facture.objects.filter(demande=demande.abonnement).exists()
    
    return render(request, 'administrations/partials/demande_details.html', {
        'demande': demande,
        'facture_exists': facture_exists
    })

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def creer_demande_reabonnement(request):
    """Vue pour créer une nouvelle demande de réabonnement"""
    if request.method == 'POST':
        try:
            client_id = request.POST.get('client')
            identifiant_abonne = request.POST.get('identifiant_abonne')
            montant = request.POST.get('montant')
            offre_choisie = request.POST.get('offre_choisie')
            commentaires = request.POST.get('commentaires', '')
            
            # Validation des données
            if not all([client_id, identifiant_abonne, montant]):
                messages.error(request, "Tous les champs obligatoires doivent être remplis.")
                return redirect('gestion_reabonnements_canal')
            
            # Récupérer ou créer l'abonnement
            client = get_object_or_404(CustomUser, id=client_id)
            
            abonnement, created = Abonnement.objects.get_or_create(
                client=client,
                type_service='CANAL',
                identifiant_abonne=identifiant_abonne,
                defaults={'est_actif': True}
            )
            
            if not created:
                abonnement.est_actif = True
                abonnement.save()
            
            # Créer la demande de réabonnement
            demande = DemandeReabonnement.objects.create(
                abonnement=abonnement,
                montant=montant,
                offre_choisie=offre_choisie,
                commentaires=commentaires,
                statut='EN_ATTENTE'
            )
            
            messages.success(request, f"Demande de réabonnement #{demande.id} créée avec succès!")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la création de la demande: {str(e)}")
        
        return redirect('gestion_reabonnements_canal')
    
    return redirect('gestion_reabonnements_canal')

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def traiter_demande_reabonnement(request):
    """Vue pour traiter une demande de réabonnement"""
    if request.method == 'POST':
        try:
            demande_id = request.POST.get('demande_id')
            nouveau_statut = request.POST.get('nouveau_statut')
            commentaires = request.POST.get('commentaires', '')
            
            demande = get_object_or_404(DemandeReabonnement, id=demande_id)
            
            # Mettre à jour la demande
            demande.statut = nouveau_statut
            if commentaires:
                if demande.commentaires:
                    demande.commentaires += f"\n--- Traitement {timezone.now().strftime('%d/%m/%Y %H:%M')} ---\n{commentaires}"
                else:
                    demande.commentaires = f"Traitement {timezone.now().strftime('%d/%m/%Y %H:%M')}:\n{commentaires}"
            
            if nouveau_statut == 'TRAITEE':
                demande.date_traitement = timezone.now()
            
            demande.save()
            
            messages.success(request, f"Demande #{demande.id} mise à jour avec le statut: {demande.get_statut_display()}")
            
        except Exception as e:
            messages.error(request, f"Erreur lors du traitement de la demande: {str(e)}")
        
        return redirect('gestion_reabonnements_canal')
    
    return redirect('gestion_reabonnements_canal')

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def upload_facture_reabonnement(request):
    """Vue pour uploader une facture pour une demande"""
    if request.method == 'POST':
        try:
            demande_id = request.POST.get('demande_id')
            numero_facture = request.POST.get('numero_facture')
            date_echeance = request.POST.get('date_echeance')
            fichier_facture = request.FILES.get('fichier_facture')
            
            if not all([demande_id, numero_facture, date_echeance, fichier_facture]):
                messages.error(request, "Tous les champs doivent être remplis.")
                return redirect('gestion_reabonnements_canal')
            
            # Vérifier si le numéro de facture est unique
            if Facture.objects.filter(numero_facture=numero_facture).exists():
                messages.error(request, "Ce numéro de facture existe déjà.")
                return redirect('gestion_reabonnements_canal')
            
            # Récupérer la demande et l'abonnement associé
            demande_reabonnement = get_object_or_404(DemandeReabonnement, id=demande_id)
            abonnement = demande_reabonnement.abonnement
            
            # Vérifier la taille du fichier (max 10MB)
            if fichier_facture.size > 10 * 1024 * 1024:
                messages.error(request, "Le fichier est trop volumineux. Taille maximale: 10MB.")
                return redirect('gestion_reabonnements_canal')
            
            # Vérifier l'extension du fichier
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            file_extension = os.path.splitext(fichier_facture.name)[1].lower()
            if file_extension not in allowed_extensions:
                messages.error(request, "Type de fichier non supporté. Formats acceptés: PDF, JPG, PNG.")
                return redirect('gestion_reabonnements_canal')
            
            # Créer la facture
            facture = Facture.objects.create(
                demande=abonnement,
                numero_facture=numero_facture,
                fichier=fichier_facture,
                date_echeance=date_echeance,
                est_payee=False
            )
            
            # Mettre à jour le statut de la demande si nécessaire
            if demande_reabonnement.statut == 'EN_ATTENTE':
                demande_reabonnement.statut = 'EN_COURS'
                demande_reabonnement.save()
            
            messages.success(request, f"Facture {numero_facture} uploadée avec succès pour la demande #{demande_id}!")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de l'upload de la facture: {str(e)}")
        
        return redirect('gestion_reabonnements_canal')
    
    return redirect('gestion_reabonnements_canal')

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def supprimer_demande_reabonnement(request, demande_id):
    """Vue pour supprimer une demande de réabonnement"""
    if request.method == 'POST':
        try:
            demande = get_object_or_404(DemandeReabonnement, id=demande_id)
            demande_id = demande.id
            demande.delete()
            
            messages.success(request, f"Demande #{demande_id} supprimée avec succès!")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
    return redirect('gestion_reabonnements_canal')

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def telecharger_facture(request, facture_id):
    """Vue pour télécharger une facture"""
    facture = get_object_or_404(Facture, id=facture_id)
    
    # Vérifier les permissions (optionnel)
    # ...
    
    response = FileResponse(facture.fichier.open(), as_attachment=True, filename=facture.fichier.name)
    return response

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def statistiques_reabonnements(request):
    """Vue pour les statistiques détaillées des réabonnements"""
    # Statistiques par période
    aujourdhui = timezone.now().date()
    debut_semaine = aujourdhui - timedelta(days=aujourdhui.weekday())
    debut_mois = aujourdhui.replace(day=1)
    
    stats = {
        'semaine': DemandeReabonnement.objects.filter(
            abonnement__type_service='CANAL',
            date_demande__date__gte=debut_semaine
        ).count(),
        'mois': DemandeReabonnement.objects.filter(
            abonnement__type_service='CANAL',
            date_demande__date__gte=debut_mois
        ).count(),
        'total_montant': DemandeReabonnement.objects.filter(
            abonnement__type_service='CANAL',
            statut='TRAITEE'
        ).aggregate(Sum('montant'))['montant__sum'] or 0,
    }
    
    return JsonResponse(stats)

@login_required(login_url='login')
@user_passes_test(is_admin_user)
def get_client_abonnements(request, client_id):
    """Vue pour récupérer les abonnements d'un client (AJAX)"""
    client = get_object_or_404(CustomUser, id=client_id)
    abonnements = Abonnement.objects.filter(
        client=client, 
        type_service='CANAL'
    ).values('id', 'identifiant_abonne')
    
    return JsonResponse(list(abonnements), safe=False)





def finances_dashboard(request):
    """Tableau de bord financier avec graphiques et statistiques"""
    
    # Période par défaut (6 derniers mois)
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=180)
    
    # Revenus mensuels pour le graphique
    monthly_revenue = RevenueRecord.objects.filter(
        transaction_date__date__gte=start_date,
        transaction_date__date__lte=end_date,
        status='completed'
    ).annotate(
        month=TruncMonth('transaction_date')
    ).values('month').annotate(
        total_revenue=Sum('amount'),
        total_net=Sum('net_amount'),
        transaction_count=Count('id')
    ).order_by('month')
    
    # Préparer les données pour Chart.js
    months = [item['month'].strftime('%b %Y') for item in monthly_revenue]
    revenues = [float(item['total_revenue']) for item in monthly_revenue]
    net_revenues = [float(item['total_net']) for item in monthly_revenue]
    
    # Statistiques principales
    total_revenue = RevenueRecord.objects.filter(
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    monthly_revenue_current = RevenueRecord.objects.filter(
        transaction_date__month=end_date.month,
        transaction_date__year=end_date.year,
        status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    pending_payments = Payment.objects.filter(
        status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    active_subscriptions = Subscription.objects.filter(
        status='active'
    ).count()
    
    # Répartition par type de revenu
    revenue_by_type = RevenueRecord.objects.filter(
        status='completed'
    ).values('revenue_type').annotate(
        total=Sum('amount'),
        count=Count('id')
    )
    
    # Top zones par revenu
    top_zones = RevenueRecord.objects.filter(
        status='completed'
    ).values('zone__nom').annotate(
        total_revenue=Sum('amount')
    ).order_by('-total_revenue')[:5]
    
    # Derniers paiements
    recent_payments = Payment.objects.select_related(
        'subscription', 'subscription__user'
    ).order_by('-payment_date')[:10]
    
    # Croissance mensuelle
    growth_data = []
    for i in range(len(monthly_revenue)):
        if i > 0:
            prev_revenue = revenues[i-1]
            current_revenue = revenues[i]
            if prev_revenue > 0:
                growth = ((current_revenue - prev_revenue) / prev_revenue) * 100
            else:
                growth = 100 if current_revenue > 0 else 0
            growth_data.append(round(growth, 2))
        else:
            growth_data.append(0)
    
    context = {
        'page_title': 'Tableau de Bord Financier',
        'months_json': json.dumps(months),
        'revenues_json': json.dumps(revenues),
        'net_revenues_json': json.dumps(net_revenues),
        'growth_data_json': json.dumps(growth_data),
        'total_revenue': total_revenue,
        'monthly_revenue_current': monthly_revenue_current,
        'pending_payments': pending_payments,
        'active_subscriptions': active_subscriptions,
        'revenue_by_type': revenue_by_type,
        'top_zones': top_zones,
        'recent_payments': recent_payments,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'administrations/finances_dashboard.html', context)