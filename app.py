import os
import psycopg2
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go


# =================== CONFIGURATION ===================
st.set_page_config(
    page_title="Rama Shop Management",
    page_icon="🏪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for modern UI
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        padding: 1rem;
        background: linear-gradient(90deg, #e3f2fd, #f3e5f5);
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    .metric-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        border-left: 4px solid #1f77b4;
    }
    
    .success-message {
        background: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 5px;
        border: 1px solid #c3e6cb;
    }
    
    .sidebar-logo {
        text-align: center;
        font-size: 1.5rem;
        font-weight: bold;
        color: #1f77b4;
        margin-bottom: 2rem;
    }
</style>
""", unsafe_allow_html=True)

# =================== DATABASE CONNECTION ===================
load_dotenv()

@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASS"),
        port=os.getenv("DB_PORT", "5432")
    )

def run_query(query, params=None, fetch=False):
    try:
        conn = init_connection()  # cached connection
        cur = conn.cursor()
        cur.execute(query, params or ())
        data = cur.fetchall() if fetch else None
        conn.commit()
        cur.close()
        return data
    except Exception as e:
        st.error(f"Database error: {str(e)}")
        return None

# =================== UTILITY FUNCTIONS ===================
def get_dashboard_stats():
    """Get key business metrics"""
    customers = run_query("SELECT COUNT(*) FROM customers", fetch=True)
    products = run_query("SELECT COUNT(*), SUM(quantity) FROM products", fetch=True)
    orders = run_query("SELECT COUNT(*) FROM repair_orders WHERE status = 'Pending'", fetch=True)
    today_sales = run_query("""
        SELECT COUNT(*), COALESCE(SUM(total_price), 0) 
        FROM sales 
        WHERE DATE(sale_date) = CURRENT_DATE
    """, fetch=True)
    
    return {
        'customers': customers[0][0] if customers else 0,
        'products': products[0][0] if products else 0,
        'stock': products[0][1] if products and products[0][1] else 0,
        'pending_orders': orders[0][0] if orders else 0,
        'today_sales': today_sales[0][0] if today_sales else 0,
        'today_revenue': float(today_sales[0][1]) if today_sales else 0.0
    }


def generate_professional_receipt(items, total, customer_name=None):
    """Generate professional PDF receipt"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"receipt_{timestamp}.pdf"
    
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # === Header ===
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 60, "RAMA WATCH & MOBILE SHOPEE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 85, "Viman Nagar, Pune - 411014")
    c.drawCentredString(width / 2, height - 105, "Phone: +91-XXXXXXXXXX")
    
    # === Receipt Info ===
    c.line(50, height - 125, width - 50, height - 125)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 150, f"Receipt #: R{timestamp}")
    c.drawRightString(width - 50, height - 150, f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    if customer_name:
        c.setFont("Helvetica", 10)
        c.drawString(50, height - 170, f"Customer: {customer_name}")
    
    # === Items Table Header ===
    y_pos = height - 200
    c.setFont("Helvetica-Bold", 11)
    c.drawString(60, y_pos, "ITEM")
    c.drawString(300, y_pos, "QTY")
    c.drawString(360, y_pos, "RATE")
    c.drawString(450, y_pos, "AMOUNT")
    c.line(50, y_pos - 10, width - 50, y_pos - 10)
    
    # === Items List ===
    y_pos -= 25
    c.setFont("Helvetica", 10)
    for item_name, quantity, amount in items:
        rate = amount / quantity if quantity > 0 else amount
        c.drawString(60, y_pos, str(item_name)[:30])
        c.drawString(300, y_pos, str(quantity))
        c.drawRightString(400, y_pos, f"₹{rate:.2f}")
        c.drawRightString(490, y_pos, f"₹{amount:.2f}")
        y_pos -= 20
    
    # === Total Section ===
    c.line(350, y_pos - 5, width - 50, y_pos - 5)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y_pos - 25, "TOTAL:")
    c.drawRightString(490, y_pos - 25, f"₹{total:.2f}")
    
    # === Footer ===
    c.setFont("Helvetica", 8)
    c.drawCentredString(width / 2, 80, "Thank you for your business!")
    c.drawCentredString(width / 2, 65, "Visit us again!")
    
    c.save()
    return filename


