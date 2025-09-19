import os
import psycopg2
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

# =================== DB CONNECTION ===================
load_dotenv()

def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

def run_query(query, params=None, fetch=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params or ())
    data = cur.fetchall() if fetch else None
    conn.commit()
    cur.close()
    conn.close()
    return data

# =================== RECEIPT GENERATOR ===================
def generate_receipt_pdf(items, total):
    filename = "receipt.pdf"
    c = canvas.Canvas(filename, pagesize=letter)
    c.drawString(100, 750, "SHOP RECEIPT")
    y = 720
    for item, qty, price in items:
        c.drawString(100, y, f"{item} x{qty} - Rs {price}")
        y -= 20
    c.drawString(100, y-20, f"Total: Rs {total}")
    c.save()
    return filename

# =================== STREAMLIT APP ===================
st.set_page_config(page_title="Shop Management System", layout="wide")
st.title("📦 Shop Management System")

menu = ["Customers", "Products", "Repair Orders", "POS"]
choice = st.sidebar.radio("Navigation", menu)

# =================== CUSTOMERS PAGE ===================
if choice == "Customers":
    st.header("👥 Manage Customers")

    with st.form("add_customer_form"):
        st.subheader("➕ Add Customer")
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Name")
            contact = st.text_input("Contact Number")
        with col2:
            address = st.text_area("Address")
        submitted = st.form_submit_button("Add Customer")
        if submitted and name:
            run_query("INSERT INTO customers (name, contact_number, address) VALUES (%s, %s, %s)",
                      (name, contact, address))
            st.success(f"✅ Customer '{name}' added successfully!")
            st.rerun()

    st.subheader("📋 Customer List")
    customers = run_query("SELECT customer_id, name, contact_number, address FROM customers", fetch=True)
    if customers:
        df = pd.DataFrame(customers, columns=["ID", "Name", "Contact", "Address"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No customers found. Add one above.")

# =================== PRODUCTS PAGE ===================
elif choice == "Products":
    st.header("📦 Manage Products")

    with st.form("add_product_form"):
        st.subheader("➕ Add Product")
        col1, col2, col3 = st.columns(3)
        with col1:
            pname = st.text_input("Product Name")
        with col2:
            price = st.number_input("Price", min_value=0.0, step=0.1)
        with col3:
            qty = st.number_input("Quantity", min_value=0, step=1)
        submitted = st.form_submit_button("Add Product")
        if submitted and pname:
            run_query("INSERT INTO products (name, price, quantity) VALUES (%s, %s, %s)", (pname, price, qty))
            st.success(f"✅ Product '{pname}' added successfully!")
            st.rerun()


    st.subheader("📋 Product Inventory")
    products = run_query("SELECT product_id, name, price, quantity FROM products", fetch=True)
    if products:
        df = pd.DataFrame(products, columns=["ID", "Name", "Price", "Stock"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No products found. Add one above.")

# =================== REPAIR ORDERS PAGE ===================
elif choice == "Repair Orders":
    st.header("🛠 Manage Repair Orders")

    with st.form("add_order_form"):
        st.subheader("➕ New Repair Order")
        col1, col2 = st.columns(2)
        with col1:
            cust_id = st.number_input("Customer ID", min_value=1, step=1)
            product_details = st.text_input("Product Details")
        with col2:
            issue = st.text_area("Issue Description")
        submitted = st.form_submit_button("Create Order")
        if submitted:
            run_query("""INSERT INTO repair_orders (customer_id, product_details, issue_description)
                        VALUES (%s, %s, %s)""", (cust_id, product_details, issue))
            st.success("✅ Repair order created successfully!")
            st.rerun()


    st.subheader("📋 Repair Orders")
    orders = run_query("SELECT order_id, customer_id, product_details, issue_description, status FROM repair_orders", fetch=True)
    if orders:
        df = pd.DataFrame(orders, columns=["Order ID", "Customer ID", "Product", "Issue", "Status"])
        st.dataframe(df, use_container_width=True)
    else:
        st.info("No repair orders yet. Add one above.")

# =================== POS PAGE ===================
elif choice == "POS":
    st.header("🧾 Point of Sale")

    products = run_query("SELECT product_id, name, price, quantity FROM products", fetch=True)
    if not products:
        st.warning("⚠ No products available. Please add products first.")
    else:
        product_names = [f"{p[1]} (Stock: {p[3]})" for p in products]
        selection = st.selectbox("Select Product", product_names)
        selected = products[product_names.index(selection)]
        max_qty = selected[3]

        qty = st.number_input("Quantity", min_value=1, max_value=max_qty if max_qty else 1, step=1)
        total = qty * selected[2]
        st.metric("💰 Total Price", f"Rs {total}")

        if st.button("✅ Complete Sale"):
            run_query("UPDATE products SET quantity = quantity - %s WHERE product_id = %s", (qty, selected[0]))
            run_query("INSERT INTO sales (product_id, quantity, total_price) VALUES (%s, %s, %s)",
                      (selected[0], qty, total))
            receipt = generate_receipt_pdf([(selected[1], qty, total)], total)
            with open(receipt, "rb") as f:
                st.download_button("📄 Download Receipt", data=f, file_name=receipt)
            st.success("✅ Sale completed successfully!")
            st.rerun()

    # =================== SALES HISTORY ===================
    st.subheader("📊 Sales History")

    sales = run_query("""
        SELECT s.sale_id, p.name, s.quantity, s.total_price, s.sale_date
        FROM sales s
        JOIN products p ON s.product_id = p.product_id
        ORDER BY s.sale_date DESC
    """, fetch=True)

    if sales:
        df = pd.DataFrame(sales, columns=["Sale ID", "Product", "Quantity", "Total Price", "Date"])
        df["Date"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df, use_container_width=True)

        # Daily summary
        st.subheader("📅 Daily Summary")
        daily_summary = df.copy()
        daily_summary["Day"] = pd.to_datetime(df["Date"]).dt.date
        summary = daily_summary.groupby("Day").agg(
            total_sales=("Total Price", "sum"),
            items_sold=("Quantity", "sum"),
            transactions=("Sale ID", "count")
        ).reset_index()
        st.dataframe(summary, use_container_width=True)
    else:
        st.info("No sales have been made yet.")
