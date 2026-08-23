import decimal

from sqlalchemy import (
    DECIMAL,
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ColorPalette(Base):
    """chat_spec.md §4.1's `get_color_palette` seed table — a deterministic depth x undertone
    lookup, never model-invented (spec §9.4: skin tone handling must be descriptive, not
    evaluative, and this table is what makes that enforceable rather than aspirational). Seeded
    from the versioned fixture in spec §4.1 §222-232; `version` lets a future re-tuning of the
    palette be audited without losing the row history of what shipped when."""

    __tablename__ = "color_palettes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    depth: Mapped[str] = mapped_column(String(20), nullable=False)
    undertone: Mapped[str] = mapped_column(String(10), default="unknown", nullable=False)
    recommended: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    de_emphasized: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)

    __table_args__ = (
        CheckConstraint(
            "depth IN ('fair','light','medium','tan','deep','rich-deep')", name="ck_color_palettes_depth"
        ),
        CheckConstraint(
            "undertone IN ('warm','cool','neutral','unknown')", name="ck_color_palettes_undertone"
        ),
        UniqueConstraint("depth", "undertone", name="uq_color_palettes_depth_undertone"),
    )


class ClimateProfile(Base):
    """chat_spec.md §4.1's `get_climate_profile` reference table. `slug` is the lookup key (e.g.
    `coxs-bazar-bd`) rather than the PK, matching this project's existing slug convention
    (`Brand.slug`, `Category.slug`) rather than spec's literal `slug PK` — an int surrogate PK is
    what every other table in this codebase does, and `destination_aliases` FKs to it either way."""

    __tablename__ = "climate_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(140), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(120), nullable=False)
    lat: Mapped[decimal.Decimal] = mapped_column(DECIMAL(9, 6), nullable=False)
    lon: Mapped[decimal.Decimal] = mapped_column(DECIMAL(9, 6), nullable=False)
    climate: Mapped[str] = mapped_column(String(20), nullable=False)
    terrain: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    typical_occasions: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    suggested_categories: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    suggested_fabrics: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    avoid_fabrics: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    # The two fields that make the Stylist reason like an actual stylist instead of a weather
    # report with products attached: what the place actually LOOKS like (the backdrop a photo or
    # an outfit reads against) and what's culturally/socially the norm to wear there. Both free
    # text because they're meant to be read by the prose-writing LLM call, not filtered on.
    visual_character: Mapped[str | None] = mapped_column(Text, nullable=True)
    style_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "climate IN ('hot-humid','hot-dry','temperate','cool','cold','rainy')",
            name="ck_climate_profiles_climate",
        ),
    )


class DestinationAlias(Base):
    """chat_spec.md §4.1's `destination_aliases` — free-text destination input ('coxsbazar',
    'cox bazar', Bangla spellings) resolved to a `ClimateProfile` before geocoding fallback.
    `alias` is stored lower-cased/normalized by the slot extractor before insert/lookup, not
    enforced here (no portable case-insensitive-unique across the DBs this project might run on)."""

    __tablename__ = "destination_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    climate_profile_id: Mapped[int] = mapped_column(
        ForeignKey("climate_profiles.id", ondelete="RESTRICT"), nullable=False
    )

    __table_args__ = (Index("ix_destination_aliases_profile", "climate_profile_id"),)
