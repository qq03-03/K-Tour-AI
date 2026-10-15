export function mapSearchResponse(results) {
  const maxFinalScore = results.reduce((max, item) => Math.max(max, item.final_score), 0)

  return results.map((item) => ({
    uid: item.segment_id,
    segment_id: item.segment_id,
    video_id: item.video_id,
    place_id: item.place_id,
    place_name: item.place_name,
    region: item.region,
    city: item.city,
    drama_title: item.drama_title,
    start_time: item.start_time,
    end_time: item.end_time,
    season: item.season,
    time_of_day: item.time_of_day,
    description: item.description,
    mood: item.mood,
    activity: item.activity,
    scene_elements: item.scene_elements,
    keyframe_path: item.keyframe_path,
    similarity: maxFinalScore > 0 ? item.final_score / maxFinalScore : 0,
  }))
}
