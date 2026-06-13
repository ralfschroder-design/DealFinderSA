"""Tests for dealfinder.geo — pure great-circle distance + radius check."""
import pytest

from dealfinder.geo import haversine_km, is_within_radius

HARTIES = (-25.7457, 27.8540)
JOHANNESBURG = (-26.2041, 28.0473)
CAPE_TOWN = (-33.9249, 18.4241)


def test_distance_to_self_is_zero():
    assert haversine_km(*HARTIES, *HARTIES) == pytest.approx(0.0, abs=1e-6)


def test_distance_is_symmetric():
    assert haversine_km(*HARTIES, *CAPE_TOWN) == pytest.approx(haversine_km(*CAPE_TOWN, *HARTIES))


def test_known_distance_cape_town_to_joburg():
    # Great-circle CPT↔JHB is ~1265 km.
    assert 1240 < haversine_km(*CAPE_TOWN, *JOHANNESBURG) < 1290


def test_hartbeespoort_to_joburg_is_about_50km():
    assert 40 < haversine_km(*HARTIES, *JOHANNESBURG) < 60


def test_is_within_radius_true_for_near_point():
    assert is_within_radius(JOHANNESBURG[0], JOHANNESBURG[1], *HARTIES, 100) is True


def test_is_within_radius_false_for_far_point():
    assert is_within_radius(CAPE_TOWN[0], CAPE_TOWN[1], *HARTIES, 100) is False


def test_is_within_radius_keeps_unknown_coords():
    # Listings we haven't geolocated yet must not be hidden by a radius filter.
    assert is_within_radius(None, None, *HARTIES, 100) is True
    assert is_within_radius(-26.0, None, *HARTIES, 100) is True
