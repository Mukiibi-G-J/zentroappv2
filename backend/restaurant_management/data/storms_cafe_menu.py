"""
The Storms Cafe menu catalog for seed_storms_cafe_menu.

Source: printed / digital menus provided by client (breakfast, lunch, burgers,
soups, local foods, pastas, sandwiches, juices).
Prices in UGX. Names lightly normalized for POS readability; phonetic originals
kept in descriptions where useful.
"""

from __future__ import annotations

RESTAURANT = {
    "name": "The Storms Cafe",
    "tagline": "Delicious Food Service",
    "location": "Uganda",
    "phones": ["+256 794 542 684"],
}

MENU = {
    "name": "The Storms Cafe Full Menu",
    "code": "TSC-MAIN",
    "is_active": True,
}

ITEM_CATEGORY = {
    "code": "FOOD",
    "description": "FOOD & BEVERAGE",
}

UNIT_OF_MEASURE = "PCS"


def _item(
    name: str,
    price: int,
    *,
    description: str = "",
    routes_to_kitchen: bool | None = None,
    dietary_info: list[str] | None = None,
    is_featured: bool = False,
    preparation_time: int = 15,
):
    return {
        "item_name": name,
        "unit_price": price,
        "description": description,
        "type": "Service",
        "routes_to_kitchen": routes_to_kitchen,
        "dietary_info": dietary_info or [],
        "is_featured": is_featured,
        "preparation_time": preparation_time,
    }


