def convert_usd_oz_to_cny_g(
    price_usd_oz: float,
    usd_cny_rate: float,
    troy_ounce_grams: float,
) -> float:
    if price_usd_oz <= 0:
        raise ValueError("price_usd_oz must be greater than zero")
    if usd_cny_rate <= 0:
        raise ValueError("usd_cny_rate must be greater than zero")
    if troy_ounce_grams <= 0:
        raise ValueError("troy_ounce_grams must be greater than zero")
    return round((price_usd_oz * usd_cny_rate) / troy_ounce_grams, 6)
