import uuid
import json
import os
from flask import Blueprint, request, jsonify, current_app
from src.extensions import db
from src.models.ai_tutor import AIConversation, AIMessage, Flashcard, PracticeTest
from src.routes.auth import token_required

# OpenAI integration
try:
    import openai
    openai.api_key = os.environ.get('OPENAI_API_KEY')
    openai.api_base = os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

ai_bp = Blueprint("ai", __name__)

# Available AI models
AVAILABLE_MODELS = {
    'gpt-3.5-turbo': {
        'name': 'GPT-3.5 Turbo',
        'description': 'Fast and efficient for most tasks',
        'max_tokens': 4096,
        'cost_tier': 'low'
    },
    'gpt-4': {
        'name': 'GPT-4',
        'description': 'Most capable model for complex reasoning',
        'max_tokens': 8192,
        'cost_tier': 'high'
    },
    'gpt-4-turbo': {
        'name': 'GPT-4 Turbo',
        'description': 'Latest GPT-4 with improved performance',
        'max_tokens': 128000,
        'cost_tier': 'medium'
    }
}

def get_ai_response(message, model='gpt-3.5-turbo', conversation_history=None):
    """Get AI response using specified model"""
    if not OPENAI_AVAILABLE:
        return f"AI response to: {message} (OpenAI not available)"
    
    try:
        # Build conversation context
        messages = [
            {
                "role": "system",
                "content": "You are StudyBuddy AI, a helpful and knowledgeable tutor. Provide clear, accurate, and educational responses to student questions. Always encourage learning and critical thinking."
            }
        ]
        
        # Add conversation history if provided
        if conversation_history:
            for msg in conversation_history[-10:]:  # Last 10 messages for context
                messages.append({
                    "role": msg.role,
                    "content": msg.content
                })
        
        # Add current message
        messages.append({
            "role": "user",
            "content": message
        })
        
        # Make API call
        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            max_tokens=AVAILABLE_MODELS.get(model, {}).get('max_tokens', 4096) // 2,
            temperature=0.7
        )
        
        return response.choices[0].message.content
        
    except Exception as e:
        current_app.logger.error(f"OpenAI API error: {str(e)}")
        return f"I apologize, but I'm having trouble processing your request right now. Please try again later."

# ---------- Model Management ----------

@ai_bp.route("/models", methods=["GET"])
@token_required
def get_available_models(current_user):
    """Get list of available AI models"""
    return jsonify({
        "models": AVAILABLE_MODELS,
        "default_model": "gpt-3.5-turbo",
        "openai_available": OPENAI_AVAILABLE
    }), 200

# ---------- Conversations ----------

@ai_bp.route("/conversations", methods=["POST"])
@token_required
def create_conversation(current_user):
    data = request.get_json()
    title = data.get("title", "New Conversation")
    conversation_type = data.get("type", "qa")
    model = data.get("model", "gpt-3.5-turbo")

    # Validate model
    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model specified"}), 400

    conversation = AIConversation(
        title=title,
        conversation_type=conversation_type,
        user_id=current_user.id,
        model=model
    )
    db.session.add(conversation)
    db.session.commit()

    return jsonify({
        "conversation": {
            "id": conversation.id,
            "title": conversation.title,
            "type": conversation.conversation_type,
            "model": conversation.model
        }
    }), 201

@ai_bp.route("/conversations", methods=["GET"])
@token_required
def get_conversations(current_user):
    """Get user's conversations"""
    conversations = AIConversation.query.filter_by(user_id=current_user.id).order_by(
        AIConversation.created_at.desc()
    ).all()
    
    return jsonify({
        "conversations": [
            {
                "id": conv.id,
                "title": conv.title,
                "type": conv.conversation_type,
                "model": conv.model,
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "message_count": len(conv.messages)
            }
            for conv in conversations
        ]
    }), 200

@ai_bp.route("/conversations/<int:conversation_id>/messages", methods=["GET"])
@token_required
def get_conversation_messages(current_user, conversation_id):
    """Get messages from a conversation"""
    conversation = AIConversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id
    ).first()
    
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    messages = AIMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(AIMessage.created_at.asc()).all()
    
    return jsonify({
        "messages": [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None
            }
            for msg in messages
        ]
    }), 200

