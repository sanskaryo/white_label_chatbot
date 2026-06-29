# WHAT DOES THIS FILE DO: Pydantic request/response models for FastAPI

# ================== IMPORTS ==================
from typing import List, Optional
from pydantic import BaseModel, Field
# ================== IMPORTS ==================


# =========== PYDANTIC MODELS ===========

class ConversationTurn(BaseModel):
    ''' Represent one user or assistant message in conversation history '''
    role: str = Field(..., pattern="^(user|assistant)$")  # USE: Regex pattern to enforce role values
    content: str = Field(..., max_length=800)


class ChatRequest(BaseModel):
    ''' Chat endpoint request with question, search params, and history '''
    question: Optional[str] = Field(None, max_length=500, description="The user query")
    top_k: Optional[int] = Field(None, le=20, description="Number of chunks to retrieve")  # USE: le=20 to limit search breadth
    conversation_history: Optional[List[ConversationTurn]] = Field(None, max_length=6, description="Previous messages in conversation")

# =========== PYDANTIC MODELS ===========
