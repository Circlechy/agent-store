export default {
  root: true,
  env: {
    browser: true,
    es2024: true
  },
  parserOptions: {
    ecmaVersion: 2024,
    sourceType: 'module'
  },
  extends: ['eslint:recommended', 'plugin:vue/vue3-recommended', 'prettier'],
  rules: {}
};
