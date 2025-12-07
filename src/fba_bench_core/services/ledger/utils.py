"""
Utility functions and constants for the ledger service.
"""

from decimal import Decimal
from typing import Dict

# Map of fee types to their corresponding ledger accounts
FEE_ACCOUNT_MAP: Dict[str, str] = {
    "referral_fee": "Expenses:Fees:Referral",
    "fulfillment_fee": "Expenses:Fees:Fulfillment",
    "storage_fee": "Expenses:Fees:Storage",
    "subscription_fee": "Expenses:Fees:Subscription",
    "advertising_fee": "Expenses:Fees:Advertising",
    "refund_administration_fee": "Expenses:Fees:RefundAdmin",
    "closing_fee": "Expenses:Fees:Closing",
    "high_volume_listing_fee": "Expenses:Fees:HighVolumeListing",
    "long_term_storage_fee": "Expenses:Fees:LongTermStorage",
    "removal_order_fee": "Expenses:Fees:RemovalOrder",
    "disposal_order_fee": "Expenses:Fees:DisposalOrder",
    "labeling_fee": "Expenses:Fees:Labeling",
    "prep_fee": "Expenses:Fees:Prep",
    "bubble_wrap_fee": "Expenses:Fees:BubbleWrap",
    "taping_fee": "Expenses:Fees:Taping",
    "opaque_bagging_fee": "Expenses:Fees:OpaqueBagging",
}

def round_currency(amount: Decimal) -> Decimal:
    """
    Round a currency amount to 2 decimal places.
    """
    return amount.quantize(Decimal("0.01"))