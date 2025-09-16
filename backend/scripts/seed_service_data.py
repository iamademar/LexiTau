# backend/scripts/seed_service_data.py
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4
import random

from app.db import SessionLocal
from app.models import (
    Business, User, Client, Project, Category,
    Document, ExtractedField, LineItem, FieldCorrection
)
from app.enums import FileType, DocumentType, DocumentStatus, DocumentClassification
from app.auth import get_password_hash

# ----------------------------
# Tunables
# ----------------------------
RANDOM_SEED = 42
START_YEAR = 2020
END_YEAR = 2025  # inclusive
COMPANIES = [
    {"name": "Kiwi Clean Co"},
    {"name": "Aotearoa Electrical"},
    {"name": "Tāmaki Plumbing & Gas"},
]
NZ_CATEGORIES = [
    "Fuel", "Supplies", "Tools & Equipment", "Vehicle Maintenance",
    "Software Subscriptions", "Advertising", "Insurance",
    "Utilities", "Rent", "Training"
]
PROJECT_NAMES = [
    "Auckland CBD Contracts", "North Shore Maintenance",
    "South Auckland Buildouts", "Emergency Callouts",
    "Annual Service Agreements"
]
CUSTOMER_NAME_SEEDS = [
    "Rangi", "Sophie", "Noah", "Aria", "Oliver",
    "Isla", "Leo", "Mia", "Lucas", "Amelia",
    "Jack", "Emily", "Hunter", "Ruby", "Nikau"
]

# Typical service line items for invoices/receipts
SERVICE_ITEMS = [
    ("Hourly Labour", Decimal("95.00")),
    ("Call-out Fee", Decimal("65.00")),
    ("Materials & Parts", Decimal("45.00")),
    ("Disposal Fee", Decimal("15.00")),
    ("Site Inspection", Decimal("55.00")),
]

def nz_blob_url(business_id: int, filename: str) -> str:
    # Placeholder Azure Blob URL; replace container/account as needed
    return f"https://example.blob.core.windows.net/lexitau/b{business_id}/{filename}"

def random_date_in_year(year: int) -> datetime:
    # Uniform random date within the given year
    start = datetime(year, 1, 1)
    end = datetime(year, 12, 31, 23, 59, 59)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))

def gen_invoice_number(year: int, seq: int) -> str:
    return f"INV-{year}-{seq:05d}"

def gen_receipt_number(year: int, seq: int) -> str:
    return f"RCT-{year}-{seq:05d}"

def create_categories(db):
    existing = {c.name for c in db.query(Category).all()}
    created = []
    for name in NZ_CATEGORIES:
        if name not in existing:
            c = Category(name=name)
            db.add(c)
            created.append(c)
    db.commit()
    return db.query(Category).all()

def create_projects(db, business_id: int):
    projects = []
    for name in PROJECT_NAMES:
        p = Project(business_id=business_id, name=name)
        db.add(p)
        projects.append(p)
    db.commit()
    return projects

