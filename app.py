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
@st.cache_data(ttl=60)
def get_dashboard_stats():
    """Get all stats in one optimized query"""
    result = run_query("""
        SELECT 
            (SELECT COUNT(*) FROM customers) as customers,
            (SELECT COUNT(*) FROM products) as products,
            (SELECT COALESCE(SUM(quantity), 0) FROM products) as stock,
            (SELECT COUNT(*) FROM repair_orders WHERE status = 'Pending') as pending_orders,
            (SELECT COUNT(*) FROM sales WHERE DATE(sale_date) = CURRENT_DATE) as today_sales,
            (SELECT COALESCE(SUM(total_price), 0) FROM sales WHERE DATE(sale_date) = CURRENT_DATE) as today_revenue
    """, fetch=True)
    
    if result:
        r = result[0]
        return {
            'customers': r[0], 'products': r[1], 'stock': r[2],
            'pending_orders': r[3], 'today_sales': r[4], 'today_revenue': float(r[5])
        }
    return {'customers': 0, 'products': 0, 'stock': 0, 'pending_orders': 0, 'today_sales': 0, 'today_revenue': 0.0}

@st.cache_data(ttl=120)
def get_customers_data():
    return run_query("SELECT customer_id, name, contact_number, address FROM customers ORDER BY name", fetch=True) or []

@st.cache_data(ttl=120) 
def get_products_data():
    return run_query("SELECT product_id, name, price, quantity FROM products ORDER BY name", fetch=True) or []

@st.cache_data(ttl=180)
def get_repair_orders_data():
    return run_query("""
        SELECT ro.order_id, c.name, c.contact_number, ro.product_details, 
               ro.issue_description, ro.status, ro.created_at
        FROM repair_orders ro
        JOIN customers c ON ro.customer_id = c.customer_id
        ORDER BY ro.created_at DESC LIMIT 100
    """, fetch=True) or []

def clear_all_cache():
    get_dashboard_stats.clear()
    get_customers_data.clear() 
    get_products_data.clear()
    get_repair_orders_data.clear()

