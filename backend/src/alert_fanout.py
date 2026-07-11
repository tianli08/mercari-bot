"""Tenant-aware alert fan-out for persisted marketplace listings."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

import aiohttp
import discord

from . import database
from .destinations import DestinationRecord, DestinationType
from .discord_messages import build_listing_embed
from .keyword_registry import RegistrySubscriber
from .listings import ListingRecord, Marketplace
from .logging_utils import ContextLoggerAdapter, get_logger, log_exception
from .watchlists import WatchlistRecord

fanout_logger = get_logger("fanout")


@dataclass(frozen=True, slots=True)
class ScrapeResult:
    """A canonical listing plus the result of the persistence stage."""

    listing: ListingRecord
    is_new_listing: bool


class DestinationAlertSender(Protocol):
    """Callable transport for one tenant destination alert."""

    async def __call__(self, destination: DestinationRecord, listing: ListingRecord) -> None:
        """Send one listing to one destination."""
        ...


@dataclass(frozen=True, slots=True)
class LegacyDeliveryTarget:
    """Legacy bot-channel delivery target used during the SaaS migration."""

    destination_id: str
    send_listing: Callable[[ListingRecord], Awaitable[None]]


@dataclass(frozen=True, slots=True)
class _DeliveryRoute:
    owner_id: str
    watchlist: WatchlistRecord
    destination: DestinationRecord


@dataclass(frozen=True, slots=True)
class DiscordWebhookSender:
    """Discord webhook transport backed by a shared aiohttp session."""

    session: aiohttp.ClientSession

    async def __call__(self, destination: DestinationRecord, listing: ListingRecord) -> None:
        """Send the listing embed through the destination's Discord webhook."""
        webhook = discord.Webhook.from_url(destination.webhook_url(), session=self.session)
        await webhook.send(embed=build_listing_embed(listing))


async def fan_out_listing_alerts(
    *,
    marketplace: Marketplace,
    keyword: str,
    scrape_results: Sequence[ScrapeResult],
    should_send_listing: Callable[[bool], bool],
    observed_at: datetime,
    destination_sender: DestinationAlertSender,
    legacy_alerts_enabled: bool,
    legacy_target_factory: Callable[[], LegacyDeliveryTarget | None] | None = None,
    logger: ContextLoggerAdapter | None = None,
) -> None:
    """Fan out newly persisted scrape results to subscribed tenant destinations."""
    active_logger = logger or fanout_logger
    alertable_results = [result for result in scrape_results if should_send_listing(result.is_new_listing)]
    suppressed_count = len(scrape_results) - len(alertable_results)
    if suppressed_count:
        active_logger.debug(
            "Suppressed listing alerts by newness gate",
            context={"marketplace": marketplace, "keyword": keyword, "listings": suppressed_count},
        )

    try:
        registry_entry = await database.get_registry_entry(marketplace, keyword)
    except Exception as exc:
        log_exception(
            active_logger,
            "Failed to resolve keyword registry for fan-out",
            exc,
            marketplace=marketplace,
            keyword=keyword,
        )
        return

    subscribers = registry_entry.subscribers if registry_entry is not None else []
    active_logger.info(
        "Fan-out subscribers resolved",
        context={
            "marketplace": marketplace,
            "keyword": keyword,
            "subscriber_count": len(subscribers),
            "alertable_listings": len(alertable_results),
        },
    )

    if not alertable_results:
        return

    if not subscribers:
        await _deliver_legacy_alerts(
            marketplace=marketplace,
            keyword=keyword,
            scrape_results=alertable_results,
            observed_at=observed_at,
            legacy_alerts_enabled=legacy_alerts_enabled,
            legacy_target_factory=legacy_target_factory,
            logger=active_logger,
        )
        return

    try:
        routes = await _load_delivery_routes(
            marketplace=marketplace,
            keyword=keyword,
            subscribers=subscribers,
            logger=active_logger,
        )
    except Exception as exc:
        log_exception(
            active_logger,
            "Failed to resolve tenant delivery routes",
            exc,
            marketplace=marketplace,
            keyword=keyword,
        )
        return

    attempted_delivery_keys: set[tuple[str, str]] = set()
    for result in alertable_results:
        for route in routes:
            listing = result.listing
            if not route.watchlist.filters.matches(listing.price_value, listing.status):
                active_logger.debug(
                    "Skipping listing for watchlist filters",
                    context={
                        "marketplace": marketplace,
                        "keyword": keyword,
                        "listing_id": listing.canonical_id,
                        "owner_id": route.owner_id,
                        "watchlist_id": route.watchlist._id,
                    },
                )
                continue

            delivery_key = (listing.canonical_id, route.destination._id)
            if delivery_key in attempted_delivery_keys:
                active_logger.debug(
                    "Skipping duplicate fan-out destination route",
                    context={
                        "marketplace": marketplace,
                        "keyword": keyword,
                        "listing_id": listing.canonical_id,
                        "owner_id": route.owner_id,
                        "watchlist_id": route.watchlist._id,
                        "destination_id": route.destination._id,
                    },
                )
                continue
            attempted_delivery_keys.add(delivery_key)

            await _reserve_send_mark(
                listing=listing,
                destination_id=route.destination._id,
                owner_id=route.owner_id,
                observed_at=observed_at,
                send_alert=lambda route=route, listing=listing: destination_sender(route.destination, listing),
                logger=active_logger,
                log_context={
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "listing_id": listing.canonical_id,
                    "owner_id": route.owner_id,
                    "watchlist_id": route.watchlist._id,
                    "destination_id": route.destination._id,
                    "delivery_mode": "webhook",
                },
            )


