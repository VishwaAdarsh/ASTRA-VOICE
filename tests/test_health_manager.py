"""
Unit tests for HealthManager.
"""

from src.core.health import HealthManager, HealthStatus


def test_health_manager_defaults_and_updates():
    hm = HealthManager()
    assert len(hm.get_all_health()) == 9
    assert hm.is_overall_healthy() == True

    hm.set_status("Vision", HealthStatus.DEGRADED, "Vision provider fallback active")
    vision_health = hm.get_status("Vision")
    assert vision_health is not None
    assert vision_health.status == HealthStatus.DEGRADED
    assert "fallback active" in vision_health.message

    assert hm.is_overall_healthy() == True

    hm.set_status("Database", HealthStatus.UNAVAILABLE, "Database connection failed")
    assert hm.is_overall_healthy() == False
