from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.db import transaction
from django.utils import timezone
from .models import Abonnement, DemandeReabonnement, Facture, HistoriqueAbonnement, Notification, Subscription
from .services.payment import PaymentService
import json
from decimal import Decimal
from django.http import Http404
from django.conf import settings
import os

# Offres Canal+ pour le Cameroun
CANAL_PLUS_OFFERS = {
    'CANAL': [
        {'id': 'essentiel', 'name': 'Essentiel', 'price': 5000, 'description': 'Chaînes de base + Sports'},
        {'id': 'evasion', 'name': 'Évasion', 'price': 10000, 'description': 'Essentiel + Divertissement'},
        {'id': 'premium', 'name': 'Premium', 'price': 15000, 'description': 'Toutes les chaînes + Films'},
        {'id': 'super_sport', 'name': 'Super Sport', 'price': 25000, 'description': 'Sports complets + Premium'},
    ],
    'ENEO': [],
    'CAMWATER': []
}

@login_required(login_url='login')
def subscriptions_dashboard(request):
    """Tableau de bord des abonnements"""
    abonnements = Abonnement.objects.filter(client=request.user)
    demandes_recentes = DemandeReabonnement.objects.filter(
        abonnement__client=request.user
    ).select_related('abonnement').order_by('-date_demande')[:5]

    # Récupérer les factures associées à chaque abonnement
    factures = Facture.objects.filter(
        demande__in=abonnements
    ).select_related('demande')
    
    context = {
        'abonnements': abonnements,
        'demandes_recentes': demandes_recentes,
        'canal_offers': CANAL_PLUS_OFFERS['CANAL'],
        'factures': factures,
    }
    return render(request, 'subscriptions/dashboard.html', context)

@login_required(login_url='login')
def create_subscription(request):
    """Création d'un nouvel abonnement"""
    if request.method == 'POST':
        try:
            type_service = request.POST.get('type_service')
            identifiant_abonne = request.POST.get('identifiant_abonne')
            offre_choisie = request.POST.get('offre_choisie', '')
            
            print(f"DEBUG - Données reçues: service={type_service}, id={identifiant_abonne}, offre={offre_choisie}")
            
            # Validation
            if not all([type_service, identifiant_abonne]):
                messages.error(request, "Tous les champs obligatoires doivent être remplis")
                return redirect('create_subscription')
            
            # Pour Canal+, vérifier qu'une offre est choisie
            if type_service == 'CANAL' and not offre_choisie:
                messages.error(request, "Veuillez choisir une offre Canal+")
                return redirect('create_subscription')
            
            # Vérifier si l'abonnement existe déjà pour cet utilisateur
            if Abonnement.objects.filter(
                client=request.user,
                type_service=type_service, 
                identifiant_abonne=identifiant_abonne
            ).exists():
                messages.error(request, "Vous avez déjà un abonnement avec cet identifiant")
                return redirect('create_subscription')
            
            # Créer l'abonnement
            with transaction.atomic():
                abonnement = Abonnement.objects.create(
                    client=request.user,
                    type_service=type_service,
                    identifiant_abonne=identifiant_abonne
                )
                
                # Historique
                HistoriqueAbonnement.objects.create(
                    abonnement=abonnement,
                    action="Création d'abonnement",
                    details={
                        'type_service': type_service,
                        'identifiant': identifiant_abonne,
                        'offre_choisie': offre_choisie
                    }
                )
                
                # Notification
                Notification.create_notification(
                    user=request.user,
                    title="Abonnement créé",
                    message=f"Votre abonnement {abonnement.get_type_service_display()} a été créé avec succès",
                    notification_type='success',
                    related_object=abonnement,
                    action_url=f'/abonnements/'
                )
            
            messages.success(request, "Abonnement créé avec succès!")
            return redirect('subscriptions_dashboard_reabonnement')
            
        except Exception as e:
            print(f"DEBUG - Erreur: {str(e)}")
            messages.error(request, f"Erreur lors de la création: {str(e)}")
            return redirect('create_subscription')
    
    context = {
        'service_choices': (('CANAL', 'Canal+'), ('CANAL', 'Canal+')),
        'canal_offers': CANAL_PLUS_OFFERS['CANAL'],
    }
    return render(request, 'subscriptions/create_subscription.html', context)

