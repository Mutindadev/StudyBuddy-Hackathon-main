from flask import Blueprint, request, jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
from datetime import datetime, timedelta
from src.models.user import User, db
from src.utils.validation import (
    validate_email, validate_password, validate_username, validate_name,
    sanitize_input, validate_json_input
)

auth_bp = Blueprint('auth', __name__)

def token_required(f):
    """Decorator to require valid JWT token safely"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        
        if auth_header:
            parts = auth_header.split(" ")
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token = parts[1]
        
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            user_id = payload.get('user_id')
            if not user_id:
                return jsonify({'error': 'Invalid token payload'}), 401

            current_user = User.query.get(user_id)
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

# --- User Registration ---
@auth_bp.route('/register', methods=['POST'])
@validate_json_input(
    required_fields=['username', 'email', 'password', 'first_name', 'last_name'],
    optional_fields=[]
)
def register():
    try:
        data = request.get_json()

        # Validate input
        if not validate_username(data['username'])['valid']:
            return jsonify({'error': 'Invalid username'}), 400
        if not validate_email(data['email']):
            return jsonify({'error': 'Invalid email'}), 400
        if not validate_password(data['password'])['valid']:
            return jsonify({'error': 'Invalid password'}), 400
        if not validate_name(data['first_name'], 'First name')['valid']:
            return jsonify({'error': 'Invalid first name'}), 400
        if not validate_name(data['last_name'], 'Last name')['valid']:
            return jsonify({'error': 'Invalid last name'}), 400

        # Check uniqueness
        if User.query.filter_by(email=data['email'].lower().strip()).first():
            return jsonify({'error': 'Email already registered'}), 409
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': 'Username already taken'}), 409

        # Create user
        user = User(
            username=data['username'],
            email=data['email'].lower().strip(),
            first_name=data['first_name'].strip(),
            last_name=data['last_name'].strip()
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()

        # Generate token
        try:
            token = user.generate_token()
        except Exception as e:
            current_app.logger.error(f"Token generation failed: {e}")
            token = None

        # Safe user dict
        try:
            user_dict = user.to_dict()
        except Exception as e:
            current_app.logger.error(f"user.to_dict() failed: {e}")
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

        return jsonify({'message': 'User registered successfully', 'token': token, 'user': user_dict}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {e}")
        return jsonify({'error': 'Registration failed'}), 500

# --- User Login ---
@auth_bp.route('/login', methods=['POST'])
@validate_json_input(required_fields=['email', 'password'])
def login():
    try:
        data = request.get_json()
        email = data['email'].strip().lower()
        password = data['password']

        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401

        if hasattr(user, "reset_failed_login"):
            user.reset_failed_login()

        if hasattr(user, "update_streak"):
            user.update_streak()

        token = None
        try:
            token = user.generate_token()
        except Exception as e:
            current_app.logger.error(f"Token generation failed: {e}")

        try:
            user_dict = user.to_dict()
        except Exception as e:
            current_app.logger.error(f"user.to_dict() failed: {e}")
            user_dict = {"id": user.id, "username": user.username, "email": user.email,
                         "first_name": user.first_name, "last_name": user.last_name}

        return jsonify({'message': 'Login successful', 'token': token, 'user': user_dict}), 200

    except Exception as e:
        current_app.logger.error(f"Login failed: {e}")
        return jsonify({'error': 'Login failed'}), 500

# --- Verify Token ---
@auth_bp.route('/verify-token', methods=['POST'])
@token_required
def verify_token(current_user):
    try:
        return jsonify({'valid': True, 'user': current_user.to_dict()}), 200
    except Exception as e:
        current_app.logger.error(f"Verify token failed: {e}")
        return jsonify({'error': 'Token verification failed'}), 500

# --- Refresh Token ---
@auth_bp.route('/refresh-token', methods=['POST'])
@token_required
def refresh_token(current_user):
    try:
        new_token = current_user.generate_token()
        return jsonify({'token': new_token, 'user': current_user.to_dict()}), 200
    except Exception as e:
        current_app.logger.error(f"Token refresh failed: {e}")
        return jsonify({'error': 'Token refresh failed'}), 500

# --- Change Password ---
@auth_bp.route('/change-password', methods=['POST'])
@token_required
@validate_json_input(required_fields=['current_password', 'new_password'])
def change_password(current_user):
    try:
        data = request.get_json()
        current_password = data['current_password']
        new_password = data['new_password']

        if not current_user.check_password(current_password):
            return jsonify({'error': 'Current password is incorrect'}), 401

        password_validation = validate_password(new_password)
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400

        if current_user.check_password(new_password):
            return jsonify({'error': 'New password must be different from current password'}), 400

        current_user.set_password(new_password)
        db.session.commit()

        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Password change failed: {e}")
        return jsonify({'error': 'Password change failed'}), 500

# --- Logout ---
@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    try:
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Logout failed: {e}")
        return jsonify({'error': 'Logout failed'}), 500
