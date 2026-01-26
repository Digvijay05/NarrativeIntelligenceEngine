import uvicorn
import os

if __name__ == "__main__":
    # Ensure data dir exists
    # os.makedirs("data/events", exist_ok=True)
    
    print("Starting Forensic API Server...")
    print("Docs available at: http://localhost:8000/docs")
    
    uvicorn.run(
        "backend.api.server:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