CATEGORIES: list[dict] = [
    {
        "name": "Breakfast Teas",
        "description": "Hot teas — breakfast menu.",
        "display_order": 10,
        "routes_to_kitchen": False,
        "display_group": "Breakfast",
        "items": [
            _item("African Tea", 6000, routes_to_kitchen=False, preparation_time=5),
            _item("Black Tea", 4000, routes_to_kitchen=False, preparation_time=5),
            _item("Indian Tea", 10000, routes_to_kitchen=False, preparation_time=5),
            _item("English Tea", 10000, routes_to_kitchen=False, preparation_time=5),
            _item("Dawa Tea", 13000, routes_to_kitchen=False, preparation_time=8),
        ],
    },
    {
        "name": "Breakfast Samosas",
        "description": "Samosas — priced per piece.",
        "display_order": 11,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Veg Samosa", 1000, description="Per piece", preparation_time=8),
            _item("Beef Samosa", 1500, description="Per piece", preparation_time=8),
        ],
    },
    {
        "name": "Breakfast Rolex",
        "description": "Ugandan chapati wraps — breakfast menu.",
        "display_order": 12,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Rolex Chicken", 12000, is_featured=True),
            _item("Rolex Beef", 10000),
            _item("Rolex + Eggs", 5000),
        ],
    },
    {
        "name": "Egg Dishes",
        "description": "Omelettes, scrambled & boiled eggs.",
        "display_order": 13,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Plain Omelette", 5000),
            _item("Spanish Omelette", 7000),
            _item("Scrambled Eggs (1)", 5000, description="Single serving"),
            _item("Scrambled Eggs (4)", 9000, description="For 4"),
            _item("Boiled Egg", 1000, description="Per piece"),
        ],
    },
    {
        "name": "Breakfast Snacks & Sides",
        "description": "Snacks and sides from the breakfast menu.",
        "display_order": 14,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Doughnut", 1000, description="Per piece"),
            _item("Mandazi", 1000, description="Per piece"),
            _item("Spring Roll", 1000, description="Per piece"),
            _item("Cassava", 1000, description="Per piece"),
            _item("Chapati", 1000),
            _item("Toast Bread Fried", 5000),
            _item("Sausages (Pair)", 4000),
            _item("Chap", 3000, description="Per piece"),
            _item("Kebab", 3000, description="Per piece"),
        ],
    },
    {
        "name": "Burgers",
        "description": "Burgers — beef & chicken.",
        "display_order": 20,
        "routes_to_kitchen": True,
        "display_group": "Burgers",
        "items": [
            _item("Beef Burger", 10000),
            _item("Plain Chicken Burger", 12000),
            _item("Beef Burger with Chips", 15000, is_featured=True),
            _item("Chicken Burger with Chips", 18000, is_featured=True),
            _item("Double Burger", 30000, is_featured=True),
        ],
    },
    {
        "name": "Soups",
        "description": "Clear and cream soups.",
        "display_order": 30,
        "routes_to_kitchen": True,
        "display_group": "Soups",
        "items": [
            _item("Clear Chicken Soup", 10000),
            _item("Clear Chicken Veg Soup", 12000),
            _item("Cream of Mushroom Soup", 15000),
            _item("Clear Mushroom Soup", 10000),
            _item("Pumpkin Soup", 15000),
        ],
    },
    {
        "name": "Sandwiches",
        "description": "Chicken, beef & veg sandwiches.",
        "display_order": 40,
        "routes_to_kitchen": True,
        "display_group": "Lunch",
        "items": [
            _item("Chicken Sandwich", 15000),
            _item("Beef Sandwich", 12000),
            _item("Veg Sandwich", 8000),
        ],
    },
    {
        "name": "Lunch — Chips & Curries",
        "description": "Chips plates, curries and steaks.",
        "display_order": 50,
        "routes_to_kitchen": True,
        "display_group": "Lunch",
        "items": [
            _item("Plain Chips", 7000),
            _item("Masala Chips", 12000),
            _item("Chips + Chicken", 17000, is_featured=True),
            _item("Chips + Sausages", 11000),
            _item(
                "Chicken Curry",
                20000,
                description="Served with rice, sauced potatoes, wedges, chips or boiled potatoes",
                is_featured=True,
            ),
            _item(
                "Fish Curry",
                25000,
                description="Served with rice, sauced potatoes, wedges, chips or boiled potatoes",
                is_featured=True,
            ),
            _item("Curry Steak", 20000),
            _item("Pepper Steak (Well Done)", 30000),
            _item("Pepper Sauce Steak (Half Done)", 30000),
            _item("Pepper Sauce Steak (Medium)", 30000),
        ],
    },
    {
        "name": "Lunch — Mains",
        "description": "Grills, fries plates, pilau and more.",
        "display_order": 51,
        "routes_to_kitchen": True,
        "display_group": "Lunch",
        "items": [
            _item(
                "Pan Fried Goat + Chips (with Sauce)",
                21000,
                is_featured=True,
            ),
            _item("Hot Dog + Chips", 20000),
            _item("Chicken Tikka Masala", 20000),
            _item("Grilled Fish Fillet", 20000),
            _item("Vegetable Curry", 15000),
            _item("Whole Fish Deep Fry", 35000, is_featured=True),
            _item("Chicken Wings + Chips", 15000),
            _item("Chicken Bonanza + Chips", 12000),
            _item("Pilau Plate", 8000),
            _item("Beef Pilau", 10000),
            _item("Chips Beef", 15000),
            _item("Chips Liver", 20000),
            _item("Fried Fish Fillet", 20000),
        ],
    },
    {
        "name": "Local Foods (Matooke)",
        "description": "Matooke + all foods — local favourites.",
        "display_order": 60,
        "routes_to_kitchen": True,
        "display_group": "Local Foods",
        "items": [
            _item("Beef Stew (Matooke)", 13000),
            _item("Fish Stew (Matooke)", 15000),
            _item("Chicken Stew (Matooke)", 15000),
            _item("Fish + Groundnuts (Matooke)", 10000),
            _item("Peas (Matooke)", 7000, description="Menu: Pest"),
            _item("Goat (Matooke)", 18000, is_featured=True),
            _item("Beef or Groundnuts (Matooke)", 12000),
        ],
    },
    {
        "name": "Pastas & Specials",
        "description": "Pastas, fingers, ribs and chops.",
        "display_order": 70,
        "routes_to_kitchen": True,
        "display_group": "Pastas",
        "items": [
            _item(
                "Spaghetti Napolitana (Red Sauce)",
                12000,
                description="Menu: Supagetti Naptitene",
            ),
            _item(
                "Penne Arrabbiata (Red Sauce)",
                12000,
                description="Menu: Penre Alabiyeta",
            ),
            _item(
                "Spaghetti Bolognese",
                18000,
                description="Menu: Supergetti Bolonnise",
                is_featured=True,
            ),
            _item("Fish Fingers + Chips", 15000),
            _item("Chicken Fingers + Chips", 18000),
            _item("Pork Chops", 25000),
            _item("Pork Ribs", 30000, is_featured=True),
            _item("Goat Ribs", 30000, is_featured=True),
            _item(
                "Pasta Carbonara",
                28000,
                description="Court / cream sauce — menu: Pasta Cabonalla",
            ),
            _item(
                "Chicken Escalope",
                25000,
                description="Menu: Chicken Escop",
            ),
        ],
    },
    {
        "name": "Juices",
        "description": "Fresh juices.",
        "display_order": 80,
        "routes_to_kitchen": False,
        "display_group": "Drinks",
        "items": [
            _item("Passion Juice", 5000, routes_to_kitchen=False, preparation_time=5),
            _item(
                "Pineapple Mint Juice",
                8000,
                routes_to_kitchen=False,
                preparation_time=5,
            ),
            # Menu showed "00/=" — confirm with client; seeded at common cafe price.
            _item(
                "Avocado Juice",
                10000,
                description="Confirm price with kitchen — menu print was blank (00/=)",
                routes_to_kitchen=False,
                preparation_time=5,
            ),
            _item(
                "Juice Cocktail",
                15000,
                routes_to_kitchen=False,
                preparation_time=8,
                is_featured=True,
            ),
            _item("Mango Juice", 5000, routes_to_kitchen=False, preparation_time=5),
        ],
    },
]


