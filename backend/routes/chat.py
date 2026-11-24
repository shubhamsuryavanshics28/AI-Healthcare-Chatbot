"""
AI Chatbot and Conversation Management Routes
Handles conversational message exchange, context assembly, RAG citations, and chat persistence.
"""
import json
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User
from backend.models.chat import Conversation, ChatMessage
from backend.models.patient import PatientProfile, MedicalCondition, Allergy, PatientMedication
from backend.schemas.chat import (
    MessageSendRequest,
    ChatMessageResponse,
    ConversationSummary,
    ConversationDetailResponse,
    ChatCitation
)
from backend.security.auth import get_current_user
from backend.services.ai_service import generate_chat_response, stream_chat_response

router = APIRouter(prefix="/chat", tags=["AI Healthcare Chatbot"])


def _format_message_response(msg: ChatMessage) -> ChatMessageResponse:
    citations = []
    if msg.citations_json:
        try:
            raw_cits = json.loads(msg.citations_json)
            citations = [ChatCitation(**c) for c in raw_cits]
        except Exception:
            pass

    safety_flags = {}
    if msg.safety_flags_json:
        try:
            safety_flags = json.loads(msg.safety_flags_json)
        except Exception:
            pass

    return ChatMessageResponse(
        id=msg.id,
        conversation_id=msg.conversation_id,
        role=msg.role,
        content=msg.content,
        citations=citations if citations else None,
        safety_flags=safety_flags if safety_flags else None,
        created_at=msg.created_at
    )


