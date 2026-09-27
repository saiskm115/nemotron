import React, { useState } from 'react';
import { useSessionStore } from '../../stores/sessionStore';
import { BookMarked, Plus, X, UploadCloud, Tag } from 'lucide-react';

interface VocabularyModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const VocabularyModal: React.FC<VocabularyModalProps> = ({ isOpen, onClose }) => {
  const { session, addKeyterm, removeKeyterm } = useSessionStore();
  const [newTerm, setNewTerm] = useState('');

  if (!isOpen) return null;

  const keyterms = session?.settings?.keyterms || [
    'Ramesh', 'HustleLabs', 'Sarvam', 'Nemotron', 'NVIDIA', 'Dhan', 'Upstox', 'Oracle Fusion HCM', 'Gachibowli', 'Cyber Towers'
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
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content animate-fade-in" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="flex items-center justify-between border-b border-white/10 pb-3">
          <div className="flex items-center gap-2">
            <BookMarked size={18} className="text-cyan-400" />
            <h3 className="font-semibold text-sm text-slate-100">Custom Domain Vocabulary (Keyterms)</h3>
          </div>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-white rounded hover:bg-slate-800">
            <X size={16} />
          </button>
        </div>

        <p className="text-xs text-slate-400">
          Keyterms are injected directly into AutoTinglishSub Whisper ASR prompts to guarantee high-accuracy transcription of Indian names, Hyderabad locations, and English technical terms.
        </p>

        {/* Input */}
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="Add keyterm (e.g. Hyderabad, Cyber Towers, UPI, Ramesh)..."
            value={newTerm}
            onChange={(e) => setNewTerm(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
            className="flex-1 bg-slate-950 px-3 py-1.5 rounded-lg border border-white/10 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-cyan-400"
          />
          <button onClick={handleAdd} className="btn btn-primary px-3 py-1.5 text-xs">
            <Plus size={14} />
            <span>Add Term</span>
          </button>
        </div>

        {/* Term Badges */}
        <div className="flex flex-wrap gap-1.5 max-h-52 overflow-y-auto p-2 bg-slate-950 rounded-lg border border-white/5">
          {keyterms.map((term) => (
            <span
              key={term}
              className="inline-flex items-center gap-1.5 bg-slate-900 border border-white/10 px-2 py-0.5 rounded-md text-xs text-slate-200"
            >
              <Tag size={10} className="text-cyan-400" />
              <span>{term}</span>
              <button
                onClick={() => removeKeyterm(term)}
                className="text-slate-500 hover:text-rose-400 ml-0.5"
              >
                <X size={11} />
              </button>
            </span>
          ))}
        </div>

        {/* Footer */}
        <div className="flex justify-between items-center pt-2 border-t border-white/5">
          <label className="btn btn-secondary px-3 py-1 text-xs cursor-pointer">
            <UploadCloud size={14} />
            <span>Import CSV</span>
            <input type="file" accept=".csv,.txt" onChange={handleCsvImport} className="hidden" />
          </label>
          <button onClick={onClose} className="btn btn-primary px-4 py-1.5 text-xs">
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
