import React, { useEffect, useState } from 'react';
import { api } from '../../services/api';
import { toast } from '../../stores/toastStore';
import { BarChart3, Play, Loader2, Info } from 'lucide-react';

interface ReferenceFigures {
  dataset?: string;
  wer?: string;
  cer?: string;
  latin_preservation?: string;
  real_time_factor?: string;
  caveat?: string;
}

interface BenchmarkModel {
  id: string;
  label: string;
  local: boolean;
  recommended: boolean;
  available: boolean;
  notes: string;
  reference: ReferenceFigures | null;
}

interface MeasuredResult {
  model_id: string;
  status: 'ok' | 'error' | 'unavailable';
  error?: string;
  wer?: number;
  cer?: number;
  latency_sec?: number;
  real_time_factor?: number;
  token_count?: number;
  script?: string;
  latin_word_ratio?: number;
  transcript?: string;
}

const pct = (value?: number) => (value == null ? '—' : `${(value * 100).toFixed(1)}%`);

export const BenchmarkScreen: React.FC = () => {
  const [models, setModels] = useState<BenchmarkModel[]>([]);
  const [measured, setMeasured] = useState<MeasuredResult[] | null>(null);
  const [duration, setDuration] = useState<number | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    api.getBenchmarkReference()
      .then((data) => setModels(data.models))
      .catch((e) => toast.error(e.message, 'Benchmark Unavailable'));
  }, []);

  const runMeasurement = async () => {
    setRunning(true);
    setMeasured(null);
    try {
      const data = await api.runBenchmark({});
      const results: MeasuredResult[] = data.results ?? [];
      setMeasured(results);
      setDuration(data.audio_duration_sec);
      toast.success(
        `Scored ${results.filter((r: MeasuredResult) => r.status === 'ok').length} model(s) on ${data.audio_duration_sec}s of audio`,
        'Benchmark Complete'
      );
    } catch (e: any) {
      toast.error(e.message || 'Benchmark failed', 'Benchmark Failed');
    } finally {
      setRunning(false);
    }
  };

  const measuredById = new Map((measured ?? []).map((r) => [r.model_id, r]));

  return (
    <div className="glass-panel p-5 flex flex-col gap-4">
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <BarChart3 size={18} className="text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-100">ASR Model Comparison (Telugu + English code-mixed)</h3>
        </div>
        <button
          onClick={runMeasurement}
          disabled={running}
          className="btn btn-primary px-3 py-1.5 text-xs flex items-center gap-1.5 disabled:opacity-50"
        >
          {running ? <Loader2 size={12} className="animate-spin" /> : <Play size={12} />}
          {running ? 'Measuring…' : 'Measure on this machine'}
        </button>
      </div>

      <div className="flex items-start gap-2 rounded-lg border border-amber-500/20 bg-amber-950/20 p-3">
        <Info size={14} className="text-amber-400 mt-0.5 shrink-0" />
        <p className="text-[11px] text-amber-200/90 leading-relaxed">
          The <strong>Published</strong> column quotes each model's authors on their own test set — those
          numbers come from different corpora and are <em>not</em> comparable across rows. The
          <strong> Measured</strong> columns are computed by actually running each model on the same
          audio and reference transcript on this machine. Trust the measured columns for comparisons.
        </p>
      </div>

      <div className="overflow-x-auto rounded-xl border border-white/5 bg-slate-950/60">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-white/10 bg-slate-900/80 text-slate-300 font-medium">
              <th className="p-3">Engine</th>
              <th className="p-3">Measured WER ↓</th>
              <th className="p-3">Measured CER ↓</th>
              <th className="p-3">Measured RTF ↓</th>
              <th className="p-3">Script</th>
              <th className="p-3">Published WER / CER</th>
              <th className="p-3">Evaluation set</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {models.map((model) => {
              const result = measuredById.get(model.id);
              const measuredOk = result?.status === 'ok';
              return (
                <tr
                  key={model.id}
                  className={`${model.recommended ? 'bg-cyan-950/20' : ''} text-slate-300 hover:bg-slate-900/40`}
                >
                  <td className="p-3 font-sans">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-slate-100">{model.label}</span>
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 border border-slate-700">
                        {model.local ? 'On-device' : 'Cloud'}
                      </span>
                      {model.recommended && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300 border border-cyan-500/30">
                          Recommended
                        </span>
                      )}
                      {!model.available && (
                        <span className="text-[10px] px-1.5 py-0.5 rounded bg-rose-500/20 text-rose-300 border border-rose-500/30">
                          Unavailable
                        </span>
                      )}
                    </div>
                    {model.notes && <div className="text-[10px] text-slate-500 mt-1">{model.notes}</div>}
                  </td>
                  <td className="p-3 font-mono">{measuredOk ? pct(result.wer) : '—'}</td>
                  <td className="p-3 font-mono">{measuredOk ? pct(result.cer) : '—'}</td>
                  <td className="p-3 font-mono">
                    {measuredOk ? `${result.real_time_factor}×` : '—'}
                    {measuredOk && result.latency_sec != null && (
                      <span className="text-slate-500"> ({result.latency_sec}s)</span>
                    )}
                  </td>
                  <td className="p-3 font-mono">{measuredOk ? (result.script ?? '—') : '—'}</td>
                  <td className="p-3 font-mono text-slate-400">
                    {model.reference ? `${model.reference.wer} / ${model.reference.cer}` : '—'}
                  </td>
                  <td className="p-3 font-sans text-[11px] text-slate-400 max-w-[240px]">
                    {model.reference?.dataset ?? '—'}
                    {model.reference?.caveat && (
                      <div className="text-[10px] text-slate-500 mt-0.5">{model.reference.caveat}</div>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {measured && (
        <p className="text-[11px] text-slate-400">
          Measured on {duration}s of the two-speaker Telugu fixture at 16 kHz mono. Lower is better;
          RTF is the fraction of real time the model needed (0.1× = ten times faster than playback).
        </p>
      )}
    </div>
  );
};