# =================== SESSION STATE ===================
if 'cart' not in st.session_state:
    st.session_state.cart = []
if 'selected_customer' not in st.session_state:
    st.session_state.selected_customer = None

# =================== SIDEBAR ===================
st.sidebar.markdown('<div class="sidebar-logo">🏪 RAMA SHOP</div>', unsafe_allow_html=True)

# Navigation
menu_options = {
    "📊 Dashboard": "Dashboard",
    "👥 Customers": "Customers", 
    "📦 Products": "Products",
    "🛠️ Repair Orders": "Repair Orders",
    "💳 Point of Sale": "POS"
}

selected = st.sidebar.radio("Navigation", list(menu_options.keys()))
choice = menu_options[selected]

# Quick stats in sidebar
st.sidebar.markdown("---")
st.sidebar.subheader("📈 Quick Stats")
stats = get_dashboard_stats()
st.sidebar.metric("Today's Sales", f"₹{stats['today_revenue']:.2f}")
st.sidebar.metric("Pending Orders", stats['pending_orders'])
st.sidebar.metric("Total Stock", stats['stock'])

# =================== MAIN HEADER ===================
st.markdown(f'<div class="main-header">🏪 Rama Watch & Mobile Shop Management</div>', unsafe_allow_html=True)

# =================== DASHBOARD ===================
if choice == "Dashboard":
    st.subheader("📊 Business Overview")
    
    # Key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Customers", stats['customers'], delta="Active")
    with col2:
        st.metric("Products", stats['products'], delta=f"{stats['stock']} in stock")
    with col3:
        st.metric("Today's Revenue", f"₹{stats['today_revenue']:.2f}", delta=f"{stats['today_sales']} sales")
    with col4:
        st.metric("Pending Repairs", stats['pending_orders'], delta="To complete")
    
    # Charts
    col1, col2 = st.columns(2)
    
    # Sales trend (last 7 days)
    with col1:
        st.subheader("📈 Sales Trend (Last 7 Days)")
        sales_data = run_query("""
            SELECT DATE(sale_date) as date, SUM(total_price) as revenue
            FROM sales 
            WHERE sale_date >= CURRENT_DATE - INTERVAL '7 days'
            GROUP BY DATE(sale_date)
            ORDER BY date
        """, fetch=True)
        
        if sales_data:
            df_sales = pd.DataFrame(sales_data, columns=['Date', 'Revenue'])
            fig = px.line(df_sales, x='Date', y='Revenue', markers=True)
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sales data available for the last 7 days")
    
    # Top products
    with col2:
        st.subheader("🏆 Top Selling Products")
        top_products = run_query("""
            SELECT p.name, SUM(s.quantity) as sold
            FROM sales s
            JOIN products p ON s.product_id = p.product_id
            WHERE s.sale_date >= CURRENT_DATE - INTERVAL '30 days'
            GROUP BY p.name
            ORDER BY sold DESC
            LIMIT 5
        """, fetch=True)
        
        if top_products:
            df_top = pd.DataFrame(top_products, columns=['Product', 'Quantity Sold'])
            fig = px.bar(df_top, x='Quantity Sold', y='Product', orientation='h')
            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No sales data available")

