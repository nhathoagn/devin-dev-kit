import tseslint from "typescript-eslint";

export default tseslint.config(
  {
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
        { patterns: [{ group: ["**/nested-if*"], message: "Fixture đối chứng, không import." }] },
      ],
    },
  },
  {
    files: ["extensions/checkout/**/*.test.ts"],
    rules: {
      "max-lines-per-function": "off",
      "max-depth": "off",
      complexity: "off",
      "@typescript-eslint/require-await": "off",
      "@typescript-eslint/no-floating-promises": "off",
      "@typescript-eslint/no-confusing-void-expression": "off",
    },
  },
  {
    files: ["extensions/checkout/**/*.ts"],
    ignores: ["extensions/checkout/canonical.ts", "extensions/checkout/**/*.test.ts"],
    rules: {
      "no-restricted-properties": [
        "error",
        { object: "JSON", property: "stringify", message: "Key/digest chỉ tạo trong canonical.ts (F-019, F-034)." },
      ],
    },
  },
);
