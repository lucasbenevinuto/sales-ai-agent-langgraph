from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union
import requests
import os
from urllib.parse import urljoin

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool

from database.db_manager import DatabaseManager

db_manager = DatabaseManager()

# API configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000/api/")
HEADERS = {
    "Content-Type": "application/json"
}

# Utility function for API requests
def make_api_request(method, endpoint, params=None, data=None, headers=None):
    """Makes an API request to the specified endpoint."""
    url = urljoin(API_BASE_URL, endpoint)
    _headers = HEADERS.copy()
    if headers:
        _headers.update(headers)
    
    response = requests.request(
        method=method,
        url=url,
        params=params,
        json=data,
        headers=_headers
    )
    
    response.raise_for_status()
    return response.json() if response.content else None

# Automatic login at module initialization
def auto_login():
    """Automatically authenticate using predefined credentials"""
    try:
        # Using form data for login
        response = requests.post(
            urljoin(API_BASE_URL, "auth/login"),
            data={"username": "lucas@example.com", "password": "12345"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()
        auth_data = response.json()
        
        # Update global headers with authorization token
        HEADERS["Authorization"] = f"{auth_data['token_type']} {auth_data['access_token']}"
        print("Auto-login successful")
        return auth_data
    except Exception as e:
        print(f"Auto-login failed: {str(e)}")
        return None

# Perform automatic login at module initialization
auto_login()

# 1. API Root and Health Endpoints

@tool
def get_api_welcome():
    """
    Returns the API welcome message from the root endpoint.
    """
    return make_api_request("GET", "")

@tool
def check_api_health():
    """
    Checks the health status of the API and database connection.
    """
    return make_api_request("GET", "health")

@tool
def get_db_tables():
    """
    Lists all tables in the database.
    """
    return make_api_request("GET", "db-tables")

# 2. Authentication Endpoints

@tool
def register_user(name: str, email: str, password: str) -> Dict[str, Any]:
    """
    Registers a new user in the system.
    
    Arguments:
        name: The user's full name
        email: The user's email address
        password: The user's password
    
    Returns:
        Dict containing user information including id, name, email and created_at
    """
    data = {
        "name": name,
        "email": email,
        "password": password
    }
    return make_api_request("POST", "auth/register", data=data)

@tool
def login_user(username: str, password: str) -> Dict[str, str]:
    """
    Authenticates a user and returns an access token.
    
    Arguments:
        username: The user's email address
        password: The user's password
    
    Returns:
        Dict containing access_token and token_type
    """
    # Using form data instead of JSON for login
    response = requests.post(
        urljoin(API_BASE_URL, "auth/login"),
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"}
    )
    response.raise_for_status()
    return response.json()

@tool
def logout_user() -> Dict[str, str]:
    """
    Logs out the current user.
    
    Returns:
        Message confirming successful logout
    """
    return make_api_request("POST", "auth/logout")

# 3. User Endpoints

@tool
def get_current_user() -> Dict[str, Any]:
    """
    Retrieves the profile of the currently authenticated user.
    
    Returns:
        Dict containing user information including id, name, email and created_at
    """
    return make_api_request("GET", "users/me")

@tool
def get_user_by_id(user_id: int) -> Dict[str, Any]:
    """
    Retrieves a user profile by ID.
    
    Arguments:
        user_id: The ID of the user to retrieve
    
    Returns:
        Dict containing user information including id, name, email and created_at
    """
    return make_api_request("GET", f"users/{user_id}")

@tool
def list_users(skip: int = 0, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Lists users with pagination.
    
    Arguments:
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 10)
    
    Returns:
        List of user dictionaries
    """
    params = {
        "skip": skip,
        "limit": limit
    }
    return make_api_request("GET", "users/", params=params)

@tool
def update_user(user_id: int, name: Optional[str] = None, email: Optional[str] = None, 
                password: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates a user's profile information.
    
    Arguments:
        user_id: ID of the user to update
        name: New name for the user (optional)
        email: New email for the user (optional)
        password: New password for the user (optional)
    
    Returns:
        Updated user information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if email is not None:
        data["email"] = email
    if password is not None:
        data["password"] = password
    
    return make_api_request("PUT", f"users/{user_id}", data=data)

@tool
def delete_user(user_id: int) -> None:
    """
    Deletes a user from the system.
    
    Arguments:
        user_id: ID of the user to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"users/{user_id}")
    return {"message": f"User {user_id} has been deleted"}

@tool
def get_available_categories() -> Dict[str, List[str]]:
    """Returns a list of available product categories."""
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT DISTINCT Category
            FROM products
            WHERE Quantity > 0
        """
        )
        categories = cursor.fetchall()
        return {"categories": [category["Category"] for category in categories]}


@tool
def search_products(
    query: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Searches for products based on various criteria.

    Arguments:
        query (Optional[str]): Search term for product name or description
        category (Optional[str]): Filter by product category
        min_price (Optional[float]): Minimum price filter
        max_price (Optional[float]): Maximum price filter

    Returns:
        Dict[str, Any]: Search results with products and metadata

    Example:
        search_products(query="banana", category="fruits", max_price=5.00)
    """
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        query_parts = ["SELECT * FROM products WHERE Quantity > 0"]
        params = []

        if query:
            query_parts.append(
                """
                AND (
                    LOWER(ProductName) LIKE ? 
                    OR LOWER(Description) LIKE ?
                )
            """
            )
            search_term = f"%{query.lower()}%"
            params.extend([search_term, search_term])

        if category:
            query_parts.append("AND LOWER(Category) = ?")
            params.append(category.lower())

        if min_price is not None:
            query_parts.append("AND Price >= ?")
            params.append(min_price)

        if max_price is not None:
            query_parts.append("AND Price <= ?")
            params.append(max_price)

        # Execute search query
        cursor.execute(" ".join(query_parts), params)
        products = cursor.fetchall()

        # Get available categories for metadata
        cursor.execute(
            """
            SELECT DISTINCT Category, COUNT(*) as count 
            FROM products 
            WHERE Quantity > 0 
            GROUP BY Category
        """
        )
        categories = cursor.fetchall()

        # Get price range for metadata
        cursor.execute(
            """
            SELECT 
                MIN(Price) as min_price,
                MAX(Price) as max_price,
                AVG(Price) as avg_price
            FROM products
            WHERE Quantity > 0
        """
        )
        price_stats = cursor.fetchone()

        return {
            "status": "success",
            "products": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in products
            ],
            "metadata": {
                "total_results": len(products),
                "categories": [
                    {"name": cat["Category"], "product_count": cat["count"]}
                    for cat in categories
                ],
                "price_range": {
                    "min": float(price_stats["min_price"]),
                    "max": float(price_stats["max_price"]),
                    "average": round(float(price_stats["avg_price"]), 2),
                },
            },
        }


