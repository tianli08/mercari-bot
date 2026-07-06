# 2026-07 Per-Destination Alert Dedupe

This migration moves alert-delivery deduplication in the `listing_alerts` collection from
`channel_id` to `destination_id`. Existing listings remain globally deduped in the listings
collection; this only changes the delivery reservation shape.

## Safe Order

Run these steps against the live MongoDB database in this order:

1. Backfill `destination_id` and `owner_id` on existing alert documents.
2. Drop the old unique index.
3. Deploy the new application code.

The backfill must run before the new `listing_destination_unique` index is created. Until legacy
documents have `destination_id`, MongoDB treats the missing value as `null` for the new unique
compound index, which can collide for multiple legacy alerts sharing the same listing.

## Commands

Backfill existing alert documents:

```javascript
db.listing_alerts.updateMany(
  { destination_id: { $exists: false }, channel_id: { $exists: true } },
  [{ $set: { destination_id: "$channel_id", owner_id: null } }]
)
```

Drop the old unique index:

```javascript
db.listing_alerts.dropIndex("listing_channel_unique")
```

Deploy the new code after those commands complete. Deploying first is only safe if the backfill is
run immediately before startup creates the new index; the recommended order is backfill, drop old
index, then deploy.

It is fine to leave the legacy `channel_id` field on old documents. New alert documents will write
`destination_id` and `owner_id`, and will not write `channel_id`.
