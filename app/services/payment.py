import logging
from datetime import datetime
from django.conf import settings
from campay.sdk import Client
from app.models import Notification, Payment, Subscription, Withdrawal
from django.db import models


logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        self.client = Client({
            "app_username": "HyGJKtSsjFqCBpf5NTxtWPT5pwAFk7jFc0VW0bylHKXzsbPmt2RED6rQtnu9HtedR1hOhEvC41vIeQR666FusQ",
            "app_password": "pivVF5QYjQOEDWeQW-9elml3eOt24TJnsCopWdjerQAQ_j4TZ_yrIu-0PAqEUy9XGBX58KhaYq3ifYVHk52gEQ",
            "environment": "DEV"
        })
        
    def _validate_amount(self, amount):
        """Valide le montant de la transaction"""
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Le montant doit être un nombre positif")
        
        if amount < 5:  # Montant minimum en FCFA
            raise ValueError(f"Le montant minimum est 5 FCFA")
            
        if amount > 1000000:  # Montant maximum en FCFA
            raise ValueError(f"Le montant maximum est 1,000,000 FCFA")

    def _get_network_code(self, service_name):
        """Récupère le code du réseau mobile"""
        network_mapping = {
            'mtn': 'MTN',
            'orange': 'ORANGE',
        }
        
        network = network_mapping.get(service_name.lower())
        if not network:
            raise ValueError(f"Réseau mobile non supporté: {service_name}")
        return network

    def _handle_payment_error(self, error, user, transaction_type, amount):
        """Gère les erreurs de paiement de manière centralisée"""
        error_messages = {
            'CampayAuthorizationError': "Erreur d'autorisation avec le service Campay",
            'CampayError': "Erreur lors du traitement du paiement",
            'ValueError': "Données de transaction invalides",
            'Exception': "Une erreur inattendue est survenue",
        }
        
        default_message = f"Une erreur est survenue lors du {transaction_type}"
        message = error_messages.get(error.__class__.__name__, default_message)
        
        logger.error(
            f"Payment error for user {user.id}: {error.__class__.__name__} - {str(error)}",
            exc_info=True,
            extra={
                'user_id': user.id,
                'transaction_type': transaction_type,
                'amount': amount,
            }
        )
        
        return {
            'success': False,
            'message': message,
            'error_code': error.__class__.__name__,
        }

    def process_subscription_payment(self, user, amount, service_name, phone_number, subscription_data, subscription):
        """Process payment for subscription using initCollect (non-bloquant)"""
        try:
            # Format du numéro de téléphone
            if not phone_number.startswith('237'):
                phone_number = '237' + str(phone_number)
            
            reference = f"SUB_{user.id}_{datetime.now().timestamp()}"
            
            # Utiliser initCollect au lieu de collect pour un comportement non-bloquant
            response = self.client.initCollect({
                "amount": str(float(amount)),
                "currency": "XAF",
                "from": phone_number,
                "description": f"Abonnement EcoCity - {subscription_data.get('plan_name', 'Service')}",
                "external_reference": reference,
            })
            
            # Créer une entrée de paiement dans la base de données
            subscription = Subscription.objects.filter(user=user).first()    
            payment_record = Payment.objects.create(
                subscription=subscription,
                amount=amount,
                status='pending',
                payment_method=service_name,
                transaction_id=response.get('reference'),
                due_date=datetime.now()
            )   

            logger.info(f"Campay initCollect response: {response}")

            # initCollect retourne directement la réponse sans attendre
            print(f"voila la reponse :", response)
            if response.get('reference'):
                return {
                    'success': True,
                    'transaction_id': response.get('reference'),
                    'operator_reference': response.get('operator_reference'),
                    'amount': amount,
                    'message': "Paiement initié avec succès. Veuillez confirmer sur votre téléphone.",
                    'campay_response': response,
                    'reference': reference
                }
            else:
                error_message = response.get('message', 'Erreur lors du paiement')
                return {
                    'success': False,
                    'message': f"Échec du paiement: {error_message}",
                    'campay_response': response
                }
            
        except Exception as e:
            return self._handle_payment_error(e, user, 'paiement abonnement', amount)
        
    def process_subscription_payment_first(self, user, amount, service_name, phone_number, subscription_data, subscription):
        """Process payment for subscription using Collect (bloquant)"""
        try:
            # Format du numéro de téléphone
            if not phone_number.startswith('237'):
                phone_number = '237' + str(phone_number)
            
            reference = f"SUB_{user.id}_{datetime.now().timestamp()}"
            
            # Utiliser initCollect au lieu de collect pour un comportement non-bloquant
            response = self.client.collect({
                "amount": str(float(amount)),
                "currency": "XAF",
                "from": phone_number,
                "description": f"Abonnement EcoCity - {subscription_data.get('plan_name', 'Service')}",
                "external_reference": reference,
            })
            
            # Créer une entrée de paiement dans la base de données
            payment_record = Payment.objects.create(
                subscription=subscription,
                amount=amount,
                status='pending',
                payment_method=service_name,
                transaction_id=response.get('reference'),
                due_date=datetime.now()
            )

            logger.info(f"Campay initCollect response: {response}")

            # initCollect retourne directement la réponse sans attendre
            print(f'voila la reponse:', response)
            if response.get('status') == 'SUCCESSFUL':
                # envoyer une notification de succès
                Notification.create_notification(
                    user=user, title="Paiement Réussi",
                    message=f"Votre paiement de {amount} FCFA pour l'abonnement a été effectué avec succès.",
                    notification_type='success')
                
                payment_record.status = 'completed'
                payment_record.save()
                
                return {
                    'success': True,
                    'transaction_id': response.get('reference'),
                    'operator_reference': response.get('operator_reference'),
                    'amount': amount,
                    'message': "Paiement initié avec succès. Veuillez confirmer sur votre téléphone.",
                    'campay_response': response,
                    'reference': reference
                }
            else:
                error_message = response.get('message', 'Erreur lors du paiement')
                # envoie de notification d'echec
                Notification.create_notification(
                    user=user, title="Paiement Échoué",
                    message=f"Votre paiement de {amount} FCFA pour l'abonnement a échoué. Raison: {error_message}",
                    notification_type='error')
                
                payment_record.status = 'failed'
                payment_record.save()   
                return {
                    'success': False,
                    'message': f"Échec du paiement: {error_message}",
                    'campay_response': response
                }
            
        except Exception as e:
            return self._handle_payment_error(e, user, 'paiement abonnement', amount)

    def check_transaction_status(self, reference):
        """Check transaction status using Campay SDK"""
        try:
            # La méthode correcte dans la SDK est get_transaction_status avec un dictionnaire
            response = self.client.get_transaction_status({"reference": reference})
            
            logger.info(f"Campay status check for {reference}: {response}")
            payment_record = Payment.objects.filter(transaction_id=reference).first()
            if payment_record:
                payment_record.status = 'completed' if response.get('status') == 'SUCCESSFUL' else 'failed'
                payment_record.save()
            
            return {
                'success': True,
                'status': response.get('status'),
                'message': response.get('message', ''),
                'data': response
            }
        except Exception as e:
            logger.error(f"Failed to check transaction status for {reference}: {str(e)}")
            return {
                'success': False,
                'status': 'error',
                'message': str(e)
            }

    def process_withdrawal(self, user, amount, phone_number, description="Retrait d'argent"):
        """Process withdrawal using Campay SDK"""
        try:
            # Validation du montant
            self._validate_amount(amount)
            
            # Format du numéro de téléphone
            if not phone_number.startswith('237'):
                phone_number = '237' + str(phone_number)
            
            # Génération d'une référence unique
            reference = f"WTD_{user.id}_{datetime.now().timestamp()}"
            
            logger.info(f"Processing withdrawal for user {user.id}: amount={amount}, phone={phone_number}, reference={reference}")
            
            # Effectuer le retrait
            response = self.client.disburse({
                "amount": str(float(amount)),
                "currency": "XAF",
                "to": phone_number,
                "description": description or f"Retrait d'argent pour {user.get_full_name()}",
                "external_reference": reference,
            })
            
            logger.info(f"Campay withdrawal response: {response}")
            
            # Créer un enregistrement de retrait dans la base de données
            try:
                withdrawal = Withdrawal.objects.create(
                    user=user,
                    amount=amount,
                    phone_number=phone_number,
                    reference=reference,
                    status='pending' if response.get('status') in ['PENDING', 'SUCCESSFUL'] else 'failed',
                    transaction_id=response.get('reference'),
                    description=description or f"Retrait d'argent pour {user.get_full_name()}"
                )
                logger.info(f"Withdrawal record created: {withdrawal.id}")
            except Exception as e:
                logger.error(f"Failed to create withdrawal record: {str(e)}")
                withdrawal = None
            
            # Traiter la réponse de Campay
            if response.get('status') == 'SUCCESSFUL':
                if withdrawal:
                    withdrawal.status = 'completed'
                    withdrawal.completed_at = datetime.now()
                    withdrawal.save()
                
                # Notification de succès
                try:
                    Notification.create_notification(
                        user=user,
                        title="Retrait Réussi",
                        message=f"Votre retrait de {amount} FCFA a été effectué avec succès. Référence: {reference}",
                        notification_type='success'
                    )
                except Exception as e:
                    logger.error(f"Failed to create notification: {str(e)}")
                
                return {
                    'success': True,
                    'transaction_id': response.get('reference'),
                    'amount': amount,
                    'reference': reference,
                    'message': "Retrait effectué avec succès",
                    'withdrawal': withdrawal
                }
                
            elif response.get('status') == 'PENDING':
                return {
                    'success': True,
                    'transaction_id': response.get('reference'),
                    'amount': amount,
                    'reference': reference,
                    'message': "Retrait en cours de traitement. Veuillez vérifier le statut plus tard.",
                    'withdrawal': withdrawal
                }
                
            else:
                error_message = response.get('message', 'Erreur lors du retrait')
                
                if withdrawal:
                    withdrawal.status = 'failed'
                    withdrawal.save()
                
                # Notification d'échec
                try:
                    Notification.create_notification(
                        user=user,
                        title="Retrait Échoué",
                        message=f"Votre retrait de {amount} FCFA a échoué. Raison: {error_message}",
                        notification_type='error'
                    )
                except Exception as e:
                    logger.error(f"Failed to create notification: {str(e)}")
                
                return {
                    'success': False,
                    'message': f"Échec du retrait: {error_message}",
                    'campay_response': response,
                    'reference': reference
                }
            
        except ValueError as e:
            logger.error(f"Validation error in withdrawal: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'error_code': 'VALUE_ERROR'
            }
        except Exception as e:
            logger.error(f"Unexpected error in withdrawal: {str(e)}", exc_info=True)
            return self._handle_payment_error(e, user, 'retrait', amount)

    def check_withdrawal_status(self, reference):
        """Check withdrawal transaction status"""
        try:
            response = self.client.get_transaction_status({"reference": reference})
            
            logger.info(f"Campay withdrawal status check for {reference}: {response}")
            
            # Mettre à jour le statut dans la base de données
            try:
                withdrawal = Withdrawal.objects.filter(transaction_id=reference).first()
                
                if withdrawal:
                    if response.get('status') == 'SUCCESSFUL':
                        withdrawal.status = 'completed'
                        withdrawal.completed_at = datetime.now()
                    elif response.get('status') == 'FAILED':
                        withdrawal.status = 'failed'
                    else:
                        withdrawal.status = 'pending'
                    withdrawal.save()
                    logger.info(f"Updated withdrawal {withdrawal.id} status to {withdrawal.status}")
            except Exception as e:
                logger.error(f"Failed to update withdrawal status: {str(e)}")
            
            return {
                'success': True,
                'status': response.get('status'),
                'message': response.get('message', ''),
                'data': response
            }
        except Exception as e:
            logger.error(f"Failed to check withdrawal status for {reference}: {str(e)}")
            return {
                'success': False,
                'status': 'error',
                'message': str(e)
            }

    def get_withdrawal_history(self, user=None, status=None, start_date=None, end_date=None):
        """Get withdrawal history with optional filters"""
        try:
            withdrawals = Withdrawal.objects.all()
            
            if user:
                withdrawals = withdrawals.filter(user=user)
            
            if status:
                withdrawals = withdrawals.filter(status=status)
            
            if start_date:
                withdrawals = withdrawals.filter(created_at__gte=start_date)
            
            if end_date:
                withdrawals = withdrawals.filter(created_at__lte=end_date)
            
            withdrawals = withdrawals.order_by('-created_at')
            
            # Calculer les statistiques
            total_withdrawn = withdrawals.filter(status='completed').aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            
            stats = {
                'total_withdrawals': withdrawals.count(),
                'total_completed': withdrawals.filter(status='completed').count(),
                'total_pending': withdrawals.filter(status='pending').count(),
                'total_failed': withdrawals.filter(status='failed').count(),
                'total_amount': total_withdrawn,
                'average_amount': total_withdrawn / withdrawals.filter(status='completed').count() if withdrawals.filter(status='completed').count() > 0 else 0
            }
            
            return {
                'success': True,
                'withdrawals': withdrawals,
                'stats': stats
            }
        except Exception as e:
            logger.error(f"Failed to get withdrawal history: {str(e)}")
            return {
                'success': False,
                'message': str(e),
                'withdrawals': [],
                'stats': {}
            }

    def cancel_pending_withdrawal(self, withdrawal_id):
        """Cancel a pending withdrawal"""
        try:
            withdrawal = Withdrawal.objects.get(id=withdrawal_id)
            
            if withdrawal.status != 'pending':
                return {
                    'success': False,
                    'message': "Seul un retrait en attente peut être annulé"
                }
            
            withdrawal.status = 'cancelled'
            withdrawal.save()
            
            # Notification d'annulation
            try:
                Notification.create_notification(
                    user=withdrawal.user,
                    title="Retrait Annulé",
                    message=f"Votre retrait de {withdrawal.amount} FCFA a été annulé.",
                    notification_type='warning'
                )
            except Exception as e:
                logger.error(f"Failed to create cancellation notification: {str(e)}")
            
            return {
                'success': True,
                'message': "Retrait annulé avec succès",
                'withdrawal': withdrawal
            }
        except Withdrawal.DoesNotExist:
            return {
                'success': False,
                'message': "Retrait non trouvé"
            }
        except Exception as e:
            logger.error(f"Failed to cancel withdrawal: {str(e)}")
            return {
                'success': False,
                'message': str(e)
            }