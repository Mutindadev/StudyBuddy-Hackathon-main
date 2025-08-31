from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from src.models.user import User, db
from src.models.study_room import StudyRoom, RoomMembership, StudySession
from src.routes.auth import token_required, sanitize_input
import json

room_bp = Blueprint('room', __name__)

@room_bp.route('/rooms', methods=['GET'])
@token_required
def get_rooms(current_user):
    """Get all public rooms and user's private rooms"""
    try:
        # Get public rooms
        public_rooms = StudyRoom.query.filter_by(is_private=False, is_active=True).all()
        
        # Get user's owned rooms
        owned_rooms = StudyRoom.query.filter_by(owner_id=current_user.id, is_active=True).all()
        
        # Get rooms user is a member of
        member_rooms = db.session.query(StudyRoom).join(RoomMembership).filter(
            RoomMembership.user_id == current_user.id,
            RoomMembership.is_active == True,
            StudyRoom.is_active == True
        ).all()
        
        # Combine and deduplicate rooms
        all_rooms = list({room.id: room for room in (public_rooms + owned_rooms + member_rooms)}.values())
        
        return jsonify({
            'rooms': [room.to_dict() for room in all_rooms]
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch rooms'}), 500

@room_bp.route('/rooms', methods=['POST'])
@token_required
def create_room(current_user):
    """Create a new study room"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Sanitize input
        data = sanitize_input(data)
        
        # Validate required fields
        if not data.get('name'):
            return jsonify({'error': 'Room name is required'}), 400
        
        # Create room
        room = StudyRoom(
            name=data['name'],
            description=data.get('description', ''),
            subject=data.get('subject', ''),
            owner_id=current_user.id,
            max_participants=data.get('max_participants', 10),
            is_private=data.get('is_private', False)
        )
        
        db.session.add(room)
        db.session.flush()  # Get room ID
        
        # Add owner as member
        membership = RoomMembership(
            user_id=current_user.id,
            room_id=room.id,
            role='owner'
        )
        
        db.session.add(membership)
        db.session.commit()
        
        return jsonify({
            'message': 'Room created successfully',
            'room': room.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to create room'}), 500

@room_bp.route('/rooms/<int:room_id>', methods=['GET'])
@token_required
def get_room(current_user, room_id):
    """Get room details"""
    try:
        room = StudyRoom.query.get_or_404(room_id)
        
        # Check if user has access to this room
        if room.is_private and room.owner_id != current_user.id:
            membership = RoomMembership.query.filter_by(
                user_id=current_user.id,
                room_id=room_id,
                is_active=True
            ).first()
            if not membership:
                return jsonify({'error': 'Access denied'}), 403
        
        # Get room members
        members = db.session.query(User, RoomMembership).join(RoomMembership).filter(
            RoomMembership.room_id == room_id,
            RoomMembership.is_active == True
        ).all()
        
        room_data = room.to_dict()
        room_data['members'] = [
            {
                'user': user.to_dict(),
                'membership': membership.to_dict()
            }
            for user, membership in members
        ]
        
        return jsonify({'room': room_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch room'}), 500

@room_bp.route('/rooms/<int:room_id>/join', methods=['POST'])
@token_required
def join_room(current_user, room_id):
    """Join a study room"""
    try:
        room = StudyRoom.query.get_or_404(room_id)
        
        if not room.can_join():
            return jsonify({'error': 'Room is full or inactive'}), 400
        
        # Check if already a member
        existing_membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id
        ).first()
        
        if existing_membership:
            if existing_membership.is_active:
                return jsonify({'error': 'Already a member of this room'}), 400
            else:
                # Reactivate membership
                existing_membership.is_active = True
                existing_membership.joined_at = datetime.utcnow()
        else:
            # Create new membership
            membership = RoomMembership(
                user_id=current_user.id,
                room_id=room_id,
                role='member'
            )
            db.session.add(membership)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Successfully joined room',
            'room': room.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to join room'}), 500

@room_bp.route('/rooms/<int:room_id>/leave', methods=['POST'])
@token_required
def leave_room(current_user, room_id):
    """Leave a study room"""
    try:
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Not a member of this room'}), 400
        
        if membership.role == 'owner':
            return jsonify({'error': 'Room owner cannot leave. Transfer ownership first.'}), 400
        
        membership.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Successfully left room'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to leave room'}), 500

@room_bp.route('/rooms/join-by-code', methods=['POST'])
@token_required
def join_room_by_code(current_user):
    """Join room using room code"""
    try:
        data = request.get_json()
        if not data or not data.get('room_code'):
            return jsonify({'error': 'Room code is required'}), 400
        
        room_code = sanitize_input(data['room_code'])
        room = StudyRoom.query.filter_by(room_code=room_code, is_active=True).first()
        
        if not room:
            return jsonify({'error': 'Invalid room code'}), 404
        
        if not room.can_join():
            return jsonify({'error': 'Room is full or inactive'}), 400
        
        # Check if already a member
        existing_membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room.id
        ).first()
        
        if existing_membership and existing_membership.is_active:
            return jsonify({'error': 'Already a member of this room'}), 400
        
        if existing_membership:
            existing_membership.is_active = True
            existing_membership.joined_at = datetime.utcnow()
        else:
            membership = RoomMembership(
                user_id=current_user.id,
                room_id=room.id,
                role='member'
            )
            db.session.add(membership)
        
        db.session.commit()
        
        return jsonify({
            'message': 'Successfully joined room',
            'room': room.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to join room'}), 500

@room_bp.route('/rooms/<int:room_id>/whiteboard', methods=['GET'])
@token_required
def get_whiteboard(current_user, room_id):
    """Get whiteboard data"""
    try:
        room = StudyRoom.query.get_or_404(room_id)
        
        # Check membership
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied'}), 403
        
        whiteboard_data = json.loads(room.whiteboard_data) if room.whiteboard_data else {}
        
        return jsonify({'whiteboard_data': whiteboard_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to fetch whiteboard'}), 500

@room_bp.route('/rooms/<int:room_id>/whiteboard', methods=['POST'])
@token_required
def update_whiteboard(current_user, room_id):
    """Update whiteboard data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        room = StudyRoom.query.get_or_404(room_id)
        
        # Check membership
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied'}), 403
        
        # Update whiteboard data
        room.whiteboard_data = json.dumps(data.get('whiteboard_data', {}))
        db.session.commit()
        
        return jsonify({'message': 'Whiteboard updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update whiteboard'}), 500

@room_bp.route('/rooms/<int:room_id>/sessions', methods=['POST'])
@token_required
def start_study_session(current_user, room_id):
    """Start a study session"""
    try:
        room = StudyRoom.query.get_or_404(room_id)
        
        # Check membership
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied'}), 403
        
        # Check if user already has an active session
        active_session = StudySession.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            end_time=None
        ).first()
        
        if active_session:
            return jsonify({'error': 'Session already active'}), 400
        
        # Create new session
        session = StudySession(
            room_id=room_id,
            user_id=current_user.id
        )
        
        db.session.add(session)
        db.session.commit()
        
        return jsonify({
            'message': 'Study session started',
            'session': session.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to start session'}), 500

@room_bp.route('/rooms/<int:room_id>/sessions/<int:session_id>/end', methods=['POST'])
@token_required
def end_study_session(current_user, room_id, session_id):
    """End a study session"""
    try:
        session = StudySession.query.filter_by(
            id=session_id,
            user_id=current_user.id,
            room_id=room_id
        ).first()
        
        if not session:
            return jsonify({'error': 'Session not found'}), 404
        
        if session.end_time:
            return jsonify({'error': 'Session already ended'}), 400
        
        # End session
        session.end_time = datetime.utcnow()
        session.duration_minutes = int((session.end_time - session.start_time).total_seconds() / 60)
        
        # Update user's total study time
        current_user.total_study_time += session.duration_minutes
        
        db.session.commit()
        
        return jsonify({
            'message': 'Study session ended',
            'session': session.to_dict()
        }), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to end session'}), 500



@room_bp.route('/rooms/<int:room_id>/members', methods=['GET'])
@token_required
def get_room_members(current_user, room_id):
    """Get members of a study room"""
    try:
        # Check if user has access to the room
        room = StudyRoom.query.get(room_id)
        if not room:
            return jsonify({'error': 'Room not found'}), 404
        
        # Check if room is private and user is not a member
        if room.is_private:
            membership = RoomMembership.query.filter_by(
                user_id=current_user.id,
                room_id=room_id,
                is_active=True
            ).first()
            
            if not membership:
                return jsonify({'error': 'Access denied. You are not a member of this private room.'}), 403
        
        # Get active members
        members = db.session.query(RoomMembership, User)\
                            .join(User, RoomMembership.user_id == User.id)\
                            .filter(RoomMembership.room_id == room_id, RoomMembership.is_active == True)\
                            .order_by(RoomMembership.joined_at).all()
        
        members_data = []
        for membership, user in members:
            member_data = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'avatar_url': user.avatar_url,
                'role': membership.role,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                'last_seen': membership.last_seen.isoformat() if membership.last_seen else None,
                'is_online': (datetime.utcnow() - membership.last_seen).seconds < 300 if membership.last_seen else False  # Online if seen within 5 minutes
            }
            members_data.append(member_data)
        
        return jsonify({
            'room_id': room_id,
            'members': members_data,
            'member_count': len(members_data),
            'max_participants': room.max_participants
        }), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get room members'}), 500

@room_bp.route('/rooms/<int:room_id>/presence', methods=['POST'])
@token_required
def update_presence(current_user, room_id):
    """Update user's presence in a room"""
    try:
        # Check if user is a member
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'You are not a member of this room'}), 403
        
        # Update last seen
        membership.last_seen = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Presence updated successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to update presence'}), 500

