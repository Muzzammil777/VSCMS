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