def generate_professional_receipt(items, total, customer_data=None):
    """Generate professional PDF receipt with full customer details"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"receipt_{timestamp}.pdf"
    
    c = canvas.Canvas(filename, pagesize=letter)
    width, height = letter
    
    # === Header ===
    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 60, "RAMA WATCH & MOBILE SHOPEE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 85, "Viman Nagar, Pune - 411014")
    c.drawCentredString(width / 2, height - 105, "Phone: +91-9815267856")
    
    # === Receipt Info ===
    c.line(50, height - 125, width - 50, height - 125)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, height - 150, f"Receipt #: R{timestamp}")
    c.drawRightString(width - 50, height - 150, f"Date: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # === Customer Details Section ===
    y_pos = height - 175
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y_pos, "CUSTOMER DETAILS:")
    
    y_pos -= 20
    c.setFont("Helvetica", 10)
    
    if customer_data:
        if customer_data.get('name') == 'Walk-in Customer':
            # Handle walk-in customer
            c.drawString(50, y_pos, "Customer: Walk-in Customer")
            y_pos -= 15
            c.drawString(50, y_pos, "Contact: -")
            y_pos -= 15
            c.drawString(50, y_pos, "Address: -")
        else:
            # Handle registered customer
            customer_name = customer_data.get('name', '-')
            customer_contact = customer_data.get('contact', '-') if customer_data.get('contact') else '-'
            customer_address = customer_data.get('address', '-') if customer_data.get('address') else '-'
            
            c.drawString(50, y_pos, f"Customer: {customer_name}")
            y_pos -= 15
            c.drawString(50, y_pos, f"Contact: {customer_contact}")
            y_pos -= 15
            
            # Handle long addresses by wrapping text
            if len(customer_address) > 60:
                # Split address into multiple lines if too long
                address_lines = []
                words = customer_address.split()
                current_line = ""
                
                for word in words:
                    if len(current_line + " " + word) <= 60:
                        current_line += (" " + word) if current_line else word
                    else:
                        if current_line:
                            address_lines.append(current_line)
                        current_line = word
                
                if current_line:
                    address_lines.append(current_line)
                
                c.drawString(50, y_pos, f"Address: {address_lines[0] if address_lines else '-'}")
                y_pos -= 15
                
                # Additional address lines
                for line in address_lines[1:]:
                    c.drawString(50, y_pos, f"         {line}")
                    y_pos -= 15
            else:
                c.drawString(50, y_pos, f"Address: {customer_address}")
                y_pos -= 15
    else:
        # No customer data provided
        c.drawString(50, y_pos, "Customer: Walk-in Customer")
        y_pos -= 15
        c.drawString(50, y_pos, "Contact: -")
        y_pos -= 15
        c.drawString(50, y_pos, "Address: -")
    
    # === Items Table Header ===
    y_pos -= 20
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
        c.drawRightString(400, y_pos, f"Rs.{rate:.2f}")
        c.drawRightString(490, y_pos, f"Rs.{amount:.2f}")
        y_pos -= 20
    
    # === Total Section ===
    c.line(350, y_pos - 5, width - 50, y_pos - 5)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(350, y_pos - 25, "TOTAL:")
    c.drawRightString(490, y_pos - 25, f"Rs.{total:.2f}")
    
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
        customers = get_customers_data()
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

# =================== REPAIR ORDERS PAGE (WITH RETURN FEATURE) ===================
elif choice == "Repair Orders":
    st.subheader("🛠️ Repair Order Management")
    
    # Quick stats
    col1, col2, col3, col4, col5 = st.columns(5)
    
    status_counts = run_query("""
        SELECT status, COUNT(*) 
        FROM repair_orders 
        WHERE status != 'Returned'
        GROUP BY status
    """, fetch=True)
    
    # Get returned count separately
    returned_count = run_query("SELECT COUNT(*) FROM repair_orders WHERE status = 'Returned'", fetch=True)
    returned_count = returned_count[0][0] if returned_count else 0
    
    status_dict = {status: count for status, count in status_counts} if status_counts else {}
    
    with col1:
        st.metric("Pending", status_dict.get('Pending', 0))
    with col2:
        st.metric("In Progress", status_dict.get('In Progress', 0))
    with col3:
        st.metric("Completed", status_dict.get('Completed', 0))
    with col4:
        st.metric("Returned", returned_count, delta="Hidden from main view")
    with col5:
        total_orders = sum(status_dict.values()) + returned_count
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
    
    # Enhanced filter options
    col1, col2 = st.columns([2, 1])
    with col1:
        status_filter = st.selectbox("Filter by Status", ["Active Orders", "Pending", "In Progress", "Completed", "All (Including Returned)", "Returned Only"])
    with col2:
        show_returned = st.checkbox("Show Returned Orders", value=False, help="Include returned orders in the list")
    
    # Build query based on filters (SIMPLIFIED LOGIC)
    query = """
        SELECT ro.order_id, c.name, c.contact_number, ro.product_details, 
               ro.issue_description, ro.status, ro.created_at
        FROM repair_orders ro
        JOIN customers c ON ro.customer_id = c.customer_id
    """
    
    params = []
    conditions = []
    
    # Clear and simple filtering logic
    if status_filter == "Active Orders":
        # Show all except returned
        conditions.append("ro.status IN ('Pending', 'In Progress', 'Completed')")
    elif status_filter == "Returned Only":
        # Show only returned
        conditions.append("ro.status = 'Returned'")
    elif status_filter == "All (Including Returned)":
        # Show everything - no conditions
        pass
    elif status_filter in ["Pending", "In Progress", "Completed"]:
        # Show specific status only
        conditions.append("ro.status = %s")
        params.append(status_filter)
    
    # Apply show_returned checkbox override
    if show_returned and status_filter == "Active Orders":
        # Override: show all including returned
        conditions = []  # Remove the active orders filter
    elif not show_returned and status_filter == "All (Including Returned)":
        # Override: exclude returned even from "All"
        conditions.append("ro.status != 'Returned'")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
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
        
        # Display with enhanced status management
        for idx, order in df.iterrows():
            # Different styling for returned orders
            if order['Status'] == 'Returned':
                container_style = "border: 2px solid #ff6b6b; border-radius: 5px; padding: 10px; background-color: #ffe0e0;"
            else:
                container_style = ""
            
            with st.container():
                if container_style:
                    st.markdown(f'<div style="{container_style}">', unsafe_allow_html=True)
                
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
                    elif current_status == 'Completed':
                        st.success(f"✅ {current_status}")
                    elif current_status == 'Returned':
                        st.error(f"↩️ {current_status}")
                
                with col4:
                    # Status update logic
                    if current_status == 'Returned':
                        st.write("**Returned**")
                        if st.button("Restore", key=f"restore_{order['Order ID']}", help="Move back to Completed"):
                            run_query("UPDATE repair_orders SET status = %s WHERE order_id = %s",
                                     ('Completed', order['Order ID']))
                            st.success("Order restored to Completed status")
                            st.rerun()
                    else:
                        # Regular status updates
                        available_statuses = ["Pending", "In Progress", "Completed"]
                        
                        new_status = st.selectbox(
                            "Update Status",
                            available_statuses,
                            index=available_statuses.index(current_status),
                            key=f"status_{order['Order ID']}"
                        )
                        
                        # Update button
                        if st.button("Update", key=f"btn_{order['Order ID']}"):
                            if new_status != current_status:
                                run_query("UPDATE repair_orders SET status = %s WHERE order_id = %s",
                                         (new_status, order['Order ID']))
                                st.success(f"Status updated to {new_status}")
                                st.rerun()
                        
                        # Return button (only for completed orders)
                        if current_status == 'Completed':
                            if st.button("📦 Mark as Returned", key=f"return_{order['Order ID']}", 
                                       help="Customer has collected the repaired item"):
                                # Confirmation dialog simulation
                                if st.button(f"✅ Confirm Return #{order['Order ID']}", 
                                           key=f"confirm_return_{order['Order ID']}",
                                           type="primary"):
                                    run_query("UPDATE repair_orders SET status = %s WHERE order_id = %s",
                                             ('Returned', order['Order ID']))
                                    st.success(f"Order #{order['Order ID']} marked as returned and will be hidden from main view")
                                    st.rerun()
                
                if container_style:
                    st.markdown('</div>', unsafe_allow_html=True)
                
                st.divider()
        
        # Summary information
        active_orders = len([o for o in orders if o[5] != 'Returned'])
        returned_orders = len([o for o in orders if o[5] == 'Returned'])
        
        if status_filter == "Active Orders" or not show_returned:
            st.info(f"Showing {len(orders)} active repair orders | {returned_count} returned orders hidden")
        else:
            st.info(f"Showing {len(orders)} repair orders | Active: {active_orders}, Returned: {returned_orders}")
            
    else:
        if status_filter == "Returned Only":
            st.info("No returned repair orders found.")
        else:
            st.info("No repair orders found.")
    
    # Additional features
    if returned_count > 0:
        with st.expander("📊 Returned Orders Analytics", expanded=False):
            returned_analysis = run_query("""
                SELECT 
                    DATE_TRUNC('month', created_at) as month,
                    COUNT(*) as returned_count
                FROM repair_orders 
                WHERE status = 'Returned'
                AND created_at >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY DATE_TRUNC('month', created_at)
                ORDER BY month DESC
            """, fetch=True)
            
            if returned_analysis:
                df_returned = pd.DataFrame(returned_analysis, columns=['Month', 'Returned Count'])
                df_returned['Month'] = pd.to_datetime(df_returned['Month']).dt.strftime('%B %Y')
                
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("Monthly Returns")
                    st.dataframe(df_returned, hide_index=True)
                
                with col2:
                    st.subheader("Quick Stats")
                    st.metric("Total Returned", returned_count)
                    
                    avg_completion = run_query("""
                        SELECT AVG(EXTRACT(EPOCH FROM (
                            CASE WHEN status = 'Returned' 
                            THEN CURRENT_TIMESTAMP 
                            ELSE created_at END - created_at
                        )) / 86400) as avg_days
                        FROM repair_orders 
                        WHERE status IN ('Completed', 'Returned')
                    """, fetch=True)
                    
                    if avg_completion and avg_completion[0][0]:
                        st.metric("Avg. Completion Time", f"{avg_completion[0][0]:.1f} days")
            else:
                st.info("No returned orders data available for analysis.")

# =================== POINT OF SALE PAGE (FIXED VERSION) ===================
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
                
                # Customer selection for receipt (UPDATED)
                customers = run_query("SELECT customer_id, name, contact_number, address FROM customers ORDER BY name", fetch=True)
                if customers:
                    customer_options = ["Walk-in Customer"] + [f"{c[1]} (ID: {c[0]})" for c in customers]
                    selected_customer_display = st.selectbox("Customer", customer_options)
                    
                    # Extract customer data properly
                    if selected_customer_display != "Walk-in Customer":
                        # Extract customer ID from the display string
                        customer_id_str = selected_customer_display.split("(ID: ")[1].split(")")[0]
                        selected_customer_id = int(customer_id_str)
                        
                        # Get full customer data from the list
                        customer_info = next((c for c in customers if c[0] == selected_customer_id), None)
                        if customer_info:
                            customer_data = {
                                'name': customer_info[1],
                                'contact': customer_info[2],
                                'address': customer_info[3]
                            }
                        else:
                            customer_data = None
                    else:
                        selected_customer_id = None
                        customer_data = {'name': 'Walk-in Customer'}
                else:
                    selected_customer_id = None
                    customer_data = {'name': 'Walk-in Customer'}
                
                # Checkout buttons
                col_clear, col_checkout = st.columns(2)
                
                with col_clear:
                    if st.button("🗑️ Clear Cart", use_container_width=True):
                        st.session_state.cart = []
                        st.rerun()
                
                with col_checkout:
                    if st.button("✅ Complete Sale", use_container_width=True, type="primary"):
                        # FIXED: Process sale with proper error handling and user feedback
                        try:
                            # Show processing message
                            with st.spinner("Processing sale..."):
                                for item in st.session_state.cart:
                                    # Update inventory
                                    run_query("UPDATE products SET quantity = quantity - %s WHERE product_id = %s",
                                             (item['quantity'], item['product_id']))
                                    
                                    # Record sale - FIXED: Use the properly defined selected_customer_id
                                    run_query("INSERT INTO sales (product_id, quantity, total_price, customer_id) VALUES (%s, %s, %s, %s)",
                                             (item['product_id'], item['quantity'], item['total'], selected_customer_id))
                                
                                # Generate receipt with full customer data
                                receipt_items = [(item['name'], item['quantity'], item['total']) for item in st.session_state.cart]
                                receipt_file = generate_professional_receipt(receipt_items, grand_total, customer_data)
                            
                            # FIXED: Success message without immediate rerun
                            st.success(f"✅ Sale completed successfully! Total: ₹{grand_total:.2f}")
                            
                            # FIXED: Show balloons with delay
                            st.balloons()
                            
                            # FIXED: Download receipt with better UX
                            try:
                                with open(receipt_file, "rb") as pdf_file:
                                    pdf_data = pdf_file.read()
                                    
                                # Store receipt data in session state to prevent immediate disappearance
                                st.session_state['last_receipt'] = {
                                    'data': pdf_data,
                                    'filename': receipt_file,
                                    'total': grand_total
                                }
                                
                                st.info("Receipt generated successfully! Use the download button below:")
                                
                                # Clean up the temporary file
                                try:
                                    os.remove(receipt_file)
                                except:
                                    pass
                                
                            except Exception as e:
                                st.warning(f"Receipt generation had an issue, but sale was successful: {str(e)}")
                            
                            # Clear cart after successful sale
                            st.session_state.cart = []
                            
                            # FIXED: Don't rerun immediately, let user see the success message
                        
                        except Exception as e:
                            st.error(f"Sale processing failed: {str(e)}")
                            st.error("Please try again or contact support if the issue persists.")
                
                # FIXED: Show download button for last receipt if available
                if 'last_receipt' in st.session_state:
                    st.download_button(
                        "📄 Download Last Receipt",
                        data=st.session_state['last_receipt']['data'],
                        file_name=st.session_state['last_receipt']['filename'],
                        mime="application/pdf",
                        use_container_width=True,
                        help=f"Download receipt for ₹{st.session_state['last_receipt']['total']:.2f} transaction"
                    )
                    
                    # Option to clear receipt data
                    if st.button("Clear Receipt Data", help="Clear stored receipt to free memory"):
                        del st.session_state['last_receipt']
                        st.rerun()
                        
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