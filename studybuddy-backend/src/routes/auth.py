from flask import Blueprint, request, jsonify, current_app, g
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
    """Require a valid JWT token"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        auth_header = request.headers.get('Authorization')
        if auth_header:
            try:
                token = auth_header.split(" ")[1]
            except IndexError:
                return jsonify({'error': 'Invalid token format'}), 401
        if not token:
            return jsonify({'error': 'Token is missing'}), 401

        try:
            payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(payload['user_id'])
            if not current_user:
                return jsonify({'error': 'Invalid token'}), 401

            if hasattr(current_user, 'is_account_locked') and current_user.is_account_locked():
                return jsonify({'error': 'Account temporarily locked'}), 423
        except jwt.ExpiredSignatureError:
            return jsonify({'error': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'error': 'Invalid token Its me'}), 401
        except Exception as e:
            current_app.logger.error(f"Token validation error: {e}")
            return jsonify({'error': 'Token validation failed'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

@auth_bp.route('/register', methods=['POST'])
@validate_json_input(
    required_fields=['username', 'email', 'password', 'first_name', 'last_name']
)
def register():
    try:
        data = g.sanitized_json

        # Validation
        for field_name, validator in [
            ('username', validate_username),
            ('email', lambda e: {'valid': validate_email(e), 'message': 'Invalid email format'}),
            ('password', validate_password),
            ('first_name', lambda n: validate_name(n, 'First name')),
            ('last_name', lambda n: validate_name(n, 'Last name'))
        ]:
            result = validator(data[field_name])
            if not result['valid']:
                return jsonify({'error': result['message']}), 400

        # Check if user exists
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

        try:
            token = user.generate_token()
        except Exception as token_err:
            current_app.logger.error(f"Token generation failed: {token_err}")
            token = None

        try:
            user_dict = user.to_dict()
        except Exception as dict_err:
            current_app.logger.error(f"user.to_dict() failed: {dict_err}")
            user_dict = {
                "id": user.id,
                "username": user.username,
                "email": user.email,
                "first_name": user.first_name,
                "last_name": user.last_name
            }

        current_app.logger.info(f"New user registered: {user.username} ({user.email})")

        return jsonify({'message': 'User registered successfully', 'token': token, 'user': user_dict}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Registration failed: {e}")
        return jsonify({'error': 'Registration failed'}), 500

@auth_bp.route('/login', methods=['POST'])
@validate_json_input(
    required_fields=['email', 'password']
)
def login():
    try:
        data = g.sanitized_json
        email = data['email'].strip().lower()
        password = data['password']

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({'error': 'Invalid email or password'}), 401

        if hasattr(user, 'is_account_locked') and user.is_account_locked():
            return jsonify({'error': 'Account temporarily locked'}), 423

        if not user.check_password(password):
            if hasattr(user, 'increment_failed_login'):
                user.increment_failed_login()
            return jsonify({'error': 'Invalid email or password'}), 401

        if hasattr(user, 'reset_failed_login'):
            user.reset_failed_login()
        if hasattr(user, 'update_streak'):
            user.update_streak()

        try:
            token = user.generate_token()
        except Exception as token_err:
            current_app.logger.error(f"Token generation failed: {token_err}")
            token = None

        try:
            user_dict = user.to_dict()
        except Exception as dict_err:
            current_app.logger.error(f"user.to_dict() failed: {dict_err}")
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
        current_app.logger.error(f"Login error: {e}")
        return jsonify({'error': 'Login failed'}), 500

@auth_bp.route('/verify-token', methods=['POST'])
@token_required
def verify_token(current_user):
    try:
        return jsonify({'valid': True, 'user': current_user.to_dict()}), 200
    except Exception as e:
        current_app.logger.error(f"Verify token error: {e}")
        return jsonify({'error': 'Token verification failed'}), 500

@auth_bp.route('/refresh-token', methods=['POST'])
@token_required
def refresh_token(current_user):
    try:
        token = current_user.generate_token()
        return jsonify({'token': token, 'user': current_user.to_dict()}), 200
    except Exception as e:
        current_app.logger.error(f"Refresh token error: {e}")
        return jsonify({'error': 'Token refresh failed'}), 500

@auth_bp.route('/change-password', methods=['POST'])
@token_required
@validate_json_input(required_fields=['current_password', 'new_password'])
def change_password(current_user):
    try:
        data = g.sanitized_json
        if not current_user.check_password(data['current_password']):
            return jsonify({'error': 'Current password is incorrect'}), 401

        password_validation = validate_password(data['new_password'])
        if not password_validation['valid']:
            return jsonify({'error': password_validation['message']}), 400

        if current_user.check_password(data['new_password']):
            return jsonify({'error': 'New password must be different'}), 400

        current_user.set_password(data['new_password'])
        db.session.commit()
        current_app.logger.info(f"Password changed: {current_user.username}")
        return jsonify({'message': 'Password changed successfully'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Change password error: {e}")
        return jsonify({'error': 'Password change failed'}), 500

@auth_bp.route('/logout', methods=['POST'])
@token_required
def logout(current_user):
    try:
        current_app.logger.info(f"User logged out: {current_user.username}")
        return jsonify({'message': 'Logged out successfully'}), 200
    except Exception as e:
        current_app.logger.error(f"Logout error: {e}")
        return jsonify({'error': 'Logout failed'}), 500
