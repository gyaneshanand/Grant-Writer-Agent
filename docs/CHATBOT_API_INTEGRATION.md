# Chatbot API Integration Guide

> **For Frontend Teams** — API contract, request/response schemas, and integration scenarios.
>
> **Last Updated:** March 2026 — FAQ-powered responses for account_support, eligibility_assessment, application_guidance, and product_navigation.

## Base URL
```
POST /api/v1/chatbot/chat
```

---

## Request Schema

```typescript
interface ChatRequest {
  message: string;              // Required, 1-1000 chars
  session_id?: string;          // Auto-generated UUID if omitted
  user_id?: number;             // Set by auth layer (optional)
  user_type?: "guest-user" | "unpaid-user" | "paid-user";  // Default: "guest-user"
  conversation_mode?: "stateless" | "stateful";  // Default: "stateless"
  conversation_history?: ConversationTurn[];     // For stateless mode
}

interface ConversationTurn {
  role: "user" | "assistant";
  content: string;
  query_type?: string;
  extracted_entities?: object;
}
```

### Request Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✅ | — | User's message (1-1000 chars) |
| `session_id` | string | ❌ | Auto UUID | Session identifier for conversation continuity |
| `user_type` | string | ❌ | `"guest-user"` | User subscription status for CTA differentiation |
| `conversation_mode` | string | ❌ | `"stateless"` | `stateless` = FE manages history, `stateful` = server loads from DB |
| `conversation_history` | array | ❌ | `[]` | Full history (stateless mode only) |

---

## Response Schema

```typescript
interface ChatResponse {
  response: string;                    // Text response to display
  query_type: string;                  // Intent classification
  extracted_entities?: ExtractedEntities;
  total_grants?: number;               // Grant count (grant_search only)
  cta_type?: "signup" | "subscribe" | "view_grants";
  user_type: string;                   // Echo of request user_type
  is_follow_up: boolean;               // Was this a follow-up query?
  session_id: string;                  // Session UUID
  conversation_history: ConversationTurn[];  // Updated history (stateless mode)
}

interface ExtractedEntities {
  interest_slugs: string[];      // e.g., ["education", "arts,culture,history-&-humanities"]
  location_slugs: string[];      // e.g., ["california-usa", "new-york-usa"]
  eligibility_criteria_slugs: string[];
}
```

### Response Fields

| Field | Type | Present When | Description |
|-------|------|--------------|-------------|
| `response` | string | Always | The chatbot's text response |
| `query_type` | string | Always | Intent: `greeting`, `grant_search`, `product_navigation`, `account_support`, `eligibility_assessment`, `application_guidance`, `other` |
| `extracted_entities` | object | grant_search | Parsed filters from user query |
| `total_grants` | number | grant_search | Total matching grants count |
| `cta_type` | string | grant_search (with results) | CTA button type to render |
| `user_type` | string | Always | User's subscription status |
| `is_follow_up` | boolean | Always | If query refined a previous search |
| `session_id` | string | Always | Session UUID |
| `conversation_history` | array | Always | Full updated conversation (for stateless mode) |

---

## Query Types

| Query Type | Trigger Examples | Response Behavior |
|------------|------------------|-------------------|
| `greeting` | "Hello", "Hi" | Friendly greeting, no CTA |
| `grant_search` | "Find grants for...", "Education grants in NY" | SQL search → grant count + summary + CTA |
| `product_navigation` | "What's the price?", "How does your site work?", "What does Deadline Ongoing mean?" | **FAQ RAG** for platform questions; static pricing context for pricing questions |
| `account_support` | "Cancel my subscription", "I can't log in", "I was charged twice" | **FAQ RAG** → precise FAQ answer; falls back to support email redirect |
| `eligibility_assessment` | "Can I filter by state?", "Am I eligible?", "Our nonprofit is 1 year old" | **FAQ RAG** → FAQ answer; falls back to eligibility guidance |
| `application_guidance` | "How do I apply?", "Can you apply without subscribing?", "Grant writer costs?" | **FAQ RAG** → FAQ answer; falls back to grant writer referral |
| `other` | Unclassified queries | **FAQ RAG** (broad search); falls back to generic fallback |

> **FAQ RAG** means the chatbot searches 95 curated FAQ Q&A pairs in the vector store. If a matching FAQ is found, the response uses the pre-approved FAQ answer. If no match, the handler falls back to its static template.

---

## CTA Types by User Type

| `user_type` | `cta_type` | Button Text | Action |
|-------------|------------|-------------|--------|
| `guest-user` | `signup` | "Sign Up & View Full Report" | Navigate to `/signup` |
| `unpaid-user` | `subscribe` | "Subscribe to View Full List" | Navigate to `/pricing` |
| `paid-user` | `view_grants` | "View Full List of {N} Grants" | Navigate to search results page |

> **Note:** `cta_type` is only present when `total_grants > 0`.

---

## Integration Scenarios

### 1. Guest User — Grant Search
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "Education grants in Texas", "user_type": "guest-user"}'
```

**Response:**
```json
{
  "response": "I found 45 grants for education in Texas...",
  "query_type": "grant_search",
  "total_grants": 45,
  "cta_type": "signup",
  "user_type": "guest-user"
}
```
**FE Action:** Render "Sign Up & View Full Report" button.

---

### 2. Paid User — Grant Search
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "Healthcare grants in California", "user_type": "paid-user"}'
```

