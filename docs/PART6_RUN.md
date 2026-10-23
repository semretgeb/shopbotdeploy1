# Part 6 — AI assistant

## What's new
- `app/services/ai.py` — provider abstraction (`GroqProvider`, model from `GROQ_MODEL`), shop-only context
  (profile + up to 60 products), strict-JSON output, "forward" on anything not in the data, prompt-injection guard.
- `app/db/repo/ai_usage.py` — DB counters: per customer/hour, per shop/day, global/day (`AI_PER_CUSTOMER_HOURLY`,
  `AI_PER_SHOP_DAILY`, `AI_GLOBAL_DAILY` in `.env`).
- `app/bot/handlers/assistant.py` — customer free text (or ❓ Ask a question) → answer, or "📨 sent to the shop";
  the owner gets a ❓ card with ✍️ Reply; the reply lands in the customer's chat and the card is marked answered.
- Owner can switch the assistant off per shop: ⚙️ Shop settings → 🤖 Assistant.
- Short conversation memory (last 3 exchanges) so follow-ups like "and in red?" work.

## Test
```powershell
python -m pytest -q        # expect 43 passed (tests use a fake provider; Groq is never called)
```

## Manual test
1. `.env` has a valid `GROQ_API_KEY`. Second account: open the shop link, type "how much are the shoes?" → answer from shop data.
2. Type "can I get a discount?" → "📨 … sent to the shop"; owner gets the ❓ card → ✍️ Reply → customer receives it.
3. Ask 11 questions within an hour → "⏳ Too many questions" (customer limit).
4. Owner: ⚙️ Shop settings → 🤖 Assistant: OFF → customer text now shows the contact message.

## Deploy
Add `GROQ_API_KEY` (and optionally `GROQ_MODEL`, the three `AI_*` limits) to EthioDeploy env vars, then:
```powershell
git add -A
git commit -m "Part 6: AI assistant with forwarding and rate limits"
git push origin main
```
