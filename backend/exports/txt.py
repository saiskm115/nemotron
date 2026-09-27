from typing import List, Dict
from ..models.turn import Turn
from ..models.speaker import Speaker

def format_timestamp_clock(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    return f"{hrs:02d}:{mins:02d}:{secs:02d}"

def export_txt(turns: List[Turn], speakers: List[Speaker], include_translation: bool = False) -> str:
    spk_map: Dict[str, str] = {s.id: s.display_name for s in speakers}
    sections: List[str] = []

    for turn in turns:
        spk_name = spk_map.get(turn.speaker_id, turn.speaker_id)
        time_str = format_timestamp_clock(turn.start)
        block = f"[{spk_name}] [{time_str}]\n\n{turn.text}"
        if include_translation and turn.translated_text:
            block += f"\n\nTranslation:\n{turn.translated_text}"
        sections.append(block)

    return "\n\n---\n\n".join(sections)
