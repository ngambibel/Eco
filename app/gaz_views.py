from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.utils import timezone
import json
import uuid
from .models import *

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator

from datetime import date, timedelta, datetime



@csrf_exempt
@require_POST
def quick_gas_order(request):
    """
    Vue pour les commandes rapides de gaz sans authentification
    Utilise l'ID de subscription pour identifier l'utilisateur
    """
    try:
        data = json.loads(request.body)
        
        # Récupérer les données du formulaire
        subscription_id = data.get('subscription_id')
        product_id = data.get('product_id')
        phone_number = data.get('phone_number')
        network = data.get('network')
        delivery_address = data.get('delivery_address')
        city = data.get('city')
        quantity = int(data.get('quantity', 1))
        
        # Validation de base
        if not all([subscription_id, product_id, phone_number, network, delivery_address, city]):
            return JsonResponse({
                'success': False,
                'error': 'Tous les champs sont requis'
            }, status=400)
        
        # Vérifier le format du téléphone
        if not phone_number or not phone_number.startswith('6') or len(phone_number) != 9:
            return JsonResponse({
                'success': False,
                'error': 'Numéro de téléphone invalide. Format: 6XXXXXXXX'
            }, status=400)
        
        # Récupérer la subscription et l'utilisateur associé
        from .models import Subscription
        try:
            subscription = Subscription.objects.get(id=subscription_id)
            user = subscription.user  # L'utilisateur associé à l'abonnement
        except Subscription.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Abonnement non trouvé'
            }, status=404)
        
        # Récupérer le produit
        from .models import GasProduct
        product = get_object_or_404(GasProduct, id=product_id, is_available=True)
        
        # Vérifier le stock
        if product.stock_available < quantity:
            return JsonResponse({
                'success': False,
                'error': f'Stock insuffisant. Disponible: {product.stock_available}'
            }, status=400)
        
        # Créer ou récupérer l'adresse
        from .models import Address
        address= Address.objects.filter(
            user=user
        ).first()
        
        # Déterminer la zone (basée sur la ville)
        from .models import Zone
        zone = subscription.zone 
        
        # Créer la commande
        from .models import GasOrder, GasOrderItem
        order = GasOrder.objects.create(
            customer=user,
            address=address,
            zone=zone,
            delivery_type='standard',
            payment_method='mobile_money',
            payment_status='pending',
            status='pending',
            delivery_fee=1000,  # Frais de livraison par défaut
            tax_amount=0
        )
        
        # Créer l'item de commande
        order_item = GasOrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=product.price,
            unit_deposit=product.deposit_price
        )
        
        # Calculer les totaux
        subtotal = quantity * product.price
        total_deposit = quantity * product.deposit_price
        total_amount = subtotal + order.delivery_fee + order.tax_amount
        
        order.subtotal = subtotal
        order.total_deposit = total_deposit
        order.total_amount = total_amount
        order.save()
        
        # Réduire le stock
        product.stock_available -= quantity
        product.save()
        
        return JsonResponse({
            'success': True,
            'order_id': str(order.id),
            'order_number': order.order_number,
            'total_amount': float(total_amount),
            'message': 'Commande créée avec succès! Vous serez contacté pour la confirmation.'
        })
        
    except GasProduct.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Produit non trouvé'
        }, status=404)
    except Exception as e:
        import traceback
        print(f"Erreur dans quick_gas_order: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@csrf_exempt
def get_gas_products(request):
    """
    API pour récupérer les produits de gaz disponibles
    """
    try:
        products = GasProduct.objects.filter(is_available=True, stock_available__gt=0)
        products_list = []
        
        for product in products:
            products_list.append({
                'id': str(product.id),
                'name': str(product),
                'gaz_type': product.get_gaz_type_display(),
                'size_kg': product.size_kg,
                'price': float(product.price),
                'deposit_price': float(product.deposit_price),
                'total_price': float(product.total_price),
                'stock_available': product.stock_available,
                'image': product.image.url if product.image else None
            })
        
        return JsonResponse({
            'success': True,
            'products': products_list
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)



    
# collectors/gas_views.py


@login_required
def gas_deliveries_today(request):
    """Vue pour afficher les livraisons de gaz du jour"""
    collector = request.user
    today = timezone.now().date()
    
    # Vérifier si le collecteur a un tricycle assigné
    tricycle = collector.tricycle_set.filter(status='active').first()
    
  
    
    deliveries = GasOrder.objects.filter(
            
            created_at__date=today,
            
        ).select_related('customer', 'address', 'zone').prefetch_related('items__product')
    
    # Statistiques
    stats = {
        'total': deliveries.count(),
        'confirmed': deliveries.filter(status='confirmed').count(),
        'preparing': deliveries.filter(status='pending').count(),
        'assigned': deliveries.filter(status='assigned').count(),
        'in_transit': deliveries.filter(status='in_transit').count(),
    }
    
    context = {
        'deliveries': deliveries,
        'stats': stats,
        'today': today,
        'tricycle': tricycle,
        'today_gas_count': deliveries.count(),
    }
    
    return render(request, 'collectors/deliveries_today.html', context)


@login_required
def gas_deliveries_assigned(request):
    """Vue pour afficher les livraisons assignées au collecteur"""
    collector = request.user
    
    # Commandes assignées à ce collecteur
    deliveries = GasOrder.objects.filter(
        assigned_collector=collector
    ).exclude(
        status__in=['delivered', 'cancelled', 'failed']
    ).select_related('customer', 'address', 'zone').prefetch_related('items__product').order_by('scheduled_date', 'scheduled_time_slot')
    
    # Grouper par statut
    pending = deliveries.filter(status='pending')
    confirmed = deliveries.filter(status='confirmed')
    preparing = deliveries.filter(status='preparing')
    assigned = deliveries.filter(status='assigned')
    in_transit = deliveries.filter(status='in_transit')
    
    # Statistiques
    stats = {
        'total': deliveries.count(),
        'pending': pending.count(),
        'confirmed': confirmed.count(),
        'preparing': preparing.count(),
        'assigned': assigned.count(),
        'in_transit': in_transit.count(),
    }
    
    context = {
        'pending': pending,
        'confirmed': confirmed,
        'preparing': preparing,
        'assigned': assigned,
        'in_transit': in_transit,
        'stats': stats,
        'assigned_gas_count': deliveries.count(),
    }
    
    return render(request, 'collectors/deliveries_assigned.html', context)


@login_required
def gas_delivery_history(request):
    """Vue pour l'historique des livraisons"""
    collector = request.user
    
    # Récupérer tous les paramètres de filtre
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search = request.GET.get('search', '')
    
    # Requête de base
    deliveries = GasOrder.objects.filter(
        assigned_collector=collector
    ).select_related('customer', 'address', 'zone').prefetch_related('items__product').order_by('-delivery_date', '-order_date')
    
    # Appliquer les filtres
    if status_filter:
        deliveries = deliveries.filter(status=status_filter)
    
    if date_from:
        deliveries = deliveries.filter(delivery_date__date__gte=date_from)
    
    if date_to:
        deliveries = deliveries.filter(delivery_date__date__lte=date_to)
    
    if search:
        deliveries = deliveries.filter(
            Q(order_number__icontains=search) |
            Q(customer__username__icontains=search) |
            Q(customer__first_name__icontains=search) |
            Q(customer__last_name__icontains=search) |
            Q(address__street__icontains=search)
        )
    
    # Pagination
    paginator = Paginator(deliveries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistiques
    total_delivered = deliveries.filter(status='delivered').count()
    total_cancelled = deliveries.filter(status='cancelled').count()
    total_revenue = deliveries.filter(status='delivered').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search': search,
        'total_delivered': total_delivered,
        'total_cancelled': total_cancelled,
        'total_revenue': total_revenue,
        'status_choices': GasOrder.ORDER_STATUS_CHOICES,
    }
    
    return render(request, 'collectors/delivery_history.html', context)


@login_required
def gas_inventory(request):
    """Vue pour l'inventaire de gaz du collecteur"""
    collector = request.user
    
    # Récupérer le tricycle du collecteur
    tricycle = collector.tricycle_set.filter(status='active').first()
    
    if not tricycle:
        messages.warning(request, "Vous n'avez pas de tricycle actif assigné.")
        return render(request, 'collectors/gas/inventory.html', {'has_tricycle': False})
    
    # Récupérer l'inventaire
    inventory_items = GasInventory.objects.filter(
        tricycle=tricycle
    ).select_related('product').order_by('product__gaz_type', 'product__size_kg')
    
    # Récupérer les bouteilles physiques
    cylinders = GasCylinder.objects.filter(
        Q(status='in_transit', current_owner=collector) |
        Q(status='with_customer', current_owner=collector)
    ).select_related('product')
    
    # Grouper par statut
    cylinders_in_transit = cylinders.filter(status='in_transit')
    cylinders_with_customer = cylinders.filter(status='with_customer')
    
    # Statistiques
    stats = {
        'total_products': inventory_items.count(),
        'total_cylinders': cylinders.count(),
        'in_transit': cylinders_in_transit.count(),
        'with_customer': cylinders_with_customer.count(),
        'total_value': sum(item.quantity_available * item.product.price for item in inventory_items),
    }
    
    context = {
        'has_tricycle': True,
        'tricycle': tricycle,
        'inventory_items': inventory_items,
        'cylinders_in_transit': cylinders_in_transit,
        'cylinders_with_customer': cylinders_with_customer,
        'stats': stats,
    }
    
    return render(request, 'collectors/inventory.html', context)


@login_required
def gas_delivery_detail(request, order_id):
    """Vue pour afficher les détails d'une livraison"""
    collector = request.user
    
    order = get_object_or_404(
        GasOrder,
        id=order_id
    )
    
   
    
    # Récupérer les bouteilles assignées
    cylinders = []
    for item in order.items.all():
        cylinders.extend(item.assigned_cylinders.all())
    
    # Récupérer le suivi le plus récent
    latest_tracking = order.tracking_updates.first()
    
    context = {
        'order': order,
        'cylinders': cylinders,
        'latest_tracking': latest_tracking,
        'can_start': order.status in ['assigned', 'preparing'],
        'can_complete': order.status == 'in_transit',
        'status_choices': GasOrder.ORDER_STATUS_CHOICES,  
    }
    
    return render(request, 'collectors/delivery_detail.html', context)


@login_required
@require_http_methods(['POST'])
def start_gas_delivery(request, order_id):
    """API pour démarrer une livraison"""
    collector = request.user
    
    try:
        order = GasOrder.objects.get(id=order_id, assigned_collector=collector)
        
        if order.status not in ['assigned', 'preparing']:
            return JsonResponse({
                'success': False,
                'error': 'Cette commande ne peut pas être démarrée'
            }, status=400)
        
        # Mettre à jour le statut
        order.status = 'in_transit'
        order.pickup_date = timezone.now()
        order.save()
        
        # Créer une entrée de suivi
        tracking = GasDeliveryTracking.objects.create(
            order=order,
            status='in_transit',
            notes="Livraison démarrée par le collecteur"
        )
        
        # Notifier le client
        Notification.create_notification(
            user=order.customer,
            title="Livraison en route",
            message=f"Votre commande {order.order_number} est en cours de livraison",
            notification_type='info',
            related_object=order,
            action_url=f'/gas/orders/{order.id}/'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison démarrée avec succès',
            'tracking_id': str(tracking.id)
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(['POST'])
def complete_gas_delivery(request, order_id):
    """API pour compléter une livraison"""
    collector = request.user
    
    try:
        order = GasOrder.objects.get(id=order_id, assigned_collector=collector)
        
        if order.status != 'in_transit':
            return JsonResponse({
                'success': False,
                'error': 'Cette commande ne peut pas être complétée'
            }, status=400)
        
        # Traiter les données de la requête
        data = json.loads(request.body)
        recipient_name = data.get('recipient_name', '')
        notes = data.get('notes', '')
        
        # Mettre à jour le statut
        order.status = 'delivered'
        order.delivery_date = timezone.now()
        order.save()
        
        # Créer une entrée de suivi
        tracking = GasDeliveryTracking.objects.create(
            order=order,
            status='delivered',
            notes=f"Livrée à {recipient_name}. {notes}"
        )
        
        # Mettre à jour le statut des bouteilles
        for item in order.items.all():
            for cylinder in item.assigned_cylinders.all():
                cylinder.status = 'with_customer'
                cylinder.current_owner = order.customer
                cylinder.save()
        
        # Notifier le client
        Notification.create_notification(
            user=order.customer,
            title="Commande livrée",
            message=f"Votre commande {order.order_number} a été livrée avec succès",
            notification_type='success',
            related_object=order,
            action_url=f'/gas/orders/{order.id}/'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Livraison complétée avec succès'
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(['POST'])
def update_delivery_location(request, order_id):
    """API pour mettre à jour la localisation d'une livraison"""
    collector = request.user
    
    try:
        order = GasOrder.objects.get(id=order_id, assigned_collector=collector)
        
        if order.status != 'in_transit':
            return JsonResponse({
                'success': False,
                'error': 'Cette commande n\'est pas en cours de livraison'
            }, status=400)
        
        data = json.loads(request.body)
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        
        if not latitude or not longitude:
            return JsonResponse({
                'success': False,
                'error': 'Coordonnées requises'
            }, status=400)
        
        # Créer une entrée de suivi
        tracking = GasDeliveryTracking.objects.create(
            order=order,
            status='in_transit',
            latitude=latitude,
            longitude=longitude,
            notes="Mise à jour de localisation"
        )
        
        # Calculer le temps estimé d'arrivée (simplifié)
        # Dans une vraie application, utiliser un service de géocodage
        estimated_arrival = timezone.now() + timedelta(minutes=15)
        tracking.estimated_arrival = estimated_arrival
        tracking.save(update_fields=['estimated_arrival'])
        
        return JsonResponse({
            'success': True,
            'message': 'Localisation mise à jour',
            'estimated_arrival': estimated_arrival.isoformat()
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def scan_cylinder_qr(request):
    """Vue pour scanner le QR code d'une bouteille"""
    if request.method == 'POST':
        data = json.loads(request.body)
        cylinder_id = data.get('cylinder_id')
        order_id = data.get('order_id')
        
        try:
            cylinder = GasCylinder.objects.get(id=cylinder_id)
            order = GasOrder.objects.get(id=order_id, assigned_collector=request.user)
            
            # Vérifier si la bouteille est assignée à cette commande
            is_assigned = GasOrderItem.objects.filter(
                order=order,
                assigned_cylinders=cylinder
            ).exists()
            
            if not is_assigned:
                return JsonResponse({
                    'success': False,
                    'error': 'Cette bouteille n\'est pas assignée à cette commande'
                }, status=400)
            
            return JsonResponse({
                'success': True,
                'cylinder': {
                    'id': str(cylinder.id),
                    'serial_number': cylinder.serial_number,
                    'product': str(cylinder.product),
                    'status': cylinder.get_status_display(),
                }
            })
            
        except GasCylinder.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Bouteille non trouvée'
            }, status=404)
        except GasOrder.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Commande non trouvée'
            }, status=404)
    
    return render(request, 'collectors/scan_cylinder.html')


@login_required
def gas_delivery_stats_api(request):
    """API pour les statistiques en temps réel"""
    collector = request.user
    
    today = timezone.now().date()
    
    # Statistiques du jour
    today_deliveries = GasOrder.objects.filter(
        assigned_collector=collector,
        scheduled_date=today
    )
    
    # Commandes en cours
    active_deliveries = GasOrder.objects.filter(
        assigned_collector=collector,
        status__in=['assigned', 'in_transit']
    )
    
    # Commandes complétées aujourd'hui
    completed_today = today_deliveries.filter(status='delivered').count()
    
    # Bouteilles en transit
    cylinders_in_transit = GasCylinder.objects.filter(
        current_owner=collector,
        status='in_transit'
    ).count()
    
    # Performance (temps moyen de livraison)
    completed_orders = GasOrder.objects.filter(
        assigned_collector=collector,
        status='delivered',
        delivery_date__isnull=False,
        pickup_date__isnull=False
    ).exclude(
        pickup_date__isnull=True
    )
    
    avg_delivery_time = None
    if completed_orders.exists():
        total_time = sum(
            (order.delivery_date - order.pickup_date).total_seconds() / 60
            for order in completed_orders
        )
        avg_delivery_time = round(total_time / completed_orders.count(), 2)
    
    return JsonResponse({
        'today_total': today_deliveries.count(),
        'today_completed': completed_today,
        'active_deliveries': active_deliveries.count(),
        'cylinders_in_transit': cylinders_in_transit,
        'avg_delivery_time': avg_delivery_time,
        'timestamp': timezone.now().isoformat(),
    })



@login_required
@require_http_methods(['POST'])
def update_gas_order_status(request, order_id):
    """
    Vue pour mettre à jour le statut d'une commande de gaz
    """
    collector = request.user
    
    try:
        order = get_object_or_404(GasOrder, id=order_id)
        data = json.loads(request.body)
        
        new_status = data.get('status')
        notes = data.get('notes', '')
        
        if not new_status:
            return JsonResponse({
                'success': False,
                'error': 'Le statut est requis'
            }, status=400)
        
        # Vérifier si le nouveau statut est valide
        valid_statuses = [status[0] for status in GasOrder.ORDER_STATUS_CHOICES]
        if new_status not in valid_statuses:
            return JsonResponse({
                'success': False,
                'error': 'Statut invalide'
            }, status=400)
        
        # Vérifier la transition de statut
        old_status = order.status
        
        # Logique de validation des transitions
        invalid_transitions = {
            'delivered': ['cancelled', 'failed'],  # Une fois livrée, ne peut pas être annulée
            'cancelled': ['delivered', 'in_transit'],  # Une fois annulée, ne peut pas changer
            'failed': ['delivered', 'in_transit'],  # Une fois échouée, ne peut pas changer
        }
        
        if old_status in invalid_transitions and new_status in invalid_transitions[old_status]:
            return JsonResponse({
                'success': False,
                'error': f'Transition de statut invalide: de {old_status} vers {new_status}'
            }, status=400)
        
        # Mettre à jour le statut
        order.status = new_status
        order.notes = notes
        
        # Mettre à jour les dates en fonction du statut
        if new_status == 'confirmed' and not order.confirmation_date:
            order.confirmation_date = timezone.now()
        elif new_status == 'preparing' and not order.preparation_date:
            order.preparation_date = timezone.now()
        elif new_status == 'in_transit' and not order.pickup_date:
            order.pickup_date = timezone.now()
        elif new_status == 'delivered' and not order.delivery_date:
            order.delivery_date = timezone.now()
        
        order.save()
        
        # Créer une entrée de suivi
        tracking = GasDeliveryTracking.objects.create(
            order=order,
            status=new_status,
            notes=f"Statut mis à jour par {collector.get_full_name() or collector.username}. {notes}"
        )
        
        # Notifier le client si nécessaire
        if new_status in ['confirmed', 'in_transit', 'delivered', 'cancelled', 'failed']:
            notification_messages = {
                'confirmed': "Votre commande a été confirmée et sera bientôt préparée.",
                'in_transit': "Votre commande est en cours de livraison.",
                'delivered': "Votre commande a été livrée avec succès.",
                'cancelled': "Votre commande a été annulée.",
                'failed': "Un problème est survenu avec votre commande. Notre équipe vous contactera.",
            }
            
            if new_status in notification_messages:
                Notification.create_notification(
                    user=order.customer,
                    title=f"Commande {order.order_number} - {order.get_status_display()}",
                    message=notification_messages[new_status],
                    notification_type='info' if new_status in ['confirmed', 'in_transit'] else 
                                 ('success' if new_status == 'delivered' else 'warning'),
                    related_object=order,
                    action_url=f'/gas/orders/{order.id}/'
                )
        
        # Si la commande est livrée, mettre à jour les bouteilles
        if new_status == 'delivered':
            for item in order.items.all():
                for cylinder in item.assigned_cylinders.all():
                    cylinder.status = 'with_customer'
                    cylinder.current_owner = order.customer
                    cylinder.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Statut mis à jour avec succès',
            'new_status': order.get_status_display(),
            'tracking_id': str(tracking.id)
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée ou non assignée'
        }, status=404)
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Données JSON invalides'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(['POST'])
def report_delivery_problem(request, order_id):
    """
    Vue pour signaler un problème sur une livraison
    """
    collector = request.user
    
    try:
        order = get_object_or_404(GasOrder, id=order_id, assigned_collector=collector)
        data = json.loads(request.body)
        
        problem_type = data.get('problem_type')
        description = data.get('description')
        
        if not problem_type or not description:
            return JsonResponse({
                'success': False,
                'error': 'Type de problème et description requis'
            }, status=400)
        
        # Mettre à jour le statut de la commande
        order.status = 'failed'
        order.notes = f"Problème signalé: {problem_type}\nDescription: {description}\n{order.notes or ''}"
        order.save()
        
        # Créer une entrée de suivi
        tracking = GasDeliveryTracking.objects.create(
            order=order,
            status='failed',
            notes=f"Problème signalé par {collector.get_full_name() or collector.username}: {problem_type} - {description}"
        )
        
        # Notifier l'administrateur (optionnel)
        # Ici vous pouvez ajouter une notification pour les admins
        
        # Notifier le client
        Notification.create_notification(
            user=order.customer,
            title=f"Problème sur la commande {order.order_number}",
            message="Un problème est survenu lors de votre livraison. Notre équipe vous contactera sous peu.",
            notification_type='warning',
            related_object=order,
            action_url=f'/gas/orders/{order.id}/'
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Problème signalé avec succès',
            'tracking_id': str(tracking.id)
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée ou non assignée'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def check_order_status_api(request, order_id):
    """
    API pour vérifier si le statut d'une commande a changé
    """
    collector = request.user
    
    try:
        order = get_object_or_404(GasOrder, id=order_id, assigned_collector=collector)
        
        # Récupérer le dernier timestamp de mise à jour depuis la requête
        last_check = request.GET.get('last_check')
        
        # Vérifier si le statut a changé depuis le dernier check
        status_changed = False
        if last_check:
            try:
                last_check_date = datetime.fromisoformat(last_check.replace('Z', '+00:00'))
                if order.updated_at > last_check_date:
                    status_changed = True
            except:
                pass
        
        return JsonResponse({
            'success': True,
            'order_id': str(order.id),
            'current_status': order.status,
            'status_display': order.get_status_display(),
            'status_changed': status_changed,
            'updated_at': order.updated_at.isoformat(),
            'can_start': order.status in ['assigned', 'preparing'],
            'can_complete': order.status == 'in_transit',
        })
        
    except GasOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Commande non trouvée'
        }, status=404)