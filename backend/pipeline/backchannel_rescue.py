"""
Rescue pass for short interjections the whole-file decode dropped.

The offline pipeline runs the recogniser once over the entire recording. That is
the right call for accuracy and for speed, but it has one predictable blind
spot: a 200-350 ms "avunu", "yeah" or "ah" between two longer turns can be
swallowed by the decoder, and a single missing token is enough for the whole
region to disappear from the transcript. The user is left looking at audio that
diarisation proved contained speech, with nothing on that lane.

This pass finds those regions -- diarised speech that came back with no text --
and re-decodes each one *in isolation* with a little acoustic context on either
side. Decoding a 300 ms window on its own is a very different problem from
finding it between two long utterances, and the same ``transcribe_interval``
path the timeline's re-transcribe button already uses is exactly the right tool.

Only regions that are genuinely short and genuinely empty are re-decoded. A
segment the recogniser already covered is never touched, and a long untranscribed
stretch is left alone because a second full decode of it would be both slow and
pointless.
"""
import logging
from typing import List, Optional, Tuple

from ..models.asr import ASROptions, ASRResult, ASRToken

logger = logging.getLogger(__name__)

# Longest region worth re-decoding in isolation. Above this the decoder was not
# struggling with the length of the window, so a second pass has nothing to add.
MAX_RESCUE_SEC = 6.0
# Shortest region worth a second pass; below this there is no speech to recover.
MIN_RESCUE_SEC = 0.10
# Acoustic context added either side so the decoder has something to condition on.
CONTEXT_SEC = 0.25
# Two runs are merged into one rescue when they are this close together, so a
# backchannel followed by a pause followed by another backchannel is one decode.
MERGE_GAP_SEC = 0.30
# Ceiling on rescue decodes per file. A pathological segmentation should not turn
# into hundreds of extra model calls.
MAX_RESCUES = 24


def find_untranscribed_regions(
    diar_segments,
    tokens: List[ASRToken],
    duration: Optional[float] = None,
) -> List[Tuple[float, float, str]]:
    """
    Short diarised regions with no recognised text.

    Returns ``(start, end, speaker_id)`` for each, padded with acoustic context
    and clipped to the recording, in chronological order.
    """
    if not diar_segments:
        return []

    covered: List[Tuple[float, float]] = [
        (t.start, t.end) for t in tokens if getattr(t, "end", 0.0) > getattr(t, "start", 0.0)
    ]
    covered.sort()

    def has_text(start: float, end: float) -> bool:
        return any(max(0.0, min(end, c_end) - max(start, c_start)) > 0.02 for c_start, c_end in covered)

    regions: List[Tuple[float, float, str]] = []
    for segment in sorted(diar_segments, key=lambda s: s.start):
        start, end = segment.start, segment.end
        if end - start < MIN_RESCUE_SEC or end - start > MAX_RESCUE_SEC:
            continue
        if has_text(start, end):
            continue
        regions.append((max(0.0, start - CONTEXT_SEC), end + CONTEXT_SEC, segment.speaker_id))

    if duration and duration > 0:
        regions = [
            (lo, min(hi, duration), spk) for lo, hi, spk in regions if min(hi, duration) - lo > MIN_RESCUE_SEC
        ]

    return _merge_close(regions)[:MAX_RESCUES]


def _merge_close(regions: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
    """Collapses rescues for the same speaker that sit within ``MERGE_GAP_SEC``."""
    merged: List[Tuple[float, float, str]] = []
    for start, end, speaker in regions:
        if merged and merged[-1][2] == speaker and start - merged[-1][1] <= MERGE_GAP_SEC:
            previous = merged[-1]
            merged[-1] = (previous[0], max(previous[1], end), speaker)
        else:
            merged.append((start, end, speaker))
    return merged


async def rescue_backchannels(
    asr_provider,
    audio_file_path: str,
    diar_segments,
    asr_tokens: List[ASRToken],
    options: ASROptions,
    duration: Optional[float] = None,
) -> Tuple[List[ASRToken], int]:
    """
    Re-decodes untranscribed short regions and returns the recovered tokens.

    Returns ``(all_tokens, rescued_count)``. Any provider failure is contained:
    the pipeline keeps the original tokens rather than failing the whole job over
    a rescue pass, which is strictly an improvement pass.
    """
    regions = find_untranscribed_regions(diar_segments, asr_tokens, duration)
    if not regions:
        return asr_tokens, 0

    logger.info("Rescuing %d untranscribed short region(s)", len(regions))

    recovered: List[ASRToken] = []
    for start, end, _speaker in regions:
        try:
            result = await asr_provider.transcribe_interval(audio_file_path, start, end, options)
        except NotImplementedError:
            logger.debug("Provider cannot decode an interval; skipping rescue pass")
            return asr_tokens, 0
        except Exception as exc:  # noqa: BLE001 - a rescue failure must not fail the run
            logger.warning("Backchannel rescue failed for %.2f-%.2f: %s", start, end, exc)
            continue

        text = (result.transcript or "").strip()
        if not text:
            continue
        recovered.extend(_inside(result, start, end))

    if not recovered:
        return asr_tokens, 0

    logger.info("Recovered %d token(s) from %d region(s)", len(recovered), len(regions))
    combined = sorted(asr_tokens + recovered, key=lambda t: (t.start, t.end))
    return combined, len(recovered)


def _inside(result: ASRResult, start: float, end: float) -> List[ASRToken]:
    """
    Tokens the interval decode produced, clamped back into the original window.

    ``transcribe_interval`` prepends context, so its timestamps are rebased
    already; this only guards against a provider that reports absolute times
    outside the range it was asked about.
    """
    kept: List[ASRToken] = []
    for token in result.tokens or []:
        if token.end <= start or token.start >= end:
            continue
        token.start = max(start, token.start)
        token.end = min(end, max(token.start, token.end))
        if token.end > token.start and token.text.strip():
            kept.append(token)
    return kept
