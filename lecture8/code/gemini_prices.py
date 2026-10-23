"""Gemini prices for the L8 cost table, quoted from the Gemini pricing page.

Source: https://ai.google.dev/gemini-api/docs/pricing, read 2026-10-17. Dollars per
million tokens, standard paid tier. This model has no prompt-size tier, so one price
holds for every prompt length, and image input costs the same as text.
Chosen model: gemini-3.5-flash-lite (user, 2026-10-17), the model every recording uses."""
MODEL = "gemini-3.5-flash-lite"
PRICE_IN = 0.30
PRICE_OUT = 2.50   # the pricing page heads this row "Output price (including thinking tokens)"
SOURCE = "https://ai.google.dev/gemini-api/docs/pricing, read 2026-10-17"
