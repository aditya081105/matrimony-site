import logging
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

logger = logging.getLogger(__name__)

CACHE_KEY_ACTIVE_PLANS = "active_membership_plans"
CACHE_KEY_ALL_CITIES = "all_cities_list"
CACHE_KEY_ALL_CASTES = "all_castes_list"

DEFAULT_CACHE_TIMEOUT = 3600  # 1 hour


def get_active_plans():
    """Cache-aside retrieval for active membership plans."""
    from payments.models import Plan
    plans = cache.get(CACHE_KEY_ACTIVE_PLANS)
    if plans is None:
        plans = list(Plan.objects.filter(is_active=True).order_by('price'))
        cache.set(CACHE_KEY_ACTIVE_PLANS, plans, timeout=DEFAULT_CACHE_TIMEOUT)
        logger.debug("Cache miss for active plans - populated from DB")
    return plans


def get_cached_cities():
    """Cache-aside retrieval for cities."""
    from users.models import City
    cities = cache.get(CACHE_KEY_ALL_CITIES)
    if cities is None:
        cities = list(City.objects.all().order_by('name'))
        cache.set(CACHE_KEY_ALL_CITIES, cities, timeout=DEFAULT_CACHE_TIMEOUT)
        logger.debug("Cache miss for cities - populated from DB")
    return cities


def get_cached_castes():
    """Cache-aside retrieval for legacy castes."""
    from users.models import Caste
    castes = cache.get(CACHE_KEY_ALL_CASTES)
    if castes is None:
        castes = list(Caste.objects.all().order_by('name'))
        cache.set(CACHE_KEY_ALL_CASTES, castes, timeout=DEFAULT_CACHE_TIMEOUT)
        logger.debug("Cache miss for castes - populated from DB")
    return castes


def invalidate_plan_cache():
    cache.delete(CACHE_KEY_ACTIVE_PLANS)
    logger.info("Invalidated active plans cache")


def invalidate_city_cache():
    cache.delete(CACHE_KEY_ALL_CITIES)
    logger.info("Invalidated cities cache")


def invalidate_caste_cache():
    cache.delete(CACHE_KEY_ALL_CASTES)
    logger.info("Invalidated castes cache")
