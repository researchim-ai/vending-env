"""
Дефолтные поставщики и каталог для воспроизводимых прогонов (без внешнего API).
"""
from vending_env.core.suppliers import Supplier

# Популярные товары для вендинга (статья: research products, wholesalers)
DEFAULT_PRODUCTS = {
    "cola": 1.2,
    "water": 0.8,
    "chips": 1.5,
    "snickers": 1.4,
    "red_bull": 2.0,
    "orange_juice": 1.8,
    "cookies": 1.6,
    "gum": 0.9,
    "nuts": 2.2,
    "sandwich": 3.0,
}


def get_default_suppliers() -> list[Supplier]:
    """Два поставщика с перекрывающимся каталогом (разные цены). Слоты 0–5 small, 6–11 large."""
    # Крупные товары: sandwich, nuts — large
    size_map = {"sandwich": "large", "nuts": "large"}
    return [
        Supplier(
            supplier_id="supplier_1",
            name="Bulk Snacks Co",
            catalog={
                "cola": 1.0,
                "water": 0.6,
                "chips": 1.2,
                "snickers": 1.1,
                "red_bull": 1.7,
                "orange_juice": 1.5,
                "cookies": 1.3,
                "gum": 0.7,
            },
            min_order_value=50.0,
            lead_time_days=(2, 4),
            size_class_map=size_map,
        ),
        Supplier(
            supplier_id="supplier_2",
            name="Beverage & More",
            catalog={
                "cola": 1.1,
                "water": 0.65,
                "red_bull": 1.8,
                "orange_juice": 1.6,
                "nuts": 1.9,
                "sandwich": 2.6,
                "chips": 1.25,
                "gum": 0.75,
            },
            min_order_value=40.0,
            lead_time_days=(3, 5),
            size_class_map=size_map,
        ),
    ]
