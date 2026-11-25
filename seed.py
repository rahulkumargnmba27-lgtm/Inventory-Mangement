from pathlib import Path
from openpyxl import Workbook
from sqlalchemy.orm import Session

from .auth import hash_password
from .models import Category, Product, Supplier, User
from .services.excel_service import import_excel_bytes

INITIAL_INVENTORY_ROWS = [
    ("KIR001", "Aashirvaad Atta 5kg", "Staples", "pack", 265, 40, 10),
    ("KIR002", "Basmati Rice 1kg", "Staples", "kg", 95, 60, 15),
    ("KIR003", "Toor Dal 1kg", "Pulses", "kg", 160, 35, 10),
    ("KIR004", "Moong Dal 1kg", "Pulses", "kg", 130, 25, 8),
    ("KIR005", "Sugar 1kg", "Staples", "kg", 46, 80, 20),
    ("KIR006", "Tata Salt 1kg", "Staples", "pack", 28, 100, 25),
    ("KIR007", "Fortune Sunflower Oil 1L", "Oils", "bottle", 150, 30, 10),
    ("KIR008", "Mustard Oil 1L", "Oils", "bottle", 175, 20, 8),
    ("KIR009", "Tata Tea Gold 250g", "Beverages", "pack", 135, 28, 8),
    ("KIR010", "Nescafe Classic 50g", "Beverages", "jar", 165, 15, 5),
    ("KIR011", "Amul Butter 100g", "Dairy", "pack", 58, 24, 8),
    ("KIR012", "Amul Taaza Milk 1L", "Dairy", "pack", 56, 50, 15),
    ("KIR013", "Paneer 200g", "Dairy", "pack", 90, 12, 5),
    ("KIR014", "Maggi Noodles 70g", "Snacks", "pack", 14, 120, 30),
    ("KIR015", "Parle-G Biscuits", "Snacks", "pack", 10, 150, 40),
    ("KIR016", "Lays Magic Masala", "Snacks", "pack", 20, 60, 20),
    ("KIR017", "Surf Excel 1kg", "Household", "pack", 130, 18, 6),
    ("KIR018", "Vim Dishwash Bar", "Household", "piece", 10, 70, 20),
    ("KIR019", "Lifebuoy Soap", "Personal Care", "piece", 32, 45, 15),
    ("KIR020", "Colgate Toothpaste 100g", "Personal Care", "tube", 62, 0, 10),
    ("KIR021", "Turmeric Powder 200g", "Spices", "pack", 55, 30, 10),
    ("KIR022", "Red Chilli Powder 200g", "Spices", "pack", 70, 5, 10),
    ("KIR023", "Onion 1kg", "Vegetables", "kg", 40, 50, 20),
    ("KIR024", "Potato 1kg", "Vegetables", "kg", 30, 60, 20),
]

INITIAL_ORDER_ROWS = [
    ("SAMPLE-001", "2026-11-25 00:00:00", "", "Sample (delete this row)", "", "1x Tata Salt 1kg", 28, "Sample"),
]


def ensure_initial_workbook(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return path
    wb = Workbook()
    ws_inv = wb.active
    ws_inv.title = "Inventory"
    ws_inv.append(["SKU", "Product", "Category", "Unit", "Price", "Stock", "ReorderLevel"])
    for row in INITIAL_INVENTORY_ROWS:
        ws_inv.append(list(row))

    ws_ord = wb.create_sheet("Orders")
    ws_ord.append(["OrderID", "Date", "Phone", "CustomerName", "CustomerEmail", "Items", "Total", "Status"])
    for row in INITIAL_ORDER_ROWS:
        ws_ord.append(list(row))

    wb.save(path)
    return path


def seed_database(db: Session) -> None:
    # 1. Seed default users
    if db.query(User).count() == 0:
        db.add_all([
            User(
                name="Ramesh Gupta",
                email="owner@kiranaquick.in",
                phone="+91 98450 12345",
                password_hash=hash_password("Kirana@123"),
                role="owner",
                is_active=True,
            ),
            User(
                name="Suresh Kumar",
                email="staff@kiranaquick.in",
                phone="+91 98450 54321",
                password_hash=hash_password("Staff@123"),
                role="staff",
                is_active=True,
            ),
        ])
        db.commit()

    # 2. Seed categories
    default_categories = [
        ("Staples", "Rice, Atta, Sugar, Salt & Daily Grains", "grain", 1),
        ("Pulses", "Toor, Moong, Chana & Masoor Dals", "spa", 2),
        ("Oils", "Cooking Oils & Desi Ghee", "water_drop", 3),
        ("Spices", "Whole & Ground Indian Masalas", "local_fire_department", 4),
        ("Dairy", "Milk, Butter, Paneer & Curd", "egg_alt", 5),
        ("Beverages", "Tea, Coffee & Health Drinks", "local_cafe", 6),
        ("Snacks", "Noodles, Biscuits, Chips & Namkeen", "cookie", 7),
        ("Household", "Detergents, Dishwash & Cleaning", "cleaning_services", 8),
        ("Personal Care", "Soaps, Toothpaste & Hygiene", "soap", 9),
        ("Vegetables", "Fresh Sabzi & Daily Produce", "eco", 10),
    ]
    for name, desc, icon, order in default_categories:
        if not db.query(Category).filter(Category.name == name).first():
            db.add(Category(name=name, description=desc, icon=icon, display_order=order))
    db.commit()

    # 3. Seed suppliers
    default_suppliers = [
        {
            "name": "Mahalaxmi Wholesale Traders",
            "contact_person": "Maheshwari Ji",
            "phone": "+91 98451 22334",
            "email": "orders@mahalaxmiwholesale.in",
            "address": "Yeshwantpur APMC Yard, Bengaluru 560022",
            "gstin": "29AABCM1234F1Z5",
            "notes": "Primary supplier for Atta, Rice, Pulses, Sugar & Salt",
        },
        {
            "name": "Karnataka Dairy & Fresh Foods",
            "contact_person": "Prakash Gowda",
            "phone": "+91 99001 44556",
            "email": "supply@kdfoods.in",
            "address": "Indiranagar 100ft Road, Bengaluru 560038",
            "gstin": "29AAACK5678G1Z2",
            "notes": "Morning 6 AM delivery for Amul Milk, Butter, Paneer",
        },
        {
            "name": "Metro FMCG Distributors",
            "contact_person": "Vikram Sethi",
            "phone": "+91 98802 77889",
            "email": "b2b@metrofmcg.in",
            "address": "KR Puram Industrial Estate, Bengaluru 560016",
            "gstin": "29AABCM9988H1Z8",
            "notes": "FMCG, Snacks, Soaps, Detergents & Spices",
        },
    ]
    for sup in default_suppliers:
        if not db.query(Supplier).filter(Supplier.name == sup["name"]).first():
            db.add(Supplier(**sup))
    db.commit()

    # 4. Seed initial Excel data if products table is empty
    if db.query(Product).count() == 0:
        workbook_path = Path(__file__).resolve().parents[2] / "data" / "kirana_initial_data.xlsx"
        ensure_initial_workbook(workbook_path)
        owner = db.query(User).filter(User.role == "owner").first()
        import_excel_bytes(db, workbook_path.read_bytes(), user=owner)
