from dealfinder.fingerprint import compute_fingerprint
from dealfinder.models import Category, Listing


def _car(**over):
    base = dict(
        source_key="webuycars",
        source_listing_id="1",
        url="https://x/1",
        category=Category.CAR,
        make="Toyota",
        model="Hilux",
        variant="2.4 GD-6 SRX",
        year=2019,
        mileage_km=145000,
        price_zar=339900,
        province="Gauteng",
    )
    base.update(over)
    return Listing(**base)


def test_same_vehicle_same_fingerprint_regardless_of_price():
    a = _car(source_listing_id="1", price_zar=339900)
    b = _car(source_listing_id="2", price_zar=345000)
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_mileage_within_band_matches_across_band_differs():
    a = _car(mileage_km=145000)
    b = _car(mileage_km=148000)  # same 10k band (14)
    c = _car(mileage_km=152000)  # next band (15)
    assert compute_fingerprint(a) == compute_fingerprint(b)
    assert compute_fingerprint(a) != compute_fingerprint(c)


def test_different_model_differs():
    a = _car(model="Hilux")
    b = _car(model="Ranger")
    assert compute_fingerprint(a) != compute_fingerprint(b)


def test_variant_normalised():
    a = _car(variant="2.4 GD-6 SRX")
    b = _car(variant="2.4 GD6 SRX")
    assert compute_fingerprint(a) == compute_fingerprint(b)


def test_fingerprint_is_stable_hex_string():
    fp = compute_fingerprint(_car())
    assert isinstance(fp, str) and len(fp) == 16