# =================== CUSTOMERS PAGE ===================
elif choice == "Customers":
    st.subheader("👥 Customer Management")
    
    # Customer form with better UX
    with st.expander("➕ Add New Customer", expanded=False):
        with st.form("customer_form", clear_on_submit=True):
            col1, col2 = st.columns([2, 1])
            
            with col1:
                name = st.text_input("Full Name *", placeholder="Enter customer's full name")
                address = st.text_area("Address", placeholder="Complete address with area/city", height=100)
            
            with col2:
                contact = st.text_input("Contact Number", placeholder="+91 XXXXXXXXXX")
                
            submitted = st.form_submit_button("🔹 Add Customer", use_container_width=True)
            
            if submitted:
                if not name.strip():
                    st.error("Customer name is required!")
                elif contact and not contact.replace('+', '').replace('-', '').replace(' ', '').isdigit():
                    st.error("Please enter a valid contact number!")
                else:
                    result = run_query(
                        "INSERT INTO customers (name, contact_number, address) VALUES (%s, %s, %s) RETURNING customer_id",
                        (name.strip(), contact.strip() if contact else None, address.strip() if address else None),
                        fetch=True
                    )
                    if result:
                        st.success(f"✅ Customer '{name}' added successfully! ID: {result[0][0]}")
                        st.balloons()
                        st.rerun()

    # Enhanced customer list
    st.subheader("📋 Customer Directory")
    
    # Search functionality
    search_term = st.text_input("🔍 Search customers", placeholder="Search by name, contact, or address...")
    
    if search_term:
        customers = run_query(
            "SELECT customer_id, name, contact_number, address FROM customers WHERE name ILIKE %s OR contact_number ILIKE %s OR address ILIKE %s ORDER BY name",
            (f"%{search_term}%", f"%{search_term}%", f"%{search_term}%"),
            fetch=True
        )
    else:
        customers = run_query("SELECT customer_id, name, contact_number, address FROM customers ORDER BY name", fetch=True)
    
    if customers:
        df = pd.DataFrame(customers, columns=["ID", "Name", "Contact", "Address"])
        
        # Interactive dataframe with selection
        selected_rows = st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "ID": st.column_config.NumberColumn("Customer ID", width="small"),
                "Name": st.column_config.TextColumn("Full Name", width="medium"),
                "Contact": st.column_config.TextColumn("Phone", width="medium"),
                "Address": st.column_config.TextColumn("Address", width="large")
            }
        )
        
        st.info(f"Total customers: {len(customers)}")
    else:
        st.info("No customers found. Add your first customer above!")

# =================== PRODUCTS PAGE ===================
elif choice == "Products":
    st.subheader("📦 Inventory Management")
    
    # Product statistics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Products", stats['products'])
    with col2:
        st.metric("Total Stock", stats['stock'])
    with col3:
        low_stock = run_query("SELECT COUNT(*) FROM products WHERE quantity <= 5", fetch=True)
        low_stock_count = low_stock[0][0] if low_stock else 0
        st.metric("Low Stock Alert", low_stock_count, delta="Items ≤ 5")
    
    # Add product form
    with st.expander("➕ Add New Product", expanded=False):
        with st.form("product_form", clear_on_submit=True):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                pname = st.text_input("Product Name *", placeholder="e.g., iPhone 15, Samsung Galaxy Watch")
            with col2:
                price = st.number_input("Price (₹) *", min_value=0.01, step=0.01, format="%.2f")
            with col3:
                qty = st.number_input("Initial Stock *", min_value=0, step=1)
            
            submitted = st.form_submit_button("🔹 Add Product", use_container_width=True)
            
            if submitted and pname.strip() and price > 0:
                run_query("INSERT INTO products (name, price, quantity) VALUES (%s, %s, %s)",
                         (pname.strip(), price, qty))
                st.success(f"✅ Product '{pname}' added to inventory!")
                st.rerun()

    # Enhanced product list
    st.subheader("📋 Product Inventory")
    
    # Search and filter
    col1, col2 = st.columns([2, 1])
    with col1:
        search_product = st.text_input("🔍 Search products", placeholder="Search by product name...")
    with col2:
        stock_filter = st.selectbox("Stock Filter", ["All", "In Stock", "Low Stock (≤5)", "Out of Stock"])
    
    # Build query based on filters
    base_query = "SELECT product_id, name, price, quantity FROM products"
    params = []
    conditions = []
    
    if search_product:
        conditions.append("name ILIKE %s")
        params.append(f"%{search_product}%")
    
    if stock_filter == "In Stock":
        conditions.append("quantity > 0")
    elif stock_filter == "Low Stock (≤5)":
        conditions.append("quantity <= 5 AND quantity > 0")
    elif stock_filter == "Out of Stock":
        conditions.append("quantity = 0")
    
    if conditions:
        base_query += " WHERE " + " AND ".join(conditions)
    
    base_query += " ORDER BY name"
    
    products = run_query(base_query, params, fetch=True)
    
    if products:
        df = pd.DataFrame(products, columns=["ID", "Product Name", "Price (₹)", "Stock"])
        
        # Color code based on stock levels
        def highlight_stock(row):
            if row['Stock'] == 0:
                return ['background-color: #880000; color: white'] * len(row)  # Light red for out of stock
            elif row['Stock'] <= 5:
                return ['background-color: #FF8C00; color: white'] * len(row)  # Light orange for low stock
            else:
                return [''] * len(row)
        
        styled_df = df.style.apply(highlight_stock, axis=1)
        st.dataframe(styled_df, use_container_width=True, hide_index=True)
        
        st.info(f"Showing {len(products)} products")
        
        # Stock alerts
        if stock_filter == "All":
            out_of_stock = sum(1 for p in products if p[3] == 0)
            low_stock_items = sum(1 for p in products if 0 < p[3] <= 5)
            
            if out_of_stock > 0:
                st.error(f"⚠️ {out_of_stock} products are out of stock!")
            if low_stock_items > 0:
                st.warning(f"⚠️ {low_stock_items} products have low stock (≤5 items)!")
    else:
        st.info("No products found matching your criteria.")

