"""Seed color_palettes / climate_profiles / destination_aliases — the deterministic reference
fixtures chat_spec.md §4.1 requires `get_color_palette` and `get_climate_profile` to read from,
never invent. color_palettes is exactly spec §4.1's seed table (six depths, undertone="unknown" —
the table doesn't provide separate warm/cool rows, only a rationale note that undertone layers a
bias on top later). climate_profiles covers a small, real spread of Bangladeshi destinations
rather than just the one worked example, so the relaxation ladder and destination-alias resolution
have more than a single row to exercise. Run: python scripts/seed_styling_reference.py
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select  # noqa: E402

from app.db.session import AsyncSessionLocal  # noqa: E402
from app.models.styling import ClimateProfile, ColorPalette, DestinationAlias  # noqa: E402

COLOR_PALETTES = [
    {
        "depth": "fair",
        "recommended": ["navy", "dusty-rose", "soft-teal", "burgundy", "charcoal"],
        "de_emphasized": ["neon-yellow", "optic-white"],
        "rationale": (
            "Fair complexions read best against colors with enough depth to create contrast "
            "without overwhelming — navy and burgundy anchor an outfit, while high-shine neon "
            "and stark white can wash out the same contrast they're meant to create."
        ),
    },
    {
        "depth": "light",
        "recommended": ["forest", "plum", "denim-blue", "terracotta"],
        "de_emphasized": ["pale-beige", "washed-yellow"],
        "rationale": (
            "Light complexions carry richer, slightly muted tones well — forest and plum add "
            "depth, while pale, low-saturation neutrals sit too close to skin tone to register."
        ),
    },
    {
        "depth": "medium",
        "recommended": ["olive", "rust", "teal", "cream", "warm-red"],
        "de_emphasized": ["grey-beige"],
        "rationale": (
            "Medium complexions have room for both warmth and saturation — olive and rust read "
            "as intentional, while flat grey-beige tends to blend rather than contrast."
        ),
    },
    {
        "depth": "tan",
        "recommended": ["ivory", "cobalt", "emerald", "coral", "camel"],
        "de_emphasized": ["muddy-brown"],
        "rationale": (
            "Tan complexions hold bright, saturated color exceptionally well — cobalt and "
            "emerald pop with real contrast, while muddy, low-saturation browns flatten it."
        ),
    },
    {
        "depth": "deep",
        "recommended": [
            "cobalt", "emerald", "fuchsia", "mustard", "optic-white", "coral", "turquoise",
        ],
        "de_emphasized": ["mocha", "taupe", "muted-mauve"],
        "rationale": (
            "Deep complexions carry high-saturation and high-contrast colors exceptionally "
            "well; bright jewel tones and optic white maximize contrast, while colors sitting "
            "at a similar depth-and-muteness as the skin tend to read flat."
        ),
    },
    {
        "depth": "rich-deep",
        "recommended": ["optic-white", "electric-blue", "hot-pink", "lime", "gold", "scarlet"],
        "de_emphasized": ["deep-charcoal-brown", "dark-olive"],
        "rationale": (
            "Rich-deep complexions hold the very highest end of brightness and saturation with "
            "striking contrast — optic white and electric blue read vividly, while colors "
            "close to the skin's own depth disappear into it."
        ),
    },
]

CLIMATE_PROFILES = [
    {
        "slug": "coxs-bazar-bd",
        "display_name": "Cox's Bazar",
        "lat": Decimal("21.427200"),
        "lon": Decimal("92.005800"),
        "climate": "hot-humid",
        "terrain": ["beach", "coastal"],
        "typical_occasions": ["beach", "casual", "travel"],
        "suggested_categories": [
            "linen-shirt", "cotton-tee", "shorts", "swimwear", "kaftan", "sarong",
            "sandals", "sunglasses", "sun-hat", "beach-tote",
        ],
        "suggested_fabrics": ["linen", "cotton", "rayon", "viscose", "quick-dry"],
        "avoid_fabrics": ["wool", "heavy-denim", "leather", "velvet"],
        "visual_character": (
            "The world's longest natural sea beach — a wide, flat stretch of pale sand running "
            "for miles against a hazy grey-blue Bay of Bengal horizon, red-and-yellow lifeguard "
            "flags, wooden fishing boats pulled up on the shore, and a boardwalk lined with "
            "beach shacks and tourist stalls. Photos here read as wide open sky and water — "
            "saturated color on a person is what actually stands out against it, not white."
        ),
        "style_notes": (
            "Beach-resort casual is the norm, not activewear. Swimwear belongs on the beach "
            "itself; walking the boardwalk or eating out calls for a light cover-up — sarongs, "
            "kaftans, and loose shirts are the local uniform for exactly that reason, not just "
            "sun protection. Bangladesh is conservative outside the beach itself, so modest cuts "
            "(covered shoulders, longer hemlines) read as put-together rather than restrictive. "
            "Bright vacation color is expected and welcomed here — this is the one place a loud "
            "print or a saturated hue doesn't compete for attention with a dressed-up city crowd."
        ),
        "aliases": ["coxs bazar", "cox's bazar", "coxsbazar", "cox bazar", "কক্সবাজার"],
    },
    {
        "slug": "dhaka-bd",
        "display_name": "Dhaka",
        "lat": Decimal("23.810300"),
        "lon": Decimal("90.412500"),
        "climate": "hot-humid",
        "terrain": ["urban"],
        "typical_occasions": ["casual", "office", "party", "festive"],
        "suggested_categories": [
            "cotton-tee", "linen-shirt", "kurta", "chinos", "sneakers", "sandals",
        ],
        "suggested_fabrics": ["cotton", "linen", "viscose"],
        "avoid_fabrics": ["wool", "velvet"],
        "visual_character": (
            "Dense, fast-moving megacity — rickshaws and traffic, concrete and glass storefronts, "
            "narrow old-town lanes giving way to wide commercial boulevards. There's no single "
            "backdrop here; the city itself is the context, and what reads as stylish shifts "
            "block to block between office districts, university areas, and old Dhaka markets."
        ),
        "style_notes": (
            "Dhaka runs on quick outfit changes across one day — commute, office, evening out — "
            "so pieces that go from desk-appropriate to after-hours without a full change read as "
            "genuinely useful here, not just stylish. Office wear leans smart-casual rather than "
            "suited-up for most workplaces. Festive/ethnic wear (kurtas, panjabis) is completely "
            "normal daywear, not costume, especially around Fridays and any holiday. Modesty norms "
            "are moderate — arms and legs bared is fine in most social settings, sleeveless less "
            "so in traditional or older-generation company."
        ),
        "aliases": ["dhaka", "ঢাকা"],
    },
    {
        "slug": "sylhet-bd",
        "display_name": "Sylhet",
        "lat": Decimal("24.894200"),
        "lon": Decimal("91.868000"),
        "climate": "rainy",
        "terrain": ["hills", "tea-garden"],
        "typical_occasions": ["travel", "casual", "festive"],
        "suggested_categories": [
            "rain-jacket", "quick-dry-tee", "trekking-pants", "cotton-tee", "sandals",
        ],
        "suggested_fabrics": ["quick-dry", "cotton", "nylon"],
        "avoid_fabrics": ["suede", "velvet"],
        "visual_character": (
            "Rolling tea gardens in deep, layered green, mist sitting low over the hills most "
            "mornings, stone steps and narrow paths through the estates, rivers running clear "
            "over rock beds. Muted, natural, matte — the landscape itself is the color story, so "
            "clothing that echoes or plays against that green (rather than fighting it with "
            "neon) is what actually photographs and feels right here."
        ),
        "style_notes": (
            "Functional-first without giving up on looking put-together — this is a walking, "
            "hill-climbing, rain-dodging destination, so trekking-capable pieces that still look "
            "considered (not head-to-toe technical gear) read best. Sylhet is more traditionally "
            "conservative than Dhaka or the beach towns; modest coverage is the comfortable "
            "default in the tea-garden villages and rural areas outside the city itself."
        ),
        "aliases": ["sylhet", "সিলেট"],
    },
    {
        "slug": "bandarban-bd",
        "display_name": "Bandarban",
        "lat": Decimal("22.195600"),
        "lon": Decimal("92.218500"),
        "climate": "cool",
        "terrain": ["hills", "forest"],
        "typical_occasions": ["travel", "casual"],
        "suggested_categories": [
            "trekking-pants", "light-jacket", "cotton-tee", "sneakers", "cap",
        ],
        "suggested_fabrics": ["cotton", "fleece", "nylon"],
        "avoid_fabrics": ["silk", "velvet"],
        "visual_character": (
            "Deep-forested hill tracts, terraced ridgelines fading into blue haze at a distance, "
            "suspension footbridges over ravines, and indigenous Marma/Bawm/Chakma villages with "
            "their own distinct woven-textile traditions. The most dramatic terrain in the "
            "country — earthy, cool-toned, and genuinely remote in feel."
        ),
        "style_notes": (
            "This is the one destination where the trip itself demands real trekking-capable "
            "clothing, not just travel-casual — layering for temperature swings between sun and "
            "shade, durable fabric for rough trails. It's also home to several indigenous "
            "communities with their own textile and dress traditions worth being respectful "
            "toward rather than imitating as a costume. Earthy, muted tones read as intentional "
            "here against the forest backdrop; very bright synthetic color tends to look out of "
            "place rather than striking."
        ),
        "aliases": ["bandarban", "বান্দরবান"],
    },
]


async def main() -> None:
    async with AsyncSessionLocal() as session:
        existing_palettes = (await session.execute(select(ColorPalette.depth))).scalars().all()
        if existing_palettes:
            print(f"color_palettes already seeded ({len(existing_palettes)} rows) — skipping.")
        else:
            for row in COLOR_PALETTES:
                session.add(ColorPalette(undertone="unknown", version=1, **row))
            print(f"Inserted {len(COLOR_PALETTES)} color_palettes rows.")

        # Upsert by slug (not the earlier insert-only-if-empty logic) — this table's own rows
        # were revised in place at least once already (visual_character/style_notes added after
        # the first seed run), and simply skipping when non-empty would leave those fields null
        # on whatever was seeded before this script last changed.
        inserted, updated = 0, 0
        for row in CLIMATE_PROFILES:
            row = dict(row)
            aliases = row.pop("aliases")
            existing = (
                await session.execute(select(ClimateProfile).where(ClimateProfile.slug == row["slug"]))
            ).scalar_one_or_none()
            if existing:
                for key, value in row.items():
                    setattr(existing, key, value)
                updated += 1
            else:
                profile = ClimateProfile(**row)
                session.add(profile)
                await session.flush()  # need profile.id for the alias rows below
                for alias in aliases:
                    session.add(DestinationAlias(alias=alias, climate_profile_id=profile.id))
                inserted += 1
        print(f"climate_profiles: inserted {inserted}, updated {updated}.")

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
