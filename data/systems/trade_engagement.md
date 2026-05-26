---
schema_version: 1
topic: trade_engagement
game: poe2
last_verified: 2026-05-26
related_topics: [trade, currency, league_0_3_the_third_edict]
prerequisites: []
mastery_levels:
  not_started: "Hasn't bought or sold anything yet."
  learning: "Uses async trade for buying; doesn't list anything."
  competent: "Lists own gear at appropriate prices; manages buy + sell on async trade."
  confident: "Reads market signal; lists at-or-above market for patience-priced items; knows when chat trade still beats async (mirror-tier negotiation)."
attributed_to: [BeltonPoE, Empyrian, Ben_]
---

# Trade Engagement (PoE 2)

PoE 2 trade has two distinct surfaces in 0.5+:

1. **Asynchronous trade** (introduced 0.3) — list items in your stash, get offers without being live in your hideout
2. **Chat-based trade** (original) — direct whisper-and-meet, still relevant for mirror-tier and bespoke negotiations

## Async trade — the modern default

The async trade system flow:

1. **List an item** — mark a stash tab as "public" + set prices on items in it.
2. **Item appears on the official trade site** (the in-game trade UI + web mirror).
3. **Buyers query** the site, find your listing, send a **buy request**.
4. **You receive a notification** — accept (you teleport to a trade screen) or decline.
5. **Trade completes** without either side waiting in their hideout.

Two huge advances over chat-only:

- **No "no longer available" spam** — async trade locks the item when a buy is initiated.
- **You can stay in maps** — listings don't require live presence.

## Chat-based trade — still relevant

The original whisper-and-meet flow:

1. **Find listing on trade site**.
2. **Click "Whisper"** → game opens a chat to the seller with a standardized message.
3. **Seller invites you to their party**, you join their hideout.
4. **In-person trade** at the trade screen.

When chat trade still wins:

- **Mirror-tier items** — sellers want to verify the buyer is real before initiating. Async assumes the buyer is trustworthy; mirror trades don't.
- **Bulk currency / multi-item negotiations** — many-piece trades work better in negotiated chat.
- **Bespoke items** — items priced "ask for offer" or "best offer" go through chat.
- **Patient pricing** at the top end — the see-and-decline rhythm in chat trade lets you hold out for the right buyer.

See `negotiation_posture` edge tag for the high-end discipline.

## Pricing — listing vs market

**Listing tier choices**:

- **At-market price** — sells fast, donates margin to the next buyer.
- **At-market + 10-20%** — patient pricing. Sells in 24-48h. Captures more value.
- **Above market** — speculative. May not sell at all; risk of league-drift devaluation.
- **Bulk discount** — list at-market * 0.9 for 10x quantity. Common for currency conversion.

The **patient_pricing** edge (see edge taxonomy) lives here: fire-sale pricing donates value to flippers. List patiently, wait, find the right buyer.

## Common mistakes

- **Listing without checking market median** — listings well above the median don't sell; well below get sniped by flippers within minutes.
- **Treating all items the same** — bulk currency is a different listing pattern than mirror-tier items. Default async pricing for stack currency; chat-and-negotiate for chase items.
- **Ignoring corruption / quality variations** — two visually identical items can have very different prices due to a single mod tier or quality value. Read carefully before listing.
- **Listing in non-public stash tabs** — listings only work for items in tabs marked public. Easy to forget after a new stash tab purchase.

## See also

- `crafting_currency_overview` — what gets traded most
- `league_0_3_the_third_edict` — when async trade arrived
- `negotiation_posture` (in edge taxonomy) — high-end trade discipline
- `patient_pricing` (in edge taxonomy) — the discipline of not fire-saling