@ai_bp.route("/conversations/<int:conversation_id>/messages", methods=["POST"])
@token_required
def add_message(current_user, conversation_id):
    data = request.get_json()
    user_message = data.get("content")

    if not user_message or not user_message.strip():
        return jsonify({"error": "Message content is required"}), 400

    conversation = AIConversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id
    ).first()
    
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404

    # Get conversation history for context
    history = AIMessage.query.filter_by(
        conversation_id=conversation_id
    ).order_by(AIMessage.created_at.asc()).all()

    # Save user message
    user_msg = AIMessage(
        conversation_id=conversation_id,
        role="user",
        content=user_message.strip()
    )
    db.session.add(user_msg)
    db.session.flush()

    # Get AI response using the conversation's model
    ai_response = get_ai_response(
        user_message,
        model=conversation.model or 'gpt-3.5-turbo',
        conversation_history=history
    )
    
    # Save AI response
    ai_msg = AIMessage(
        conversation_id=conversation_id,
        role="assistant",
        content=ai_response
    )
    db.session.add(ai_msg)
    db.session.commit()

    return jsonify({
        "user_message": {
            "id": user_msg.id,
            "content": user_msg.content,
            "created_at": user_msg.created_at.isoformat()
        },
        "ai_message": {
            "id": ai_msg.id,
            "content": ai_msg.content,
            "created_at": ai_msg.created_at.isoformat()
        }
    }), 201

@ai_bp.route("/conversations/<int:conversation_id>/model", methods=["PUT"])
@token_required
def update_conversation_model(current_user, conversation_id):
    """Update the AI model for a conversation"""
    data = request.get_json()
    new_model = data.get("model")
    
    if not new_model or new_model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model specified"}), 400
    
    conversation = AIConversation.query.filter_by(
        id=conversation_id,
        user_id=current_user.id
    ).first()
    
    if not conversation:
        return jsonify({"error": "Conversation not found"}), 404
    
    conversation.model = new_model
    db.session.commit()
    
    return jsonify({
        "message": "Model updated successfully",
        "conversation": {
            "id": conversation.id,
            "model": conversation.model
        }
    }), 200

# ---------- Quick Chat ----------

@ai_bp.route("/chat", methods=["POST"])
@token_required
def quick_chat(current_user):
    """Quick chat without creating a conversation"""
    data = request.get_json()
    message = data.get("message")
    model = data.get("model", "gpt-3.5-turbo")
    
    if not message or not message.strip():
        return jsonify({"error": "Message is required"}), 400
    
    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model specified"}), 400
    
    # Get AI response
    ai_response = get_ai_response(message, model=model)
    
    return jsonify({
        "message": message,
        "response": ai_response,
        "model": model
    }), 200

# ---------- Flashcards ----------

@ai_bp.route("/flashcards", methods=["GET"])
@token_required
def get_flashcards(current_user):
    flashcards = Flashcard.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "flashcards": [
            {
                "id": f.id,
                "question": f.question,
                "answer": f.answer,
                "difficulty": f.difficulty,
                "category": f.category,
                "created_at": f.created_at.isoformat() if f.created_at else None
            }
            for f in flashcards
        ]
    }), 200

@ai_bp.route("/flashcards", methods=["POST"])
@token_required
def create_flashcard(current_user):
    data = request.get_json()
    flashcard = Flashcard(
        user_id=current_user.id,
        document_id=data.get("document_id"),
        question=data.get("question"),
        answer=data.get("answer"),
        difficulty=data.get("difficulty", "medium"),
        category=data.get("category", "general")
    )
    db.session.add(flashcard)
    db.session.commit()

    return jsonify({
        "flashcard": {
            "id": flashcard.id,
            "question": flashcard.question,
            "answer": flashcard.answer,
            "difficulty": flashcard.difficulty,
            "category": flashcard.category
        }
    }), 201

@ai_bp.route("/generate-flashcards", methods=["POST"])
@token_required
def generate_flashcards(current_user):
    data = request.get_json()
    text = data.get("text", "")
    count = min(data.get("count", 5), 20)  # Limit to 20 flashcards
    model = data.get("model", "gpt-3.5-turbo")
    
    if not text.strip():
        return jsonify({"error": "Text content is required"}), 400
    
    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model specified"}), 400

    # Generate flashcards using AI
    if OPENAI_AVAILABLE:
        try:
            prompt = f"""
            Create {count} educational flashcards from the following text. Format as JSON array with objects containing 'question', 'answer', 'difficulty' (easy/medium/hard), and 'category' fields.
            
            Text: {text[:2000]}  # Limit text length
            
            Return only the JSON array, no additional text.
            """
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an educational content creator. Generate high-quality flashcards that test understanding, not just memorization."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            # Parse AI response
            ai_content = response.choices[0].message.content.strip()
            if ai_content.startswith('```json'):
                ai_content = ai_content[7:-3]
            elif ai_content.startswith('```'):
                ai_content = ai_content[3:-3]
            
            generated_flashcards = json.loads(ai_content)
            
            # Add IDs and save to database
            saved_flashcards = []
            for card_data in generated_flashcards[:count]:
                flashcard = Flashcard(
                    user_id=current_user.id,
                    question=card_data.get('question', ''),
                    answer=card_data.get('answer', ''),
                    difficulty=card_data.get('difficulty', 'medium'),
                    category=card_data.get('category', 'generated')
                )
                db.session.add(flashcard)
                db.session.flush()
                saved_flashcards.append({
                    "id": flashcard.id,
                    "question": flashcard.question,
                    "answer": flashcard.answer,
                    "difficulty": flashcard.difficulty,
                    "category": flashcard.category
                })
            
            db.session.commit()
            return jsonify({"flashcards": saved_flashcards}), 200
            
        except Exception as e:
            current_app.logger.error(f"Flashcard generation error: {str(e)}")
            # Fall back to stub generation
    
    # Stub generation if OpenAI is not available
    generated = []
    for i in range(count):
        flashcard = Flashcard(
            user_id=current_user.id,
            question=f"Sample question {i+1} from the provided text",
            answer=f"Sample answer {i+1} based on the content",
            difficulty="medium",
            category="generated"
        )
        db.session.add(flashcard)
        db.session.flush()
        generated.append({
            "id": flashcard.id,
            "question": flashcard.question,
            "answer": flashcard.answer,
            "difficulty": flashcard.difficulty,
            "category": flashcard.category
        })
    
    db.session.commit()
    return jsonify({"flashcards": generated}), 200

