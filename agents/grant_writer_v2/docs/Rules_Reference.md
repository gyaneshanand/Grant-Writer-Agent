# Grant Detection Rules — Reference & Discussion Document

**Purpose:** Definitive specification for each business rule applied in Layer 2 to determine
if a grant program is a "valid" listing for The Grant Portal. This document is the
single source of truth for rule semantics, edge cases, and outstanding decisions.

**Status:** DRAFT — pending review with TGP team. Resolved decisions move to ✅ status.

---

## Glossary

- **Foundation:** A 501(c)(3) entity (private non-operating, private operating, public charity, or family foundation) identified by EIN.
- **Grant Program:** A distinct funding initiative within a foundation. One foundation may have many programs (e.g., "Community Grants," "Capacity Building Grants," "Founders' Circle").
- **Verdict:** The Layer 2 outcome — `VALID`, `NEEDS_REVIEW`, or `INVALID`. **Verdicts are per-program, not per-foundation.**
- **Foundation rollup verdict:** Derived. A foundation is `VALID` if at least one of its programs is `VALID`.

---

## The 6 Core Rules + 1 Lifecycle Rule

| # | Rule Name | Pass Condition | Failure → INVALID? |
|---|---|---|---|
| 1 | `has_grants` | Program actively distributes funding | Yes |
| 2 | `accepts_applications` | A way to apply exists (online portal, email, mail, phone-then-form) | Yes |
| 3 | `not_invitation_only` | Program does not require invitation/nomination | Yes |
| 4 | `not_donation_only` | Program is grant-making, not just receiving donations | Yes |
| 5 | `allows_unsolicited` | Does not say "we do not accept unsolicited proposals" | Yes |
| 6 | `geography_valid` | Available to US / Canada / US Territories / International (incl. US/CA) | Yes |
| 7 | `active_or_recurring` (lifecycle) | Either currently open OR recurring | See sub-cases below |

A program is **VALID** only when all seven evaluate to TRUE with confidence ≥ threshold (default 0.7).

---

## Rule 1 — has_grants

### Definition
The program describes funding it provides to external recipients (organizations, individuals, projects, research, etc.).

### Positive signals
- Page describes funding amounts, application process, recipient categories
- "We award grants of up to $X to nonprofits working on Y"
- Past grantee list with dollar amounts

### Negative signals (→ false)
- Foundation only describes its own internal programs/operations (a private operating foundation that runs its own museum, school, etc., and doesn't fund others)
- Page only describes scholarships INTERNAL to the foundation's beneficiary class

### Edge cases
- **Operating foundation that ALSO gives external grants** → TRUE for the external grants program
- **Donor-advised fund sponsor** (e.g., a community foundation that hosts DAFs) → Generally FALSE for the DAF service itself, but TRUE for any open-application competitive grants the community foundation directly runs
- **Foundation that only funds its founder's other organization** → Technically true but practically useless to TGP users — flag for TGP discussion

---

## Rule 2 — accepts_applications

### Definition
A pathway exists for an external party to apply. Acceptable pathways: online portal, email submission, postal mail, fax, phone inquiry that leads to a form, LOI (letter of intent) followed by full application.

### Positive signals
- "Apply here" button → leads to a form, portal, or email link
- "Submit a letter of inquiry to..."
- Application deadline + downloadable form
- "Email proposals to grants@example.org"

### Negative signals (→ false)
- "We do not accept applications"
- "Funding is determined by board nomination only" (overlaps with Rule 3)
- Apply page exists but is a 404 / dead link / "coming soon"

---

## Rule 3 — not_invitation_only

### Definition
The program does NOT restrict applications to invitees, nominees, or pre-existing relationships.

### Negative signals (→ false)
- "By invitation only"
- "Nominees are selected by our board"
- "We work with a closed network of grantees"
- "Applications accepted from current and former grantees only"

---

## Rule 4 — not_donation_only

### Definition
The program GIVES grants. It is not solely a fundraising vehicle.

### Negative signals (→ false)
- "Donate to support our cause" with no grant-making activity described
- Foundation is registered as 501(c)(3) but acts purely as an operational nonprofit with no grant-making

---

## Rule 5 — allows_unsolicited

### Definition
The program does NOT explicitly state that unsolicited proposals are rejected.

### Negative signals (→ false)
- "We do not accept unsolicited proposals"
- "Please do not send unsolicited grant requests; we will contact you"
- "Letters of inquiry must be submitted only via referral"

---

## Rule 6 — geography_valid

### Definition
The program is available to applicants based in the US, Canada, US Territories, or international programs that explicitly include US or Canada.

### Pass cases
- "Open to US-based 501(c)(3)s"
- "Open to applicants in California"
- "Worldwide"
- "Canada and US"

### Failure cases (→ false)
- "Open to applicants in sub-Saharan Africa only"
- "EU-based organizations only"

---

## Rule 7 — active_or_recurring (Lifecycle Rule)

### Definition
The program is either currently accepting applications OR has a recurring cycle that will reopen.

### Pass cases
- **Currently open** — `is_currently_open=true`
- **Closed but recurring** — `is_currently_open=false`, `recurrence=annual|biennial|rolling|quarterly`
- **Rolling** — `is_currently_open=true`, `deadline_type=rolling`

### Failure cases (→ INVALID with override `past_only`)
- "2019 cycle was our final round"
- "Program discontinued"
- A page lists only past deadlines from years ago AND has no language indicating future cycles

---

## Verdict Aggregation Logic (Per Program)

```
ALL 6 core rules == TRUE AND min confidence ≥ 0.7  AND active_or_recurring evaluates favorably
  → VALID

ANY core rule == FALSE WITH evidence quote
  → INVALID

active_or_recurring → past_only with confidence ≥ 0.8
  → INVALID, override="past_only"

Geography excluded ALL of {US, US-*, CA, INTL_INCL_US}
  → INVALID, override="geography_excluded"

Mixed signals OR confidence below threshold OR missing evidence on false rule
  → NEEDS_REVIEW
```

---

## Foundation Rollup Verdict

| Programs | Foundation Rollup |
|---|---|
| ≥1 VALID | VALID |
| 0 VALID, ≥1 NEEDS_REVIEW | NEEDS_REVIEW |
| All INVALID | INVALID |
| Crawl error / no programs identified | ERROR |

---

## Open Items for TGP Discussion

1. Operating foundations with side grant programs — in scope?
2. DAF-hosting community foundations — list general grants, skip DAFs?
3. Phone-inquiry-first as a valid application method?
4. Eligibility-quiz-then-invitation pattern — VALID or NEEDS_REVIEW?
5. Single-beneficiary trust funds — list or skip?
6. "We rarely fund unsolicited but consider exceptions" language — VALID or NEEDS_REVIEW?
7. State-restricted programs — confirm in scope.
8. City/county-only programs — list or skip?
9. Closed-but-reopening — publish now with future-date flag, or hold?
10. Re-verification cadence for closed-but-recurring programs — quarterly?
