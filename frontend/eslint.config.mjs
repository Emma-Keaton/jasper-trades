import { defineConfig, globalIgnores } from "eslint/config";
import globals from "globals";

import react from "eslint-plugin-react";
import reactHooks from "eslint-plugin-react-hooks";
import jsxA11y from "eslint-plugin-jsx-a11y";
import importPlugin from "eslint-plugin-import";
import next from "@next/eslint-plugin-next";
import tseslint from "@typescript-eslint/eslint-plugin";
import tsParser from "@typescript-eslint/parser";

// Flat ESLint 9 config.
//
// We intentionally do NOT use `eslint-config-next` here: its CommonJS entry
// requires `@rushstack/eslint-patch/modern-module-resolution`, which cannot
// detect its calling module under ESLint 9's flat config (ESLint removed the
// legacy `config-array-factory` the patch probes for), hard-crashing on every
// run. Instead we compose the equivalent rulesets from the plugins directly,
// which are all hoisted in this project's node_modules.
//
// Rule sets mirror eslint-config-next (recommended + core-web-vitals) plus the
// project's custom overrides that previously lived in `.eslintrc.json`.

const nextRules = {
  ...next.configs.recommended.rules,
  ...next.configs["core-web-vitals"].rules,
};

export default defineConfig([
  globalIgnores(["node_modules/**", ".next/**", "out/**", "build/**", ".git/**", ".venv/**"]),

  {
    files: ["**/*.{js,mjs,cjs,jsx,ts,mts,cts,tsx}"],
    languageOptions: {
      parser: tsParser,
      parserOptions: {
        ecmaVersion: "latest",
        sourceType: "module",
        ecmaFeatures: { jsx: true },
      },
      globals: {
        ...globals.browser,
        ...globals.node,
      },
    },
    plugins: {
      react,
      "react-hooks": reactHooks,
      "jsx-a11y": jsxA11y,
      import: importPlugin,
      "@next/next": next,
      "@typescript-eslint": tseslint,
    },
    settings: {
      react: { version: "detect" },
    },
    rules: {
      ...react.configs.recommended.rules,
      ...(react.configs["jsx-runtime"].rules || {}),
      ...reactHooks.configs["recommended-latest"].rules,
      ...jsxA11y.configs.recommended.rules,
      ...nextRules,
      "import/no-anonymous-default-export": "warn",

      // Rule overrides that eslint-config-next applies on top of the
      // recommended presets (see eslint-config-next/index.js).
      "react/no-unknown-property": "off",
      "react/react-in-jsx-scope": "off",
      "react/prop-types": "off",
      "react/jsx-no-target-blank": "off",
      "jsx-a11y/alt-text": ["warn", { elements: ["img"], img: ["Image"] }],
      "jsx-a11y/aria-props": "warn",
      "jsx-a11y/aria-proptypes": "warn",
      "jsx-a11y/aria-unsupported-elements": "warn",
      "jsx-a11y/role-has-required-aria-props": "warn",
      "jsx-a11y/role-supports-aria-props": "warn",

      // The app deliberately uses clickable <div role> cards; keep these as
      // warnings so they stay visible without failing lint/builds.
      "jsx-a11y/click-events-have-key-events": "warn",
      "jsx-a11y/no-static-element-interactions": "warn",
      "jsx-a11y/label-has-associated-control": "warn",
      "react/no-unescaped-entities": "warn",

      // Project-specific overrides (previously in .eslintrc.json)
      "react-hooks/exhaustive-deps": "warn",
      "react-hooks/set-state-in-effect": "off",
      "@typescript-eslint/no-unused-vars": "warn",
    },
  },
]);