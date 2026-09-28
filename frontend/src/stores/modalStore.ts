import { create } from 'zustand';

interface ModalState {
  isUploadOpen: boolean;
  isExportOpen: boolean;
  isSettingsOpen: boolean;
  isVocabularyOpen: boolean;
  isBenchmarkOpen: boolean;
  isObservabilityOpen: boolean;

  openUpload: () => void;
  closeUpload: () => void;
  openExport: () => void;
  closeExport: () => void;
  openSettings: () => void;
  closeSettings: () => void;
  openVocabulary: () => void;
  closeVocabulary: () => void;
  openBenchmark: () => void;
  closeBenchmark: () => void;
  openObservability: () => void;
  closeObservability: () => void;
}

export const useModalStore = create<ModalState>((set) => ({
  isUploadOpen: false,
  isExportOpen: false,
  isSettingsOpen: false,
  isVocabularyOpen: false,
  isBenchmarkOpen: false,
  isObservabilityOpen: false,

  openUpload: () => set({ isUploadOpen: true }),
  closeUpload: () => set({ isUploadOpen: false }),
  openExport: () => set({ isExportOpen: true }),
  closeExport: () => set({ isExportOpen: false }),
  openSettings: () => set({ isSettingsOpen: true }),
  closeSettings: () => set({ isSettingsOpen: false }),
  openVocabulary: () => set({ isVocabularyOpen: true }),
  closeVocabulary: () => set({ isVocabularyOpen: false }),
  openBenchmark: () => set({ isBenchmarkOpen: true }),
  closeBenchmark: () => set({ isBenchmarkOpen: false }),
  openObservability: () => set({ isObservabilityOpen: true }),
  closeObservability: () => set({ isObservabilityOpen: false }),
}));
