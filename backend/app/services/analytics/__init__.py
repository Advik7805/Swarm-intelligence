"""
HiveMind Analytics — Opinion Dynamics & Social Network Intelligence

A post-simulation analysis layer that turns raw OASIS simulation logs into
quantitative social-science insights:

  * HIVE-Sent      — bilingual (EN/ZH) hybrid lexicon sentiment + emotion engine
  * NetworkX graph  — influence ranking (PageRank/centrality) + community detection
  * Persona clustering — TF-IDF + KMeans archetype discovery
  * Confidence engine — statistical convergence scoring for predictions
  * SQLite store    — durable run history & metrics
"""

from .pipeline import AnalyticsPipeline, run_analytics_async
from .db import AnalyticsDB

__all__ = ["AnalyticsPipeline", "run_analytics_async", "AnalyticsDB"]
