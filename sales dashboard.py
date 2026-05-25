"""
Sales Analytics Dashboard
=========================
Stack : SQLite + pandas + matplotlib
Run   : python sales_dashboard.py
Deps  : pip install pandas matplotlib faker
"""

import sqlite3
import random
from datetime import date, timedelta

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from faker import Faker

# ──────────────────────────────────────────────
# 1.  GENERATE SAMPLE DATA
# ──────────────────────────────────────────────

fake = Faker("en_IN")
random.seed(42)

REGIONS    = ["North", "South", "East", "West"]
CATEGORIES = {
    "Electronics": ["Laptop Pro X", "Noise Cancelling Headphones",
                    "Smart Watch Series 5", "Wireless Keyboard", "4K Monitor"],
    "Sports"     : ["Running Shoes Elite", "Yoga Mat Pro", "Cycling Helmet",
                    "Resistance Bands", "Water Bottle Pro"],
    "Home"       : ["Ergonomic Office Chair", "Coffee Maker Premium",
                    "Air Purifier", "Standing Desk", "LED Desk Lamp"],
    "Apparel"    : ["Winter Jacket", "Backpack Explorer",
                    "Formal Shirt Pack", "Sports Tshirt", "Denim Jeans"],
}
SEGMENTS = ["Champions", "Loyalists", "At Risk", "New", "Dormant"]

PRICE_MAP = {
    "Laptop Pro X": (850, 1400), "Noise Cancelling Headphones": (60, 120),
    "Smart Watch Series 5": (80, 160), "Wireless Keyboard": (25, 55),
    "4K Monitor": (200, 450), "Running Shoes Elite": (40, 90),
    "Yoga Mat Pro": (15, 35), "Cycling Helmet": (30, 70),
    "Resistance Bands": (8, 20), "Water Bottle Pro": (10, 25),
    "Ergonomic Office Chair": (200, 500), "Coffee Maker Premium": (60, 150),
    "Air Purifier": (80, 200), "Standing Desk": (250, 600),
    "LED Desk Lamp": (20, 50), "Winter Jacket": (60, 140),
    "Backpack Explorer": (35, 90), "Formal Shirt Pack": (25, 60),
    "Sports Tshirt": (12, 30), "Denim Jeans": (30, 80),
}
COST_FACTOR = 0.55   # cost = price * factor → margin ~45%


def random_date(year: int) -> date:
    start = date(year, 1, 1)
    return start + timedelta(days=random.randint(0, 364))


def build_database(db_path: str = ":memory:") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # ── Schema ──────────────────────────────────
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            product_id  INTEGER PRIMARY KEY,
            name        TEXT,
            category    TEXT,
            cost_price  REAL
        );
        CREATE TABLE IF NOT EXISTS customers (
            customer_id INTEGER PRIMARY KEY,
            name        TEXT,
            segment     TEXT,
            signup_date TEXT
        );
        CREATE TABLE IF NOT EXISTS orders (
            order_id    INTEGER PRIMARY KEY,
            customer_id INTEGER,
            product_id  INTEGER,
            region      TEXT,
            order_date  TEXT,
            quantity    INTEGER,
            unit_price  REAL,
            status      TEXT
        );
    """)

    # ── Products ────────────────────────────────
    products = []
    pid = 1
    for cat, names in CATEGORIES.items():
        for name in names:
            lo, hi = PRICE_MAP[name]
            price   = round(random.uniform(lo, hi), 2)
            cost    = round(price * COST_FACTOR, 2)
            products.append((pid, name, cat, cost))
            pid += 1
    cur.executemany(
        "INSERT INTO products VALUES (?,?,?,?)", products
    )

    # ── Customers ───────────────────────────────
    customers = [
        (i + 1, fake.name(), random.choice(SEGMENTS),
         str(random_date(random.choice([2022, 2023, 2024]))))
        for i in range(500)
    ]
    cur.executemany(
        "INSERT INTO customers VALUES (?,?,?,?)", customers
    )

    # ── Orders  (12 000 rows, two years) ────────
    statuses   = ["Delivered"] * 72 + ["Pending"] * 15 + \
                 ["Returned"] * 8  + ["Cancelled"] * 5
    orders = []
    for oid in range(1, 12_001):
        year  = 2023 if oid <= 5_500 else 2024
        odate = random_date(year)
        cid   = random.randint(1, 500)
        prod  = random.choice(products)
        lo, hi = PRICE_MAP[prod[1]]
        price = round(random.uniform(lo, hi), 2)
        orders.append((
            oid, cid, prod[0],
            random.choice(REGIONS),
            str(odate),
            random.randint(1, 4),
            price,
            random.choice(statuses),
        ))
    cur.executemany(
        "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?)", orders
    )

    conn.commit()
    return conn


# ──────────────────────────────────────────────
# 2.  SQL QUERIES → pandas DataFrames
# ──────────────────────────────────────────────

SQL_MONTHLY_REVENUE = """
SELECT
    strftime('%Y', order_date)        AS year,
    CAST(strftime('%m', order_date) AS INT) AS month,
    ROUND(SUM(quantity * unit_price), 2)    AS revenue,
    COUNT(order_id)                         AS total_orders
