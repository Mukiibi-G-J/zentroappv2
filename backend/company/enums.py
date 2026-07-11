from enum import Enum


class SubscriptionPlan(Enum):
    FREE_TRIAL = "Free Trial"
    STANDARD = "Standard Plan"
    MULTI_BRANCH = "Multi-Branch Plan"
    PREMIUM = "Premium Plan with EFRIS"
    STARTER_PACK = "Starter Pack"
    # New value-based plans
    STARTER = "Starter"
    BUSINESS = "Business"
    PRO = "Pro"


class SubscriptionStatus(Enum):
    TRIAL = "trial"
    PENDING = "pending"
    ACTIVE = "active"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class CompanySize(Enum):
    TWO_TO_TEN_MEMBERS = "2 ~ 10 Members"
    ELEVEN_TO_FIFTY_MEMBERS = "11 ~ 50 Members"
    FIFTY_ONE_TO_TWO_HUNDRED_MEMBERS = "51 ~ 200 Members"
    TWO_HUNDRED_ONE_TO_FIVE_HUNDRED_MEMBERS = "201 ~ 500 Members"


class BusinessObjective(Enum):
    START_A_NEW_BUSINESS = "Start a New Business"
    MANAGE_EXISTING_BUSINESS = "Manage Existing Business"
    MULTI_BRANCH = "Multi-Branch Setup"


class BusinessCategory(Enum):
    PRODUCTION = "Production"
    SERVICE = "Service"
    RETAIL = "Retail"
    MANUFACTURING = "Manufacturing"
    # CONSTRUCTION = "Construction"
    # FINANCIAL_SERVICES = "Financial Services"
    # EDUCATION = "Education"
    # HEALTHCARE = "Healthcare"
    OTHER = "Other"
