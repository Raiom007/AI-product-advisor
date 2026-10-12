from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid

from advisor.service import advise
from advisor.agent.tools import _get_stores
from advisor.core.config import load_config
from advisor.llm.gateway import Gateway
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="AI Product Advisor API")

# Setup CORS for the React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev only
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

security = HTTPBearer()

# Very basic OAuth check (in a real app, you'd verify the JWT with Auth0/JWKS)
def verify_token(credentials: HTTPAuthorizationCredentials = Security(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")
    return token

class QueryRequest(BaseModel):
    query: str
    session_id: str | None = None
    chat_history: list[dict] = []

@app.on_event("startup")
def startup_event():
    # Warm up models
    # WHY: _get_stores expects context dict with 'config' key, not raw config
    cfg = load_config()
    profile = cfg.get("_profile", os.environ.get("ADVISOR_PROFILE", "dev"))
    _get_stores({"config": cfg})
    
    if profile == "prod":
        gw = Gateway(cfg.get("models", {}), cfg.get("limits", {}))
        gw.self_check(live_probe=True)

@app.post("/api/advise")
def advise_endpoint(req: QueryRequest, token: str = Depends(verify_token)):
    session_id = req.session_id or str(uuid.uuid4())
    try:
        resp = advise(req.query, session_id=session_id, chat_history=req.chat_history)
        return {
            "session_id": session_id,
            "response": resp.model_dump()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
