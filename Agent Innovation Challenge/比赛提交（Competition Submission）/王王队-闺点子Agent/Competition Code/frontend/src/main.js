import { createApp } from "vue";
import { create } from "naive-ui";

import App from "./App.vue";
import "./assets/styles/global.css";

const app = createApp(App);
const naive = create();

app.use(naive);
app.mount("#app");