DISPLAY_GROUPS = [
    {"name": "Breakfast", "display_order": 10, "tile_color": "#F59E0B"},
    {"name": "Burgers", "display_order": 20, "tile_color": "#DC2626"},
    {"name": "Soups", "display_order": 30, "tile_color": "#EA580C"},
    {"name": "Lunch", "display_order": 40, "tile_color": "#16A34A"},
    {"name": "Local Foods", "display_order": 50, "tile_color": "#B8860B"},
    {"name": "Pastas", "display_order": 60, "tile_color": "#7C3AED"},
    {"name": "Drinks", "display_order": 70, "tile_color": "#0EA5E9"},
]

# Static assets for the public guest menu (served from frontend /images/...).
DIGITAL_MENU_IMAGE_BASE = "/images/restaurant/storms-cafe"

DIGITAL_MENU_PUBLICATION_IMAGES = {
    "logo_url": f"{DIGITAL_MENU_IMAGE_BASE}/logo.png",
    "cover_image_url": f"{DIGITAL_MENU_IMAGE_BASE}/flyer.png",
    "gallery_images": [
        f"{DIGITAL_MENU_IMAGE_BASE}/hero-pizza.png",
        f"{DIGITAL_MENU_IMAGE_BASE}/hero-lamb.png",
    ],
}

DIGITAL_MENU_SECTION_IMAGES = {
    "Breakfast": f"{DIGITAL_MENU_IMAGE_BASE}/breakfast.png",
    "Burgers": f"{DIGITAL_MENU_IMAGE_BASE}/burgers-soups.png",
    "Soups": f"{DIGITAL_MENU_IMAGE_BASE}/burgers-soups.png",
    "Lunch": f"{DIGITAL_MENU_IMAGE_BASE}/lunch-mains.png",
    "Local Foods": f"{DIGITAL_MENU_IMAGE_BASE}/local-pastas.png",
    "Pastas": f"{DIGITAL_MENU_IMAGE_BASE}/local-pastas.png",
    "Drinks": f"{DIGITAL_MENU_IMAGE_BASE}/juices.png",
}

DIGITAL_MENU_SECTION_SUBTITLES = {
    "Local Foods": "Matooke + all foods",
}


def build_catalog() -> dict:
    """Export shape consumed by seed_storms_cafe_menu and JSON export."""
    return {
        "restaurant": RESTAURANT,
        "menu": MENU,
        "item_category": ITEM_CATEGORY,
        "unit_of_measure": UNIT_OF_MEASURE,
        "display_groups": DISPLAY_GROUPS,
        "categories": CATEGORIES,
    }