# ---------- Practice Tests ----------

@ai_bp.route("/practice-tests", methods=["GET"])
@token_required
def get_practice_tests(current_user):
    tests = PracticeTest.query.filter_by(user_id=current_user.id).all()
    return jsonify({
        "practice_tests": [t.to_dict() for t in tests]
    }), 200

@ai_bp.route("/practice-tests", methods=["POST"])
@token_required
def create_practice_test(current_user):
    data = request.get_json()
    test = PracticeTest(
        user_id=current_user.id,
        document_id=data.get("document_id"),
        title=data.get("title"),
        questions=json.dumps(data.get("questions", [])),
        user_answers=json.dumps(data.get("user_answers", [])),
        score=data.get("score"),
        total_questions=data.get("total_questions"),
        time_taken=data.get("time_taken")
    )
    db.session.add(test)
    db.session.commit()

    return jsonify({"practice_test": test.to_dict()}), 201

@ai_bp.route("/generate-practice-test", methods=["POST"])
@token_required
def generate_practice_test(current_user):
    data = request.get_json()
    text = data.get("text", "")
    question_count = min(data.get("question_count", 5), 20)
    model = data.get("model", "gpt-3.5-turbo")
    
    if not text.strip():
        return jsonify({"error": "Text content is required"}), 400
    
    if model not in AVAILABLE_MODELS:
        return jsonify({"error": "Invalid model specified"}), 400

    # Generate practice test using AI
    if OPENAI_AVAILABLE:
        try:
            prompt = f"""
            Create a practice test with {question_count} multiple choice questions from the following text.
            Format as JSON with 'title' and 'questions' array. Each question should have 'question', 'options' (array of 4 choices), 'correct_answer' (the correct option), and 'explanation'.
            
            Text: {text[:2000]}
            
            Return only the JSON object, no additional text.
            """
            
            response = openai.ChatCompletion.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an educational assessment creator. Generate high-quality multiple choice questions that test comprehension and application."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=3000,
                temperature=0.7
            )
            
            # Parse AI response
            ai_content = response.choices[0].message.content.strip()
            if ai_content.startswith('```json'):
                ai_content = ai_content[7:-3]
            elif ai_content.startswith('```'):
                ai_content = ai_content[3:-3]
            
            generated_test = json.loads(ai_content)
            
            # Save to database
            test = PracticeTest(
                user_id=current_user.id,
                title=generated_test.get('title', 'Generated Practice Test'),
                questions=json.dumps(generated_test.get('questions', [])),
                total_questions=len(generated_test.get('questions', []))
            )
            db.session.add(test)
            db.session.commit()
            
            return jsonify({"practice_test": test.to_dict()}), 200
            
        except Exception as e:
            current_app.logger.error(f"Practice test generation error: {str(e)}")
            # Fall back to stub generation

    # Stub generation
    generated = {
        "title": "Sample Practice Test",
        "questions": [
            {
                "question": f"Sample question {i+1} based on the provided text?",
                "options": ["Option A", "Option B", "Option C", "Option D"],
                "correct_answer": "Option A",
                "explanation": f"Explanation for question {i+1}"
            }
            for i in range(question_count)
        ]
    }
    
    test = PracticeTest(
        user_id=current_user.id,
        title=generated["title"],
        questions=json.dumps(generated["questions"]),
        total_questions=len(generated["questions"])
    )
    db.session.add(test)
    db.session.commit()

    return jsonify({"practice_test": test.to_dict()}), 200
