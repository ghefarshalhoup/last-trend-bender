/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Origin of the FastAPI service for production builds. Empty = same origin. */
  readonly VITE_API_BASE_URL?: string
}
