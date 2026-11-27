"""
Schema do banco (SQLAlchemy Core).

Dinheiro em centavos inteiros.

"""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    Table,
    Text,
    text,
)

from emporio.db.rows import PAYMENT_METHODS, STATUSES_WITHOUT_SHIPPING


def _in(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


metadata = MetaData()

categories = Table(
    "categories",
    metadata,
    Column("category_id", Integer, primary_key=True, autoincrement=False),
    Column("name", Text, nullable=False, unique=True),
    Column("description", Text),
)

customers = Table(
    "customers",
    metadata,
    Column("customer_id", Integer, primary_key=True, autoincrement=False),
    Column("name", Text, nullable=False),
    Column("phone", Text, nullable=False, unique=True),
    # Identidade do cliente: dígitos nacionais (DDD + número)
    Column("phone_digits", Text, nullable=False, unique=True),
    # Deliberadamente não único: clientes 11 e 43 compartilham o mesmo e-mail
    Column("email", Text, nullable=False),
    Column("city", Text, nullable=False),
)

products = Table(
    "products",
    metadata,
    Column("product_id", Integer, primary_key=True, autoincrement=False),
    Column("category_id", Integer, ForeignKey("categories.category_id"), nullable=False),
    Column("name", Text, nullable=False),
    Column("description", Text),
    Column("price_cents", Integer, nullable=False),
    Column("stock_quantity", Integer, nullable=False),
    Column("status", Text, nullable=False),
    Column("specs_json", Text, nullable=False),
    Column("created_at", Date, nullable=False),
    # Derivadas
    Column("strings_type", Text),
    Column("string_count", Integer),
    Column("is_electric", Boolean(create_constraint=False)),
    Column("normalized_name", Text, nullable=False),
    Column(
        "cadastro_inconsistente",
        Boolean(create_constraint=False),
        nullable=False,
        server_default=text("0"),
    ),
    CheckConstraint("price_cents > 0", name="ck_products_price"),
    CheckConstraint("stock_quantity >= 0", name="ck_products_stock"),
    CheckConstraint(
        _in("status", ("active", "discontinued", "coming_soon")), name="ck_products_status"
    ),
    CheckConstraint(
        "strings_type IS NULL OR strings_type IN ('nylon', 'steel')",
        name="ck_products_strings_type",
    ),
    CheckConstraint("is_electric IS NULL OR is_electric IN (0, 1)", name="ck_products_electric"),
    CheckConstraint("cadastro_inconsistente IN (0, 1)", name="ck_products_inconsistente"),
)
Index("ix_products_category_id", products.c.category_id)
Index("ix_products_status_stock", products.c.status, products.c.stock_quantity)
Index("ix_products_price_cents", products.c.price_cents)

promotions = Table(
    "promotions",
    metadata,
    Column("promotion_id", Integer, primary_key=True, autoincrement=False),
    Column("product_id", Integer, ForeignKey("products.product_id"), nullable=False),
    Column("discount_percent", Integer, nullable=False),
    Column("description", Text),
    Column("is_active", Boolean(create_constraint=False), nullable=False),
    CheckConstraint("discount_percent BETWEEN 1 AND 99", name="ck_promotions_discount"),
    CheckConstraint("is_active IN (0, 1)", name="ck_promotions_active"),
)

# No máximo uma promoção ativa por produto
Index(
    "uq_promotions_active_product",
    promotions.c.product_id,
    unique=True,
    sqlite_where=promotions.c.is_active == 1,
    postgresql_where=promotions.c.is_active.is_(True),
)

orders = Table(
    "orders",
    metadata,
    Column("order_id", Integer, primary_key=True, autoincrement=False),
    Column("customer_id", Integer, ForeignKey("customers.customer_id"), nullable=False),
    Column("order_date", Date, nullable=False),
    Column("status", Text, nullable=False),
    Column("total_cents", Integer, nullable=False),
    Column("payment_method", Text, nullable=False),
    # Derivada de payment_method: NULL para PIX/boleto, 1 para débito, n para crédito em n parcelas
    Column("installments", Integer),
    Column("tracking_code", Text),
    Column("estimated_delivery", Date),
    Column("notes", Text),
    CheckConstraint(
        _in("status", ("pending", "confirmed", "shipped", "delivered", "cancelled")),
        name="ck_orders_status",
    ),
    CheckConstraint("total_cents > 0", name="ck_orders_total"),
    CheckConstraint(_in("payment_method", PAYMENT_METHODS), name="ck_orders_payment_method"),
    CheckConstraint(
        "installments IS NULL OR installments BETWEEN 1 AND 12", name="ck_orders_installments"
    ),
    # Rastreio e previsão só podem faltar antes do envio ou no cancelamento
    CheckConstraint(
        f"{_in('status', STATUSES_WITHOUT_SHIPPING)} "
        "OR (tracking_code IS NOT NULL AND estimated_delivery IS NOT NULL)",
        name="ck_orders_shipping_fields",
    ),
    CheckConstraint(
        "estimated_delivery IS NULL OR estimated_delivery >= order_date",
        name="ck_orders_estimate_after_order",
    ),
)
Index("ix_orders_customer_id", orders.c.customer_id)

order_items = Table(
    "order_items",
    metadata,
    Column("order_id", Integer, ForeignKey("orders.order_id"), nullable=False),
    Column("product_id", Integer, ForeignKey("products.product_id"), nullable=False),
    Column("quantity", Integer, nullable=False),
    PrimaryKeyConstraint("order_id", "product_id"),
    CheckConstraint("quantity > 0", name="ck_order_items_quantity"),
)

CSV_TABLES: tuple[Table, ...] = (categories, customers, products, promotions, orders, order_items)
