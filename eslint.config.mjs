import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    // TODO(fe-kit maintainers): un-ignore fe-gate — 28 strictTypeChecked errors remain
    // (6 complexity, ~13 no-restricted-syntax `in`, ~9 no-unsafe-member-access).
    ignores: ["node_modules/**", "extensions/nested-if.ts", "extensions/fe-gate*.ts"],
  },
  ...tseslint.configs.strictTypeChecked,
  {
    languageOptions: {
      parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname },
    },
    rules: {
      "@typescript-eslint/no-explicit-any": "error",
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "no-console": "error",
      "max-depth": ["error", 3],
      complexity: ["error", 10],
      "max-lines-per-function": ["error", 60],
      "no-restricted-syntax": [
        "error",
        { selector: "ForInStatement", message: "Dùng Object.entries/Map; for...in đọc cả prototype." },
        { selector: "BinaryExpression[operator='in']", message: "Dùng Object.hasOwn (F-016)." },
      ],
      "no-restricted-imports": [
        "error",
        { patterns: [{ group: ["**/fixtures/**"], message: "Fixture kiểm thử tool review, không import." }] },
      ],
    },
  },
  {
    files: ["**/*.test.ts"],
    rules: {
      "max-lines-per-function": "off",
      "max-depth": "off",
      complexity: "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/no-confusing-void-expression": "off",
    },
  },
);
