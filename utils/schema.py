"""
This module contains the Pydantic models for the schema of the BOL.

"""
from typing import Optional

from langchain_core.pydantic_v1 import BaseModel, Field

class Address(BaseModel):
    company_name: Optional[str] = Field(..., description="The name of the company.")
    contact_person: Optional[str] = Field(None, description="The contact person at the company.")
    contact_number: Optional[str] = Field(None, description="The contact number for the company.")
    address: Optional[str] = Field(..., description="The address of the company.")

class CarrierInfo(BaseModel):
    carrier_name: Optional[str] = Field(..., description="The name of the carrier.")
    scac: Optional[str] = Field(..., description="The Standard Carrier Alpha Code (SCAC) of the carrier.")
    pro_number: Optional[str] = Field(..., description="The pro number of the carrier.")

class CustomerOrderInformation(BaseModel):
    order_number: str = Field(..., description="The customer order number.")
    shipment_id: str = Field(..., description="The shipment ID.")
    pallets: Optional[int] = Field(..., description="The number of pallets in the shipment.")
    cartons: Optional[int] = Field(..., description="The number of cartons in the shipment.")
    weight: Optional[float] = Field(..., description="The weight of the shipment in pounds.")

class Shipment(BaseModel):
    """
    The schema for the Bill of Lading (BOL) document.
    """
    ship_from: Address = Field(..., description="The address from which the shipment is being sent.")
    ship_to: Address = Field(..., description="The address to which the shipment is being sent.")
    carrier_info: CarrierInfo = Field(..., description="Information about the carrier.")
    customer_order_information: CustomerOrderInformation = Field(..., description="Information about the customer order.")