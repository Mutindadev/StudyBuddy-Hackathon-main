from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import json
from src.models.user import User, db
from src.models.profile import ProfileSettings, LMSIntegration, UserActivity
from src.routes.auth import token_required, sanitize_input

profile_bp = Blueprint('profile', __name__)

@profile_bp.route('/settings', methods=['GET'])
@token_required
def get_profile_settings(current_user):
    """Get user's profile settings"""
    try:
        profile_settings = ProfileSettings.query.filter_by(user_id=current_user.id).first()
        
        if not profile_settings:
            # Create default profile settings
            profile_settings = ProfileSettings(user_id=current_user.id)
            db.session.add(profile_settings)
            db.session.commit()
        
        return jsonify({
            'user': current_user.to_dict(),
            'profile_settings': profile_settings.to_dict(include_private=True)
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting profile settings: {e}")
        return jsonify({'error': 'Failed to get profile settings'}), 500

@profile_bp.route('/settings', methods=['PUT'])
@token_required
def update_profile_settings(current_user):
    """Update user's profile settings"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        data = sanitize_input(data)
        
        # Get or create profile settings
        profile_settings = ProfileSettings.query.filter_by(user_id=current_user.id).first()
        if not profile_settings:
            profile_settings = ProfileSettings(user_id=current_user.id)
            db.session.add(profile_settings)
        
        # Update basic profile info
        if 'first_name' in data:
            current_user.first_name = data['first_name']
        if 'last_name' in data:
            current_user.last_name = data['last_name']
        if 'username' in data:
            # Check if username is already taken
            existing_user = User.query.filter(
                User.username == data['username'],
                User.id != current_user.id
            ).first()
            if existing_user:
                return jsonify({'error': 'Username already taken'}), 400
            current_user.username = data['username']
        
        # Update profile settings
        if 'is_public' in data:
            profile_settings.is_public = bool(data['is_public'])
        if 'show_email' in data:
            profile_settings.show_email = bool(data['show_email'])
        if 'show_study_stats' in data:
            profile_settings.show_study_stats = bool(data['show_study_stats'])
        if 'show_badges' in data:
            profile_settings.show_badges = bool(data['show_badges'])
        if 'show_streak' in data:
            profile_settings.show_streak = bool(data['show_streak'])
        if 'show_study_rooms' in data:
            profile_settings.show_study_rooms = bool(data['show_study_rooms'])
        if 'bio' in data:
            profile_settings.bio = data['bio'][:500]  # Limit bio length
        if 'learning_goals' in data:
            profile_settings.learning_goals = data['learning_goals'][:1000]
        if 'preferred_subjects' in data:
            profile_settings.set_preferred_subjects(data['preferred_subjects'])
        if 'social_links' in data:
            profile_settings.set_social_links(data['social_links'])
        if 'timezone' in data:
            profile_settings.timezone = data['timezone']
        if 'language_preference' in data:
            profile_settings.language_preference = data['language_preference']
        if 'notification_preferences' in data:
            profile_settings.set_notification_preferences(data['notification_preferences'])
        
        profile_settings.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            activity_type='profile_update',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        activity.set_activity_data({
            'updated_fields': list(data.keys()),
            'privacy_level': profile_settings.get_privacy_level()
        })
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': current_user.to_dict(),
            'profile_settings': profile_settings.to_dict(include_private=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile settings: {e}")
        return jsonify({'error': 'Failed to update profile settings'}), 500

@profile_bp.route('/public/<int:user_id>', methods=['GET'])
def get_public_profile(user_id):
    """Get public profile of a user"""
    try:
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        profile_settings = ProfileSettings.query.filter_by(user_id=user_id).first()
        if not profile_settings or not profile_settings.is_public:
            return jsonify({'error': 'Profile is private'}), 403
        
        # Build public profile data
        public_data = {
            'id': user.id,
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name,
            'avatar_url': user.avatar_url,
            'created_at': user.created_at.isoformat() if user.created_at else None
        }
        
        # Add conditionally visible fields
        if profile_settings.show_email:
            public_data['email'] = user.email
        if profile_settings.show_study_stats:
            public_data.update({
                'streak_count': user.streak_count,
                'total_study_time': user.total_study_time
            })
        if profile_settings.show_badges:
            public_data['badges'] = user.badges
        
        # Add profile settings data
        profile_data = profile_settings.to_dict(include_private=False)
        public_data.update(profile_data)
        
        return jsonify({'profile': public_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting public profile: {e}")
        return jsonify({'error': 'Failed to get public profile'}), 500

@profile_bp.route('/lms/integrations', methods=['GET'])
@token_required
def get_lms_integrations(current_user):
    """Get user's LMS integrations"""
    try:
        integrations = LMSIntegration.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).all()
        
        return jsonify({
            'integrations': [integration.to_dict() for integration in integrations]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting LMS integrations: {e}")
        return jsonify({'error': 'Failed to get LMS integrations'}), 500

@profile_bp.route('/lms/connect', methods=['POST'])
@token_required
def connect_lms(current_user):
    """Connect to an LMS"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        data = sanitize_input(data)
        lms_type = data.get('lms_type')
        
        if not lms_type:
            return jsonify({'error': 'LMS type is required'}), 400
        
        supported_lms = ['canvas', 'blackboard', 'moodle', 'google_classroom', 'teams_education']
        if lms_type not in supported_lms:
            return jsonify({
                'error': 'Unsupported LMS type',
                'supported_types': supported_lms
            }), 400
        
        # Check if integration already exists
        existing_integration = LMSIntegration.query.filter_by(
            user_id=current_user.id,
            lms_type=lms_type,
            is_active=True
        ).first()
        
        if existing_integration:
            return jsonify({'error': 'LMS integration already exists'}), 400
        
        # Create new integration (placeholder - actual OAuth flow would be implemented)
        integration = LMSIntegration(
            user_id=current_user.id,
            lms_type=lms_type,
            lms_username=data.get('lms_username'),
            sync_status='pending'
        )
        
        # Store additional integration data
        integration_data = {
            'connection_requested_at': datetime.utcnow().isoformat(),
            'connection_method': 'manual'
        }
        integration.set_integration_data(integration_data)
        
        db.session.add(integration)
        db.session.commit()
        
        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            activity_type='lms_connection',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        activity.set_activity_data({
            'lms_type': lms_type,
            'integration_id': integration.id
        })
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'message': f'{lms_type.title()} integration created successfully',
            'integration': integration.to_dict(),
            'next_steps': 'Complete OAuth flow to activate integration'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error connecting LMS: {e}")
        return jsonify({'error': 'Failed to connect LMS'}), 500

@profile_bp.route('/lms/<int:integration_id>/disconnect', methods=['DELETE'])
@token_required
def disconnect_lms(current_user, integration_id):
    """Disconnect from an LMS"""
    try:
        integration = LMSIntegration.query.filter_by(
            id=integration_id,
            user_id=current_user.id
        ).first()
        
        if not integration:
            return jsonify({'error': 'Integration not found'}), 404
        
        integration.is_active = False
        integration.updated_at = datetime.utcnow()
        db.session.commit()
        
        # Log activity
        activity = UserActivity(
            user_id=current_user.id,
            activity_type='lms_disconnection',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        activity.set_activity_data({
            'lms_type': integration.lms_type,
            'integration_id': integration.id
        })
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({'message': 'LMS integration disconnected successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error disconnecting LMS: {e}")
        return jsonify({'error': 'Failed to disconnect LMS'}), 500

@profile_bp.route('/export', methods=['POST'])
@token_required
def export_profile_data(current_user):
    """Export user's profile data"""
    try:
        data = request.get_json()
        export_format = data.get('format', 'json') if data else 'json'
        
        if export_format not in ['json', 'csv']:
            return jsonify({'error': 'Unsupported export format'}), 400
        
        # Collect user data
        export_data = {
            'user_profile': current_user.to_dict(),
            'profile_settings': None,
            'lms_integrations': [],
            'recent_activities': [],
            'export_metadata': {
                'exported_at': datetime.utcnow().isoformat(),
                'export_format': export_format,
                'data_version': '1.0'
            }
        }
        
        # Add profile settings
        profile_settings = ProfileSettings.query.filter_by(user_id=current_user.id).first()
        if profile_settings:
            export_data['profile_settings'] = profile_settings.to_dict(include_private=True)
        
        # Add LMS integrations (without sensitive tokens)
        integrations = LMSIntegration.query.filter_by(user_id=current_user.id).all()
        export_data['lms_integrations'] = [
            integration.to_dict(include_tokens=False) for integration in integrations
        ]
        
        # Add recent activities
        activities = UserActivity.query.filter_by(user_id=current_user.id)\
                                      .order_by(UserActivity.created_at.desc())\
                                      .limit(100).all()
        export_data['recent_activities'] = [activity.to_dict() for activity in activities]
        
        # Log export activity
        activity = UserActivity(
            user_id=current_user.id,
            activity_type='data_export',
            ip_address=request.remote_addr,
            user_agent=request.headers.get('User-Agent', '')
        )
        activity.set_activity_data({
            'export_format': export_format,
            'data_size': len(json.dumps(export_data))
        })
        db.session.add(activity)
        db.session.commit()
        
        return jsonify({
            'message': 'Profile data exported successfully',
            'export_data': export_data
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error exporting profile data: {e}")
        return jsonify({'error': 'Failed to export profile data'}), 500

@profile_bp.route('/activity', methods=['GET'])
@token_required
def get_user_activity(current_user):
    """Get user's recent activity"""
    try:
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # Cap at 100 records
        
        activities = UserActivity.query.filter_by(user_id=current_user.id)\
                                      .order_by(UserActivity.created_at.desc())\
                                      .limit(limit).all()
        
        return jsonify({
            'activities': [activity.to_dict() for activity in activities]
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting user activity: {e}")
        return jsonify({'error': 'Failed to get user activity'}), 500

