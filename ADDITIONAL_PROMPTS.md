# Additional Prompts and Configurations - StudyBuddy Enhanced

## 🤖 AI Model Configurations

### Supported AI Models
The enhanced StudyBuddy now supports multiple AI models for different use cases:

```python
SUPPORTED_MODELS = {
    "gpt-3.5-turbo": {
        "name": "GPT-3.5 Turbo",
        "description": "Fast and efficient for general tutoring",
        "max_tokens": 4096,
        "cost_effective": True
    },
    "gpt-4": {
        "name": "GPT-4",
        "description": "Advanced reasoning for complex problems",
        "max_tokens": 8192,
        "premium_only": True
    },
    "gpt-4-turbo": {
        "name": "GPT-4 Turbo",
        "description": "Latest model with enhanced capabilities",
        "max_tokens": 128000,
        "premium_only": True
    }
}
```

## 📝 Enhanced AI Prompts

### 1. Tutoring System Prompt
```
You are StudyBuddy AI, an intelligent and patient tutor designed to help students learn effectively. Your role is to:

1. **Explain Concepts Clearly**: Break down complex topics into digestible parts
2. **Encourage Learning**: Use positive reinforcement and motivational language
3. **Adapt to Learning Styles**: Adjust explanations based on student responses
4. **Provide Examples**: Use relevant, real-world examples to illustrate concepts
5. **Ask Guiding Questions**: Help students discover answers through Socratic method

Guidelines:
- Always be encouraging and supportive
- Use simple language appropriate for the student's level
- Provide step-by-step explanations for problem-solving
- Offer multiple approaches when possible
- Encourage critical thinking over memorization

Current conversation context: {conversation_history}
Student's question: {user_message}

Respond as StudyBuddy AI with helpful, educational content.
```

### 2. Flashcard Generation Prompt
```
Generate educational flashcards from the provided content. Create {count} flashcards that:

1. **Cover Key Concepts**: Focus on the most important information
2. **Use Clear Questions**: Make questions specific and unambiguous
3. **Provide Comprehensive Answers**: Include explanations, not just facts
4. **Vary Difficulty**: Mix basic recall with application questions
5. **Include Examples**: Add relevant examples where helpful

Format each flashcard as:
```json
{
  "question": "Clear, specific question",
  "answer": "Comprehensive answer with explanation",
  "difficulty": "easy|medium|hard",
  "category": "subject/topic",
  "tags": ["tag1", "tag2"]
}
```

Content to process: {content}
Number of flashcards: {count}
Subject focus: {subject}
```

### 3. Practice Test Generation Prompt
```
Create a practice test from the provided content with {question_count} questions. Include:

1. **Multiple Choice Questions** (60%): 4 options each, one correct answer
2. **True/False Questions** (20%): Clear statements with explanations
3. **Short Answer Questions** (20%): Require brief explanations

Requirements:
- Questions should test understanding, not just memorization
- Include a mix of difficulty levels
- Provide detailed explanations for all answers
- Cover different aspects of the content
- Use clear, unambiguous language

Format as:
```json
{
  "test_title": "Practice Test: {topic}",
  "questions": [
    {
      "type": "multiple_choice|true_false|short_answer",
      "question": "Question text",
      "options": ["A", "B", "C", "D"], // for multiple choice only
      "correct_answer": "Answer",
      "explanation": "Detailed explanation",
      "difficulty": "easy|medium|hard",
      "points": 1
    }
  ],
  "total_points": {total_points},
  "estimated_time": "{time} minutes"
}
```

Content: {content}
Subject: {subject}
Focus areas: {focus_areas}
```

### 4. Document Analysis Prompt
```
Analyze the uploaded document and provide:

1. **Content Summary**: Brief overview of main topics
2. **Key Concepts**: List of important terms and definitions
3. **Learning Objectives**: What students should learn from this content
4. **Study Suggestions**: How to best study this material
5. **Related Topics**: Connections to other subjects

Document content: {document_content}
Document type: {document_type}
Subject area: {subject}

Provide analysis in structured format for educational use.
```

## 🔧 Configuration Templates

### 1. OpenAI API Configuration
```python
# src/config/ai_config.py
OPENAI_CONFIG = {
    "api_key": os.getenv("OPENAI_API_KEY"),
    "api_base": os.getenv("OPENAI_API_BASE", "https://api.openai.com/v1"),
    "default_model": "gpt-3.5-turbo",
    "max_tokens": {
        "gpt-3.5-turbo": 4096,
        "gpt-4": 8192,
        "gpt-4-turbo": 128000
    },
    "temperature": 0.7,
    "top_p": 1.0,
    "frequency_penalty": 0.0,
    "presence_penalty": 0.0
}
```

