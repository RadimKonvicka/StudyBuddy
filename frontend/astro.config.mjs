// Astro běží ve statickém režimu – stránky se postaví jako HTML a data si načtou v prohlížeči z API.
import { defineConfig } from "astro/config";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  output: "static",
  vite: { plugins: [tailwindcss()] },
});
