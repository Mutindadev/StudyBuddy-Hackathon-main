from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
import json
from src.models.user import User, db
from src.models.study_room import StudyRoom, RoomMembership
from src.models.whiteboard import WhiteboardSession, WhiteboardHistory, RoomDocument, CollaborationEvent
from src.models.document import Document
from src.routes.auth import token_required, sanitize_input

whiteboard_bp = Blueprint('whiteboard', __name__)

@whiteboard_bp.route('/rooms/<int:room_id>/whiteboard', methods=['GET'])
@token_required
def get_whiteboard_session(current_user, room_id):
    """Get whiteboard session for a room"""
    try:
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Get or create whiteboard session
        whiteboard_session = WhiteboardSession.query.filter_by(
            room_id=room_id,
            is_active=True
        ).first()
        
        if not whiteboard_session:
            whiteboard_session = WhiteboardSession(room_id=room_id)
            db.session.add(whiteboard_session)
            db.session.commit()
        
        return jsonify({
            'whiteboard_session': whiteboard_session.to_dict(include_data=True),
            'room_id': room_id,
            'user_permissions': {
                'can_draw': True,
                'can_clear': membership.role in ['owner', 'moderator'],
                'can_save': True
            }
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting whiteboard session: {e}")
        return jsonify({'error': 'Failed to get whiteboard session'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/whiteboard', methods=['PUT'])
@token_required
def update_whiteboard_session(current_user, room_id):
    """Update whiteboard session data"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Get whiteboard session
        whiteboard_session = WhiteboardSession.query.filter_by(
            room_id=room_id,
            is_active=True
        ).first()
        
        if not whiteboard_session:
            whiteboard_session = WhiteboardSession(room_id=room_id)
            db.session.add(whiteboard_session)
        
        # Update session data
        session_data = data.get('session_data')
        if session_data:
            # Save current version to history before updating
            if whiteboard_session.session_data:
                history = WhiteboardHistory(
                    whiteboard_session_id=whiteboard_session.id,
                    version=whiteboard_session.version,
                    session_data=whiteboard_session.session_data,
                    modified_by=whiteboard_session.last_modified_by or current_user.id,
                    change_description=f"Version {whiteboard_session.version}"
                )
                db.session.add(history)
            
            whiteboard_session.set_session_data(session_data)
            whiteboard_session.last_modified_by = current_user.id
        
        db.session.commit()
        
        # Log collaboration event
        event = CollaborationEvent(
            room_id=room_id,
            user_id=current_user.id,
            event_type='whiteboard_update'
        )
        event.set_event_data({
            'version': whiteboard_session.version,
            'element_count': whiteboard_session.get_element_count(),
            'update_type': data.get('update_type', 'full_update')
        })
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'message': 'Whiteboard updated successfully',
            'whiteboard_session': whiteboard_session.to_dict(include_data=True)
        }), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating whiteboard session: {e}")
        return jsonify({'error': 'Failed to update whiteboard session'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/whiteboard/clear', methods=['POST'])
@token_required
def clear_whiteboard(current_user, room_id):
    """Clear whiteboard content"""
    try:
        # Check if user has permission to clear whiteboard
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership or membership.role not in ['owner', 'moderator']:
            return jsonify({'error': 'Access denied. Only room owners and moderators can clear the whiteboard.'}), 403
        
        # Get whiteboard session
        whiteboard_session = WhiteboardSession.query.filter_by(
            room_id=room_id,
            is_active=True
        ).first()
        
        if whiteboard_session:
            # Save current version to history before clearing
            if whiteboard_session.session_data:
                history = WhiteboardHistory(
                    whiteboard_session_id=whiteboard_session.id,
                    version=whiteboard_session.version,
                    session_data=whiteboard_session.session_data,
                    modified_by=whiteboard_session.last_modified_by or current_user.id,
                    change_description=f"Before clearing - Version {whiteboard_session.version}"
                )
                db.session.add(history)
            
            whiteboard_session.clear_whiteboard(current_user.id)
            db.session.commit()
            
            # Log collaboration event
            event = CollaborationEvent(
                room_id=room_id,
                user_id=current_user.id,
                event_type='whiteboard_clear'
            )
            event.set_event_data({
                'cleared_at': datetime.utcnow().isoformat(),
                'previous_version': whiteboard_session.version - 1
            })
            db.session.add(event)
            db.session.commit()
        
        return jsonify({'message': 'Whiteboard cleared successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error clearing whiteboard: {e}")
        return jsonify({'error': 'Failed to clear whiteboard'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/whiteboard/history', methods=['GET'])
@token_required
def get_whiteboard_history(current_user, room_id):
    """Get whiteboard version history"""
    try:
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Get whiteboard session
        whiteboard_session = WhiteboardSession.query.filter_by(
            room_id=room_id,
            is_active=True
        ).first()
        
        if not whiteboard_session:
            return jsonify({'history': []}), 200
        
        # Get history
        limit = request.args.get('limit', 10, type=int)
        limit = min(limit, 50)  # Cap at 50 records
        
        history = WhiteboardHistory.query.filter_by(whiteboard_session_id=whiteboard_session.id)\
                                        .order_by(WhiteboardHistory.created_at.desc())\
                                        .limit(limit).all()
        
        return jsonify({
            'history': [h.to_dict() for h in history],
            'current_version': whiteboard_session.version
        }), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting whiteboard history: {e}")
        return jsonify({'error': 'Failed to get whiteboard history'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/documents', methods=['GET'])
@token_required
def get_room_documents(current_user, room_id):
    """Get documents shared in a room"""
    try:
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Get shared documents
        room_documents = db.session.query(RoomDocument, Document, User)\
                                  .join(Document, RoomDocument.document_id == Document.id)\
                                  .join(User, RoomDocument.shared_by == User.id)\
                                  .filter(RoomDocument.room_id == room_id, RoomDocument.is_active == True)\
                                  .order_by(RoomDocument.shared_at.desc()).all()
        
        documents_data = []
        for room_doc, document, sharer in room_documents:
            doc_data = document.to_dict()
            doc_data.update({
                'room_document_id': room_doc.id,
                'shared_by': {
                    'id': sharer.id,
                    'username': sharer.username,
                    'first_name': sharer.first_name,
                    'last_name': sharer.last_name
                },
                'permissions': room_doc.permissions,
                'shared_at': room_doc.shared_at.isoformat() if room_doc.shared_at else None,
                'can_read': room_doc.can_read(),
                'can_write': room_doc.can_write(),
                'can_admin': room_doc.can_admin()
            })
            documents_data.append(doc_data)
        
        return jsonify({'documents': documents_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting room documents: {e}")
        return jsonify({'error': 'Failed to get room documents'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/documents/share', methods=['POST'])
@token_required
def share_document_in_room(current_user, room_id):
    """Share a document in a room"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        data = sanitize_input(data)
        document_id = data.get('document_id')
        permissions = data.get('permissions', 'read')
        
        if not document_id:
            return jsonify({'error': 'Document ID is required'}), 400
        
        if permissions not in ['read', 'write', 'admin']:
            return jsonify({'error': 'Invalid permissions'}), 400
        
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Check if document exists and user has access
        document = Document.query.filter_by(id=document_id).first()
        if not document:
            return jsonify({'error': 'Document not found'}), 404
        
        if document.uploader_id != current_user.id and not document.is_public:
            return jsonify({'error': 'Access denied. You do not have permission to share this document.'}), 403
        
        # Check if document is already shared in this room
        existing_share = RoomDocument.query.filter_by(
            room_id=room_id,
            document_id=document_id,
            is_active=True
        ).first()
        
        if existing_share:
            return jsonify({'error': 'Document is already shared in this room'}), 400
        
        # Create room document share
        room_document = RoomDocument(
            room_id=room_id,
            document_id=document_id,
            shared_by=current_user.id,
            permissions=permissions
        )
        
        db.session.add(room_document)
        db.session.commit()
        
        # Log collaboration event
        event = CollaborationEvent(
            room_id=room_id,
            user_id=current_user.id,
            event_type='document_share'
        )
        event.set_event_data({
            'document_id': document_id,
            'document_name': document.original_filename,
            'permissions': permissions,
            'shared_at': room_document.shared_at.isoformat()
        })
        db.session.add(event)
        db.session.commit()
        
        return jsonify({
            'message': 'Document shared successfully',
            'room_document': room_document.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error sharing document in room: {e}")
        return jsonify({'error': 'Failed to share document in room'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/documents/<int:room_document_id>/unshare', methods=['DELETE'])
@token_required
def unshare_document_from_room(current_user, room_id, room_document_id):
    """Remove document share from room"""
    try:
        # Get room document
        room_document = RoomDocument.query.filter_by(
            id=room_document_id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not room_document:
            return jsonify({'error': 'Shared document not found'}), 404
        
        # Check permissions - only the sharer or room owner/moderator can unshare
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        can_unshare = (
            room_document.shared_by == current_user.id or
            membership.role in ['owner', 'moderator']
        )
        
        if not can_unshare:
            return jsonify({'error': 'Access denied. You do not have permission to unshare this document.'}), 403
        
        # Remove share
        room_document.is_active = False
        db.session.commit()
        
        # Log collaboration event
        event = CollaborationEvent(
            room_id=room_id,
            user_id=current_user.id,
            event_type='document_unshare'
        )
        event.set_event_data({
            'document_id': room_document.document_id,
            'room_document_id': room_document_id,
            'unshared_at': datetime.utcnow().isoformat()
        })
        db.session.add(event)
        db.session.commit()
        
        return jsonify({'message': 'Document unshared successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error unsharing document from room: {e}")
        return jsonify({'error': 'Failed to unshare document from room'}), 500

@whiteboard_bp.route('/rooms/<int:room_id>/events', methods=['GET'])
@token_required
def get_collaboration_events(current_user, room_id):
    """Get recent collaboration events for a room"""
    try:
        # Check if user is a member of the room
        membership = RoomMembership.query.filter_by(
            user_id=current_user.id,
            room_id=room_id,
            is_active=True
        ).first()
        
        if not membership:
            return jsonify({'error': 'Access denied. You are not a member of this room.'}), 403
        
        # Get recent events
        limit = request.args.get('limit', 20, type=int)
        limit = min(limit, 100)  # Cap at 100 records
        
        events = db.session.query(CollaborationEvent, User)\
                           .join(User, CollaborationEvent.user_id == User.id)\
                           .filter(CollaborationEvent.room_id == room_id)\
                           .order_by(CollaborationEvent.created_at.desc())\
                           .limit(limit).all()
        
        events_data = []
        for event, user in events:
            event_data = event.to_dict()
            event_data['user'] = {
                'id': user.id,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            events_data.append(event_data)
        
        return jsonify({'events': events_data}), 200
        
    except Exception as e:
        current_app.logger.error(f"Error getting collaboration events: {e}")
        return jsonify({'error': 'Failed to get collaboration events'}), 500

