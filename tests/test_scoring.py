from dealfinder.models import Category, Listing
from dealfinder.scoring import cohort_key, build_market_reference, score_listing


def _l(price, make="Toyota", model="Hilux", year=2019, valid=True, lid="x", mileage=None):
    return Listing(
        source_key="gumtree", source_listing_id=str(lid), url="https://g/a/1",
        category=Category.CAR, make=make, model=model, year=year,
        price_zar=price, is_valid=valid, mileage_km=mileage,
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


def test_vw_and_volkswagen_merge_into_one_cohort():
    ref = build_market_reference([
        _l(280000, make="VW", lid=1),
        _l(320000, make="Volkswagen", lid=2),
    ])
    assert len(ref) == 1
    stat = next(iter(ref.values()))
    assert stat["count"] == 2 and stat["median"] == 300000


def test_make_alias_enables_scoring():
    # Two spellings of the same make reach the >=2 cohort threshold, so a
    # third listing can now be scored where before it could not.
    ref = build_market_reference([
        _l(280000, make="VW", lid=1),
        _l(320000, make="Volkswagen", lid=2),
    ])
    r = score_listing(_l(270000, make="vw"), ref)  # 10% under merged median
    assert r is not None
    assert r["deal_score"] == 75


# ---------------------------------------------------------------------------
# Mileage-aware (condition) scoring — Plan 10
# ---------------------------------------------------------------------------

def test_build_reference_includes_mileage_median():
    ref = build_market_reference([
        _l(300000, lid=1, mileage=100000),
        _l(300000, lid=2, mileage=200000),
    ])
    stat = ref[("car", "toyota", "hilux", 2019)]
    assert stat["mileage_median"] == 150000
    assert stat["mileage_count"] == 2


def test_low_mileage_scores_higher_than_high_mileage_at_same_price():
    listings = [_l(300000, lid=1, mileage=80000), _l(300000, lid=2, mileage=220000)]
    ref = build_market_reference(listings)  # mileage_median = 150000
    low = score_listing(_l(300000, lid=3, mileage=80000), ref)
    high = score_listing(_l(300000, lid=4, mileage=220000), ref)
    # both priced at market (price_score 50); mileage tips them either side of 50
    assert low["deal_score"] > 50
    assert high["deal_score"] < 50
    assert low["deal_score"] > high["deal_score"]


def test_high_mileage_discounts_an_otherwise_good_price():
    ref = build_market_reference([
        _l(300000, lid=1, mileage=100000),
        _l(300000, lid=2, mileage=100000),
    ])  # mileage_median = 100000
    # 10% under market (price_score 75) but 250k km vs 100k peers -> -20 -> 55
    r = score_listing(_l(270000, lid=3, mileage=250000), ref)
    assert r["deal_score"] == 55


def test_mileage_adjustment_is_bounded_to_20():
    ref = build_market_reference([
        _l(300000, lid=1, mileage=300000),
        _l(300000, lid=2, mileage=300000),
    ])  # mileage_median = 300000
    # near-zero km at market price -> +20 cap -> 70
    r = score_listing(_l(300000, lid=3, mileage=1), ref)
    assert r["deal_score"] == 70


def test_no_mileage_means_pure_price_score():
    ref = build_market_reference([
        _l(300000, lid=1, mileage=100000),
        _l(300000, lid=2, mileage=200000),
    ])
    # listing with no mileage_km -> unchanged price score (10% under = 75)
    r = score_listing(_l(270000, lid=3), ref)
    assert r["deal_score"] == 75


def test_mileage_ignored_when_cohort_has_under_two_mileaged_peers():
    # Only one peer has mileage -> mileage_count 1 -> no adjustment.
    ref = build_market_reference([
        _l(300000, lid=1, mileage=100000),
        _l(300000, lid=2),  # no mileage
    ])
    r = score_listing(_l(300000, lid=3, mileage=10), ref)
    assert r["deal_score"] == 50  # pure price score, no mileage tip
