from src.segment_row import segment_from_row


def test_segment_from_row_reads_the_517_dataset_columns():
    row = (
        "V007_P031_S002_SCENE_001",   # segment_id
        "V007_P031_S002",             # source_segment_id
        "V007_Z7u5SNDq0jw",           # video_id
        "P031",                       # place_id
        "충주 중앙탑공원",              # place_name
        "충청북도",                     # region
        "충주시",                      # city
        "사랑의 불시착",                # drama_title
        0.0,                          # start_time
        3.75,                         # end_time
        "A nighttime view of a brightly lit bridge over calm water.",  # description (caption column)
        "summer",                     # season
        "night",                      # time_of_day
        "keyframes/V007_Z7u5SNDq0jw/V007_P031_S002_SCENE_001.jpg",  # keyframe_path
        ["peaceful", "calm", "serene"],           # mood
        ["walking", "strolling"],                 # activity
        ["bridge", "water", "lights"],             # scene_elements
        ["K드라마성지"],                            # k_culture_elements
    )
    segment = segment_from_row(row)
    assert segment["segment_id"] == "V007_P031_S002_SCENE_001"
    assert segment["source_segment_id"] == "V007_P031_S002"
    assert segment["place_id"] == "P031"
    assert segment["place_name"] == "충주 중앙탑공원"
    assert segment["region"] == "충청북도"
    assert segment["city"] == "충주시"
    assert segment["drama_title"] == "사랑의 불시착"
    assert segment["description"] == "A nighttime view of a brightly lit bridge over calm water."
    assert segment["season"] == "summer"
    assert segment["time_of_day"] == "night"
    assert segment["mood"] == ["peaceful", "calm", "serene"]
    assert segment["activity"] == ["walking", "strolling"]
    assert segment["scene_elements"] == ["bridge", "water", "lights"]
    assert segment["k_culture_elements"] == ["K드라마성지"]
