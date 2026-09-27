from typing import List, Dict
from ..models.turn import Turn
from ..models.speaker import Speaker

def format_timestamp_vtt(seconds: float) -> str:
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def export_vtt(turns: List[Turn], speakers: List[Speaker], include_translation: bool = False) -> str:
    spk_map: Dict[str, str] = {s.id: s.display_name for s in speakers}
    lines: List[str] = ["WEBVTT", ""]

    for idx, turn in enumerate(turns, 1):
        spk_name = spk_map.get(turn.speaker_id, turn.speaker_id)
        start_str = format_timestamp_vtt(turn.start)
        end_str = format_timestamp_vtt(turn.end)

        lines.append(f"{idx}")
        lines.append(f"{start_str} --> {end_str}")
        content = f"<v {spk_name}>{turn.text}</v>"
        if include_translation and turn.translated_text:
            content += f"\n({turn.translated_text})"
        lines.append(content)
        lines.append("")

    return "\n".join(lines)
