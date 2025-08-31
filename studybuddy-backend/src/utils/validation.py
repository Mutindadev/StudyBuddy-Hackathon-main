"""
Input validation utilities for StudyBuddy backend
"""
import re
import bleach
from typing import Any, Dict, List, Optional, Union
from flask import request, jsonify
from functools import wraps

# Allowed HTML tags and attributes for content sanitization
ALLOWED_TAGS = [
    'p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
    'blockquote', 'code', 'pre', 'a', 'img'
]

ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title'],
    'img': ['src', 'alt', 'width', 'height'],
    '*': ['class']
}

def sanitize_html(content: str) -> str:
    """Sanitize HTML content to prevent XSS attacks"""
    if not content:
        return ""
    return bleach.clean(content, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRIBUTES, strip=True)

def validate_email(email: str) -> bool:
    """Validate email format"""
    if not email or len(email) > 254:
        return False
    
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_password(password: str) -> Dict[str, Any]:
    """Validate password strength"""
    if not password:
        return {"valid": False, "message": "Password is required"}
    
    if len(password) < 8:
        return {"valid": False, "message": "Password must be at least 8 characters long"}
    
    if len(password) > 128:
        return {"valid": False, "message": "Password must be less than 128 characters"}
    
    # Check for at least one uppercase, lowercase, digit, and special character
    if not re.search(r'[A-Z]', password):
        return {"valid": False, "message": "Password must contain at least one uppercase letter"}
    
    if not re.search(r'[a-z]', password):
        return {"valid": False, "message": "Password must contain at least one lowercase letter"}
    
    if not re.search(r'\d', password):
        return {"valid": False, "message": "Password must contain at least one digit"}
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        return {"valid": False, "message": "Password must contain at least one special character"}
    
    return {"valid": True, "message": "Password is valid"}

def validate_username(username: str) -> Dict[str, Any]:
    """Validate username format"""
    if not username:
        return {"valid": False, "message": "Username is required"}
    
    if len(username) < 3:
        return {"valid": False, "message": "Username must be at least 3 characters long"}
    
    if len(username) > 30:
        return {"valid": False, "message": "Username must be less than 30 characters"}
    
    # Allow alphanumeric characters, underscores, and hyphens
    if not re.match(r'^[a-zA-Z0-9_-]+$', username):
        return {"valid": False, "message": "Username can only contain letters, numbers, underscores, and hyphens"}
    
    return {"valid": True, "message": "Username is valid"}

def validate_name(name: str, field_name: str = "Name") -> Dict[str, Any]:
    """Validate first name or last name"""
    if not name:
        return {"valid": False, "message": f"{field_name} is required"}
    
    if len(name) < 1:
        return {"valid": False, "message": f"{field_name} cannot be empty"}
    
    if len(name) > 50:
        return {"valid": False, "message": f"{field_name} must be less than 50 characters"}
    
    # Allow letters, spaces, hyphens, and apostrophes
    if not re.match(r"^[a-zA-Z\s\-']+$", name):
        return {"valid": False, "message": f"{field_name} can only contain letters, spaces, hyphens, and apostrophes"}
    
    return {"valid": True, "message": f"{field_name} is valid"}

def sanitize_input(data: Union[str, Dict, List]) -> Union[str, Dict, List]:
    """Recursively sanitize input data"""
    if isinstance(data, str):
        return sanitize_html(data)
    elif isinstance(data, dict):
        return {key: sanitize_input(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [sanitize_input(item) for item in data]
    else:
        return data

def validate_file_upload(file) -> Dict[str, Any]:
    """Validate file upload"""
    if not file:
        return {"valid": False, "message": "No file provided"}
    
    if file.filename == '':
        return {"valid": False, "message": "No file selected"}
    
    # Check file size (50MB limit)
    file.seek(0, 2)  # Seek to end
    file_size = file.tell()
    file.seek(0)  # Reset to beginning
    
    if file_size > 50 * 1024 * 1024:  # 50MB
        return {"valid": False, "message": "File size exceeds 50MB limit"}
    
    # Check file extension
    allowed_extensions = {'.pdf', '.doc', '.docx', '.txt', '.md', '.png', '.jpg', '.jpeg', '.gif'}
    file_ext = '.' + file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    
    if file_ext not in allowed_extensions:
        return {"valid": False, "message": f"File type {file_ext} not allowed"}
    
    return {"valid": True, "message": "File is valid"}

def validate_json_input(required_fields: List[str] = None, optional_fields: List[str] = None):
    """Decorator to validate JSON input"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({"error": "Content-Type must be application/json"}), 400
            
            data = request.get_json()
            if not data:
                return jsonify({"error": "No JSON data provided"}), 400
            
            # Check required fields
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    return jsonify({
                        "error": "Missing required fields",
                        "missing_fields": missing_fields
                    }), 400
            
            # Check for unexpected fields
            all_allowed_fields = set(required_fields or []) | set(optional_fields or [])
            if all_allowed_fields:
                unexpected_fields = [field for field in data.keys() if field not in all_allowed_fields]
                if unexpected_fields:
                    return jsonify({
                        "error": "Unexpected fields in request",
                        "unexpected_fields": unexpected_fields
                    }), 400
            
            # Sanitize input data (but don't modify request.json)
            sanitized_data = sanitize_input(data)
            
            # Store sanitized data in g for access in the route
            from flask import g
            g.sanitized_json = sanitized_data
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def validate_pagination_params():
    """Validate pagination parameters"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    if page < 1:
        page = 1
    
    if per_page < 1:
        per_page = 10
    elif per_page > 100:  # Limit to prevent abuse
        per_page = 100
    
    return page, per_page

def validate_room_code(room_code: str) -> Dict[str, Any]:
    """Validate study room code format"""
    if not room_code:
        return {"valid": False, "message": "Room code is required"}
    
    if len(room_code) != 6:
        return {"valid": False, "message": "Room code must be exactly 6 characters"}
    
    if not re.match(r'^[A-Z0-9]+$', room_code):
        return {"valid": False, "message": "Room code can only contain uppercase letters and numbers"}
    
    return {"valid": True, "message": "Room code is valid"}

def validate_payment_amount(amount: Union[str, float, int]) -> Dict[str, Any]:
    """Validate payment amount"""
    try:
        amount = float(amount)
    except (ValueError, TypeError):
        return {"valid": False, "message": "Invalid amount format"}
    
    if amount <= 0:
        return {"valid": False, "message": "Amount must be greater than 0"}
    
    if amount > 1000000:  # 1 million limit
        return {"valid": False, "message": "Amount exceeds maximum limit"}
    
    # Check for reasonable decimal places (max 2)
    if round(amount, 2) != amount:
        return {"valid": False, "message": "Amount can have at most 2 decimal places"}
    
    return {"valid": True, "message": "Amount is valid"}

