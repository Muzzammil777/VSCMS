# backend/routes/customer.py

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from models import UserCreate, UserLogin, ServiceRequestModel
from database import db
from auth import hash_password, verify_password, create_access_token, get_current_user
from datetime import datetime
from pydantic import BaseModel
import random

router = APIRouter(prefix="/customer", tags=["Customer"])

# Model for payment
class PaymentModel(BaseModel):
    service_request_id: str
    amount: float
    payment_method: str  # e.g., "credit_card", "paypal", etc.

# Customer registration
@router.post("/register")
def register(user: UserCreate):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")
    user_data = user.dict()
    user_data["password"] = hash_password(user.password)
    user_data["role"] = user_data.get("role", "customer")  # Default to "customer"
    db.users.insert_one(user_data)
    return {"message": "Registered successfully"}

# Customer login
@router.post("/login")
def login_customer(user: UserLogin):
    found = db.users.find_one({"email": user.email, "role": "customer"})
    if not found or not verify_password(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": "customer"})
    return {"access_token": token, "token_type": "bearer"}

# Schedule a service
@router.post("/schedule_service")
def schedule_service(request: ServiceRequestModel, user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can schedule services")

    # Fetch all mechanics
    mechanics = list(db.users.find({"role": "mechanic"}))
    if not mechanics:
        raise HTTPException(status_code=404, detail="No mechanics available to assign the task")

    # Randomly select a mechanic
    selected_mechanic = random.choice(mechanics)

    # Insert service request details
    request_data = request.dict()
    request_data["customer_id"] = str(user["_id"])
    request_data["mechanic_id"] = str(selected_mechanic["_id"])
    request_data["status"] = "pending"
    request_data["created_at"] = datetime.utcnow()
    db.service_requests.insert_one(request_data)

    return {"message": "Service request submitted successfully", "mechanic": selected_mechanic["email"]}

# Get customer service requests
@router.get("/service_requests")
def get_customer_requests(user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can view their service requests")
    
    # Fetch service requests for the customer
    requests = list(db.service_requests.find({"customer_id": str(user["_id"])}))
    filtered_requests = []
    for req in requests:
        req["_id"] = str(req["_id"])
        req["mechanic_id"] = str(req.get("mechanic_id", ""))
        if "bill" in req:
            req["bill"]["amount"] = float(req["bill"]["amount"])  # Ensure amount is a float
        
        # Exclude completed transactions
        completed_transaction = db.transactions.find_one({
            "service_request_id": str(req["_id"]),
            "status": "completed"
        })
        if not completed_transaction:
            filtered_requests.append(req)

    return {"service_requests": filtered_requests}

# Initiate payment
@router.post("/initiate_payment")
def initiate_payment(payment: PaymentModel, user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can initiate payments")

    # Check if the service request exists and belongs to the customer
    service_request = db.service_requests.find_one({"_id": ObjectId(payment.service_request_id), "customer_id": str(user["_id"])})
    if not service_request:
        raise HTTPException(status_code=404, detail="Service request not found or does not belong to the customer")

    if payment.amount != service_request["bill"]["amount"]:
        raise HTTPException(status_code=400, detail="Payment amount does not match the bill")

    # Insert payment transaction
    transaction_data = {
        "customer_id": str(user["_id"]),
        "service_request_id": str(payment.service_request_id),
        "amount": payment.amount,
        "payment_method": payment.payment_method,
        "status": "completed",
        "created_at": datetime.utcnow()
    }
    inserted_id = db.transactions.insert_one(transaction_data).inserted_id
    transaction_data["_id"] = str(inserted_id)

    return {"message": "Payment completed successfully", "transaction": transaction_data}

# Get completed transactions
@router.get("/completed_transactions")
def get_completed_transactions(user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can view their completed transactions")
    
    transactions = list(db.transactions.find({"customer_id": str(user["_id"]), "status": "completed"}))
    for transaction in transactions:
        transaction["_id"] = str(transaction["_id"])
        transaction["service_request_id"] = str(transaction["service_request_id"])
    return {"completed_transactions": transactions}

from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel

app = FastAPI()

# Example model for scheduling a service
class ScheduleServiceRequest(BaseModel):
    service_type: str
    description: str
    vehicle: dict

@app.post("/customer/schedule_service")
async def schedule_service(request: ScheduleServiceRequest):
    # Logic to handle the service scheduling
    return {"message": "Service scheduled successfully!"}
