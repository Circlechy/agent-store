<template>
  <NConfigProvider>
    <NMessageProvider>
      <ChatView />
    </NMessageProvider>
  </NConfigProvider>
</template>

<script setup>
import { NConfigProvider, NMessageProvider } from "naive-ui";
import ChatView from "./views/ChatView.vue";
</script>
