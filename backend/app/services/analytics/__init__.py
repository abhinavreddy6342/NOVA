"""
NOVA Analytics Service Package.
"""

from app.services.analytics.service import (
    AnalyticsService,
    analytics_service,
)

__all__ = [
    "AnalyticsService",
    "analytics_service",
]