@login_required(login_url='login')
def delete_subscription(request, subscription_id):
    """Suppression d'un abonnement"""
    abonnement = get_object_or_404(Abonnement, id=subscription_id, client=request.user)
    
    if request.method == 'POST':
        try:
            service_name = abonnement.get_type_service_display()
            
            with transaction.atomic():
                # Historique avant suppression
                HistoriqueAbonnement.objects.create(
                    abonnement=abonnement,
                    action="Suppression d'abonnement",
                    details={
                        'type_service': abonnement.type_service,
                        'identifiant': abonnement.identifiant_abonne
                    }
                )
                
                abonnement.delete()
                
                # Notification
                Notification.create_notification(
                    user=request.user,
                    title="Abonnement supprimé",
                    message=f"Votre abonnement {service_name} a été supprimé",
                    notification_type='info'
                )
            
            messages.success(request, "Abonnement supprimé avec succès")
            
        except Exception as e:
            messages.error(request, f"Erreur lors de la suppression: {str(e)}")
    
    return redirect('subscriptions_dashboard_reabonnement')

@login_required(login_url='login')
def create_renewal_request(request, subscription_id):
    """Création d'une demande de réabonnement"""
    abonnement = get_object_or_404(Abonnement, id=subscription_id, client=request.user)
    
    # Vérifier s'il existe déjà une demande en cours pour cet abonnement
    demande_existante = DemandeReabonnement.objects.filter(
        abonnement=abonnement,
        statut__in=['EN_ATTENTE', 'EN_COURS']
    ).first()
    
    if request.method == 'POST':
        try:
            # Si une demande existe déjà et n'est pas annulée, rediriger
            if demande_existante and demande_existante.statut != 'ANNULEE':
                messages.info(request, "Une demande est déjà en cours pour cet abonnement.")
                return redirect('create_renewal_request', subscription_id=subscription_id)
                
            offre_id = request.POST.get('offre_id')
            montant_input = request.POST.get('montant')
            
            print(f"DEBUG - Demande réabonnement: offre={offre_id}, montant={montant_input}")
            
            # Déterminer le montant selon le type de service
            if abonnement.type_service == 'CANAL':
                if not offre_id:
                    messages.error(request, "Veuillez choisir une offre Canal+")
                    return redirect('create_renewal_request', subscription_id=subscription_id)
                
                # Trouver l'offre Canal+ sélectionnée
                offre_data = next((offer for offer in CANAL_PLUS_OFFERS['CANAL'] if offer['id'] == offre_id), None)
                if not offre_data:
                    messages.error(request, "Offre Canal+ non valide")
                    return redirect('create_renewal_request', subscription_id=subscription_id)
                
                montant = Decimal(offre_data['price'])
                
            else:  # ENEO ou CAMWATER
                if not montant_input or Decimal(montant_input) <= 0:
                    messages.error(request, "Veuillez saisir un montant valide")
                    return redirect('create_renewal_request', subscription_id=subscription_id)
                
                montant = Decimal(montant_input)
                offre_id = None
            
            # Créer la demande
            with transaction.atomic():
                demande = DemandeReabonnement.objects.create(
                    abonnement=abonnement,
                    montant=montant,
                    offre_choisie=offre_id
                )
                
                # Historique
                HistoriqueAbonnement.objects.create(
                    abonnement=abonnement,
                    action="Demande de réabonnement",
                    details={
                        'demande_id': demande.id,
                        'montant': float(montant),
                        'offre_choisie': offre_id
                    }
                )
                
                # Notification
                Notification.create_notification(
                    user=request.user,
                    title="Demande de réabonnement",
                    message=f"Votre demande de réabonnement pour {abonnement.get_type_service_display()} a été créée",
                    notification_type='info',
                    related_object=demande,
                    action_url=f'/abonnements/demandes/{demande.id}/paiement/'
                )
            
            messages.success(request, "Demande créée avec succès! Veuillez procéder au paiement.")
            return redirect('process_payment', request_id=demande.id)
            
        except Exception as e:
            print(f"DEBUG - Erreur demande: {str(e)}")
            messages.error(request, f"Erreur lors de la demande: {str(e)}")
            return redirect('create_renewal_request', subscription_id=subscription_id)
    
    context = {
        'abonnement': abonnement,
        'offres': CANAL_PLUS_OFFERS.get(abonnement.type_service, []),
        'is_canal': abonnement.type_service == 'CANAL',
        'is_eneo_camwater': abonnement.type_service in ['ENEO', 'CAMWATER'],
        'demande_existante': demande_existante,
    }
    return render(request, 'subscriptions/create_renewal.html', context)


