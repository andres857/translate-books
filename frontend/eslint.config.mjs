import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // `{ [key]: _, ...rest }` es la forma de quitar una clave de un objeto sin mutarlo
      "@typescript-eslint/no-unused-vars": ["warn", { ignoreRestSiblings: true }],
      // 20 efectos hacen setState al cambiar sus dependencias (reinicios de vista y cargas). Corregirlos es un
      // refactor propio: docs/frontend-review/16-setstate-en-efectos.md. Hasta entonces, aviso y no error.
      "react-hooks/set-state-in-effect": "warn",
    },
  },
  globalIgnores([".next/**", "out/**", "build/**", "next-env.d.ts", "test-results/**", "playwright-report/**"]),
]);

export default eslintConfig;