**Response:**
```json
{
  "response": "I found 31 grants for healthcare in California...",
  "query_type": "grant_search",
  "total_grants": 31,
  "cta_type": "view_grants",
  "user_type": "paid-user"
}
```
**FE Action:** Render "View Full List of 31 Grants" button → link to search page.

---

### 3. No Results Found
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "Aerospace grants in Alaska", "user_type": "guest-user"}'
```

**Response:**
```json
{
  "response": "I couldn't find active grants matching interests like aerospace in Alaska...",
  "query_type": "grant_search",
  "total_grants": 0,
  "cta_type": null,
  "user_type": "guest-user"
}
```
**FE Action:** No CTA button, show refinement suggestions.

---

### 4. Product Question — Pricing (Static Context)
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "What are TGP pricing plans?"}'
```

**Response:**
```json
{
  "response": "We offer Weekly ($14.99/week), Monthly ($34.99/month), Quarterly ($79.99/quarter), and Yearly ($199.99/year) plans. Visit https://www.thegrantportal.com/pricing-and-plans for full details!",
  "query_type": "product_navigation",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** No CTA, just display response.

---

### 5. Product Question — FAQ-Answered
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "What does Deadline Ongoing mean?"}'
```

**Response:**
```json
{
  "response": "'Deadline Ongoing' means that the grant provider awards grants on an ongoing basis. Check the grant provider for details.",
  "query_type": "product_navigation",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** No CTA, just display response. The response comes from the curated FAQ database.

---

### 6. Account Support — FAQ-Answered
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "How do I cancel my subscription?"}'
```

**Response:**
```json
{
  "response": "Log into your account. Select 'My Account Settings' in the drop-down menu. Select 'Subscription Level'. Select 'Manage My Account'. Select 'Cancel'. Check your inbox for cancellation confirmation. Or please use the [Contact Us](https://www.thegrantportal.com/contact-us) tab or email us at tech@promero.com",
  "query_type": "account_support",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** Display response with actionable steps. Note: response may contain markdown links.

---

### 7. Application Guidance — FAQ-Answered
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "How do I apply for a grant?"}'
```

**Response:**
```json
{
  "response": "Paid subscribers have access to the grant details and the grant provider's website and application link. On their website, you will be able to find the information to apply.",
  "query_type": "application_guidance",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** Display response.

---

### 8. Eligibility — FAQ-Answered
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "Can I filter grants by state?"}'
```

**Response:**
```json
{
  "response": "Yes, you can filter grants by using the Search For Grants box — by Location, by Interests, and by Eligibilities.",
  "query_type": "eligibility_assessment",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** Display response.

---

### 9. Stateless Conversation Flow
**First message:**
```json
{
  "message": "Hi",
  "conversation_history": []
}
```

**Response includes updated history:**
```json
{
  "conversation_history": [
    {"role": "user", "content": "Hi", "query_type": "greeting"},
    {"role": "assistant", "content": "Hey! Ready to find some funding?", "query_type": "greeting"}
  ]
}
```

**Second message — send history back:**
```json
{
  "message": "Find grants for nonprofits",
  "conversation_history": [
    {"role": "user", "content": "Hi", "query_type": "greeting"},
    {"role": "assistant", "content": "Hey! Ready to find some funding?", "query_type": "greeting"}
  ]
}
```

---

## Filter Chips (Entity Display)

When `extracted_entities` is present, render clickable filter chips:

```json
{
  "extracted_entities": {
    "interest_slugs": ["education"],
    "location_slugs": ["california-usa"],
    "eligibility_criteria_slugs": ["nonprofits"]
  }
}
```

**Display format:**
- `education` → **Education**
- `california-usa` → **California**
- `nonprofits` → **Nonprofits**

---

## Error Handling

| HTTP Code | Meaning | Action |
|-----------|---------|--------|
| 200 | Success | Render response |
| 422 | Validation error | Show "Invalid message" |
| 500 | Server error | Show "Something went wrong" |

---

## Health Check

```bash
GET /api/v1/chatbot/health
```

**Response:**
```json
{
  "status": "ok",
  "service": "chatbot",
  "database_configured": true,
  "vector_store_provider": "chroma",
  "vector_store_initialized": true
}
```

---

## FAQ Data Management

The chatbot uses 95 curated FAQ Q&A pairs stored in `agents/chatbot/data/faqs.json`. These are ingested into the Chroma vector store as atomic documents (one per FAQ, no chunking).

### Re-ingesting FAQs

After updating `faqs.json`, re-ingest to update the vector store:

```bash
python -m agents.chatbot.ingest_faqs --clear-existing
```

This removes old FAQ documents from Chroma and ingests the updated set. Website page documents are **not affected**.

### FAQ Response Behavior

- **FAQ match found** → Response uses the pre-approved FAQ answer (with markdown links preserved)
- **No FAQ match** → Handler falls back to its static template response
- **Pricing questions** → Always use static pricing context (not FAQ data)
- **Grant search** → Always use SQL search (not FAQ data)

### Support Email

The support email used in fallback templates is configured in `agents/chatbot/config.py`:
```python
support_email: str = "tech@promero.com"
```
