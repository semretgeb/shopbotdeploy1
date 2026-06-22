from groq import Groq
import os
from database import get_shop_context
from dotenv import load_dotenv

load_dotenv()

client = Groq(api_key=os.getenv("GROQ_API_KEY"))

def build_system_prompt(owner_id):
    shop, products = get_shop_context(owner_id)
    if not shop:
        return None

    product_list = "\n".join([
        f"- {p[0]}: {p[1]} ETB" + (f" — {p[2]}" if p[2] else "")
        for p in products
    ]) if products else "No products added yet."

    return f"""You are a friendly AI assistant for a shop called "{shop[1]}" on Telegram.

SHOP INFORMATION:
- Shop name: {shop[1]}
- Delivery: {shop[2]}
- Payment methods: {shop[3]}
- Payment number: {shop[4]}

PRODUCTS:
{product_list}

INSTRUCTIONS:
- Reply in the same language the customer uses (Amharic or English)
- Keep replies short, warm, and helpful (2-4 sentences)
- When a customer wants to order, ask for their delivery address
- After getting their address, tell them the total amount and ask them to pay via {shop[3]} to number {shop[4]}
- Tell them to send a payment screenshot after paying
- If they ask about payment status, tell them you are waiting for their screenshot
- Never confirm an order until the owner verifies payment
- Use occasional warm Ethiopian greetings like ሰላም
- Never make up prices or products not listed above"""

def get_ai_reply(owner_id, conversation_history):
    system = build_system_prompt(owner_id)
    if not system:
        return "This shop is not set up yet. Please contact the shop owner."

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1000,
            messages=[
                {"role": "system", "content": system},
                *conversation_history
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq API error: {e}")
        return "Sorry, I am having trouble right now. Please try again in a moment."
