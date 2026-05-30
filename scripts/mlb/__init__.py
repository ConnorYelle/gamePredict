"""Shared library for the MLB game-prediction pipeline.

Layered design:

* :mod:`mlb.http_client`  -- ``JsonHttpClient`` gateway (HTTP + disk cache)
* :mod:`mlb.stats_api`    -- ``MlbStatsApi`` repository over statsapi.mlb.com
* :mod:`mlb.scraper`      -- ``BaseballReferenceScraper`` (HTML scraping)
* :mod:`mlb.model`        -- ``PredictionModel`` win-probability formula
* :mod:`mlb.config`       -- paths + weight load/save
* services: :mod:`mlb.trainer`, :mod:`mlb.backtester`, :mod:`mlb.slate_grader`
* presentation: :mod:`mlb.social`

The thin scripts in ``scripts/`` are CLI facades over these components.
"""

from . import config
from .http_client import JsonHttpClient
from .model import PredictionModel
from .stats_api import MlbStatsApi

__all__ = ["config", "JsonHttpClient", "MlbStatsApi", "PredictionModel"]
