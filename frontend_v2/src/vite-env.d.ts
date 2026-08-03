/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Show the seeded demo accounts on the login screen in a built bundle.
   * `vite dev` already shows them; this is the explicit opt-in for a demo
   * deployment. Leave unset in production. */
  readonly VITE_SHOW_DEMO_ACCOUNTS?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
