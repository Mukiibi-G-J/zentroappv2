"""
Royal Joint Restaurant menu catalog for seed_royal_joint_menu.

Source: printed menus (Lusaniya combos + full halal restaurant menu).
Prices in UGX; ranges use midpoint as unit_price with min/max preserved.
"""

from __future__ import annotations

RESTAURANT = {
    "name": "Royal Joint Restaurant",
    "tagline": "100% Halal | Great Food, Great Taste, Royal Experience!",
    "location": "Busega, Northern Bypass",
    "phones": ["+256 766174778", "+256 704970471"],
}

MENU = {
    "name": "Royal Joint Full Menu",
    "code": "RJ-MAIN",
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
    price_min: int | None = None,
    price_max: int | None = None,
    routes_to_kitchen: bool | None = None,
    dietary_info: list[str] | None = None,
    is_featured: bool = False,
    preparation_time: int = 15,
):
    return {
        "item_name": name,
        "unit_price": price,
        "description": description,
        "price_min": price_min,
        "price_max": price_max,
        "type": "Service",
        "routes_to_kitchen": routes_to_kitchen,
        "dietary_info": dietary_info or ["halal"],
        "is_featured": is_featured,
        "preparation_time": preparation_time,
    }


def _range(low: int, high: int) -> tuple[int, int, int]:
    """Return (unit_price midpoint, price_min, price_max)."""
    return (low + high) // 2, low, high


def _price_range_item(
    name: str,
    low: int,
    high: int,
    *,
    description: str = "",
    routes_to_kitchen: bool | None = None,
    **kwargs,
):
    mid, pmin, pmax = _range(low, high)
    return [
        _item(
            name,
            mid,
            description=description,
            price_min=pmin,
            price_max=pmax,
            routes_to_kitchen=routes_to_kitchen,
            **kwargs,
        )
    ]


def _lusaniya_items() -> list[dict]:
    combos = [
        (
            "Lusaniya for 1",
            25000,
            30000,
            "Matooke, pilau, posho or yams; beef stew/RJ chicken; beans stew or g. nuts sauce; "
            "grilled chicken or beef; chapati; fried irish potato; salads or greens; fresh juice.",
        ),
        (
            "Lusaniya for 2",
            50000,
            60000,
            "Matooke, pilau, posho or yams; beef stew/RJ chicken; beans stew or g. nuts sauce; "
            "grilled chicken or beef; chapati; fried irish potato; salads or greens; 2 fresh juices.",
        ),
        (
            "Lusaniya for 3",
            75000,
            90000,
            "Matooke, pilau, posho or yams; grilled chicken; beef stew/RJ chicken; beans stew or "
            "g. nuts sauce; 3 chapati; fried irish or gonja; vegetable salad; 3 fresh juices.",
        ),
        (
            "Lusaniya for 4",
            100000,
            120000,
            "Matooke, pilau, posho or yams; grilled chicken; beef stew/RJ chicken; beans or "
            "g. nuts sauce; 4 chapati; fried irish or gonja; vegetable or salad; 4 fresh juices.",
        ),
        (
            "Lusaniya for 5",
            180000,
            180000,
            "Large matooke platter; grilled chicken and beef stew; 5 chapati; fried plantains; "
            "vegetable salad; 2 rolex; 5 fresh juices.",
        ),
        (
            "Lusaniya for 6",
            180000,
            180000,
            "Large matooke platter; grilled chicken and beef stew; 6 chapati; fried plantains; "
            "vegetable salad; 3 rolex; 6 fresh juices.",
        ),
        (
            "Lusaniya for 7",
            210000,
            220000,
            "Matooke, pilau, posho or yams; grilled chicken or beef stew/RJ chicken; beans stew "
            "or g. nuts sauce; 7 chapati; fried irish potatoes or gonja; vegetable or salad; "
            "7 fresh juices; 3 rolex.",
        ),
        (
            "Lusaniya for 8",
            240000,
            260000,
            "Large matooke platter, pilau, posho or yams; 2 grilled chicken or beef stew/RJ "
            "chicken; beans stew and g. nuts sauce; 8 chapati; fried irish potatoes and gonja; "
            "vegetable salad + greens; 8 fresh juices; 4 rolex.",
        ),
        (
            "Lusaniya for 9",
            270000,
            290000,
            "Large matooke platter, pilau, posho or yams; 2 grilled chicken or beef stew/RJ "
            "chicken; beans stew or g. nuts sauce; 9 chapati; fried irish potatoes and gonja; "
            "large vegetable or salad; 9 fresh juices; 4 rolex.",
        ),
        (
            "Lusaniya for 10",
            300000,
            320000,
            "Extra large matooke platter, pilau, posho or yams; 2 whole grilled chicken or beef "
            "stew/roasted chicken; beans stew or g. nuts sauce; 10 chapati; fried irish potatoes "
            "or gonja; family-size vegetable salad + greens; 10 fresh juices; 5 rolex.",
        ),
    ]
    out: list[dict] = []
    for name, low, high, desc in combos:
        mid, pmin, pmax = _range(low, high)
        out.append(
            _item(
                name,
                mid,
                description=desc,
                price_min=pmin if low != high else None,
                price_max=pmax if low != high else None,
                is_featured=low >= 100000,
            )
        )
    return out