### 2. IntaSend Payment Configuration
```python
# src/config/payment_config.py
INTASEND_CONFIG = {
    "publishable_key": os.getenv("INTASEND_PUBLISHABLE_KEY"),
    "secret_key": os.getenv("INTASEND_SECRET_KEY"),
    "test_mode": os.getenv("INTASEND_TEST_MODE", "true").lower() == "true",
    "webhook_secret": os.getenv("INTASEND_WEBHOOK_SECRET"),
    "currency": "KES",
    "payment_methods": ["M-PESA", "CARD", "BANK"],
    "subscription_plans": {
        "premium_monthly": {
            "name": "Premium Monthly",
            "price": 65.00,
            "duration_days": 30,
            "features": [
                "Unlimited study rooms",
                "Advanced AI tutor with GPT-4",
                "Unlimited document uploads",
                "Priority support"
            ]
        },
        "premium_yearly": {
            "name": "Premium Yearly",
            "price": 650.00,
            "duration_days": 365,
            "features": [
                "All monthly features",
                "Advanced analytics",
                "Custom branding",
                "Export study data",
                "Offline access"
            ]
        }
    }
}
```

### 3. Security Configuration
```python
# src/config/security_config.py
SECURITY_CONFIG = {
    "rate_limiting": {
        "default": "1000 per hour",
        "auth_login": "5 per minute",
        "auth_register": "3 per minute",
        "payment": "10 per minute",
        "ai_chat": "100 per hour"
    },
    "password_requirements": {
        "min_length": 8,
        "max_length": 128,
        "require_uppercase": True,
        "require_lowercase": True,
        "require_digits": True,
        "require_special": True
    },
    "jwt": {
        "expiration_hours": 24,
        "refresh_threshold_hours": 2,
        "algorithm": "HS256"
    },
    "file_upload": {
        "max_size_mb": 50,
        "allowed_extensions": [".pdf", ".doc", ".docx", ".txt", ".md"],
        "scan_for_malware": True
    }
}
```

## 🎯 Prompt Optimization Strategies

### 1. Context-Aware Responses
```python
def build_context_prompt(conversation_history, user_message, user_profile):
    context = f"""
    Student Profile:
    - Learning Level: {user_profile.get('level', 'intermediate')}
    - Preferred Style: {user_profile.get('learning_style', 'visual')}
    - Subject Focus: {user_profile.get('subjects', [])}
    
    Recent Conversation:
    {format_conversation_history(conversation_history[-5:])}
    
    Current Question: {user_message}
    
    Provide a response that:
    1. Builds on previous discussion
    2. Matches the student's learning level
    3. Uses their preferred learning style
    4. Encourages continued engagement
    """
    return context
```

### 2. Adaptive Difficulty
```python
def adjust_difficulty_prompt(user_performance, base_prompt):
    if user_performance['accuracy'] > 0.8:
        difficulty_modifier = "Increase complexity and introduce advanced concepts."
    elif user_performance['accuracy'] < 0.5:
        difficulty_modifier = "Simplify explanations and provide more basic examples."
    else:
        difficulty_modifier = "Maintain current difficulty level."
    
    return f"{base_prompt}\n\nDifficulty Adjustment: {difficulty_modifier}"
```

### 3. Subject-Specific Prompts
```python
SUBJECT_PROMPTS = {
    "mathematics": """
    For mathematics problems:
    1. Show step-by-step solutions
    2. Explain the reasoning behind each step
    3. Provide alternative solution methods when applicable
    4. Include visual representations when helpful
    5. Connect to real-world applications
    """,
    
    "science": """
    For science topics:
    1. Start with observable phenomena
    2. Explain underlying principles
    3. Use analogies and metaphors
    4. Connect to everyday experiences
    5. Encourage experimental thinking
    """,
    
    "history": """
    For historical content:
    1. Provide chronological context
    2. Explain cause-and-effect relationships
    3. Include multiple perspectives
    4. Connect to contemporary issues
    5. Use storytelling techniques
    """,
    
    "language": """
    For language learning:
    1. Provide pronunciation guides
    2. Explain grammar rules with examples
    3. Include cultural context
    4. Encourage practice through conversation
    5. Use mnemonics for vocabulary
    """
}
```

## 🔄 Dynamic Prompt Generation

### 1. Conversation Flow Management
```python
class ConversationManager:
    def __init__(self):
        self.conversation_states = {
            "greeting": "Welcome and assess student needs",
            "explaining": "Provide detailed explanations",
            "questioning": "Ask probing questions",
            "practicing": "Guide through practice problems",
            "summarizing": "Recap key learning points"
        }
    
    def get_state_prompt(self, state, context):
        base_prompt = self.conversation_states[state]
        return f"{base_prompt}\n\nContext: {context}"
```

