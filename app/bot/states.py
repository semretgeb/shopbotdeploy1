"""Conversation state names stored in chat_states.state. Prefix = owning module."""

IDLE = "idle"

# Onboarding wizard
ONB_NAME = "onb_name"
ONB_DESC = "onb_desc"
ONB_PHONE = "onb_phone"
ONB_DELIVERY = "onb_delivery"
ONB_PAYMENT = "onb_payment"
ONB_STEPS = (ONB_NAME, ONB_DESC, ONB_PHONE, ONB_DELIVERY, ONB_PAYMENT)

# Add product wizard
PROD_PHOTO = "prod_photo"
PROD_NAME = "prod_name"
PROD_PRICE = "prod_price"
PROD_STOCK = "prod_stock"
PROD_CATEGORY = "prod_category"
PROD_CATEGORY_NEW = "prod_category_new"
PROD_PREVIEW = "prod_preview"

# Edit one field of an existing product (data: product_id, field)
PROD_EDIT_FIELD = "prod_edit_field"

# Shop settings edit (data: field)
SETTINGS_EDIT = "settings_edit"

# Customer chat checkout (data: cart {product_id: qty}, name, phone, address, payment)
CUST_NAME = "cust_name"
CUST_PHONE = "cust_phone"
CUST_ADDRESS = "cust_address"
CUST_PAYMENT = "cust_payment"
CUST_CONFIRM = "cust_confirm"
CUST_PROOF = "cust_proof"  # waiting for a payment screenshot (data: order_id)

# Owner rejecting an order (data: order_id)
ORD_REJECT_REASON = "ord_reject_reason"

# Customer typing a question for the assistant (data: chat_hist)
CUST_ASK = "cust_ask"
# Owner replying to a forwarded question (data: fq_id)
FQ_REPLY = "fq_reply"

# Owner sending a subscription payment screenshot
SUBS_PROOF = "subs_proof"
# Admin typing a broadcast / pause reason (data: text | shop_id)
ADMIN_BROADCAST = "admin_broadcast"
