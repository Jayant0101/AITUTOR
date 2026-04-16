import os
import sys
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.llm.assistant_service import LearningAssistantService
from app.api.auth import hash_password
import uuid

def test_registration():
    db_path = "test_learner.db"
    if os.path.exists(db_path):
        os.remove(db_path)
        
    service = LearningAssistantService(data_dir="test_data", db_path=db_path)
    service.initialize()
    
    user_id = str(uuid.uuid4())
    email = "test@example.com"
    hashed = hash_password("password123")
    
    print(f"Registering user: {email}")
    user = service.learner.register_user(
        user_id=user_id,
        email=email,
        password_hash=hashed,
        display_name="Test User"
    )
    
    print(f"User registered: {user}")
    
    # Verify lookup
    lookup = service.learner.get_user_by_email(email)
    print(f"Lookup result: {lookup}")
    
    assert lookup["email"] == email
    print("Test passed!")

if __name__ == "__main__":
    try:
        test_registration()
    except Exception as e:
        print(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
