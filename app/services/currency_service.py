from decimal import Decimal

# Static conversion rates to USD (base currency).
# rate = how many USD per 1 unit of foreign currency.
RATES_TO_USD: dict[str, Decimal] = {
    "USD": Decimal("1.00"),
    "EUR": Decimal("1.09"),
    "GBP": Decimal("1.27"),
    "INR": Decimal("0.012"),
    "JPY": Decimal("0.0067"),
    "CAD": Decimal("0.74"),
    "AUD": Decimal("0.66"),
    "CHF": Decimal("1.12"),
    "CNY": Decimal("0.14"),
    "BRL": Decimal("0.18"),
}


def convert_to_base(amount: Decimal, currency: str, base_currency: str = "USD") -> Decimal:
    """
    Convert an amount from `currency` to `base_currency` using static rates.
    Falls back to 1:1 if the currency is unknown.
    """
    if currency == base_currency:
        return amount

    # Convert source currency -> USD
    source_rate = RATES_TO_USD.get(currency.upper(), Decimal("1.00"))
    amount_in_usd = amount * source_rate

    # Convert USD -> target base currency
    target_rate = RATES_TO_USD.get(base_currency.upper(), Decimal("1.00"))
    if target_rate == 0:
        return amount_in_usd

    return (amount_in_usd / target_rate).quantize(Decimal("0.01"))
