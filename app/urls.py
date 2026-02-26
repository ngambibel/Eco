# accounts/urls.py
from django.urls import path

from EcoCity import settings
from django.conf.urls.static import static
from . import views, canal, admins, collecte_admin, client_admin, collectors



urlpatterns = [
   path('signup/', views.signup_view, name='signup'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('', views.accueil , name='dashboard'),

    path('abonnement/', views.subscription_page, name='subscription_page'),
    path('api/create-subscription/', views.create_subscription, name='create_subscription'),
    path('api/schedule/<uuid:subscription_id>/', views.get_subscription_schedule, name='get_schedule'),
    path('subscription/payment/', views.process_subscription_payment, name='process_subscription_payment'),
    path('subscription/payment/verify/', views.verify_payment_status, name='verify_payment_status'),

    # Tableau de bord des abonnements
    path('mes-abonnements/', views.subscriptions_dashboard, name='subscriptions_dashboard'),
    
    # Détail d'un abonnement
    path('abonnement/<uuid:subscription_id>/', views.subscription_detail, name='subscription_detail'),
    
    # Modification d'un abonnement
    path('abonnement/<uuid:subscription_id>/modifier/', views.edit_subscription, name='edit_subscription'),
    
    # Mise à jour asynchrone (pour AJAX)
    path('abonnement/<uuid:subscription_id>/mise-a-jour/', views.update_subscription, name='update_subscription'),
    path('abonnement/<uuid:subscription_id>/suspendre/', views.suspend_subscription, name='suspend_subscription'),

    
    
    path('api/zones/<uuid:zone_id>/schedule/', views.get_zone_schedule, name='get_zone_schedule'),

    path('subscription/<uuid:subscription_id>/renew-with-payment/', views.renew_subscription_with_payment, name='renew_subscription_with_payment'),
    path('subscription/process-renewal/', views.process_renewal_after_payment, name='process_renewal_after_payment'),
    path('subscription/check-renewal-status/', views.check_renewal_status, name='check_renewal_status'),


    # QR Code URLs
    path('subscription/<uuid:subscription_id>/qr-code/', views.generate_qr_code_view, name='generate_qr_code'),
    path('subscription/<uuid:subscription_id>/download-qr/', views.download_qr_code, name='download_qr_code'),
    path('subscription/qr-renew/<str:token>/', views.qr_renewal_gateway, name='qr_renewal_gateway'),
    path('check-status/', views.check_qr_renewal_status, name='check_qr_renewal_status'),
    path('subscription/qr-renew/success/<str:token>/', views.qr_renewal_success, name='qr_renewal_success'),


    # url des zone de disponibilité
    path('zones-programmes/', views.ZonesProgrammesView.as_view(), name='zones_programmes'),

    #les urls pour les notifications
    path('notifications/', views.notification_list, name='notification_list'),
    path('mark-all-read/', views.mark_all_as_read, name='mark_all_read'),
    path('<uuid:notification_id>/mark-read/', views.mark_as_read, name='mark_as_read'),
    path('api/unread-count/', views.get_unread_count, name='unread_count'),
    path('api/recent/', views.get_recent_notifications, name='recent_notifications'),


    # les urls pour les demandes de reabonnement
    path('reabonnements/', canal.subscriptions_dashboard, name='subscriptions_dashboard_reabonnement'),
    path('reabonnements/creer/', canal.create_subscription, name='create_subscription'),
    path('reabonnements/<int:subscription_id>/supprimer/', canal.delete_subscription, name='delete_subscription'),
    path('reabonnements/<int:subscription_id>/reabonnement/', canal.create_renewal_request, name='create_renewal_request'),
    path('reabonnements/demandes/<int:request_id>/paiement/', canal.process_payment, name='process_payment'),
    path('reabonnements/demandes/<int:request_id>/statut/', canal.check_payment_status, name='check_payment_status'),
    path('factures/<int:facture_id>/telecharger/', canal.download_facture, name='download_facture'),


    # les vues pour le tableau de bord administrateur
    path('admins/dashboard/', admins.DashboardView.as_view(), name='admin_dashboard'),
    # Page principale pour le reabonnement canal    
    path('reabonnements-canal/', admins.gestion_reabonnements_canal, name='gestion_reabonnements_canal'),
    # url pour exporter les numeros de tel des clients ayant une demande de reabonement
     path('export-reabonnements-utilisateurs/', admins.export_reabonnements_utilisateurs_xls, name='export_reabonnements_utilisateurs'),
     path('export-clients/', admins.export_clients_xls, name='export_clients'),
    
    # Actions sur les demandes
    path('demandes/creer/', admins.creer_demande_reabonnement, name='creer_demande_reabonnement'),
    path('<int:demande_id>/details/', admins.details_demande_reabonnement, name='details_demande_reabonnement'),
    path('demandes/traiter/', admins.traiter_demande_reabonnement, name='traiter_demande_reabonnement'),
    path('demandes/<int:demande_id>/supprimer/', admins.supprimer_demande_reabonnement, name='supprimer_demande_reabonnement'),
    
    # Gestion des factures
    path('factures/upload/', admins.upload_facture_reabonnement, name='upload_facture_reabonnement'),
    path('factures/<int:facture_id>/telecharger/', admins.telecharger_facture, name='telecharger_facture'),
    
    # Données AJAX
    path('statistiques/', admins.statistiques_reabonnements, name='statistiques_reabonnements'),
    path('clients/<int:client_id>/abonnements/', admins.get_client_abonnements, name='get_client_abonnements'),

    # urls des finances 
    path('finances/', admins.finances_dashboard, name='finances_dashboard'),

    # API URLs pour la gestion des zones, tricycles et programmes
    path('gestion-collecte/', collecte_admin.GestionCollecteView.as_view(), name='gestion_collecte'),
    
    # API Zones
    path('api/zones/', collecte_admin.ZoneListCreateAPIView.as_view(), name='api_zones'),
    path('api/zones/<uuid:pk>/', collecte_admin.ZoneRetrieveUpdateDestroyAPIView.as_view(), name='api_zone_detail'),
    path('api/zones/active/', collecte_admin.ActiveZoneListAPIView.as_view(), name='api_zones_active'),
    
    # API Tricycles
    path('api/tricycles/', collecte_admin.TricycleListCreateAPIView.as_view(), name='api_tricycles'),
    path('api/tricycles/<uuid:pk>/', collecte_admin.TricycleRetrieveUpdateDestroyAPIView.as_view(), name='api_tricycle_detail'),
    path('api/tricycles/active/', collecte_admin.ActiveTricycleListAPIView.as_view(), name='api_tricycles_active'),
    
    # API Programmes
    path('api/programs/', collecte_admin.ProgrammeTricycleListCreateAPIView.as_view(), name='api_programs'),
    path('api/programs/<uuid:pk>/', collecte_admin.ProgrammeTricycleRetrieveUpdateDestroyAPIView.as_view(), name='api_program_detail'),
    
    # API Jours de collecte
    path('api/collection-days/', collecte_admin.CollectionDayListCreateAPIView.as_view(), name='api_collection_days'),
    path('api/collection-days/<int:pk>/', collecte_admin.CollectionDayRetrieveUpdateDestroyAPIView.as_view(), name='api_collection_day_detail'),
    
    # API Données de formulaire
    path('api/cities/', collecte_admin.CityListAPIView.as_view(), name='api_cities'),
    path('api/collectors/', collecte_admin.CollectorListAPIView.as_view(), name='api_collectors'),

    # urls de gestion des utilisateurs et des abonement 
    path('administrations/export-abonnements-expirant/', client_admin.export_abonnements_expirant, name='export_abonnements_expirant'),
    path('api/abonnements-expirant-stats/', client_admin.get_abonnements_expirant_stats, name='abonnements_expirant_stats'),

    path('gestion-abonnements/', client_admin.gestion_abonnements, name='gestion_abonnements'),
    path('gestion-abonnements/ajouter-utilisateur/', client_admin.ajouter_utilisateur, name='ajouter_utilisateur'),
    path('gestion-abonnements/editer-utilisateur/', client_admin.editer_utilisateur, name='editer_utilisateur'),
    path('gestion-abonnements/supprimer-utilisateur/<uuid:user_id>/', client_admin.supprimer_utilisateur, name='supprimer_utilisateur'),
    path('gestion-abonnements/editer-abonnement/', client_admin.editer_abonnement, name='editer_abonnement'),
    path('gestion-abonnements/supprimer-abonnement/<uuid:subscription_id>/', client_admin.supprimer_abonnement, name='supprimer_abonnement'),
    path('gestion-abonnements/generer-qr/<uuid:subscription_id>/', client_admin.generer_qr_code, name='generer_qr_code'),
    path('gestion-abonnements/telecharger-qr/<uuid:subscription_id>/', client_admin.telecharger_qr_code, name='telecharger_qr_code'),
    
    # Gestion de la collecte
    path('gestion-collecte/', client_admin.gestion_collecte, name='gestion_collecte'),
    # url de generation de qr code 
    path('administrations/gestion-abonnements/recuperer-qr/<uuid:subscription_id>/', client_admin.recuperer_qr_code, name='recuperer_qr_code'),
    
    # Réabonnements Canal+
    
    
    # API pour les données AJAX
    path('api/utilisateurs/', client_admin.api_utilisateurs, name='api_utilisateurs'),
    path('api/abonnements/', client_admin.api_abonnements, name='api_abonnements'),
    path('api/statistiques/', client_admin.api_statistiques, name='api_statistiques'),
    
    # Détails
    path('utilisateur/<uuid:user_id>/', client_admin.detail_utilisateur, name='detail_utilisateur'),
    path('abonnement/<uuid:subscription_id>/', client_admin.detail_abonnement, name='detail_abonnement'),

    # les urls des tricycles pour les collecteurs
      # Pages principales
    path('dashboard_collector/', collectors.collector_dashboard, name='collector_dashboard'),
    path('daily-schedule/', collectors.daily_schedule, name='daily_schedule'),
    path('weekly-schedule/', collectors.weekly_schedule, name='weekly_schedule'),
    path('history/', collectors.collection_history, name='collection_history'),
    path('api/collections/by-distance/', collectors.get_sorted_collections_by_distance, name='api_collections_by_distance'),
    
    # Gestion des collectes
   
    path('collection/complete/', collectors.complete_collection, name='complete_collection'),
    path('collection/details/', collectors.collection_details, name='collection_details'),
    
    # Profil et préférences
    path('profile/', collectors.collector_profile, name='collector_profile'),
    path('profile/update/', collectors.update_profile, name='update_profile'),
    path('profile/change-password/', collectors.change_password, name='change_password'),
    path('profile/preferences/', collectors.update_preferences, name='update_preferences'),
    
    # Tricycle
    path('tricycle/', collectors.collector_tricycle, name='collector_tricycle'),
    
    # APIs AJAX
    path('api/stats/', collectors.api_collection_stats, name='api_collection_stats'),
    path('api/collection/<uuid:collection_id>/start/', collectors.api_start_collection, name='api_start_collection'),
    path('api/collection/<uuid:collection_id>/complete/', collectors.api_complete_collection, name='api_complete_collection'),


  
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)