### 2. Personalization Engine
```python
def personalize_prompt(base_prompt, user_data):
    personalizations = []
    
    if user_data.get('learning_disabilities'):
        personalizations.append("Use clear, simple language and break down complex concepts.")
    
    if user_data.get('preferred_examples') == 'sports':
        personalizations.append("Use sports analogies and examples when possible.")
    
    if user_data.get('motivation_level') == 'low':
        personalizations.append("Use encouraging language and celebrate small wins.")
    
    return f"{base_prompt}\n\nPersonalization: {' '.join(personalizations)}"
```

## 📊 Analytics and Monitoring Prompts

### 1. Learning Progress Analysis
```
Analyze the student's learning progress based on:

Interaction Data:
- Questions asked: {question_count}
- Topics covered: {topics}
- Session duration: {duration}
- Engagement level: {engagement_score}

Performance Metrics:
- Correct answers: {correct_answers}
- Improvement rate: {improvement_rate}
- Difficulty progression: {difficulty_trend}

Provide insights on:
1. Learning strengths and weaknesses
2. Recommended focus areas
3. Suggested study strategies
4. Progress milestones achieved
5. Next learning objectives

Format as structured learning report.
```

### 2. Content Effectiveness Evaluation
```
Evaluate the effectiveness of educational content based on:

Student Interactions:
- Engagement duration: {duration}
- Question frequency: {questions_per_minute}
- Comprehension indicators: {understanding_signals}
- Follow-up questions: {followup_count}

Learning Outcomes:
- Concept mastery: {mastery_level}
- Retention rate: {retention_score}
- Application ability: {application_success}

Provide recommendations for:
1. Content optimization
2. Delivery method improvements
3. Engagement enhancements
4. Difficulty adjustments
5. Additional resources needed
```

## 🚀 Advanced Features Configuration

### 1. Multi-Language Support
```python
LANGUAGE_CONFIG = {
    "supported_languages": ["en", "sw", "fr", "es"],
    "default_language": "en",
    "translation_prompts": {
        "sw": "Respond in Swahili while maintaining educational quality",
        "fr": "Répondez en français en maintenant la qualité éducative",
        "es": "Responde en español manteniendo la calidad educativa"
    }
}
```

### 2. Accessibility Features
```python
ACCESSIBILITY_CONFIG = {
    "screen_reader_support": True,
    "high_contrast_mode": True,
    "font_size_adjustment": True,
    "audio_descriptions": True,
    "simplified_language_option": True,
    "dyslexia_friendly_fonts": True
}
```

### 3. Gamification Elements
```python
GAMIFICATION_CONFIG = {
    "achievements": {
        "first_question": "Asked first question",
        "study_streak_7": "7-day study streak",
        "topic_master": "Mastered a topic",
        "helpful_peer": "Helped other students"
    },
    "point_system": {
        "question_asked": 5,
        "correct_answer": 10,
        "help_peer": 15,
        "daily_login": 2
    },
    "levels": {
        "beginner": 0,
        "intermediate": 100,
        "advanced": 500,
        "expert": 1000
    }
}
```

## 🔍 Debugging and Testing Prompts

### 1. AI Response Quality Testing
```
Test the AI tutor response for:

Quality Metrics:
1. **Accuracy**: Is the information factually correct?
2. **Clarity**: Is the explanation easy to understand?
3. **Completeness**: Does it fully address the question?
4. **Engagement**: Is it interesting and motivating?
5. **Appropriateness**: Is it suitable for the student's level?

Response to evaluate: {ai_response}
Student question: {student_question}
Expected learning outcome: {learning_objective}

Provide scoring (1-10) for each metric and improvement suggestions.
```

### 2. Error Handling Prompts
```python
ERROR_HANDLING_PROMPTS = {
    "api_timeout": "I'm experiencing some technical difficulties. Let me try a different approach to help you with this question.",
    
    "content_filter": "I notice this topic might need a more careful approach. Let me provide educational information that's appropriate and helpful.",
    
    "unclear_question": "I want to make sure I understand your question correctly. Could you provide a bit more context or rephrase your question?",
    
    "out_of_scope": "That's an interesting question! While it's outside my main expertise area, I can point you to some resources or help you break it down into smaller parts."
}
```

---

**Note**: All prompts and configurations are designed to be:
- **Educational**: Focus on learning outcomes
- **Adaptive**: Adjust to individual needs
- **Engaging**: Maintain student interest
- **Safe**: Appropriate content filtering
- **Scalable**: Support growing user base

For implementation details, refer to the respective source files in the `src/` directory.

