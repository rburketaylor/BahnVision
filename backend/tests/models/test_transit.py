from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models.transit import TransitRoute, TransitStop


def test_transit_stop_wheelchair_boarding_range() -> None:
    with pytest.raises(ValidationError):
        TransitStop(
            id="de:09162:6",
            name="München Hbf",
            latitude=48.1403,
            longitude=11.5583,
            wheelchair_boarding=3,
        )


def test_transit_route_type_must_be_non_negative() -> None:
    with pytest.raises(ValidationError):
        TransitRoute(
            id="route-1",
            short_name="S1",
            long_name="Freising - München Hbf",
            route_type=-1,
        )


def test_transit_route_type_accepts_gtfs_extended_values() -> None:
    route = TransitRoute(
        id="route-400",
        short_name="U3",
        long_name="Moosach - Fürstenried West",
        route_type=400,
    )

    assert route.route_type == 400
