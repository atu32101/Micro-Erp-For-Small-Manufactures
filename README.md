# Micro ERP Website

A fully working Micro ERP Website for small manufacturers with role-based access control.

## Folder Structure
```

├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── README.md              # Project documentation
├── instance/
│   └── erp.db             # SQLite database
├── templates/
│   ├── base.html          # Base template with sidebar
│   ├── login.html         # Login page
│   ├── dashboard.html    # Dashboard with statistics
│   ├── products.html      # Product list
│   ├── add_product.html   # Add/Edit product
│   ├── orders.html        # Orders list
│   ├── add_order.html     # Create new order
│   ├── suppliers.html     # Supplier list
│   ├── add_supplier.html  # Add supplier
│   ├── users.html         # User list (Admin only)
│   └── add_user.html     # Add user (Admin only)
└── static/
    ├── style.css          # Modern responsive CSS
    └── script.js          # JavaScript validation
```

## Database Schema

### users
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| username | TEXT | Unique username |
| password | TEXT | User password |
| role | TEXT | User role (admin/manager/staff) |

### suppliers
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Supplier name |
| contact | TEXT | Contact person |
| email | TEXT | Email address |
| phone | TEXT | Phone number |

### products
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| name | TEXT | Product name |
| quantity | INTEGER | Stock quantity |
| price | REAL | Unit price |
| supplier_id | INTEGER | Foreign key to suppliers |

### orders
| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER | Primary key |
| product_id | INTEGER | Foreign key to products |
| quantity | INTEGER | Order quantity |
| total_price | REAL | Total price |
| order_date | TEXT | Order timestamp |
| created_by | INTEGER | Foreign key to users |

## User Roles & Permissions

| Role | Permissions |
|------|-------------|
| **Admin** | Full access to all features including user management |
| **Manager** | Can manage products, orders, and suppliers |
| **Staff** | Can view and create orders only |

## Features

1. **Authentication System**
   - Login with username and password
   - Session management
   - Role-based access control
   - Logout functionality

2. **Dashboard**
   - Total products count
   - Total orders count
   - Total suppliers count
   - Total inventory value
   - Users count (Admin only)

3. **Inventory Management**
   - Add/Edit/Delete products
   - Fields: Name, Quantity, Price, Supplier

4. **Orders Module**
   - Create new orders
   - Auto-calculate total price
   - Inventory automatically deducted
   - Track who created the order

5. **Supplier Management**
   - Add/Delete suppliers

6. **User Management (Admin only)**
   - Add new users
   - Delete users
   - Assign roles (admin/manager/staff)

## How to Run

1. Navigate to the project directory:
```
cd "d:/6th sem project"
```

2. Install dependencies:
```
pip install -r requirements.txt
```

3. Run the application:
```
python app.py
```

4. Open browser and go to:
```
http://127.0.0.1:5000
```

## Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | admin | admin123 |
| Manager | manager | manager123 |
| Staff | staff | staff123 |

## Tech Stack
- Backend: Python with Flask
- Database: SQLite
- Frontend: HTML, CSS, JavaScript
- Templating: Jinja2

