"""Leitura do banco com queries parametrizadas (No Cache)."""

from emporio.repositories.catalog import CatalogRepository, Category, Product, Promotion
from emporio.repositories.customers import Customer, CustomerRepository
from emporio.repositories.orders import Order, OrderItem, OrderRepository
from emporio.repositories.tickets import Ticket, TicketRepository

__all__ = [
    "CatalogRepository",
    "Category",
    "Customer",
    "CustomerRepository",
    "Order",
    "OrderItem",
    "OrderRepository",
    "Product",
    "Promotion",
    "Ticket",
    "TicketRepository",
]
