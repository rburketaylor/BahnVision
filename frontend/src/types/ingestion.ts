/**
 * Ingestion status types
 * Types for GTFS static feed and realtime harvester status
 */

export interface GTFSFeedStatus {
  feed_id: string | null
  feed_url: string | null
  downloaded_at: string | null
  feed_start_date: string | null
  feed_end_date: string | null
  stop_count: number
  route_count: number
  trip_count: number
  is_expired: boolean
}

export interface GTFSRTHarvesterStatus {
  is_running: boolean
  last_harvest_at: string | null
  stations_updated_last_harvest: number
  total_stats_records: number
}

export interface IngestionStatus {
  gtfs_feed: GTFSFeedStatus
  gtfs_rt_harvester: GTFSRTHarvesterStatus
}