def create_company_with_user(db, company_name: str, email: str, password: str):
    biz = Business(name=company_name)
    db.add(biz)
    db.commit()
    db.refresh(biz)

    user = User(
        email=email,
        password_hash=get_password_hash(password),
        business_id=biz.id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return biz, user

def create_clients(db, business_id: int, n: int):
    # 10 customers, NZ-flavoured names
    clients = []
    picks = random.sample(CUSTOMER_NAME_SEEDS, k=min(n, len(CUSTOMER_NAME_SEEDS)))
    for i in range(n):
        name = picks[i % len(picks)]
        client = Client(business_id=business_id, name=f"{name} Ltd")
        db.add(client)
        clients.append(client)
    db.commit()
    return clients

def add_extracted_fields(db, document: Document, is_invoice: bool, when: datetime, client_name: str, doc_number: str, total_amount: Decimal):
    # Common extracted fields from OCR
    fields = [
        ("issue_date", when.strftime("%Y-%m-%d"), 0.96),
        ("due_date", (when + timedelta(days=14)).strftime("%Y-%m-%d") if is_invoice else None, 0.91 if is_invoice else 0.0),
        ("document_number", doc_number, 0.94),
        ("vendor_name", " ".join(document.filename.split("_")[:2]), 0.9),
        ("client_name", client_name, 0.93 if is_invoice else 0.88),
        ("total_amount", str(total_amount), 0.95),
        ("currency", "NZD", 0.99),
        ("gst_registered", "True", 0.8),
    ]
    for field_name, value, conf in fields:
        db.add(ExtractedField(
            document_id=document.id,
            business_id=document.business_id,
            field_name=field_name,
            value=value,
            confidence=conf
        ))

def add_line_items(db, document: Document, is_invoice: bool):
    # 1–5 items
    item_count = random.randint(1, 5)
    total = Decimal("0.00")
    for _ in range(item_count):
        desc, base_price = random.choice(SERVICE_ITEMS)
        # Hours or units: 1.0–6.0 in 0.5 steps
        qty = Decimal(random.choice([x / 2 for x in range(2, 13)]))  # 1.0 to 6.0
        unit_price = base_price + Decimal(random.choice([0, 5, 10, 15]))
        line_total = (unit_price * qty).quantize(Decimal("0.01"))
        total += line_total
        db.add(LineItem(
            document_id=document.id,
            business_id=document.business_id,
            description=desc,
            quantity=qty,
            unit_price=unit_price,
            total=line_total,
            confidence=random.uniform(0.85, 0.99),
        ))
    return total.quantize(Decimal("0.01"))

def maybe_review(db, document: Document, reviewer_id: int):
    # ~40% documents reviewed
    if random.random() < 0.4 and document.status == DocumentStatus.COMPLETED:
        # lightweight “review” audit by adding a correction sometimes
        document.reviewed_at = datetime.utcnow()
        document.reviewed_by = reviewer_id
        if random.random() < 0.25:
            db.add(FieldCorrection(
                document_id=document.id,
                business_id=document.business_id,
                field_name="client_name",
                original_value="Clinet Name",  # typo to simulate OCR error
                corrected_value="Client Name",
                corrected_by=reviewer_id
            ))

def create_documents_for_client(db, *, user: User, business: Business, client: Client, projects: list, cats_by_name: dict):
    seq_invoice = 1
    seq_receipt = 1
    # Each client gets a mix per year
    for year in range(START_YEAR, END_YEAR + 1):
        for _ in range(random.randint(3, 9)):  # number of docs per year per client
            is_invoice = random.random() < 0.55  # slightly more invoices
            when = random_date_in_year(year)
            project = random.choice(projects)
            if is_invoice:
                number = gen_invoice_number(year, seq_invoice); seq_invoice += 1
                doc_type = DocumentType.INVOICE
                classification = DocumentClassification.REVENUE
                category = cats_by_name.get("Advertising")  # arbitrary for invoices (some systems leave cat empty until review)
            else:
                number = gen_receipt_number(year, seq_receipt); seq_receipt += 1
                doc_type = DocumentType.RECEIPT
                classification = DocumentClassification.EXPENSE
                category = cats_by_name.get(random.choice(NZ_CATEGORIES))

            file_ext = random.choice([("pdf", FileType.PDF), ("jpg", FileType.JPG), ("png", FileType.PNG)])
            fname = f"{client.name.replace(' ', '_')}_{number}.{file_ext[0]}"
            status = random.choices(
                [DocumentStatus.COMPLETED, DocumentStatus.PENDING, DocumentStatus.PROCESSING, DocumentStatus.FAILED],
                weights=[70, 10, 15, 5],
                k=1
            )[0]

            doc = Document(
                user_id=user.id,
                business_id=business.id,
                client_id=client.id,
                project_id=project.id,
                category_id=category.id if category else None,
                filename=fname,
                file_url=nz_blob_url(business.id, fname),
                file_type=file_ext[1],
                document_type=doc_type,
                classification=classification,
                status=status,
                confidence_score=round(random.uniform(0.75, 0.99), 3),
                created_at=when,
                updated_at=when + timedelta(minutes=random.randint(1, 120))
            )
            db.add(doc)
            db.flush()  # ensure doc.id UUID is available

            # Add items and fields to simulate OCR results
            gross_total = add_line_items(db, doc, is_invoice=is_invoice)
            add_extracted_fields(
                db, doc, is_invoice=is_invoice, when=when,
                client_name=client.name, doc_number=number, total_amount=gross_total
            )
            maybe_review(db, doc, reviewer_id=user.id)

        db.commit()

def main():
    random.seed(RANDOM_SEED)
    db = SessionLocal()
    try:
        # 1) Global categories (once)
        categories = create_categories(db)
        cats_by_name = {c.name: c for c in categories}

        # 2) Three NZ service companies + owner users (simple emails/passwords for seed)
        #    Passwords are hashed using your repo’s bcrypt setup.
        companies_spec = [
            ("Kiwi Clean Co",       "owner@kiwiclean.nz",        "Password1!"),
            ("Aotearoa Electrical", "owner@aotearoaelectric.nz", "Password1!"),
            ("Tāmaki Plumbing & Gas","owner@tamakiplumb.nz",     "Password1!"),
        ]

        created = []
        for name, email, pw in companies_spec:
            biz, user = create_company_with_user(db, name, email, pw)
            created.append((biz, user))

        # 3) For each business: 10 clients, some projects, then docs per client (2020–2025)
        for biz, user in created:
            projects = create_projects(db, biz.id)
            clients = create_clients(db, biz.id, 10)
            for cl in clients:
                create_documents_for_client(
                    db, user=user, business=biz, client=cl,
                    projects=projects, cats_by_name=cats_by_name
                )

        print("✅ Seed complete.")
    finally:
        db.close()

if __name__ == "__main__":
    main()