async def _load_delivery_routes(
    *,
    marketplace: Marketplace,
    keyword: str,
    subscribers: Sequence[RegistrySubscriber],
    logger: ContextLoggerAdapter,
) -> list[_DeliveryRoute]:
    watchlists = await database.get_watchlists_by_ids(subscriber.watchlist_id for subscriber in subscribers)
    destination_ids = {watchlist.destination_id for watchlist in watchlists.values() if watchlist.enabled}
    destinations = await database.get_destinations_by_ids(destination_ids)

    routes: list[_DeliveryRoute] = []
    for subscriber in subscribers:
        watchlist = watchlists.get(subscriber.watchlist_id)
        if watchlist is None:
            logger.warning(
                "Skipping subscriber with missing watchlist",
                context={
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "owner_id": subscriber.owner_id,
                    "watchlist_id": subscriber.watchlist_id,
                },
            )
            continue

        if not watchlist.enabled:
            logger.debug(
                "Skipping disabled watchlist subscriber",
                context={
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "owner_id": subscriber.owner_id,
                    "watchlist_id": subscriber.watchlist_id,
                },
            )
            continue

        destination = destinations.get(watchlist.destination_id)
        if destination is None:
            logger.warning(
                "Skipping watchlist with missing destination",
                context={
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "owner_id": subscriber.owner_id,
                    "watchlist_id": watchlist._id,
                    "destination_id": watchlist.destination_id,
                },
            )
            continue

        if destination.type != DestinationType.DISCORD_WEBHOOK:
            logger.warning(
                "Skipping unsupported destination type",
                context={
                    "marketplace": marketplace,
                    "keyword": keyword,
                    "owner_id": subscriber.owner_id,
                    "watchlist_id": watchlist._id,
                    "destination_id": destination._id,
                    "destination_type": destination.type.value,
                },
            )
            continue

        routes.append(_DeliveryRoute(owner_id=subscriber.owner_id, watchlist=watchlist, destination=destination))

    logger.info(
        "Fan-out delivery routes resolved",
        context={
            "marketplace": marketplace,
            "keyword": keyword,
            "subscriber_count": len(subscribers),
            "route_count": len(routes),
        },
    )
    return routes


async def _deliver_legacy_alerts(
    *,
    marketplace: Marketplace,
    keyword: str,
    scrape_results: Sequence[ScrapeResult],
    observed_at: datetime,
    legacy_alerts_enabled: bool,
    legacy_target_factory: Callable[[], LegacyDeliveryTarget | None] | None,
    logger: ContextLoggerAdapter,
) -> None:
    if not legacy_alerts_enabled:
        logger.info(
            "Skipping legacy channel fallback because it is disabled",
            context={"marketplace": marketplace, "keyword": keyword},
        )
        return
    if legacy_target_factory is None:
        logger.info(
            "Skipping legacy channel fallback because no target factory is configured",
            context={"marketplace": marketplace, "keyword": keyword},
        )
        return

    # Legacy bot-channel delivery is kept only for the migration window and is removed in a later step.
    legacy_target = legacy_target_factory()
    if legacy_target is None:
        logger.warning(
            "Skipping legacy channel fallback because no channel is available",
            context={"marketplace": marketplace, "keyword": keyword},
        )
        return

    logger.info(
        "Using legacy channel alert fallback",
        context={
            "marketplace": marketplace,
            "keyword": keyword,
            "destination_id": legacy_target.destination_id,
            "listings": len(scrape_results),
        },
    )
    for result in scrape_results:
        await _reserve_send_mark(
            listing=result.listing,
            destination_id=legacy_target.destination_id,
            owner_id=None,
            observed_at=observed_at,
            send_alert=lambda result=result: legacy_target.send_listing(result.listing),
            logger=logger,
            log_context={
                "marketplace": marketplace,
                "keyword": keyword,
                "listing_id": result.listing.canonical_id,
                "destination_id": legacy_target.destination_id,
                "delivery_mode": "legacy_channel",
            },
        )


async def _reserve_send_mark(
    *,
    listing: ListingRecord,
    destination_id: str,
    owner_id: str | None,
    observed_at: datetime,
    send_alert: Callable[[], Awaitable[None]],
    logger: ContextLoggerAdapter,
    log_context: dict[str, object],
) -> None:
    delivery_id = None
    message_sent = False
    try:
        delivery_id = await database.reserve_alert_delivery(
            listing,
            destination_id=destination_id,
            owner_id=owner_id,
            observed_at=observed_at,
        )
        if delivery_id is None:
            logger.debug("Skipping already reserved alert delivery", context=log_context)
            return

        await send_alert()
        message_sent = True
        await database.mark_alert_delivery_sent(
            delivery_id,
            listing.canonical_id,
            delivered_at=observed_at,
        )
        logger.info("Alert delivery sent", context={**log_context, "delivery_id": delivery_id})
    except Exception as exc:
        if delivery_id is not None and not message_sent:
            await _discard_pending_delivery(delivery_id, listing, logger)

        message = "Alert delivery bookkeeping failed" if message_sent else "Alert delivery failed"
        log_exception(logger, message, exc, **log_context, delivery_id=delivery_id)


async def _discard_pending_delivery(
    delivery_id: str,
    listing: ListingRecord,
    logger: ContextLoggerAdapter,
) -> None:
    try:
        await database.discard_pending_alert_delivery(delivery_id)
    except Exception as exc:
        log_exception(
            logger,
            "Failed to discard pending alert reservation",
            exc,
            delivery_id=delivery_id,
            listing_id=listing.canonical_id,
        )
