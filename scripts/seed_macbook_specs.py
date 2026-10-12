import sqlite3

conn = sqlite3.connect("data/advisor.db")
cur = conn.cursor()

specs_data = [
    # MCA_B0B3C4H9NW: 2022 MacBook Air M2
    ("MCA_B0B3C4H9NW", [
        ("Processor", "Apple M2 chip with 8-core CPU and 8-core GPU", "Apple M2 chip with 8-core CPU and 8-core GPU"),
        ("Memory", "8GB Unified Memory", "8GB Unified Memory"),
        ("Storage", "256GB Superfast SSD Storage", "256GB Superfast SSD Storage"),
        ("Display", "13.6-inch Liquid Retina display with True Tone", "13.6-inch Liquid Retina display with True Tone"),
        ("Battery", "Up to 18 hours battery life", "Up to 18 hours battery life")
    ]),
    # MCA_B0CM5BWT68: 2023 MacBook Pro 14 M3
    ("MCA_B0CM5BWT68", [
        ("Processor", "Apple M3 chip with 8-core CPU and 10-core GPU", "Apple M3 chip with 8-core CPU and 10-core GPU"),
        ("Memory", "8GB Unified Memory", "8GB Unified Memory"),
        ("Storage", "512GB NVMe SSD Storage", "512GB NVMe SSD Storage"),
        ("Display", "14.2-inch Liquid Retina XDR display with ProMotion 120Hz", "14.2-inch Liquid Retina XDR display with ProMotion 120Hz"),
        ("Battery", "Up to 22 hours battery life", "Up to 22 hours battery life")
    ]),
    # MCA_B0C76C2K26: 2023 MacBook Air 15 M2
    ("MCA_B0C76C2K26", [
        ("Processor", "Apple M2 chip with 8-core CPU and 10-core GPU", "Apple M2 chip with 8-core CPU and 10-core GPU"),
        ("Memory", "8GB Unified Memory", "8GB Unified Memory"),
        ("Storage", "256GB SSD Storage", "256GB SSD Storage"),
        ("Display", "15.3-inch Liquid Retina display with 500 nits brightness", "15.3-inch Liquid Retina display with 500 nits brightness"),
        ("Battery", "Up to 18 hours battery life", "Up to 18 hours battery life")
    ]),
    # MCA_B0CM5J95Y6: 2023 MacBook Pro 16 M3 Pro
    ("MCA_B0CM5J95Y6", [
        ("Processor", "Apple M3 Pro chip with 12-core CPU and 18-core GPU", "Apple M3 Pro chip with 12-core CPU and 18-core GPU"),
        ("Memory", "18GB Unified Memory", "18GB Unified Memory"),
        ("Storage", "512GB SSD Storage", "512GB SSD Storage"),
        ("Display", "16.2-inch Liquid Retina XDR display with 1000 nits sustained brightness", "16.2-inch Liquid Retina XDR display with 1000 nits sustained brightness"),
        ("Battery", "Up to 22 hours battery life", "Up to 22 hours battery life")
    ])
]

for pid, specs in specs_data:
    cur.execute("DELETE FROM product_specs WHERE product_id = ?", (pid,))
    for seq, (k, v, orig) in enumerate(specs, 1):
        spec_id = f"spec:{pid}:{seq}"
        cur.execute("""
            INSERT INTO product_specs (spec_id, product_id, seq, key, value, unit, original_line)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (spec_id, pid, seq, k, v, None, orig))

conn.commit()
print("Successfully inserted detailed specs for all MacBooks into product_specs!")
conn.close()
