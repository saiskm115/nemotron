import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { BookMarked, Plus, X, UploadCloud, Tag } from 'lucide-react';

export const CustomVocabulary: React.FC = () => {
  const { session, addKeyterm, removeKeyterm } = useSessionStore();
  const [newTerm, setNewTerm] = useState('');

  const keyterms = session?.settings?.keyterms || [
    'Ramesh', 'HustleLabs', 'Sarvam', 'Nemotron', 'NVIDIA', 'Dhan', 'Upstox', 'Oracle Fusion HCM'
  ];

  const handleAdd = () => {
    if (newTerm.trim()) {
      addKeyterm(newTerm.trim());
      setNewTerm('');
    }
  };

  const handleCsvImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      const text = event.target?.result as string;
      const terms = text.split(/[,\n\r]+/).map(t => t.trim()).filter(Boolean);
      terms.forEach(t => addKeyterm(t));
    };
    reader.readAsText(file);
  };

  return (
    <div className="glass-panel p-4 flex flex-col gap-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/5 pb-3">
        <div className="flex items-center gap-2">
          <BookMarked size={18} className="text-cyan-400" />
          <h3 className="font-semibold text-sm text-slate-100">Custom Domain Vocabulary (Keyterms)</h3>
        </div>

        <label className="btn btn-secondary px-3 py-1.5 text-xs cursor-pointer">
          <UploadCloud size={14} />
          <span>Import CSV</span>
          <input
            type="file"
            accept=".csv,.txt"
            onChange={handleCsvImport}
            className="hidden"
          />
        </label>
      </div>

      <p className="text-xs text-slate-400">
        Keyterms are injected directly into AutoTinglishSub Whisper ASR prompts to guarantee high-accuracy transcription of Indian names, Hyderabad locations, and English technical terms.
      </p>

      {/* Add Input */}
      <div className="flex gap-2">
        <input
          type="text"
          placeholder="Add keyterm (e.g. Hyderabad, Cyber Towers, UPI, Ramesh)..."
          value={newTerm}
          onChange={(e) => setNewTerm(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
          className="flex-1 bg-slate-950 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
        />
        <button
          onClick={handleAdd}
          className="btn btn-primary px-3 py-1.5 text-xs"
        >
          <Plus size={14} />
          <span>Add Term</span>
        </button>
      </div>

      {/* Term Badges */}
      <div className="flex flex-wrap gap-2 pt-2">
        {keyterms.map((term) => (
          <span
            key={term}
            className="inline-flex items-center gap-1.5 bg-slate-900 border border-white/10 px-2.5 py-1 rounded-full text-xs text-slate-200"
          >
            <Tag size={11} className="text-cyan-400" />
            <span>{term}</span>
            <button
              onClick={() => removeKeyterm(term)}
              className="text-slate-500 hover:text-rose-400 ml-0.5"
            >
              <X size={12} />
            </button>
          </span>
        ))}
      </div>
    </div>
  );
};