@tool
def create_order(
    products: List[Dict[str, Any]], *, config: RunnableConfig
) -> Dict[str, str]:
    """
    Creates a new order (product purchase) for the customer.

     Arguments:
         products (List[Dict[str, Any]]): The list of products to be purchased.

     Returns:
         Dict[str, str]: Order details including status and message

     Example:
         create_order([{"ProductName": "Product A", "Quantity": 2}, {"ProductName": "Product B", "Quantity": 1}])
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        return ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        try:
            # Start transaction
            cursor.execute("BEGIN TRANSACTION")

            # Create order
            cursor.execute(
                """INSERT INTO orders (CustomerId, OrderDate, Status) 
                   VALUES (?, ?, ?)""",
                (customer_id, datetime.now().isoformat(), "Pending"),
            )
            order_id = cursor.lastrowid

            total_amount = Decimal("0")
            ordered_products = []

            # Process each product
            for item in products:
                product_name = item["ProductName"]
                quantity = item["Quantity"]

                # Get product details
                cursor.execute(
                    "SELECT ProductId, Price, Quantity FROM products WHERE LOWER(ProductName) = LOWER(?)",
                    (product_name,),
                )
                product = cursor.fetchone()

                if not product:
                    raise ValueError(f"Product not found: {product_name}")

                if product["Quantity"] < quantity:
                    raise ValueError(f"Insufficient stock for {product_name}")

                # Add order detail
                cursor.execute(
                    """INSERT INTO orders_details (OrderId, ProductId, Quantity, UnitPrice) 
                       VALUES (?, ?, ?, ?)""",
                    (order_id, product["ProductId"], quantity, product["Price"]),
                )

                # Update inventory
                cursor.execute(
                    "UPDATE products SET Quantity = Quantity - ? WHERE ProductId = ?",
                    (quantity, product["ProductId"]),
                )

                total_amount += Decimal(str(product["Price"])) * Decimal(str(quantity))
                ordered_products.append(
                    {
                        "name": product_name,
                        "quantity": quantity,
                        "unit_price": float(product["Price"]),
                    }
                )

            cursor.execute("COMMIT")

            return {
                "order_id": str(order_id),
                "status": "success",
                "message": "Order created successfully",
                "total_amount": float(total_amount),
                "products": ordered_products,
                "customer_id": str(customer_id),
            }

        except Exception as e:
            cursor.execute("ROLLBACK")
            return {
                "status": "error",
                "message": str(e),
                "customer_id": str(customer_id),
            }


@tool
def check_order_status(
    order_id: Union[str, None], *, config: RunnableConfig
) -> Dict[str, Union[str, None]]:
    """
    Checks the status of a specific order or all customer orders.

    Arguments:
        order_id (Union[str, None]): The ID of the order to check. If None, all customer orders will be returned.
    """
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        if order_id:
            # Query specific order
            cursor.execute(
                """
                SELECT 
                    o.OrderId,
                    o.OrderDate,
                    o.Status,
                    GROUP_CONCAT(p.ProductName || ' (x' || od.Quantity || ')') as Products,
                    SUM(od.Quantity * od.UnitPrice) as TotalAmount
                FROM orders o
                JOIN orders_details od ON o.OrderId = od.OrderId
                JOIN products p ON od.ProductId = p.ProductId
                WHERE o.OrderId = ? AND o.CustomerId = ?
                GROUP BY o.OrderId
            """,
                (order_id, customer_id),
            )

            order = cursor.fetchone()
            if not order:
                return {
                    "status": "error",
                    "message": "Order not found",
                    "customer_id": str(customer_id),
                    "order_id": str(order_id),
                }

            return {
                "status": "success",
                "order_id": str(order["OrderId"]),
                "order_date": order["OrderDate"],
                "order_status": order["Status"],
                "products": order["Products"],
                "total_amount": float(order["TotalAmount"]),
                "customer_id": str(customer_id),
            }
        else:
            # Query all customer orders
            cursor.execute(
                """
                SELECT 
                    o.OrderId,
                    o.OrderDate,
                    o.Status,
                    COUNT(od.OrderDetailId) as ItemCount,
                    SUM(od.Quantity * od.UnitPrice) as TotalAmount
                FROM orders o
                JOIN orders_details od ON o.OrderId = od.OrderId
                WHERE o.CustomerId = ?
                GROUP BY o.OrderId
                ORDER BY o.OrderDate DESC
            """,
                (customer_id,),
            )

            orders = cursor.fetchall()
            return {
                "status": "success",
                "customer_id": str(customer_id),
                "orders": [
                    {
                        "order_id": str(order["OrderId"]),
                        "order_date": order["OrderDate"],
                        "status": order["Status"],
                        "item_count": order["ItemCount"],
                        "total_amount": float(order["TotalAmount"]),
                    }
                    for order in orders
                ],
            }


@tool
def search_products_recommendations(config: RunnableConfig) -> Dict[str, str]:
    """Searches for product recommendations for the customer."""
    configuration = config.get("configurable", {})
    customer_id = configuration.get("customer_id", None)

    if not customer_id:
        raise ValueError("No customer ID configured.")

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()

        # Get customer's previous purchases
        cursor.execute(
            """
            SELECT DISTINCT p.Category
            FROM orders o
            JOIN orders_details od ON o.OrderId = od.OrderId
            JOIN products p ON od.ProductId = p.ProductId
            WHERE o.CustomerId = ?
            ORDER BY o.OrderDate DESC
            LIMIT 3
        """,
            (customer_id,),
        )

        favorite_categories = cursor.fetchall()

        if not favorite_categories:
            # If no purchase history, recommend popular products
            cursor.execute(
                """
                SELECT 
                    ProductId,
                    ProductName,
                    Category,
                    Description,
                    Price,
                    Quantity
                FROM products
                WHERE Quantity > 0
                ORDER BY RANDOM()
                LIMIT 5
            """
            )
        else:
            # Recommend products from favorite categories
            placeholders = ",".join("?" * len(favorite_categories))
            categories = [cat["Category"] for cat in favorite_categories]

            cursor.execute(
                f"""
                SELECT 
                    ProductId,
                    ProductName,
                    Category,
                    Description,
                    Price,
                    Quantity
                FROM products
                WHERE Category IN ({placeholders})
                AND Quantity > 0
                ORDER BY RANDOM()
                LIMIT 5
            """,
                categories,
            )

        recommendations = cursor.fetchall()

        return {
            "status": "success",
            "customer_id": str(customer_id),
            "recommendations": [
                {
                    "product_id": str(product["ProductId"]),
                    "name": product["ProductName"],
                    "category": product["Category"],
                    "description": product["Description"],
                    "price": float(product["Price"]),
                    "stock": product["Quantity"],
                }
                for product in recommendations
            ],
        }

# 4. Expense Endpoints

@tool
def create_expense(amount: float, date: str, category_id: Optional[int] = None, 
                  description: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new expense record.
    
    Arguments:
        amount: Amount of the expense (must be greater than 0)
        date: Date of the expense in YYYY-MM-DD format
        category_id: ID of the expense category (optional)
        description: Description of the expense (optional)
    
    Returns:
        Created expense information
    """
    data = {
        "amount": amount,
        "date": date
    }
    if category_id is not None:
        data["category_id"] = category_id
    if description is not None:
        data["description"] = description
    
    return make_api_request("POST", "expenses/", data=data)

