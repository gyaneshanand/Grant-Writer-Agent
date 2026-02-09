# Chatbot API Integration Guide

> **For Frontend Teams** — API contract, request/response schemas, and integration scenarios.

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
| `query_type` | string | Always | Intent: `greeting`, `grant_search`, `product_navigation`, `application_guidance`, `support`, `other` |
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
| `grant_search` | "Find grants for...", "Education grants in NY" | Grant count + summary + CTA |
| `product_navigation` | "What's the price?", "How do I sign up?" | RAG-based answer about TGP |
| `application_guidance` | "How to apply for a grant?" | Step-by-step guidance |
| `support` | "I need help", "Contact support" | Support message + contact info |
| `other` | Unclassified queries | Generic fallback |

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

### 4. Product Question (RAG)
```bash
curl -X POST /api/v1/chatbot/chat \
  -d '{"message": "What are TGP pricing plans?"}'
```

**Response:**
```json
{
  "response": "TGP offers three pricing tiers: Basic ($29/mo), Pro ($99/mo)...",
  "query_type": "product_navigation",
  "total_grants": null,
  "cta_type": null
}
```
**FE Action:** No CTA, just display response.

---

### 5. Stateless Conversation Flow
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
