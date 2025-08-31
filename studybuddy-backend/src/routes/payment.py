from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timedelta
import json
from src.models.user import User, db
from src.models.payment import PaymentRecord, SubscriptionPlan
from src.routes.auth import token_required, sanitize_input
from src.services.payment_service import PaymentService

payment_bp = Blueprint('payment', __name__)

def get_payment_service():
    """Get payment service instance within application context"""
    if not hasattr(current_app, 'payment_service'):
        current_app.payment_service = PaymentService()
    return current_app.payment_service

@payment_bp.route('/plans', methods=['GET'])
def get_subscription_plans():
    """Get available subscription plans"""
    try:
        payment_service = get_payment_service()
        plans = payment_service.get_subscription_plans()
        return jsonify({'plans': plans}), 200
    except Exception as e:
        current_app.logger.error(f"Error getting subscription plans: {e}")
        return jsonify({'error': 'Failed to get subscription plans'}), 500

@payment_bp.route('/create-payment', methods=['POST'])
@token_required
def create_payment(current_user):
    """Create a payment request with IntaSend"""
    try:
        payment_service = get_payment_service()
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        data = sanitize_input(data)
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return jsonify({'error': 'Plan ID is required'}), 400
        
        # Check if user already has an active subscription
        subscription_status = payment_service.get_user_subscription_status(current_user.id)
        if subscription_status['is_active'] and plan_id == 'premium_yearly':
            return jsonify({
                'error': 'You already have an active premium subscription',
                'current_subscription': subscription_status
            }), 400
        
        # Create payment request
        payment_data = payment_service.create_payment_request(current_user.id, plan_id)
        
        return jsonify({
            'payment_id': payment_data['payment_id'],
            'checkout_url': payment_data['checkout_url'],
            'amount': payment_data['amount'],
            'currency': payment_data['currency'],
            'expires_at': payment_data['expires_at']
        }), 201
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Payment creation error: {e}")
        return jsonify({'error': 'Payment creation failed'}), 500

@payment_bp.route('/webhook', methods=['POST'])
def payment_webhook():
    """Handle payment webhook from IntaSend"""
    try:
        payment_service = get_payment_service()
        payload = request.get_data(as_text=True)
        signature = request.headers.get('X-IntaSend-Signature', '')
        
        current_app.logger.info(f"Webhook received: signature={signature[:20]}...")
        
        if not payload:
            current_app.logger.warning("Webhook received with no payload")
            return jsonify({'error': 'No payload provided'}), 400
        
        # Process webhook
        result = payment_service.process_webhook(payload, signature)
        
        current_app.logger.info(f"Webhook processed successfully: {result}")
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook processed successfully',
            'data': result
        }), 200
        
    except ValueError as e:
        current_app.logger.warning(f"Webhook validation error: {e}")
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Webhook processing error: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@payment_bp.route('/callback', methods=['GET', 'POST'])
def payment_callback():
    """Handle payment callback redirect from IntaSend"""
    try:
        # This endpoint handles the redirect after payment
        # The actual payment processing is done via webhook
        
        if request.method == 'GET':
            # Handle GET callback (redirect from IntaSend)
            api_ref = request.args.get('api_ref')
            status = request.args.get('status', 'unknown')
            
            if api_ref:
                payment_record = PaymentRecord.query.filter_by(api_ref=api_ref).first()
                if payment_record:
                    return jsonify({
                        'status': 'redirect_received',
                        'payment_status': payment_record.status,
                        'message': 'Payment status will be updated via webhook'
                    }), 200
        
        return jsonify({
            'status': 'callback_received',
            'message': 'Payment callback received'
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Callback processing error: {e}")
        return jsonify({'error': 'Callback processing failed'}), 500

@payment_bp.route('/status', methods=['GET'])
@token_required
def get_subscription_status(current_user):
    """Get current user's subscription status"""
    try:
        payment_service = get_payment_service()
        status = payment_service.get_user_subscription_status(current_user.id)
        return jsonify(status), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting subscription status: {e}")
        return jsonify({'error': 'Failed to get subscription status'}), 500

@payment_bp.route('/cancel', methods=['POST'])
@token_required
def cancel_subscription(current_user):
    """Cancel premium subscription"""
    try:
        payment_service = get_payment_service()
        result = payment_service.cancel_subscription(current_user.id)
        return jsonify(result), 200
        
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Subscription cancellation error: {e}")
        return jsonify({'error': 'Failed to cancel subscription'}), 500

@payment_bp.route('/history', methods=['GET'])
@token_required
def get_payment_history(current_user):
    """Get user's payment history"""
    try:
        payment_service = get_payment_service()
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)  # Cap at 50 records
        
        history = payment_service.get_payment_history(current_user.id, limit)
        
        return jsonify({'payments': history}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting payment history: {e}")
        return jsonify({'error': 'Failed to get payment history'}), 500

@payment_bp.route('/verify/<int:payment_id>', methods=['GET'])
@token_required
def verify_payment(current_user, payment_id):
    """Verify payment status"""
    try:
        payment_service = get_payment_service()
        payment_record = PaymentRecord.query.filter_by(
            id=payment_id, 
            user_id=current_user.id
        ).first()
        
        if not payment_record:
            return jsonify({'error': 'Payment record not found'}), 404
        
        # Check if payment has expired
        if payment_record.is_expired() and payment_record.status == 'pending':
            payment_record.status = 'expired'
            db.session.commit()
        
        return jsonify({
            'payment': payment_record.to_dict(),
            'subscription_status': payment_service.get_user_subscription_status(current_user.id)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error verifying payment: {e}")
        return jsonify({'error': 'Failed to verify payment'}), 500

