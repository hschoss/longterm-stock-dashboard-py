from __future__ import annotations

import math

import pytest

from findash.analytics.irr import internal_rate_of_return


def test_irr_of_single_period_investment() -> None:
    # -100 heute, +110 nach einem Jahr => 10 % IRR
    irr = internal_rate_of_return([-100.0, 110.0], [0.0, 1.0])
    assert irr == pytest.approx(0.10, abs=1e-6)


def test_irr_of_annuity_style_cashflows() -> None:
    # jaehrlich -10 fuer drei Jahre, dann +36.31 im vierten Jahr
    irr = internal_rate_of_return([-10.0, -10.0, -10.0, 36.31], [0.0, 1.0, 2.0, 3.0])
    assert 0.0 < irr < 0.3


def test_irr_requires_sign_change_returns_nan() -> None:
    irr = internal_rate_of_return([10.0, 20.0], [0.0, 1.0])
    assert math.isnan(irr)
