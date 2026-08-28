import { createApp } from "vue";
import App from "./App.vue";
import router from "./router";

// 自托管字体(校园网/演示现场可能访问不了 Google Fonts)
import "@fontsource/fraunces/400.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/jetbrains-mono/400.css";
import "@fontsource/noto-serif-sc/400.css";
import "@fontsource/noto-serif-sc/600.css";

import "./style.css";

createApp(App).use(router).mount("#app");
