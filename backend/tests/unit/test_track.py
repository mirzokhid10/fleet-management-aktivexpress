"""Unit tests for the clean track rules (Day 10)."""

import datetime as dt

import pytest
from django.contrib.gis.geos import Point
from django.core.management import call_command

from apps.tracking import track
from apps.tracking.models import LocationPoint
from apps.tracking.track import Sample, assess
from tests import factories as f

T0 = dt.datetime(2026, 11, 18, 5, 0, tzinfo=dt.UTC)
LAT = 41.3
# Near Tashkent, one degree of latitude ≈ 111.2 km, one of longitude ≈ 83.5 km.
M_PER_DEG_LAT = 111_195


def north(meters: float) -> float:
    return LAT + meters / M_PER_DEG_LAT


def s(seconds: float, meters_north: float = 0, accuracy=None, valid=True) -> Sample:
    return Sample(T0 + dt.timedelta(seconds=seconds), 69.2, north(meters_north), accuracy, valid)


# --- pure rules --------------------------------------------------------------

@pytest.mark.unit
def test_distance_is_right_within_half_a_percent():
    # Tashkent centre to Chorsu, about 4.1 km apart on the map
    d = track.distance_m(69.2797, 41.3111, 69.2340, 41.3264)
    assert 4_000 < d < 4_200
    assert track.distance_m(69.2, LAT, 69.2, north(1000)) == pytest.approx(1000, rel=0.005)


@pytest.mark.unit
def test_first_point_is_good_with_nothing_to_measure():
    assert assess(s(0), None, None) == track.Verdict(True)


@pytest.mark.unit
def test_normal_driving_gets_distance_and_speed():
    v = assess(s(30, 400), s(0), s(0))  # 400 m in 30 s = 48 km/h
    assert v.is_valid
    assert v.distance_m == pytest.approx(400, rel=0.005)
    assert v.speed_kmh == pytest.approx(48, rel=0.005)


@pytest.mark.unit
@pytest.mark.parametrize("accuracy, valid", [(None, True), (100, True), (100.1, False),
                                             (1500, False)])
def test_low_accuracy_is_bad(accuracy, valid):
    assert assess(s(30, 100, accuracy=accuracy), s(0), s(0)).is_valid is valid


@pytest.mark.unit
@pytest.mark.parametrize("meters, valid", [(1240, True), (1260, False), (5000, False)])
def test_faster_than_150_kmh_is_a_jump(meters, valid):
    # 30 s: 1250 m = 150 km/h
    assert assess(s(30, meters), s(0), s(0)).is_valid is valid


@pytest.mark.unit
def test_standing_still_jitter_counts_as_zero():
    v = assess(s(30, 12), s(0), s(0))
    assert (v.is_valid, v.distance_m, v.speed_kmh) == (True, 0.0, 0.0)


@pytest.mark.unit
def test_same_second_counts_distance_without_speed():
    v = assess(s(0, 50), s(0), s(0))
    assert v.is_valid and v.speed_kmh is None


@pytest.mark.unit
def test_two_agreeing_points_after_a_jump_mean_the_anchor_was_wrong():
    anchor = s(0)
    jumped = s(30, 5000, valid=False)          # 600 km/h from the anchor
    nxt = s(60, 5300)                          # 36 km/h from the jumped point
    v = assess(nxt, anchor, jumped)
    assert (v.is_valid, v.accept_previous) == (True, True)
    assert v.distance_m == pytest.approx(300, rel=0.005)


@pytest.mark.unit
def test_point_back_on_track_after_a_single_jump_is_good():
    anchor = s(0)
    jumped = s(30, 5000, valid=False)
    back = s(60, 600)                          # 36 km/h from the anchor
    v = assess(back, anchor, jumped)
    assert (v.is_valid, v.accept_previous) == (True, False)


@pytest.mark.unit
def test_low_accuracy_point_is_not_trusted_as_a_new_anchor():
    anchor = s(0)
    vague = s(30, 5000, accuracy=500, valid=False)
    v = assess(s(60, 5300), anchor, vague)
    assert v.is_valid is False


# --- database ----------------------------------------------------------------

def _points(sh, rows):
    """rows: (seconds, meters north, accuracy) -> raw points, not yet assessed."""
    return [LocationPoint.objects.create(shift=sh, vehicle=sh.vehicle, recorded_at=T0 +
                                         dt.timedelta(seconds=sec),
                                         point=Point(69.2, north(m)), accuracy_m=acc)
            for sec, m, acc in rows]


DRIVE = [(0, 0, 10), (30, 400, 10), (60, 6000, 10),   # jump
         (90, 800, 10), (120, 820, 500),               # back on track; vague point
         (150, 1200, 10), (180, 1205, 10)]             # 400 m; standing still


@pytest.mark.unit
@pytest.mark.django_db
def test_recalculate_cleans_a_stored_track_and_totals_add_up():
    sh = f.shift(started_at=T0)
    _points(sh, DRIVE)
    assert track.recalculate(sh) == 6  # the first point was already right
    valid = [p.is_valid for p in sh.points.order_by("recorded_at")]
    assert valid == [True, True, False, True, False, True, True]
    t = track.totals(sh)
    assert (t.points, t.bad_points) == (7, 2)
    assert t.distance_km == pytest.approx(1.2, abs=0.01)  # 400 + 400 + 400 + 0
    assert t.max_speed_kmh == pytest.approx(48, rel=0.01)
    assert track.recalculate(sh) == 0  # nothing left to change


@pytest.mark.unit
@pytest.mark.django_db
def test_recalculate_command_reports_each_shift(capsys):
    sh = f.shift(started_at=T0)
    _points(sh, DRIVE)
    f.shift()  # no points: skipped
    call_command("recalculate_track")
    assert capsys.readouterr().out == f"shift {sh.pk}: 7 points, 2 bad, 1.2 km, 6 changed, 1 trips\n"
