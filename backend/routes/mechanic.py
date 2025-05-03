from fastapi import APIRouter, Depends, HTTPException
from models import UserCreate, UserLogin, ServiceRequestModel
from database import db
from auth import hash_password, verify_password, create_access_token, get_current_user
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel

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
    return {"assigned_requests": requests}

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