@tool
def get_expense(expense_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific expense.
    
    Arguments:
        expense_id: ID of the expense
    
    Returns:
        Expense details
    """
    return make_api_request("GET", f"expenses/{expense_id}")

@tool
def list_expenses(category_id: Optional[int] = None, start_date: Optional[str] = None,
                 end_date: Optional[str] = None, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Lists expenses with optional filtering.
    
    Arguments:
        category_id: Filter by expense category (optional)
        start_date: Start date filter in YYYY-MM-DD format (optional)
        end_date: End date filter in YYYY-MM-DD format (optional)
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
    
    Returns:
        List of expense records
    """
    params = {
        "skip": skip,
        "limit": limit
    }
    if category_id is not None:
        params["category_id"] = category_id
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    
    return make_api_request("GET", "expenses/", params=params)

@tool
def update_expense(expense_id: int, category_id: Optional[int] = None, amount: Optional[float] = None,
                  date: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing expense.
    
    Arguments:
        expense_id: ID of the expense to update
        category_id: New category ID (optional)
        amount: New amount (optional, must be greater than 0)
        date: New date in YYYY-MM-DD format (optional)
        description: New description (optional)
    
    Returns:
        Updated expense information
    """
    data = {}
    if category_id is not None:
        data["category_id"] = category_id
    if amount is not None:
        data["amount"] = amount
    if date is not None:
        data["date"] = date
    if description is not None:
        data["description"] = description
    
    return make_api_request("PUT", f"expenses/{expense_id}", data=data)

@tool
def delete_expense(expense_id: int) -> None:
    """
    Deletes an expense.
    
    Arguments:
        expense_id: ID of the expense to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"expenses/{expense_id}")
    return {"message": f"Expense {expense_id} has been deleted"}

# 5. Expense Categories Endpoints

@tool
def create_expense_category(name: str) -> Dict[str, Any]:
    """
    Creates a new expense category.
    
    Arguments:
        name: Name of the category
    
    Returns:
        Created category information
    """
    data = {"name": name}
    return make_api_request("POST", "expense-categories/", data=data)

@tool
def get_expense_category(category_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific expense category.
    
    Arguments:
        category_id: ID of the category
    
    Returns:
        Category details
    """
    return make_api_request("GET", f"expense-categories/{category_id}")

@tool
def list_expense_categories() -> List[Dict[str, Any]]:
    """
    Lists all expense categories for the current user.
    
    Returns:
        List of expense categories
    """
    return make_api_request("GET", "expense-categories/")

@tool
def update_expense_category(category_id: int, name: str) -> Dict[str, Any]:
    """
    Updates an existing expense category.
    
    Arguments:
        category_id: ID of the category to update
        name: New name for the category
    
    Returns:
        Updated category information
    """
    data = {"name": name}
    return make_api_request("PUT", f"expense-categories/{category_id}", data=data)

@tool
def delete_expense_category(category_id: int) -> None:
    """
    Deletes an expense category.
    
    Arguments:
        category_id: ID of the category to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"expense-categories/{category_id}")
    return {"message": f"Expense category {category_id} has been deleted"}

# 6. Investment Endpoints

@tool
def create_investment(name: str, amount: float, investment_type: str, start_date: str,
                     end_date: Optional[str] = None, expected_rate: Optional[float] = None,
                     notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new investment record.
    
    Arguments:
        name: Name of the investment
        amount: Amount invested (must be greater than 0)
        investment_type: Type of investment (e.g., "CDB", "Stocks")
        start_date: Start date of the investment in YYYY-MM-DD format
        end_date: End/maturity date of the investment in YYYY-MM-DD format (optional)
        expected_rate: Expected annual return rate in percentage (optional)
        notes: Additional notes about the investment (optional)
    
    Returns:
        Created investment information
    """
    data = {
        "name": name,
        "amount": amount,
        "investment_type": investment_type,
        "start_date": start_date
    }
    if end_date is not None:
        data["end_date"] = end_date
    if expected_rate is not None:
        data["expected_rate"] = expected_rate
    if notes is not None:
        data["notes"] = notes
    
    return make_api_request("POST", "investments/", data=data)

@tool
def get_investment(investment_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific investment.
    
    Arguments:
        investment_id: ID of the investment
    
    Returns:
        Investment details
    """
    return make_api_request("GET", f"investments/{investment_id}")

@tool
def list_investments(investment_type: Optional[str] = None, skip: int = 0, 
                    limit: int = 100) -> List[Dict[str, Any]]:
    """
    Lists investments with optional filtering.
    
    Arguments:
        investment_type: Filter by investment type (optional)
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
    
    Returns:
        List of investment records
    """
    params = {
        "skip": skip,
        "limit": limit
    }
    if investment_type is not None:
        params["investment_type"] = investment_type
    
    return make_api_request("GET", "investments/", params=params)

@tool
def update_investment(investment_id: int, name: Optional[str] = None, amount: Optional[float] = None,
                     investment_type: Optional[str] = None, start_date: Optional[str] = None,
                     end_date: Optional[str] = None, expected_rate: Optional[float] = None,
                     notes: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing investment.
    
    Arguments:
        investment_id: ID of the investment to update
        name: New name for the investment (optional)
        amount: New amount (optional, must be greater than 0)
        investment_type: New investment type (optional)
        start_date: New start date in YYYY-MM-DD format (optional)
        end_date: New end/maturity date in YYYY-MM-DD format (optional)
        expected_rate: New expected annual return rate (optional)
        notes: New additional notes (optional)
    
    Returns:
        Updated investment information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if amount is not None:
        data["amount"] = amount
    if investment_type is not None:
        data["investment_type"] = investment_type
    if start_date is not None:
        data["start_date"] = start_date
    if end_date is not None:
        data["end_date"] = end_date
    if expected_rate is not None:
        data["expected_rate"] = expected_rate
    if notes is not None:
        data["notes"] = notes
    
    return make_api_request("PUT", f"investments/{investment_id}", data=data)

@tool
def delete_investment(investment_id: int) -> None:
    """
    Deletes an investment.
    
    Arguments:
        investment_id: ID of the investment to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"investments/{investment_id}")
    return {"message": f"Investment {investment_id} has been deleted"}

# 7. Financial Goals Endpoints

@tool
def create_goal(name: str, target_amount: float, current_amount: float = 0.0,
               target_date: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new financial goal.
    
    Arguments:
        name: Name of the goal
        target_amount: Target amount for the goal (must be greater than 0)
        current_amount: Current accumulated amount (default: 0.0)
        target_date: Target date to achieve the goal in YYYY-MM-DD format (optional)
        description: Description of the goal (optional)
    
    Returns:
        Created goal information
    """
    data = {
        "name": name,
        "target_amount": target_amount,
        "current_amount": current_amount
    }
    if target_date is not None:
        data["target_date"] = target_date
    if description is not None:
        data["description"] = description
    
    return make_api_request("POST", "goals/", data=data)

@tool
def get_goal(goal_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific financial goal.
    
    Arguments:
        goal_id: ID of the goal
    
    Returns:
        Goal details
    """
    return make_api_request("GET", f"goals/{goal_id}")

@tool
def list_goals() -> List[Dict[str, Any]]:
    """
    Lists all financial goals for the current user.
    
    Returns:
        List of financial goals
    """
    return make_api_request("GET", "goals/")

@tool
def update_goal(goal_id: int, name: Optional[str] = None, target_amount: Optional[float] = None,
               current_amount: Optional[float] = None, target_date: Optional[str] = None,
               description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing financial goal.
    
    Arguments:
        goal_id: ID of the goal to update
        name: New name for the goal (optional)
        target_amount: New target amount (optional, must be greater than 0)
        current_amount: New current amount (optional)
        target_date: New target date in YYYY-MM-DD format (optional)
        description: New description (optional)
    
    Returns:
        Updated goal information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if target_amount is not None:
        data["target_amount"] = target_amount
    if current_amount is not None:
        data["current_amount"] = current_amount
    if target_date is not None:
        data["target_date"] = target_date
    if description is not None:
        data["description"] = description
    
    return make_api_request("PUT", f"goals/{goal_id}", data=data)

@tool
def delete_goal(goal_id: int) -> None:
    """
    Deletes a financial goal.
    
    Arguments:
        goal_id: ID of the goal to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"goals/{goal_id}")
    return {"message": f"Goal {goal_id} has been deleted"}

# 8. Income Endpoints

@tool
def create_income(amount: float, date: str, source: str, description: Optional[str] = None,
                 is_recurring: bool = False) -> Dict[str, Any]:
    """
    Creates a new income record.
    
    Arguments:
        amount: Amount of the income (must be greater than 0)
        date: Date of the income in YYYY-MM-DD format
        source: Source of the income (e.g., "Salary", "Freelance")
        description: Description of the income (optional)
        is_recurring: Whether this is a recurring income (default: False)
    
    Returns:
        Created income information
    """
    data = {
        "amount": amount,
        "date": date,
        "source": source,
        "is_recurring": is_recurring
    }
    if description is not None:
        data["description"] = description
    
    return make_api_request("POST", "incomes/", data=data)

@tool
def get_income(income_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific income.
    
    Arguments:
        income_id: ID of the income
    
    Returns:
        Income details
    """
    return make_api_request("GET", f"incomes/{income_id}")

@tool
def list_incomes(source: Optional[str] = None, start_date: Optional[str] = None,
                end_date: Optional[str] = None, is_recurring: Optional[bool] = None,
                skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Lists incomes with optional filtering.
    
    Arguments:
        source: Filter by source (optional)
        start_date: Start date filter in YYYY-MM-DD format (optional)
        end_date: End date filter in YYYY-MM-DD format (optional)
        is_recurring: Filter only recurring incomes (optional)
        skip: Number of records to skip (default: 0)
        limit: Maximum number of records to return (default: 100)
    
    Returns:
        List of income records
    """
    params = {
        "skip": skip,
        "limit": limit
    }
    if source is not None:
        params["source"] = source
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    if is_recurring is not None:
        params["is_recurring"] = str(is_recurring).lower()
    
    return make_api_request("GET", "incomes/", params=params)

@tool
def update_income(income_id: int, amount: Optional[float] = None, date: Optional[str] = None,
                 source: Optional[str] = None, description: Optional[str] = None,
                 is_recurring: Optional[bool] = None) -> Dict[str, Any]:
    """
    Updates an existing income.
    
    Arguments:
        income_id: ID of the income to update
        amount: New amount (optional, must be greater than 0)
        date: New date in YYYY-MM-DD format (optional)
        source: New source (optional)
        description: New description (optional)
        is_recurring: Update recurring status (optional)
    
    Returns:
        Updated income information
    """
    data = {}
    if amount is not None:
        data["amount"] = amount
    if date is not None:
        data["date"] = date
    if source is not None:
        data["source"] = source
    if description is not None:
        data["description"] = description
    if is_recurring is not None:
        data["is_recurring"] = is_recurring
    
    return make_api_request("PUT", f"incomes/{income_id}", data=data)

@tool
def delete_income(income_id: int) -> None:
    """
    Deletes an income.
    
    Arguments:
        income_id: ID of the income to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"incomes/{income_id}")
    return {"message": f"Income {income_id} has been deleted"}

# 9. Reports Endpoints

@tool
def get_expenses_by_category(start_date: Optional[str] = None, end_date: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Gets a report of expenses grouped by category.
    
    Arguments:
        start_date: Start date for the report in YYYY-MM-DD format (optional)
        end_date: End date for the report in YYYY-MM-DD format (optional)
    
    Returns:
        List of expense categories with amounts and percentages
    """
    params = {}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    
    return make_api_request("GET", "reports/expenses-by-category", params=params)

@tool
def get_expenses_by_month(year: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Gets a report of expenses grouped by month.
    
    Arguments:
        year: Year for the report (optional, defaults to current year)
    
    Returns:
        List of monthly expense totals
    """
    params = {}
    if year is not None:
        params["year"] = year
    
    return make_api_request("GET", "reports/expenses-by-month", params=params)

@tool
def get_cashflow(start_date: Optional[str] = None, end_date: Optional[str] = None,
                group_by: str = "month") -> List[Dict[str, Any]]:
    """
    Gets a cash flow report (income vs expenses).
    
    Arguments:
        start_date: Start date for the report in YYYY-MM-DD format (optional)
        end_date: End date for the report in YYYY-MM-DD format (optional)
        group_by: Grouping period - "day", "month", or "year" (default: "month")
    
    Returns:
        List of periods with income, expense, and balance information
    """
    params = {"group_by": group_by}
    if start_date is not None:
        params["start_date"] = start_date
    if end_date is not None:
        params["end_date"] = end_date
    
    return make_api_request("GET", "reports/cashflow", params=params)

# 10. Analysis Endpoints

@tool
def get_financial_summary() -> Dict[str, Any]:
    """
    Gets a summary of the current financial situation.
    
    Returns:
        Summary of financial status including balance, income, expenses, savings, investments, and goals
    """
    return make_api_request("GET", "analysis/summary")

@tool
def get_financial_trends(months: int = 6) -> Dict[str, Any]:
    """
    Gets financial trend analysis over time.
    
    Arguments:
        months: Number of months to analyze (default: 6)
    
    Returns:
        Financial trends including income, expenses, and savings over time
    """
    params = {"months": months}
    return make_api_request("GET", "analysis/trends", params=params)

# 11. Chat Endpoints

@tool
def send_chat_message(user_id: str, message: str, session_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Sends a message to the finance assistant.
    
    Arguments:
        user_id: Unique ID of the user
        message: User's message
        session_id: ID of the conversation session (optional)
    
    Returns:
        Response from the assistant
    """
    data = {
        "user_id": user_id,
        "message": message
    }
    if session_id is not None:
        data["session_id"] = session_id
    
    return make_api_request("POST", "chat", data=data)

@tool
def get_session_state(session_id: str) -> Dict[str, Any]:
    """
    Gets the current state of a chat session.
    
    Arguments:
        session_id: ID of the conversation session
    
    Returns:
        Current state of the conversation
    """
    return make_api_request("GET", f"sessions/{session_id}/state")

@tool
def reset_session(session_id: str) -> None:
    """
    Resets/restarts a chat session.
    
    Arguments:
        session_id: ID of the conversation session to reset
    
    Returns:
        None
    """
    make_api_request("DELETE", f"sessions/{session_id}")
    return {"message": f"Session {session_id} has been reset"}

# 12. Kanban Project Endpoints

@tool
def create_project(name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new project for the kanban system.
    
    Arguments:
        name: Name of the project
        description: Description of the project (optional)
    
    Returns:
        Created project information
    """
    data = {"name": name}
    if description is not None:
        data["description"] = description
    
    return make_api_request("POST", "projects/", data=data)

@tool
def get_project(project_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific project.
    
    Arguments:
        project_id: ID of the project
    
    Returns:
        Project details
    """
    return make_api_request("GET", f"projects/{project_id}")

@tool
def list_projects() -> List[Dict[str, Any]]:
    """
    Lists all projects for the current user.
    
    Returns:
        List of projects
    """
    return make_api_request("GET", "projects/")

@tool
def update_project(project_id: int, name: Optional[str] = None, 
                  description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing project.
    
    Arguments:
        project_id: ID of the project to update
        name: New name for the project (optional)
        description: New description (optional)
    
    Returns:
        Updated project information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    
    return make_api_request("PUT", f"projects/{project_id}", data=data)

@tool
def delete_project(project_id: int) -> None:
    """
    Deletes a project.
    
    Arguments:
        project_id: ID of the project to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"projects/{project_id}")
    return {"message": f"Project {project_id} has been deleted"}

# 13. Kanban Board Endpoints

@tool
def create_board(project_id: int, name: str, description: Optional[str] = None) -> Dict[str, Any]:
    """
    Creates a new board within a project.
    
    Arguments:
        project_id: ID of the project the board belongs to
        name: Name of the board
        description: Description of the board (optional)
    
    Returns:
        Created board information
    """
    data = {
        "project_id": project_id,
        "name": name
    }
    if description is not None:
        data["description"] = description
    
    return make_api_request("POST", "boards/", data=data)

@tool
def get_board(board_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific board.
    
    Arguments:
        board_id: ID of the board
    
    Returns:
        Board details
    """
    return make_api_request("GET", f"boards/{board_id}")

@tool
def list_boards(project_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lists boards with optional filtering by project.
    
    Arguments:
        project_id: Filter boards by project (optional)
    
    Returns:
        List of boards
    """
    params = {}
    if project_id is not None:
        params["project_id"] = project_id
    
    return make_api_request("GET", "boards/", params=params)

@tool
def update_board(board_id: int, name: Optional[str] = None, 
                description: Optional[str] = None) -> Dict[str, Any]:
    """
    Updates an existing board.
    
    Arguments:
        board_id: ID of the board to update
        name: New name for the board (optional)
        description: New description (optional)
    
    Returns:
        Updated board information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if description is not None:
        data["description"] = description
    
    return make_api_request("PUT", f"boards/{board_id}", data=data)

@tool
def delete_board(board_id: int) -> None:
    """
    Deletes a board.
    
    Arguments:
        board_id: ID of the board to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"boards/{board_id}")
    return {"message": f"Board {board_id} has been deleted"}

# 14. Kanban Column Endpoints

@tool
def create_column(board_id: int, name: str, position: Optional[int] = None) -> Dict[str, Any]:
    """
    Creates a new column in a board.
    
    Arguments:
        board_id: ID of the board the column belongs to
        name: Name of the column
        position: Position of the column in the board (optional)
    
    Returns:
        Created column information
    """
    data = {
        "board_id": board_id,
        "name": name
    }
    if position is not None:
        data["position"] = position
    
    return make_api_request("POST", "columns/", data=data)

@tool
def get_column(column_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific column.
    
    Arguments:
        column_id: ID of the column
    
    Returns:
        Column details
    """
    return make_api_request("GET", f"columns/{column_id}")

@tool
def list_columns(board_id: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lists columns with optional filtering by board.
    
    Arguments:
        board_id: Filter columns by board (optional)
    
    Returns:
        List of columns
    """
    params = {}
    if board_id is not None:
        params["board_id"] = board_id
    
    return make_api_request("GET", "columns/", params=params)

@tool
def update_column(column_id: int, name: Optional[str] = None, 
                 position: Optional[int] = None) -> Dict[str, Any]:
    """
    Updates an existing column.
    
    Arguments:
        column_id: ID of the column to update
        name: New name for the column (optional)
        position: New position (optional)
    
    Returns:
        Updated column information
    """
    data = {}
    if name is not None:
        data["name"] = name
    if position is not None:
        data["position"] = position
    
    return make_api_request("PUT", f"columns/{column_id}", data=data)

@tool
def delete_column(column_id: int) -> None:
    """
    Deletes a column.
    
    Arguments:
        column_id: ID of the column to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"columns/{column_id}")
    return {"message": f"Column {column_id} has been deleted"}

# 15. Kanban Task Endpoints

@tool
def create_task(column_id: int, title: str, description: Optional[str] = None,
               due_date: Optional[str] = None, priority: Optional[int] = None,
               position: Optional[int] = None) -> Dict[str, Any]:
    """
    Creates a new task in a column.
    
    Arguments:
        column_id: ID of the column the task belongs to
        title: Title of the task
        description: Description of the task (optional)
        due_date: Due date in YYYY-MM-DD format (optional)
        priority: Priority level 1-5 (optional)
        position: Position of the task in the column (optional)
    
    Returns:
        Created task information
    """
    data = {
        "column_id": column_id,
        "title": title
    }
    if description is not None:
        data["description"] = description
    if due_date is not None:
        data["due_date"] = due_date
    if priority is not None:
        data["priority"] = priority
    if position is not None:
        data["position"] = position
    
    return make_api_request("POST", "tasks/", data=data)

@tool
def get_task(task_id: int) -> Dict[str, Any]:
    """
    Retrieves information about a specific task.
    
    Arguments:
        task_id: ID of the task
    
    Returns:
        Task details
    """
    return make_api_request("GET", f"tasks/{task_id}")

@tool
def list_tasks(column_id: Optional[int] = None, board_id: Optional[int] = None,
              priority: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Lists tasks with optional filtering.
    
    Arguments:
        column_id: Filter tasks by column (optional)
        board_id: Filter tasks by board (optional)
        priority: Filter by priority level (optional)
    
    Returns:
        List of tasks
    """
    params = {}
    if column_id is not None:
        params["column_id"] = column_id
    if board_id is not None:
        params["board_id"] = board_id
    if priority is not None:
        params["priority"] = priority
    
    return make_api_request("GET", "tasks/", params=params)

@tool
def update_task(task_id: int, column_id: Optional[int] = None, title: Optional[str] = None,
               description: Optional[str] = None, due_date: Optional[str] = None,
               priority: Optional[int] = None, position: Optional[int] = None) -> Dict[str, Any]:
    """
    Updates an existing task.
    
    Arguments:
        task_id: ID of the task to update
        column_id: New column ID (optional, used to move task between columns)
        title: New title (optional)
        description: New description (optional)
        due_date: New due date in YYYY-MM-DD format (optional)
        priority: New priority level 1-5 (optional)
        position: New position (optional)
    
    Returns:
        Updated task information
    """
    data = {}
    if column_id is not None:
        data["column_id"] = column_id
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if due_date is not None:
        data["due_date"] = due_date
    if priority is not None:
        data["priority"] = priority
    if position is not None:
        data["position"] = position
    
    return make_api_request("PUT", f"tasks/{task_id}", data=data)

@tool
def delete_task(task_id: int) -> None:
    """
    Deletes a task.
    
    Arguments:
        task_id: ID of the task to delete
    
    Returns:
        None
    """
    make_api_request("DELETE", f"tasks/{task_id}")
    return {"message": f"Task {task_id} has been deleted"}
