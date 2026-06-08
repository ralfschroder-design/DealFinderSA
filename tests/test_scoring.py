from dealfinder.models import Category, Listing
from dealfinder.scoring import cohort_key, build_market_reference, score_listing


def _l(price, make="Toyota", model="Hilux", year=2019, valid=True, lid="x"):
    return Listing(
        source_key="gumtree", source_listing_id=str(lid), url="https://g/a/1",
        category=Category.CAR, make=make, model=model, year=year,
        price_zar=price, is_valid=valid,
    )


def test_cohort_key_requires_make_and_model():
    assert cohort_key(_l(100000)) == ("car", "toyota", "hilux", 2019)
    assert cohort_key(_l(100000, make=None)) is None
    assert cohort_key(_l(100000, model=None)) is None


def test_build_market_reference_median_and_count():
    ref = build_market_reference([_l(280000, lid=1), _l(300000, lid=2), _l(320000, lid=3)])
    stat = ref[("car", "toyota", "hilux", 2019)]
    assert stat["median"] == 300000 and stat["count"] == 3


def test_reference_ignores_invalid_and_unpriced():
    ref = build_market_reference([_l(300000, lid=1), _l(999, lid=2, valid=False), _l(None, lid=3)])
    assert ref[("car", "toyota", "hilux", 2019)]["count"] == 1


def test_score_at_market_is_50():
    ref = {("car", "toyota", "hilux", 2019): {"median": 300000, "count": 5}}
    r = score_listing(_l(300000), ref)
    assert r["deal_score"] == 50 and r["deal_delta_zar"] == 0 and r["deal_confidence"] == "medium"


def test_score_underpriced_capped_100_high_conf():
    ref = {("car", "toyota", "hilux", 2019): {"median": 300000, "count": 20}}
    r = score_listing(_l(240000), ref)  # 20% under market
    assert r["deal_score"] == 100 and r["deal_delta_zar"] == 60000 and r["deal_confidence"] == "high"


def test_score_ten_percent_under_is_75():
    ref = {("car", "toyota", "hilux", 2019): {"median": 300000, "count": 3}}
    r = score_listing(_l(270000), ref)
    assert r["deal_score"] == 75 and r["deal_confidence"] == "low"


def test_score_overpriced_floor_0():
    ref = {("car", "toyota", "hilux", 2019): {"median": 300000, "count": 6}}
    r = score_listing(_l(360000), ref)  # 20% over
    assert r["deal_score"] == 0


def test_no_score_for_thin_cohort():
    ref = {("car", "toyota", "hilux", 2019): {"median": 300000, "count": 1}}
    assert score_listing(_l(250000), ref) is None


def test_no_score_without_make_or_model_or_price():
    ref = {}
    assert score_listing(_l(250000, make=None), ref) is None
    assert score_listing(_l(None), ref) is None
