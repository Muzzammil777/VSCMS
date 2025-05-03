# backend/routes/customer.py

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException
from models import UserCreate, UserLogin, ServiceRequestModel
from database import db
from auth import hash_password, verify_password, create_access_token, get_current_user
from datetime import datetime
from pydantic import BaseModel

router = APIRouter(prefix="/customer", tags=["Customer"])

# backend/routes/customer.py

class PaymentModel(BaseModel):
    service_request_id: str
    amount: float
    payment_method: str  # e.g., "credit_card", "paypal", etc.

@router.post("/register")
def register(user: UserCreate):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="User already exists")
    user_data = user.dict()
    user_data["password"] = hash_password(user.password)
    # Use the role provided by the frontend
    user_data["role"] = user_data.get("role", "customer")  # Default to "customer" if not provided
    db.users.insert_one(user_data)
    return {"message": "Registered successfully"}


@router.post("/login")
def login_customer(user: UserLogin):
    found = db.users.find_one({"email": user.email, "role": "customer"})
    if not found or not verify_password(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": "customer"})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/schedule_service")
def schedule_service(request: ServiceRequestModel, user=Depends(get_current_user)):
    print(user)  # Debug: Print the logged-in user's details
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can schedule services")

    # Find the least busy mechanic (based on the number of assigned tasks)
    mechanic = db.users.aggregate([
        {"$match": {"role": "mechanic"}},
        {"$lookup": {
            "from": "service_requests",
            "localField": "_id",
            "foreignField": "mechanic_id",
            "as": "tasks"
        }},
        {"$addFields": {"task_count": {"$size": "$tasks"}}},
        {"$sort": {"task_count": 1}},
        {"$limit": 1}
    ])
    mechanic = list(mechanic)
    if not mechanic:
        raise HTTPException(status_code=404, detail="No mechanics available to assign the task")
    mechanic = mechanic[0]

    # Insert service request details into the service_requests table
    request_data = request.dict()
    request_data["customer_id"] = str(user["_id"])
    request_data["mechanic_id"] = str(mechanic["_id"])  # Assign the least busy mechanic
    request_data["status"] = "pending"
    request_data["created_at"] = datetime.utcnow()
    db.service_requests.insert_one(request_data)

    return {"message": "Service request submitted successfully"}

@router.get("/service_requests")
def get_customer_requests(user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can view their service requests")
    
    # Fetch service requests for the customer
    requests = list(db.service_requests.find({"customer_id": str(user["_id"])}))
    
    # Exclude service requests with completed transactions
    filtered_requests = []
    for req in requests:
        req["_id"] = str(req["_id"])
        req["mechanic_id"] = str(req.get("mechanic_id", ""))
        if "bill" in req:
            req["bill"]["amount"] = float(req["bill"]["amount"])  # Ensure amount is a float
        
        # Check if the transaction for this service request is completed
        completed_transaction = db.transactions.find_one({
            "service_request_id": str(req["_id"]),
            "status": "completed"
        })
        if not completed_transaction:
            filtered_requests.append(req)  # Add only non-completed transactions

    return {"service_requests": filtered_requests}

@router.post("/initiate_payment")
def initiate_payment(payment: PaymentModel, user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can initiate payments")

    # Check if the service request exists and belongs to the customer
    service_request = db.service_requests.find_one({"_id": ObjectId(payment.service_request_id), "customer_id": str(user["_id"])})
    if not service_request:
        raise HTTPException(status_code=404, detail="Service request not found or does not belong to the customer")

    # Insert the payment transaction into the transactions table
    transaction_data = {
        "customer_id": str(user["_id"]),
        "service_request_id": str(payment.service_request_id),
        "amount": payment.amount,
        "payment_method": payment.payment_method,
        "status": "completed",  # Mark as completed after payment
        "created_at": datetime.utcnow()
    }
    inserted_id = db.transactions.insert_one(transaction_data).inserted_id
    transaction_data["_id"] = str(inserted_id)  # Add the inserted transaction ID

    return {"message": "Payment completed successfully", "transaction": transaction_data}

@router.get("/completed_transactions")
def get_completed_transactions(user=Depends(get_current_user)):
    if user["role"] != "customer":
        raise HTTPException(status_code=403, detail="Only customers can view their completed transactions")
    
    transactions = list(db.transactions.find({"customer_id": str(user["_id"]), "status": "completed"}))
    for transaction in transactions:
        transaction["_id"] = str(transaction["_id"])
        transaction["service_request_id"] = str(transaction["service_request_id"])
    return {"completed_transactions": transactions}