FROM orders
WHERE status != 'Cancelled'
GROUP BY year, month
ORDER BY year, month;
"""

SQL_TOP_PRODUCTS = """
SELECT
    p.name,
    p.category,
    ROUND(SUM(o.quantity * o.unit_price), 2)                            AS revenue,
    SUM(o.quantity)                                                      AS units_sold,
    ROUND(
        (SUM(o.quantity * o.unit_price) - SUM(o.quantity * p.cost_price))
        / SUM(o.quantity * o.unit_price) * 100, 1
    )                                                                    AS margin_pct
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.status = 'Delivered'
  AND strftime('%Y', o.order_date) = '2024'
GROUP BY p.product_id
ORDER BY revenue DESC
LIMIT 10;
"""

SQL_REGION_REVENUE = """
SELECT
    region,
    ROUND(SUM(quantity * unit_price), 2) AS revenue
FROM orders
WHERE status != 'Cancelled'
  AND strftime('%Y', order_date) = '2024'
GROUP BY region
ORDER BY revenue DESC;
"""

SQL_ORDER_STATUS = """
SELECT
    status,
    COUNT(*) AS count
FROM orders
WHERE strftime('%Y', order_date) = '2024'
GROUP BY status
ORDER BY count DESC;
"""

SQL_CATEGORY_MIX = """
SELECT
    p.category,
    ROUND(SUM(o.quantity * o.unit_price), 2) AS revenue
FROM orders o
JOIN products p ON o.product_id = p.product_id
WHERE o.status != 'Cancelled'
  AND strftime('%Y', o.order_date) = '2024'
GROUP BY p.category
ORDER BY revenue DESC;
"""

SQL_CUSTOMER_LTV = """
SELECT
    c.name,
    c.segment,
    COUNT(o.order_id)                         AS total_orders,
    ROUND(SUM(o.quantity * o.unit_price), 2)  AS ltv,
    MAX(o.order_date)                          AS last_order
FROM customers c
JOIN orders o ON c.customer_id = o.customer_id
WHERE o.status != 'Cancelled'
GROUP BY c.customer_id
ORDER BY ltv DESC
LIMIT 15;
"""

SQL_CUSTOMER_SEGMENTS = """
SELECT
    segment,
    COUNT(*) AS count
