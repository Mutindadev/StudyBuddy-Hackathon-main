from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from src.extensions import db

class WhiteboardSession(db.Model):
    __tablename__ = "whiteboard_sessions"
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('study_room.id'), nullable=False)
    session_data = db.Column(db.Text)  # JSON string of whiteboard drawing data
    last_modified_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    room = db.relationship('StudyRoom', backref='whiteboard_sessions', lazy=True)
    last_modifier = db.relationship('User', backref='whiteboard_modifications', lazy=True)
    
    def get_session_data(self):
        """Get session data as dictionary"""
        try:
            return json.loads(self.session_data) if self.session_data else {
                'strokes': [],
                'shapes': [],
                'text_elements': [],
                'background_color': '#ffffff',
                'canvas_size': {'width': 800, 'height': 600}
            }
        except json.JSONDecodeError:
            return {
                'strokes': [],
                'shapes': [],
                'text_elements': [],
                'background_color': '#ffffff',
                'canvas_size': {'width': 800, 'height': 600}
            }
    
    def set_session_data(self, data_dict):
        """Set session data from dictionary"""
        self.session_data = json.dumps(data_dict) if data_dict else None
        self.version += 1
        self.updated_at = datetime.utcnow()
    
    def add_stroke(self, stroke_data, user_id):
        """Add a new stroke to the whiteboard"""
        data = self.get_session_data()
        stroke_data['id'] = f"stroke_{len(data['strokes'])}_{int(datetime.utcnow().timestamp())}"
        stroke_data['created_by'] = user_id
        stroke_data['created_at'] = datetime.utcnow().isoformat()
        data['strokes'].append(stroke_data)
        self.set_session_data(data)
        self.last_modified_by = user_id
    
    def add_shape(self, shape_data, user_id):
        """Add a new shape to the whiteboard"""
        data = self.get_session_data()
        shape_data['id'] = f"shape_{len(data['shapes'])}_{int(datetime.utcnow().timestamp())}"
        shape_data['created_by'] = user_id
        shape_data['created_at'] = datetime.utcnow().isoformat()
        data['shapes'].append(shape_data)
        self.set_session_data(data)
        self.last_modified_by = user_id
    
    def add_text(self, text_data, user_id):
        """Add text element to the whiteboard"""
        data = self.get_session_data()
        text_data['id'] = f"text_{len(data['text_elements'])}_{int(datetime.utcnow().timestamp())}"
        text_data['created_by'] = user_id
        text_data['created_at'] = datetime.utcnow().isoformat()
        data['text_elements'].append(text_data)
        self.set_session_data(data)
        self.last_modified_by = user_id
    
    def clear_whiteboard(self, user_id):
        """Clear all whiteboard content"""
        data = {
            'strokes': [],
            'shapes': [],
            'text_elements': [],
            'background_color': '#ffffff',
            'canvas_size': {'width': 800, 'height': 600}
        }
        self.set_session_data(data)
        self.last_modified_by = user_id
    
    def get_element_count(self):
        """Get total count of elements on whiteboard"""
        data = self.get_session_data()
        return len(data['strokes']) + len(data['shapes']) + len(data['text_elements'])
    
    def to_dict(self, include_data=True):
        """Convert to dictionary"""
        result = {
            'id': self.id,
            'room_id': self.room_id,
            'last_modified_by': self.last_modified_by,
            'version': self.version,
            'is_active': self.is_active,
            'element_count': self.get_element_count(),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_data:
            result['session_data'] = self.get_session_data()
        
        return result

class WhiteboardHistory(db.Model):
    __tablename__ = "whiteboard_history"
    
    id = db.Column(db.Integer, primary_key=True)
    whiteboard_session_id = db.Column(db.Integer, db.ForeignKey('whiteboard_sessions.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    session_data = db.Column(db.Text)  # Snapshot of whiteboard at this version
    modified_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    change_description = db.Column(db.String(255))  # Brief description of changes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    whiteboard_session = db.relationship('WhiteboardSession', backref='history', lazy=True)
    modifier = db.relationship('User', backref='whiteboard_history', lazy=True)
    
    def get_session_data(self):
        """Get session data as dictionary"""
        try:
            return json.loads(self.session_data) if self.session_data else {}
        except json.JSONDecodeError:
            return {}
    
    def to_dict(self):
        return {
            'id': self.id,
            'whiteboard_session_id': self.whiteboard_session_id,
            'version': self.version,
            'modified_by': self.modified_by,
            'change_description': self.change_description,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'session_data': self.get_session_data()
        }

class RoomDocument(db.Model):
    __tablename__ = "room_documents"
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('study_room.id'), nullable=False)
    document_id = db.Column(db.Integer, db.ForeignKey('document.id'), nullable=False)
    shared_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    permissions = db.Column(db.String(20), default='read')  # read, write, admin
    shared_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    room = db.relationship('StudyRoom', backref='shared_documents', lazy=True)
    document = db.relationship('Document', backref='room_shares', lazy=True)
    sharer = db.relationship('User', backref='shared_room_documents', lazy=True)
    
    # Unique constraint to prevent duplicate shares
    __table_args__ = (db.UniqueConstraint('room_id', 'document_id', name='unique_room_document'),)
    
    def can_read(self):
        """Check if document can be read"""
        return self.is_active and self.permissions in ['read', 'write', 'admin']
    
    def can_write(self):
        """Check if document can be modified"""
        return self.is_active and self.permissions in ['write', 'admin']
    
    def can_admin(self):
        """Check if document can be administered"""
        return self.is_active and self.permissions == 'admin'
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'document_id': self.document_id,
            'shared_by': self.shared_by,
            'is_active': self.is_active,
            'permissions': self.permissions,
            'can_read': self.can_read(),
            'can_write': self.can_write(),
            'can_admin': self.can_admin(),
            'shared_at': self.shared_at.isoformat() if self.shared_at else None
        }

class CollaborationEvent(db.Model):
    __tablename__ = "collaboration_events"
    
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('study_room.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)  # join, leave, whiteboard_update, document_share, etc.
    event_data = db.Column(db.Text)  # JSON string of event details
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    room = db.relationship('StudyRoom', backref='collaboration_events', lazy=True)
    user = db.relationship('User', backref='collaboration_events', lazy=True)
    
    def get_event_data(self):
        """Get event data as dictionary"""
        try:
            return json.loads(self.event_data) if self.event_data else {}
        except json.JSONDecodeError:
            return {}
    
    def set_event_data(self, data_dict):
        """Set event data from dictionary"""
        self.event_data = json.dumps(data_dict) if data_dict else None
    
    def to_dict(self):
        return {
            'id': self.id,
            'room_id': self.room_id,
            'user_id': self.user_id,
            'event_type': self.event_type,
            'event_data': self.get_event_data(),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