@room_bp.route('/rooms/<int:room_id>/kick/<int:user_id>', methods=['POST'])
@token_required
def kick_member(current_user, room_id, user_id):
    """Kick a member from the room (owner/moderator only)"""
    try:
        # Check if current user has permission
        current_membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not current_membership or current_membership.role not in ['owner', 'moderator']:
            return jsonify({'error': 'Access denied. Only room owners and moderators can kick members.'}), 403
        
        # Get the member to kick
        target_membership = RoomMembership.query.filter_by(
            user_id=user_id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not target_membership:
            return jsonify({'error': 'User is not a member of this room'}), 404
        
        # Cannot kick the owner
        if target_membership.role == 'owner':
            return jsonify({'error': 'Cannot kick the room owner'}), 400
        
        # Moderators can only kick regular members
        if current_membership.role == 'moderator' and target_membership.role == 'moderator':
            return jsonify({'error': 'Moderators cannot kick other moderators'}), 403
        
        # Deactivate membership
        target_membership.is_active = False
        target_membership.last_seen = datetime.utcnow()
        db.session.commit()
        
        # Log collaboration event
        from src.models.whiteboard import CollaborationEvent
        event = CollaborationEvent(
            room_id=room_id,
            user_id=current_user.id,
            event_type='member_kick'
        )
        event.set_event_data({
            'kicked_user_id': user_id,
            'kicked_at': datetime.utcnow().isoformat(),
            'reason': 'Kicked by moderator/owner'
        })
        db.session.add(event)
        db.session.commit()
        
        return jsonify({'message': 'Member kicked successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to kick member'}), 500

@room_bp.route('/rooms/<int:room_id>/promote/<int:user_id>', methods=['POST'])
@token_required
def promote_member(current_user, room_id, user_id):
    """Promote a member to moderator (owner only)"""
    try:
        # Check if current user is the owner
        room = StudyRoom.query.get(room_id)
        if not room or room.owner_id != current_user.id:
            return jsonify({'error': 'Access denied. Only room owners can promote members.'}), 403
        
        # Get the member to promote
        target_membership = RoomMembership.query.filter_by(
            user_id=user_id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not target_membership:
            return jsonify({'error': 'User is not a member of this room'}), 404
        
        if target_membership.role != 'member':
            return jsonify({'error': 'User is already a moderator or owner'}), 400
        
        # Promote to moderator
        target_membership.role = 'moderator'
        db.session.commit()
        
        # Log collaboration event
        from src.models.whiteboard import CollaborationEvent
        event = CollaborationEvent(
            room_id=room_id,
            user_id=current_user.id,
            event_type='member_promotion'
        )
        event.set_event_data({
            'promoted_user_id': user_id,
            'promoted_at': datetime.utcnow().isoformat(),
            'new_role': 'moderator'
        })
        db.session.add(event)
        db.session.commit()
        
        return jsonify({'message': 'Member promoted to moderator successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Failed to promote member'}), 500

@room_bp.route('/rooms/my-rooms', methods=['GET'])
@token_required
def get_my_rooms(current_user):
    """Get rooms where user is a member or owner"""
    try:
        # Get rooms where user is a member
        member_rooms = db.session.query(StudyRoom, RoomMembership)\
                                 .join(RoomMembership, StudyRoom.id == RoomMembership.room_id)\
                                 .filter(RoomMembership.user_id == current_user.id,
                                        RoomMembership.is_active == True,
                                        StudyRoom.is_active == True)\
                                 .order_by(RoomMembership.last_seen.desc()).all()
        
        rooms_data = []
        for room, membership in member_rooms:
            room_data = room.to_dict()
            room_data.update({
                'my_role': membership.role,
                'joined_at': membership.joined_at.isoformat() if membership.joined_at else None,
                'last_seen': membership.last_seen.isoformat() if membership.last_seen else None,
                'is_owner': room.owner_id == current_user.id
            })
            rooms_data.append(room_data)
        
        return jsonify({'rooms': rooms_data}), 200
        
    except Exception as e:
        return jsonify({'error': 'Failed to get your rooms'}), 500

