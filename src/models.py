from pydantic import BaseModel, Field, ConfigDict
from typing import Optional


class RequestBody(BaseModel):
    source1: str
    source2: str
    target_model: str
    max_loops: int = 4

class ProductBasicInfo(BaseModel):
    company_name: str
    factory_address: str
    model: str
    variant: str
    quality_standard: list[str]|None = None
    model_config = ConfigDict(extra='allow')

class PhysicalData(BaseModel):
    weight: float|None = Field(default=None, gt=0)
    dimensions: str|None = None
    color: str|None = None
    material: str|None = None
    model_config = ConfigDict(extra='allow')

class units(BaseModel):
    parameter_name: str = Field(description="e.g., 'Max PV Input', 'Start-up', or 'MPPT Range'")
    value: str | None = None
    unit: str | None = None
    model_config = ConfigDict(extra='allow')


class InputData(BaseModel):
    voltage: list[units] | None = None
    current: list[units] | None = None
    power: list[units] | None = None
    model_config = ConfigDict(extra='allow')

class OutputData(BaseModel):
    voltage: list[units] | None = None
    current: list[units] | None = None
    power: list[units] | None = None
    model_config = ConfigDict(extra='allow')
    
    

class SecurityData(BaseModel):
    warning: list[str] | None = None
    warranty_years: list[str] | None = None
    safety_guidelines: list[str] | None = None
    restrictions: Optional[dict] = None
    temperature: float|None = None
    operating_conditions: Optional[dict] = None
    model_config = ConfigDict(extra='allow')

class additionalInfo(BaseModel):
    title: str | None = None
    content: str | None = None
    importance_reason: str | None = None
    model_config = ConfigDict(extra='allow')
    

class ProductData(BaseModel):
    basicinfo: ProductBasicInfo
    physicalinfo: PhysicalData
    inputinfo: InputData
    outputinfo: OutputData
    securityinfo: SecurityData
    features: Optional[list[additionalInfo]] = None
    additional_info: Optional[list[additionalInfo]] = None
    model_config = ConfigDict(extra='allow')

class ReviewResultSchema(BaseModel):
    review_passed: bool
    instruction: str
    conflicts: list[str]
    model_config = ConfigDict(extra='allow')
