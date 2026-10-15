// Reduces a list of segments to one marker per unique place_id, using the
// confirmed lat/lng from placeCoordinates.js. Segments whose place_id has no
// known coordinates are skipped rather than guessed. dramaTitles collects
// every distinct drama filmed at that place (first-seen order) so the map
// pin's info window can show what was shot there, not just the place name.
export function getMapMarkers(segments, coordinates) {
  const markersByPlaceId = new Map()
  for (const segment of segments) {
    const coord = coordinates[segment.place_id]
    if (!coord) continue

    let marker = markersByPlaceId.get(segment.place_id)
    if (!marker) {
      marker = {
        place_id: segment.place_id,
        label: coord.place_name,
        latitude: coord.latitude,
        longitude: coord.longitude,
        dramaTitles: [],
      }
      markersByPlaceId.set(segment.place_id, marker)
    }
    if (segment.drama_title && !marker.dramaTitles.includes(segment.drama_title)) {
      marker.dramaTitles.push(segment.drama_title)
    }
  }
  return [...markersByPlaceId.values()]
}
