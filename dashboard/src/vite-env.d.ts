/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEFAULT_APPS?: string;
  readonly VITE_DEFAULT_GROUPS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