@router.post("/message", response_model=ChatMessageResponse)
async def send_chat_message(
    msg_in: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Process patient chat input, execute RAG retrieval and AI reasoning, and store message thread.
    """
    cleaned_content = msg_in.content.strip() if msg_in.content else ""
    if not cleaned_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty."
        )

    conversation = None
    if msg_in.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == msg_in.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access unauthorized."
            )
    else:
        # Create new conversation with title inferred from prompt
        title_snippet = msg_in.content.strip().replace("\n", " ")[:45]
        if len(msg_in.content.strip()) > 45:
            title_snippet += "..."
        conversation = Conversation(
            user_id=current_user.id,
            title=title_snippet or "Healthcare Consultation"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    # Gather patient background for clinical context
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    demographics = []
    if profile:
        if profile.gender:
            demographics.append(f"Gender: {profile.gender}")
        if profile.date_of_birth:
            from datetime import date
            today = date.today()
            dob = profile.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            demographics.append(f"Age: {age} years")
        if profile.blood_group:
            demographics.append(f"Blood Group: {profile.blood_group}")

    conditions = [
        c.condition_name for c in db.query(MedicalCondition).filter(
            MedicalCondition.user_id == current_user.id,
            MedicalCondition.status == "active"
        ).all()
    ]
    allergies = [
        f"{a.allergen} ({a.reaction})" for a in db.query(Allergy).filter(
            Allergy.user_id == current_user.id
        ).all()
    ]
    meds = [
        f"{m.medication_name} {m.dosage}" for m in db.query(PatientMedication).filter(
            PatientMedication.user_id == current_user.id,
            PatientMedication.is_current == True
        ).all()
    ]
    patient_context = {
        "demographics": demographics,
        "conditions": conditions,
        "allergies": allergies,
        "medications": meds
    }

    # Fetch recent conversation history
    past_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc()).all()

    conv_history = [{"role": m.role, "content": m.content} for m in past_messages[-8:]]

    # Save user message to database
    user_msg_db = ChatMessage(
        conversation_id=conversation.id,
        role="user",
        content=msg_in.content.strip()
    )
    db.add(user_msg_db)
    db.commit()

    # Generate AI response (handles emergency check, RAG, and LLM)
    ai_result = await generate_chat_response(
        user_message=msg_in.content.strip(),
        conversation_history=conv_history,
        patient_context=patient_context
    )

    # Save assistant message to database
    assistant_msg_db = ChatMessage(
        conversation_id=conversation.id,
        role="assistant",
        content=ai_result.content,
        citations_json=json.dumps(ai_result.citations) if ai_result.citations else None,
        safety_flags_json=json.dumps(ai_result.safety_flags) if ai_result.safety_flags else None,
        tokens_used=ai_result.tokens_used
    )
    db.add(assistant_msg_db)
    db.commit()
    db.refresh(assistant_msg_db)

    return _format_message_response(assistant_msg_db)


@router.post("/message/stream")
async def send_chat_message_stream(
    msg_in: MessageSendRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Progressively streams the AI healthcare response via Server-Sent Events (SSE).
    Persists user and assistant messages in the database.
    """
    cleaned_content = msg_in.content.strip() if msg_in.content else ""
    if not cleaned_content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Message content cannot be empty."
        )

    conversation = None
    if msg_in.conversation_id:
        conversation = db.query(Conversation).filter(
            Conversation.id == msg_in.conversation_id,
            Conversation.user_id == current_user.id
        ).first()
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access unauthorized."
            )
    else:
        title_snippet = cleaned_content.replace("\n", " ")[:45]
        if len(cleaned_content) > 45:
            title_snippet += "..."
        conversation = Conversation(
            user_id=current_user.id,
            title=title_snippet or "Healthcare Consultation"
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    conv_id = conversation.id

    # Gather patient background for clinical context
    profile = db.query(PatientProfile).filter(PatientProfile.user_id == current_user.id).first()
    demographics = []
    if profile:
        if profile.gender:
            demographics.append(f"Gender: {profile.gender}")
        if profile.date_of_birth:
            from datetime import date
            today = date.today()
            dob = profile.date_of_birth
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            demographics.append(f"Age: {age} years")
        if profile.blood_group:
            demographics.append(f"Blood Group: {profile.blood_group}")

    conditions = [
        c.condition_name for c in db.query(MedicalCondition).filter(
            MedicalCondition.user_id == current_user.id,
            MedicalCondition.status == "active"
        ).all()
    ]
    allergies = [
        f"{a.allergen} ({a.reaction})" for a in db.query(Allergy).filter(
            Allergy.user_id == current_user.id
        ).all()
    ]
    meds = [
        f"{m.medication_name} {m.dosage}" for m in db.query(PatientMedication).filter(
            PatientMedication.user_id == current_user.id,
            PatientMedication.is_current == True
        ).all()
    ]
    patient_context = {
        "demographics": demographics,
        "conditions": conditions,
        "allergies": allergies,
        "medications": meds
    }

    # Fetch recent conversation history
    past_messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conv_id
    ).order_by(ChatMessage.created_at.asc()).all()

    conv_history = [{"role": m.role, "content": m.content} for m in past_messages[-10:]]

    # Save user message to database
    user_msg_db = ChatMessage(
        conversation_id=conv_id,
        role="user",
        content=cleaned_content
    )
    db.add(user_msg_db)
    db.commit()

    async def sse_generator():
        citations_holder = []
        safety_flags_holder = {}
        full_content_holder = []

        try:
            async for event in stream_chat_response(
                user_message=cleaned_content,
                conversation_history=conv_history,
                patient_context=patient_context
            ):
                event_type = event.get("type")
                if event_type == "start":
                    citations_holder.extend(event.get("citations", []))
                    safety_flags_holder.update(event.get("safety_flags", {}))
                    event["conversation_id"] = conv_id
                elif event_type == "emergency":
                    full_content_holder.append(event.get("content", ""))
                    citations_holder.extend(event.get("citations", []))
                    safety_flags_holder.update(event.get("safety_flags", {}))
                    event["conversation_id"] = conv_id
                elif event_type == "token":
                    full_content_holder.append(event.get("content", ""))
                elif event_type == "done":
                    if "full_content" in event:
                        final_text = event["full_content"]
                    else:
                        final_text = "".join(full_content_holder)

                    # Save assistant message to database (try request db first, then fallback to SessionLocal)
                    try:
                        assistant_msg = ChatMessage(
                            conversation_id=conv_id,
                            role="assistant",
                            content=final_text,
                            citations_json=json.dumps(citations_holder) if citations_holder else None,
                            safety_flags_json=json.dumps(safety_flags_holder) if safety_flags_holder else None,
                            tokens_used=event.get("tokens_used", 0)
                        )
                        db.add(assistant_msg)
                        db.commit()
                    except Exception:
                        from backend.database import SessionLocal
                        save_db = SessionLocal()
                        try:
                            assistant_msg = ChatMessage(
                                conversation_id=conv_id,
                                role="assistant",
                                content=final_text,
                                citations_json=json.dumps(citations_holder) if citations_holder else None,
                                safety_flags_json=json.dumps(safety_flags_holder) if safety_flags_holder else None,
                                tokens_used=event.get("tokens_used", 0)
                            )
                            save_db.add(assistant_msg)
                            save_db.commit()
                        finally:
                            save_db.close()

                # Yield SSE chunk
                yield f"data: {json.dumps(event)}\n\n"

        except Exception as e:
            err_data = json.dumps({"type": "error", "message": str(e)})
            yield f"data: {err_data}\n\n"

    return StreamingResponse(
        sse_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@router.get("/history", response_model=List[ConversationSummary])
def get_user_conversations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve list of all conversations for authenticated patient."""
    conversations = db.query(Conversation).filter(
        Conversation.user_id == current_user.id
    ).order_by(Conversation.updated_at.desc()).all()

    summaries = []
    for conv in conversations:
        msg_count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count()
        summaries.append(ConversationSummary(
            id=conv.id,
            title=conv.title,
            status=conv.status,
            created_at=conv.created_at,
            updated_at=conv.updated_at,
            message_count=msg_count
        ))
    return summaries


@router.get("/history/{conversation_id}", response_model=ConversationDetailResponse)
def get_conversation_details(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Retrieve full message history for a specific conversation."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access unauthorized."
        )

    messages = db.query(ChatMessage).filter(
        ChatMessage.conversation_id == conversation.id
    ).order_by(ChatMessage.created_at.asc()).all()

    formatted_messages = [_format_message_response(m) for m in messages]

    return ConversationDetailResponse(
        id=conversation.id,
        title=conversation.title,
        status=conversation.status,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=formatted_messages
    )


@router.delete("/history/{conversation_id}")
def delete_conversation(
    conversation_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Permanently delete a conversation and its messages."""
    conversation = db.query(Conversation).filter(
        Conversation.id == conversation_id,
        Conversation.user_id == current_user.id
    ).first()
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access unauthorized."
        )

    db.delete(conversation)
    db.commit()
    return {"message": "Conversation deleted successfully", "id": conversation_id}
