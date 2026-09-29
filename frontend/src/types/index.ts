export interface LanguageSegment {
  text: string;
  language: string;
}

export interface Turn {
  id: string;
  speaker_id: string;
  start: number;
  end: number;
  text: string;
  translated_text?: string;
  source_language?: string;
  language_segments?: LanguageSegment[];
  confidence?: number;
  status: "interim" | "final" | "edited";
  overlap?: boolean;
  overlap_speakers?: string[];
  source: "model" | "user_edit";
  original_model_text?: string;
  original_model_speaker_id?: string;
  original_start?: number;
  original_end?: number;
  translation_status?: "not_requested" | "pending" | "complete" | "failed";
  /** True when Nemotron detected speaker activity but ASR has no transcript coverage.
   *  These are timeline-only entries \u2014 shown in the diarization track but hidden from transcript. */
  speech_only?: boolean;
  created_at: string;
  updated_at: string;
}

export interface Speaker {
  id: string;
  display_name: string;
  color: string;
  total_speaking_time: number;
  turn_count: number;
  first_seen: number;
  last_seen: number;
  model_label: string;
}

/** The kinds of label a reviewer can draw on the timeline. */
export type AnnotationLabel =
  | "note"
  | "important"
  | "question"
  | "action_item"
  | "review"
  | "backchannel"
  | "speaker_label"
  | "error";

export const ANNOTATION_LABELS: {
  id: AnnotationLabel;
  label: string;
  color: string;
  hint: string;
}[] = [
  { id: "note", label: "Note", color: "#38bdf8", hint: "General observation" },
  { id: "important", label: "Important", color: "#f59e0b", hint: "Must not be missed" },
  { id: "question", label: "Question", color: "#a855f7", hint: "Open question" },
  { id: "action_item", label: "Action", color: "#10b981", hint: "Someone has to do this" },
  { id: "review", label: "Review", color: "#06b6d4", hint: "Needs a second pass" },
  { id: "backchannel", label: "Backchannel", color: "#ec4899", hint: "Short interjection" },
  { id: "speaker_label", label: "Speaker", color: "#f43f5e", hint: "Assign who speaks here" },
  { id: "error", label: "Error", color: "#ef4444", hint: "Diarisation or ASR is wrong" },
];

/** A manual label drawn on the timeline by a reviewer. */
export interface Annotation {
  id: string;
  start: number;
  end: number;
  text: string;
  label: AnnotationLabel;
  /** Which voice this label is about. Null means "this region". */
  speaker_id?: string | null;
  turn_id?: string | null;
  source: "manual" | "model";
  author?: string | null;
  created_at: string;
  updated_at: string;
}

export interface SessionSettings {
  asr_mode: "normal" | "codemix" | "verbatim";
  /** Registry id of the transcription model used for this session. */
  asr_model: string;
  primary_language: string;
  target_language: string;
  auto_translate: boolean;
  keyterms: string[];
  show_interim: boolean;
  display_mode: "original" | "translation" | "both";
  transliteration_mode: "script" | "roman" | "codemix";
}

/** A selectable speech-to-text model as reported by GET /api/audio/models. */
export interface ASRModelOption {
  id: string;
  label: string;
  description: string;
  languages: string[];
  local: boolean;
  recommended: boolean;
  notes: string;
  available: boolean;
  selected: boolean;
  requires_api_key?: string;
  unavailable_reason?: string;
}

export interface AudioMetadata {
  duration_sec: number;
  sample_rate: number;
  channels: number;
  sample_count: number;
  rms_db: number;
  peak_db?: number;
  /** Coarse waveform envelope (peak_levels[0]). */
  peaks: number[];
  /** Resolution pyramid, coarsest first. The timeline picks a level from its zoom. */
  peak_levels?: number[][];
}

export interface Session {
  id: string;
  title: string;
  created_at: string;
  duration: number;
  audio_source: "file" | "microphone" | "stream";
  audio_file_path?: string;
  source_languages: string[];
  target_language?: string;
  speakers: Speaker[];
  turns: Turn[];
  /** Manual labels drawn on the timeline by a reviewer. */
  annotations?: Annotation[];
  processing_status: "uploading" | "processing" | "complete" | "failed";
  error_message?: string;
  mode: "live" | "offline";
  settings: SessionSettings;
  metadata?: Record<string, any>;
}

export interface BenchmarkResult {
  provider: string;
  wer: number;
  cer: number;
  latency_sec: number;
  language_detection: string;
  codemix_preservation: string;
  timestamp_quality: string;
}