# =================== REPAIR ORDERS PAGE ===================
elif choice == "Repair Orders":
    st.subheader("🛠️ Repair Order Management")
    
    # Quick stats
    col1, col2, col3, col4 = st.columns(4)
    
    status_counts = run_query("""
        SELECT status, COUNT(*) 
        FROM repair_orders 
        GROUP BY status
    """, fetch=True)
    
    status_dict = {status: count for status, count in status_counts} if status_counts else {}
    
    with col1:
        st.metric("Pending", status_dict.get('Pending', 0))
    with col2:
        st.metric("In Progress", status_dict.get('In Progress', 0))
    with col3:
        st.metric("Completed", status_dict.get('Completed', 0))
    with col4:
        total_orders = sum(status_dict.values())
        st.metric("Total Orders", total_orders)
    
    # Create new repair order
    with st.expander("➕ Create New Repair Order", expanded=False):
        with st.form("repair_order_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                # Customer selection with search
                customers = run_query("SELECT customer_id, name, contact_number FROM customers ORDER BY name", fetch=True)
                if customers:
                    customer_options = [f"{c[1]} (ID: {c[0]}) - {c[2] or 'No contact'}" for c in customers]
                    selected_customer_idx = st.selectbox("Select Customer", range(len(customer_options)),
                                                        format_func=lambda x: customer_options[x])
                    selected_customer_id = customers[selected_customer_idx][0]
                else:
                    st.error("No customers found. Please add customers first.")
                    selected_customer_id = None
                
                product_details = st.text_input("Product Details *", 
                                               placeholder="e.g., iPhone 12 Pro, Samsung Galaxy Watch 4")
            
            with col2:
                issue = st.text_area("Issue Description *", 
                                   placeholder="Describe the problem in detail...",
                                   height=100)
                priority = st.selectbox("Priority", ["Normal", "High", "Urgent"])
            
            submitted = st.form_submit_button("🔹 Create Repair Order", use_container_width=True)
            
            if submitted and selected_customer_id and product_details.strip() and issue.strip():
                run_query("""
                    INSERT INTO repair_orders (customer_id, product_details, issue_description, status) 
                    VALUES (%s, %s, %s, %s)
                """, (selected_customer_id, product_details.strip(), issue.strip(), 'Pending'))
                st.success("✅ Repair order created successfully!")
                st.rerun()

    # Repair orders list with status management
    st.subheader("📋 Repair Orders")
    
    # Status filter
    status_filter = st.selectbox("Filter by Status", ["All", "Pending", "In Progress", "Completed"])
    
    query = """
        SELECT ro.order_id, c.name, c.contact_number, ro.product_details, 
               ro.issue_description, ro.status, ro.created_at
        FROM repair_orders ro
        JOIN customers c ON ro.customer_id = c.customer_id
    """
    
    if status_filter != "All":
        query += " WHERE ro.status = %s"
        params = [status_filter]
    else:
        params = []
    
    query += " ORDER BY ro.created_at DESC"
    
    orders = run_query(query, params, fetch=True)
    
    if orders:
        # Create interactive dataframe
        df = pd.DataFrame(orders, columns=[
            "Order ID", "Customer", "Contact", "Product", 
            "Issue", "Status", "Created"
        ])
        
        # Format datetime
        df['Created'] = pd.to_datetime(df['Created']).dt.strftime('%d/%m/%Y %H:%M')
        
        # Display with status update capability
        for idx, order in df.iterrows():
            with st.container():
                col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
                
                with col1:
                    st.write(f"**#{order['Order ID']}** - {order['Customer']}")
                    st.write(f"📱 {order['Product']}")
                    st.write(f"🔧 {order['Issue'][:50]}...")
                
                with col2:
                    st.write(f"📞 {order['Contact'] or 'No contact'}")
                    st.write(f"📅 {order['Created']}")
                
                with col3:
                    current_status = order['Status']
                    if current_status == 'Pending':
                        st.warning(f"⏳ {current_status}")
                    elif current_status == 'In Progress':
                        st.info(f"🔄 {current_status}")
                    else:
                        st.success(f"✅ {current_status}")
                
                with col4:
                    new_status = st.selectbox(
                        "Update Status",
                        ["Pending", "In Progress", "Completed"],
                        index=["Pending", "In Progress", "Completed"].index(current_status),
                        key=f"status_{order['Order ID']}"
                    )
                    
                    if st.button("Update", key=f"btn_{order['Order ID']}"):
                        if new_status != current_status:
                            run_query("UPDATE repair_orders SET status = %s WHERE order_id = %s",
                                     (new_status, order['Order ID']))
                            st.success(f"Status updated to {new_status}")
                            st.rerun()
                
                st.divider()
        
        st.info(f"Showing {len(orders)} repair orders")
    else:
        st.info("No repair orders found.")

# =================== POINT OF SALE PAGE ===================
elif choice == "POS":
    st.subheader("💳 Point of Sale System")
    
    # Check if products exist
    products = run_query("SELECT product_id, name, price, quantity FROM products WHERE quantity > 0 ORDER BY name", fetch=True)
    
    if not products:
        st.warning("⚠️ No products available in stock. Please add products first.")
    else:
        col1, col2 = st.columns([2, 1])
        
        # Product selection and cart
        with col1:
            st.subheader("🛒 Product Selection")
            
            # Search products
            search_pos = st.text_input("🔍 Search products", placeholder="Type to search...")
            
            if search_pos:
                filtered_products = [p for p in products if search_pos.lower() in p[1].lower()]
            else:
                filtered_products = products
            
            if filtered_products:
                selected_product_idx = st.selectbox(
                    "Select Product",
                    range(len(filtered_products)),
                    format_func=lambda x: f"{filtered_products[x][1]} - ₹{filtered_products[x][2]:.2f} (Stock: {filtered_products[x][3]})"
                )
                
                selected_product = filtered_products[selected_product_idx]
                max_qty = selected_product[3]
                
                col_qty, col_add = st.columns([1, 1])
                with col_qty:
                    qty = st.number_input("Quantity", min_value=1, max_value=max_qty, value=1)
                with col_add:
                    st.write("") # Space
                    if st.button("🛒 Add to Cart", use_container_width=True):
                        # Check if product already in cart
                        existing_item = next((item for item in st.session_state.cart 
                                            if item['product_id'] == selected_product[0]), None)
                        
                        if existing_item:
                            existing_item['quantity'] += qty
                            existing_item['total'] = existing_item['quantity'] * existing_item['price']
                        else:
                            cart_item = {
                                'product_id': selected_product[0],
                                'name': selected_product[1],
                                'price': selected_product[2],
                                'quantity': qty,
                                'total': qty * selected_product[2]
                            }
                            st.session_state.cart.append(cart_item)
                        
                        st.success(f"Added {qty}x {selected_product[1]} to cart!")
                        st.rerun()
        
        # Shopping cart and checkout
        with col2:
            st.subheader("🧾 Shopping Cart")
            
            if st.session_state.cart:
                # Display cart items
                for idx, item in enumerate(st.session_state.cart):
                    col_item, col_remove = st.columns([3, 1])
                    
                    with col_item:
                        st.write(f"**{item['name']}**")
                        st.write(f"{item['quantity']} x ₹{item['price']:.2f} = ₹{item['total']:.2f}")
                    
                    with col_remove:
                        if st.button("❌", key=f"remove_{idx}", help="Remove item"):
                            st.session_state.cart.pop(idx)
                            st.rerun()
                    
                    st.divider()
                
                # Cart total
                grand_total = sum(item['total'] for item in st.session_state.cart)
                st.metric("**Grand Total**", f"₹{grand_total:.2f}")
                
                # Customer selection for receipt
                customers = run_query("SELECT customer_id, name FROM customers ORDER BY name", fetch=True)
                if customers:
                    customer_options = ["Walk-in Customer"] + [f"{c[1]} (ID: {c[0]})" for c in customers]
                    selected_customer = st.selectbox("Customer", customer_options)
                    
                    if selected_customer != "Walk-in Customer":
                        customer_name = selected_customer.split(" (ID:")[0]
                    else:
                        customer_name = None
                else:
                    customer_name = None
                
                # Checkout buttons
                col_clear, col_checkout = st.columns(2)
                
                with col_clear:
                    if st.button("🗑️ Clear Cart", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()
                
                with col_checkout:
                    if st.button("✅ Complete Sale", use_container_width=True, type="primary"):
                        # Process sale
                        try:
                            for item in st.session_state.cart:
                                # Update inventory
                                run_query("UPDATE products SET quantity = quantity - %s WHERE product_id = %s",
                                         (item['quantity'], item['product_id']))
                                
                                # Record sale
                                run_query("INSERT INTO sales (product_id, quantity, total_price) VALUES (%s, %s, %s)",
                                         (item['product_id'], item['quantity'], item['total']))
                            
                            # Generate receipt
                            receipt_items = [(item['name'], item['quantity'], item['total']) for item in st.session_state.cart]
                            receipt_file = generate_professional_receipt(receipt_items, grand_total, customer_name)
                            
                            # Success message
                            st.success(f"✅ Sale completed! Total: ₹{grand_total:.2f}")
                            st.balloons()
                            
                            # Download receipt
                            with open(receipt_file, "rb") as pdf_file:
                                st.download_button(
                                    "📄 Download Receipt",
                                    data=pdf_file.read(),
                                    file_name=receipt_file,
                                    mime="application/pdf",
                                    use_container_width=True
                                )
                            
                            # Clear cart
                            st.session_state.cart = []
                            st.rerun()
                        
                        except Exception as e:
                            st.error(f"Sale processing failed: {str(e)}")
            else:
                st.info("Cart is empty. Add products to get started!")
        
        # Sales history and analytics
        st.subheader("📊 Sales Analytics")
        
        # Today's sales summary
        today_sales = run_query("""
            SELECT COUNT(*), SUM(total_price), SUM(quantity)
            FROM sales 
            WHERE DATE(sale_date) = CURRENT_DATE
        """, fetch=True)
        
        if today_sales and today_sales[0][0]:
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Today's Transactions", today_sales[0][0])
            with col2:
                st.metric("Today's Revenue", f"₹{today_sales[0][1]:.2f}")
            with col3:
                st.metric("Items Sold Today", today_sales[0][2])
        
        # Recent sales
        with st.expander("📋 Recent Sales History", expanded=False):
            recent_sales = run_query("""
                SELECT s.sale_id, p.name, s.quantity, s.total_price, s.sale_date
                FROM sales s
                JOIN products p ON s.product_id = p.product_id
                ORDER BY s.sale_date DESC
                LIMIT 20
            """, fetch=True)
            
            if recent_sales:
                df_sales = pd.DataFrame(recent_sales, columns=[
                    "Sale ID", "Product", "Quantity", "Amount", "Date"
                ])
                df_sales['Date'] = pd.to_datetime(df_sales['Date']).dt.strftime('%d/%m/%Y %H:%M')
                
                st.dataframe(df_sales, use_container_width=True, hide_index=True)
                
                # Quick stats
                total_sales = sum(sale[3] for sale in recent_sales)
                st.info(f"Showing last 20 transactions | Total value: ₹{total_sales:.2f}")
            else:
                st.info("No recent sales found.")

# =================== FOOTER ===================
st.markdown("---")
st.markdown("""
<div style='text-align: center; color: #666; padding: 1rem;'>
    <p>🏪 <strong>Rama Watch & Mobile Shopee</strong> - Digital Management System</p>
    <p>Developed by: Kishor Kumbhar, Rohan Koli, Shreeram Kulat | T.Y.B.Sc Computer Science</p>
    <p><em>Nowrosjee Wadia College, Pune</em></p>
</div>
""", unsafe_allow_html=True)