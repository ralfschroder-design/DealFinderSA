"""Tests for dealfinder.vehicles.split_make_model — offline / pure-logic."""
from __future__ import annotations

import pytest

from dealfinder.vehicles import split_make_model


# ---------------------------------------------------------------------------
# Happy-path: single-word makes
# ---------------------------------------------------------------------------

def test_toyota_hilux():
    make, model, variant = split_make_model("2019-toyota-hilux-2-4-gd6-srx")
    assert make == "Toyota"
    assert model == "Hilux"
    assert variant is not None and "2" in variant  # e.g. "2 4 Gd6 Srx"


def test_bmw_no_year():
    make, model, variant = split_make_model("bmw-220i-m-sport")
    assert make is not None and make.lower() == "bmw"
    assert model is not None and model.lower() == "220i"


# ---------------------------------------------------------------------------
# Happy-path: multi-word makes
# ---------------------------------------------------------------------------

def test_land_rover():
    make, model, variant = split_make_model("2018-land-rover-discovery-sport")
    assert make == "Land Rover"
    assert model == "Discovery"


def test_harley_davidson():
    make, model, variant = split_make_model("2017-harley-davidson-street-glide")
    assert make is not None and "harley" in make.lower()
    assert "davidson" in make.lower()
    assert model is not None and model.lower() == "street"


def test_mercedes_benz():
    make, model, variant = split_make_model("2020-mercedes-benz-c-class")
    assert make is not None and "mercedes" in make.lower()
    assert model is not None and model.lower() == "c"


def test_range_rover():
    make, model, variant = split_make_model("2021-range-rover-sport-3-0")
    assert make == "Range Rover"
    assert model is not None and model.lower() == "sport"


def test_alfa_romeo():
    make, model, variant = split_make_model("2019-alfa-romeo-giulia-ti")
    assert make == "Alfa Romeo"
    assert model is not None and model.lower() == "giulia"


# ---------------------------------------------------------------------------
# Fallback: unknown make
# ---------------------------------------------------------------------------

def test_unknown_make_fallback():
    make, model, variant = split_make_model("2015-acme-rocket-gt")
    assert make == "Acme"
    assert model == "Rocket"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_no_year():
    make, model, variant = split_make_model("toyota-corolla-1-8")
    assert make == "Toyota"
    assert model == "Corolla"


def test_variant_none_when_only_make_model():
    make, model, variant = split_make_model("2020-ford-ranger")
    assert make == "Ford"
    assert model == "Ranger"
    # variant should be None or empty string — normalise to falsy
    assert not variant


def test_plus_separator():
    """+ characters in slug should be treated as spaces."""
    make, model, variant = split_make_model("2018+volkswagen+polo+tsi")
    assert make is not None and make.lower() == "volkswagen"
    assert model is not None and model.lower() == "polo"


def test_vw_alias():
    """'vw' is a known make alias."""
    make, model, variant = split_make_model("2016-vw-golf-7-tdi")
    assert make is not None and make.lower() == "vw"
    assert model is not None and model.lower() == "golf"


def test_returns_tuple_of_three():
    result = split_make_model("2019-toyota-hilux")
    assert isinstance(result, tuple)
    assert len(result) == 3
