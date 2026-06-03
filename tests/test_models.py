from dealfinder.models import Category, Listing, ListingStatus


def test_listing_minimal_valid():
    listing = Listing(
        source_key="webuycars",
        source_listing_id="123",
        url="https://example.com/123",
        category=Category.CAR,
        title="2019 Toyota Hilux",
        make="Toyota",
        model="Hilux",
        year=2019,
        price_zar=339900,
    )
    assert listing.status == ListingStatus.ACTIVE
    assert listing.image_urls == []
    assert listing.price_zar == 339900


def test_listing_rejects_bad_year():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Listing(
            source_key="webuycars",
            source_listing_id="1",
            url="u",
            category=Category.CAR,
            year=1800,  # below minimum
        )
