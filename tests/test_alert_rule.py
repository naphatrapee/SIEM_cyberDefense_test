import pytest

@pytest.mark.skip(reason="TODO: 5 failed logins from one IP in 5 min -> one alert")
def test_failed_login_alert_fires():
    ...
