from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
from src.extensions import db

class PaymentRecord(db.Model):
    __tablename__ = "payment_records"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    intasend_payment_id = db.Column(db.String(255), unique=True)
    amount = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='KES')
    status = db.Column(db.String(20), nullable=False)  # pending, completed, failed, cancelled
    plan_type = db.Column(db.String(50), nullable=False)
    payment_method = db.Column(db.String(50))  # M-PESA, Card, Bank Transfer
    api_ref = db.Column(db.String(255), unique=True)
    callback_data = db.Column(db.Text)  # Store full callback data as JSON
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    expires_at = db.Column(db.DateTime)
    
    # Relationships
    user = db.relationship('User', backref='payment_records', lazy=True)
    
    def is_expired(self):
        """Check if payment has expired"""
        return self.expires_at and self.expires_at < datetime.utcnow()
    
    def is_successful(self):
        """Check if payment was successful"""
        return self.status == 'completed'
    
    def get_subscription_end_date(self):
        """Get subscription end date based on plan type"""
        if self.plan_type == 'premium_yearly':
            return self.created_at + timedelta(days=365)
        elif self.plan_type == 'premium_monthly':
            return self.created_at + timedelta(days=30)
        return None
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'intasend_payment_id': self.intasend_payment_id,
            'amount': float(self.amount) if self.amount else None,
            'currency': self.currency,
            'status': self.status,
            'plan_type': self.plan_type,
            'payment_method': self.payment_method,
            'api_ref': self.api_ref,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_expired': self.is_expired(),
            'is_successful': self.is_successful(),
            'subscription_end_date': self.get_subscription_end_date().isoformat() if self.get_subscription_end_date() else None
        }

class SubscriptionPlan(db.Model):
    __tablename__ = "subscription_plans"
    
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), default='KES')
    duration_days = db.Column(db.Integer, nullable=False)
    features = db.Column(db.Text)  # JSON string of features
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def get_features_list(self):
        """Get features as a list"""
        import json
        try:
            return json.loads(self.features) if self.features else []
        except json.JSONDecodeError:
            return []
    
    def to_dict(self):
        return {
            'id': self.id,
            'plan_id': self.plan_id,
            'name': self.name,
            'description': self.description,
            'price': float(self.price) if self.price else None,
            'currency': self.currency,
            'duration_days': self.duration_days,
            'features': self.get_features_list(),
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

class WebhookLog(db.Model):
    __tablename__ = "webhook_logs"
    
    id = db.Column(db.Integer, primary_key=True)
    webhook_type = db.Column(db.String(50), nullable=False)  # intasend, lms, etc.
    payload = db.Column(db.Text, nullable=False)
    signature = db.Column(db.String(255))
    status = db.Column(db.String(20), default='received')  # received, processed, failed
    error_message = db.Column(db.Text)
    processed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def mark_processed(self):
        """Mark webhook as processed"""
        self.status = 'processed'
        self.processed_at = datetime.utcnow()
        db.session.commit()
    
    def mark_failed(self, error_message):
        """Mark webhook as failed"""
        self.status = 'failed'
        self.error_message = error_message
        self.processed_at = datetime.utcnow()
        db.session.commit()
    
    def to_dict(self):
        return {
            'id': self.id,
            'webhook_type': self.webhook_type,
            'status': self.status,
            'error_message': self.error_message,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