@login_required(login_url='login')
def process_payment(request, request_id):
    """Traitement du paiement pour une demande"""
    demande = get_object_or_404(
        DemandeReabonnement, 
        id=request_id, 
        abonnement__client=request.user
    )
    
    # Préparer les offres pour le template
    offres = CANAL_PLUS_OFFERS.get(demande.abonnement.type_service, [])
    
    if request.method == 'POST':
        try:
            phone_number = request.POST.get('phone_number')
            
            if not phone_number:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Le numéro de téléphone est obligatoire'
                    })
                messages.error(request, "Le numéro de téléphone est obligatoire")
                return redirect('process_payment', request_id=request_id)
            
            # Valider le format du numéro
            if not phone_number.isdigit() or len(phone_number) != 9:
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': 'Numéro de téléphone invalide. Format: 9 chiffres (ex: 677123456)'
                    })
                messages.error(request, "Numéro de téléphone invalide. Format: 9 chiffres (ex: 677123456)")
                return redirect('process_payment', request_id=request_id)
            
            payment_service = PaymentService()
            
            # Données pour le paiement
            subscription_data = {
                'plan_name': demande.abonnement.get_type_service_display(),
                'offre_id': demande.offre_choisie or '',
                'identifiant_abonne': demande.abonnement.identifiant_abonne
            }
            
            # Traitement du paiement avec votre fonction existante
            result = payment_service.process_subscription_payment_first(
                user=request.user,
                amount= 10, #float(demande.montant),
                service_name=demande.abonnement.type_service,
                phone_number=phone_number,
                subscription_data=subscription_data,
                subscription= Subscription.objects.filter(user=request.user).first()
            )
            
            # Votre fonction retourne déjà les notifications, on utilise simplement le résultat
            if result['success']:
                # Mettre à jour la demande
                demande.statut = 'COMPLETEE'  # Car process_subscription_payment_first est bloquant
                demande.telephone_paiement = phone_number
                if result.get('reference'):
                    demande.reference_paiement = result['reference']
                if result.get('transaction_id'):
                    demande.reference_paiement = result['transaction_id']
                demande.save()
                
                # Historique
                HistoriqueAbonnement.objects.create(
                    abonnement=demande.abonnement,
                    action="Paiement réussi",
                    details={
                        'demande_id': demande.id,
                        'montant': float(demande.montant),
                        'telephone': phone_number,
                        'reference': result.get('reference', result.get('transaction_id', '')),
                        'statut': 'COMPLETEE'
                    }
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': True,
                        'message': result.get('message', 'Paiement effectué avec succès!'),
                        'redirect_url': f'/abonnements/demandes/{demande.id}/statut/'
                    })
                
                messages.success(request, result.get('message', 'Paiement effectué avec succès!'))
                return redirect('check_payment_status', request_id=demande.id)
            else:
                # Historique d'erreur
                HistoriqueAbonnement.objects.create(
                    abonnement=demande.abonnement,
                    action="Erreur paiement",
                    details={
                        'demande_id': demande.id,
                        'erreur': result['message'],
                        'telephone': phone_number
                    }
                )
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({
                        'success': False,
                        'message': result['message']
                    })
                
                messages.error(request, result['message'])
                return redirect('process_payment', request_id=request_id)
                
        except Exception as e:
            error_message = f"Erreur lors du paiement: {str(e)}"
            print(f"DEBUG - Erreur paiement: {error_message}")
            
            # Historique d'erreur
            HistoriqueAbonnement.objects.create(
                abonnement=demande.abonnement,
                action="Erreur système paiement",
                details={
                    'demande_id': demande.id,
                    'erreur': str(e)
                }
            )
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'message': error_message
                })
            
            messages.error(request, error_message)
            return redirect('process_payment', request_id=request_id)
    
    context = {
        'demande': demande,
        'offres': offres,
    }
    
    # Si requête AJAX, retourner JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'success': False, 'message': 'Méthode non autorisée'})
    
    return render(request, 'subscriptions/payment.html', context)

@login_required(login_url='login')
def check_payment_status(request, request_id):
    """Vérification du statut du paiement"""
    demande = get_object_or_404(
        DemandeReabonnement, 
        id=request_id, 
        abonnement__client=request.user
    )
    
    # Pour process_subscription_payment_first (bloquant), le statut est déjà défini
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'status': demande.statut,
            'status_display': demande.get_statut_display(),
            'last_updated': demande.date_maj.isoformat() if demande.date_maj else demande.date_creation.isoformat()
        })
    
    context = {
        'demande': demande,
    }
    return render(request, 'subscriptions/payment_status.html', context)


@login_required
def download_facture(request, facture_id):
    """Télécharger une facture"""
    facture = get_object_or_404(
        Facture, 
        id=facture_id, 
        demande__client=request.user
    )
    
    if facture.fichier:
        file_path = facture.fichier.path
        if os.path.exists(file_path):
            with open(file_path, 'rb') as fh:
                response = HttpResponse(fh.read(), content_type="application/pdf")
                response['Content-Disposition'] = f'inline; filename="{os.path.basename(file_path)}"'
                return response
    
    raise Http404("Facture non trouvée")