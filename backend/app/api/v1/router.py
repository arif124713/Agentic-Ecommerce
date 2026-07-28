from fastapi import APIRouter

from app.api.v1.account import addresses
from app.api.v1.account import support as account_support
from app.api.v1.admin import catalog as admin_catalog
from app.api.v1.admin import cms as admin_cms
from app.api.v1.admin import coupons as admin_coupons
from app.api.v1.admin import dashboard as admin_dashboard
from app.api.v1.admin import orders as admin_orders
from app.api.v1.admin import reviews as admin_reviews
from app.api.v1.admin import support as admin_support
from app.api.v1.admin import users as admin_users
from app.api.v1.auth import router as auth
from app.api.v1.cart import router as cart
from app.api.v1.discovery import router as discovery
from app.api.v1.orders import router as orders
from app.api.v1.public import catalog
from app.api.v1.public import cms
from app.api.v1.public import reviews
from app.api.v1.search import router as search
from app.api.v1 import security

api_router = APIRouter()
api_router.include_router(catalog.router)
api_router.include_router(cms.router)
api_router.include_router(reviews.router)
api_router.include_router(search.router)
api_router.include_router(discovery.router)
api_router.include_router(security.router)
api_router.include_router(auth.router)
api_router.include_router(cart.router)
api_router.include_router(addresses.router)
api_router.include_router(account_support.router)
api_router.include_router(orders.router)
api_router.include_router(admin_catalog.router)
api_router.include_router(admin_orders.router)
api_router.include_router(admin_users.router)
api_router.include_router(admin_coupons.router)
api_router.include_router(admin_dashboard.router)
api_router.include_router(admin_reviews.router)
api_router.include_router(admin_cms.router)
api_router.include_router(admin_support.router)
