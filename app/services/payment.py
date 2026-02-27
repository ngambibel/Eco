import logging
from datetime import datetime
from django.conf import settings
from campay.sdk import Client
from app.models import Notification, Payment, Subscription


logger = logging.getLogger(__name__)

class PaymentService:
    def __init__(self):
        self.client = Client({
            "app_username": "HyGJKtSsjFqCBpf5NTxtWPT5pwAFk7jFc0VW0bylHKXzsbPmt2RED6rQtnu9HtedR1hOhEvC41vIeQR666FusQ",
            "app_password": "pivVF5QYjQOEDWeQW-9elml3eOt24TJnsCopWdjerQAQ_j4TZ_yrIu-0PAqEUy9XGBX58KhaYq3ifYVHk52gEQ",
            "environment": "DEV"
        })
        
    def _validate_amount(self, amount):
        if not isinstance(amount, (int, float)) or amount <= 0:
            raise ValueError("Le montant doit être un nombre positif")
        
        if amount < 5:  # Montant minimum en FCFA
            raise ValueError(f"Le montant minimum est 5 FCFA")
            
        if amount > 1000000:  # Montant maximum en FCFA
            raise ValueError(f"Le montant maximum est 1,000,000 FCFA")

    def _get_network_code(self, service_name):
        network_mapping = {
            'mtn': 'MTN',
            'orange': 'ORANGE',
        }
        
        network = network_mapping.get(service_name.lower())
        if not network:
            raise ValueError(f"Réseau mobile non supporté: {service_name}")
        return network

    def _handle_payment_error(self, error, user, transaction_type, amount):
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
            # creer une entree de paiement dans la base de donnee
            subscription= Subscription.objects.filter(user=user).first()    
            payment_record = Payment.objects.create(
                subcription=subscription,
                amount=amount,
                status='pending',
                payment_method=service_name,
                transaction_id=response.get('reference'),
                due_date=datetime.now()
            )   

            logger.info(f"Campay initCollect response: {response}")

            # initCollect retourne directement la réponse sans attendre
            print(f"voila la reponse :", response)
            if response['reference'] :
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
                # creer une entree de paiement dans la base de donnee
            
            subscription= Subscription.objects.filter(user__id=user.id).first()
            payment_record = Payment.objects.create(
                subscription= subscription,
                amount=amount,
                status='pending',
                payment_method=service_name,
                transaction_id=response.get('reference'),
                due_date=datetime.now()
            )

            logger.info(f"Campay initCollect response: {response}")

            # initCollect retourne directement la réponse sans attendre
            print(f'voila la reponse:',response)
            if response['status'] == 'SUCCESSFUL':
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
            payment_record= Payment.objects.filter(transaction_id=reference).first()
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