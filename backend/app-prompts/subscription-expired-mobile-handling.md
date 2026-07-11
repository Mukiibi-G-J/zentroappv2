# Mobile App: Complete Subscription Flow Implementation Guide

This guide documents **everything** the ZentroApp web frontend does for the subscription flow so the mobile app can implement the same behavior. It covers backend behavior, all API endpoints, screens, state, navigation, and exact UI copy.

---

## Table of Contents

1. [Overview & Flow Diagram](#1-overview--flow-diagram)
2. [Backend: 402 Subscription Expired](#2-backend-402-subscription-expired)
3. [Login / Post-Login Redirect Logic](#3-login--post-login-redirect-logic)
4. [402 Handler (API Interceptor)](#4-402-handler-api-interceptor)
5. [Subscription Expired Modal](#5-subscription-expired-modal)
6. [Routes & Navigation](#6-routes--navigation)
7. [Subscription Page (Choose Plan)](#7-subscription-page-choose-plan)
8. [Mobile Money Payment Instructions Page](#8-mobile-money-payment-instructions-page)
9. [Payment Submitted / Verification Pending Screen](#9-payment-submitted--verification-pending-screen)
10. [Extra Users Flow](#10-extra-users-flow)
11. [Stripe Payment Flow (Card – Coming Soon)](#11-stripe-payment-flow-card--coming-soon)
12. [All API Endpoints](#12-all-api-endpoints)
13. [JWT Subscription Data](#13-jwt-subscription-data)
14. [Layout & Subscription Nav](#14-layout--subscription-nav)
15. [Implementation Checklist](#15-implementation-checklist)

---

## 1. Overview & Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│ USER LOGS IN                                                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ JWT decoded → subscription.is_active? subscription.status?               │
│ • is_active=false → navigate /subscription                               │
│ • status="pending" → navigate /subscription                              │
│ • is_active=true → proceed to app (Home, etc.)                           │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼ (user in app, makes API calls)
┌─────────────────────────────────────────────────────────────────────────┐
│ API RETURNS 402 (subscription expired)                                   │
│ → Close branch selection modal if open                                   │
│ → If on /subscription* → ignore (do nothing)                             │
│ → Else: GET mobile-money-instructions                                    │
│   → has_pending_verification? → redirect /subscription/mobile-money?fromExpired=1
│   → else → show Subscription Expired Modal                               │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
          ┌──────────────────────┴──────────────────────┐
          │                                             │
          ▼                                             ▼
┌─────────────────────────────┐           ┌─────────────────────────────────┐
│ SUBSCRIPTION EXPIRED MODAL  │           │ MOBILE MONEY (pending)           │
│ Title: Trial Period Ended   │           │ Shows "Payment submitted" screen │
│ [Proceed to Payment]        │           │ with reference, "close page"     │
└──────────────┬──────────────┘           └─────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ SUBSCRIPTION PAGE (/subscription)                                        │
│ • Fetch: pricing-plans, add-ons, mobile-money-instructions               │
│ • If has_active_subscription → redirect to app                           │
│ • If has_pending_verification → redirect /subscription/mobile-money      │
│ • Show plans, add-ons, upfront months, payment method (Mobile Money)     │
│ • [Proceed to Mobile Money] → navigate /subscription/mobile-money        │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ MOBILE MONEY PAGE (/subscription/mobile-money)                           │
│ • Fetch mobile-money-instructions                                        │
│ • If has_active_subscription → redirect to app                           │
│ • If has_pending_verification + reference → show "Payment submitted"     │
│ • Else: show instructions, amount, phone numbers, Transaction ID input   │
│ • [I HAVE PAID] → POST create-manual-payment or create-extra-users       │
│   → success → show "Payment submitted" with reference                    │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Backend: 402 Subscription Expired

### When 402 Occurs

- `SubscriptionCheckMiddleware` blocks requests when:
  - Tenant has no subscription, or
  - `subscription_end_date <= today` (including “0 days remaining”)
- Runs **after** authentication; user stays logged in.

### 402 Response

```json
{
  "code": "subscription_expired",
  "detail": "Your trial period has ended. Please proceed to the subscription page to continue."
}
```

**HTTP Status:** `402` (Payment Required)

### API Paths That Bypass 402 (Never Blocked)

| Pattern | Purpose |
|---------|---------|
| `/api/auth/` | Login, refresh, logout |
| `/api/company/subscription` | Mobile money instructions, create-manual-payment, create-extra-users |
| `/api/company/subscriptions` | Subscription listing |
| `/api/company/pricing-plans` | Pricing plans |
| `/api/company/add-ons` | Add-on plans |
| `/api/company/starter-*` | Starter pack flow |
| `/admin/`, `/static/`, `/media/` | Admin, assets |

All other `/api/` paths return 402 when subscription is expired.

---

## 3. Login / Post-Login Redirect Logic

After successful login, decode JWT and check:

```typescript
// shouldRedirectToSubscription(subscription)
// Redirect when subscription is not active
if (!subscription || !subscription.is_active) {
  navigate("/subscription");
  return;
}

// subscription.status === "pending" (needs to complete subscription)
if (subscription.status === "pending") {
  navigate("/subscription");
  return;
}
```

- **`subscription.is_active === false`** → go to `/subscription`
- **`subscription.status === "pending"`** → go to `/subscription`
- Otherwise proceed to app (Home or `authenticatedEntryPath`).

---

## 4. 402 Handler (API Interceptor)

When any API returns 402:

1. **Close branch selection modal** (if multi-branch).
2. **Skip handling** if current path includes `/subscription`.
3. **Call** `GET /api/company/subscription/mobile-money-instructions/`.
4. **If** `has_pending_verification === true`:
   - Redirect to `{origin}/subscription/mobile-money?fromExpired=1`
5. **Else** (or on error):
   - Show Subscription Expired Modal.

**Important:** Debounce/coalesce multiple 402s into one action (e.g. many failing requests on Home).

---

## 5. Subscription Expired Modal

**Title:** Trial Period Ended

**Copy:**
- Heading: Your trial period has ended
- Body: To continue using Zentro, please subscribe to a plan. You will be taken to the subscription page to choose a plan and proceed with payment.

**Actions:**
- **Proceed to Payment** (primary) → Close modal, navigate to `/subscription` with `state: { fromExpiredModal: true }`
- **Close (X)** → Same: close modal, navigate to `/subscription` with `state: { fromExpiredModal: true }`

---

## 6. Routes & Navigation

| Route | Component | Purpose |
|-------|-----------|---------|
| `/subscription` | SubscriptionPage | Choose plan, add-ons, proceed to payment |
| `/subscription/mobile-money` | MobileMoneyPaymentInstructions | Mobile money instructions, Transaction ID, Payment submitted |
| `/payment` | PaymentPage (Stripe) | Card payment (coming soon) |

**State passed via navigation:**
- `fromExpiredModal: true` – User came from subscription expired modal
- `fromUserLimit: true` – User adding extra user slots
- `fromBillingRenewal: true` – Active user renewing upfront
- `selectedPlan`, `amount`, `billingCycle`, `months` – For mobile money page
- `extraUsersOnly`, `extraUsersCount`, `pricePerUser` – For extra-users payment

---

## 7. Subscription Page (Choose Plan)

**URL:** `/subscription`

### On Load

1. Set layout to **Landing** (minimal chrome, no sidebar).
2. **Redirect** users with active subscription to app (unless `fromExpiredModal`, `fromUserLimit`, or `fromBillingRenewal`).
3. **Fetch:**
   - `GET /api/company/pricing-plans/`
   - `GET /api/company/add-ons/`
   - `GET /api/company/subscription/mobile-money-instructions/`
4. **If** `has_active_subscription` → redirect to app.
5. **If** `has_pending_verification` → redirect to `/subscription/mobile-money` (replace).
6. **If** `fromUserLimit` → fetch `GET /api/company/overview/` for user limit breakdown.

### UI

- **Heading:** Choose Your Plan (or "Add Extra User Slots" if `fromUserLimit`)
- **Subtext:** Select a plan that best fits your business needs
- **Tagline:** 14-day free trial • No upfront payment • Monthly from UGX 50,000
- **Toggle:** Monthly / Yearly (Yearly: "Save up to 20%")
- **Plan cards** via PlanComparisonTable
- **Add-ons** (AddOnsSelector)
- **Upfront months** (1–24) when Mobile Money + plan selected
- **Payment method:** Pay with Mobile Money (primary), Pay with Card (Coming soon, disabled)
- **Sticky footer:** [Proceed to Mobile Money] (or [Proceed to Payment] for card)

### From User Limit

- Different heading: "Add Extra User Slots"
- Extra users input (1–99), price per user (e.g. UGX 10,000)
- [Proceed to Mobile Money] → navigate with `extraUsersOnly`, `extraUsersCount`, `amount`, `pricePerUser`, `fromUserLimit: true`

### Proceed to Payment (Mobile Money)

Navigate to `/subscription/mobile-money` with:

```typescript
state: {
  selectedPlan,
  amount: totalAmount,  // plan * months + addOnTotal
  billingCycle: "monthly",
  months: upfrontMonths,
  fromExpiredModal,
  fromUserLimit,
  fromBillingRenewal,
}
```

---

## 8. Mobile Money Payment Instructions Page

**URL:** `/subscription/mobile-money`  
**Query:** `?fromExpired=1` (from 402 handler when pending verification)

### On Load

1. Set layout to **Landing**.
2. **Redirect** users with active subscription (unless `fromExpiredModal`, `fromUserLimit`, `fromBillingRenewal`).
3. **Fetch** `GET /api/company/subscription/mobile-money-instructions/`.
4. **If** `has_active_subscription` → redirect to app.
5. **If** `has_pending_verification` and `pending_payment_reference` → set `submitted=true`, show Payment Submitted screen.
6. **If** no `state.selectedPlan` and no `extraUsersOnly` / invalid state → redirect to `/subscription`.

### Payment Form (Before Submit)

- **Heading:** Pay with Mobile Money
- **Product line:** `{plan name or "Extra Users (N slots)"} – UGX X,XXX` (+ "monthly"/"annual"/"N months upfront")
- **Instructions:** From API (`instructions.instructions`)
- **Mobile Money Numbers:** One or more numbers with [Copy] button
- **Amount to send:** Formatted UGX
- **Account name:** From API
- **Note:** When prompted for reference, use company name or identifier. After paying, click "I HAVE PAID" and enter your transaction ID.
- **Input:** Transaction reference (Transaction ID) – **12 digits**, required
- **Button:** I HAVE PAID (disabled until valid 12-digit reference)

### Transaction Reference Validation

- Exactly **12 digits**
- Input: numeric, maxLength 12, placeholder: "12 digits from your mobile money receipt"
- Error: "Transaction reference must be exactly 12 digits"

---

## 9. Payment Submitted / Verification Pending Screen

Shown when:
1. User just submitted payment (API success), or
2. User lands with `has_pending_verification` and `pending_payment_reference`.

**UI:**

| Element | Content |
|---------|---------|
| **Icon** | Green checkmark in circle |
| **Heading** | Payment submitted |
| **Message** | We will verify your payment and activate your subscription shortly. You will receive an email when it is ready. |
| **Reference** | Your payment reference: **{reference}** (e.g. `ZENTRO-semuna-033957FF`) |
| **Footer** | You can close this page. We will contact you once verification is complete. |

**Nav:** Same SubscriptionNav (logo, user name, Logout).

**User:** Can close page. Stays logged in. Subscription remains inactive until admin verifies. On next app open, 402 → redirect to mobile-money → same screen (no re-payment).

---

## 10. Extra Users Flow

- **Trigger:** User limit reached, navigate to `/subscription` with `fromUserLimit: true`.
- **Subscription Page:** Shows "Add Extra User Slots", input 1–99, UGX per user.
- **Proceed:** Navigate to `/subscription/mobile-money` with `extraUsersOnly`, `extraUsersCount`, `amount`, `pricePerUser`, `fromUserLimit`.
- **Submit:** `POST /api/company/subscription/create-extra-users-payment/` with `extra_users_count`, `reference`.
- Same "Payment submitted" screen after success.

---

## 11. Stripe Payment Flow (Card – Coming Soon)

- Subscription page: "Pay with Card" is disabled with label "Coming soon".
- When enabled: create payment intent, navigate to `/payment` with `clientSecret`, `paymentData`, etc.
- Uses Stripe Elements; on success, verify payment and redirect to app.

---

## 12. All API Endpoints

### Subscription-Related (Bypass 402)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/company/pricing-plans/` | List pricing plans |
| GET | `/api/company/add-ons/` | List add-ons |
| GET | `/api/company/subscription/mobile-money-instructions/` | Instructions, `has_pending_verification`, `pending_payment_reference`, `has_active_subscription` |
| POST | `/api/company/subscription/create-manual-payment/` | Submit mobile money payment (plan) |
| POST | `/api/company/subscription/create-extra-users-payment/` | Submit extra users payment |

### GET mobile-money-instructions Response

```json
{
  "mobile_money_number": "0750440865",
  "mobile_money_numbers": ["0750440865", "0779899789"],
  "account_name": "ZentroApp",
  "instructions": "Send the amount to one of the numbers below. Use the reference when prompted.",
  "has_pending_verification": true,
  "pending_payment_reference": "ZENTRO-semuna-033957FF",
  "has_active_subscription": false
}
```

### POST create-manual-payment

**Request:**
```json
{
  "plan_id": 1,
  "amount": 50000,
  "billing_cycle": "monthly",
  "months": 1,
  "reference": "123456789012"
}
```

**Response (201):**
```json
{
  "billing_history_id": 1,
  "reference": "ZENTRO-semuna-033957FF",
  "amount": "50000",
  "product": "Standard Plan",
  "instructions": { ... },
  "message": "Payment submitted. We will verify and activate your subscription shortly."
}
```

### POST create-extra-users-payment

**Request:**
```json
{
  "extra_users_count": 2,
  "reference": "123456789012"
}
```

**Response:** Same shape as create-manual-payment.

### Other (Subject to 402)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/company/overview/` | Company overview, user limit (for fromUserLimit) |
| GET | `/api/user-setup/my-setup/` | Used on Home to trigger 402 check |

---

## 13. JWT Subscription Data

```json
{
  "subscription": {
    "plan": "Standard",
    "status": "trial" | "active" | "pending" | "expired",
    "is_trial": true | false,
    "is_active": true | false,
    "trial_end_date": "2025-03-15",
    "subscription_end_date": "2025-03-15"
  }
}
```

- **Redirect on login:** `!subscription.is_active` or `subscription.status === "pending"`.
- **Do not** use JWT alone for access control; backend 402 is source of truth.

---

## 14. Layout & Subscription Nav

### Layout

- **Landing** for subscription flows: minimal chrome, no sidebar.
- **Classic** for main app (sidebar, etc.).

### SubscriptionNav (Top Bar)

- Zentro logo (left)
- User name (center/right)
- **Logout** button (right)

Shown on: Subscription Page, Mobile Money Page, Payment Submitted screen.

---

## 15. Implementation Checklist

| Item | Action |
|------|--------|
| 402 | Treat as subscription expired; do not logout or show permission modal |
| Before modal | Call `getMobileMoneyInstructions`; if `has_pending_verification`, go to mobile-money |
| Subscription expired modal | Title "Trial Period Ended", copy as above, "Proceed to Payment" → /subscription |
| Login redirect | If `!is_active` or `status === "pending"` → /subscription |
| Multiple 402s | Debounce/coalesce into one modal or redirect |
| Subscription page | Fetch plans, add-ons, instructions; handle redirects; show plans, add-ons, upfront months |
| Mobile money page | Instructions, numbers, amount, 12-digit Transaction ID, "I HAVE PAID" |
| Payment submitted | Heading, message, reference, "You can close this page" |
| Extra users | Same flow with `extraUsersOnly` state and create-extra-users-payment API |
| Layout | Landing for subscription; SubscriptionNav (logo, user, Logout) |
| Skip 402 handling | When already on subscription-related screen |

---

## Self-serve plan change (`fromPlanChange`)

- **Entry:** Company app → **Company** → **Billing & Subscription** → **Change plan** navigates to `/subscription` with `location.state.fromPlanChange === true`.
- **Purpose:** Lets tenants with an **active** subscription open the plan comparison and mobile-money checkout without being redirected back to the main app (same bypass pattern as `fromBillingRenewal` and `fromUserLimit`).
- **Flow:** `SubscriptionPage` and `MobileMoneyPaymentInstructions` skip the `has_active_subscription` redirect when `fromPlanChange` is set; `navigate("/subscription/mobile-money", { state: { …, fromPlanChange: true } })` preserves the flag until payment is submitted.
- **Do not remove** these bypasses without replacing them; otherwise active users cannot self-serve a tier change.

---

## Related Files

| File | Purpose |
|------|---------|
| `zentro-backend/utils/subscription_middleware.py` | 402 middleware |
| `zentro-backend/company/views.py` | get_mobile_money_instructions, create_manual_payment, create_extra_users_payment |
| `zentro-frontend/src/services/BaseService.ts` | 402 interceptor |
| `zentro-frontend/src/services/SubscriptionServices.ts` | API calls |
| `zentro-frontend/src/components/shared/SubscriptionExpiredModal.tsx` | Modal UI |
| `zentro-frontend/src/views/Subscription/SubscriptionPage.tsx` | Plan selection |
| `zentro-frontend/src/views/Subscription/MobileMoneyPaymentInstructions.tsx` | Mobile money + Payment submitted |
| `zentro-frontend/src/utils/starterPackUtils.ts` | shouldRedirectToSubscription |
| `zentro-frontend/src/utils/hooks/useAuth.ts` | Login redirect logic |
