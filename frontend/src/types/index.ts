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

export interface SessionSettings {
  asr_mode: "normal" | "codemix" | "verbatim";
  primary_language: string;
  target_language: string;
  auto_translate: boolean;
  keyterms: string[];
  show_interim: boolean;
  display_mode: "original" | "translation" | "both";
  transliteration_mode: "script" | "roman" | "codemix";
}

export interface AudioMetadata {
  duration_sec: number;
  sample_rate: number;
  channels: number;
  sample_count: number;
  rms_db: number;
  peaks: number[];
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
