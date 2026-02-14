"""
Seed script for client-specific defect type catalogs
Populates industry-appropriate defect types for each client
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine, text
from datetime import datetime
import uuid

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///database/kpi_platform.db")

# Global defect types available to all clients
GLOBAL_DEFECT_TYPES = {
    "industry": "Global (All Industries)",
    "defects": [
        {
            "code": "DIM_OOS",
            "name": "Dimension Out of Spec",
            "category": "Measurement",
            "severity": "MAJOR",
            "desc": "Part or product dimensions outside specification tolerance",
        },
        {
            "code": "VISUAL_DEF",
            "name": "Visual Defect",
            "category": "Appearance",
            "severity": "MINOR",
            "desc": "Visible cosmetic defect affecting appearance",
        },
        {
            "code": "SURFACE_DMG",
            "name": "Surface Damage",
            "category": "Damage",
            "severity": "MAJOR",
            "desc": "Scratches, dents, or marks on surface",
        },
        {
            "code": "MISSING_COMP",
            "name": "Missing Component",
            "category": "Assembly",
            "severity": "CRITICAL",
            "desc": "Required component or part not present",
        },
        {
            "code": "WRONG_PART",
            "name": "Wrong Part/Component",
            "category": "Assembly",
            "severity": "CRITICAL",
            "desc": "Incorrect part or component used",
        },
        {
            "code": "CONTAMINATION",
            "name": "Contamination",
            "category": "Cleanliness",
            "severity": "MAJOR",
            "desc": "Foreign material, debris, or contamination present",
        },
        {
            "code": "FUNC_FAIL",
            "name": "Functional Failure",
            "category": "Testing",
            "severity": "CRITICAL",
            "desc": "Product fails functional or performance testing",
        },
        {
            "code": "DOC_ERROR",
            "name": "Documentation Error",
            "category": "Documentation",
            "severity": "MINOR",
            "desc": "Missing, incorrect, or incomplete documentation",
        },
        {
            "code": "LABEL_ERR",
            "name": "Labeling Error",
            "category": "Labeling",
            "severity": "MAJOR",
            "desc": "Missing, incorrect, or illegible labeling",
        },
        {
            "code": "PKG_DAMAGE",
            "name": "Packaging Damage",
            "category": "Packaging",
            "severity": "MAJOR",
            "desc": "Damaged, crushed, or compromised packaging",
        },
        {
            "code": "MAT_DEFECT",
            "name": "Material Defect",
            "category": "Material",
            "severity": "CRITICAL",
            "desc": "Raw material or component quality issue",
        },
        {
            "code": "WORKMANSHIP",
            "name": "Poor Workmanship",
            "category": "Process",
            "severity": "MAJOR",
            "desc": "General workmanship quality issue",
        },
        {
            "code": "OTHER",
            "name": "Other Defect",
            "category": "General",
            "severity": "MINOR",
            "desc": "Other defects not categorized above",
        },
    ],
}

# Reserved client_id for global defect types
GLOBAL_CLIENT_ID = "GLOBAL"

# Industry-specific defect type definitions
DEFECT_TYPES_BY_INDUSTRY = {
    # General Manufacturing (ACME-MFG)
    "ACME-MFG": {
        "industry": "General Manufacturing",
        "defects": [
            {
                "code": "DIM_ERR",
                "name": "Dimensional Error",
                "category": "Measurement",
                "severity": "MAJOR",
                "desc": "Part dimensions outside tolerance",
            },
            {
                "code": "SURF_DEF",
                "name": "Surface Defect",
                "category": "Finish",
                "severity": "MINOR",
                "desc": "Scratches, dents, or blemishes on surface",
            },
            {
                "code": "MAT_DEF",
                "name": "Material Defect",
                "category": "Material",
                "severity": "CRITICAL",
                "desc": "Raw material quality issues",
            },
            {
                "code": "ASSY_ERR",
                "name": "Assembly Error",
                "category": "Assembly",
                "severity": "MAJOR",
                "desc": "Incorrect assembly or missing components",
            },
            {
                "code": "WELD_DEF",
                "name": "Weld Defect",
                "category": "Process",
                "severity": "CRITICAL",
                "desc": "Weld cracks, porosity, or incomplete fusion",
            },
            {
                "code": "PAINT_DEF",
                "name": "Paint/Coating Defect",
                "category": "Finish",
                "severity": "MINOR",
                "desc": "Paint runs, orange peel, or coating issues",
            },
            {
                "code": "BURR",
                "name": "Burr/Sharp Edge",
                "category": "Finish",
                "severity": "MINOR",
                "desc": "Rough edges requiring deburring",
            },
            {
                "code": "FUNC_FAIL",
                "name": "Functional Failure",
                "category": "Testing",
                "severity": "CRITICAL",
                "desc": "Part fails functional testing",
            },
            {
                "code": "CONTAM",
                "name": "Contamination",
                "category": "Cleanliness",
                "severity": "MAJOR",
                "desc": "Foreign material or debris",
            },
            {
                "code": "OTHER",
                "name": "Other",
                "category": "General",
                "severity": "MINOR",
                "desc": "Other defects not categorized above",
            },
        ],
    },
    # Textile/Apparel (TEXTIL-PRO)
    "TEXTIL-PRO": {
        "industry": "Textile & Apparel",
        "defects": [
            {
                "code": "STITCH",
                "name": "Stitching Defect",
                "category": "Sewing",
                "severity": "MAJOR",
                "desc": "Broken, skipped, or loose stitches",
            },
            {
                "code": "FABRIC",
                "name": "Fabric Defect",
                "category": "Material",
                "severity": "MAJOR",
                "desc": "Holes, snags, or weave issues in fabric",
            },
            {
                "code": "MEASURE",
                "name": "Measurement Error",
                "category": "Sizing",
                "severity": "MAJOR",
                "desc": "Garment measurements outside specification",
            },
            {
                "code": "COLOR",
                "name": "Color Shade Variation",
                "category": "Dyeing",
                "severity": "MINOR",
                "desc": "Color inconsistency or shade variation",
            },
            {
                "code": "PILLING",
                "name": "Pilling",
                "category": "Material",
                "severity": "MINOR",
                "desc": "Fabric pilling or fuzzing",
            },
            {
                "code": "HOLE_TEAR",
                "name": "Hole/Tear",
                "category": "Material",
                "severity": "CRITICAL",
                "desc": "Holes or tears in fabric",
            },
            {
                "code": "STAIN",
                "name": "Stain",
                "category": "Cleanliness",
                "severity": "MINOR",
                "desc": "Oil, dirt, or other stains",
            },
            {
                "code": "SEAM_PUCKER",
                "name": "Seam Pucker",
                "category": "Sewing",
                "severity": "MINOR",
                "desc": "Puckering along seam lines",
            },
            {
                "code": "LABEL_ERR",
                "name": "Label Error",
                "category": "Labeling",
                "severity": "MINOR",
                "desc": "Missing, incorrect, or poorly attached labels",
            },
            {
                "code": "OTHER",
                "name": "Other",
                "category": "General",
                "severity": "MINOR",
                "desc": "Other defects not categorized above",
            },
        ],
    },
    # Electronics Assembly (ELEC-ASSY)
    "ELEC-ASSY": {
        "industry": "Electronics Assembly",
        "defects": [
            {
                "code": "SOLDER_DEF",
                "name": "Solder Defect",
                "category": "Assembly",
                "severity": "MAJOR",
                "desc": "Cold solder, bridges, insufficient solder",
                "standard": "IPC-A-610-5.2",
            },
            {
                "code": "COMP_MISS",
                "name": "Component Missing",
                "category": "Assembly",
                "severity": "CRITICAL",
                "desc": "Required component not present on PCB",
            },
            {
                "code": "COMP_WRONG",
                "name": "Wrong Component",
                "category": "Assembly",
                "severity": "CRITICAL",
                "desc": "Incorrect component value or type installed",
            },
            {
                "code": "POLARITY",
                "name": "Polarity Error",
                "category": "Assembly",
                "severity": "CRITICAL",
                "desc": "Component installed with wrong polarity",
            },
            {
                "code": "SHORT",
                "name": "Short Circuit",
                "category": "Electrical",
                "severity": "CRITICAL",
                "desc": "Unintended electrical connection",
            },
            {
                "code": "OPEN",
                "name": "Open Circuit",
                "category": "Electrical",
                "severity": "CRITICAL",
                "desc": "Missing required electrical connection",
            },
            {
                "code": "ESD_DMG",
                "name": "ESD Damage",
                "category": "Handling",
                "severity": "CRITICAL",
                "desc": "Electrostatic discharge damage to components",
            },
            {
                "code": "PCB_DEF",
                "name": "PCB Defect",
                "category": "Material",
                "severity": "MAJOR",
                "desc": "Board delamination, cracks, or copper issues",
            },
            {
                "code": "TOMBSTONE",
                "name": "Tombstoning",
                "category": "Assembly",
                "severity": "MAJOR",
                "desc": "Component standing on one end",
                "standard": "IPC-A-610-8.3",
            },
            {
                "code": "OTHER",
                "name": "Other",
                "category": "General",
                "severity": "MINOR",
                "desc": "Other defects not categorized above",
            },
        ],
    },
    # Packaging/Logistics (PACK-SHIP)
    "PACK-SHIP": {
        "industry": "Packaging & Logistics",
        "defects": [
            {
                "code": "PKG_DMG",
                "name": "Package Damage",
                "category": "Packaging",
                "severity": "MAJOR",
                "desc": "Crushed, torn, or damaged packaging",
            },
            {
                "code": "SEAL_FAIL",
                "name": "Seal Failure",
                "category": "Packaging",
                "severity": "CRITICAL",
                "desc": "Package seal broken or incomplete",
            },
            {
                "code": "LABEL_ERR",
                "name": "Label Error",
                "category": "Labeling",
                "severity": "MAJOR",
                "desc": "Incorrect, missing, or unreadable labels",
            },
            {
                "code": "BARCODE",
                "name": "Barcode Issue",
                "category": "Labeling",
                "severity": "MAJOR",
                "desc": "Barcode unreadable or incorrect",
            },
            {
                "code": "QTY_ERR",
                "name": "Quantity Error",
                "category": "Fulfillment",
                "severity": "CRITICAL",
                "desc": "Incorrect item count in package",
            },
            {
                "code": "WRONG_ITEM",
                "name": "Wrong Item",
                "category": "Fulfillment",
                "severity": "CRITICAL",
                "desc": "Incorrect product in package",
            },
            {
                "code": "CONTAM",
                "name": "Contamination",
                "category": "Cleanliness",
                "severity": "MAJOR",
                "desc": "Foreign material in package",
            },
            {
                "code": "MOIST_DMG",
                "name": "Moisture Damage",
                "category": "Environment",
                "severity": "MAJOR",
                "desc": "Water or humidity damage",
            },
            {
                "code": "PRINT_DEF",
                "name": "Print Defect",
                "category": "Printing",
                "severity": "MINOR",
                "desc": "Poor print quality on packaging",
            },
            {
                "code": "OTHER",
                "name": "Other",
                "category": "General",
                "severity": "MINOR",
                "desc": "Other defects not categorized above",
            },
        ],
    },
    # Medical Devices (MEDDEV-INC)
    "MEDDEV-INC": {
        "industry": "Medical Devices",
        "defects": [
            {
                "code": "STERIL_FAIL",
                "name": "Sterility Failure",
                "category": "Sterility",
                "severity": "CRITICAL",
                "desc": "Product failed sterility testing",
                "standard": "ISO-11137",
            },
            {
                "code": "BIOCOMPAT",
                "name": "Biocompatibility Issue",
                "category": "Material",
                "severity": "CRITICAL",
                "desc": "Material biocompatibility concern",
                "standard": "ISO-10993",
            },
            {
                "code": "DIM_OOT",
                "name": "Dimension Out of Tolerance",
                "category": "Measurement",
                "severity": "MAJOR",
                "desc": "Critical dimension outside specification",
            },
            {
                "code": "SURF_FINISH",
                "name": "Surface Finish Defect",
                "category": "Finish",
                "severity": "MAJOR",
                "desc": "Surface roughness or finish issues",
            },
            {
                "code": "CONTAM",
                "name": "Particulate Contamination",
                "category": "Cleanliness",
                "severity": "CRITICAL",
                "desc": "Particle contamination on device",
            },
            {
                "code": "FUNC_FAIL",
                "name": "Functional Failure",
                "category": "Testing",
                "severity": "CRITICAL",
                "desc": "Device fails functional testing",
            },
            {
                "code": "LABEL_ERR",
                "name": "Labeling Error",
                "category": "Labeling",
                "severity": "MAJOR",
                "desc": "UDI or label compliance issue",
                "standard": "FDA-UDI",
            },
            {
                "code": "PKG_INTEG",
                "name": "Package Integrity Failure",
                "category": "Packaging",
                "severity": "CRITICAL",
                "desc": "Sterile barrier breach",
            },
            {
                "code": "DOC_ERR",
                "name": "Documentation Error",
                "category": "Documentation",
                "severity": "MAJOR",
                "desc": "IFU or DHR documentation issues",
            },
            {
                "code": "OTHER",
                "name": "Other",
                "category": "General",
                "severity": "MINOR",
                "desc": "Other defects not categorized above",
            },
        ],
    },
}


def generate_id(client_id: str, code: str) -> str:
    """Generate unique defect type ID"""
    return f"DT-{client_id}-{code}-{uuid.uuid4().hex[:6].upper()}"


def seed_defect_types():
    """Seed defect types for all clients including global types"""
    engine = create_engine(DATABASE_URL)

    with engine.connect() as conn:
        # Create table if not exists (note: GLOBAL doesn't have FK constraint)
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS DEFECT_TYPE_CATALOG (
                defect_type_id VARCHAR(50) PRIMARY KEY,
                client_id VARCHAR(50) NOT NULL,
                defect_code VARCHAR(20) NOT NULL,
                defect_name VARCHAR(100) NOT NULL,
                description TEXT,
                category VARCHAR(50),
                severity_default VARCHAR(20) DEFAULT 'MAJOR',
                industry_standard_code VARCHAR(50),
                is_active INTEGER DEFAULT 1,
                sort_order INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """
            )
        )
        conn.commit()

        # Check existing data
        result = conn.execute(text("SELECT COUNT(*) FROM DEFECT_TYPE_CATALOG"))
        existing_count = result.fetchone()[0]

        if existing_count > 0:
            print(f"Found {existing_count} existing defect types. Clearing and re-seeding...")
            conn.execute(text("DELETE FROM DEFECT_TYPE_CATALOG"))
            conn.commit()

        total_inserted = 0

        # First, seed GLOBAL defect types
        print(f"\nSeeding GLOBAL defect types ({GLOBAL_DEFECT_TYPES['industry']})...")
        for idx, defect in enumerate(GLOBAL_DEFECT_TYPES["defects"]):
            defect_type_id = generate_id(GLOBAL_CLIENT_ID, defect["code"])

            conn.execute(
                text(
                    """
                INSERT INTO DEFECT_TYPE_CATALOG
                (defect_type_id, client_id, defect_code, defect_name, description,
                 category, severity_default, industry_standard_code, is_active, sort_order)
                VALUES (:id, :client_id, :code, :name, :desc, :category, :severity, :standard, 1, :order)
            """
                ),
                {
                    "id": defect_type_id,
                    "client_id": GLOBAL_CLIENT_ID,
                    "code": defect["code"],
                    "name": defect["name"],
                    "desc": defect["desc"],
                    "category": defect["category"],
                    "severity": defect["severity"],
                    "standard": defect.get("standard"),
                    "order": idx + 1,
                },
            )

            total_inserted += 1
            print(f"  + [GLOBAL] {defect['code']}: {defect['name']}")

        conn.commit()

        # Then, seed client-specific defect types
        for client_id, data in DEFECT_TYPES_BY_INDUSTRY.items():
            print(f"\nSeeding defect types for {client_id} ({data['industry']})...")

            for idx, defect in enumerate(data["defects"]):
                defect_type_id = generate_id(client_id, defect["code"])

                conn.execute(
                    text(
                        """
                    INSERT INTO DEFECT_TYPE_CATALOG
                    (defect_type_id, client_id, defect_code, defect_name, description,
                     category, severity_default, industry_standard_code, is_active, sort_order)
                    VALUES (:id, :client_id, :code, :name, :desc, :category, :severity, :standard, 1, :order)
                """
                    ),
                    {
                        "id": defect_type_id,
                        "client_id": client_id,
                        "code": defect["code"],
                        "name": defect["name"],
                        "desc": defect["desc"],
                        "category": defect["category"],
                        "severity": defect["severity"],
                        "standard": defect.get("standard"),
                        "order": idx + 1,
                    },
                )

                total_inserted += 1
                print(f"  + {defect['code']}: {defect['name']}")

            conn.commit()

        print(f"\n{'='*50}")
        print(f"Successfully seeded {total_inserted} defect types:")
        print(f"  - {len(GLOBAL_DEFECT_TYPES['defects'])} GLOBAL types (available to all clients)")
        print(
            f"  - {total_inserted - len(GLOBAL_DEFECT_TYPES['defects'])} client-specific types across {len(DEFECT_TYPES_BY_INDUSTRY)} clients"
        )
        print(f"{'='*50}")


if __name__ == "__main__":
    seed_defect_types()
