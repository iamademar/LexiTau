Great! Here's a **compiled, developer-ready specification** for **LexiTau**, based on everything we've discussed.

---

# 🧠 **LexiTau – Product Specification**

## 🎯 Overview

**LexiTau** is a fully managed, lightweight AI-powered tool that helps small service-based businesses (e.g., landscaping, HVAC) extract, classify, and analyze financial documents (invoices and receipts) without needing accounting knowledge or SQL. It supports natural language financial queries and provides a clear, interactive dashboard with document traceability and correction features.

---

## 1. 👥 **Target Users**

* Small business owners (non-technical, low accounting background)
* Use case: Automate financial understanding from scanned/emailed PDFs
* Multi-user per business (no user roles)
* No external consultant or accountant access

---

## 2. ☁️ **Hosting & Deployment**

* Fully managed SaaS hosted on **Azure**
* Multi-tenant architecture
* No custom subdomains or geographic hosting restrictions

---

## 3. 📤 **Document Upload**

| Feature             | Value                                         |
| ------------------- | --------------------------------------------- |
| Allowed Types       | PDF, JPG, PNG                                 |
| Max File Size       | 10MB                                          |
| Multi-file Upload   | ✅ Supported                                   |
| Upload Destinations | Tagged to Client / Project / Category         |
| Processing          | Async via background workers (Celery + Redis) |
| Viewer              | ✅ Built-in PDF/Image Viewer                   |

---

## 4. 🧾 **Document Intelligence Pipeline**

* Use **Azure Form Recognizer (Document Intelligence)** for OCR

  * Handles scanned and digital PDFs/images
  * Extract:

    * Invoices: Issue date, due date, vendor/client, line items, subtotal, tax, total, payment terms
    * Receipts: Date, vendor, line items, total paid, tax, payment method
* Store extraction confidence scores per field

---

## 5. ✍️ **Field Review & Correction**

| Feature                  | Behavior                                 |
| ------------------------ | ---------------------------------------- |
| Manual review            | ✅ Before save + later via viewer         |
| Inline editing           | ✅ Yes                                    |
| Highlight low-confidence | ✅ Visual cues (e.g., yellow/red fields)  |
| Click-to-remap           | ✅ (Optional advanced — text selection)   |
| Store corrections        | ✅ Yes — for improving future extractions |

---

## 6. 🧠 **Natural Language Query Interface**

| Feature                  | Support?          | Notes                                                                |
| ------------------------ | ----------------- | -------------------------------------------------------------------- |
| Chat-style NLQ interface | ✅ Yes             | Primary interface for queries                                        |
| Support filters:         | ✅ Yes             | Date ranges, amount thresholds, client/category                      |
| Query types:             | ✅ Yes             | Revenue by client, expenses by category, unpaid invoices, net income |
| Output:                  | ✅ Tables + Charts | Toggle between views                                                 |
| Clarify vague queries    | ✅ Yes             | Suggest options or ask for missing filters                           |
| Fallback keyword search  | ✅ Yes             | Show partial matches if LLM fails                                    |
| Form-style fallback      | ✅ Yes             | Smart form with dropdowns/sliders for structured query building      |

---

## 7. 📊 **Dashboard (Post-Login Home)**

| Section                   | Details                                                               |
| ------------------------- | --------------------------------------------------------------------- |
| 💡 Business Summary Cards | Revenue, Expenses, Unpaid Invoices, Estimated Net Income              |
| 📈 Charts                 | Revenue vs Expenses (line/bar), Top Clients, Expense Categories (pie) |
| 📂 Recent Uploads         | Latest 3–5 docs with status and actions                               |
| 🧾 Unpaid Invoices        | Due date, amount, client                                              |
| 🔍 Suggested Queries      | Click-to-run examples (rotating)                                      |
| 🧠 Personalized Insights  | Weekly insights like “+12% revenue from last month”                   |

---

## 8. 📚 **Client & Document Management**

* Assign docs to:

  * Clients (e.g., "Client A")
  * Projects (optional)
  * Categories (e.g., fuel, software)
* CRUD support:

  * Create/edit/delete clients
  * View/delete documents

---

## 9. 🔐 **Authentication**

| Feature              | Value                    |
| -------------------- | ------------------------ |
| Login/signup         | Email + password         |
| Email verification   | ❌ Not required           |
| Password reset / 2FA | ❌ Not required           |
| Auth implementation  | JWT (pyjwt, python-jose) |

---

## 10. 📤 **Export & Integration**

| Export/Sync Option         | Support? | Notes                  |
| -------------------------- | -------- | ---------------------- |
| Manual CSV export          | ✅ Yes    | Filtered tables only   |
| Sync to external platforms | ❌ No     | Not in scope at launch |
| Scheduled exports          | ❌ No     | Manual download only   |

---

## 11. 🔍 **Audit & Activity Tracking**

| Feature                    | Support? | Notes                      |
| -------------------------- | -------- | -------------------------- |
| Track who uploaded/edited  | ✅ Yes    | Internal only              |
| Query & correction logging | ✅ Yes    | Internal analytics         |
| User-facing audit log      | ❌ No     | No undo/history UI for now |

---

## 12. 🎓 **Onboarding & Guidance**

| Feature                         | Support? | Notes                                               |
| ------------------------------- | -------- | --------------------------------------------------- |
| Interactive guided tour         | ✅ Yes    | Tooltip walkthrough (Shepherd.js / Intro.js)        |
| Sample demo documents           | ✅ Yes    | For first-time users                                |
| Inline tips & query suggestions | ✅ Yes    | Hover tips, field helper text, rotating query hints |

---

## 13. 🛠️ **Tech Stack**

### Backend

* FastAPI + Uvicorn
* PostgreSQL (prod) + SQLite (dev)
* SQLAlchemy ORM
* Celery + Redis for async document processing
* JWT Auth (pyjwt, python-jose)

### AI / NLP

* Azure Form Recognizer for OCR
* Azure OpenAI for natural language queries
* SentenceTransformers / spaCy for fallback keyword extraction
* Optional embeddings (FAISS, Pinecone, etc.)

### Frontend

* Next.js
* Charting: Chart.js or Plotly

