from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import re
from datetime import datetime, timedelta
from src.models.user import User, db
from src.utils.validation import (
    validate_email, validate_password, validate_username, validate_name,
    sanitize_input, validate_json_input
)

auth_bp = Blueprint('auth', __name__)

def token_required(f):
    """Decorator to require valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            try:
                token = auth_header.split(" ")[1]  # Bearer <token>
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401
                
            # Check if account is locked
            if hasattr(current_user, 'is_account_locked') and current_user.is_account_locked():
                return jsonify({
                    'error': 'Account temporarily locked',
                    'message': 'Too many failed login attempts. Please try again later.'
                }), 423
                
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token'}), 401
        except Exception as e:
            current_app.logger.error(f"Token validation error: {e}")
            return jsonify({'error': 'Token validation failed'}), 401
        
        return f(current_user, *args, **kwargs)
    
    return decorated

@auth_bp.route('/register', methods=['POST'])
@validate_json_input(
    required_fields=['username', 'email', 'password', 'first_name', 'last_name'],
    optional_fields=[]
)
def register():
    """Register a new user"""
    try:
        data = g.sanitized_json  # Use sanitized input

        # Validate input fields
        username_validation = validate_username(data['username'])
        if not username_validation['valid']:
            return jsonify({'error': username_validation['message']}), 400

        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email format'}), 400

        password_validation = validate_password(data['password'])
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400

        first_name_validation = validate_name(data['first_name'], 'First name')
        if not first_name_validation['valid']:
            return jsonify({'error': first_name_validation['message']}), 400

        last_name_validation = validate_name(data['last_name'], 'Last name')
        if not last_name_validation['valid']:
            return jsonify({'error': last_name_validation['message']}), 400

        # Check if user already exists
        if User.query.filter_by(email=data['email'].lower().strip()).first():
            return jsonify({'error': 'Email already registered'}), 409

        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 409

        # Create new user
        user = User(
            username=data['username'],
            email=data['email'].lower().strip(),
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip()
        )
        user.set_password(data['password'])

        db.session.add(user)
        db.session.commit()

        # Generate token safely
        try:
            token = user.generate_token()
        except Exception as token_err:
            current_app.logger.error(f"Token generation failed: {str(token_err)}")
            token = None

        # Build user dict safely
        try:
            user_dict = user.to_dict()
        except Exception as dict_err:
            current_app.logger.error(f"user.to_dict() failed: {str(dict_err)}")
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

        current_app.logger.info(f"New user registered: {user.username} ({user.email})")

        return jsonify({
            'message': 'User registered successfully',
            'token': token,
            'user': user_dict
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {str(e)}")
        return jsonify({'error': 'Registration failed'}), 500


@auth_bp.route('/login', methods=['POST'])
@validate_json_input(
    required_fields=['email', 'password'],
    optional_fields=[]
)
def login():
    """Login user"""
    try:
        data = g.sanitized_json  # Use sanitized input

        email = data['email'].strip().lower()
        password = data['password']

        # Find user by normalized email
        user = User.query.filter_by(email=email).first()

        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        # Check account lock
        if hasattr(user, "is_account_locked") and user.is_account_locked():
            return jsonify({'error': 'Account temporarily locked'}), 423

        # Check password
        if not user.check_password(password):
            if hasattr(user, "increment_failed_login"):
                user.increment_failed_login()
            return jsonify({'error': 'Invalid email or password'}), 401

        # Reset failed login attempts
        if hasattr(user, "reset_failed_login"):
            user.reset_failed_login()

        # Update streak/last activity
        if hasattr(user, "update_streak"):
            user.update_streak()

        # Generate token safely
        try:
            token = user.generate_token()
        except Exception as token_err:
            current_app.logger.error(f"Token generation failed: {str(token_err)}")
            token = None

        # Build user dict safely
        try:
            user_dict = user.to_dict()
        except Exception as dict_err:
            current_app.logger.error(f"user.to_dict() failed: {str(dict_err)}")
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

        current_app.logger.info(f"User logged in: {user.username}")

        return jsonify({'message': 'Login successful', 'token': token, 'user': user_dict}), 200

    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({'error': 'Login failed'}), 500


@auth_bp.route('/verify-token', methods=['POST'])
@token_required
def verify_token(current_user):
    """Verify if token is valid"""
    return jsonify({
        'valid': True,
        'user': current_user.to_dict()
    }), 200

@auth_bp.route('/refresh-token', methods=['POST'])
@token_required
def refresh_token(current_user):
    """Refresh JWT token"""
    try:
        new_token = current_user.generate_token()
        return jsonify({
            'token': new_token,
            'user': current_user.to_dict()
        }), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh error: {e}")
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
@validate_json_input(
    required_fields=['current_password', 'new_password'],
    optional_fields=[]
)
def change_password(current_user):
    """Change user password"""
    try:
        data = g.sanitized_json  # Use sanitized input
        
        current_password = data['current_password']
        new_password = data['new_password']
        
        # Verify current password
        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401
        
        # Validate new password
        password_validation = validate_password(new_password)
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400
        
        # Check if new password is different from current
        if current_user.check_password(new_password):
            return jsonify({'error': 'New password must be different from current password'}), 400
        
        # Update password
        current_user.set_password(new_password)
        db.session.commit()
        
        current_app.logger.info(f"Password changed for user: {current_user.username}")
        
        return jsonify({'message': 'Password changed successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password change error: {e}")
        return jsonify({'error': 'Password change failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    """Logout user (client should discard token)"""
    try:
        current_app.logger.info(f"User logged out: {current_user.username}")
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500
