from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, documents, tags, analysis, clients

app = FastAPI(
    title="LexiTau API",
    description="Backend API for LexiTau application",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(clients.router)
app.include_router(tags.router)
app.include_router(analysis.router)

# Warm the value index at startup
from .db import get_db
from .routers.analysis import get_value_index

@app.on_event("startup")
def warm_indexes():
    # open a short-lived session and build LSH index once
    try:
        db = next(get_db())
        get_value_index(db)
    except Exception:
        # don't crash app on warm failure; it will build on first request
        pass

@app.get("/health")
async def health_check():
    return {"status": "healthy", "message": "LexiTau API is running"}

@app.get("/")
async def root():
    return {"message": "Welcome to LexiTau API"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)