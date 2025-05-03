import os
from fastapi import FastAPI
from routes import customer, mechanic, admin
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.include_router(customer.router)
app.include_router(mechanic.router)
app.include_router(admin.router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Vehicle Service Center API is live"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))  # Render injects PORT env variable
    uvicorn.run("main:app", host="0.0.0.0", port=port)
