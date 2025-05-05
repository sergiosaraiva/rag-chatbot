/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_PROJECT_NAME: string
  readonly VITE_CHATBOT_NAME: string
  readonly VITE_CHATBOT_USER: string
  readonly VITE_MAX_MESSAGES: string
  // Add more env variables as needed
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}