CATEGORIES: list[dict] = [
    {
        "name": "Lusaniya Menu Combos",
        "description": "Shared platters for groups — matooke, pilau, grilled meats, sides & fresh juice.",
        "display_order": 1,
        "routes_to_kitchen": True,
        "display_group": "Lusaniya",
        "items": [
            *_lusaniya_items(),
        ],
    },
    {
        "name": "Extras",
        "description": "Individual sides and add-ons for Lusaniya platters.",
        "display_order": 2,
        "routes_to_kitchen": True,
        "display_group": "Lusaniya",
        "items": [
            _item("Chapati", 5000),
            _item("Fried Plantains", 5000),
            _item("Rolex", 6000),
            _item("Beans Stew", 5000),
            _item("G. Nuts Sauce", 5000),
            _item("Salad / Greens", 5000),
            _item("Grilled Chicken (Extra)", 6000),
            _item("Beef Stew (Extra)", 6000),
            _item("Fried Irish Potatoes", 5000),
            _item("Matooke / Yams", 5000),
        ],
    },
    {
        "name": "Ugandan Breakfast",
        "description": "Served 24/7 — local breakfast favourites.",
        "display_order": 10,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Katogo (Beef)", 12000, description="Matooke + halal beef stew"),
            _item("Katogo (Beans)", 9500, description="Matooke + beans + ghee"),
            _item("Katogo (G-nuts)", 9500, description="Matooke + g-nut sauce"),
            *_price_range_item(
                "Fish Katogo (Nile Perch)",
                15000,
                30000,
                description="Matooke + fried Nile perch",
            ),
            _item("Cassava Leaves + Rice", 12000, description="Sombe stew"),
            _item("Rolex Classic", 7000),
            _item("Rolex Classic + Avocado", 11000, description="Rolex + avocado add-on"),
            _item(
                "Rolex Classic + Halal Sausage",
                13000,
                description="Rolex + halal sausage add-on",
            ),
            _item("Kikomando", 7000, description="Chapati + beans"),
            _item("Chapati 2pcs + Beef Stew", 12000, description="Halal beef"),
            _item("Boiled Cassava/Yam + G-nut Sauce", 9000),
            _item("Porridge (Bushera/Millet)", 5000),
        ],
    },
    {
        "name": "International Breakfast",
        "description": "Served 24/7 — international breakfast plates.",
        "display_order": 11,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item(
                "Full English Halal",
                18000,
                description="2 eggs, halal beef sausage, beans, toast",
            ),
            _item(
                "Chicken Omelette + Toast",
                12000,
                description="3 eggs + grilled halal chicken",
            ),
            _item("Pancakes 3pcs + Honey", 12000),
            _item("Banana", 12000),
            _item("Waffles 2pcs + Syrup", 12000),
            _item("Waffles 2pcs + Syrup + Fruit", 15000),
            _item("Fruit Bowl", 8000),
            _item("Oats + Milk + Honey", 8000),
            _item(
                "Beef Burger Breakfast",
                15000,
                description="Halal beef patty, egg, toast",
            ),
            _item("Chicken Sandwich + Chips", 15000),
            _item("Pilau + Beef/Chicken", 15000),
        ],
    },
    {
        "name": "Breakfast Combos",
        "description": "Value breakfast combos — served 24/7.",
        "display_order": 12,
        "routes_to_kitchen": True,
        "display_group": "Breakfast",
        "items": [
            _item("Boda Guy Special", 7000, description="Rolex + tea"),
            _item(
                "Night Driver",
                12000,
                description="Fish katogo + tea. Available 10PM – 6AM",
            ),
            _item(
                "Family Tray",
                18000,
                description="2 chapati + beans + 2 tea + 2 mandazi",
            ),
        ],
    },
    {
        "name": "Breakfast Drinks",
        "description": "Hot & cold drinks with breakfast.",
        "display_order": 13,
        "routes_to_kitchen": False,
        "display_group": "Breakfast",
        "items": [
            _item("African Tea (Breakfast)", 5400, routes_to_kitchen=False),
            _item("Black Tea (Breakfast)", 3500, routes_to_kitchen=False),
            _item("Coffee (Breakfast)", 6500, routes_to_kitchen=False),
            _item("Milk Coffee (Breakfast)", 5500, routes_to_kitchen=False),
            _item("Fresh Juice (Breakfast)", 8000, routes_to_kitchen=False),
            _item("Malt Drink (Breakfast)", 6000, routes_to_kitchen=False),
            _item("Bushera (Breakfast)", 3000, routes_to_kitchen=False),
            _item("Soda 300ml (Breakfast)", 3000, routes_to_kitchen=False),
        ],
    },
    {
        "name": "Halal BBQ Grills",
        "description": "Charcoal grills and platters.",
        "display_order": 20,
        "routes_to_kitchen": True,
        "display_group": "BBQ & Grills",
        "items": [
            _item("Beef Muchomo", 18000),
            _item("Chicken Quarter BBQ", 20000),
            _item("Half Grilled Chicken", 25000),
            _item("Full Grilled Chicken", 50000),
            _item("Beef Skewers (2)", 15000),
            _item("Grilled Tilapia (Whole)", 35000),
            _item("Mixed Grill Platter (2 People)", 75000),
            _item("Royal Family Grill Platter (4 People)", 140000, is_featured=True),
            _item("Lamb Chops (3pcs)", 25000, description="NEW"),
            _item("Grilled Rabbit (Half)", 28000, description="NEW"),
        ],
    },
    {
        "name": "Soups",
        "description": "Hot and cold soups.",
        "display_order": 30,
        "routes_to_kitchen": True,
        "display_group": "Soups",
        "items": [
            _item("Clear Chicken Soup", 25000),
            _item("Clear Fish Soup", 25000),
            _item("Veggie Soup", 16000),
            _item("Creamy Avocado Cucumber Cold Soup", 15000),
            _item("Lamb with Potatoes and Carrots Soup", 23000),
            _item("Mushroom Soup", 18000),
            _item("Banana with Goat's Meat (Mtori) Soup", 25000),
            _item("Potato Leeks Soup", 13000),
            _item("Chicken Noodle Soup", 15000),
            _item("Tomato & Sweet Corn Soup", 13000),
            _item("Mexican Shredded Beef Soup", 15000),
        ],
    },
    {
        "name": "Local Food Combos",
        "description": "Local combo meals.",
        "display_order": 40,
        "routes_to_kitchen": True,
        "display_group": "Combos",
        "items": [
            _item("Kampala Street Combo", 10000, description="Rolex + African tea"),
            _item("Busega Katogo Combo", 15000, description="Beef katogo + African tea"),
            _item("Driver's Energy Meal", 10000, description="Kikomando + black tea"),
            _item(
                "Village Taste Combo",
                12000,
                description="Boiled cassava + g-nut sauce + bushera",
            ),
            _item("Northern Bypass Special", 18000, description="Pilau + beef + soda"),
            _item("Fisherman's Delight", 25000, description="Fish katogo + fresh juice"),
        ],
    },
    {
        "name": "Hot Snacks",
        "description": "Hot snacks — available 24/7.",
        "display_order": 50,
        "routes_to_kitchen": True,
        "display_group": "Snacks",
        "items": [
            _item("Samosa 1pc", 3000, description="Beef or veg — halal"),
            _item("Samosa 3pcs", 8000, description="Beef or veg — halal"),
            _item("Spring Rolls 3pcs", 5000, description="Veg or halal chicken"),
            _item("Kebab Rolls", 3500, description="Chapati + grilled halal beef/chicken"),
            _item("Uka Rolls", 3500, description="Fried chapati + spiced beef"),
            _item("Chips Plain", 12000),
            _item("Chips + Chicken", 15000),
            _item("Chips + Sausage", 20000, description="Chips + halal sausage add-on"),
            _item("Grilled Halal Sausage 1pc", 4000),
            _item(
                "Aubergine + Sliced Aroko (Gonja) with Garlic Sauce",
                12000,
            ),
        ],
    },
    {
        "name": "Baked & Sweet Snacks",
        "description": "Baked goods and sweet snacks — available 24/7.",
        "display_order": 51,
        "routes_to_kitchen": True,
        "display_group": "Snacks",
        "items": [
            _item("Mandazi 1pc", 3000),
            _item("Mandazi 4pcs", 8000),
            _item("Chapati 1pc (Snack)", 3000),
            _item("Pancakes 1pc (Snack)", 5000),
            _item("Waffle 1pc", 5000, description="With honey drizzle"),
            _item("Hard Boiled Eggs 2pcs", 3000),
            *_price_range_item("Fresh Fruit Salad Cup", 8000, 12000),
        ],
    },
    {
        "name": "Snack Combos",
        "description": "Snack combo deals — available 24/7.",
        "display_order": 52,
        "routes_to_kitchen": True,
        "display_group": "Snacks",
        "items": [
            _item("Snack Attack", 10000, description="1 samosa + 2 spring rolls + soda"),
            _item(
                "3AM Muchomo Snack",
                25000,
                description="1/4kg goat + chips. Midnight – 5AM",
            ),
            _item(
                "Tea Time Deal",
                8000,
                description="1 samosa + African tea. 7AM – 10AM",
            ),
        ],
    },
    {
        "name": "Snack Drinks",
        "description": "Drinks with snacks.",
        "display_order": 53,
        "routes_to_kitchen": False,
        "display_group": "Snacks",
        "items": [
            _item("African Tea (Snacks)", 5000, routes_to_kitchen=False),
            _item("Coffee (Snacks)", 5500, routes_to_kitchen=False),
            _item("Twings Tea", 8000, routes_to_kitchen=False),
            _item("Malt Drink (Snacks)", 6000, routes_to_kitchen=False),
            _item("Fresh Juice (Snacks)", 8000, routes_to_kitchen=False),
            *_price_range_item("Smoothies", 8000, 10000, routes_to_kitchen=False),
            *_price_range_item("Milkshakes", 10000, 15000, routes_to_kitchen=False),
            _item("Soda 300ml (Snacks)", 3000, routes_to_kitchen=False),
            _item("Water 500ml", 3000, routes_to_kitchen=False),
        ],
    },
    {
        "name": "Fast Food Combos",
        "description": "Burger, chicken and family fast-food trays.",
        "display_order": 60,
        "routes_to_kitchen": True,
        "display_group": "Fast Food",
        "items": [
            _item("Royal Burger Combo", 22000, description="Beef burger + chips + soda"),
            _item(
                "Chicken Crunch Combo",
                20000,
                description="Chicken sandwich + chips + soda",
            ),
            _item(
                "BBQ Chicken Combo",
                25000,
                description="Quarter grilled chicken + chips + soda",
            ),
            _item(
                "Snack Attack Combo",
                12000,
                description="2 samosas + spring rolls + soda",
            ),
            _item(
                "Royal Breakfast Combo",
                22000,
                description="Full English breakfast + coffee",
            ),
            _item(
                "Family Fast Food Tray",
                70000,
                description="4 burgers + large chips + 4 sodas",
            ),
        ],
    },
]


DISPLAY_GROUPS = [
    {"name": "Lusaniya", "display_order": 1, "tile_color": "#B8860B"},
    {"name": "Breakfast", "display_order": 10, "tile_color": "#F59E0B"},
    {"name": "BBQ & Grills", "display_order": 20, "tile_color": "#DC2626"},
    {"name": "Soups", "display_order": 30, "tile_color": "#EA580C"},
    {"name": "Combos", "display_order": 40, "tile_color": "#16A34A"},
    {"name": "Snacks", "display_order": 50, "tile_color": "#CA8A04"},
    {"name": "Fast Food", "display_order": 60, "tile_color": "#7C3AED"},
]


def build_catalog() -> dict:
    """Export shape consumed by seed_royal_joint_menu and JSON export."""
    return {
        "restaurant": RESTAURANT,
        "menu": MENU,
        "item_category": ITEM_CATEGORY,
        "unit_of_measure": UNIT_OF_MEASURE,
        "display_groups": DISPLAY_GROUPS,
        "categories": CATEGORIES,
    }
