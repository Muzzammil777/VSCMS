# backend/models.py

from pydantic import BaseModel, EmailStr
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr
    name: str
    role: str  # customer, admin, mechanic

class UserCreate(UserBase):
    password: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class VehicleModel(BaseModel):
    make: str
    model: str
    year: int

class ServiceRequestModel(BaseModel):
    service_type: str
    description: str
    vehicle: VehicleModel
