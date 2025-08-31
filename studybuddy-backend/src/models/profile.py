from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from src.extensions import db

class ProfileSettings(db.Model):
    __tablename__ = "profile_settings"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), unique=True, nullable=False)
    is_public = db.Column(db.Boolean, default=False)
    show_email = db.Column(db.Boolean, default=False)
    show_study_stats = db.Column(db.Boolean, default=True)
    show_badges = db.Column(db.Boolean, default=True)
    show_streak = db.Column(db.Boolean, default=True)
    show_study_rooms = db.Column(db.Boolean, default=True)
    bio = db.Column(db.Text)
    social_links = db.Column(db.Text)  # JSON string of social media links
    learning_goals = db.Column(db.Text)
    preferred_subjects = db.Column(db.Text)  # JSON string of subjects
    timezone = db.Column(db.String(50), default='UTC')
    language_preference = db.Column(db.String(10), default='en')
    notification_preferences = db.Column(db.Text)  # JSON string of notification settings
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref=db.backref('profile_settings', uselist=False), lazy=True)
    
    def get_social_links(self):
        """Get social links as a dictionary"""
        try:
            return json.loads(self.social_links) if self.social_links else {}
        except json.JSONDecodeError:
            return {}
    
    def set_social_links(self, links_dict):
        """Set social links from dictionary"""
        self.social_links = json.dumps(links_dict) if links_dict else None
    
    def get_preferred_subjects(self):
        """Get preferred subjects as a list"""
        try:
            return json.loads(self.preferred_subjects) if self.preferred_subjects else []
        except json.JSONDecodeError:
            return []
    
    def set_preferred_subjects(self, subjects_list):
        """Set preferred subjects from list"""
        self.preferred_subjects = json.dumps(subjects_list) if subjects_list else None
    
    def get_notification_preferences(self):
        """Get notification preferences as a dictionary"""
        try:
            return json.loads(self.notification_preferences) if self.notification_preferences else {
                'email_notifications': True,
                'push_notifications': True,
                'study_reminders': True,
                'room_invitations': True,
                'ai_tutor_updates': True,
                'payment_notifications': True
            }
        except json.JSONDecodeError:
            return {
                'email_notifications': True,
                'push_notifications': True,
                'study_reminders': True,
                'room_invitations': True,
                'ai_tutor_updates': True,
                'payment_notifications': True
            }
    
    def set_notification_preferences(self, prefs_dict):
        """Set notification preferences from dictionary"""
        self.notification_preferences = json.dumps(prefs_dict) if prefs_dict else None
    
    def is_profile_complete(self):
        """Check if profile is complete"""
        required_fields = [self.bio, self.learning_goals]
        return all(field and field.strip() for field in required_fields)
    
    def get_privacy_level(self):
        """Get privacy level as string"""
        if not self.is_public:
            return 'private'
        elif self.show_email and self.show_study_stats:
            return 'public'
        else:
            return 'limited'
    
    def to_dict(self, include_private=False):
        """Convert to dictionary with privacy controls"""
        base_data = {
            'id': self.id,
            'user_id': self.user_id,
            'is_public': self.is_public,
            'bio': self.bio if self.is_public or include_private else None,
            'learning_goals': self.learning_goals if self.is_public or include_private else None,
            'preferred_subjects': self.get_preferred_subjects() if self.is_public or include_private else [],
            'timezone': self.timezone,
            'language_preference': self.language_preference,
            'privacy_level': self.get_privacy_level(),
            'is_complete': self.is_profile_complete(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        # Add private fields if authorized
        if include_private:
            base_data.update({
                'show_email': self.show_email,
                'show_study_stats': self.show_study_stats,
                'show_badges': self.show_badges,
                'show_streak': self.show_streak,
                'show_study_rooms': self.show_study_rooms,
                'social_links': self.get_social_links(),
                'notification_preferences': self.get_notification_preferences()
            })
        
        # Add conditionally visible fields
        if self.is_public or include_private:
            if self.show_study_stats or include_private:
                base_data['show_study_stats'] = True
            if self.show_badges or include_private:
                base_data['show_badges'] = True
            if self.show_streak or include_private:
                base_data['show_streak'] = True
            if self.show_study_rooms or include_private:
                base_data['show_study_rooms'] = True
        
        return base_data

class LMSIntegration(db.Model):
    __tablename__ = "lms_integrations"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    lms_type = db.Column(db.String(50), nullable=False)  # canvas, blackboard, moodle, etc.
    lms_user_id = db.Column(db.String(255))
    lms_username = db.Column(db.String(255))
    access_token = db.Column(db.Text)  # Encrypted
    refresh_token = db.Column(db.Text)  # Encrypted
    token_expires_at = db.Column(db.DateTime)
    integration_data = db.Column(db.Text)  # JSON string of additional data
    is_active = db.Column(db.Boolean, default=True)
    last_sync = db.Column(db.DateTime)
    sync_status = db.Column(db.String(20), default='pending')  # pending, syncing, completed, failed
    error_message = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='lms_integrations', lazy=True)
    
    def get_integration_data(self):
        """Get integration data as dictionary"""
        try:
            return json.loads(self.integration_data) if self.integration_data else {}
        except json.JSONDecodeError:
            return {}
    
    def set_integration_data(self, data_dict):
        """Set integration data from dictionary"""
        self.integration_data = json.dumps(data_dict) if data_dict else None
    
    def is_token_expired(self):
        """Check if access token is expired"""
        return self.token_expires_at and self.token_expires_at < datetime.utcnow()
    
    def needs_refresh(self):
        """Check if token needs refresh (expires within 1 hour)"""
        if not self.token_expires_at:
            return False
        return self.token_expires_at < datetime.utcnow() + timedelta(hours=1)
    
    def mark_sync_started(self):
        """Mark sync as started"""
        self.sync_status = 'syncing'
        self.last_sync = datetime.utcnow()
        self.error_message = None
        db.session.commit()
    
    def mark_sync_completed(self):
        """Mark sync as completed"""
        self.sync_status = 'completed'
        self.error_message = None
        db.session.commit()
    
    def mark_sync_failed(self, error_message):
        """Mark sync as failed"""
        self.sync_status = 'failed'
        self.error_message = error_message
        db.session.commit()
    
    def to_dict(self, include_tokens=False):
        """Convert to dictionary"""
        data = {
            'id': self.id,
            'user_id': self.user_id,
            'lms_type': self.lms_type,
            'lms_user_id': self.lms_user_id,
            'lms_username': self.lms_username,
            'is_active': self.is_active,
            'last_sync': self.last_sync.isoformat() if self.last_sync else None,
            'sync_status': self.sync_status,
            'error_message': self.error_message,
            'is_token_expired': self.is_token_expired(),
            'needs_refresh': self.needs_refresh(),
            'integration_data': self.get_integration_data(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_tokens:
            data.update({
                'token_expires_at': self.token_expires_at.isoformat() if self.token_expires_at else None
            })
        
        return data

class UserActivity(db.Model):
    __tablename__ = "user_activities"
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    activity_type = db.Column(db.String(50), nullable=False)  # login, study_session, document_upload, etc.
    activity_data = db.Column(db.Text)  # JSON string of activity details
    ip_address = db.Column(db.String(45))  # Support IPv6
    user_agent = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='activities', lazy=True)
    
    def get_activity_data(self):
        """Get activity data as dictionary"""
        try:
            return json.loads(self.activity_data) if self.activity_data else {}
        except json.JSONDecodeError:
            return {}
    
    def set_activity_data(self, data_dict):
        """Set activity data from dictionary"""
        self.activity_data = json.dumps(data_dict) if data_dict else None
    
    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'activity_type': self.activity_type,
            'activity_data': self.get_activity_data(),
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

