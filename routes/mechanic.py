from fastapi import APIRouter, Depends, HTTPException
from models import UserCreate, UserLogin, ServiceRequestModel
from database import db
from auth import hash_password, verify_password, create_access_token, get_current_user
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
import random

router = APIRouter(prefix="/mechanic", tags=["Mechanic"])

class UpdateRequestModel(BaseModel):
    update: str

class InventoryUsageModel(BaseModel):
    item_name: str
    quantity_used: int

@router.post("/register")
def register_mechanic(user: UserCreate):
    if db.users.find_one({"email": user.email}):
        raise HTTPException(status_code=400, detail="Mechanic already exists")
    user_data = user.dict()
    user_data["password"] = hash_password(user.password)
    user_data["role"] = "mechanic"
    db.users.insert_one(user_data)
    return {"message": "Mechanic registered successfully"}

@router.post("/login")
def login_mechanic(user: UserLogin):
    found = db.users.find_one({"email": user.email, "role": "mechanic"})
    if not found or not verify_password(user.password, found["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.email, "role": "mechanic"})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/assigned_requests")
def get_assigned_requests(user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can view assigned requests")
    requests = list(db.service_requests.find({"mechanic_id": str(user["_id"])}))
    for req in requests:
        req["_id"] = str(req["_id"])
        req["customer_id"] = str(req.get("customer_id", ""))
        req["service_type"] = req.get("service_type", "N/A")  # Include service type
        req["description"] = req.get("description", "N/A")  # Include description
    return {"assigned_requests": requests}

@router.get("/completed_requests")
def get_completed_requests(user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can view completed requests")
    
    # Fetch completed service requests assigned to the mechanic
    requests = list(db.service_requests.find({"mechanic_id": str(user["_id"]), "status": "completed"}))
    for req in requests:
        req["_id"] = str(req["_id"])
        req["customer_id"] = str(req.get("customer_id", ""))
    return {"completed_requests": requests}

@router.post("/update_request_status/{request_id}")
def update_request_status(request_id: str, status: str, user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can update request status")
    result = db.service_requests.update_one(
        {"_id": ObjectId(request_id), "mechanic_id": str(user["_id"])},
        {"$set": {"status": status, "updated_at": datetime.utcnow()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service request not found or not assigned to this mechanic")
    return {"message": "Service request status updated"}

@router.post("/submit_update/{request_id}")
def submit_update(request_id: str, update_request: UpdateRequestModel, user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can submit updates")
    result = db.service_requests.update_one(
        {"_id": ObjectId(request_id), "mechanic_id": str(user["_id"])},
        {"$set": {"mechanic_update": update_request.update, "update_status": "pending_admin_verification"}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Service request not found or not assigned to this mechanic")
    return {"message": "Update submitted for admin verification"}

@router.post("/record_inventory/{request_id}")
def record_inventory(request_id: str, inventory_usage: InventoryUsageModel, user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can record inventory usage")
    
    # Add the inventory usage to the inventory table
    inventory_data = inventory_usage.dict()
    inventory_data["mechanic_id"] = str(user["_id"])
    inventory_data["service_request_id"] = request_id
    inventory_data["recorded_at"] = datetime.utcnow()
    db.inventory.insert_one(inventory_data)

    return {"message": "Inventory usage recorded successfully"}

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

@router.get("/service_requests")
def get_all_service_requests(user=Depends(get_current_user)):
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Only admins can view service requests")
    
    # Fetch all service requests
    requests = list(db.service_requests.find())
    for req in requests:
        req["_id"] = str(req["_id"])
        req["customer_id"] = str(req.get("customer_id", ""))
        req["service_type"] = req.get("service_type", "N/A")
        req["description"] = req.get("description", "N/A")
        req["inventories"] = req.get("inventories", [])  # Ensure inventories are included
    return {"service_requests": requests}

@router.post("/mark_as_complete/{request_id}")
def mark_as_complete(request_id: str, user=Depends(get_current_user)):
    if user["role"] != "mechanic":
        raise HTTPException(status_code=403, detail="Only mechanics can mark services as complete")

    # Check if the service request exists
    service_request = db.service_requests.find_one({"_id": ObjectId(request_id)})
    if not service_request:
        raise HTTPException(status_code=404, detail="Service request not found")

    # Update the service request status to "completed"
    db.service_requests.update_one(
        {"_id": ObjectId(request_id)},
        {"$set": {"status": "completed", "updated_at": datetime.utcnow()}}
    )

    return {"message": "Service marked as complete"}
