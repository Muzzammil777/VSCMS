from fastapi import APIRouter, Depends, HTTPException
from models import UserCreate, UserLogin, ServiceRequestModel
from database import db
from auth import hash_password, verify_password, create_access_token, get_current_user
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.post("/register")
def register_admin(user: UserCreate):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Admin already exists")
    user_data = user.dict()
    user_data["password"] = hash_password(user.password)
    user_data["role"] = "admin"
    db.users.insert_one(user_data)
    return {"message": "Admin registered successfully"}

@router.post("/login")
def login_admin(user: UserLogin):
    found = db.users.find_one({"email": user.email, "role": "admin"})
    if not found or not verify_password(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": "admin"})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/service_requests")
def get_all_service_requests(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view service requests")
    
    # Fetch all service requests
    requests = list(db.service_requests.find())
    
    # Exclude service requests with completed transactions
    filtered_requests = []
    for req in requests:
        req["_id"] = str(req["_id"])
        req["customer_id"] = str(req.get("customer_id", ""))
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

@router.post("/update_service_status/{request_id}")
def update_service_status(request_id: str, payload: dict, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can update service status")
    
    status = payload.get("status")
    if not status:
        raise HTTPException(status_code=400, detail="Status is required")
    
    result = db.service_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service request not found")
    
    return {"message": "Service request status updated"}

class VerifyUpdateModel(BaseModel):
    verified: bool

@router.post("/verify_update/{request_id}")
def verify_update(request_id: str, verify_request: VerifyUpdateModel, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can verify updates")
    
    update_data = {"update_status": "verified" if verify_request.verified else "rejected"}
    if verify_request.verified:
        update_data["status"] = "completed"  # Example: Mark as completed if verified
    
    result = db.service_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": update_data}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service request not found")
    
    return {"message": "Update verification completed"}

@router.get("/completed_transactions")
def get_all_completed_transactions(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view completed transactions")
    
    transactions = list(db.transactions.find({"status": "completed"}))
    for transaction in transactions:
        transaction["_id"] = str(transaction["_id"])
        transaction["customer_id"] = str(transaction["customer_id"])
        transaction["service_request_id"] = str(transaction["service_request_id"])
    return {"completed_transactions": transactions}

class BillModel(BaseModel):
    service_request_id: str
    amount: float
    description: str

@router.post("/generate_bill")
def generate_bill(bill: BillModel, user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can generate bills")

    # Check if the service request exists
    service_request = db.service_requests.find_one({"_id": ObjectId(bill.service_request_id)})
    if not service_request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Insert the bill into the service request
    result = db.service_requests.update_one(
        {"_id": ObjectId(bill.service_request_id)},
        {"$set": {"bill": {"amount": bill.amount, "description": bill.description}}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Failed to generate bill")

    return {"message": "Bill generated successfully"}
