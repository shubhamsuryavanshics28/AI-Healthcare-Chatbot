"""
Authentication and User Authorization Routes
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User, UserConsent
from backend.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from backend.security.hashing import hash_password, verify_password
from backend.security.auth import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(request: Request, user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new patient account with Argon2 password hashing and consent recording.
    """
    if not user_in.agree_medical_disclaimer:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must acknowledge the medical AI disclaimer before proceeding."
        )

    # Check for existing email
    existing_user = db.query(User).filter(User.email == user_in.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists."
        )

    # Hash password securely using Argon2
    hashed_pwd = hash_password(user_in.password)

    new_user = User(
        email=user_in.email.lower(),
        hashed_password=hashed_pwd,
        full_name=user_in.full_name.strip(),
        is_active=True,
        is_admin=False
    )
    db.add(new_user)
    db.flush()

    # Record patient consent
    client_ip = request.client.host if request.client else None
    consent_disclaimer = UserConsent(
        user_id=new_user.id,
        consent_type="medical_disclaimer",
        agreed=user_in.agree_medical_disclaimer,
        ip_address=client_ip
    )
    consent_privacy = UserConsent(
        user_id=new_user.id,
        consent_type="privacy_policy",
        agreed=user_in.agree_privacy_policy,
        ip_address=client_ip
    )
    db.add(consent_disclaimer)
    db.add(consent_privacy)
    db.commit()
    db.refresh(new_user)

    # Create JWT token
    access_token = create_access_token(data={"sub": str(new_user.id), "email": new_user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(new_user)
    )


@router.post("/login", response_model=Token)
def login(credentials: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate patient credentials and issue JWT access token.
    """
    user = db.query(User).filter(User.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account has been deactivated. Please contact support."
        )

    access_token = create_access_token(data={"sub": str(user.id), "email": user.email})

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user)
    )


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(current_user: User = Depends(get_current_user)):
    """Return currently authenticated user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Client-side token invalidation acknowledgment.
    """
    return {"message": "Logged out successfully", "user_id": current_user.id}