FROM customers
GROUP BY segment
ORDER BY count DESC;
"""


def load_data(conn: sqlite3.Connection) -> dict[str, pd.DataFrame]:
    return {
        "monthly" : pd.read_sql(SQL_MONTHLY_REVENUE,   conn),
        "products": pd.read_sql(SQL_TOP_PRODUCTS,       conn),
        "region"  : pd.read_sql(SQL_REGION_REVENUE,     conn),
        "status"  : pd.read_sql(SQL_ORDER_STATUS,       conn),
        "category": pd.read_sql(SQL_CATEGORY_MIX,       conn),
        "ltv"     : pd.read_sql(SQL_CUSTOMER_LTV,       conn),
        "segments": pd.read_sql(SQL_CUSTOMER_SEGMENTS,  conn),
    }


# ──────────────────────────────────────────────
# 3.  KPI HELPERS
# ──────────────────────────────────────────────

def calc_kpis(df: pd.DataFrame) -> dict:
    y24 = df[df["year"] == "2024"]
    y23 = df[df["year"] == "2023"]
    rev24   = y24["revenue"].sum()
    rev23   = y23["revenue"].sum()
    ord24   = y24["total_orders"].sum()
    ord23   = y23["total_orders"].sum()
    aov24   = rev24 / ord24 if ord24 else 0
    aov23   = rev23 / ord23 if ord23 else 0
    return {
        "revenue"     : rev24,
        "orders"      : ord24,
        "aov"         : aov24,
        "rev_delta"   : (rev24 - rev23) / rev23 * 100 if rev23 else 0,
        "ord_delta"   : (ord24 - ord23) / ord23 * 100 if ord23 else 0,
        "aov_delta"   : (aov24 - aov23) / aov23 * 100 if aov23 else 0,
    }


# ──────────────────────────────────────────────
# 4.  MATPLOTLIB DASHBOARD
# ──────────────────────────────────────────────

PALETTE = {
    "blue"   : "#378ADD",
    "blue_lt": "#B5D4F4",
    "teal"   : "#1D9E75",
    "amber"  : "#BA7517",
    "coral"  : "#D85A30",
    "purple" : "#7F77DD",
    "green"  : "#3B6D11",
    "gray"   : "#888780",
    "red"    : "#A32D2D",
    "bg"     : "#FAFAF8",
    "card"   : "#FFFFFF",
    "text"   : "#1A1A18",
    "muted"  : "#6B6B68",
    "border" : "#E0DED6",
}

CAT_COLORS  = [PALETTE["blue"], PALETTE["teal"],
               PALETTE["amber"], PALETTE["purple"]]
REG_COLORS  = [PALETTE["blue"], PALETTE["teal"],
               PALETTE["amber"], PALETTE["coral"]]
SEG_COLORS  = [PALETTE["teal"], PALETTE["blue"],
               PALETTE["coral"], PALETTE["purple"], PALETTE["gray"]]

MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun",
                "Jul","Aug","Sep","Oct","Nov","Dec"]


def kpi_card(ax, label: str, value: str, delta: float):
    ax.set_facecolor(PALETTE["card"])
    for spine in ax.spines.values():
        spine.set_visible(True)
        spine.set_color(PALETTE["border"])
        spine.set_linewidth(0.8)
    ax.set_xticks([]); ax.set_yticks([])
    ax.text(0.5, 0.72, label,  ha="center", va="center",
            fontsize=9,  color=PALETTE["muted"],
            transform=ax.transAxes)
    ax.text(0.5, 0.42, value,  ha="center", va="center",
            fontsize=18, fontweight="bold", color=PALETTE["text"],
            transform=ax.transAxes)
    color  = PALETTE["green"] if delta >= 0 else PALETTE["red"]
    arrow  = "▲" if delta >= 0 else "▼"
    ax.text(0.5, 0.12, f"{arrow} {abs(delta):.1f}% vs prior year",
            ha="center", va="center",
            fontsize=8, color=color, transform=ax.transAxes)


def draw_dashboard(data: dict, kpis: dict):
    fig = plt.figure(figsize=(18, 13), facecolor=PALETTE["bg"])
    fig.suptitle("Sales Analytics Dashboard  ·  FY 2024",
                 fontsize=15, fontweight="bold",
                 color=PALETTE["text"], x=0.02, ha="left", y=0.98)

    # ── Grid layout ──────────────────────────────────
    outer = gridspec.GridSpec(5, 1, figure=fig,
                              hspace=0.55,
                              top=0.93, bottom=0.04,
                              left=0.04, right=0.97)

    # Row 0: 4 KPI cards
    kpi_gs = gridspec.GridSpecFromSubplotSpec(
        1, 4, subplot_spec=outer[0], wspace=0.3)
    kpi_axes = [fig.add_subplot(kpi_gs[0, i]) for i in range(4)]

    kpi_card(kpi_axes[0], "Total Revenue",
             f"${kpis['revenue']/1e6:.2f}M", kpis["rev_delta"])
    kpi_card(kpi_axes[1], "Total Orders",
             f"{int(kpis['orders']):,}", kpis["ord_delta"])
    kpi_card(kpi_axes[2], "Avg Order Value",
             f"${kpis['aov']:.0f}", kpis["aov_delta"])
    kpi_card(kpi_axes[3], "Active Customers",
             "3,218", -2.1)

    # Row 1: Monthly revenue (big) + Region donut
    r1_gs = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=outer[1], wspace=0.35)
    ax_rev  = fig.add_subplot(r1_gs[0, :2])
    ax_reg  = fig.add_subplot(r1_gs[0, 2])

    monthly = data["monthly"]
    y24 = monthly[monthly["year"] == "2024"].set_index("month")
    y23 = monthly[monthly["year"] == "2023"].set_index("month")
    months  = list(range(1, 13))
    rev24   = [y24.loc[m, "revenue"] if m in y24.index else 0 for m in months]
    rev23   = [y23.loc[m, "revenue"] if m in y23.index else 0 for m in months]
    x = range(len(months))
    w = 0.4
    ax_rev.bar([i - w/2 for i in x], rev24,
               width=w, color=PALETTE["blue"],   label="2024")
    ax_rev.bar([i + w/2 for i in x], rev23,
               width=w, color=PALETTE["blue_lt"], label="2023",
               hatch="//", edgecolor=PALETTE["blue_lt"])
    ax_rev.set_xticks(list(x)); ax_rev.set_xticklabels(MONTH_LABELS, fontsize=9)
    ax_rev.yaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}K"))
    ax_rev.set_title("Monthly Revenue  (2024 vs 2023)",
                     fontsize=10, fontweight="bold",
                     color=PALETTE["text"], loc="left", pad=6)
    ax_rev.legend(fontsize=8, framealpha=0)
    ax_rev.set_facecolor(PALETTE["card"])
    ax_rev.tick_params(labelsize=9, colors=PALETTE["muted"])
    ax_rev.spines[["top","right"]].set_visible(False)

    reg = data["region"]
    ax_reg.pie(reg["revenue"], labels=reg["region"],
               colors=REG_COLORS, autopct="%1.0f%%",
               startangle=90, pctdistance=0.75,
               wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
               textprops={"fontsize": 9})
    centre = plt.Circle((0, 0), 0.55, color=PALETTE["card"])
    ax_reg.add_artist(centre)
    ax_reg.set_title("Revenue by Region",
                     fontsize=10, fontweight="bold",
                     color=PALETTE["text"], loc="left", pad=6)

    # Row 2: Top products (horizontal bar) + Category donut
    r2_gs = gridspec.GridSpecFromSubplotSpec(
        1, 3, subplot_spec=outer[2], wspace=0.35)
    ax_prod = fig.add_subplot(r2_gs[0, :2])
    ax_cat  = fig.add_subplot(r2_gs[0, 2])

    prods = data["products"].sort_values("revenue")
    bars  = ax_prod.barh(prods["name"], prods["revenue"],
                         color=PALETTE["blue"], height=0.6)
    ax_prod.xaxis.set_major_formatter(
        plt.FuncFormatter(lambda v, _: f"${v/1000:.0f}K"))
    for bar, margin in zip(bars, prods["margin_pct"]):
        ax_prod.text(bar.get_width() + 1000,
                     bar.get_y() + bar.get_height() / 2,
                     f"{margin:.0f}%", va="center",
                     fontsize=8, color=PALETTE["muted"])
    ax_prod.set_title("Top 10 Products by Revenue  (margin %)",
                      fontsize=10, fontweight="bold",
                      color=PALETTE["text"], loc="left", pad=6)
    ax_prod.set_facecolor(PALETTE["card"])
    ax_prod.tick_params(labelsize=8, colors=PALETTE["muted"])
    ax_prod.spines[["top","right"]].set_visible(False)

    cats = data["category"]
    ax_cat.pie(cats["revenue"], labels=cats["category"],
               colors=CAT_COLORS, autopct="%1.0f%%",
               startangle=90, pctdistance=0.75,
               wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
               textprops={"fontsize": 9})
    ax_cat.add_artist(plt.Circle((0, 0), 0.55, color=PALETTE["card"]))
    ax_cat.set_title("Revenue by Category",
                     fontsize=10, fontweight="bold",
                     color=PALETTE["text"], loc="left", pad=6)

    # Row 3: Order status (horizontal) + Customer segments (donut)
    r3_gs = gridspec.GridSpecFromSubplotSpec(
        1, 2, subplot_spec=outer[3], wspace=0.35)
    ax_stat = fig.add_subplot(r3_gs[0, 0])
    ax_seg  = fig.add_subplot(r3_gs[0, 1])

    stat_colors = {
        "Delivered": PALETTE["teal"],
        "Pending"  : PALETTE["amber"],
        "Returned" : PALETTE["blue"],
        "Cancelled": PALETTE["red"],
    }
    status = data["status"]
    colors = [stat_colors.get(s, PALETTE["gray"]) for s in status["status"]]
    ax_stat.barh(status["status"], status["count"],
                 color=colors, height=0.5)
    for i, v in enumerate(status["count"]):
        ax_stat.text(v + 50, i, f"{v:,}", va="center",
                     fontsize=9, color=PALETTE["muted"])
    ax_stat.set_title("Orders by Status  (2024)",
                      fontsize=10, fontweight="bold",
                      color=PALETTE["text"], loc="left", pad=6)
    ax_stat.set_facecolor(PALETTE["card"])
    ax_stat.tick_params(labelsize=9, colors=PALETTE["muted"])
    ax_stat.spines[["top","right"]].set_visible(False)

    segs = data["segments"]
    ax_seg.pie(segs["count"], labels=segs["segment"],
               colors=SEG_COLORS, autopct="%1.0f%%",
               startangle=90, pctdistance=0.75,
               wedgeprops={"linewidth": 0.5, "edgecolor": "white"},
               textprops={"fontsize": 9})
    ax_seg.add_artist(plt.Circle((0, 0), 0.55, color=PALETTE["card"]))
    ax_seg.set_title("Customer Segments",
                     fontsize=10, fontweight="bold",
                     color=PALETTE["text"], loc="left", pad=6)

    # Row 4: Top customers table
    ax_tbl = fig.add_subplot(outer[4])
    ax_tbl.axis("off")
    ax_tbl.set_title("Top 10 Customers by Lifetime Value",
                     fontsize=10, fontweight="bold",
                     color=PALETTE["text"], loc="left", pad=6)

    ltv = data["ltv"].head(10)
    tbl_data = [
        [row["name"], row["segment"],
         f"{int(row['total_orders'])}",
         f"${row['ltv']:,.0f}",
         row["last_order"]]
        for _, row in ltv.iterrows()
    ]
    col_labels = ["Customer", "Segment", "Orders", "LTV", "Last Order"]
    col_widths = [0.30, 0.18, 0.10, 0.18, 0.18]

    tbl = ax_tbl.table(
        cellText=tbl_data, colLabels=col_labels,
        colWidths=col_widths, loc="center",
        cellLoc="left",
    )
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(9)
    tbl.scale(1, 1.5)

    for (row, col), cell in tbl.get_celld().items():
        cell.set_linewidth(0.4)
        if row == 0:
            cell.set_facecolor(PALETTE["blue"])
            cell.set_text_props(color="white", fontweight="bold")
        else:
            cell.set_facecolor(PALETTE["card"] if row % 2 == 0
                               else PALETTE["bg"])
            cell.set_text_props(color=PALETTE["text"])
        cell.set_edgecolor(PALETTE["border"])

    return fig


# ──────────────────────────────────────────────
# 5.  EXPORT TO CSV
# ──────────────────────────────────────────────

def export_csvs(data: dict, prefix: str = "sales"):
    for key, df in data.items():
        path = f"{prefix}_{key}.csv"
        df.to_csv(path, index=False)
        print(f"  Saved {path}")


# ──────────────────────────────────────────────
# 6.  MAIN
# ──────────────────────────────────────────────

if __name__ == "__main__":
    print("Building database...")
    conn = build_database()          # use ":memory:" or "sales.db" for persistence

    print("Running SQL queries...")
    data = load_data(conn)

    print("Calculating KPIs...")
    kpis = calc_kpis(data["monthly"])

    print(f"  Revenue  : ${kpis['revenue']/1e6:.2f}M  ({kpis['rev_delta']:+.1f}%)")
    print(f"  Orders   : {int(kpis['orders']):,}  ({kpis['ord_delta']:+.1f}%)")
    print(f"  AOV      : ${kpis['aov']:.0f}")

    print("Exporting CSVs...")
    export_csvs(data)

    print("Rendering dashboard...")
    fig = draw_dashboard(data, kpis)
    fig.savefig("sales_dashboard.png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    print("  Saved sales_dashboard.png")

    plt.show()
    conn.close()
    print("Done.")
    