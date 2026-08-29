import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import "react-toastify/dist/ReactToastify.css";
import { ToastContainer } from "react-toastify";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// Self-hosted fonts (no external request at runtime)
import "@fontsource/inter/400.css";
import "@fontsource/inter/500.css";
import "@fontsource/inter/600.css";
import "@fontsource/inter/700.css";
import "@fontsource/fraunces/400.css";
import "@fontsource/fraunces/500.css";
import "@fontsource/fraunces/600.css";
import "@fontsource/fraunces/700.css";

import "./index.css";

import "./i18n/config";

import { router } from "./routes/index.tsx";
import { SYSTEM_NAME } from "./lib/system";

document.title = SYSTEM_NAME;

// Register the app-shell service worker so the PWA can be installed and
// launches to the sign-in page. Skip it in local dev to avoid cache noise.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      /** Service workers are an enhancement; never block the app on them. */
    });
  });
}

// Keep displayed tables current across navigation, focus changes, and updates
// made by other staff members. Mutations below still invalidate immediately.
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 15_000,
      refetchOnMount: true,
      refetchOnWindowFocus: "always",
      refetchOnReconnect: "always",
      refetchInterval: 30_000,
    },
  },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
      <ToastContainer />
    </QueryClientProvider>
  </React.StrictMode>,
);
