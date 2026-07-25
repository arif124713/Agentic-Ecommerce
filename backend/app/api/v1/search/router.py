from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.repositories.search import SearchRepository
from app.schemas.search import SearchSuggestOut, SuggestBrandOut, SuggestCategoryOut, SuggestProductOut

router = APIRouter(prefix="/search", tags=["search"])


@router.get("/suggest", response_model=SearchSuggestOut)
async def suggest(q: str = Query(min_length=1, max_length=100), db: AsyncSession = Depends(get_db)):
    repo = SearchRepository(db)
    products = await repo.suggest_products(q)
    brands = await repo.suggest_brands(q)
    categories = await repo.suggest_categories(q)
    popular = await repo.popular_queries(q)
    return SearchSuggestOut(
        products=[SuggestProductOut.model_validate(p) for p in products],
        brands=[SuggestBrandOut.model_validate(b) for b in brands],
        categories=[SuggestCategoryOut.model_validate(c) for c in categories],
        popular_queries=popular,
    )
